"""Checkout orchestration (cloud only). Safe to call from worker threads."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Optional

from app.api.cloud_client import CloudClient, CloudClientError
from app.logging_setup import log_event
from app.models.cart import Cart
from app.models.order import (
    OrderStatus,
    is_cancellable,
    is_terminal,
    normalize_order_status,
    user_message_for_status,
)
from app.state.order_store import ActiveOrder, ActiveOrderStore

logger = logging.getLogger(__name__)


@dataclass
class PollResult:
    status: OrderStatus
    raw_status: Optional[str]
    message: str
    terminal: bool
    attempts: int


class CheckoutService:
    def __init__(
        self,
        cloud: CloudClient,
        *,
        machine_id: str,
        order_store: ActiveOrderStore,
        poll_interval_seconds: float = 2.0,
        poll_max_attempts: int = 90,
    ):
        self.cloud = cloud
        self.machine_id = machine_id
        self.order_store = order_store
        self.poll_interval_seconds = poll_interval_seconds
        self.poll_max_attempts = poll_max_attempts

    def start_checkout(self, cart: Cart) -> str:
        items = cart.to_order_items()
        if not items:
            raise ValueError("Cart is empty")
        amount_cents = cart.total_cents()
        if amount_cents <= 0:
            raise ValueError("Cart total must be positive")

        created = self.cloud.create_order(
            machine_id=self.machine_id,
            items=items,
            amount_cents=amount_cents,
        )
        order_id = str(created.get("order_id") or "")
        if not order_id:
            raise CloudClientError("create_order missing order_id")

        self.order_store.save(
            ActiveOrder(
                order_id=order_id,
                amount_cents=amount_cents,
                machine_id=self.machine_id,
            )
        )
        log_event(
            logger,
            "checkout.created",
            order_id=order_id,
            machine_id=self.machine_id,
            item_count=len(items),
            amount_cents=amount_cents,
        )

        self.cloud.start_payment(order_id)
        log_event(logger, "checkout.payment_started", order_id=order_id)
        return order_id

    def poll_once(self, order_id: str, *, attempt: int) -> PollResult:
        data = self.cloud.get_order(order_id)
        raw = data.get("status")
        status = normalize_order_status(raw if isinstance(raw, str) else None)
        return PollResult(
            status=status,
            raw_status=raw if isinstance(raw, str) else None,
            message=user_message_for_status(status),
            terminal=is_terminal(status),
            attempts=attempt,
        )

    def poll_until_terminal(
        self,
        order_id: str,
        *,
        on_update: Optional[Callable[[PollResult], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> PollResult:
        last = PollResult(
            status=OrderStatus.UNKNOWN,
            raw_status=None,
            message="Checking order status…",
            terminal=False,
            attempts=0,
        )
        for attempt in range(1, self.poll_max_attempts + 1):
            if should_stop and should_stop():
                return last
            last = self.poll_once(order_id, attempt=attempt)
            if on_update:
                on_update(last)
            if last.terminal:
                self.order_store.clear()
                return last
            time.sleep(self.poll_interval_seconds)

        timed_out = PollResult(
            status=OrderStatus.UNKNOWN,
            raw_status=last.raw_status,
            message=(
                "Payment/vend started, but final status was not confirmed. "
                "Please ask staff for help."
            ),
            terminal=True,
            attempts=self.poll_max_attempts,
        )
        # Keep active order for recovery — status may still settle.
        if on_update:
            on_update(timed_out)
        return timed_out

    def cancel_if_allowed(self, order_id: str, current_status: Optional[OrderStatus]) -> bool:
        status = current_status or OrderStatus.CREATED
        if not is_cancellable(status):
            log_event(
                logger,
                "checkout.cancel_blocked",
                order_id=order_id,
                status=status.value,
            )
            return False
        self.cloud.cancel_order(order_id)
        self.order_store.clear()
        log_event(logger, "checkout.cancelled", order_id=order_id)
        return True

    def resume_if_needed(self) -> Optional[str]:
        """
        On startup: if a persisted order exists and is non-terminal, return its id
        so the UI can resume polling before allowing a new checkout.
        """
        active = self.order_store.load()
        if not active:
            return None
        try:
            data = self.cloud.get_order(active.order_id)
        except CloudClientError:
            # Keep file; UI should show recovery/waiting.
            return active.order_id
        status = normalize_order_status(data.get("status") if isinstance(data.get("status"), str) else None)
        if is_terminal(status):
            self.order_store.clear()
            return None
        log_event(
            logger,
            "checkout.resume",
            order_id=active.order_id,
            status=status.value,
        )
        return active.order_id

"""Checkout orchestration (cloud only). Safe to call from worker threads."""

from __future__ import annotations

import logging
import time
from threading import Lock
from dataclasses import dataclass
from typing import Callable, Optional

from app.api.cloud_client import CloudClient, CloudClientError
from app.logging_setup import log_event
from app.models.cart import Cart
from app.models.order import (
    OrderStatus,
    is_cancellable,
    normalize_order_status,
    user_message_for_status,
)
from app.state.order_store import ActiveOrder, ActiveOrderStore

logger = logging.getLogger(__name__)

CHECKING_PAYMENT = "Please wait. We’re checking your payment."
PAYMENT_UNCONFIRMED = "We couldn’t confirm your payment yet. Please ask staff for help."



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
        self._checkout_lock = Lock()

    def current_order_id(self) -> Optional[str]:
        active = self.order_store.load()
        return active.order_id if active else None

    def start_checkout(self, cart: Cart) -> str:
        with self._checkout_lock:
            if self.current_order_id():
                raise CloudClientError("The previous checkout is unresolved")
            return self._start_checkout_locked(cart)

    def _start_checkout_locked(self, cart: Cart) -> str:
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
        bound = data.get("order_id") == order_id and data.get("machine_id") == self.machine_id
        status = normalize_order_status(raw if isinstance(raw, str) and bound else None)
        has_vend = bool(data.get("vend_job_id"))
        no_payment_review = not data.get("payment_recovery") and not data.get("operator_review")
        # A payment-only success webhook can also write COMPLETED. Require the
        # settled vend fields before dismissing recovery. A bare decline or
        # cancellation is not proof that a new collection is safe.
        terminal = bound and has_vend and no_payment_review and (
            (raw == "COMPLETED" and data.get("payment_status") == "captured"
             and data.get("physical_outcome") in ("dispensed", "partial"))
            or (raw == "FAILED" and data.get("payment_status") == "cancelled"
                and data.get("physical_outcome") == "not_dispensed")
        )
        if not terminal and status in {
            OrderStatus.UNKNOWN, OrderStatus.COMPLETED, OrderStatus.PAYMENT_FAILED,
            OrderStatus.FAILED, OrderStatus.CANCELLED,
        }:
            status = OrderStatus.UNKNOWN
        return PollResult(
            status=status,
            raw_status=raw if isinstance(raw, str) else None,
            message=CHECKING_PAYMENT if status == OrderStatus.UNKNOWN else user_message_for_status(status),
            terminal=terminal,
            attempts=attempt,
        )

    def _clear_if_same_order(self, order_id: str) -> None:
        with self._checkout_lock:
            if self.current_order_id() == order_id:
                self.order_store.clear()

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
            message=CHECKING_PAYMENT,
            terminal=False,
            attempts=0,
        )
        for attempt in range(1, self.poll_max_attempts + 1):
            if should_stop and should_stop():
                return last
            try:
                last = self.poll_once(order_id, attempt=attempt)
            except CloudClientError:
                # A lost read is not proof of failure or permission to collect again.
                last = PollResult(OrderStatus.UNKNOWN, None, CHECKING_PAYMENT, False, attempt)
            if on_update:
                on_update(last)
            if last.terminal:
                self._clear_if_same_order(order_id)
                return last
            time.sleep(self.poll_interval_seconds)

        timed_out = PollResult(
            status=OrderStatus.UNKNOWN,
            raw_status=last.raw_status,
            message=PAYMENT_UNCONFIRMED,
            terminal=False,
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
        log_event(logger, "checkout.cancel_requested", order_id=order_id)
        return True

    def cancel_wait_timeout(self, order_id: str) -> str:
        """
        Ask Cloud to release an AUTHORIZED hold after the vend wait expires.

        Returns:
          "cancelled" — order/PI cancelled
          "vend_in_progress" — Pi already claimed (HTTP 409); keep polling
        """
        try:
            self.cloud.cancel_order(
                order_id,
                reason="Wait timed out",
                cancel_mode="wait_timeout",
            )
        except CloudClientError as exc:
            if exc.status_code == 409:
                log_event(
                    logger,
                    "checkout.wait_timeout_conflict",
                    order_id=order_id,
                    status_code=409,
                )
                return "vend_in_progress"
            raise
        log_event(logger, "checkout.wait_timeout_response", order_id=order_id)
        return "cancelled"

    def resume_if_needed(self) -> Optional[str]:
        """Resume the original order; do not start a replacement collection."""
        return self.current_order_id()

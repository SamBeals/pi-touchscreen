"""Application screen / checkout finite state machine (UI-agnostic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.models.order import (
    OrderStatus,
    is_cancellable,
    is_failure,
    is_success,
    is_terminal,
    normalize_order_status,
)


class AppScreen(str, Enum):
    BOOT = "boot"
    FATAL = "fatal"
    ATTRACT = "attract"
    BROWSE = "browse"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    PAYMENT = "payment"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class AppStateMachine:
    screen: AppScreen = AppScreen.BOOT
    selected_slot_id: Optional[str] = None
    active_order_id: Optional[str] = None
    last_order_status: Optional[OrderStatus] = None
    status_message: str = ""
    error_message: str = ""
    cloud_reachable: bool = False
    inventory_fresh: bool = False
    fatal_reason: str = ""
    poll_attempts: int = 0

    def can_checkout(self) -> bool:
        return self.cloud_reachable and self.inventory_fresh

    def boot_ok(self) -> None:
        self.screen = AppScreen.ATTRACT
        self.fatal_reason = ""

    def boot_fatal(self, reason: str) -> None:
        self.screen = AppScreen.FATAL
        self.fatal_reason = reason

    def go_attract(self) -> None:
        self.screen = AppScreen.ATTRACT
        self.selected_slot_id = None
        self.error_message = ""

    def go_browse(self) -> None:
        self.screen = AppScreen.BROWSE
        self.selected_slot_id = None

    def open_product(self, slot_id: str) -> None:
        self.selected_slot_id = slot_id
        self.screen = AppScreen.PRODUCT_DETAIL

    def go_cart(self) -> None:
        self.screen = AppScreen.CART

    def begin_payment(self, order_id: str) -> None:
        self.active_order_id = order_id
        self.poll_attempts = 0
        self.last_order_status = OrderStatus.CREATED
        self.status_message = "Preparing checkout…"
        self.error_message = ""
        self.screen = AppScreen.PAYMENT

    def update_payment_status(self, raw_status: Optional[str]) -> OrderStatus:
        status = normalize_order_status(raw_status)
        self.last_order_status = status
        self.poll_attempts += 1
        return status

    def mark_success(self) -> None:
        self.screen = AppScreen.SUCCESS
        self.status_message = "Purchase complete."

    def mark_failure(self, message: str) -> None:
        self.screen = AppScreen.FAILURE
        self.error_message = message

    def clear_active_order(self) -> None:
        self.active_order_id = None
        self.last_order_status = None
        self.poll_attempts = 0

    def cancel_allowed(self) -> bool:
        if self.screen != AppScreen.PAYMENT:
            return False
        if self.last_order_status is None:
            return True  # before first poll; still pre-vend
        return is_cancellable(self.last_order_status)

    def apply_terminal(self, status: OrderStatus) -> None:
        if is_success(status):
            self.mark_success()
        elif is_failure(status):
            self.mark_failure(
                {
                    OrderStatus.PAYMENT_FAILED: "Payment failed. Please try again.",
                    OrderStatus.FAILED: "Vend failed. Your payment was not captured.",
                    OrderStatus.CANCELLED: "Purchase cancelled.",
                }.get(status, "Checkout failed.")
            )


def checkout_gate_reason(*, cloud_reachable: bool, inventory_fresh: bool) -> Optional[str]:
    if not cloud_reachable:
        return "Cloud is unreachable. Checkout is unavailable."
    if not inventory_fresh:
        return "Inventory is stale. Refresh before checkout."
    return None

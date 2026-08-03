"""Order status normalization for SellMateCloud lifecycle."""

from __future__ import annotations

from enum import Enum
from typing import Optional


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    AUTHORIZING = "AUTHORIZING"
    AUTHORIZED = "AUTHORIZED"
    VENDING = "VENDING"
    COMPLETED = "COMPLETED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


# Primary Cloud statuses plus Android/legacy aliases.
_ALIASES = {
    "CREATED": OrderStatus.CREATED,
    "AUTHORIZING": OrderStatus.AUTHORIZING,
    "PAYMENT_STARTED": OrderStatus.AUTHORIZING,  # legacy Android
    "AUTHORIZED": OrderStatus.AUTHORIZED,
    "VENDING": OrderStatus.VENDING,
    "CAPTURING": OrderStatus.VENDING,  # mid-complete; still in flight
    "COMPLETED": OrderStatus.COMPLETED,
    "COMPLETE": OrderStatus.COMPLETED,
    "VEND_COMPLETED": OrderStatus.COMPLETED,
    "VEND_SUCCESS": OrderStatus.COMPLETED,
    "SUCCEEDED": OrderStatus.COMPLETED,
    "PAID": OrderStatus.COMPLETED,  # legacy
    "PAYMENT_FAILED": OrderStatus.PAYMENT_FAILED,
    "FAILED": OrderStatus.FAILED,
    "VEND_FAILED": OrderStatus.FAILED,
    "CANCELLED": OrderStatus.CANCELLED,
    "CANCELED": OrderStatus.CANCELLED,
}


def normalize_order_status(raw: Optional[str]) -> OrderStatus:
    if not raw:
        return OrderStatus.UNKNOWN
    return _ALIASES.get(raw.strip().upper(), OrderStatus.UNKNOWN)


def is_terminal(status: OrderStatus) -> bool:
    return status in {
        OrderStatus.COMPLETED,
        OrderStatus.FAILED,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.CANCELLED,
    }


def is_success(status: OrderStatus) -> bool:
    return status == OrderStatus.COMPLETED


def is_failure(status: OrderStatus) -> bool:
    return status in {
        OrderStatus.FAILED,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.CANCELLED,
    }


def is_cancellable(status: OrderStatus) -> bool:
    """
    Cancel is safe only before a vend_job exists.

    AUTHORIZED is intentionally excluded: Cloud already created a PENDING
    vend_job, and cancel races with Pi claim (Cloud cancel does not
    transactionally prevent claim). Once AUTHORIZED/VENDING, hide Cancel.
    """
    return status in {
        OrderStatus.CREATED,
        OrderStatus.AUTHORIZING,
    }


def user_message_for_status(status: OrderStatus) -> str:
    return {
        OrderStatus.CREATED: "Preparing checkout…",
        OrderStatus.AUTHORIZING: "Waiting for card…",
        OrderStatus.AUTHORIZED: "Payment authorized. Preparing to vend…",
        OrderStatus.VENDING: "Vending your item…",
        OrderStatus.COMPLETED: "Purchase complete.",
        OrderStatus.PAYMENT_FAILED: "Payment failed. Please try again.",
        OrderStatus.FAILED: "Vend failed. Your payment was not captured.",
        OrderStatus.CANCELLED: "Purchase cancelled.",
        OrderStatus.UNKNOWN: "Processing order…",
    }[status]

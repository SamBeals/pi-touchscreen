from __future__ import annotations

import unittest

from app.models.order import (
    OrderStatus,
    is_cancellable,
    is_terminal,
    normalize_order_status,
)


class TestOrderStatus(unittest.TestCase):
    def test_primary_statuses(self):
        for name in (
            "CREATED",
            "AUTHORIZING",
            "AUTHORIZED",
            "VENDING",
            "COMPLETED",
            "PAYMENT_FAILED",
            "FAILED",
            "CANCELLED",
        ):
            self.assertEqual(normalize_order_status(name), OrderStatus[name])

    def test_legacy_aliases(self):
        self.assertEqual(normalize_order_status("PAID"), OrderStatus.COMPLETED)
        self.assertEqual(normalize_order_status("PAYMENT_STARTED"), OrderStatus.AUTHORIZING)
        self.assertEqual(normalize_order_status("VEND_FAILED"), OrderStatus.FAILED)

    def test_cancellable_before_vend_job_only(self):
        self.assertTrue(is_cancellable(OrderStatus.CREATED))
        self.assertTrue(is_cancellable(OrderStatus.AUTHORIZING))
        # AUTHORIZED already has a PENDING vend_job — UI must not cancel.
        self.assertFalse(is_cancellable(OrderStatus.AUTHORIZED))
        self.assertFalse(is_cancellable(OrderStatus.VENDING))
        self.assertFalse(is_cancellable(OrderStatus.COMPLETED))

    def test_terminal(self):
        self.assertTrue(is_terminal(OrderStatus.COMPLETED))
        self.assertTrue(is_terminal(OrderStatus.FAILED))
        self.assertFalse(is_terminal(OrderStatus.VENDING))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.models.cart import Cart
from app.models.order import OrderStatus
from app.models.product import Product
from app.state.checkout_service import CheckoutService
from app.state.order_store import ActiveOrder, ActiveOrderStore


class TestCheckoutService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ActiveOrderStore(
            Path(self.tmp.name) / "active.json",
            expected_machine_id="machine_002",
        )
        self.cloud = MagicMock()
        self.service = CheckoutService(
            self.cloud,
            machine_id="machine_002",
            order_store=self.store,
            poll_interval_seconds=0.0,
            poll_max_attempts=3,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_start_checkout_uses_cart_total(self):
        cart = Cart()
        cart.add(Product("S01", "A", 150, 5), 2)
        self.cloud.create_order.return_value = {"order_id": "ord-1", "status": "CREATED"}
        self.cloud.start_payment.return_value = {"status": "AUTHORIZING"}

        order_id = self.service.start_checkout(cart)
        self.assertEqual(order_id, "ord-1")
        kwargs = self.cloud.create_order.call_args.kwargs
        self.assertEqual(kwargs["amount_cents"], 300)
        self.assertEqual(kwargs["machine_id"], "machine_002")
        self.assertEqual(self.store.load().order_id, "ord-1")

    def test_poll_until_terminal(self):
        self.cloud.get_order.side_effect = [
            {"status": "AUTHORIZING"},
            {"status": "VENDING"},
            {"status": "COMPLETED"},
        ]
        result = self.service.poll_until_terminal("ord-1")
        self.assertEqual(result.status, OrderStatus.COMPLETED)
        self.assertTrue(result.terminal)
        self.assertIsNone(self.store.load())

    def test_cancel_blocked_when_vending(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        ok = self.service.cancel_if_allowed("ord-1", OrderStatus.VENDING)
        self.assertFalse(ok)
        self.cloud.cancel_order.assert_not_called()
        self.assertIsNotNone(self.store.load())

    def test_cancel_blocked_when_authorized(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        ok = self.service.cancel_if_allowed("ord-1", OrderStatus.AUTHORIZED)
        self.assertFalse(ok)
        self.cloud.cancel_order.assert_not_called()

    def test_cancel_allowed_when_authorizing(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        self.cloud.cancel_order.return_value = {"status": "CANCELLED"}
        ok = self.service.cancel_if_allowed("ord-1", OrderStatus.AUTHORIZING)
        self.assertTrue(ok)
        self.cloud.cancel_order.assert_called_once()
        self.assertIsNone(self.store.load())

    def test_resume_clears_terminal_orders(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        self.cloud.get_order.return_value = {"status": "COMPLETED"}
        self.assertIsNone(self.service.resume_if_needed())
        self.assertIsNone(self.store.load())

    def test_resume_returns_open_order(self):
        self.store.save(ActiveOrder("ord-9", 100, "machine_002"))
        self.cloud.get_order.return_value = {"status": "AUTHORIZING"}
        self.assertEqual(self.service.resume_if_needed(), "ord-9")


if __name__ == "__main__":
    unittest.main()

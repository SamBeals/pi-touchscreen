from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.api.cloud_client import CloudClientError
from app.models.cart import Cart
from app.models.order import OrderStatus
from app.models.product import Product
from app.state.checkout_service import CHECKING_PAYMENT, PAYMENT_UNCONFIRMED, CheckoutService
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

    def order(self, status, **fields):
        return {"order_id": "ord-1", "machine_id": "machine_002", "status": status, **fields}

    def test_poll_until_terminal(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        self.cloud.get_order.side_effect = [
            self.order("AUTHORIZING"),
            self.order("VENDING"),
            self.order("COMPLETED", vend_job_id="job-1", physical_outcome="dispensed",
                       payment_status="captured"),
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
        self.assertEqual(self.store.load().order_id, "ord-1")

    def test_restart_does_not_drop_status_only_completion(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        self.cloud.get_order.return_value = self.order("COMPLETED")
        self.assertEqual(self.service.resume_if_needed(), "ord-1")
        result = self.service.poll_until_terminal("ord-1")
        self.assertFalse(result.terminal)
        self.assertEqual(result.message, PAYMENT_UNCONFIRMED)
        self.assertEqual(self.store.load().order_id, "ord-1")

    def test_resume_returns_open_order(self):
        self.store.save(ActiveOrder("ord-9", 100, "machine_002"))
        self.cloud.get_order.return_value = {"status": "AUTHORIZING"}
        self.assertEqual(self.service.resume_if_needed(), "ord-9")

    def test_lost_start_reply_persists_original_and_blocks_replacement(self):
        cart = Cart()
        cart.add(Product("S01", "A", 150, 5), 1)
        self.cloud.create_order.return_value = {"order_id": "ord-1"}
        self.cloud.start_payment.side_effect = CloudClientError("lost reply")
        with self.assertRaises(CloudClientError):
            self.service.start_checkout(cart)
        self.assertEqual(self.service.resume_if_needed(), "ord-1")
        with self.assertRaises(CloudClientError):
            self.service.start_checkout(cart)
        self.cloud.create_order.assert_called_once()
        self.cloud.start_payment.assert_called_once_with("ord-1")

    def test_nonfinal_responses_never_clear_even_when_no_job_is_listed(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        for status in ("PAYMENT_FAILED", "FAILED", "CANCELLED"):
            with self.subTest(status=status):
                self.cloud.get_order.return_value = self.order(status)
                observed = self.service.poll_once("ord-1", attempt=1)
                self.assertFalse(observed.terminal)
                self.assertEqual(observed.message, CHECKING_PAYMENT)
                self.assertEqual(self.store.load().order_id, "ord-1")

    def test_lost_read_then_late_authorization_and_complete_original(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        self.cloud.get_order.side_effect = [
            CloudClientError("offline"),
            self.order("AUTHORIZED", vend_job_id="job-1"),
            self.order("COMPLETED", vend_job_id="job-1", physical_outcome="dispensed",
                       payment_status="captured"),
        ]
        seen = []
        result = self.service.poll_until_terminal("ord-1", on_update=seen.append)
        self.assertEqual([r.status for r in seen], [
            OrderStatus.UNKNOWN, OrderStatus.AUTHORIZED, OrderStatus.COMPLETED])
        self.assertTrue(result.terminal)
        self.assertIsNone(self.store.load())
        self.cloud.start_payment.assert_not_called()
        self.cloud.create_order.assert_not_called()

    def test_stale_finished_poll_cannot_clear_a_different_order(self):
        self.store.save(ActiveOrder("ord-new", 100, "machine_002"))
        self.cloud.get_order.return_value = self.order(
            "COMPLETED", vend_job_id="job-1", physical_outcome="dispensed",
            payment_status="captured")
        self.service.poll_until_terminal("ord-1")
        self.assertEqual(self.store.load().order_id, "ord-new")

    def test_wrong_machine_or_order_is_not_authoritative(self):
        self.store.save(ActiveOrder("ord-1", 100, "machine_002"))
        for mismatch in ({"machine_id": "machine-other"}, {"order_id": "wrong"}):
            self.cloud.get_order.return_value = self.order("COMPLETED", **{
                "vend_job_id": "job-1", "physical_outcome": "dispensed",
                "payment_status": "captured", **mismatch})
            self.assertFalse(self.service.poll_once("ord-1", attempt=1).terminal)


if __name__ == "__main__":
    unittest.main()

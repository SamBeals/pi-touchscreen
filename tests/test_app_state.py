from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app.api.inventory_client import InventorySnapshot
from app.models.order import OrderStatus
from app.models.product import Product
from app.state.app_state import AppScreen, AppStateMachine, checkout_gate_reason


class TestAppState(unittest.TestCase):
    def test_screen_flow_happy_path(self):
        fsm = AppStateMachine()
        fsm.boot_ok()
        self.assertEqual(fsm.screen, AppScreen.ATTRACT)
        fsm.go_browse()
        fsm.open_product("S01")
        self.assertEqual(fsm.screen, AppScreen.PRODUCT_DETAIL)
        fsm.go_cart()
        fsm.begin_payment("ord-1")
        self.assertEqual(fsm.screen, AppScreen.PAYMENT)
        fsm.mark_success()
        self.assertEqual(fsm.screen, AppScreen.SUCCESS)

    def test_cancel_allowed_rules(self):
        fsm = AppStateMachine()
        fsm.begin_payment("ord-1")
        fsm.last_order_status = OrderStatus.AUTHORIZING
        self.assertTrue(fsm.cancel_allowed())
        fsm.last_order_status = OrderStatus.AUTHORIZED
        self.assertFalse(fsm.cancel_allowed())
        fsm.last_order_status = OrderStatus.VENDING
        self.assertFalse(fsm.cancel_allowed())

    def test_checkout_gate(self):
        self.assertIsNotNone(
            checkout_gate_reason(cloud_reachable=False, inventory_fresh=True)
        )
        self.assertIsNotNone(
            checkout_gate_reason(cloud_reachable=True, inventory_fresh=False)
        )
        self.assertIsNone(
            checkout_gate_reason(cloud_reachable=True, inventory_fresh=True)
        )

    def test_stale_inventory_blocks_checkout(self):
        old = datetime.now(timezone.utc) - timedelta(seconds=1000)
        snap = InventorySnapshot(
            products=[Product("S01", "A", 100, 1)],
            fetched_at=old,
            source="cache",
        )
        self.assertFalse(snap.is_fresh(300))
        reason = checkout_gate_reason(
            cloud_reachable=True, inventory_fresh=snap.is_fresh(300)
        )
        self.assertIn("stale", reason.lower())


if __name__ == "__main__":
    unittest.main()

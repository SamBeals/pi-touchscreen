"""Exercise the QML-facing slots with real Qt workers and no external services."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    from PySide6.QtCore import QCoreApplication
except ImportError:
    QCoreApplication = None

from app.api.cloud_client import CloudClientError
from app.config import load_settings
from app.models.product import Product
from app.state.app_state import AppScreen
from app.state.checkout_service import CHECKING_PAYMENT, PAYMENT_UNCONFIRMED
from app.state.order_store import ActiveOrder, ActiveOrderStore


@unittest.skipIf(QCoreApplication is None, "controller tests require PySide6")
class TestCheckoutRecoveryController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {
            "MACHINE_ID": "machine_test",
            "CLOUD_BASE": "https://example.invalid",
            "TOUCHSCREEN_DATA_DIR": self.tmp.name,
            "POLL_MAX_ATTEMPTS": "2",
            "POLL_INTERVAL_SECONDS": "0.01",
        }
        with patch.dict(os.environ, env, clear=True):
            self.settings = load_settings(load_machine_env_file=False)
        self.assertEqual(self.settings.data_dir, Path(self.tmp.name))
        self.store = ActiveOrderStore(self.settings.active_order_path, expected_machine_id="machine_test")
        self.cloud = MagicMock()
        self.inventory = MagicMock()
        # Recovery must still work on a cold kiosk with no usable inventory.
        self.inventory.load.side_effect = OSError("inventory unavailable")
        self.controllers = []
        self.addCleanup(self.close_controllers)

    def close_controllers(self):
        for controller in self.controllers:
            controller.shutdown()
            self.qt.processEvents()

    def controller(self):
        from app.ui.app_controller import AppController

        with patch("app.ui.app_controller.CloudClient", return_value=self.cloud), patch(
            "app.ui.app_controller.InventoryClient", return_value=self.inventory
        ):
            ctrl = AppController(self.settings)
        self.controllers.append(ctrl)
        return ctrl

    def wait_for(self, condition):
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            self.qt.processEvents()
            time.sleep(0.002)
        self.assertTrue(condition(), "Qt recovery state was not reached")

    def test_restart_offline_done_and_idle_keep_checkout_locked_then_late_result(self):
        self.store.save(ActiveOrder("original", 100, "machine_test"))
        self.cloud.get_order.side_effect = CloudClientError("offline")
        ctrl = self.controller()
        messages = []
        ctrl.statusChanged.connect(lambda: messages.append(ctrl.paymentMessage))
        self.wait_for(lambda: ctrl.paymentRecoveryHelp)
        self.assertIn(CHECKING_PAYMENT, messages)
        self.assertEqual(ctrl.resultMessage, PAYMENT_UNCONFIRMED)
        self.inventory.load.assert_not_called()
        ctrl.finishToAttract()
        ctrl._on_idle_timeout()
        ctrl.startCheckout()  # Delayed gesture from a previous screen.
        self.assertEqual(ctrl.fsm.screen, AppScreen.FAILURE)
        self.assertEqual(self.store.load().order_id, "original")
        self.cloud.create_order.assert_not_called()
        self.cloud.start_payment.assert_not_called()
        ctrl.shutdown()

        self.cloud.get_order.side_effect = [
            {"machine_id": "machine_test", "order_id": "original", "status": "AUTHORIZED"},
            {
                "machine_id": "machine_test", "order_id": "original", "status": "COMPLETED",
                "vend_job_id": "job-test", "physical_outcome": "dispensed",
                "payment_status": "captured",
            },
        ]
        resumed = self.controller()
        self.wait_for(lambda: resumed.fsm.screen == AppScreen.SUCCESS)
        resumed.startCheckout()  # Old queued gesture cannot restart after a late result.
        self.assertIsNone(self.store.load())
        self.assertTrue(all(c.args == ("original",) for c in self.cloud.get_order.call_args_list))
        self.cloud.create_order.assert_not_called()
        self.cloud.start_payment.assert_not_called()
        self.cloud.cancel_order.assert_not_called()

    def test_duplicate_cart_press_does_not_create_replacement_after_lost_start_reply(self):
        self.cloud.create_order.return_value = {"order_id": "original"}
        self.cloud.start_payment.side_effect = CloudClientError("lost start reply")
        self.cloud.get_order.return_value = {
            "machine_id": "machine_test", "order_id": "original", "status": "PAYMENT_FAILED"
        }
        ctrl = self.controller()
        # Run the same public checkout slot the cart button uses, without a
        # catalog or terminal; normal boot itself is not part of this case.
        ctrl._bootstrap = lambda: None
        ctrl.fsm.screen = AppScreen.CART
        ctrl.fsm.cloud_reachable = ctrl.fsm.inventory_fresh = True
        ctrl.cart.add(Product("S01", "Test product", 100, 1), 1)
        ctrl.startCheckout()
        ctrl.startCheckout()
        self.wait_for(lambda: ctrl.paymentRecoveryHelp)
        ctrl.checkPaymentStatus()
        self.wait_for(lambda: ctrl.paymentRecoveryHelp)
        self.assertEqual(self.store.load().order_id, "original")
        self.cloud.create_order.assert_called_once()
        self.cloud.start_payment.assert_called_once_with("original")

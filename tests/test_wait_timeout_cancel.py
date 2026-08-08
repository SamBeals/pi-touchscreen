"""Unit tests for wait-timeout cancel client + checkout service path."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.api.cloud_client import CloudClient, CloudClientError
from app.state.checkout_service import CheckoutService
from app.state.order_store import ActiveOrder, ActiveOrderStore


class TestCloudClientWaitTimeoutPayload(unittest.TestCase):
    def test_cancel_order_includes_cancel_mode(self):
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "CANCELLED", "cancel_mode": "wait_timeout"}
        session.request.return_value = resp
        client = CloudClient("https://example.test", session=session)

        result = client.cancel_order(
            "order-1",
            reason="Wait timed out",
            cancel_mode="wait_timeout",
        )

        self.assertEqual(result["status"], "CANCELLED")
        kwargs = session.request.call_args.kwargs
        self.assertEqual(
            kwargs["json"],
            {"reason": "Wait timed out", "cancel_mode": "wait_timeout"},
        )


class TestCheckoutWaitTimeout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "active_order.json"
        self.store = ActiveOrderStore(path, expected_machine_id="machine_001")
        self.cloud = MagicMock()
        self.service = CheckoutService(
            self.cloud,
            machine_id="machine_001",
            order_store=self.store,
        )
        self.store.save(
            ActiveOrder(
                order_id="order-1",
                amount_cents=50,
                machine_id="machine_001",
            )
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_cancel_wait_timeout_clears_store(self):
        self.cloud.cancel_order.return_value = {"status": "CANCELLED"}

        result = self.service.cancel_wait_timeout("order-1")

        self.assertEqual(result, "cancelled")
        self.cloud.cancel_order.assert_called_once_with(
            "order-1",
            reason="Wait timed out",
            cancel_mode="wait_timeout",
        )
        self.assertIsNone(self.store.load())

    def test_cancel_wait_timeout_409_keeps_store(self):
        self.cloud.cancel_order.side_effect = CloudClientError(
            "Cloud returned HTTP 409",
            status_code=409,
        )

        result = self.service.cancel_wait_timeout("order-1")

        self.assertEqual(result, "vend_in_progress")
        self.assertIsNotNone(self.store.load())


class TestVendWaitConfig(unittest.TestCase):
    def test_default_vend_wait_seconds(self):
        import os
        from unittest.mock import patch

        from app.config import load_settings

        env = {k: v for k, v in os.environ.items()}
        env["MACHINE_ID"] = "machine_002"
        env["CLOUD_BASE"] = "https://example.run.app"
        env.pop("VEND_WAIT_SECONDS", None)
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings(load_machine_env_file=False)
        self.assertEqual(settings.vend_wait_seconds, 60.0)


if __name__ == "__main__":
    unittest.main()

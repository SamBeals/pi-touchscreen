"""Lightweight checks that polling stop semantics are available without Qt GUI."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.state.checkout_service import CheckoutService
from app.state.order_store import ActiveOrderStore
from pathlib import Path
import tempfile


class TestPollStopFlag(unittest.TestCase):
    def test_poll_until_terminal_honors_should_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ActiveOrderStore(
                Path(tmp) / "a.json", expected_machine_id="machine_002"
            )
            cloud = MagicMock()
            cloud.get_order.return_value = {"status": "AUTHORIZING"}
            service = CheckoutService(
                cloud,
                machine_id="machine_002",
                order_store=store,
                poll_interval_seconds=0.0,
                poll_max_attempts=10,
            )
            calls = {"n": 0}

            def should_stop() -> bool:
                calls["n"] += 1
                return calls["n"] >= 2

            result = service.poll_until_terminal(
                "ord-1", should_stop=should_stop
            )
            self.assertFalse(result.terminal)
            self.assertLess(cloud.get_order.call_count, 10)


if __name__ == "__main__":
    unittest.main()

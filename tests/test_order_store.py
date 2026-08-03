from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.state.order_store import ActiveOrder, ActiveOrderStore


class TestOrderStore(unittest.TestCase):
    def test_persist_and_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ActiveOrderStore(
                Path(tmp) / "active.json", expected_machine_id="machine_002"
            )
            self.assertIsNone(store.load())
            store.save(ActiveOrder("ord-1", 500, "machine_002"))
            loaded = store.load()
            self.assertEqual(loaded.order_id, "ord-1")
            self.assertEqual(loaded.amount_cents, 500)
            store.clear()
            self.assertIsNone(store.load())

    def test_atomic_replace_leaves_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "active.json"
            store = ActiveOrderStore(path, expected_machine_id="machine_002")
            store.save(ActiveOrder("ord-1", 100, "machine_002"))
            store.save(ActiveOrder("ord-2", 200, "machine_002"))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["order_id"], "ord-2")
            # No leftover temp files
            leftovers = list(Path(tmp).glob("active_order.*.tmp"))
            self.assertEqual(leftovers, [])

    def test_corrupted_file_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "active.json"
            path.write_text("{not-json", encoding="utf-8")
            store = ActiveOrderStore(path, expected_machine_id="machine_002")
            self.assertIsNone(store.load())
            # Corrupted file removed so boot can continue cleanly
            self.assertFalse(path.exists())

    def test_truncated_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "active.json"
            path.write_text("   \n", encoding="utf-8")
            store = ActiveOrderStore(path, expected_machine_id="machine_002")
            self.assertIsNone(store.load())

    def test_machine_id_mismatch_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "active.json"
            path.write_text(
                json.dumps(
                    {
                        "order_id": "ord-x",
                        "amount_cents": 1,
                        "machine_id": "machine_999",
                    }
                ),
                encoding="utf-8",
            )
            store = ActiveOrderStore(path, expected_machine_id="machine_002")
            self.assertIsNone(store.load())
            # File preserved (do not destroy another machine's record)
            self.assertTrue(path.exists())

    def test_save_rejects_mismatched_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ActiveOrderStore(
                Path(tmp) / "active.json", expected_machine_id="machine_002"
            )
            with self.assertRaises(ValueError):
                store.save(ActiveOrder("ord-1", 1, "machine_999"))


if __name__ == "__main__":
    unittest.main()

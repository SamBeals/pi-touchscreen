from __future__ import annotations

import unittest

from app.api.inventory_client import merge_slot_docs


class TestInventoryMerge(unittest.TestCase):
    def test_merge_prefers_inventory_fields(self):
        plan = {"S01": {"enabled": True, "name": "Plan Name"}}
        inv = {
            "S01": {
                "name": "Live Name",
                "price_cents": 199,
                "qty": 3,
                "enabled": True,
                "imageUrl": "https://example.com/a.png",
            }
        }
        products = merge_slot_docs(plan, inv)
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "Live Name")
        self.assertEqual(products[0].price_cents, 199)
        self.assertEqual(products[0].qty, 3)
        self.assertTrue(products[0].sellable)


if __name__ == "__main__":
    unittest.main()

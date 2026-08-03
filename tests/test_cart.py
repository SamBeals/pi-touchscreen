from __future__ import annotations

import unittest

from app.models.cart import Cart
from app.models.product import Product


def _product(slot: str, price: int = 100, qty: int = 5) -> Product:
    return Product(slot_id=slot, name=f"Item {slot}", price_cents=price, qty=qty)


class TestCart(unittest.TestCase):
    def test_total_from_inventory_prices(self):
        cart = Cart()
        cart.add(_product("S01", price=250), 2)
        cart.add(_product("S02", price=100), 1)
        self.assertEqual(cart.total_cents(), 600)
        self.assertEqual(
            cart.to_order_items(),
            [{"slot_id": "S01", "qty": 2}, {"slot_id": "S02", "qty": 1}],
        )

    def test_rejects_over_stock(self):
        cart = Cart()
        with self.assertRaises(ValueError):
            cart.add(_product("S01", qty=1), 2)

    def test_rejects_unsellable(self):
        cart = Cart()
        with self.assertRaises(ValueError):
            cart.add(Product("S01", "X", 100, qty=0, enabled=True))

    def test_clear(self):
        cart = Cart()
        cart.add(_product("S01"), 1)
        cart.clear()
        self.assertEqual(cart.item_count(), 0)


if __name__ == "__main__":
    unittest.main()

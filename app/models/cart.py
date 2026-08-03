from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping

from .product import Product


@dataclass
class CartLine:
    product: Product
    quantity: int

    @property
    def line_total_cents(self) -> int:
        return self.product.price_cents * self.quantity


@dataclass
class Cart:
    """In-memory cart. Totals always derived from Product.price_cents."""

    _lines: Dict[str, CartLine] = field(default_factory=dict)

    def clear(self) -> None:
        self._lines.clear()

    def lines(self) -> List[CartLine]:
        return list(self._lines.values())

    def item_count(self) -> int:
        return sum(line.quantity for line in self._lines.values())

    def total_cents(self) -> int:
        return sum(line.line_total_cents for line in self._lines.values())

    def to_order_items(self) -> List[dict]:
        return [
            {"slot_id": line.product.slot_id, "qty": line.quantity}
            for line in self._lines.values()
            if line.quantity > 0
        ]

    def add(self, product: Product, quantity: int = 1) -> None:
        if not product.sellable:
            raise ValueError("Product is not sellable")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        existing = self._lines.get(product.slot_id)
        new_qty = (existing.quantity if existing else 0) + quantity
        if new_qty > product.qty:
            raise ValueError("Quantity exceeds available stock")
        self._lines[product.slot_id] = CartLine(product=product, quantity=new_qty)

    def set_quantity(self, slot_id: str, quantity: int, catalog: Mapping[str, Product]) -> None:
        if quantity <= 0:
            self._lines.pop(slot_id, None)
            return
        product = catalog.get(slot_id)
        if product is None:
            raise KeyError(slot_id)
        if quantity > product.qty:
            raise ValueError("Quantity exceeds available stock")
        self._lines[slot_id] = CartLine(product=product, quantity=quantity)

    def remove_one(self, slot_id: str) -> None:
        line = self._lines.get(slot_id)
        if not line:
            return
        if line.quantity <= 1:
            self._lines.pop(slot_id, None)
        else:
            self._lines[slot_id] = CartLine(
                product=line.product, quantity=line.quantity - 1
            )

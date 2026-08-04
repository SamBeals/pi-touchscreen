"""Qt list models for catalog and cart (QML bindings)."""

from __future__ import annotations

from typing import List, Optional, Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Slot

from app.models.cart import Cart
from app.models.product import Product


def _money(cents: int) -> str:
    return f"${cents / 100:.2f}"


class CatalogModel(QAbstractListModel):
    SlotIdRole = Qt.UserRole + 1
    NameRole = Qt.UserRole + 2
    PriceTextRole = Qt.UserRole + 3
    StockTextRole = Qt.UserRole + 4
    ImageUrlRole = Qt.UserRole + 5
    PriceCentsRole = Qt.UserRole + 6
    QtyRole = Qt.UserRole + 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._products: List[Product] = []

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._products)

    def data(self, index, role=Qt.DisplayRole):  # noqa: N802
        if not index.isValid() or not (0 <= index.row() < len(self._products)):
            return None
        product = self._products[index.row()]
        if role in (Qt.DisplayRole, self.NameRole):
            return product.name
        if role == self.SlotIdRole:
            return product.slot_id
        if role == self.PriceTextRole:
            return _money(product.price_cents)
        if role == self.StockTextRole:
            return f"{product.qty} in stock · {product.slot_id}"
        if role == self.ImageUrlRole:
            return product.image_url or ""
        if role == self.PriceCentsRole:
            return product.price_cents
        if role == self.QtyRole:
            return product.qty
        return None

    def roleNames(self):  # noqa: N802
        return {
            self.SlotIdRole: b"slotId",
            self.NameRole: b"name",
            self.PriceTextRole: b"priceText",
            self.StockTextRole: b"stockText",
            self.ImageUrlRole: b"imageUrl",
            self.PriceCentsRole: b"priceCents",
            self.QtyRole: b"qty",
        }

    def set_products(self, products: Sequence[Product]) -> None:
        self.beginResetModel()
        self._products = list(products)
        self.endResetModel()


class CartModel(QAbstractListModel):
    NameRole = Qt.UserRole + 1
    QuantityRole = Qt.UserRole + 2
    LineTotalTextRole = Qt.UserRole + 3
    SlotIdRole = Qt.UserRole + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cart: Optional[Cart] = None

    def bind_cart(self, cart: Cart) -> None:
        self._cart = cart
        self.refresh()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        if parent.isValid() or self._cart is None:
            return 0
        return len(self._cart.lines())

    def data(self, index, role=Qt.DisplayRole):  # noqa: N802
        if self._cart is None or not index.isValid():
            return None
        lines = self._cart.lines()
        if not (0 <= index.row() < len(lines)):
            return None
        line = lines[index.row()]
        if role in (Qt.DisplayRole, self.NameRole):
            return line.product.name
        if role == self.QuantityRole:
            return line.quantity
        if role == self.LineTotalTextRole:
            return _money(line.line_total_cents)
        if role == self.SlotIdRole:
            return line.product.slot_id
        return None

    def roleNames(self):  # noqa: N802
        return {
            self.NameRole: b"name",
            self.QuantityRole: b"quantity",
            self.LineTotalTextRole: b"lineTotalText",
            self.SlotIdRole: b"slotId",
        }

    @Slot()
    def refresh(self) -> None:
        self.beginResetModel()
        self.endResetModel()

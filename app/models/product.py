from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Product:
    slot_id: str
    name: str
    price_cents: int
    qty: int
    enabled: bool = True
    image_url: Optional[str] = None
    capacity: Optional[int] = None
    sku_id: Optional[str] = None

    @property
    def sellable(self) -> bool:
        return self.enabled and self.qty > 0 and bool(self.name.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "name": self.name,
            "price_cents": self.price_cents,
            "qty": self.qty,
            "enabled": self.enabled,
            "image_url": self.image_url,
            "capacity": self.capacity,
            "sku_id": self.sku_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Product":
        return cls(
            slot_id=str(data["slot_id"]),
            name=str(data.get("name") or ""),
            price_cents=int(data.get("price_cents") or 0),
            qty=int(data.get("qty") or 0),
            enabled=bool(data.get("enabled", True)),
            image_url=data.get("image_url"),
            capacity=data.get("capacity"),
            sku_id=data.get("sku_id"),
        )

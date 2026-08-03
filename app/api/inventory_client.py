"""Load machine inventory from Firestore (or fixture). Never talks to vend-api."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.logging_setup import log_event
from app.models.product import Product

logger = logging.getLogger(__name__)


@dataclass
class InventorySnapshot:
    products: List[Product]
    fetched_at: datetime
    source: str  # "firestore" | "fixture" | "cache"

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now(timezone.utc)
        fetched = self.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return max(0.0, (now - fetched).total_seconds())

    def is_fresh(self, max_age_seconds: float, now: Optional[datetime] = None) -> bool:
        return self.age_seconds(now) <= max_age_seconds

    def catalog(self) -> Dict[str, Product]:
        return {p.slot_id: p for p in self.products}

    def sellable(self) -> List[Product]:
        return sorted(
            [p for p in self.products if p.sellable],
            key=lambda p: p.name.lower(),
        )


def _pick(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def merge_slot_docs(
    planogram: Dict[str, Dict[str, Any]],
    inventory: Dict[str, Dict[str, Any]],
) -> List[Product]:
    """Merge planogramSlots + inventory the way SellMateKioskApp does."""
    slot_ids = set(planogram) | set(inventory)
    products: List[Product] = []
    for slot_id in sorted(slot_ids):
        inv = inventory.get(slot_id, {})
        plan = planogram.get(slot_id, {})
        name = str(_pick(inv, "name", "productName", default=_pick(plan, "name", default="")) or "")
        price = int(
            _pick(inv, "price_cents", "priceCents", default=_pick(plan, "price_cents", "priceCents", default=0))
            or 0
        )
        qty = int(_pick(inv, "qty", "inventory", default=0) or 0)
        enabled = bool(_pick(inv, "enabled", default=_pick(plan, "enabled", default=True)))
        image = _pick(inv, "imageUrl", "image_url", "image", "imageUri")
        capacity = _pick(inv, "capacity")
        sku = _pick(inv, "sku_id", "skuId")
        products.append(
            Product(
                slot_id=slot_id,
                name=name,
                price_cents=price,
                qty=qty,
                enabled=enabled,
                image_url=str(image) if image else None,
                capacity=int(capacity) if capacity is not None else None,
                sku_id=str(sku) if sku else None,
            )
        )
    return products


class InventoryClient:
    def __init__(
        self,
        *,
        machine_id: str,
        cache_path: Path,
        project_id: Optional[str] = None,
        fixture_path: Optional[str] = None,
    ):
        self.machine_id = machine_id
        self.cache_path = cache_path
        self.project_id = project_id
        self.fixture_path = fixture_path

    def load(self) -> InventorySnapshot:
        if self.fixture_path:
            return self._load_fixture()
        try:
            snapshot = self._load_firestore()
            self._write_cache(snapshot)
            return snapshot
        except Exception as exc:  # noqa: BLE001
            log_event(
                logger,
                "inventory.firestore_failed",
                machine_id=self.machine_id,
                error=type(exc).__name__,
            )
            cached = self._read_cache()
            if cached:
                return cached
            raise

    def _load_fixture(self) -> InventorySnapshot:
        path = Path(self.fixture_path)  # type: ignore[arg-type]
        data = json.loads(path.read_text(encoding="utf-8"))
        products = [Product.from_dict(item) for item in data.get("products", data)]
        return InventorySnapshot(
            products=products,
            fetched_at=datetime.now(timezone.utc),
            source="fixture",
        )

    def _load_firestore(self) -> InventorySnapshot:
        from google.cloud import firestore

        client_kwargs = {}
        if self.project_id:
            client_kwargs["project"] = self.project_id
        db = firestore.Client(**client_kwargs)

        plan_docs = (
            db.collection("machines")
            .document(self.machine_id)
            .collection("planogramSlots")
            .stream()
        )
        inv_docs = (
            db.collection("machines")
            .document(self.machine_id)
            .collection("inventory")
            .stream()
        )

        planogram: Dict[str, Dict[str, Any]] = {}
        for doc in plan_docs:
            data = doc.to_dict() or {}
            slot_id = str(_pick(data, "slot_id", "slotId", default=doc.id))
            planogram[slot_id] = data

        inventory: Dict[str, Dict[str, Any]] = {}
        for doc in inv_docs:
            data = doc.to_dict() or {}
            slot_id = str(_pick(data, "slot_id", "slotId", default=doc.id))
            inventory[slot_id] = data

        if not planogram and not inventory:
            raise RuntimeError(f"No inventory/planogram for {self.machine_id}")

        products = merge_slot_docs(planogram, inventory)
        log_event(
            logger,
            "inventory.loaded",
            machine_id=self.machine_id,
            product_count=len(products),
            source="firestore",
        )
        return InventorySnapshot(
            products=products,
            fetched_at=datetime.now(timezone.utc),
            source="firestore",
        )

    def _write_cache(self, snapshot: InventorySnapshot) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "fetched_at": snapshot.fetched_at.isoformat(),
                "source": snapshot.source,
                "products": [p.to_dict() for p in snapshot.products],
            }
            self.cache_path.write_text(json.dumps(payload), encoding="utf-8")
        except OSError as exc:
            log_event(logger, "inventory.cache_write_failed", error=type(exc).__name__)

    def _read_cache(self) -> Optional[InventorySnapshot]:
        if not self.cache_path.is_file():
            return None
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(
                str(data["fetched_at"]).replace("Z", "+00:00")
            )
            products = [Product.from_dict(item) for item in data.get("products", [])]
            return InventorySnapshot(
                products=products, fetched_at=fetched, source="cache"
            )
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "inventory.cache_read_failed", error=type(exc).__name__)
            return None

"""Persist active order ID for restart recovery (atomic, machine-scoped)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.logging_setup import log_event

logger = logging.getLogger(__name__)


@dataclass
class ActiveOrder:
    order_id: str
    amount_cents: int
    machine_id: str


class ActiveOrderStore:
    def __init__(self, path: Path, *, expected_machine_id: str):
        self.path = path
        self.expected_machine_id = expected_machine_id.strip()

    def load(self) -> Optional[ActiveOrder]:
        if not self.path.is_file():
            return None
        try:
            raw = self.path.read_text(encoding="utf-8")
            if not raw.strip():
                log_event(logger, "active_order.empty_file")
                self._safe_unlink()
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                log_event(logger, "active_order.malformed", reason="not_object")
                self._safe_unlink()
                return None
            order_id = str(data.get("order_id") or "").strip()
            machine_id = str(data.get("machine_id") or "").strip()
            if not order_id:
                log_event(logger, "active_order.malformed", reason="missing_order_id")
                self._safe_unlink()
                return None
            if machine_id != self.expected_machine_id:
                log_event(
                    logger,
                    "active_order.machine_mismatch",
                    expected_machine_id=self.expected_machine_id,
                    file_machine_id=machine_id or "(missing)",
                )
                # Do not clear automatically — another machine's file should not
                # be destroyed if data dirs were shared incorrectly; just ignore.
                return None
            return ActiveOrder(
                order_id=order_id,
                amount_cents=int(data.get("amount_cents") or 0),
                machine_id=machine_id,
            )
        except Exception as exc:  # noqa: BLE001
            log_event(
                logger,
                "active_order.load_failed",
                error=type(exc).__name__,
            )
            self._safe_unlink()
            return None

    def save(self, order: ActiveOrder) -> None:
        if order.machine_id != self.expected_machine_id:
            raise ValueError("Cannot persist active order for a different MACHINE_ID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "order_id": order.order_id,
            "amount_cents": order.amount_cents,
            "machine_id": order.machine_id,
        }
        data = json.dumps(payload, sort_keys=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix="active_order.",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        log_event(
            logger,
            "active_order.saved",
            order_id=order.order_id,
            machine_id=order.machine_id,
        )

    def clear(self) -> None:
        self._safe_unlink()
        log_event(logger, "active_order.cleared")

    def _safe_unlink(self) -> None:
        try:
            if self.path.is_file():
                self.path.unlink()
        except OSError as exc:
            log_event(logger, "active_order.clear_failed", error=type(exc).__name__)

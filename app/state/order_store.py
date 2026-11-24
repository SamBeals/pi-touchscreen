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


class RecoveryRecordError(RuntimeError):
    """A pending checkout record could not be read safely."""


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
        """Only a missing file means no pending checkout; preserve bad evidence."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeError) as exc:
            raise RecoveryRecordError("Cannot read active checkout record") from exc
        try:
            data = json.loads(raw)
            order_id = data["order_id"]
            machine_id = data["machine_id"]
            amount = data["amount_cents"]
            if not isinstance(order_id, str) or not order_id.strip():
                raise ValueError("missing order ID")
            if machine_id != self.expected_machine_id:
                raise ValueError("machine mismatch")
            if type(amount) is not int or amount <= 0:
                raise ValueError("invalid amount")
        except (ValueError, TypeError, KeyError) as exc:
            raise RecoveryRecordError("Cannot validate active checkout record") from exc
        return ActiveOrder(order_id, amount, machine_id)

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
            # Payment may be sent immediately after save; persist the rename too.
            dir_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
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

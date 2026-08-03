"""Structured JSON logging. Never log secrets, tokens, or payment details."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        extras = getattr(record, "fields", None)
        if isinstance(extras, dict):
            payload.update(extras)
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, default=str, sort_keys=True)


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit a structured log line. Callers must not pass secrets."""
    forbidden = {
        "token",
        "password",
        "secret",
        "api_key",
        "authorization",
        "card",
        "pan",
        "cvv",
        "payment_method",
    }
    safe = {
        k: v
        for k, v in fields.items()
        if k.lower() not in forbidden and "token" not in k.lower()
    }
    logger.info(event, extra={"event": event, "fields": safe})

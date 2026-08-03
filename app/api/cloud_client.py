"""SellMateCloud HTTP client. No secrets logged; no local vend-api calls."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - exercised in minimal test envs
    requests = None  # type: ignore

from app.logging_setup import log_event

logger = logging.getLogger(__name__)


class CloudClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class CloudClient:
    def __init__(
        self,
        cloud_base: str,
        *,
        session: Optional[Any] = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ):
        if session is None and requests is None:
            raise RuntimeError("requests package is required for CloudClient")
        self.cloud_base = cloud_base.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

    def health(self) -> bool:
        try:
            resp = self.session.get(
                f"{self.cloud_base}/health", timeout=self.timeout
            )
            return resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "cloud.health_failed", error=type(exc).__name__)
            return False

    def create_order(
        self,
        *,
        machine_id: str,
        items: List[Dict[str, Any]],
        amount_cents: int,
    ) -> Dict[str, Any]:
        payload = {
            "machine_id": machine_id,
            "items": items,
            "amount_cents": amount_cents,
        }
        return self._request("POST", "/orders", json=payload)

    def start_payment(self, order_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/orders/{order_id}/start_payment")

    def get_order(self, order_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/orders/{order_id}")

    def cancel_order(self, order_id: str, reason: str = "Cancelled from kiosk") -> Dict[str, Any]:
        return self._request(
            "POST",
            f"/orders/{order_id}/cancel",
            json={"reason": reason},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.cloud_base}{path}"
        try:
            resp = self.session.request(
                method, url, json=json, timeout=self.timeout
            )
        except Exception as exc:  # noqa: BLE001
            log_event(
                logger,
                "cloud.request_failed",
                method=method,
                path=path,
                error=type(exc).__name__,
            )
            raise CloudClientError(f"Cloud request failed: {type(exc).__name__}") from exc

        if resp.status_code >= 400:
            # Do not log response bodies (may contain sensitive detail).
            log_event(
                logger,
                "cloud.http_error",
                method=method,
                path=path,
                status_code=resp.status_code,
            )
            raise CloudClientError(
                f"Cloud returned HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise CloudClientError("Cloud returned non-JSON body") from exc
        if not isinstance(data, dict):
            raise CloudClientError("Cloud returned unexpected JSON type")
        return data

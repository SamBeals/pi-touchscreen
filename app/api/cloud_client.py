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
        machine_id: Optional[str] = None,
        session: Optional[Any] = None,
        timeout: tuple[float, float] = (5.0, 20.0),
    ):
        if session is None and requests is None:
            raise RuntimeError("requests package is required for CloudClient")
        self.cloud_base = cloud_base.rstrip("/")
        self.machine_id = machine_id
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

    def get_machine_theme(self, *, machine_token: str, machine_id: Optional[str] = None) -> Dict[str, Any]:
        mid = machine_id or self.machine_id
        if not mid:
            raise CloudClientError("machine_id required for theme status")
        return self._request(
            "GET",
            f"/machines/{mid}/theme",
            headers={"X-Machine-Token": machine_token},
        )

    def download_machine_theme_package(
        self, *, machine_token: str, machine_id: Optional[str] = None
    ) -> bytes:
        mid = machine_id or self.machine_id
        if not mid:
            raise CloudClientError("machine_id required for theme download")
        data = self._request(
            "GET",
            f"/machines/{mid}/theme/package",
            headers={"X-Machine-Token": machine_token},
            raw=True,
        )
        if not isinstance(data, (bytes, bytearray)):
            raise CloudClientError("Theme package response was not bytes")
        return bytes(data)

    def ack_machine_theme(
        self,
        *,
        machine_token: str,
        revision: int,
        status: str,
        package_id: str,
        theme_id: str,
        sha256: str,
        error: Optional[str] = None,
        app_version: Optional[str] = None,
        machine_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        mid = machine_id or self.machine_id
        if not mid:
            raise CloudClientError("machine_id required for theme ack")
        payload: Dict[str, Any] = {
            "revision": revision,
            "status": status,
            "package_id": package_id,
            "theme_id": theme_id,
            "sha256": sha256,
        }
        if error:
            payload["error"] = error
        if app_version:
            payload["app_version"] = app_version
        return self._request(
            "POST",
            f"/machines/{mid}/theme/ack",
            json=payload,
            headers={"X-Machine-Token": machine_token},
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        raw: bool = False,
    ) -> Any:
        url = f"{self.cloud_base}{path}"
        timeout = (5.0, 120.0) if raw else self.timeout
        try:
            resp = self.session.request(
                method, url, json=json, headers=headers, timeout=timeout
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
        if raw:
            return resp.content
        try:
            data = resp.json()
        except ValueError as exc:
            raise CloudClientError("Cloud returned non-JSON body") from exc
        if not isinstance(data, dict):
            raise CloudClientError("Cloud returned unexpected JSON type")
        return data

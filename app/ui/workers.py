"""QThread workers — all Cloud/Firestore work stays off the UI thread."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from app.api.cloud_client import CloudClient, CloudClientError
from app.api.inventory_client import InventoryClient, InventorySnapshot
from app.models.cart import Cart
from app.state.checkout_service import CheckoutService, PollResult


class InventoryLoadWorker(QThread):
    finished_ok = Signal(object)  # InventorySnapshot
    finished_err = Signal(str)

    def __init__(self, client: InventoryClient, parent=None):
        super().__init__(parent)
        self._client = client

    def run(self) -> None:
        try:
            snap = self._client.load()
            self.finished_ok.emit(snap)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc) or type(exc).__name__)


class CloudHealthWorker(QThread):
    finished_ok = Signal(bool)

    def __init__(self, cloud: CloudClient, parent=None):
        super().__init__(parent)
        self._cloud = cloud

    def run(self) -> None:
        self.finished_ok.emit(self._cloud.health())


class CheckoutStartWorker(QThread):
    finished_ok = Signal(str)
    finished_err = Signal(str)

    def __init__(self, service: CheckoutService, cart: Cart, parent=None):
        super().__init__(parent)
        self._service = service
        self._cart = cart

    def run(self) -> None:
        try:
            order_id = self._service.start_checkout(self._cart)
            self.finished_ok.emit(order_id)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc) or type(exc).__name__)


class OrderPollWorker(QThread):
    status_update = Signal(object)  # PollResult
    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(self, service: CheckoutService, order_id: str, parent=None):
        super().__init__(parent)
        self._service = service
        self._order_id = order_id
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            result = self._service.poll_until_terminal(
                self._order_id,
                on_update=lambda r: self.status_update.emit(r),
                should_stop=lambda: self._stop,
            )
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc) or type(exc).__name__)


class CancelOrderWorker(QThread):
    finished_ok = Signal(bool)
    finished_err = Signal(str)

    def __init__(
        self,
        service: CheckoutService,
        order_id: str,
        current_status,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._order_id = order_id
        self._status = current_status

    def run(self) -> None:
        try:
            ok = self._service.cancel_if_allowed(self._order_id, self._status)
            self.finished_ok.emit(ok)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc) or type(exc).__name__)


class ResumeOrderWorker(QThread):
    finished_ok = Signal(object)  # Optional[str]
    finished_err = Signal(str)

    def __init__(self, service: CheckoutService, parent=None):
        super().__init__(parent)
        self._service = service

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._service.resume_if_needed())
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc) or type(exc).__name__)


class ThemeSyncWorker(QThread):
    """Poll Cloud for a desired theme and install when Attract-idle."""

    finished_ok = Signal(object)  # Optional ActiveThemePointer / truthy if applied
    finished_err = Signal(str)

    def __init__(
        self,
        cloud: CloudClient,
        *,
        machine_token: str,
        data_dir,
        parent=None,
    ):
        super().__init__(parent)
        self._cloud = cloud
        self._token = machine_token
        self._data_dir = data_dir

    def run(self) -> None:
        from app.theme.cloud_sync import ack_theme_failed, sync_desired_theme

        try:
            pointer = sync_desired_theme(
                cloud_client=self._cloud,
                machine_token=self._token,
                data_dir=self._data_dir,
            )
            self.finished_ok.emit(pointer)
        except Exception as exc:  # noqa: BLE001
            message = str(exc) or type(exc).__name__
            try:
                status = self._cloud.get_machine_theme(machine_token=self._token)
                desired = status.get("desired_theme") or {}
                if desired:
                    ack_theme_failed(
                        cloud_client=self._cloud,
                        machine_token=self._token,
                        desired=desired,
                        error=message,
                    )
            except Exception:  # noqa: BLE001
                pass
            self.finished_err.emit(message)
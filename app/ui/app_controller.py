"""UI-agnostic application controller exposed to QML."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from app.api.cloud_client import CloudClient
from app.api.inventory_client import InventoryClient, InventorySnapshot
from app.config import Settings
from app.logging_setup import log_event
from app.models.cart import Cart
from app.models.order import OrderStatus
from app.models.product import Product
from app.state.app_state import AppScreen, AppStateMachine, checkout_gate_reason
from app.state.checkout_service import (
    CHECKING_PAYMENT, PAYMENT_UNCONFIRMED, CheckoutService, PollResult,
)
from app.state.order_store import ActiveOrderStore, RecoveryRecordError
from app.ui.layout import browse_column_count, current_profile
from app.ui.list_models import CartModel, CatalogModel
from app.ui.theme_bridge import ThemeBridge
from app.ui.theme_provider import create_theme_bridge
from app.ui.workers import (
    CancelOrderWorker,
    CheckoutStartWorker,
    CloudHealthWorker,
    InventoryLoadWorker,
    OrderPollWorker,
    ResumeOrderWorker,
    ThemeSyncWorker,
    WaitTimeoutCancelWorker,
)

logger = logging.getLogger(__name__)


def _money(cents: int) -> str:
    return f"${cents / 100:.2f}"


class AppController(QObject):
    screenChanged = Signal()
    statusChanged = Signal()
    detailChanged = Signal()
    cartChanged = Signal()
    toastRequested = Signal(str, str)  # title, message

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.cart = Cart()
        self.fsm = AppStateMachine()
        self.catalog: Dict[str, Product] = {}
        self.snapshot: Optional[InventorySnapshot] = None

        from app.theme.cloud_sync import resolve_boot_theme

        boot_theme_id, boot_packages_dir = resolve_boot_theme(
            data_dir=settings.data_dir,
            fallback_theme_id=settings.theme_id,
            fallback_packages_dir=settings.theme_packages_dir,
        )
        self._theme_bridge = create_theme_bridge(
            theme_id=boot_theme_id,
            packages_dir=boot_packages_dir,
            parent=self,
        )

        self.catalog_model = CatalogModel(self)
        self.cart_model = CartModel(self)
        self.cart_model.bind_cart(self.cart)

        self.cloud = CloudClient(settings.cloud_base, machine_id=settings.machine_id)
        self.inventory_client = InventoryClient(
            machine_id=settings.machine_id,
            cache_path=settings.inventory_cache_path,
            project_id=settings.firestore_project_id,
            fixture_path=settings.inventory_fixture_path,
        )
        self.order_store = ActiveOrderStore(
            settings.active_order_path,
            expected_machine_id=settings.machine_id,
        )
        self.checkout = CheckoutService(
            self.cloud,
            machine_id=settings.machine_id,
            order_store=self.order_store,
            poll_interval_seconds=settings.poll_interval_seconds,
            poll_max_attempts=settings.poll_max_attempts,
        )

        self._workers: List = []
        self._poll_worker: Optional[OrderPollWorker] = None
        self._closing = False
        self._recovering_payment = False
        self._recovery_help = False
        self._payment_start_in_flight = False
        self._detail_qty = 1
        profile = current_profile()
        self._browse_viewport_width = profile.window_width
        self._window_width = profile.window_width
        self._window_height = profile.window_height
        self._boot_message = "Starting SellMate…"
        self._payment_message = "Waiting for card…"
        self._result_message = ""
        self._user_notice = ""
        self._vend_wait_total = max(1.0, float(settings.vend_wait_seconds))
        self._vend_wait_deadline: Optional[float] = None
        self._vend_wait_seconds_remaining = 0
        self._vend_wait_active = False
        self._wait_timeout_cancel_in_flight = False

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(int(settings.idle_timeout_seconds * 1000))
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        self.inventory_timer = QTimer(self)
        self.inventory_timer.setInterval(
            int(settings.inventory_idle_refresh_seconds * 1000)
        )
        self.inventory_timer.timeout.connect(self._refresh_inventory_idle)

        self.theme_timer = QTimer(self)
        self.theme_timer.setInterval(int(max(15.0, settings.theme_poll_seconds) * 1000))
        self.theme_timer.timeout.connect(self._refresh_theme_idle)
        self._theme_sync_running = False

        self.vend_wait_timer = QTimer(self)
        self.vend_wait_timer.setInterval(250)
        self.vend_wait_timer.timeout.connect(self._on_vend_wait_tick)

        QTimer.singleShot(0, self._bootstrap)

    # ----- Qt properties -----

    @Property(QObject, constant=True)
    def theme(self) -> ThemeBridge:
        return self._theme_bridge

    @Property(str, notify=screenChanged)
    def screen(self) -> str:
        return self.fsm.screen.value

    @Property(str, notify=statusChanged)
    def bootMessage(self) -> str:  # noqa: N802
        return self._boot_message

    @Property(str, notify=statusChanged)
    def fatalReason(self) -> str:  # noqa: N802
        return self.fsm.fatal_reason

    @Property(str, notify=statusChanged)
    def browseStatus(self) -> str:  # noqa: N802
        products = self.snapshot.sellable() if self.snapshot else []
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        return gate or f"{len(products)} available"

    @Property(int, notify=cartChanged)
    def cartCount(self) -> int:  # noqa: N802
        return self.cart.item_count()

    @Property(str, notify=cartChanged)
    def cartTotalText(self) -> str:  # noqa: N802
        base = f"Total: {_money(self.cart.total_cents())}"
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        if gate:
            return f"{base} — {gate}"
        return base

    @Property(bool, notify=cartChanged)
    def checkoutEnabled(self) -> bool:  # noqa: N802
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        return self.cart.item_count() > 0 and gate is None

    @Property(str, notify=statusChanged)
    def paymentMessage(self) -> str:  # noqa: N802
        return self._payment_message

    @Property(bool, notify=statusChanged)
    def cancelEnabled(self) -> bool:  # noqa: N802
        return not self._recovering_payment and self.fsm.cancel_allowed()

    @Property(bool, notify=statusChanged)
    def paymentStartPending(self) -> bool:  # noqa: N802
        return self._payment_start_in_flight

    @Property(bool, notify=statusChanged)
    def paymentRecoveryHelp(self) -> bool:  # noqa: N802
        return self._recovery_help

    @Property(bool, notify=statusChanged)
    def vendWaitActive(self) -> bool:  # noqa: N802
        return self._vend_wait_active

    @Property(int, notify=statusChanged)
    def vendWaitSecondsRemaining(self) -> int:  # noqa: N802
        return int(self._vend_wait_seconds_remaining)

    @Property(float, notify=statusChanged)
    def vendWaitProgress(self) -> float:  # noqa: N802
        """Fraction of wait remaining (1.0 = just started, 0.0 = expired)."""
        if self._vend_wait_total <= 0:
            return 0.0
        return max(
            0.0,
            min(1.0, self._vend_wait_seconds_remaining / self._vend_wait_total),
        )

    @Property(str, notify=statusChanged)
    def resultMessage(self) -> str:  # noqa: N802
        return self._result_message

    @Property(str, notify=detailChanged)
    def detailName(self) -> str:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        return product.name if product else ""

    @Property(str, notify=detailChanged)
    def detailPriceText(self) -> str:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        return _money(product.price_cents) if product else ""

    @Property(str, notify=detailChanged)
    def detailMeta(self) -> str:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        if not product:
            return ""
        return f"Slot {product.slot_id} · {product.qty} available"

    @Property(str, notify=detailChanged)
    def detailImageUrl(self) -> str:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        return (product.image_url or "") if product else ""

    @Property(str, notify=detailChanged)
    def detailSlotId(self) -> str:  # noqa: N802
        return self.fsm.selected_slot_id or ""

    @Property(int, notify=detailChanged)
    def detailQty(self) -> int:  # noqa: N802
        return self._detail_qty

    @Property(int, notify=statusChanged)
    def browseColumns(self) -> int:  # noqa: N802
        return browse_column_count(self._browse_viewport_width)

    @Property(int, notify=statusChanged)
    def windowWidth(self) -> int:  # noqa: N802
        return self._window_width

    @Property(int, notify=statusChanged)
    def windowHeight(self) -> int:  # noqa: N802
        return self._window_height

    # ----- bootstrap -----

    def _bootstrap(self) -> None:
        settings = self.settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        log_event(
            logger,
            "app.bootstrap",
            machine_id=settings.machine_id,
            cloud_base=settings.cloud_base,
            theme_id=self.theme.id,
        )
        self._try_resume_order()

    def _run_health_then_inventory(self) -> None:
        if self._closing:
            return
        worker = CloudHealthWorker(self.cloud)
        self._track(worker)

        def on_health(ok: bool) -> None:
            if self._closing:
                return
            self.fsm.cloud_reachable = ok
            self._load_inventory(boot=True)

        worker.finished_ok.connect(on_health)
        worker.start()

    def _load_inventory(self, *, boot: bool = False) -> None:
        if self._closing:
            return
        worker = InventoryLoadWorker(self.inventory_client)
        self._track(worker)

        def ok(snap: InventorySnapshot) -> None:
            if self._closing:
                return
            self._apply_snapshot(snap)
            if boot:
                self.fsm.boot_ok()
                self._show_screen(AppScreen.ATTRACT)
                self.inventory_timer.start()
                self.theme_timer.start()
            elif self.fsm.screen in {AppScreen.ATTRACT, AppScreen.BROWSE}:
                self.statusChanged.emit()

        def err(msg: str) -> None:
            if self._closing:
                return
            if boot and self.snapshot is None:
                self.fsm.boot_fatal(f"Inventory load failed: {msg}")
                self._show_screen(AppScreen.FATAL)
            else:
                log_event(logger, "inventory.refresh_failed", error=msg)

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _apply_snapshot(self, snap: InventorySnapshot) -> None:
        self.snapshot = snap
        self.catalog = snap.catalog()
        self.fsm.inventory_fresh = snap.is_fresh(
            self.settings.inventory_max_age_seconds
        )
        self.catalog_model.set_products(snap.sellable())
        self.statusChanged.emit()
        self.cartChanged.emit()

    def _try_resume_order(self) -> None:
        if self._closing:
            return
        worker = ResumeOrderWorker(self.checkout)
        self._track(worker)

        def ok(order_id: Optional[str]) -> None:
            if self._closing:
                return
            if order_id:
                self._begin_payment_recovery(order_id)
            else:
                self._run_health_then_inventory()

        def err(msg: str) -> None:
            if self._closing:
                return
            log_event(logger, "checkout.resume_failed", error=msg)
            self._show_payment_recovery_help()

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _show_payment_recovery_help(self) -> None:
        self._recovering_payment = True
        self._recovery_help = True
        self.fsm.mark_failure(PAYMENT_UNCONFIRMED)
        self._result_message = PAYMENT_UNCONFIRMED
        self._show_screen(AppScreen.FAILURE)

    def _begin_payment_recovery(self, order_id: str) -> None:
        self._recovering_payment = True
        self._recovery_help = False
        self.fsm.begin_payment(order_id)
        self._set_payment_message(CHECKING_PAYMENT)
        self._show_screen(AppScreen.PAYMENT)
        self._start_polling(order_id)

    @Slot()
    def checkPaymentStatus(self) -> None:  # noqa: N802
        if self._closing or not self._recovery_help or self.fsm.screen != AppScreen.FAILURE:
            return
        try:
            order_id = self.checkout.current_order_id()
        except RecoveryRecordError:
            order_id = None
        if order_id:
            self._begin_payment_recovery(order_id)
        else:
            self._show_payment_recovery_help()

    def _show_screen(self, screen: AppScreen) -> None:
        self.fsm.screen = screen
        self.screenChanged.emit()
        self.statusChanged.emit()
        self._bump_idle()

    def _bump_idle(self) -> None:
        if self.fsm.screen in {
            AppScreen.PAYMENT,
            AppScreen.BOOT,
            AppScreen.FATAL,
        }:
            self.idle_timer.stop()
            return
        self.idle_timer.start()

    def _on_idle_timeout(self) -> None:
        if self.fsm.screen in {AppScreen.PAYMENT, AppScreen.BOOT, AppScreen.FATAL}:
            return
        log_event(logger, "app.idle_timeout", screen=self.fsm.screen.value)
        self._return_to_attract()

    def _refresh_inventory_idle(self) -> None:
        if self.fsm.screen == AppScreen.ATTRACT:
            self._load_inventory()
            health = CloudHealthWorker(self.cloud)
            self._track(health)

            def apply(ok: bool) -> None:
                self.fsm.cloud_reachable = ok
                self.statusChanged.emit()
                self.cartChanged.emit()

            health.finished_ok.connect(apply)
            health.start()
            self._refresh_theme_idle()

    def _refresh_theme_idle(self) -> None:
        if not self.settings.theme_sync_enabled:
            return
        if not self.settings.machine_shared_token:
            return
        if self.fsm.screen != AppScreen.ATTRACT:
            return
        if self.fsm.active_order_id:
            return
        if self._theme_sync_running:
            return

        self._theme_sync_running = True
        worker = ThemeSyncWorker(
            self.cloud,
            machine_token=self.settings.machine_shared_token,
            data_dir=self.settings.data_dir,
        )
        self._track(worker)

        def on_ok(pointer) -> None:
            self._theme_sync_running = False
            if not pointer:
                return
            log_event(
                logger,
                "theme.restart_for_apply",
                theme_id=getattr(pointer, "theme_id", None),
                revision=getattr(pointer, "revision", None),
            )
            # Exit non-zero so systemd Restart=on-failure reloads fonts/QML cleanly.
            from PySide6.QtCore import QCoreApplication

            QCoreApplication.exit(1)

        def on_err(message: str) -> None:
            self._theme_sync_running = False
            log_event(logger, "theme.sync_failed", error=message)

        worker.finished_ok.connect(on_ok)
        worker.finished_err.connect(on_err)
        worker.start()

    def _set_payment_message(self, text: str) -> None:
        self._payment_message = text
        self.fsm.status_message = text
        self.statusChanged.emit()

    def _clear_vend_wait(self) -> None:
        self.vend_wait_timer.stop()
        self._vend_wait_deadline = None
        self._vend_wait_seconds_remaining = 0
        self._vend_wait_active = False
        self.statusChanged.emit()

    def _start_vend_wait(self) -> None:
        if self._vend_wait_deadline is not None:
            return
        self._vend_wait_deadline = time.monotonic() + self._vend_wait_total
        self._vend_wait_active = True
        self._on_vend_wait_tick()
        self.vend_wait_timer.start()

    def _on_vend_wait_tick(self) -> None:
        if self._vend_wait_deadline is None:
            self._clear_vend_wait()
            return
        remaining = self._vend_wait_deadline - time.monotonic()
        self._vend_wait_seconds_remaining = max(0, int(remaining + 0.999))
        self._vend_wait_active = remaining > 0
        self.statusChanged.emit()
        if remaining > 0:
            return
        self.vend_wait_timer.stop()
        self._vend_wait_active = False
        self._maybe_fire_wait_timeout_cancel()

    def _maybe_fire_wait_timeout_cancel(self) -> None:
        if self._closing or self._wait_timeout_cancel_in_flight:
            return
        if self.fsm.screen != AppScreen.PAYMENT:
            return
        if self.fsm.last_order_status != OrderStatus.AUTHORIZED:
            return
        order_id = self.fsm.active_order_id
        if not order_id:
            return
        self._wait_timeout_cancel_in_flight = True
        log_event(logger, "checkout.wait_timeout_fire", order_id=order_id)
        worker = WaitTimeoutCancelWorker(self.checkout, order_id)
        self._track(worker)

        def ok(result: str) -> None:
            self._wait_timeout_cancel_in_flight = False
            if self._closing or self.fsm.active_order_id != order_id:
                return
            if result == "cancelled":
                self._begin_payment_recovery(order_id)
                return
            # Claim won the race — keep polling for COMPLETED/FAILED.
            self._clear_vend_wait()
            self._set_payment_message("Vending in progress…")

        def err(msg: str) -> None:
            self._wait_timeout_cancel_in_flight = False
            if self._closing or self.fsm.active_order_id != order_id:
                return
            log_event(logger, "checkout.wait_timeout_unconfirmed", error=msg)
            self._begin_payment_recovery(order_id)

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _track(self, worker) -> None:
        self._workers.append(worker)
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )

    # ----- QML slots -----

    @Slot()
    def bumpIdle(self) -> None:  # noqa: N802
        self._bump_idle()

    @Slot(int)
    def setBrowseViewportWidth(self, width: int) -> None:  # noqa: N802
        if width <= 0:
            return
        if width != self._browse_viewport_width:
            self._browse_viewport_width = width
            self.statusChanged.emit()

    @Slot(int, int)
    def setWindowGeometry(self, width: int, height: int) -> None:  # noqa: N802
        """Track actual portrait window size; layout derives from these values."""
        if width <= 0 or height <= 0:
            return
        changed = False
        if width != self._window_width:
            self._window_width = width
            changed = True
        if height != self._window_height:
            self._window_height = height
            changed = True
        if width != self._browse_viewport_width:
            self._browse_viewport_width = width
            changed = True
        if changed:
            self.statusChanged.emit()

    @Slot()
    def enterBrowse(self) -> None:  # noqa: N802
        self.fsm.go_browse()
        self.statusChanged.emit()
        self.cartChanged.emit()
        self._show_screen(AppScreen.BROWSE)

    @Slot(str)
    def openDetail(self, slot_id: str) -> None:  # noqa: N802
        product = self.catalog.get(slot_id)
        if not product:
            return
        self.fsm.open_product(slot_id)
        self._detail_qty = 1
        self.detailChanged.emit()
        self._show_screen(AppScreen.PRODUCT_DETAIL)

    @Slot(int)
    def detailAdjust(self, delta: int) -> None:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        if not product:
            return
        self._detail_qty = max(1, min(product.qty, self._detail_qty + delta))
        self.detailChanged.emit()
        self._bump_idle()

    @Slot()
    def detailAdd(self) -> None:  # noqa: N802
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        if not product:
            return
        try:
            self.cart.add(product, self._detail_qty)
        except ValueError as exc:
            self.toastRequested.emit("Cart", str(exc))
            return
        self.cart_model.refresh()
        self.cartChanged.emit()
        self.enterBrowse()

    @Slot()
    def openCart(self) -> None:  # noqa: N802
        self.cart_model.refresh()
        self.fsm.go_cart()
        self.cartChanged.emit()
        self._show_screen(AppScreen.CART)

    @Slot()
    def backToBrowse(self) -> None:  # noqa: N802
        self._show_screen(AppScreen.BROWSE)

    @Slot()
    def startCheckout(self) -> None:  # noqa: N802
        # Changing screen synchronously consumes this input before any worker
        # starts, so a queued second press from the cart cannot start checkout.
        if self._closing or self.fsm.screen != AppScreen.CART:
            return
        try:
            order_id = self.checkout.current_order_id()
        except RecoveryRecordError:
            self._show_payment_recovery_help()
            return
        if order_id:
            self._begin_payment_recovery(order_id)
            return
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        if gate:
            self.toastRequested.emit("Checkout unavailable", gate)
            return
        if self.cart.item_count() <= 0:
            return
        self._payment_start_in_flight = True
        self.fsm.screen = AppScreen.PAYMENT
        self.fsm.status_message = "Preparing checkout…"
        self.fsm.error_message = ""
        self.fsm.last_order_status = OrderStatus.CREATED
        self._set_payment_message("Preparing checkout…")
        self.screenChanged.emit()
        self.idle_timer.stop()

        worker = CheckoutStartWorker(self.checkout, self.cart)
        self._track(worker)

        def ok(order_id: str) -> None:
            self._payment_start_in_flight = False
            if self._closing:
                return
            self.fsm.begin_payment(order_id)
            self._set_payment_message("Waiting for card…")
            self.statusChanged.emit()
            self._start_polling(order_id)

        def err(msg: str) -> None:
            self._payment_start_in_flight = False
            if self._closing:
                return
            log_event(logger, "checkout.start_failed", error=msg)
            try:
                order_id = self.checkout.current_order_id()
            except RecoveryRecordError:
                self._show_payment_recovery_help()
                return
            if order_id:
                self._begin_payment_recovery(order_id)
            else:
                message = "Couldn’t start checkout. Please ask staff for help."
                self.fsm.mark_failure(message)
                self._result_message = message
                self._show_screen(AppScreen.FAILURE)

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _stop_polling(self) -> None:
        worker = self._poll_worker
        if worker is None:
            return
        for signal in (worker.status_update, worker.finished_ok, worker.finished_err):
            try:
                signal.disconnect()
            except (RuntimeError, TypeError):
                pass
        worker.request_stop()
        if worker.isRunning():
            worker.wait(3000)
        self._poll_worker = None

    def _start_polling(self, order_id: str) -> None:
        if self._closing:
            return
        self._stop_polling()
        self._clear_vend_wait()
        self._wait_timeout_cancel_in_flight = False
        worker = OrderPollWorker(self.checkout, order_id)
        self._poll_worker = worker
        self._track(worker)

        def on_update(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self.fsm.last_order_status = result.status
            if result.status == OrderStatus.AUTHORIZED and not self._recovering_payment:
                self._start_vend_wait()
            elif result.status in {OrderStatus.VENDING, OrderStatus.UNKNOWN}:
                self._clear_vend_wait()
            recovery_message = (
                CHECKING_PAYMENT if self._recovering_payment and not result.terminal
                and result.status in {OrderStatus.CREATED, OrderStatus.AUTHORIZING}
                else result.message
            )
            self._set_payment_message(recovery_message)

        def on_done(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self._clear_vend_wait()
            self.statusChanged.emit()
            if result.status == OrderStatus.COMPLETED and result.terminal:
                self._recovering_payment = False
                self._recovery_help = False
                self.cart.clear()
                self.cart_model.refresh()
                self.cartChanged.emit()
                self.fsm.mark_success()
                self._result_message = result.message
                self._show_screen(AppScreen.SUCCESS)
                self._load_inventory()
                QTimer.singleShot(
                    5000,
                    lambda: self.finishToAttract()
                    if self.fsm.screen == AppScreen.SUCCESS and self.fsm.active_order_id == order_id
                    else None,
                )
            elif result.status == OrderStatus.FAILED and result.terminal:
                self._recovering_payment = False
                self._recovery_help = False
                self.fsm.mark_failure(result.message)
                self._result_message = result.message
                self._show_screen(AppScreen.FAILURE)
                self._load_inventory()
            else:
                self._show_payment_recovery_help()

        def on_err(msg: str) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self._clear_vend_wait()
            log_event(logger, "checkout.poll_failed", error=msg)
            self._show_payment_recovery_help()

        worker.status_update.connect(on_update)
        worker.finished_ok.connect(on_done)
        worker.finished_err.connect(on_err)
        worker.start()

    @Slot()
    def cancelCheckout(self) -> None:  # noqa: N802
        order_id = self.fsm.active_order_id
        if not order_id or not self.cancelEnabled:
            return
        self._stop_polling()
        self._recovering_payment = True
        self._set_payment_message(CHECKING_PAYMENT)
        worker = CancelOrderWorker(
            self.checkout, order_id, self.fsm.last_order_status
        )
        self._track(worker)

        def resume(*_args) -> None:
            if not self._closing and self.fsm.active_order_id == order_id:
                self._begin_payment_recovery(order_id)

        worker.finished_ok.connect(resume)
        worker.finished_err.connect(resume)
        worker.start()

    @Slot()
    def abandonActiveOrder(self) -> None:  # noqa: N802
        self._return_to_attract()

    @Slot()
    def finishToAttract(self) -> None:  # noqa: N802
        self._return_to_attract()

    def _return_to_attract(self) -> None:
        if self._closing or self._payment_start_in_flight:
            return
        self._stop_polling()
        self._clear_vend_wait()
        self._wait_timeout_cancel_in_flight = False
        self.cart.clear()
        self.cart_model.refresh()
        self.fsm.clear_active_order()
        self.cartChanged.emit()
        try:
            pending = bool(self.checkout.current_order_id())
        except RecoveryRecordError:
            pending = True
        if pending or self._recovery_help:
            # Clear customer display and cart, not the order recovery record.
            self._show_payment_recovery_help()
            return
        self._recovering_payment = False
        self._recovery_help = False
        if self.snapshot is None or not self.fsm.cloud_reachable:
            self._show_screen(AppScreen.BOOT)
            self._run_health_then_inventory()
            return
        self.fsm.go_attract()
        self._show_screen(AppScreen.ATTRACT)
        self.inventory_timer.start()
        self.theme_timer.start()

    @Slot()
    def shutdown(self) -> None:
        self._closing = True
        self.idle_timer.stop()
        self.inventory_timer.stop()
        self.theme_timer.stop()
        self.vend_wait_timer.stop()
        self._stop_polling()
        for worker in list(self._workers):
            if hasattr(worker, "request_stop"):
                worker.request_stop()
            if worker.isRunning():
                worker.wait(2000)
        self._workers.clear()
        log_event(logger, "app.shutdown")

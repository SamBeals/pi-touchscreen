"""UI-agnostic application controller exposed to QML."""

from __future__ import annotations

import logging
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
from app.state.checkout_service import CheckoutService, PollResult
from app.state.order_store import ActiveOrderStore
from app.theme.loader import load_theme
from app.ui.layout import browse_column_count, current_profile
from app.ui.list_models import CartModel, CatalogModel
from app.ui.theme_bridge import ThemeBridge
from app.ui.workers import (
    CancelOrderWorker,
    CheckoutStartWorker,
    CloudHealthWorker,
    InventoryLoadWorker,
    OrderPollWorker,
    ResumeOrderWorker,
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

        theme_result = load_theme(
            settings.theme_id,
            packages_dir=settings.theme_packages_dir,
        )
        self.theme = ThemeBridge(theme_result.theme, self)

        self.catalog_model = CatalogModel(self)
        self.cart_model = CartModel(self)
        self.cart_model.bind_cart(self.cart)

        self.cloud = CloudClient(settings.cloud_base)
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
        self._detail_qty = 1
        self._browse_viewport_width = current_profile().window_width
        self._boot_message = "Starting SellMate…"
        self._payment_message = "Waiting for card…"
        self._result_message = ""
        self._user_notice = ""

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(int(settings.idle_timeout_seconds * 1000))
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        self.inventory_timer = QTimer(self)
        self.inventory_timer.setInterval(
            int(settings.inventory_idle_refresh_seconds * 1000)
        )
        self.inventory_timer.timeout.connect(self._refresh_inventory_idle)

        QTimer.singleShot(0, self._bootstrap)

    # ----- Qt properties -----

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
        return self.fsm.cancel_allowed()

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

    @Property(int, notify=detailChanged)
    def detailQty(self) -> int:  # noqa: N802
        return self._detail_qty

    @Property(int, notify=statusChanged)
    def browseColumns(self) -> int:  # noqa: N802
        return browse_column_count(self._browse_viewport_width)

    @Property(int, notify=statusChanged)
    def windowWidth(self) -> int:  # noqa: N802
        return current_profile().window_width

    @Property(int, notify=statusChanged)
    def windowHeight(self) -> int:  # noqa: N802
        return current_profile().window_height

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
        self._run_health_then_inventory(resume=True)

    def _run_health_then_inventory(self, *, resume: bool) -> None:
        if self._closing:
            return
        worker = CloudHealthWorker(self.cloud)
        self._track(worker)

        def on_health(ok: bool) -> None:
            if self._closing:
                return
            self.fsm.cloud_reachable = ok
            self._load_inventory(resume=resume)

        worker.finished_ok.connect(on_health)
        worker.start()

    def _load_inventory(self, *, resume: bool) -> None:
        if self._closing:
            return
        worker = InventoryLoadWorker(self.inventory_client)
        self._track(worker)

        def ok(snap: InventorySnapshot) -> None:
            if self._closing:
                return
            self._apply_snapshot(snap)
            if resume:
                self._try_resume_order()
            elif self.fsm.screen in {AppScreen.ATTRACT, AppScreen.BROWSE}:
                self.statusChanged.emit()

        def err(msg: str) -> None:
            if self._closing:
                return
            if self.snapshot is None:
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
                self.fsm.begin_payment(order_id)
                self._set_payment_message("Resuming unfinished order…")
                self._show_screen(AppScreen.PAYMENT)
                self._start_polling(order_id)
            else:
                self.fsm.boot_ok()
                self._show_screen(AppScreen.ATTRACT)
                self.inventory_timer.start()
                self._bump_idle()

        def err(msg: str) -> None:
            if self._closing:
                return
            log_event(logger, "checkout.resume_failed", error=msg)
            self.fsm.boot_ok()
            self._show_screen(AppScreen.ATTRACT)
            self.inventory_timer.start()

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

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
        self.cart.clear()
        self.cart_model.refresh()
        self.fsm.clear_active_order()
        self.fsm.go_attract()
        self.cartChanged.emit()
        self._show_screen(AppScreen.ATTRACT)

    def _refresh_inventory_idle(self) -> None:
        if self.fsm.screen == AppScreen.ATTRACT:
            self._load_inventory(resume=False)
            health = CloudHealthWorker(self.cloud)
            self._track(health)

            def apply(ok: bool) -> None:
                self.fsm.cloud_reachable = ok
                self.statusChanged.emit()
                self.cartChanged.emit()

            health.finished_ok.connect(apply)
            health.start()

    def _set_payment_message(self, text: str) -> None:
        self._payment_message = text
        self.fsm.status_message = text
        self.statusChanged.emit()

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
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        if gate:
            self.toastRequested.emit("Checkout unavailable", gate)
            return
        if self.cart.item_count() <= 0:
            return
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
            self.fsm.begin_payment(order_id)
            self._set_payment_message("Waiting for card…")
            self.statusChanged.emit()
            self._start_polling(order_id)

        def err(msg: str) -> None:
            self.fsm.mark_failure(msg)
            self._result_message = msg
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
        worker = OrderPollWorker(self.checkout, order_id)
        self._poll_worker = worker
        self._track(worker)

        def on_update(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self.fsm.last_order_status = result.status
            self._set_payment_message(result.message)

        def on_done(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self.statusChanged.emit()
            if result.status == OrderStatus.COMPLETED:
                self.cart.clear()
                self.cart_model.refresh()
                self.cartChanged.emit()
                self.fsm.mark_success()
                self._result_message = result.message
                self._show_screen(AppScreen.SUCCESS)
                self._load_inventory(resume=False)
                QTimer.singleShot(5000, self.finishToAttract)
            elif result.terminal:
                self.fsm.mark_failure(result.message)
                self._result_message = result.message
                self._show_screen(AppScreen.FAILURE)
                self._load_inventory(resume=False)

        def on_err(msg: str) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self.fsm.mark_failure(msg)
            self._result_message = msg
            self._show_screen(AppScreen.FAILURE)

        worker.status_update.connect(on_update)
        worker.finished_ok.connect(on_done)
        worker.finished_err.connect(on_err)
        worker.start()

    @Slot()
    def cancelCheckout(self) -> None:  # noqa: N802
        order_id = self.fsm.active_order_id
        if not order_id or not self.fsm.cancel_allowed():
            return
        self._stop_polling()
        worker = CancelOrderWorker(
            self.checkout, order_id, self.fsm.last_order_status
        )
        self._track(worker)

        def ok(cancelled: bool) -> None:
            if cancelled:
                self.fsm.mark_failure("Purchase cancelled.")
                self._result_message = "Purchase cancelled."
                self.fsm.clear_active_order()
                self._show_screen(AppScreen.FAILURE)
            else:
                self.toastRequested.emit(
                    "Cancel unavailable",
                    "This order can no longer be cancelled.",
                )

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(
            lambda msg: self.toastRequested.emit("Cancel failed", msg)
        )
        worker.start()

    @Slot()
    def finishToAttract(self) -> None:  # noqa: N802
        self.cart.clear()
        self.cart_model.refresh()
        self.fsm.clear_active_order()
        self.fsm.go_attract()
        self.cartChanged.emit()
        self._show_screen(AppScreen.ATTRACT)
        self.inventory_timer.start()

    @Slot()
    def shutdown(self) -> None:
        self._closing = True
        self.idle_timer.stop()
        self.inventory_timer.stop()
        self._stop_polling()
        for worker in list(self._workers):
            if hasattr(worker, "request_stop"):
                worker.request_stop()
            if worker.isRunning():
                worker.wait(2000)
        self._workers.clear()
        log_event(logger, "app.shutdown")

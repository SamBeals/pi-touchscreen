"""Fullscreen landscape kiosk window and screen orchestration."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.api.cloud_client import CloudClient
from app.api.inventory_client import InventoryClient, InventorySnapshot
from app.config import Settings
from app.logging_setup import log_event
from app.models.cart import Cart
from app.models.order import OrderStatus, user_message_for_status
from app.models.product import Product
from app.state.app_state import AppScreen, AppStateMachine, checkout_gate_reason
from app.state.checkout_service import CheckoutService, PollResult
from app.state.order_store import ActiveOrderStore
from app.ui.styles import APP_STYLESHEET
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


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("SellMate")
        self.setStyleSheet(APP_STYLESHEET)

        self.cart = Cart()
        self.fsm = AppStateMachine()
        self.catalog: Dict[str, Product] = {}
        self.snapshot: Optional[InventorySnapshot] = None

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

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.boot_page = self._build_message_page("Starting SellMate…")
        self.fatal_page = self._build_message_page("Configuration error", danger=True)
        self.attract_page = self._build_attract()
        self.browse_page = self._build_browse()
        self.detail_page = self._build_detail()
        self.cart_page = self._build_cart()
        self.payment_page = self._build_payment()
        self.success_page = self._build_result(success=True)
        self.failure_page = self._build_result(success=False)

        for page in (
            self.boot_page,
            self.fatal_page,
            self.attract_page,
            self.browse_page,
            self.detail_page,
            self.cart_page,
            self.payment_page,
            self.success_page,
            self.failure_page,
        ):
            self.stack.addWidget(page)

        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(int(settings.idle_timeout_seconds * 1000))
        self.idle_timer.timeout.connect(self._on_idle_timeout)

        self.inventory_timer = QTimer(self)
        self.inventory_timer.setInterval(
            int(settings.inventory_idle_refresh_seconds * 1000)
        )
        self.inventory_timer.timeout.connect(self._refresh_inventory_idle)

        self._show_screen(AppScreen.BOOT)
        QTimer.singleShot(0, self._bootstrap)

    # ----- bootstrap / recovery -----

    def _bootstrap(self) -> None:
        settings = self.settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        log_event(
            logger,
            "app.bootstrap",
            machine_id=settings.machine_id,
            cloud_base=settings.cloud_base,
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
                self._render_browse_grid()

        def err(msg: str) -> None:
            if self._closing:
                return
            if self.snapshot is None:
                self.fsm.boot_fatal(f"Inventory load failed: {msg}")
                self._set_message(self.fatal_page, self.fsm.fatal_reason)
                self._show_screen(AppScreen.FATAL)
            else:
                log_event(logger, "inventory.refresh_failed", error=msg)

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _apply_snapshot(self, snap: InventorySnapshot) -> None:
        self.snapshot = snap
        self.catalog = snap.catalog()
        # Checkout requires sufficiently fresh inventory (live or cache within TTL).
        self.fsm.inventory_fresh = snap.is_fresh(
            self.settings.inventory_max_age_seconds
        )
        self._render_browse_grid()

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

    # ----- idle -----

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
        self.fsm.clear_active_order()
        self.fsm.go_attract()
        self._show_screen(AppScreen.ATTRACT)

    def _refresh_inventory_idle(self) -> None:
        if self.fsm.screen == AppScreen.ATTRACT:
            self._load_inventory(resume=False)
            health = CloudHealthWorker(self.cloud)
            self._track(health)
            health.finished_ok.connect(
                lambda ok: setattr(self.fsm, "cloud_reachable", ok)
            )
            health.start()

    # ----- screens -----

    def _show_screen(self, screen: AppScreen) -> None:
        mapping = {
            AppScreen.BOOT: self.boot_page,
            AppScreen.FATAL: self.fatal_page,
            AppScreen.ATTRACT: self.attract_page,
            AppScreen.BROWSE: self.browse_page,
            AppScreen.PRODUCT_DETAIL: self.detail_page,
            AppScreen.CART: self.cart_page,
            AppScreen.PAYMENT: self.payment_page,
            AppScreen.SUCCESS: self.success_page,
            AppScreen.FAILURE: self.failure_page,
        }
        self.fsm.screen = screen
        self.stack.setCurrentWidget(mapping[screen])
        self._bump_idle()

    def _build_message_page(self, text: str, danger: bool = False) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        label = QLabel(text)
        label.setObjectName("title")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        if danger:
            label.setStyleSheet("color: #FCA5A5;")
        layout.addWidget(label)
        layout.addStretch()
        page._message_label = label  # type: ignore[attr-defined]
        return page

    def _set_message(self, page: QWidget, text: str) -> None:
        label = getattr(page, "_message_label", None)
        if label:
            label.setText(text)

    def _build_attract(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        title = QLabel("SellMate")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Touch to shop")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Start shopping")
        btn.setMinimumHeight(72)
        btn.clicked.connect(self._enter_browse)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        page.mousePressEvent = lambda _e: self._enter_browse()  # type: ignore[method-assign]
        return page

    def _build_browse(self) -> QWidget:
        page = QWidget()
        root = QVBoxLayout(page)
        header = QHBoxLayout()
        title = QLabel("Choose a product")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.browse_cart_btn = QPushButton("Cart (0)")
        self.browse_cart_btn.clicked.connect(self._open_cart)
        header.addWidget(self.browse_cart_btn)
        root.addLayout(header)

        self.browse_status = QLabel("")
        self.browse_status.setObjectName("subtitle")
        root.addWidget(self.browse_status)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_host = QWidget()
        self.grid_layout = QGridLayout(self.grid_host)
        self.grid_layout.setSpacing(16)
        scroll.setWidget(self.grid_host)
        root.addWidget(scroll)
        return page

    def _render_browse_grid(self) -> None:
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        products = self.snapshot.sellable() if self.snapshot else []
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        self.browse_status.setText(gate or f"{len(products)} available")

        cols = 3
        for idx, product in enumerate(products):
            card = self._product_card(product)
            self.grid_layout.addWidget(card, idx // cols, idx % cols)
        self.browse_cart_btn.setText(f"Cart ({self.cart.item_count()})")

    def _product_card(self, product: Product) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        layout = QVBoxLayout(frame)
        name = QLabel(product.name)
        name.setWordWrap(True)
        name.setObjectName("subtitle")
        price = QLabel(_money(product.price_cents))
        price.setObjectName("price")
        stock = QLabel(f"{product.qty} in stock · {product.slot_id}")
        btn = QPushButton("View")
        btn.clicked.connect(lambda _=False, s=product.slot_id: self._open_detail(s))
        layout.addWidget(name)
        layout.addWidget(price)
        layout.addWidget(stock)
        layout.addWidget(btn)
        frame.setMinimumHeight(180)
        return frame

    def _build_detail(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.detail_name = QLabel("")
        self.detail_name.setObjectName("title")
        self.detail_price = QLabel("")
        self.detail_price.setObjectName("price")
        self.detail_meta = QLabel("")
        self.detail_meta.setObjectName("subtitle")
        self.detail_qty_label = QLabel("Qty: 1")
        btns = QHBoxLayout()
        minus = QPushButton("−")
        minus.setObjectName("secondary")
        plus = QPushButton("+")
        plus.setObjectName("secondary")
        add = QPushButton("Add to cart")
        add.setObjectName("success")
        back = QPushButton("Back")
        back.setObjectName("secondary")
        minus.clicked.connect(lambda: self._detail_adjust(-1))
        plus.clicked.connect(lambda: self._detail_adjust(1))
        add.clicked.connect(self._detail_add)
        back.clicked.connect(lambda: self._show_screen(AppScreen.BROWSE))
        btns.addWidget(minus)
        btns.addWidget(self.detail_qty_label)
        btns.addWidget(plus)
        btns.addStretch()
        btns.addWidget(back)
        btns.addWidget(add)
        layout.addWidget(self.detail_name)
        layout.addWidget(self.detail_price)
        layout.addWidget(self.detail_meta)
        layout.addStretch()
        layout.addLayout(btns)
        self._detail_qty = 1
        return page

    def _build_cart(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Your cart")
        title.setObjectName("title")
        layout.addWidget(title)
        self.cart_list = QVBoxLayout()
        layout.addLayout(self.cart_list)
        layout.addStretch()
        self.cart_total = QLabel("Total: $0.00")
        self.cart_total.setObjectName("price")
        layout.addWidget(self.cart_total)
        row = QHBoxLayout()
        back = QPushButton("Continue shopping")
        back.setObjectName("secondary")
        back.clicked.connect(self._enter_browse)
        checkout = QPushButton("Checkout")
        checkout.setObjectName("success")
        checkout.clicked.connect(self._start_checkout)
        self.cart_checkout_btn = checkout
        row.addWidget(back)
        row.addStretch()
        row.addWidget(checkout)
        layout.addLayout(row)
        return page

    def _build_payment(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        self.payment_title = QLabel("Payment")
        self.payment_title.setObjectName("title")
        self.payment_title.setAlignment(Qt.AlignCenter)
        self.payment_status = QLabel("Waiting for card…")
        self.payment_status.setObjectName("subtitle")
        self.payment_status.setAlignment(Qt.AlignCenter)
        self.payment_status.setWordWrap(True)
        layout.addWidget(self.payment_title)
        layout.addWidget(self.payment_status)
        layout.addStretch()
        self.cancel_btn = QPushButton("Cancel purchase")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.clicked.connect(self._cancel_checkout)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.cancel_btn)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _build_result(self, *, success: bool) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        label = QLabel("Purchase complete" if success else "Something went wrong")
        label.setObjectName("title")
        label.setAlignment(Qt.AlignCenter)
        detail = QLabel("")
        detail.setObjectName("subtitle")
        detail.setAlignment(Qt.AlignCenter)
        detail.setWordWrap(True)
        btn = QPushButton("Done")
        btn.setObjectName("success" if success else "secondary")
        btn.clicked.connect(self._finish_to_attract)
        layout.addWidget(label)
        layout.addWidget(detail)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        page._detail = detail  # type: ignore[attr-defined]
        return page

    # ----- actions -----

    def _enter_browse(self) -> None:
        self.fsm.go_browse()
        self._render_browse_grid()
        self._show_screen(AppScreen.BROWSE)

    def _open_detail(self, slot_id: str) -> None:
        product = self.catalog.get(slot_id)
        if not product:
            return
        self.fsm.open_product(slot_id)
        self._detail_qty = 1
        self.detail_name.setText(product.name)
        self.detail_price.setText(_money(product.price_cents))
        self.detail_meta.setText(f"Slot {product.slot_id} · {product.qty} available")
        self.detail_qty_label.setText("Qty: 1")
        self._show_screen(AppScreen.PRODUCT_DETAIL)
        self._bump_idle()

    def _detail_adjust(self, delta: int) -> None:
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        if not product:
            return
        self._detail_qty = max(1, min(product.qty, self._detail_qty + delta))
        self.detail_qty_label.setText(f"Qty: {self._detail_qty}")
        self._bump_idle()

    def _detail_add(self) -> None:
        product = self.catalog.get(self.fsm.selected_slot_id or "")
        if not product:
            return
        try:
            self.cart.add(product, self._detail_qty)
        except ValueError as exc:
            QMessageBox.warning(self, "Cart", str(exc))
            return
        self._enter_browse()

    def _open_cart(self) -> None:
        self._render_cart()
        self.fsm.go_cart()
        self._show_screen(AppScreen.CART)

    def _render_cart(self) -> None:
        while self.cart_list.count():
            item = self.cart_list.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for line in self.cart.lines():
            row = QLabel(
                f"{line.product.name} × {line.quantity} — {_money(line.line_total_cents)}"
            )
            row.setObjectName("subtitle")
            self.cart_list.addWidget(row)
        self.cart_total.setText(f"Total: {_money(self.cart.total_cents())}")
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        self.cart_checkout_btn.setEnabled(
            self.cart.item_count() > 0 and gate is None
        )
        if gate:
            self.cart_total.setText(f"Total: {_money(self.cart.total_cents())} — {gate}")

    def _start_checkout(self) -> None:
        gate = checkout_gate_reason(
            cloud_reachable=self.fsm.cloud_reachable,
            inventory_fresh=self.fsm.inventory_fresh,
        )
        if gate:
            QMessageBox.warning(self, "Checkout unavailable", gate)
            return
        if self.cart.item_count() <= 0:
            return
        # Totals come only from cart lines priced from loaded inventory.
        self.fsm.screen = AppScreen.PAYMENT
        self.fsm.status_message = "Preparing checkout…"
        self.fsm.error_message = ""
        self.fsm.last_order_status = OrderStatus.CREATED
        self._set_payment_message("Preparing checkout…")
        self.cancel_btn.setEnabled(True)
        self._show_screen(AppScreen.PAYMENT)
        self.idle_timer.stop()

        worker = CheckoutStartWorker(self.checkout, self.cart)
        self._track(worker)

        def ok(order_id: str) -> None:
            self.fsm.begin_payment(order_id)
            self._set_payment_message("Waiting for card…")
            self.cancel_btn.setEnabled(self.fsm.cancel_allowed())
            self._start_polling(order_id)

        def err(msg: str) -> None:
            self.fsm.mark_failure(msg)
            self.failure_page._detail.setText(msg)  # type: ignore[attr-defined]
            self._show_screen(AppScreen.FAILURE)

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(err)
        worker.start()

    def _stop_polling(self) -> None:
        worker = self._poll_worker
        if worker is None:
            return
        try:
            worker.status_update.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.finished_ok.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            worker.finished_err.disconnect()
        except (RuntimeError, TypeError):
            pass
        worker.request_stop()
        if worker.isRunning():
            worker.wait(3000)
        self._poll_worker = None

    def _start_polling(self, order_id: str) -> None:
        if self._closing:
            return
        # Prevent duplicate poll loops across retries / screen transitions.
        self._stop_polling()
        worker = OrderPollWorker(self.checkout, order_id)
        self._poll_worker = worker
        self._track(worker)

        def on_update(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self.fsm.last_order_status = result.status
            self._set_payment_message(result.message)
            self.cancel_btn.setEnabled(self.fsm.cancel_allowed())

        def on_done(result: PollResult) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self.cancel_btn.setEnabled(False)
            if result.status == OrderStatus.COMPLETED:
                self.cart.clear()
                self.fsm.mark_success()
                self.success_page._detail.setText(result.message)  # type: ignore[attr-defined]
                self._show_screen(AppScreen.SUCCESS)
                self._load_inventory(resume=False)
                QTimer.singleShot(5000, self._finish_to_attract)
            elif result.terminal:
                self.fsm.mark_failure(result.message)
                self.failure_page._detail.setText(result.message)  # type: ignore[attr-defined]
                self._show_screen(AppScreen.FAILURE)
                self._load_inventory(resume=False)

        def on_err(msg: str) -> None:
            if self._closing or self._poll_worker is not worker:
                return
            self._poll_worker = None
            self.fsm.mark_failure(msg)
            self.failure_page._detail.setText(msg)  # type: ignore[attr-defined]
            self._show_screen(AppScreen.FAILURE)

        worker.status_update.connect(on_update)
        worker.finished_ok.connect(on_done)
        worker.finished_err.connect(on_err)
        worker.start()

    def _cancel_checkout(self) -> None:
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
                self.failure_page._detail.setText("Purchase cancelled.")  # type: ignore[attr-defined]
                self.fsm.clear_active_order()
                self._show_screen(AppScreen.FAILURE)
            else:
                QMessageBox.information(
                    self,
                    "Cancel unavailable",
                    "This order can no longer be cancelled.",
                )

        worker.finished_ok.connect(ok)
        worker.finished_err.connect(
            lambda msg: QMessageBox.warning(self, "Cancel failed", msg)
        )
        worker.start()

    def _finish_to_attract(self) -> None:
        self.cart.clear()
        self.fsm.clear_active_order()
        self.fsm.go_attract()
        self._show_screen(AppScreen.ATTRACT)
        self.inventory_timer.start()

    def _set_payment_message(self, text: str) -> None:
        self.payment_status.setText(text)

    def _track(self, worker) -> None:
        self._workers.append(worker)
        worker.finished.connect(lambda w=worker: self._workers.remove(w) if w in self._workers else None)

    def closeEvent(self, event) -> None:  # noqa: N802
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
        super().closeEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._bump_idle()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        self._bump_idle()
        if event.key() == Qt.Key_Escape and not self.settings.fullscreen:
            self.close()
        super().keyPressEvent(event)

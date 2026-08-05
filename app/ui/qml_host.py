"""QML application host for the SellMate kiosk."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QUrl, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from app.config import Settings
from app.logging_setup import log_event
from app.ui.app_controller import AppController
from app.ui.layout import current_profile, portrait_geometry_warning
from app.ui.theme_provider import register_theme_singleton

logger = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent / "qml"


class QmlHost(QObject):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._shutting_down = False
        self._portrait_warned = False

        # Basic style allows control customization (background/contentItem).
        os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
        try:
            QQuickStyle.setStyle("Basic")
        except Exception:  # noqa: BLE001
            logger.debug("qt.quick.style_set_failed", exc_info=True)

        # Theme + AppController before the engine so the Theme singleton
        # is registered prior to QQmlApplicationEngine construction.
        self.controller = AppController(settings, self)
        register_theme_singleton(self.controller.theme)

        self.engine = QQmlApplicationEngine(self)
        self.engine.addImportPath(str(QML_DIR))

        # Engine owns the theme for the QML lifetime.
        self.controller.theme.setParent(self.engine)

        # App / models remain context properties (slots + signals).
        # Theme is the SellMate 1.0 singleton — do not also set as context
        # property (avoids dual-binding / teardown null races).
        self.engine.rootContext().setContextProperty("App", self.controller)
        self.engine.rootContext().setContextProperty(
            "CatalogModel", self.controller.catalog_model
        )
        self.engine.rootContext().setContextProperty(
            "CartModel", self.controller.cart_model
        )
        self.controller.toastRequested.connect(self._on_toast)

        main_qml = QML_DIR / "main.qml"
        self.engine.load(QUrl.fromLocalFile(str(main_qml)))
        if not self.engine.rootObjects():
            raise RuntimeError(f"Failed to load QML: {main_qml}")

        self.window = self.engine.rootObjects()[0]
        if isinstance(self.window, QQuickWindow):
            if settings.fullscreen:
                self.window.showFullScreen()
            else:
                width, height = current_profile().window_size
                self.window.setWidth(width)
                self.window.setHeight(height)
                self.window.show()

            self.window.widthChanged.connect(self._on_window_geometry_changed)
            self.window.heightChanged.connect(self._on_window_geometry_changed)
            self._sync_and_validate_geometry()

        self._validate_primary_screen()

    def _validate_primary_screen(self) -> None:
        app = QGuiApplication.instance()
        if app is None:
            return
        screen = app.primaryScreen()
        if screen is None:
            return
        geo = screen.geometry()
        self._warn_if_not_portrait(
            geo.width(),
            geo.height(),
            source="primary_screen",
        )

    def _on_window_geometry_changed(self) -> None:
        self._sync_and_validate_geometry()

    def _sync_and_validate_geometry(self) -> None:
        if not isinstance(self.window, QQuickWindow):
            return
        width = int(self.window.width())
        height = int(self.window.height())
        self.controller.setWindowGeometry(width, height)
        self._warn_if_not_portrait(width, height, source="window")

    def _warn_if_not_portrait(self, width: int, height: int, *, source: str) -> None:
        warning = portrait_geometry_warning(width, height)
        if not warning:
            return
        # One structured warning per process is enough; geometry may re-fire.
        if self._portrait_warned:
            return
        self._portrait_warned = True
        log_event(
            logger,
            "display.portrait_misconfigured",
            width=width,
            height=height,
            source=source,
            message=warning,
        )
        logger.warning("%s", warning)

    @Slot(str, str)
    def _on_toast(self, title: str, message: str) -> None:
        # QML shows notices via App-driven overlays when present; log as fallback.
        logger.info("ui.toast title=%s message=%s", title, message)
        if hasattr(self.window, "showToast"):
            self.window.showToast(title, message)

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True

        # Stop workers/timers while QML context objects are still valid.
        self.controller.shutdown()

        # Tear down the QML tree before context properties / singletons die,
        # so bindings do not re-evaluate against null App/Theme.
        try:
            self.controller.toastRequested.disconnect(self._on_toast)
        except (RuntimeError, TypeError):
            pass

        for root in list(self.engine.rootObjects()):
            root.deleteLater()
        self.engine.clearComponentCache()
        app = QGuiApplication.instance()
        if app is not None:
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

        self.window = None

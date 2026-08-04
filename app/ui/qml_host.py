"""QML application host for the SellMate kiosk."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from app.config import Settings
from app.ui.app_controller import AppController
from app.ui.layout import current_profile

logger = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent / "qml"


class QmlHost(QObject):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.controller = AppController(settings, self)
        self.engine = QQmlApplicationEngine(self)
        self.engine.addImportPath(str(QML_DIR))
        self.engine.rootContext().setContextProperty("App", self.controller)
        self.engine.rootContext().setContextProperty("Theme", self.controller.theme)
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

    @Slot(str, str)
    def _on_toast(self, title: str, message: str) -> None:
        # QML shows notices via App-driven overlays when present; log as fallback.
        logger.info("ui.toast title=%s message=%s", title, message)
        if hasattr(self.window, "showToast"):
            self.window.showToast(title, message)

    def shutdown(self) -> None:
        self.controller.shutdown()

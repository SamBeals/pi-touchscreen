"""QML application host for the SellMate kiosk."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import QEvent, QFileSystemWatcher, QObject, QTimer, QUrl, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from app.config import Settings
from app.logging_setup import log_event
from app.theme.fonts import register_package_fonts
from app.ui.app_controller import AppController
from app.ui.layout import current_profile, portrait_geometry_warning
from app.ui.theme_provider import register_theme_singleton

logger = logging.getLogger(__name__)

QML_DIR = Path(__file__).resolve().parent / "qml"
THEMES_DIR = Path(__file__).resolve().parents[2] / "themes"


class QmlHost(QObject):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._shutting_down = False
        self._portrait_warned = False
        self._watcher: QFileSystemWatcher | None = None
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(250)
        self._reload_timer.timeout.connect(self._reload_qml)

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
        # Fonts require QGuiApplication (created in __main__ before QmlHost).
        register_package_fonts(self.controller.theme.packageDir())

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

        self._load_main_qml()
        if not settings.fullscreen and self._hot_reload_enabled():
            self._start_hot_reload_watcher()

    def _hot_reload_enabled(self) -> bool:
        raw = os.environ.get("QML_HOT_RELOAD", "").strip().lower()
        if raw in {"0", "false", "no", "off"}:
            return False
        if raw in {"1", "true", "yes", "on"}:
            return True
        # Default on for windowed Mac/dev runs.
        return not self.settings.fullscreen

    def _load_main_qml(self) -> None:
        main_qml = QML_DIR / "main.qml"
        self.engine.load(QUrl.fromLocalFile(str(main_qml)))
        if not self.engine.rootObjects():
            raise RuntimeError(f"Failed to load QML: {main_qml}")

        self.window = self.engine.rootObjects()[0]
        if isinstance(self.window, QQuickWindow):
            if self.settings.fullscreen:
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

    def _watch_paths(self) -> list[str]:
        paths: list[str] = []
        for root, dirs, files in os.walk(QML_DIR):
            # Skip caches
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            paths.append(root)
            for name in files:
                if name.endswith((".qml", ".js")):
                    paths.append(str(Path(root) / name))
        theme_pkg = THEMES_DIR / self.settings.theme_id
        if theme_pkg.is_dir():
            paths.append(str(theme_pkg))
            theme_json = theme_pkg / "theme.json"
            if theme_json.is_file():
                paths.append(str(theme_json))
        return paths

    def _start_hot_reload_watcher(self) -> None:
        self._watcher = QFileSystemWatcher(self)
        paths = self._watch_paths()
        for path in paths:
            self._watcher.addPath(path)
        self._watcher.directoryChanged.connect(self._on_watch_event)
        self._watcher.fileChanged.connect(self._on_watch_event)
        log_event(
            logger,
            "ui.hot_reload_enabled",
            watched=len(paths),
            qml_dir=str(QML_DIR),
        )

    @Slot(str)
    def _on_watch_event(self, _path: str) -> None:
        if self._shutting_down:
            return
        self._reload_timer.start()

    @Slot()
    def _reload_qml(self) -> None:
        if self._shutting_down:
            return
        logger.info("ui.qml_hot_reload")
        try:
            for root in list(self.engine.rootObjects()):
                root.deleteLater()
            self.engine.clearComponentCache()
            app = QGuiApplication.instance()
            if app is not None:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                app.processEvents()
            self._load_main_qml()
            # Re-arm file watches (editors often replace files atomically).
            if self._watcher is not None:
                existing = set(self._watcher.files()) | set(self._watcher.directories())
                for path in self._watch_paths():
                    if path not in existing:
                        self._watcher.addPath(path)
        except Exception:  # noqa: BLE001
            logger.exception("ui.qml_hot_reload_failed")

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

        if self._reload_timer.isActive():
            self._reload_timer.stop()
        if self._watcher is not None:
            try:
                self._watcher.directoryChanged.disconnect(self._on_watch_event)
                self._watcher.fileChanged.disconnect(self._on_watch_event)
            except (RuntimeError, TypeError):
                pass
            self._watcher = None

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

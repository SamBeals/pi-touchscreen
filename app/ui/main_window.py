"""
Deprecated Widgets UI.

The kiosk presentation layer is Qt Quick / QML via `app.ui.qml_host.QmlHost`
and `app.ui.app_controller.AppController`. This module remains only as a
compatibility import shim for older scripts.
"""

from __future__ import annotations

from app.ui.app_controller import AppController
from app.ui.qml_host import QmlHost

# Historical name used by early smoke scripts.
MainWindow = QmlHost

__all__ = ["AppController", "MainWindow", "QmlHost"]

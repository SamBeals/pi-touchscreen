"""Central theme provider for QML.

Guarantees a complete ThemeBridge before any QML document is loaded.
Renter packages flow through load_theme(); failures fall back to the
bundled SellMate default. Register the singleton *before* creating
QQmlApplicationEngine (PySide6 requirement).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import QObject
from PySide6.QtQml import qmlRegisterSingletonInstance

from app.theme.loader import default_resolved_theme, load_theme
from app.ui.theme_bridge import ThemeBridge

logger = logging.getLogger(__name__)

THEME_URI = "SellMate"
THEME_MAJOR = 1
THEME_MINOR = 0
THEME_QML_NAME = "Theme"

_registered = False


def create_theme_bridge(
    *,
    theme_id: str,
    packages_dir: Union[str, Path],
    parent: Optional[QObject] = None,
) -> ThemeBridge:
    """Load renter/bundled theme; never returns a ThemeBridge without a full theme."""
    try:
        result = load_theme(theme_id, packages_dir=packages_dir)
        theme = result.theme
    except Exception:  # noqa: BLE001
        logger.exception("theme.provider_load_failed theme_id=%s", theme_id)
        theme = default_resolved_theme()
    return ThemeBridge(theme, parent)


def register_theme_singleton(bridge: ThemeBridge) -> None:
    """
    Register Theme as a QML singleton.

    Must be called before QQmlApplicationEngine is constructed.
    Safe to call once per process; subsequent calls are no-ops.
    """
    global _registered
    if _registered:
        return
    qmlRegisterSingletonInstance(
        ThemeBridge,
        THEME_URI,
        THEME_MAJOR,
        THEME_MINOR,
        THEME_QML_NAME,
        bridge,
    )
    _registered = True

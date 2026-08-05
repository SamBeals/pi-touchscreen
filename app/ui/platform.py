"""Qt platform selection for SellMate touchscreen.

Portrait display mapping is an OS concern. This module only chooses a Qt
platform plugin so the app can talk to the compositor natively on the Pi
(Wayland) while remaining compatible with macOS and headless tests.
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)


def configure_qt_platform() -> None:
    """
    Set a default QT_QPA_PLATFORM when unset.

    - Never overrides an explicit value (e.g. offscreen smoke tests).
    - macOS: leave unset (Cocoa).
    - Linux: prefer Wayland, fall back to XCB (X11 / Xwayland) if needed.
    """
    if os.environ.get("QT_QPA_PLATFORM", "").strip():
        return

    if sys.platform == "darwin":
        return

    if sys.platform.startswith("linux"):
        # Prefer native Wayland when the session exposes it; otherwise Qt
        # tries xcb. Avoid forcing wayland-only so X11 sessions still boot.
        os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
        logger.debug(
            "qt.platform.default platform=%s wayland_display=%s",
            os.environ["QT_QPA_PLATFORM"],
            os.environ.get("WAYLAND_DISPLAY", ""),
        )

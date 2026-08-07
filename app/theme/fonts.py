"""Register theme package fonts with Qt's application font database."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FONT_SUFFIXES = {".ttf", ".otf", ".ttc"}
# path -> family names from a successful addApplicationFont call
_registered: dict[str, tuple[str, ...]] = {}


def register_package_fonts(package_dir: str | Path) -> tuple[str, ...]:
    """
    Load ``assets/fonts/*.{ttf,otf,ttc}`` from a theme package.

    Safe to call repeatedly — already-registered paths are skipped.
    Returns distinct family names for fonts in this package directory.

    Must be called with a live ``QGuiApplication`` (not ``QCoreApplication``).
    """
    fonts_dir = Path(package_dir) / "assets" / "fonts"
    if not fonts_dir.is_dir():
        return ()

    from PySide6.QtGui import QFontDatabase, QGuiApplication

    if QGuiApplication.instance() is None:
        logger.debug("theme.font_skip_no_gui package=%s", package_dir)
        return ()

    families: list[str] = []
    seen: set[str] = set()
    for path in sorted(fonts_dir.iterdir()):
        if path.suffix.lower() not in _FONT_SUFFIXES or not path.is_file():
            continue
        key = str(path.resolve())
        if key in _registered:
            for family in _registered[key]:
                if family not in seen:
                    seen.add(family)
                    families.append(family)
            continue

        font_id = QFontDatabase.addApplicationFont(key)
        if font_id < 0:
            logger.warning("theme.font_load_failed path=%s", key)
            continue
        loaded = tuple(QFontDatabase.applicationFontFamilies(font_id))
        _registered[key] = loaded
        logger.info("theme.font_loaded path=%s families=%s", path.name, list(loaded))
        for family in loaded:
            if family and family not in seen:
                seen.add(family)
                families.append(family)
    return tuple(families)

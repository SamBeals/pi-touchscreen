from __future__ import annotations

import unittest

from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QQmlEngine

from app.theme.loader import default_resolved_theme, load_theme
from app.theme.schema import COLOR_KEYS, DEFAULT_THEME_ID
from app.ui.theme_bridge import ThemeBridge
from app.ui.theme_provider import (
    THEME_QML_NAME,
    THEME_URI,
    create_theme_bridge,
    register_theme_singleton,
)


class TestThemeProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QCoreApplication.instance() is None:
            cls._app = QCoreApplication([])
        else:
            cls._app = QCoreApplication.instance()

    def test_default_resolved_theme_complete(self):
        theme = default_resolved_theme()
        self.assertEqual(theme.id, DEFAULT_THEME_ID)
        for key in COLOR_KEYS:
            self.assertIn(key, theme.colors)
            self.assertTrue(theme.colors[key].startswith("#"))
        self.assertTrue(theme.font_family)
        self.assertGreater(theme.corner_radius, 0)

    def test_bridge_never_null_properties(self):
        bridge = ThemeBridge(None)
        self.assertEqual(bridge.id, DEFAULT_THEME_ID)
        self.assertTrue(bridge.primary)
        self.assertTrue(bridge.fontFamily)
        self.assertTrue(bridge.background)
        self.assertTrue(bridge.border)
        self.assertTrue(bridge.imageWell)
        self.assertEqual(bridge.squareRadius, 8)

    def test_create_theme_bridge_missing_package(self):
        bridge = create_theme_bridge(
            theme_id="does-not-exist",
            packages_dir="/nonexistent",
        )
        self.assertEqual(bridge.id, DEFAULT_THEME_ID)
        self.assertTrue(bridge.usedFallback)
        self.assertTrue(bridge.primary)

    def test_register_singleton_before_engine(self):
        # Fresh bridge; registration is process-global — call is idempotent.
        bridge = create_theme_bridge(
            theme_id=DEFAULT_THEME_ID,
            packages_dir="/nonexistent",
        )
        register_theme_singleton(bridge)
        register_theme_singleton(bridge)  # no-op second call
        engine = QQmlEngine()
        bridge.setParent(engine)
        self.assertIs(bridge.parent(), engine)
        # Smoke: URI constants stay stable for QML imports.
        self.assertEqual(THEME_URI, "SellMate")
        self.assertEqual(THEME_QML_NAME, "Theme")


class TestLoadThemeFallback(unittest.TestCase):
    def test_load_theme_always_returns_theme(self):
        result = load_theme("missing", packages_dir="/nope")
        self.assertIsNotNone(result.theme)
        self.assertTrue(result.theme.used_fallback)


if __name__ == "__main__":
    unittest.main()

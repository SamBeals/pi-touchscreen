from __future__ import annotations

import os
import unittest
from unittest import mock

from app.ui.layout import (
    BROWSE_MAX_COLUMNS,
    DEV_WINDOW_HEIGHT,
    DEV_WINDOW_WIDTH,
    PI_LOGICAL_HEIGHT,
    PI_LOGICAL_WIDTH,
    PORTRAIT,
    browse_column_count,
    current_profile,
    portrait_geometry_warning,
)
from app.ui.platform import configure_qt_platform


class TestLayout(unittest.TestCase):
    def test_current_profile_is_portrait_only(self):
        profile = current_profile()
        self.assertIs(profile, PORTRAIT)
        self.assertEqual(profile.window_size, (DEV_WINDOW_WIDTH, DEV_WINDOW_HEIGHT))
        self.assertLess(profile.window_width, profile.window_height)

    def test_no_landscape_exports(self):
        import app.ui.layout as layout_mod

        self.assertFalse(hasattr(layout_mod, "LANDSCAPE"))
        self.assertFalse(hasattr(layout_mod, "Orientation"))

    def test_pi_logical_geometry_is_portrait(self):
        self.assertEqual((PI_LOGICAL_WIDTH, PI_LOGICAL_HEIGHT), (600, 1024))
        self.assertLess(PI_LOGICAL_WIDTH, PI_LOGICAL_HEIGHT)

    def test_dev_window_browse_two_columns(self):
        profile = current_profile()
        self.assertEqual(profile.browse_columns_at_target, 2)
        self.assertEqual(browse_column_count(DEV_WINDOW_WIDTH, profile), 2)

    def test_pi_logical_width_is_one_column(self):
        self.assertEqual(browse_column_count(PI_LOGICAL_WIDTH), 1)

    def test_narrow_portrait_falls_back_to_one_column(self):
        self.assertEqual(browse_column_count(480, PORTRAIT), 1)

    def test_never_opens_three_columns(self):
        self.assertEqual(browse_column_count(2400, PORTRAIT), BROWSE_MAX_COLUMNS)
        self.assertEqual(BROWSE_MAX_COLUMNS, 2)

    def test_touch_minimum_dimensions(self):
        profile = current_profile()
        self.assertGreaterEqual(profile.button_min_height, 72)
        self.assertGreaterEqual(profile.card_min_height, 200)

    def test_portrait_geometry_warning_on_landscape(self):
        msg = portrait_geometry_warning(1024, 600)
        self.assertIsNotNone(msg)
        self.assertIn("landscape", msg.lower())
        self.assertIn("will not rotate", msg.lower())

    def test_portrait_geometry_ok(self):
        self.assertIsNone(portrait_geometry_warning(600, 1024))
        self.assertIsNone(portrait_geometry_warning(800, 1280))


class TestPlatform(unittest.TestCase):
    def test_configure_skips_when_already_set(self):
        with mock.patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=False):
            configure_qt_platform()
            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "offscreen")

    def test_configure_skips_on_darwin(self):
        env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("app.ui.platform.sys.platform", "darwin"):
                configure_qt_platform()
                self.assertNotIn("QT_QPA_PLATFORM", os.environ)

    def test_configure_prefers_wayland_on_linux(self):
        env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch("app.ui.platform.sys.platform", "linux"):
                configure_qt_platform()
                self.assertEqual(os.environ["QT_QPA_PLATFORM"], "wayland;xcb")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.ui.layout import (
    LANDSCAPE,
    PORTRAIT,
    browse_column_count,
    current_profile,
)


class TestLayout(unittest.TestCase):
    def test_current_profile_is_portrait(self):
        profile = current_profile()
        self.assertIs(profile, PORTRAIT)
        self.assertEqual(profile.orientation, "portrait")
        self.assertIsNot(profile, LANDSCAPE)

    def test_portrait_window_size(self):
        width, height = current_profile().window_size
        self.assertEqual(width, 800)
        self.assertEqual(height, 1280)

    def test_portrait_browse_two_columns_at_target_width(self):
        profile = current_profile()
        self.assertEqual(profile.browse_columns_at_target, 2)
        self.assertEqual(browse_column_count(800, profile), 2)
        self.assertEqual(browse_column_count(profile.window_width), 2)

    def test_narrow_portrait_falls_back_to_one_column(self):
        self.assertEqual(browse_column_count(480, PORTRAIT), 1)

    def test_portrait_never_opens_three_columns(self):
        self.assertEqual(browse_column_count(2400, PORTRAIT), 2)

    def test_touch_minimum_dimensions(self):
        profile = current_profile()
        self.assertGreaterEqual(profile.button_min_height, 72)
        self.assertGreaterEqual(profile.card_min_height, 200)


if __name__ == "__main__":
    unittest.main()

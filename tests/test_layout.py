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

    def test_portrait_browse_one_column_at_target_width(self):
        profile = current_profile()
        self.assertEqual(profile.browse_columns_at_target, 1)
        self.assertEqual(browse_column_count(800, profile), 1)
        self.assertEqual(browse_column_count(profile.window_width), 1)

    def test_wider_portrait_may_use_two_columns(self):
        # Usable width must fit two min columns after margins.
        self.assertEqual(browse_column_count(1200, PORTRAIT), 2)
        # Portrait never opens a third column.
        self.assertEqual(browse_column_count(2400, PORTRAIT), 2)

    def test_touch_minimum_dimensions(self):
        profile = current_profile()
        self.assertGreaterEqual(profile.button_min_height, 72)
        self.assertGreaterEqual(profile.card_min_height, 200)


if __name__ == "__main__":
    unittest.main()

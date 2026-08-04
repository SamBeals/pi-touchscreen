from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.theme.loader import bundled_themes_dir, load_theme
from app.theme.schema import (
    CARD_MIN_HEIGHT,
    DEFAULT_THEME_ID,
    PRIMARY_BUTTON_MIN_HEIGHT,
    SECONDARY_BUTTON_MIN_HEIGHT,
)


class TestThemeLoader(unittest.TestCase):
    def test_loads_bundled_default(self):
        result = load_theme(DEFAULT_THEME_ID, packages_dir="/nonexistent")
        self.assertEqual(result.theme.id, DEFAULT_THEME_ID)
        self.assertEqual(result.theme.business_name, "SellMate")
        self.assertFalse(result.errors)
        self.assertGreaterEqual(result.theme.primary_button_min_height, PRIMARY_BUTTON_MIN_HEIGHT)
        self.assertGreaterEqual(
            result.theme.secondary_button_min_height, SECONDARY_BUTTON_MIN_HEIGHT
        )
        self.assertGreaterEqual(result.theme.card_min_height, CARD_MIN_HEIGHT)

    def test_missing_theme_falls_back_to_default(self):
        result = load_theme("does-not-exist", packages_dir="/nonexistent")
        self.assertTrue(result.errors)
        self.assertEqual(result.theme.id, DEFAULT_THEME_ID)
        self.assertTrue(result.theme.used_fallback)

    def test_invalid_colors_fall_back_fieldwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "bad-colors"
            pkg.mkdir()
            data = json.loads((bundled_themes_dir() / DEFAULT_THEME_ID / "theme.json").read_text())
            data["id"] = "bad-colors"
            data["colors"]["primary"] = "not-a-color"
            data["colors"]["text"] = "#111827"  # same as background → contrast fail
            (pkg / "theme.json").write_text(json.dumps(data), encoding="utf-8")
            result = load_theme("bad-colors", packages_dir=root)
            self.assertEqual(result.theme.id, "bad-colors")
            self.assertEqual(result.theme.colors["primary"], "#2563EB")
            self.assertNotEqual(result.theme.colors["text"], "#111827")
            self.assertTrue(result.warnings)

    def test_unsupported_schema_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "future"
            pkg.mkdir()
            (pkg / "theme.json").write_text(
                json.dumps({"schema_version": 99, "id": "future"}),
                encoding="utf-8",
            )
            result = load_theme("future", packages_dir=root)
            self.assertTrue(result.theme.used_fallback)
            self.assertEqual(result.theme.id, DEFAULT_THEME_ID)

    def test_renter_overlay_business_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "acme"
            pkg.mkdir()
            data = json.loads((bundled_themes_dir() / DEFAULT_THEME_ID / "theme.json").read_text())
            data["id"] = "acme"
            data["brand"]["business_name"] = "Acme Cafe"
            data["chrome"]["attract_headline"] = "Welcome to Acme"
            (pkg / "theme.json").write_text(json.dumps(data), encoding="utf-8")
            result = load_theme("acme", packages_dir=root)
            self.assertEqual(result.theme.business_name, "Acme Cafe")
            self.assertEqual(result.theme.attract_headline, "Welcome to Acme")
            self.assertFalse(result.theme.used_fallback)

    def test_bundled_light_theme(self):
        result = load_theme("sellmate-light", packages_dir="/nonexistent")
        self.assertEqual(result.theme.id, "sellmate-light")
        self.assertEqual(result.theme.mode, "light")
        self.assertFalse(result.theme.used_fallback)
        self.assertEqual(result.theme.background.type, "solid")


if __name__ == "__main__":
    unittest.main()

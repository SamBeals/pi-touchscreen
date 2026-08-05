"""
Portrait layout metrics for the SellMate touchscreen.

Portrait is a permanent hardware invariant: the panel is always mounted
vertically. The OS/compositor must expose a logical portrait display
(Pi ≈ 600×1024). This module never rotates the UI and never offers a
landscape profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Minimum card width before another browse column is introduced.
# At 800px Mac/dev portrait (minus margins), two retail cards fit.
# At ~600px Pi logical portrait, one column is expected.
BROWSE_MIN_COLUMN_WIDTH = 320
BROWSE_MAX_COLUMNS = 2

# Expected logical geometries (app does not rotate to achieve these).
PI_LOGICAL_WIDTH = 600
PI_LOGICAL_HEIGHT = 1024
DEV_WINDOW_WIDTH = 800
DEV_WINDOW_HEIGHT = 1280


@dataclass(frozen=True)
class LayoutProfile:
    """Portrait-only layout metrics used for windowed defaults and touch floors."""

    window_width: int
    window_height: int
    browse_columns_at_target: int
    button_min_height: int
    card_min_height: int
    page_margin: int
    title_font_px: int
    subtitle_font_px: int
    body_font_px: int
    price_font_px: int

    @property
    def window_size(self) -> tuple[int, int]:
        return (self.window_width, self.window_height)


# Windowed Mac/dev default. On the Pi, fullscreen uses the logical screen
# geometry (≈ 600×1024); components derive from actual width/height.
PORTRAIT = LayoutProfile(
    window_width=DEV_WINDOW_WIDTH,
    window_height=DEV_WINDOW_HEIGHT,
    browse_columns_at_target=2,
    button_min_height=72,
    card_min_height=280,
    page_margin=28,
    title_font_px=40,
    subtitle_font_px=22,
    body_font_px=18,
    price_font_px=26,
)


def current_profile() -> LayoutProfile:
    """Return the portrait layout profile (the only supported profile)."""
    return PORTRAIT


def browse_column_count(viewport_width: int, profile: LayoutProfile | None = None) -> int:
    """
    Derive browse columns from available portrait width.

    Mac/dev 800px → 2 columns. Pi logical ~600px → 1 column.
    Never opens a landscape-style 3-column mode.
    """
    profile = profile or current_profile()
    if viewport_width <= 0:
        return profile.browse_columns_at_target

    usable = max(0, viewport_width - (2 * profile.page_margin))
    cols = max(1, usable // BROWSE_MIN_COLUMN_WIDTH)
    return min(BROWSE_MAX_COLUMNS, cols)


def portrait_geometry_warning(width: int, height: int) -> Optional[str]:
    """
    Return a warning message when geometry is not portrait.

    Does not suggest or apply rotation — OS display provisioning must fix this.
    """
    if width <= 0 or height <= 0:
        return None
    if width > height:
        return (
            f"Display geometry {width}x{height} is landscape (width > height). "
            f"SellMate expects a logical portrait display "
            f"(Pi ≈ {PI_LOGICAL_WIDTH}x{PI_LOGICAL_HEIGHT}; "
            f"Mac/dev windowed {DEV_WINDOW_WIDTH}x{DEV_WINDOW_HEIGHT}). "
            "Configure OS/compositor rotation and touch calibration during "
            "machine provisioning — the application will not rotate the UI."
        )
    return None

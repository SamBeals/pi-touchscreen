"""
Orientation-aware layout metrics for the SellMate touchscreen.

Portrait is the only active profile for the current permanently mounted
hardware revision. Landscape metrics are retained as an unused stub so a
future revision can switch without rewriting screens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Orientation = Literal["portrait", "landscape"]

# Minimum card width before a second browse column is introduced.
# Chosen so target portrait (800px minus margins) stays one column.
BROWSE_MIN_COLUMN_WIDTH = 400


@dataclass(frozen=True)
class LayoutProfile:
    orientation: Orientation
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


PORTRAIT = LayoutProfile(
    orientation="portrait",
    window_width=800,
    window_height=1280,
    browse_columns_at_target=1,
    button_min_height=72,
    card_min_height=200,
    page_margin=24,
    title_font_px=42,
    subtitle_font_px=24,
    body_font_px=20,
    price_font_px=28,
)

# Unused for this hardware revision — kept for future landscape mounts.
LANDSCAPE = LayoutProfile(
    orientation="landscape",
    window_width=1280,
    window_height=800,
    browse_columns_at_target=3,
    button_min_height=56,
    card_min_height=180,
    page_margin=20,
    title_font_px=36,
    subtitle_font_px=22,
    body_font_px=18,
    price_font_px=24,
)


def current_profile() -> LayoutProfile:
    """Return the active layout profile (portrait for current machines)."""
    return PORTRAIT


def browse_column_count(viewport_width: int, profile: LayoutProfile | None = None) -> int:
    """
    Derive browse columns from available width.

    Portrait target (800px) → 1 column. Wider portrait panels may get 2.
    Landscape runtime switching is out of scope; this only scales columns.
    """
    profile = profile or current_profile()
    if viewport_width <= 0:
        return profile.browse_columns_at_target

    usable = max(0, viewport_width - (2 * profile.page_margin))
    cols = max(1, usable // BROWSE_MIN_COLUMN_WIDTH)
    # Cap at 2 for portrait-first kiosks; do not open landscape 3-col mode here.
    if profile.orientation == "portrait":
        return min(2, cols)
    return min(3, cols)

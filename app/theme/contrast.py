"""WCAG contrast helpers for theme color validation."""

from __future__ import annotations

import re

_HEX_RE = re.compile(r"^#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?$")


def parse_hex_color(value: str) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = _HEX_RE.match(value.strip())
    if not match:
        return None
    raw = match.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def is_valid_hex_color(value: str) -> bool:
    return parse_hex_color(value) is not None


def _channel(c: int) -> float:
    s = c / 255.0
    if s <= 0.03928:
        return s / 12.92
    return ((s + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(fg: str, bg: str) -> float | None:
    fg_rgb = parse_hex_color(fg)
    bg_rgb = parse_hex_color(bg)
    if fg_rgb is None or bg_rgb is None:
        return None
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def meets_wcag_aa(fg: str, bg: str, *, large_text: bool = False) -> bool:
    ratio = contrast_ratio(fg, bg)
    if ratio is None:
        return False
    return ratio >= (3.0 if large_text else 4.5)

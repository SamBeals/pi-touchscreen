"""Load, validate, and resolve renter theme packages."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.logging_setup import log_event
from app.theme.contrast import is_valid_hex_color, meets_wcag_aa
from app.theme.schema import (
    ANIMATION_INTENSITIES,
    BACKGROUND_TYPES,
    BUTTON_SHAPES,
    BUTTON_STYLES,
    COLOR_KEYS,
    DEFAULT_THEME_ID,
    MODES,
    PRODUCT_CARD_STYLES,
    PRODUCT_IMAGE_TREATMENTS,
    SCHEMA_VERSION,
    SPACING_DENSITIES,
    TYPE_SCALES,
    BackgroundSpec,
    ResolvedTheme,
    default_theme_dict,
)

logger = logging.getLogger(__name__)

DEFAULT_PACKAGES_DIR = Path("/etc/sellmate/themes")


def bundled_themes_dir() -> Path:
    # app/theme/loader.py -> repo root / themes
    return Path(__file__).resolve().parents[2] / "themes"


@dataclass(frozen=True)
class ThemeLoadResult:
    theme: ResolvedTheme
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _resolve_package_dir(
    theme_id: str,
    packages_dir: Path,
    bundled_dir: Path,
) -> Path | None:
    candidates = [
        packages_dir / theme_id,
        bundled_dir / theme_id,
    ]
    for path in candidates:
        if (path / "theme.json").is_file():
            return path
    return None


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _enum(value: Any, allowed: frozenset[str], default: str, warnings: list[str], field: str) -> str:
    if isinstance(value, str) and value in allowed:
        return value
    if value is not None:
        warnings.append(f"{field}: invalid value {value!r}, using {default!r}")
    return default


def _color(
    value: Any,
    default: str,
    warnings: list[str],
    field: str,
) -> str:
    if isinstance(value, str) and is_valid_hex_color(value):
        return value.strip()
    if value is not None:
        warnings.append(f"{field}: invalid color {value!r}, using default")
    return default


def _asset_rel(
    package_dir: Path,
    relative: Any,
    warnings: list[str],
    field: str,
) -> str:
    if not relative:
        return ""
    if not isinstance(relative, str):
        warnings.append(f"{field}: asset path must be a string")
        return ""
    rel = relative.strip().lstrip("./")
    if not rel or ".." in Path(rel).parts:
        warnings.append(f"{field}: unsafe asset path {relative!r}")
        return ""
    full = package_dir / rel
    if not full.is_file():
        warnings.append(f"{field}: missing asset {rel}")
        return ""
    return rel


def _resolve_from_dict(
    data: dict[str, Any],
    package_dir: Path,
    *,
    used_fallback: bool,
    errors: list[str],
    warnings: list[str],
) -> ResolvedTheme:
    defaults = default_theme_dict()
    merged = _deep_merge(defaults, data)

    version = merged.get("schema_version", SCHEMA_VERSION)
    try:
        version_i = int(version)
    except (TypeError, ValueError):
        errors.append(f"schema_version invalid: {version!r}")
        version_i = SCHEMA_VERSION
    if version_i != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {version_i}")

    brand = merged.get("brand") or {}
    colors_in = merged.get("colors") or {}
    typography = merged.get("typography") or {}
    shape = merged.get("shape") or {}
    layout = merged.get("layout") or {}
    chrome = merged.get("chrome") or {}
    bg_in = chrome.get("background") or {}

    colors: dict[str, str] = {}
    for key in COLOR_KEYS:
        colors[key] = _color(
            colors_in.get(key),
            defaults["colors"][key],
            warnings,
            f"colors.{key}",
        )

    # Contrast guardrails: text and price against background/surface.
    if not meets_wcag_aa(colors["text"], colors["background"]):
        warnings.append("colors.text fails WCAG AA on background; restoring default text")
        colors["text"] = defaults["colors"]["text"]
    if not meets_wcag_aa(colors["price"], colors["background"], large_text=True):
        warnings.append("colors.price fails contrast; restoring default price color")
        colors["price"] = defaults["colors"]["price"]
    if not meets_wcag_aa(colors["text"], colors["surface"]):
        warnings.append("colors.text fails WCAG AA on surface; adjusting surface to default")
        colors["surface"] = defaults["colors"]["surface"]

    mode = _enum(merged.get("mode"), MODES, "dark", warnings, "mode")
    type_scale = _enum(
        typography.get("scale"), TYPE_SCALES, "comfortable", warnings, "typography.scale"
    )
    spacing = _enum(
        layout.get("spacing_density"),
        SPACING_DENSITIES,
        "comfortable",
        warnings,
        "layout.spacing_density",
    )
    animation = _enum(
        layout.get("animation_intensity"),
        ANIMATION_INTENSITIES,
        "moderate",
        warnings,
        "layout.animation_intensity",
    )
    button_style = _enum(
        shape.get("button_style"), BUTTON_STYLES, "filled", warnings, "shape.button_style"
    )
    button_shape = _enum(
        shape.get("button_shape"), BUTTON_SHAPES, "rounded", warnings, "shape.button_shape"
    )
    card_style = _enum(
        shape.get("product_card_style"),
        PRODUCT_CARD_STYLES,
        "elevated",
        warnings,
        "shape.product_card_style",
    )
    image_treatment = _enum(
        chrome.get("product_image_treatment"),
        PRODUCT_IMAGE_TREATMENTS,
        "cover_rounded",
        warnings,
        "chrome.product_image_treatment",
    )

    radius_raw = shape.get("corner_radius", 16)
    try:
        corner_radius = max(0, min(32, int(radius_raw)))
    except (TypeError, ValueError):
        warnings.append(f"shape.corner_radius invalid: {radius_raw!r}")
        corner_radius = 16

    bg_type = _enum(
        bg_in.get("type"), BACKGROUND_TYPES, "gradient", warnings, "chrome.background.type"
    )
    stops_raw = bg_in.get("stops") or defaults["chrome"]["background"]["stops"]
    stops: list[str] = []
    if isinstance(stops_raw, list):
        for i, stop in enumerate(stops_raw):
            stops.append(
                _color(stop, defaults["colors"]["background"], warnings, f"chrome.background.stops[{i}]")
            )
    if len(stops) < 2:
        stops = list(defaults["chrome"]["background"]["stops"])

    bg_color = _color(
        bg_in.get("color"),
        colors["background"],
        warnings,
        "chrome.background.color",
    )
    bg_image = ""
    if bg_type == "image":
        bg_image = _asset_rel(
            package_dir, bg_in.get("image") or bg_in.get("path"), warnings, "chrome.background.image"
        )
        if not bg_image:
            warnings.append("chrome.background.image missing; falling back to gradient")
            bg_type = "gradient"

    logo = _asset_rel(package_dir, brand.get("logo"), warnings, "brand.logo")
    banner = _asset_rel(package_dir, chrome.get("banner"), warnings, "chrome.banner")

    font_family = typography.get("family") or defaults["typography"]["family"]
    if not isinstance(font_family, str) or not font_family.strip():
        font_family = defaults["typography"]["family"]
        warnings.append("typography.family invalid; using default")

    business_name = brand.get("business_name") or merged.get("display_name") or "SellMate"
    if not isinstance(business_name, str) or not business_name.strip():
        business_name = "SellMate"

    headline = chrome.get("attract_headline")
    if not isinstance(headline, str) or not headline.strip():
        headline = defaults["chrome"]["attract_headline"]
    promo = chrome.get("attract_promo")
    if not isinstance(promo, str):
        promo = ""

    theme_id = merged.get("id") or package_dir.name
    if not isinstance(theme_id, str) or not theme_id.strip():
        theme_id = DEFAULT_THEME_ID

    display_name = merged.get("display_name") or business_name
    if not isinstance(display_name, str) or not display_name.strip():
        display_name = business_name

    return ResolvedTheme(
        schema_version=SCHEMA_VERSION,
        id=str(theme_id).strip(),
        display_name=str(display_name).strip(),
        mode=mode,  # type: ignore[arg-type]
        business_name=str(business_name).strip(),
        logo_path=logo,
        colors=colors,
        font_family=font_family.strip(),
        type_scale=type_scale,  # type: ignore[arg-type]
        corner_radius=corner_radius,
        button_style=button_style,  # type: ignore[arg-type]
        button_shape=button_shape,  # type: ignore[arg-type]
        product_card_style=card_style,  # type: ignore[arg-type]
        spacing_density=spacing,  # type: ignore[arg-type]
        animation_intensity=animation,  # type: ignore[arg-type]
        background=BackgroundSpec(
            type=bg_type,  # type: ignore[arg-type]
            color=bg_color,
            stops=tuple(stops),
            image=bg_image,
        ),
        attract_headline=headline.strip(),
        attract_promo=promo.strip(),
        banner_path=banner,
        product_image_treatment=image_treatment,  # type: ignore[arg-type]
        package_dir=str(package_dir.resolve()),
        used_fallback=used_fallback,
        warnings=tuple(warnings),
    )


def load_theme(
    theme_id: Optional[str] = None,
    *,
    packages_dir: Optional[str | Path] = None,
    bundled_dir: Optional[str | Path] = None,
) -> ThemeLoadResult:
    """
    Load a theme package by id.

    On hard failure (missing package, bad JSON, unsupported schema), returns
    the bundled SellMate default theme with used_fallback=True.
    Soft issues (bad colors/assets) become warnings and field-level defaults.
    """
    tid = (theme_id or DEFAULT_THEME_ID).strip() or DEFAULT_THEME_ID
    pkg_root = Path(packages_dir) if packages_dir else DEFAULT_PACKAGES_DIR
    bundled = Path(bundled_dir) if bundled_dir else bundled_themes_dir()
    errors: list[str] = []
    warnings: list[str] = []

    package_dir = _resolve_package_dir(tid, pkg_root, bundled)
    if package_dir is None:
        errors.append(f"theme package not found: {tid}")
        package_dir = _resolve_package_dir(DEFAULT_THEME_ID, pkg_root, bundled)
        if package_dir is None:
            # Synthesize from in-code defaults if even bundled files are missing.
            theme = _resolve_from_dict(
                default_theme_dict(),
                bundled / DEFAULT_THEME_ID,
                used_fallback=True,
                errors=errors,
                warnings=warnings,
            )
            log_event(
                logger,
                "theme.load_failed",
                theme_id=tid,
                errors=errors,
                warnings=list(warnings),
            )
            return ThemeLoadResult(theme=theme, errors=tuple(errors), warnings=tuple(warnings))
        tid = DEFAULT_THEME_ID

    raw = _load_json(package_dir / "theme.json")
    if raw is None:
        errors.append(f"invalid theme.json in {package_dir}")
        raw = default_theme_dict()
        used_fallback = True
        package_dir = bundled / DEFAULT_THEME_ID
        if not (package_dir / "theme.json").is_file():
            package_dir = bundled / DEFAULT_THEME_ID
    else:
        used_fallback = tid == DEFAULT_THEME_ID and bool(errors)

    # Unsupported schema → full fallback to default package.
    version = raw.get("schema_version", SCHEMA_VERSION)
    try:
        version_i = int(version)
    except (TypeError, ValueError):
        version_i = -1
    if version_i != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version {version!r}")
        default_pkg = _resolve_package_dir(DEFAULT_THEME_ID, pkg_root, bundled)
        if default_pkg is not None:
            package_dir = default_pkg
            raw = _load_json(package_dir / "theme.json") or default_theme_dict()
        else:
            raw = default_theme_dict()
        used_fallback = True

    theme = _resolve_from_dict(
        raw,
        package_dir,
        used_fallback=used_fallback or bool(errors),
        errors=errors,
        warnings=warnings,
    )

    if errors or warnings:
        log_event(
            logger,
            "theme.loaded",
            theme_id=theme.id,
            used_fallback=theme.used_fallback,
            errors=errors,
            warnings=warnings,
        )
    else:
        log_event(logger, "theme.loaded", theme_id=theme.id, used_fallback=False)

    return ThemeLoadResult(
        theme=theme,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )

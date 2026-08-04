"""Theme schema enums, defaults, and resolved theme model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = 1
DEFAULT_THEME_ID = "sellmate-default"

Mode = Literal["light", "dark"]
TypeScale = Literal["compact", "comfortable", "large"]
SpacingDensity = Literal["compact", "comfortable", "spacious"]
AnimationIntensity = Literal["none", "subtle", "moderate"]
ButtonStyle = Literal["filled", "outline", "soft"]
ButtonShape = Literal["rounded", "pill", "square"]
ProductCardStyle = Literal["flat", "elevated", "outlined"]
ProductImageTreatment = Literal["cover_rounded", "contain", "circle", "none"]
BackgroundType = Literal["solid", "gradient", "image"]

MODES = frozenset({"light", "dark"})
TYPE_SCALES = frozenset({"compact", "comfortable", "large"})
SPACING_DENSITIES = frozenset({"compact", "comfortable", "spacious"})
ANIMATION_INTENSITIES = frozenset({"none", "subtle", "moderate"})
BUTTON_STYLES = frozenset({"filled", "outline", "soft"})
BUTTON_SHAPES = frozenset({"rounded", "pill", "square"})
PRODUCT_CARD_STYLES = frozenset({"flat", "elevated", "outlined"})
PRODUCT_IMAGE_TREATMENTS = frozenset(
    {"cover_rounded", "contain", "circle", "none"}
)
BACKGROUND_TYPES = frozenset({"solid", "gradient", "image"})

COLOR_KEYS = (
    "primary",
    "secondary",
    "accent",
    "background",
    "surface",
    "text",
    "text_muted",
    "success",
    "warning",
    "error",
    "price",
)

# Usability floors — themes cannot lower these.
PRIMARY_BUTTON_MIN_HEIGHT = 72
SECONDARY_BUTTON_MIN_HEIGHT = 56
CARD_MIN_HEIGHT = 200

SPACING_TABLE = {
    "compact": {"page_margin": 16, "gap": 8, "section_gap": 16},
    "comfortable": {"page_margin": 24, "gap": 12, "section_gap": 24},
    "spacious": {"page_margin": 32, "gap": 16, "section_gap": 32},
}

TYPE_SCALE_TABLE = {
    "compact": {"title": 36, "subtitle": 20, "body": 18, "price": 24},
    "comfortable": {"title": 42, "subtitle": 24, "body": 20, "price": 28},
    "large": {"title": 48, "subtitle": 28, "body": 22, "price": 32},
}

ANIMATION_MS = {
    "none": 0,
    "subtle": 150,
    "moderate": 280,
}


@dataclass(frozen=True)
class BackgroundSpec:
    type: BackgroundType = "gradient"
    color: str = "#111827"
    stops: tuple[str, ...] = ("#111827", "#0F172A")
    image: str = ""


@dataclass(frozen=True)
class ResolvedTheme:
    schema_version: int
    id: str
    display_name: str
    mode: Mode
    business_name: str
    logo_path: str
    colors: dict[str, str]
    font_family: str
    type_scale: TypeScale
    corner_radius: int
    button_style: ButtonStyle
    button_shape: ButtonShape
    product_card_style: ProductCardStyle
    spacing_density: SpacingDensity
    animation_intensity: AnimationIntensity
    background: BackgroundSpec
    attract_headline: str
    attract_promo: str
    banner_path: str
    product_image_treatment: ProductImageTreatment
    package_dir: str
    used_fallback: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def page_margin(self) -> int:
        return SPACING_TABLE[self.spacing_density]["page_margin"]

    @property
    def gap(self) -> int:
        return SPACING_TABLE[self.spacing_density]["gap"]

    @property
    def section_gap(self) -> int:
        return SPACING_TABLE[self.spacing_density]["section_gap"]

    @property
    def title_font_px(self) -> int:
        return TYPE_SCALE_TABLE[self.type_scale]["title"]

    @property
    def subtitle_font_px(self) -> int:
        return TYPE_SCALE_TABLE[self.type_scale]["subtitle"]

    @property
    def body_font_px(self) -> int:
        return TYPE_SCALE_TABLE[self.type_scale]["body"]

    @property
    def price_font_px(self) -> int:
        return TYPE_SCALE_TABLE[self.type_scale]["price"]

    @property
    def animation_ms(self) -> int:
        return ANIMATION_MS[self.animation_intensity]

    @property
    def primary_button_min_height(self) -> int:
        return PRIMARY_BUTTON_MIN_HEIGHT

    @property
    def secondary_button_min_height(self) -> int:
        return SECONDARY_BUTTON_MIN_HEIGHT

    @property
    def card_min_height(self) -> int:
        return CARD_MIN_HEIGHT

    def color(self, key: str) -> str:
        return self.colors[key]

    def asset_url(self, relative: str) -> str:
        if not relative:
            return ""
        path = Path(relative)
        if path.is_absolute():
            return path.as_uri() if path.is_file() else ""
        full = Path(self.package_dir) / relative
        return full.as_uri() if full.is_file() else ""

    def to_qml_dict(self) -> dict[str, Any]:
        bg = asdict(self.background)
        return {
            "id": self.id,
            "displayName": self.display_name,
            "mode": self.mode,
            "businessName": self.business_name,
            "logoUrl": self.asset_url(self.logo_path) if self.logo_path else "",
            "bannerUrl": self.asset_url(self.banner_path) if self.banner_path else "",
            "colors": dict(self.colors),
            "fontFamily": self.font_family,
            "typeScale": self.type_scale,
            "cornerRadius": self.corner_radius,
            "buttonStyle": self.button_style,
            "buttonShape": self.button_shape,
            "productCardStyle": self.product_card_style,
            "spacingDensity": self.spacing_density,
            "animationIntensity": self.animation_intensity,
            "animationMs": self.animation_ms,
            "pageMargin": self.page_margin,
            "gap": self.gap,
            "sectionGap": self.section_gap,
            "titleFontPx": self.title_font_px,
            "subtitleFontPx": self.subtitle_font_px,
            "bodyFontPx": self.body_font_px,
            "priceFontPx": self.price_font_px,
            "primaryButtonMinHeight": self.primary_button_min_height,
            "secondaryButtonMinHeight": self.secondary_button_min_height,
            "cardMinHeight": self.card_min_height,
            "attractHeadline": self.attract_headline,
            "attractPromo": self.attract_promo,
            "productImageTreatment": self.product_image_treatment,
            "backgroundType": bg["type"],
            "backgroundColor": bg["color"],
            "backgroundStops": list(bg["stops"]),
            "backgroundImageUrl": self.asset_url(bg["image"]) if bg["image"] else "",
            "usedFallback": self.used_fallback,
        }


def default_theme_dict() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": DEFAULT_THEME_ID,
        "display_name": "SellMate",
        "mode": "light",
        "brand": {"business_name": "SellMate", "logo": ""},
        "colors": {
            "primary": "#A3E635",
            "secondary": "#F3F4F6",
            "accent": "#84CC16",
            "background": "#FFFFFF",
            "surface": "#FFFFFF",
            "text": "#1F2937",
            "text_muted": "#6B7280",
            "success": "#16A34A",
            "warning": "#D97706",
            "error": "#DC2626",
            "price": "#1F2937",
        },
        "typography": {"family": "DejaVu Sans", "scale": "comfortable"},
        "shape": {
            "corner_radius": 20,
            "button_style": "filled",
            "button_shape": "pill",
            "product_card_style": "elevated",
        },
        "layout": {
            "spacing_density": "comfortable",
            "animation_intensity": "subtle",
        },
        "chrome": {
            "background": {
                "type": "solid",
                "color": "#FFFFFF",
                "stops": ["#FFFFFF", "#F9FAFB"],
            },
            "attract_headline": "Tap to start shopping",
            "attract_promo": "",
            "banner": "",
            "product_image_treatment": "contain",
        },
    }

"""Expose ResolvedTheme to QML as a reactive object.

Always holds a complete theme. Chrome/UI tokens come from theme.json
``chrome.ui`` (merged over defaults) so components stay consistent without
per-component hardcoded palettes.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QObject, Signal

from app.theme.loader import default_resolved_theme
from app.theme.schema import ChromeUi, ResolvedTheme


class ThemeBridge(QObject):
    changed = Signal()

    def __init__(self, theme: Optional[ResolvedTheme] = None, parent=None):
        super().__init__(parent)
        self._theme = theme if theme is not None else default_resolved_theme()

    def apply(self, theme: ResolvedTheme) -> None:
        self._theme = theme if theme is not None else default_resolved_theme()
        self.changed.emit()

    def packageDir(self) -> str:  # noqa: N802
        return self._t().package_dir

    def _t(self) -> ResolvedTheme:
        if self._theme is None:
            self._theme = default_resolved_theme()
        return self._theme

    def _ui(self) -> ChromeUi:
        return self._t().chrome_ui

    @Property(str, notify=changed)
    def id(self) -> str:
        return self._t().id

    @Property(str, notify=changed)
    def businessName(self) -> str:  # noqa: N802
        return self._t().business_name

    @Property(str, notify=changed)
    def displayName(self) -> str:  # noqa: N802
        return self._t().display_name

    @Property(str, notify=changed)
    def mode(self) -> str:
        return self._t().mode

    @Property(str, notify=changed)
    def logoUrl(self) -> str:  # noqa: N802
        return self._t().asset_url(self._t().logo_path) if self._t().logo_path else ""

    @Property(str, notify=changed)
    def bannerUrl(self) -> str:  # noqa: N802
        return self._t().asset_url(self._t().banner_path) if self._t().banner_path else ""

    @Property(str, notify=changed)
    def fontFamily(self) -> str:  # noqa: N802
        return self._t().font_family

    @Property(str, notify=changed)
    def primary(self) -> str:
        return self._t().color("primary")

    @Property(str, notify=changed)
    def secondary(self) -> str:
        return self._t().color("secondary")

    @Property(str, notify=changed)
    def accent(self) -> str:
        return self._t().color("accent")

    @Property(str, notify=changed)
    def background(self) -> str:
        return self._t().color("background")

    @Property(str, notify=changed)
    def surface(self) -> str:
        return self._t().color("surface")

    @Property(str, notify=changed)
    def text(self) -> str:
        return self._t().color("text")

    @Property(str, notify=changed)
    def textMuted(self) -> str:  # noqa: N802
        return self._t().color("text_muted")

    @Property(str, notify=changed)
    def success(self) -> str:
        return self._t().color("success")

    @Property(str, notify=changed)
    def warning(self) -> str:
        return self._t().color("warning")

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._t().color("error")

    @Property(str, notify=changed)
    def price(self) -> str:
        return self._t().color("price")

    # --- Shared chrome / component tokens ---

    @Property(str, notify=changed)
    def border(self) -> str:
        return self._ui().border

    @Property(str, notify=changed)
    def imageWell(self) -> str:  # noqa: N802
        return self._ui().image_well

    @Property(str, notify=changed)
    def warningSurface(self) -> str:  # noqa: N802
        return self._ui().warning_surface

    @Property(str, notify=changed)
    def warningBorder(self) -> str:  # noqa: N802
        return self._ui().warning_border

    @Property(str, notify=changed)
    def errorSurface(self) -> str:  # noqa: N802
        return self._ui().error_surface

    @Property(str, notify=changed)
    def onContrast(self) -> str:  # noqa: N802
        return self._ui().on_contrast

    @Property(str, notify=changed)
    def shadowSoft(self) -> str:  # noqa: N802
        return self._ui().shadow_soft

    @Property(str, notify=changed)
    def shadowSofter(self) -> str:  # noqa: N802
        return self._ui().shadow_softer

    @Property(str, notify=changed)
    def shadowLift(self) -> str:  # noqa: N802
        return self._ui().shadow_lift

    @Property(str, notify=changed)
    def scrim(self) -> str:
        if self._t().mode == "light":
            return self._ui().scrim_light
        return self._ui().scrim_dark

    @Property(int, notify=changed)
    def squareRadius(self) -> int:  # noqa: N802
        return int(self._ui().square_radius)

    @Property(int, notify=changed)
    def statusBadgeSize(self) -> int:  # noqa: N802
        return int(self._ui().status_badge_size)

    @Property(int, notify=changed)
    def cornerRadius(self) -> int:  # noqa: N802
        return self._t().corner_radius

    @Property(str, notify=changed)
    def buttonStyle(self) -> str:  # noqa: N802
        return self._t().button_style

    @Property(str, notify=changed)
    def buttonShape(self) -> str:  # noqa: N802
        return self._t().button_shape

    @Property(str, notify=changed)
    def productCardStyle(self) -> str:  # noqa: N802
        return self._t().product_card_style

    @Property(str, notify=changed)
    def productImageTreatment(self) -> str:  # noqa: N802
        return self._t().product_image_treatment

    @Property(str, notify=changed)
    def logoPlacement(self) -> str:  # noqa: N802
        return self._t().logo_placement

    @Property(int, notify=changed)
    def pageMargin(self) -> int:  # noqa: N802
        return self._t().page_margin

    @Property(int, notify=changed)
    def gap(self) -> int:
        return self._t().gap

    @Property(int, notify=changed)
    def sectionGap(self) -> int:  # noqa: N802
        return self._t().section_gap

    @Property(int, notify=changed)
    def titleFontPx(self) -> int:  # noqa: N802
        return self._t().title_font_px

    @Property(int, notify=changed)
    def subtitleFontPx(self) -> int:  # noqa: N802
        return self._t().subtitle_font_px

    @Property(int, notify=changed)
    def bodyFontPx(self) -> int:  # noqa: N802
        return self._t().body_font_px

    @Property(int, notify=changed)
    def priceFontPx(self) -> int:  # noqa: N802
        return self._t().price_font_px

    @Property(int, notify=changed)
    def primaryButtonMinHeight(self) -> int:  # noqa: N802
        return self._t().primary_button_min_height

    @Property(int, notify=changed)
    def secondaryButtonMinHeight(self) -> int:  # noqa: N802
        return self._t().secondary_button_min_height

    @Property(int, notify=changed)
    def cardMinHeight(self) -> int:  # noqa: N802
        return self._t().card_min_height

    @Property(int, notify=changed)
    def animationMs(self) -> int:  # noqa: N802
        return self._t().animation_ms

    @Property(str, notify=changed)
    def attractHeadline(self) -> str:  # noqa: N802
        return self._t().attract_headline

    @Property(str, notify=changed)
    def attractPromo(self) -> str:  # noqa: N802
        return self._t().attract_promo

    @Property(list, notify=changed)
    def attractGifUrls(self):  # noqa: N802
        urls = []
        for rel in self._t().attract_gif_paths:
            url = self._t().asset_url(rel)
            if url:
                urls.append(url)
        return urls

    @Property(int, notify=changed)
    def attractGifIntervalMs(self) -> int:  # noqa: N802
        return int(self._t().attract_gif_interval_ms)

    @Property(str, notify=changed)
    def attractCta(self) -> str:  # noqa: N802
        return self._ui().attract_cta

    @Property(str, notify=changed)
    def attractBed(self) -> str:  # noqa: N802
        return self._ui().attract_bed

    @Property(str, notify=changed)
    def attractScrimTop(self) -> str:  # noqa: N802
        return self._ui().attract_scrim_top

    @Property(str, notify=changed)
    def attractScrimMid(self) -> str:  # noqa: N802
        return self._ui().attract_scrim_mid

    @Property(str, notify=changed)
    def attractScrimBottom(self) -> str:  # noqa: N802
        return self._ui().attract_scrim_bottom

    @Property(str, notify=changed)
    def backgroundType(self) -> str:  # noqa: N802
        return self._t().background.type

    @Property(str, notify=changed)
    def backgroundColor(self) -> str:  # noqa: N802
        return self._t().background.color

    @Property(list, notify=changed)
    def backgroundStops(self):  # noqa: N802
        return list(self._t().background.stops)

    @Property(str, notify=changed)
    def backgroundImageUrl(self) -> str:  # noqa: N802
        img = self._t().background.image
        return self._t().asset_url(img) if img else ""

    @Property(bool, notify=changed)
    def usedFallback(self) -> bool:  # noqa: N802
        return self._t().used_fallback

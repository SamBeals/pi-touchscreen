# Figma design loop (pi-touchscreen)

Visual source of truth for the SellMate portrait kiosk. Implement look-and-feel
in QML under `app/ui/qml/`; treat Figma exports as reference, not a wholesale
app replace (runtime stays PySide6 / existing Theme singleton).

## Install (once)

1. Open [Figma](https://www.figma.com) (desktop preferred).
2. Install **[Figma to Qt](https://www.figma.com/community/plugin/1428838670955327829/figma-to-qt)**
   from the Community (Qt’s official plugin — not generic React exporters).
3. Create a design file named **SellMate Pi Touchscreen UI** (or reuse one).
4. Optional: use Figma to Qt **Live Preview** to sanity-check Qt mapping before
   hand-porting into this repo.

Do **not** replace `app/ui/qml/` with a generated project. Merge visual decisions
into existing components and `themes/*/theme.json`.

## Portrait frames

Create frames at both sizes used in production / Mac preview:

| Frame name | Size | Role |
|---|---|---|
| Attract · Pi | 600×1024 | Full-bleed media + pink CTA |
| Browse · Pi | 600×1024 | Header, promo, product grid |
| Detail · Pi | 600×1024 | Image, price, qty, actions |
| Cart · Pi | 600×1024 | Lines, total, checkout |
| Attract · Mac | 800×1280 | Dev windowed |
| Browse · Mac | 800×1280 | Dev windowed |
| Detail · Mac | 800×1280 | Dev windowed |
| Cart · Mac | 800×1280 | Dev windowed |

Payment / Success / Failure can follow after the four primary frames land.

## Token map (Figma ↔ theme.json)

| Visual | Theme token |
|---|---|
| Brand lime | `colors.primary` `#A3E635` |
| Soft gray chip | `colors.secondary` `#F3F4F6` |
| Page bg | `colors.background` |
| Card surface | `colors.surface` |
| Body text | `colors.text` `#1F2937` |
| Muted | `colors.text_muted` |
| Attract CTA | `chrome.ui.attract_cta` `#EC4899` |
| Attract bed | `chrome.ui.attract_bed` `#111111` |
| Borders | `chrome.ui.border` `#E5E7EB` |
| Type family | `typography.family` → Source Sans 3 |
| Corner radius | `shape.corner_radius` (20) |
| Primary hit target | ≥ 72px height |
| Secondary hit target | ≥ 56px height |

## Workflow

```text
Figma frames (+ Figma to Qt preview)
        ↓
theme.json + assets/fonts + QML components
        ↓
Mac windowed (FULLSCREEN=false, QML_HOT_RELOAD=1)
        ↓
Pi smoke (animation_intensity: subtle)
```

See [THEMES.md](./THEMES.md) for package layout and [README.md](../README.md)
for the Mac reload loop.

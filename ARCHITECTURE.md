# SellMate Pi Touchscreen — Architecture

## Role

Customer-facing fullscreen kiosk on a Raspberry Pi 10.1" touchscreen,
**permanently mounted in portrait**. Logical Pi geometry is **≈ 600×1024**;
Mac/dev windowed default is **800×1280**. The OS/compositor must expose that
portrait desktop (and calibrated touch); the app never rotates the screen and
has no landscape profile.

- Talks to **SellMateCloud** for orders/payment status.
- Reads **Firestore** inventory/planogram for product display.
- **Never** calls local vend-api, motors, ToF, claim, or complete.

Physical vend remains: Cloud → `sellmate-poller` → `vend-api`.

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| Presentation | `app/ui/qml/` | Qt Quick / QML screens + design-system components |
| Bridge | `app/ui/app_controller.py`, `list_models.py`, `theme_bridge.py` | QObject API for QML; no business rules in QML |
| Theme | `app/theme/` | Package load, schema validation, contrast guardrails |
| Workers | `app/ui/workers.py` | QThreads for Cloud/Firestore |
| State | `app/state` | Screen FSM, checkout orchestration, active-order persistence |
| API | `app/api` | Cloud HTTP client, Firestore inventory client |
| Models | `app/models` | Product, cart, order status mapping |
| Config | `app/config.py` | Env + `/etc/sellmate/machine.env` + touchscreen.env |
| Layout | `app/ui/layout.py` | Portrait-only metrics / browse columns |
| Platform | `app/ui/platform.py` | Qt Wayland preference on Linux; Cocoa on macOS |
| Logging | `app/logging_setup.py` | Structured JSON; no secrets |

Branding is presentation-only. Checkout gates, order polling, cancel rules,
inventory freshness, active-order recovery, and payment/error **copy** remain
Python-owned.

## Screen / state flow

```text
Boot → Attract → Browse ⇄ ProductDetail → Cart → Payment → Success/Failure → Attract
                     ↑ idle 90s clears cart ─────────────────────────────────────┘
```

On boot, if `active_order.json` references a non-terminal order, resume **Payment** polling before allowing a new checkout.

## Themes

Configuration-driven packages (`theme.json` + assets). See [docs/THEMES.md](./docs/THEMES.md).

- Install path: `/etc/sellmate/themes/<theme_id>/`
- Selection: `THEME_ID` (default `sellmate-default`)
- Bundled: `themes/sellmate-default`, `themes/sellmate-light`
- Invalid packages fall back to SellMate default without bricking the kiosk
- QML access: `import SellMate 1.0` → singleton `Theme` (registered before engine
  create via `app/ui/theme_provider.py`); never a nullable context property

### `theme.json` (schema_version 1)

Customizable: business name, logo, colors (primary/secondary/accent/background/surface/text/text_muted/success/warning/error/price), typography family + scale, product-card style, button shape/style, background solid|gradient|image, attract headline/promo, banner, product image treatment, corner radius, spacing density, animation intensity, light|dark mode.

## Order statuses (primary)

`CREATED` → `AUTHORIZING` → `AUTHORIZED` → `VENDING` → `COMPLETED`  
Failures: `PAYMENT_FAILED`, `FAILED`, `CANCELLED`

Legacy Android aliases (`PAID`, `PAYMENT_STARTED`, …) map into the primary model.

**Cancel** allowed only for `CREATED` / `AUTHORIZING`.  
`AUTHORIZED` is **not** cancellable in the UI: Cloud has already created a `PENDING` vend_job, and cancel races with Pi claim (Cloud does not transactionally block claim).

## Checkout gate

Checkout requires:

1. Cloud `GET /health` reachable  
2. Inventory snapshot age ≤ `INVENTORY_MAX_AGE_SECONDS`

Cached inventory may display products; stale cache blocks checkout.

## Identity

Reuse `/etc/sellmate/machine.env` (`MACHINE_ID`, `CLOUD_BASE`) — same file as Pi poller/health.

## Display / layout

- Portrait-only via `app/ui/layout.py` — no landscape profile or orientation switch.
- Browse columns derive from **actual** viewport width (≈1 column at Pi 600px; 2 at Mac 800px).
- Startup warns (`display.portrait_misconfigured`) if width > height; UI is not rearranged.
- **Machine provisioning** (labwc): `provisioning/display/install-portrait-display.sh`
  writes `~/.config/labwc/autostart` + `rc.xml` and `/etc/sellmate/display.env` so boot
  yields `Transform: 90|270` with matched touch — see [docs/DISPLAY.md](./docs/DISPLAY.md).
- Pi launch prefers Qt Wayland (`wayland;xcb`) so Quick is not forced through Xwayland.

## Pi performance notes

- Single process: Python + Qt Quick (no Chromium)
- Prefer `animation_intensity: subtle` or `none` on Pi 4
- Keep background/banner assets modest (edge ≤ ~1920px; JPEG/WebP)
- Product grids use QML `GridView` recycling

## Out of scope

- Hardware control, health reporting, kiosk auth, multi-language
- OS display rotation / touch calibration (provisioning only — see DISPLAY.md)
- Runtime landscape UI, orientation switching, UI rotation transforms
- Cloud theme marketplace / dashboard theme editor

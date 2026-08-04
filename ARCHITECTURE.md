# SellMate Pi Touchscreen — Architecture

## Role

Customer-facing fullscreen kiosk on a Raspberry Pi 10.1" touchscreen,
**permanently mounted in portrait** (dev window **800×1280**). The OS
framebuffer and touch input are assumed already rotated; the app renders
portrait-first layout only (no runtime landscape mode).

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
| Layout | `app/ui/layout.py` | Portrait metrics / browse columns |
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

- Active profile: portrait via `app/ui/layout.py` (`current_profile()`).
- Browse columns derive from viewport width (1 column at 800px; up to 2 on wider portrait panels).
- Landscape layout constants exist as unused stubs only.

## Pi performance notes

- Single process: Python + Qt Quick (no Chromium)
- Prefer `animation_intensity: subtle` or `none` on Pi 4
- Keep background/banner assets modest (edge ≤ ~1920px; JPEG/WebP)
- Product grids use QML `GridView` recycling

## Out of scope

- Hardware control, health reporting, kiosk auth, multi-language
- OS display rotation configuration; runtime landscape UI
- Cloud theme marketplace / dashboard theme editor

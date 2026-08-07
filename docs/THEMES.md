# SellMate touchscreen themes

Renter branding is configuration-driven. Install a theme package and set
`THEME_ID` — no application code changes.

## Package layout

```text
/etc/sellmate/themes/<theme_id>/
  theme.json
  assets/
    logo.png
    background.jpg
    banner-attract.png
    product-placeholder.png
    fonts/
      BrandSans-Regular.ttf   # or .otf — registered on load
```

Bundled themes ship in the repo under `themes/`:

| ID | Purpose |
|---|---|
| `sellmate-default` | Premium white / lime retail brand (default) |
| `sellmate-light` | Alternate light theme (spacious density) |

Fonts under `assets/fonts/*.{ttf,otf,ttc}` are registered via Qt’s font
database when the theme loads (`app/theme/fonts.py`). Set
`typography.family` to the PostScript/family name (bundled default:
**Source Sans 3**).

Shared chrome (borders, shadows, attract CTA/scrim) lives in
`chrome.ui` inside `theme.json` — see bundled packages for the full key set.

## Selection

In `/etc/sellmate/touchscreen.env`:

```bash
THEME_ID=acme-cafe
# THEME_PACKAGES_DIR=/etc/sellmate/themes
```

Restart the service after changing themes:

```bash
sudo systemctl restart sellmate-touchscreen
```

### Cloud apply (MVP)

Theme Studio can **Publish & apply** a zip to a specific `machine_id`. Cloud
stores an immutable package and sets `machines/{id}.desired_theme`. While the
kiosk is on **Attract**, touchscreen polls Cloud (`THEME_SYNC_ENABLED`, default
on), downloads the zip with `X-Machine-Token`, installs under:

```text
$TOUCHSCREEN_DATA_DIR/themes/<theme_id>/
$TOUCHSCREEN_DATA_DIR/active_theme.json
```

Then acks and exits non-zero so systemd `Restart=on-failure` reloads the UI.
Boot prefers `active_theme.json` when that package exists on disk; otherwise
falls back to `THEME_ID` / `THEME_PACKAGES_DIR`.

Requires `MACHINE_SHARED_TOKEN` in `/etc/sellmate/machine.env` (same as health).

On Mac/dev (`FULLSCREEN=false`), QML/theme file changes hot-reload by default
(`QML_HOT_RELOAD=1`). Set `QML_HOT_RELOAD=0` to disable.

## Validation and fallback

On boot, the theme provider (`app/ui/theme_provider.py`):

1. Loads via `load_theme` — resolves `/etc/sellmate/themes/<THEME_ID>/` then
   bundled `themes/<THEME_ID>/`
2. Validates `schema_version` (currently `1`)
3. Merges over SellMate defaults
4. Enforces contrast (text/price), hex colors, safe asset paths, enum fields
5. On hard failure (missing package, bad JSON, unsupported schema) → loads
   `sellmate-default` and logs `theme.load_failed` / `theme.loaded` with
   `used_fallback=true`
6. Registers `Theme` as a **QML singleton** (`import SellMate 1.0`) *before*
   the QML engine is created, so every screen/component receives a complete,
   non-null theme object

Soft failures (bad color, missing banner) strip that field and keep the rest.

Components use `Theme.*` tokens for colors, type, spacing, radii, shadows, and
chrome — not hardcoded palette values.

## Usability floors (not overridable)

- Primary button min height ≥ 72px
- Secondary / qty targets ≥ 56px
- Card min height ≥ 200px
- Payment, cancel, checkout, and error **copy** come from the app — themes
  style only
- Prices always visible with contrast-checked color

## Authoring checklist

1. Copy `themes/sellmate-default` as a starting point
2. Edit `theme.json` (`business_name`, colors, chrome, shape, layout)
3. Add licensed assets under `assets/`
4. Install to `/etc/sellmate/themes/<id>/`
5. Set `THEME_ID=<id>` and restart
6. Confirm Attract shows the business name and checkout still gates correctly

See `theme.json` schema fields in [ARCHITECTURE.md](../ARCHITECTURE.md).

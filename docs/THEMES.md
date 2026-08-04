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
      BrandSans-Regular.ttf
```

Bundled themes ship in the repo under `themes/`:

| ID | Purpose |
|---|---|
| `sellmate-default` | Dark SellMate brand (default) |
| `sellmate-light` | Light-mode reference theme |

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

## Validation and fallback

On boot, `ThemeLoader`:

1. Resolves `/etc/sellmate/themes/<THEME_ID>/` then bundled `themes/<THEME_ID>/`
2. Validates `schema_version` (currently `1`)
3. Merges over SellMate defaults
4. Enforces contrast (text/price), hex colors, safe asset paths, enum fields
5. On hard failure (missing package, bad JSON, unsupported schema) → loads
   `sellmate-default` and logs `theme.load_failed` / `theme.loaded` with
   `used_fallback=true`

Soft failures (bad color, missing banner) strip that field and keep the rest.

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

# SellMate display provisioning (portrait invariant)

SellMate treats **portrait** as a permanent hardware invariant. The panel is
always mounted vertically. The **application never rotates** the screen, never
applies Qt rotation transforms, and has no landscape layout.

Portrait desktop + touch alignment are configured once on the machine via the
**labwc / Wayland provisioning** in this repository.

## Physical vs logical geometry

| Layer | Typical geometry | Owner |
|---|---|---|
| HDMI panel native timing | 1024×600 landscape | Panel / HDMI mode |
| Logical desktop after provision | **~600×1024**, `Transform: 90` or `270` | labwc + `wlr-randr` |
| Mac development window | 800×1280 portrait | App windowed default |
| SellMate UI | Matches logical portrait size | App (no rotation) |

## What this repo installs

| Path | Role |
|---|---|
| `/etc/sellmate/display.env` | Output name, transform, touch device, calibration matrix |
| `/usr/local/bin/sellmate-apply-portrait-display` | Runs `wlr-randr --transform` at session start |
| `~/.config/labwc/autostart` | Calls the apply script on every labwc login |
| `~/.config/labwc/rc.xml` | `mapToOutput` + libinput `calibrationMatrix` for touch |

Source scripts live under [`provisioning/display/`](../provisioning/display/).

## One-time provision (Raspberry Pi OS + labwc)

Run on the Pi as a user with sudo (kiosk user defaults to `$SUDO_USER`):

```bash
cd ~/pi-touchscreen   # or your clone path
git pull

# Optional: discover names first
wlr-randr
libinput list-devices   # find "Device:" with Capabilities: touch

sudo ./provisioning/display/install-portrait-display.sh
# If the image is upside-down after reboot:
# sudo ./provisioning/display/install-portrait-display.sh --transform 270

# Or pin names explicitly:
# sudo ./provisioning/display/install-portrait-display.sh \
#   --output HDMI-A-1 \
#   --transform 90 \
#   --touch "Goodix Capacitive TouchScreen" \
#   --user sambeals

sudo reboot
```

### What the installer does

1. Writes `/etc/sellmate/display.env`.
2. Installs `/usr/local/bin/sellmate-apply-portrait-display`.
3. Appends a marked block to `~/.config/labwc/autostart` so the transform is
   applied automatically whenever labwc starts (**no manual `wlr-randr` after boot**).
4. Writes/merges `~/.config/labwc/rc.xml`:
   - `<touch … mapToOutput="HDMI-A-1" />` so touch is bound to the HDMI output
   - `<calibrationMatrix>…</calibrationMatrix>` matching the chosen transform  
     (`90` → `0 -1 1 1 0 0`, `270` → `0 1 0 -1 1 0`)

Manual `wlr-randr --transform` alone is **not** enough: without the rc.xml touch
mapping + matrix, touch coordinates stay wrong. Do not rely on ad-hoc shell
commands; use the installer.

## Verification (after reboot)

On the graphical console as the kiosk user:

```bash
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
wlr-randr
./provisioning/display/verify-portrait-display.sh
```

**Pass criteria**

1. `wlr-randr` shows your HDMI output with `Transform: 90` or `Transform: 270`
   — **not** `Transform: normal`.
2. Logical mode is portrait (height > width), typically about `600x1024`.
3. Tapping each corner hits the matching on-screen position.
4. SellMate starts fullscreen into that portrait desktop with no manual steps.

If transform is still `normal`, confirm labwc is the active compositor, that
`~/.config/labwc/autostart` contains the `SELLMATE-PORTRAIT-DISPLAY` block, and
re-run the installer + reboot.

If the picture is rotated but touch is wrong, re-run with the correct
`--touch "Device Name"` from `libinput list-devices`, or flip `--transform`
between `90` and `270` (matrix is updated to match).

## SellMate systemd unit

`services/sellmate-touchscreen.service` assumes a **already-portrait** Wayland
session:

- `QT_QPA_PLATFORM=wayland;xcb` (native Wayland; X11 fallback only)
- `WAYLAND_DISPLAY=wayland-0`
- `XDG_RUNTIME_DIR=/run/user/%U`
- **No** application rotation environment variables

Enable the app only after display verification passes:

```bash
sudo cp services/sellmate-touchscreen.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sellmate-touchscreen.service
```

## What the application does / does not do

**Does**

- Assume width ≤ height.
- Derive layout from the actual window/screen size.
- Log `display.portrait_misconfigured` if width > height (mis-provisioned OS).

**Does not**

- Call `wlr-randr` or change compositor transforms.
- Apply Qt/QML rotation transforms.
- Offer landscape layout or orientation switching.

## Transform reference

| Mount result | `--transform` | Calibration matrix |
|---|---|---|
| Portrait (default) | `90` | `0 -1 1 1 0 0` |
| Portrait, opposite cable/up orientation | `270` | `0 1 0 -1 1 0` |

wlroots/labwc transforms are counter-clockwise. Pick the value that makes the
desktop upright on the physical kiosk; the installer keeps touch in sync.

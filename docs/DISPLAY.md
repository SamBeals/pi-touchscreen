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
| Logical desktop after provision | **~600×1024**, `Transform: 270` | labwc + `wlr-randr` |
| Mac development window | 800×1280 portrait | App windowed default |
| SellMate UI | Matches logical portrait size | App (no rotation) |

SellMate machines ship with display transform **270°**. That orientation is
correct for physical assembly. Touch mapping is a **separate** calibration
problem and must not be "fixed" by flipping the display transform.

## What this repo installs

| Path | Role |
|---|---|
| `/etc/sellmate/display.env` | Output name, transform, touch device, calibration matrix (**shell-quoted** values) |
| `/usr/local/bin/sellmate-apply-portrait-display` | Runs `wlr-randr --transform` at session start |
| `~/.config/labwc/autostart` | Calls the apply script on every labwc login |
| `~/.config/labwc/rc.xml` | `mapToOutput` + libinput `calibrationMatrix` for touch |
| `/etc/udev/rules.d/99-sellmate-touch-portrait.rules` | `LIBINPUT_CALIBRATION_MATRIX` at device add |

Source scripts live under [`provisioning/display/`](../provisioning/display/).

## One-time provision (Raspberry Pi OS + labwc)

Run on the Pi as a user with sudo (kiosk user defaults to `$SUDO_USER`):

```bash
cd ~/pi-touchscreen   # or your clone path
git pull

# Optional: discover names first
wlr-randr
libinput list-devices   # find "Device:" with Capabilities: touch

# Default transform is 270 (SellMate assembly).
sudo ./provisioning/display/install-portrait-display.sh \
  --touch "yldzkj USB2IIC_CTP_CONTROL" \
  --user "$USER"

sudo reboot
```

The installer may write a **generic placeholder** matrix paired with the
transform. That is **not** sufficient for `yldzkj USB2IIC_CTP_CONTROL`. After
reboot, run the empirical calibrator (below).

### What the installer does

1. Writes `/etc/sellmate/display.env` with **shell-quoted** values, then
   validates with `bash -n` and a `source` round-trip.
2. Installs `/usr/local/bin/sellmate-apply-portrait-display`.
3. Appends a marked block to `~/.config/labwc/autostart` so the transform is
   applied automatically whenever labwc starts (**no manual `wlr-randr` after boot**).
4. Writes/merges `~/.config/labwc/rc.xml` (Pi OS `openbox_config` root):
   - Catch-all + named `<touch … mapToOutput="…" mouseEmulation="yes" />`
   - `<libinput>` `calibrationMatrix` for both `category="touch"` and the
     exact device name
5. Installs udev rules so libinput applies `LIBINPUT_CALIBRATION_MATRIX` at
   device add.

Optional: pass a measured matrix into the installer without re-running the UI:

```bash
sudo ./provisioning/display/install-portrait-display.sh \
  --transform 270 \
  --touch "yldzkj USB2IIC_CTP_CONTROL" \
  --matrix "a b c d e f"
```

## Empirical touch calibration (required)

Do **not** assume the standard libinput matrix for a 270° display transform.
Hardware testing showed transform 270 is visually correct while the generic
270 matrix remains significantly inaccurate for this controller.

```bash
# On the graphical console. Prefer sudo -E so Wayland env vars are preserved.
# User must be able to open /dev/input (group `input`) or run as root.
sudo usermod -aG input "$USER"   # once, then re-login
sudo -E ./provisioning/display/calibrate-touch.sh --apply
sudo reboot
```

What the calibrator does:

1. Fullscreen UI with five targets: top-left, top-right, bottom-left,
   bottom-right, center.
2. Reads **raw** absolute coordinates from `/dev/input/event*` (bypasses
   libinput calibration).
3. Fits affine `x' = a x + b y + c`, `y' = d x + e y + f`.
4. Writes the measured matrix to:
   - `/etc/sellmate/display.env`
   - `/etc/udev/rules.d/99-sellmate-touch-portrait.rules`
   - `~/.config/labwc/rc.xml`
5. Leaves **display transform at 270°** unchanged.

Dry-run (print matrix only, no writes):

```bash
./provisioning/display/calibrate-touch.sh
```

## Verification (after reboot)

On the graphical console as the kiosk user:

```bash
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
wlr-randr
./provisioning/display/verify-portrait-display.sh
libinput list-devices | less   # Calibration must not be identity
```

**Pass criteria**

1. `wlr-randr` shows `Transform: 270` — **not** `Transform: normal`.
2. Logical mode is portrait (height > width), typically about `600x1024`.
3. `libinput list-devices` for `yldzkj USB2IIC_CTP_CONTROL` shows a
   **non-identity** `Calibration:` line (preferably the measured matrix).
4. Tapping each corner hits the matching on-screen position.
5. SellMate starts fullscreen into that portrait desktop with no manual steps.

If transform is still `normal`, confirm labwc is the active compositor, that
`~/.config/labwc/autostart` contains the `SELLMATE-PORTRAIT-DISPLAY` block, and
re-run the installer + reboot.

If the picture is upright but touch is wrong: **re-run the calibrator**. Do not
swap 90↔270 to chase touch axes — transform 270 is the assembly standard.

## SellMate systemd unit

`services/sellmate-touchscreen.service` assumes a **already-portrait** Wayland
session:

- `QT_QPA_PLATFORM=wayland;xcb` (native Wayland; X11 fallback only)
- `WAYLAND_DISPLAY=wayland-0`
- `XDG_RUNTIME_DIR=/run/user/%U`
- **No** application rotation environment variables

Enable the app only after display + touch verification passes:

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
- Calibrate touch (that is OS provisioning only).

## Transform vs matrix reference

| Concern | Correct approach |
|---|---|
| Desktop upright on assembled machine | `SELLMATE_DISPLAY_TRANSFORM=270` |
| Touch axes / corners wrong | Measure with `calibrate-touch.sh --apply` |
| Generic placeholder only | Installer `--matrix` omitted; replace ASAP |

Placeholder matrices (not authoritative for this controller):

| Transform | Placeholder matrix |
|---|---|
| `90` | `0.0 -1.0 1.0 1.0 0.0 0.0` |
| `270` | `0.0 1.0 0.0 -1.0 1.0 0.0` |

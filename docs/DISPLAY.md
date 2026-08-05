# SellMate display provisioning (portrait invariant)

SellMate treats **portrait** as a permanent hardware invariant. The
touchscreen is always mounted vertically. The application is designed,
tested, and launched against a **logical portrait** display and **never**
rotates the screen, switches orientation, or applies UI rotation transforms.

## Physical vs logical geometry

| Layer | Typical geometry | Owner |
|---|---|---|
| HDMI panel native timing | 1024×600 landscape | Panel firmware / HDMI mode |
| Logical desktop (what apps see) | **600×1024 portrait** | OS / compositor provisioning |
| Mac development window | 800×1280 portrait | App windowed default |
| SellMate UI | Matches logical portrait size | App (no rotation) |

The OS must present the panel as portrait **before** SellMate starts. Touch
coordinates must match the displayed position after that mapping.

## What the application does

- Assumes width ≤ height at runtime.
- Derives browse columns and layout from the **actual** window/screen size.
- Logs a clear warning if width > height (misconfigured OS display).
- Does **not** rotate, rearrange into landscape, or “fix” orientation in software.

## What machine provisioning must do

1. **Rotate the logical output** so the desktop is ~600×1024 (or equivalent portrait).
2. **Calibrate / transform touch input** so taps align with the rotated picture.
3. Confirm with a tool on the Pi that the primary output reports portrait size
   before enabling the SellMate service.

Exact steps depend on the image (Raspberry Pi OS Wayland/labwc vs X11). Common
approaches:

- Kernel/firmware display rotate (`display_rotate` / dtoverlay options), **or**
- Compositor output transform (e.g. 90° / 270°) plus matching touch
  calibration matrix / libinput calibration.

After changes, reboot and verify:

```bash
# Wayland session example (tooling varies by compositor)
echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
# Confirm the logical mode is portrait (height > width), e.g. 600x1024
```

Touch test: tap the four corners of the panel; the cursor/hit target must match.

## Qt / Wayland

On the Raspberry Pi, SellMate prefers native **Wayland** (`QT_QPA_PLATFORM=wayland;xcb`)
so Qt Quick does not unnecessarily run through Xwayland. macOS leaves the
platform unset (Cocoa). Headless tests may set `QT_QPA_PLATFORM=offscreen`.

The systemd unit sets Wayland-oriented environment variables; see
`services/sellmate-touchscreen.service` and `services/touchscreen.env.example`.

## Out of scope for the app

- Landscape layout profiles or constants
- Runtime orientation switching
- Accelerometer / sensor-driven rotation
- Qt `rotation` / transform-based screen turning
- Inventory, cart, checkout, payment, persistence, or vend behavior

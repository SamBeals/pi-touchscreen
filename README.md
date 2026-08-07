# SellMate Pi Touchscreen

Fullscreen PySide6 **Qt Quick / QML** customer kiosk for a Raspberry Pi 10.1"
touchscreen **permanently mounted in portrait**.

Portrait is a hardware invariant, not an app setting:

- Pi logical display: **≈ 600×1024** (OS/compositor maps the native 1024×600 panel)
- Mac/dev windowed default: **800×1280**
- SellMate never rotates the screen or runs a landscape layout

Display rotation and touch calibration are **machine provisioning** — see
[docs/DISPLAY.md](./docs/DISPLAY.md).

Browse inventory, cart, Cloud checkout + payment status polling, idle timeout,
active-order recovery, and **configuration-driven renter themes**.

**Does not** control motors, ToF, or local vend-api. Vending stays on `sellmate-pi` background services.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md). Themes: [docs/THEMES.md](./docs/THEMES.md).
Display / Wayland: [docs/DISPLAY.md](./docs/DISPLAY.md).
Figma / Figma to Qt design loop: [docs/FIGMA.md](./docs/FIGMA.md).

## Configuration

Shared machine identity (required):

```bash
/etc/sellmate/machine.env
```

```bash
MACHINE_ID=machine_002
CLOUD_BASE=https://sellmatecloud-1002770348452.us-west4.run.app
```

Touchscreen-specific env (unit file or shell):

| Variable | Default | Meaning |
|---|---|---|
| `IDLE_TIMEOUT_SECONDS` | `90` | Clear cart → attract |
| `POLL_INTERVAL_SECONDS` | `2` | Order status poll |
| `POLL_MAX_ATTEMPTS` | `90` | ~3 minutes |
| `INVENTORY_MAX_AGE_SECONDS` | `300` | Max age for checkout |
| `INVENTORY_IDLE_REFRESH_SECONDS` | `120` | Refresh while on attract |
| `FULLSCREEN` | `true` | Kiosk mode |
| `TOUCHSCREEN_DATA_DIR` | `~/.local/share/sellmate-touchscreen` | Cache + active order |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Firestore reader JSON |
| `FIRESTORE_PROJECT_ID` | — | e.g. `sellmate-bdd22` |
| `INVENTORY_FIXTURE_PATH` | — | Lab JSON instead of Firestore |
| `THEME_ID` | `sellmate-default` | Theme package folder name |
| `THEME_PACKAGES_DIR` | `/etc/sellmate/themes` | Installed renter themes |
| `LOG_LEVEL` | `INFO` | Logging |

## Local development

```bash
cd ~/pi-touchscreen   # or this repo path
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export MACHINE_ID=machine_001
export CLOUD_BASE=https://sellmatecloud-1002770348452.us-west4.run.app
export FULLSCREEN=false
export INVENTORY_FIXTURE_PATH=$PWD/fixtures/inventory.json
export THEME_ID=sellmate-default
# export THEME_ID=sellmate-light   # light-mode reference

python -m app   # windowed portrait 800×1280 when FULLSCREEN=false
```

Windowed Mac/dev runs enable **QML hot reload** by default (watches
`app/ui/qml/` + the active theme package). Disable with `QML_HOT_RELOAD=0`.

macOS leaves `QT_QPA_PLATFORM` unset (Cocoa). Do not set Wayland plugins on Mac.

Design iteration: mock portrait frames in Figma with **Figma to Qt**, then port
tokens/layout into `themes/*/theme.json` and QML — see [docs/FIGMA.md](./docs/FIGMA.md).

## Tests

```bash
cd /path/to/pi-touchscreen
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MACHINE_ID=machine_test CLOUD_BASE=https://example.test \
  python -m unittest discover -s tests -v
```

## Raspberry Pi install (graphical session)

```bash
cd ~
git clone https://github.com/SamBeals/pi-touchscreen.git
cd pi-touchscreen
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Shared env (do not overwrite an existing file blindly)
sudo mkdir -p /etc/sellmate
sudo cp services/machine.env.example /etc/sellmate/machine.env   # only if missing
sudo nano /etc/sellmate/machine.env   # unique MACHINE_ID + CLOUD_BASE
sudo chmod 600 /etc/sellmate/machine.env

# Firestore reader credentials + touchscreen env (keep secrets out of the unit)
sudo cp /path/to/firestore-reader.json /etc/sellmate/firestore-reader.json
sudo chmod 600 /etc/sellmate/firestore-reader.json
sudo cp services/touchscreen.env.example /etc/sellmate/touchscreen.env
sudo nano /etc/sellmate/touchscreen.env
sudo chown root:root /etc/sellmate/touchscreen.env
sudo chmod 600 /etc/sellmate/touchscreen.env

# Data dir must be writable by the service user
mkdir -p ~/.local/share/sellmate-touchscreen

# REQUIRED: persistent portrait desktop + touch (labwc). Do this before the app.
# See docs/DISPLAY.md — transform stays 270; calibrate touch empirically.
sudo apt-get install -y wlr-randr || true
sudo ./provisioning/display/install-portrait-display.sh --user "$USER" \
  --touch "yldzkj USB2IIC_CTP_CONTROL"
sudo reboot
# After reboot, on the graphical console:
#   ./provisioning/display/verify-portrait-display.sh
#   sudo -E ./provisioning/display/calibrate-touch.sh --apply
#   sudo reboot
# Expect: Transform: 270; measured Calibration; touch corners align.

sudo cp services/sellmate-touchscreen.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sellmate-touchscreen.service
systemctl status sellmate-touchscreen.service --no-pager
journalctl -u sellmate-touchscreen.service -n 100 --no-pager
```

The app unit prefers native **Wayland** (`QT_QPA_PLATFORM=wayland;xcb`), runs as
non-root `sambeals`, and loads `/etc/sellmate/machine.env` plus optional
`/etc/sellmate/touchscreen.env`. It does **not** rotate the display — that is
done by labwc provisioning above. If width > height at startup, SellMate logs
`display.portrait_misconfigured` and continues without rotating the UI.

## Active-order recovery

During checkout, `TOUCHSCREEN_DATA_DIR/active_order.json` stores the Cloud `order_id`.  
On restart, the app polls that order; if still non-terminal, it resumes the payment screen and blocks a new checkout until the order finishes or is safely cancelled.

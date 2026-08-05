#!/usr/bin/env bash
# SellMate touchscreen calibrator wrapper.
# Keeps display transform at 270°; measures/writes only the touch matrix.
#
# Usage (on the Pi graphical console):
#   ./provisioning/display/calibrate-touch.sh
#   ./provisioning/display/calibrate-touch.sh --apply
#   sudo -E ./provisioning/display/calibrate-touch.sh --apply
#
# Prefer `sudo -E` so WAYLAND_DISPLAY / XDG_RUNTIME_DIR stay available for Qt.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/provisioning/display/calibrate_touch.py"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Missing calibrator: $SCRIPT" >&2
  exit 1
fi

# Ensure kiosk user can read /dev/input when not root.
if [[ "$(id -u)" -ne 0 ]]; then
  if ! id -nG 2>/dev/null | tr ' ' '\n' | grep -qx input; then
    echo "Note: user is not in group 'input'. Raw /dev/input access may fail." >&2
    echo "      Use: sudo usermod -aG input \"\$USER\" && re-login" >&2
    echo "      Or:  sudo -E $0 --apply" >&2
  fi
fi

exec python3 "$SCRIPT" \
  --device "${SELLMATE_TOUCH_DEVICE:-yldzkj USB2IIC_CTP_CONTROL}" \
  --transform "${SELLMATE_DISPLAY_TRANSFORM:-270}" \
  "$@"

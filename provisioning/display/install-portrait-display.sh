#!/usr/bin/env bash
# Provision persistent portrait display + touch mapping for Raspberry Pi OS
# (Wayland / labwc). Does not rotate anything inside the SellMate application.
#
# Usage (on the Pi, from the pi-touchscreen repo):
#   sudo ./provisioning/display/install-portrait-display.sh
#   sudo ./provisioning/display/install-portrait-display.sh --transform 270
#   sudo ./provisioning/display/install-portrait-display.sh \
#        --output HDMI-A-1 --touch "Goodix Capacitive TouchScreen"
#
# After install: log out/in or reboot, then:
#   ./provisioning/display/verify-portrait-display.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=provisioning/display/display_env.sh
source "$ROOT/provisioning/display/display_env.sh"
# shellcheck source=provisioning/display/touch_config.sh
source "$ROOT/provisioning/display/touch_config.sh"
APPLY_SRC="$ROOT/provisioning/display/sellmate-apply-portrait-display.sh"
APPLY_DST="/usr/local/bin/sellmate-apply-portrait-display"
ENV_DST="/etc/sellmate/display.env"
UDEV_DST="/etc/udev/rules.d/99-sellmate-touch-portrait.rules"

OUTPUT=""
TRANSFORM="90"
TOUCH_DEVICE=""
KIOSK_USER="${SUDO_USER:-${USER:-}}"
RECONFIGURE=1

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="${2:-}"; shift 2 ;;
    --transform) TRANSFORM="${2:-}"; shift 2 ;;
    --touch) TOUCH_DEVICE="${2:-}"; shift 2 ;;
    --user) KIOSK_USER="${2:-}"; shift 2 ;;
    --no-reconfigure) RECONFIGURE=0; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 1 ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo) so files can be installed under /etc and /usr/local." >&2
  exit 1
fi

if [[ -z "$KIOSK_USER" || "$KIOSK_USER" == "root" ]]; then
  echo "Could not determine kiosk user. Pass --user sambeals" >&2
  exit 1
fi

KIOSK_HOME="$(getent passwd "$KIOSK_USER" | cut -d: -f6 || true)"
if [[ -z "$KIOSK_HOME" || ! -d "$KIOSK_HOME" ]]; then
  echo "Home directory for user '$KIOSK_USER' not found." >&2
  exit 1
fi

if ! CAL_MATRIX="$(calibration_matrix_for_transform "$TRANSFORM")"; then
  echo "Unsupported --transform '$TRANSFORM' (use 90 or 270 for portrait)." >&2
  exit 1
fi

detect_output() {
  if [[ -n "$OUTPUT" ]]; then
    return
  fi
  if [[ -n "${WAYLAND_DISPLAY:-}" ]] && command -v wlr-randr >/dev/null 2>&1; then
    OUTPUT="$(wlr-randr 2>/dev/null | awk '/^[^[:space:]]/ && !/^[0-9]/ {print $1; exit}')"
  fi
  if [[ -z "$OUTPUT" ]]; then
    OUTPUT="HDMI-A-1"
    echo "Note: defaulting output to HDMI-A-1 (set --output if wlr-randr shows another name)."
  fi
}

detect_touch() {
  if [[ -n "$TOUCH_DEVICE" ]]; then
    return
  fi
  if command -v libinput >/dev/null 2>&1; then
    TOUCH_DEVICE="$(
      libinput list-devices 2>/dev/null | awk '
        BEGIN { name="" }
        /^Device:/ {
          name=$0
          sub(/^Device:[[:space:]]*/, "", name)
        }
        /Capabilities:/ && /touch/ {
          gsub(/[[:space:]]+$/, "", name)
          print name
          exit
        }
      '
    )"
  fi
  # Trim accidental whitespace from --touch / detection.
  TOUCH_DEVICE="${TOUCH_DEVICE#"${TOUCH_DEVICE%%[![:space:]]*}"}"
  TOUCH_DEVICE="${TOUCH_DEVICE%"${TOUCH_DEVICE##*[![:space:]]}"}"
  if [[ -z "$TOUCH_DEVICE" ]]; then
    TOUCH_DEVICE="touch"
    echo "Note: no named touchscreen detected; using libinput category 'touch'."
    echo "      Re-run with --touch \"Exact Device Name\" from libinput list-devices if needed."
  else
    echo "Detected touch device: $TOUCH_DEVICE"
  fi
}

xml_escape() {
  # Escape XML special characters in device names.
  local s="$1"
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  s="${s//\"/&quot;}"
  s="${s//\'/&apos;}"
  printf '%s' "$s"
}

detect_output
detect_touch

echo "Installing SellMate portrait display provisioning:"
echo "  user:       $KIOSK_USER ($KIOSK_HOME)"
echo "  output:     $OUTPUT"
echo "  transform:  $TRANSFORM"
echo "  touch:      $TOUCH_DEVICE"
echo "  matrix:     $CAL_MATRIX"

install -d -m 755 /etc/sellmate
install -d -m 755 /usr/local/bin
install -m 755 "$APPLY_SRC" "$APPLY_DST"

write_display_env "$ENV_DST" "$OUTPUT" "$TRANSFORM" "$TOUCH_DEVICE" "$CAL_MATRIX"
chmod 644 "$ENV_DST"
if ! validate_display_env "$ENV_DST" "$OUTPUT" "$TRANSFORM" "$TOUCH_DEVICE" "$CAL_MATRIX"; then
  echo "Refusing to continue: $ENV_DST is not safely sourceable." >&2
  echo "Touch device names and calibration matrices with spaces must be shell-quoted." >&2
  exit 1
fi

LABWC_DIR="$KIOSK_HOME/.config/labwc"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" -m 755 "$KIOSK_HOME/.config"
install -d -o "$KIOSK_USER" -g "$KIOSK_USER" -m 755 "$LABWC_DIR"

# --- autostart (merge SellMate block) ---
AUTOSTART="$LABWC_DIR/autostart"
MARKER_BEGIN="# BEGIN SELLMATE-PORTRAIT-DISPLAY"
MARKER_END="# END SELLMATE-PORTRAIT-DISPLAY"
BLOCK="$(cat <<EOF
${MARKER_BEGIN}
# Persist portrait transform at every labwc session start (no Qt/app rotation).
/usr/local/bin/sellmate-apply-portrait-display || logger -t sellmate-display "portrait apply failed"
${MARKER_END}
EOF
)"

if [[ -f "$AUTOSTART" ]]; then
  TMP="$(mktemp)"
  awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" '
    $0 == begin {skip=1; next}
    $0 == end {skip=0; next}
    !skip {print}
  ' "$AUTOSTART" > "$TMP"
  printf '%s\n' "$BLOCK" >> "$TMP"
  cat "$TMP" > "$AUTOSTART"
  rm -f "$TMP"
else
  printf '%s\n' "$BLOCK" > "$AUTOSTART"
fi
chown "$KIOSK_USER:$KIOSK_USER" "$AUTOSTART"
chmod 644 "$AUTOSTART"

# --- rc.xml touch map + calibration (labwc) ---
RC_XML="$LABWC_DIR/rc.xml"
OUTPUT_XML="$(xml_escape "$OUTPUT")"
TOUCH_XML="$(xml_escape "$TOUCH_DEVICE")"
BLOCK_FILE="$(mktemp)"
build_labwc_touch_block "$OUTPUT_XML" "$TOUCH_XML" "$CAL_MATRIX" > "$BLOCK_FILE"

# Prefer openbox_config root for Raspberry Pi OS labwc compatibility.
FRESH_RC="$(mktemp)"
{
  printf '%s\n' '<?xml version="1.0"?>'
  printf '%s\n' '<openbox_config xmlns="http://openbox.org/3.4/rc">'
  sed 's/^/  /' "$BLOCK_FILE"
  printf '%s\n' '</openbox_config>'
} > "$FRESH_RC"

export SELLMATE_RC_PATH="$RC_XML"
export SELLMATE_RC_FRESH="$FRESH_RC"
export SELLMATE_RC_BLOCK="$BLOCK_FILE"
python3 - <<'PY'
from pathlib import Path
import os
import re

rc_path = Path(os.environ["SELLMATE_RC_PATH"])
fresh = Path(os.environ["SELLMATE_RC_FRESH"]).read_text(encoding="utf-8")
block = Path(os.environ["SELLMATE_RC_BLOCK"]).read_text(encoding="utf-8").rstrip() + "\n"

begin = "<!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->"
end = "<!-- END SELLMATE-PORTRAIT-DISPLAY -->"

if rc_path.is_file() and rc_path.stat().st_size > 0:
    text = rc_path.read_text(encoding="utf-8")
    if begin in text and end in text:
        pre, rest = text.split(begin, 1)
        _, post = rest.split(end, 1)
        text = pre + block + post
    elif re.search(r"</(openbox_config|labwc_config)>\s*$", text):
        indented = "  " + block.replace("\n", "\n  ").rstrip() + "\n"
        text = re.sub(
            r"</(openbox_config|labwc_config)>\s*$",
            indented + r"</\1>\n",
            text,
        )
    else:
        text = text.rstrip() + "\n  " + block.replace("\n", "\n  ") + "\n"
else:
    text = fresh

rc_path.write_text(text, encoding="utf-8")
PY
rm -f "$FRESH_RC" "$BLOCK_FILE"
chown "$KIOSK_USER:$KIOSK_USER" "$RC_XML"
chmod 644 "$RC_XML"

# --- udev: apply the same matrix at libinput level (survives labwc match misses) ---
if [[ "$TOUCH_DEVICE" != "touch" ]]; then
  cat > "$UDEV_DST" <<EOF
# Managed by pi-touchscreen provisioning/display/install-portrait-display.sh
# Applies libinput calibration for portrait output transform=${TRANSFORM}.
ACTION=="add|change", KERNEL=="event[0-9]*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ATTRS{name}=="${TOUCH_DEVICE}", ENV{LIBINPUT_CALIBRATION_MATRIX}="${CAL_MATRIX}"
EOF
else
  cat > "$UDEV_DST" <<EOF
# Managed by pi-touchscreen provisioning/display/install-portrait-display.sh
# Applies libinput calibration to all touchscreens (no named device detected).
ACTION=="add|change", KERNEL=="event[0-9]*", ENV{ID_INPUT_TOUCHSCREEN}=="1", ENV{LIBINPUT_CALIBRATION_MATRIX}="${CAL_MATRIX}"
EOF
fi
chmod 644 "$UDEV_DST"
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules
  udevadm trigger --subsystem-match=input --action=add || true
fi

echo
echo "Installed:"
echo "  $ENV_DST"
echo "  $APPLY_DST"
echo "  $AUTOSTART"
echo "  $RC_XML"
echo "  $UDEV_DST"

if [[ "$RECONFIGURE" -eq 1 ]]; then
  # Best-effort live apply for an already-running session.
  if [[ -n "${WAYLAND_DISPLAY:-}" ]] || [[ -S "/run/user/$(id -u "$KIOSK_USER")/wayland-0" ]]; then
    RUNTIME="/run/user/$(id -u "$KIOSK_USER")"
    if sudo -u "$KIOSK_USER" env \
        "XDG_RUNTIME_DIR=$RUNTIME" \
        "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}" \
        "$APPLY_DST" 2>/dev/null; then
      echo "Applied transform via wlr-randr in the current session."
    else
      echo "Could not apply transform live; it will apply on next labwc session start."
    fi
    # libinput calibration from rc.xml is not reliably picked up by --reconfigure;
    # a full session restart / reboot is required for touch. Still try reconfigure
    # for mapToOutput refresh.
    if command -v labwc >/dev/null 2>&1; then
      sudo -u "$KIOSK_USER" env \
        "XDG_RUNTIME_DIR=$RUNTIME" \
        "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}" \
        labwc --reconfigure 2>/dev/null || true
    fi
  fi
fi

echo
echo "Next steps:"
echo "  1. Reboot (required so udev + labwc both load touch calibration)."
echo "  2. As $KIOSK_USER on the graphical console:"
echo "       $ROOT/provisioning/display/verify-portrait-display.sh"
echo "  3. Confirm wlr-randr shows Transform: $TRANSFORM (not normal)."
echo "  4. Confirm libinput list-devices Calibration is NOT 'identity matrix'."
echo "  5. Tap corners to confirm touch alignment."
echo "  6. If the image is upside-down, re-run with --transform 270 (or 90)."
echo "  7. If image is upright but touch axes are wrong, re-run with --transform 270"
echo "     (swaps the paired calibration matrix) or pass --touch with the exact"
echo "     Device: name from libinput list-devices."
echo
echo "SellMate itself does not rotate the UI; keep QT_QPA_PLATFORM=wayland;xcb."

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
APPLY_SRC="$ROOT/provisioning/display/sellmate-apply-portrait-display.sh"
APPLY_DST="/usr/local/bin/sellmate-apply-portrait-display"
ENV_DST="/etc/sellmate/display.env"

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

case "$TRANSFORM" in
  90)
    CAL_MATRIX="0 -1 1 1 0 0"
    ;;
  270)
    CAL_MATRIX="0 1 0 -1 1 0"
    ;;
  180)
    CAL_MATRIX="-1 0 1 0 -1 1"
    ;;
  *)
    echo "Unsupported --transform '$TRANSFORM' (use 90 or 270 for portrait)." >&2
    exit 1
    ;;
esac

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
          print name
          exit
        }
      '
    )"
  fi
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

cat > "$ENV_DST" <<EOF
# Managed by pi-touchscreen provisioning/display/install-portrait-display.sh
SELLMATE_DISPLAY_OUTPUT=${OUTPUT}
SELLMATE_DISPLAY_TRANSFORM=${TRANSFORM}
SELLMATE_TOUCH_DEVICE=${TOUCH_DEVICE}
SELLMATE_TOUCH_CALIBRATION_MATRIX=${CAL_MATRIX}
EOF
chmod 644 "$ENV_DST"

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

# --- rc.xml touch map + calibration ---
RC_XML="$LABWC_DIR/rc.xml"
OUTPUT_XML="$(xml_escape "$OUTPUT")"
# libinput category: concrete device name, or type "touch" as fallback.
LIBINPUT_CATEGORY="$(xml_escape "$TOUCH_DEVICE")"
# <touch deviceName> empty = all touch devices (used when category is the type "touch").
if [[ "$TOUCH_DEVICE" == "touch" ]]; then
  TOUCH_NAME_XML=""
else
  TOUCH_NAME_XML="$(xml_escape "$TOUCH_DEVICE")"
fi
# Prefer openbox_config root for Raspberry Pi OS labwc compatibility.
RC_BODY="$(cat <<EOF
<?xml version="1.0"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->
  <touch deviceName="${TOUCH_NAME_XML}" mapToOutput="${OUTPUT_XML}" mouseEmulation="no" />
  <libinput>
    <device category="${LIBINPUT_CATEGORY}">
      <calibrationMatrix>${CAL_MATRIX}</calibrationMatrix>
    </device>
  </libinput>
  <!-- END SELLMATE-PORTRAIT-DISPLAY -->
</openbox_config>
EOF
)"

FRESH_RC="$(mktemp)"
printf '%s\n' "$RC_BODY" > "$FRESH_RC"
export SELLMATE_RC_PATH="$RC_XML"
export SELLMATE_RC_FRESH="$FRESH_RC"
export SELLMATE_TOUCH_NAME_XML="$TOUCH_NAME_XML"
export SELLMATE_LIBINPUT_CATEGORY="$LIBINPUT_CATEGORY"
export SELLMATE_OUTPUT_XML="$OUTPUT_XML"
export SELLMATE_CAL_MATRIX="$CAL_MATRIX"
python3 - <<'PY'
from pathlib import Path
import os
import re

rc_path = Path(os.environ["SELLMATE_RC_PATH"])
fresh = Path(os.environ["SELLMATE_RC_FRESH"]).read_text(encoding="utf-8")
touch_name = os.environ["SELLMATE_TOUCH_NAME_XML"]
category = os.environ["SELLMATE_LIBINPUT_CATEGORY"]
output = os.environ["SELLMATE_OUTPUT_XML"]
matrix = os.environ["SELLMATE_CAL_MATRIX"]

block = f"""<!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->
  <touch deviceName="{touch_name}" mapToOutput="{output}" mouseEmulation="no" />
  <libinput>
    <device category="{category}">
      <calibrationMatrix>{matrix}</calibrationMatrix>
    </device>
  </libinput>
  <!-- END SELLMATE-PORTRAIT-DISPLAY -->"""

begin = "<!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->"
end = "<!-- END SELLMATE-PORTRAIT-DISPLAY -->"

if rc_path.is_file() and rc_path.stat().st_size > 0:
    text = rc_path.read_text(encoding="utf-8")
    if begin in text and end in text:
        pre, rest = text.split(begin, 1)
        _, post = rest.split(end, 1)
        text = pre + block + post
    elif re.search(r"</(openbox_config|labwc_config)>\s*$", text):
        text = re.sub(
            r"</(openbox_config|labwc_config)>\s*$",
            "  " + block.replace("\n", "\n  ") + r"\n</\1>\n",
            text,
        )
    else:
        text = text.rstrip() + "\n  " + block.replace("\n", "\n  ") + "\n"
else:
    text = fresh

rc_path.write_text(text, encoding="utf-8")
PY
rm -f "$FRESH_RC"
chown "$KIOSK_USER:$KIOSK_USER" "$RC_XML"
chmod 644 "$RC_XML"

echo
echo "Installed:"
echo "  $ENV_DST"
echo "  $APPLY_DST"
echo "  $AUTOSTART"
echo "  $RC_XML"

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
echo "  1. Reboot (or log out/in) so labwc reloads autostart + rc.xml."
echo "  2. As $KIOSK_USER on the graphical console:"
echo "       $ROOT/provisioning/display/verify-portrait-display.sh"
echo "  3. Confirm wlr-randr shows Transform: $TRANSFORM (not normal)."
echo "  4. Tap corners to confirm touch alignment."
echo "  5. If the image is upside-down, re-run with --transform 270 (or 90)."
echo
echo "SellMate itself does not rotate the UI; keep QT_QPA_PLATFORM=wayland;xcb."

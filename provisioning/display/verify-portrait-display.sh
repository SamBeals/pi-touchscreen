#!/usr/bin/env bash
# Verify SellMate portrait display + touch provisioning (labwc / wlr-randr / libinput).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${SELLMATE_DISPLAY_ENV:-/etc/sellmate/display.env}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

OUTPUT="${SELLMATE_DISPLAY_OUTPUT:-HDMI-A-1}"
TRANSFORM="${SELLMATE_DISPLAY_TRANSFORM:-90}"
TOUCH_DEVICE="${SELLMATE_TOUCH_DEVICE:-}"
CAL_MATRIX="${SELLMATE_TOUCH_CALIBRATION_MATRIX:-}"
UDEV_RULE="/etc/udev/rules.d/99-sellmate-touch-portrait.rules"
FAIL=0

echo "== SellMate portrait display verify =="
echo "Expected output:    $OUTPUT"
echo "Expected transform: $TRANSFORM"
echo "Touch device:       ${TOUCH_DEVICE:-"(unset)"}"
echo "Calibration matrix: ${CAL_MATRIX:-"(unset)"}"
echo

if [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "FAIL: WAYLAND_DISPLAY is unset (run inside the graphical Wayland session)."
  exit 1
fi

if ! command -v wlr-randr >/dev/null 2>&1; then
  echo "FAIL: wlr-randr not installed (apt install wlr-randr)."
  exit 1
fi

REPORT="$(wlr-randr)"
echo "$REPORT"
echo

block="$(echo "$REPORT" | awk -v out="$OUTPUT" '
  $0 ~ "^"out"(\\s|$)" {p=1; print; next}
  p && /^[^[:space:]]/ {exit}
  p {print}
')"

if [[ -z "$block" ]]; then
  echo "FAIL: output $OUTPUT not present in wlr-randr."
  FAIL=1
else
  if echo "$block" | grep -qiE "Transform:[[:space:]]*${TRANSFORM}\\b"; then
    echo "OK: Transform is $TRANSFORM"
  elif echo "$block" | grep -qiE "Transform:[[:space:]]*normal\\b"; then
    echo "FAIL: Transform is still normal (portrait transform not applied)."
    FAIL=1
  else
    got="$(echo "$block" | awk -F: '/Transform:/ {gsub(/^[[:space:]]+/,"",$2); print $2; exit}')"
    echo "FAIL: Transform is '${got:-unknown}', expected $TRANSFORM."
    FAIL=1
  fi

  if echo "$block" | grep -qoE '[0-9]+x[0-9]+[[:space:]]*px'; then
    size="$(echo "$block" | grep -oE '[0-9]+x[0-9]+[[:space:]]*px' | head -1 | tr -d ' px')"
    w="${size%x*}"; h="${size#*x}"
    if [[ "$w" -lt "$h" ]]; then
      echo "OK: logical mode ${w}x${h} is portrait"
    else
      echo "WARN: logical mode ${w}x${h} is not portrait (width >= height)"
    fi
  fi
fi

echo
echo "== Touch provisioning files =="
RC_XML="${HOME}/.config/labwc/rc.xml"
if [[ -f "$RC_XML" ]] && grep -q "BEGIN SELLMATE-PORTRAIT-DISPLAY" "$RC_XML"; then
  echo "OK: $RC_XML contains SellMate touch block"
  if grep -q 'mapToOutput=' "$RC_XML" && grep -q 'calibrationMatrix' "$RC_XML"; then
    echo "OK: rc.xml has mapToOutput + calibrationMatrix"
  else
    echo "FAIL: rc.xml missing mapToOutput or calibrationMatrix"
    FAIL=1
  fi
  if [[ -n "$TOUCH_DEVICE" && "$TOUCH_DEVICE" != "touch" ]]; then
    if grep -Fq "$TOUCH_DEVICE" "$RC_XML"; then
      echo "OK: rc.xml references touch device '$TOUCH_DEVICE'"
    else
      echo "FAIL: rc.xml does not mention touch device '$TOUCH_DEVICE'"
      FAIL=1
    fi
  fi
else
  echo "FAIL: $RC_XML missing SellMate portrait touch block"
  FAIL=1
fi

if [[ -f "$UDEV_RULE" ]]; then
  echo "OK: udev rule present ($UDEV_RULE)"
  if [[ -n "$CAL_MATRIX" ]] && grep -Fq "$CAL_MATRIX" "$UDEV_RULE"; then
    echo "OK: udev rule embeds calibration matrix"
  else
    echo "WARN: udev rule present but matrix text not found (re-run installer)"
  fi
  if [[ -n "$TOUCH_DEVICE" && "$TOUCH_DEVICE" != "touch" ]]; then
    if grep -Fq "$TOUCH_DEVICE" "$UDEV_RULE"; then
      echo "OK: udev rule matches touch device name"
    else
      echo "FAIL: udev rule does not match touch device '$TOUCH_DEVICE'"
      FAIL=1
    fi
  fi
else
  echo "FAIL: missing $UDEV_RULE (libinput may still use identity calibration)"
  FAIL=1
fi

echo
echo "== libinput calibration (active device) =="
if command -v libinput >/dev/null 2>&1; then
  LI="$(libinput list-devices 2>/dev/null || true)"
  if [[ -z "$LI" ]]; then
    echo "WARN: libinput list-devices returned no data (permissions? try sudo)"
  else
    touch_block="$(echo "$LI" | awk -v want="$TOUCH_DEVICE" '
      BEGIN { name=""; dump=0 }
      /^Device:/ {
        if (dump) exit
        name=$0
        sub(/^Device:[[:space:]]*/, "", name)
        gsub(/[[:space:]]+$/, "", name)
        buf=name "\n"
        dump=0
        next
      }
      {
        buf=buf $0 "\n"
        if ($0 ~ /Capabilities:/ && $0 ~ /touch/) {
          if (want == "" || want == "touch" || name == want) dump=1
        }
      }
      END { if (dump) printf "%s", buf }
    ')"
    if [[ -z "$touch_block" ]]; then
      # Fall back to first touchscreen block.
      touch_block="$(echo "$LI" | awk '
        BEGIN {keep=0; buf=""}
        /^Device:/ { if (keep) { print buf; exit } buf=$0 "\n"; keep=0; next }
        { buf=buf $0 "\n" }
        /Capabilities:/ && /touch/ { keep=1 }
        END { if (keep) print buf }
      ')"
    fi
    if [[ -n "$touch_block" ]]; then
      echo "$touch_block" | sed -n '1,20p'
      cal="$(echo "$touch_block" | awk -F: '/Calibration:/ {sub(/^[[:space:]]+/,"",$2); print $2; exit}')"
      if [[ -z "$cal" ]]; then
        echo "WARN: no Calibration: line in libinput output"
      elif echo "$cal" | grep -qi 'identity'; then
        echo "FAIL: libinput Calibration is still identity (matrix not active)."
        echo "      Reboot after installer, confirm udev rule, then: sudo udevadm trigger"
        FAIL=1
      else
        echo "OK: libinput Calibration is non-identity ($cal)"
      fi
    else
      echo "WARN: could not find a touchscreen in libinput list-devices"
    fi
  fi
else
  echo "WARN: libinput not installed; skip calibration probe"
fi

echo
echo "Manual check: tap each corner; the pointer/hit target must match."

if [[ "$FAIL" -ne 0 ]]; then
  echo
  echo "Provisioning incomplete. Re-run:"
  echo "  sudo $ROOT/provisioning/display/install-portrait-display.sh --touch \"${TOUCH_DEVICE:-yldzkj USB2IIC_CTP_CONTROL}\""
  echo "  sudo reboot"
  exit 1
fi

echo
echo "PASS: portrait transform + touch calibration provisioning look active."
exit 0

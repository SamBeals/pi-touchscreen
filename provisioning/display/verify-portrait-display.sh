#!/usr/bin/env bash
# Verify SellMate portrait display provisioning (labwc / wlr-randr / touch).
set -euo pipefail

ENV_FILE="${SELLMATE_DISPLAY_ENV:-/etc/sellmate/display.env}"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

OUTPUT="${SELLMATE_DISPLAY_OUTPUT:-HDMI-A-1}"
TRANSFORM="${SELLMATE_DISPLAY_TRANSFORM:-90}"
FAIL=0

echo "== SellMate portrait display verify =="
echo "Expected output:    $OUTPUT"
echo "Expected transform: $TRANSFORM"
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

  # Logical size should be portrait (height > width) after 90/270.
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
echo "Touch check (manual): tap each corner; the pointer/hit target must match."
echo "labwc maps touch via ~/.config/labwc/rc.xml (mapToOutput + calibrationMatrix)."

if [[ "$FAIL" -ne 0 ]]; then
  echo
  echo "Provisioning incomplete. Re-run:"
  echo "  sudo ./provisioning/display/install-portrait-display.sh"
  exit 1
fi

echo
echo "PASS: portrait transform is active."
exit 0

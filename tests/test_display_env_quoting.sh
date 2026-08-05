#!/usr/bin/env bash
# Regression: display.env values with spaces must source without word-splitting.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=provisioning/display/display_env.sh
source "$ROOT/provisioning/display/display_env.sh"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

OUTPUT="HDMI-A-1"
TRANSFORM="90"
TOUCH_DEVICE="yldzkj USB2IIC_CTP_CONTROL"
CAL_MATRIX="0.0 -1.0 1.0 1.0 0.0 0.0"

write_display_env "$TMP" "$OUTPUT" "$TRANSFORM" "$TOUCH_DEVICE" "$CAL_MATRIX"

if ! validate_display_env "$TMP" "$OUTPUT" "$TRANSFORM" "$TOUCH_DEVICE" "$CAL_MATRIX"; then
  echo "FAIL: quoted display.env did not round-trip" >&2
  echo "----- generated file -----" >&2
  cat "$TMP" >&2 || true
  exit 1
fi

# Guard against the original bug: bare spaces with no quoting/escapes.
# Broken:  SELLMATE_TOUCH_DEVICE=yldzkj USB2IIC_CTP_CONTROL
# Fixed:   SELLMATE_TOUCH_DEVICE='yldzkj USB2IIC_CTP_CONTROL'
#      or  SELLMATE_TOUCH_DEVICE=yldzkj\ USB2IIC_CTP_CONTROL
if grep -Eq "^SELLMATE_TOUCH_DEVICE=[^'\"\\]*[[:space:]]" "$TMP"; then
  echo "FAIL: SELLMATE_TOUCH_DEVICE has unescaped spaces (not shell-safe)" >&2
  cat "$TMP" >&2
  exit 1
fi
if grep -Eq "^SELLMATE_TOUCH_CALIBRATION_MATRIX=[^'\"\\]*[[:space:]]" "$TMP"; then
  echo "FAIL: SELLMATE_TOUCH_CALIBRATION_MATRIX has unescaped spaces (not shell-safe)" >&2
  cat "$TMP" >&2
  exit 1
fi

echo "OK: display.env quoting round-trips spaced touch device + matrix"
exit 0

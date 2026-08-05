#!/usr/bin/env bash
# Regression: labwc touch block + matrices for portrait transforms.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=provisioning/display/touch_config.sh
source "$ROOT/provisioning/display/touch_config.sh"

m90="$(calibration_matrix_for_transform 90)"
m270="$(calibration_matrix_for_transform 270)"
[[ "$m90" == "0.0 -1.0 1.0 1.0 0.0 0.0" ]] || { echo "bad 90 matrix: $m90" >&2; exit 1; }
[[ "$m270" == "0.0 1.0 0.0 -1.0 1.0 0.0" ]] || { echo "bad 270 matrix: $m270" >&2; exit 1; }

block="$(build_labwc_touch_block "HDMI-A-1" "yldzkj USB2IIC_CTP_CONTROL" "$m90")"
echo "$block" | grep -Fq 'deviceName=""' || { echo "missing catch-all touch" >&2; exit 1; }
echo "$block" | grep -Fq 'deviceName="yldzkj USB2IIC_CTP_CONTROL"' || { echo "missing named touch" >&2; exit 1; }
echo "$block" | grep -Fq 'mapToOutput="HDMI-A-1"' || { echo "missing mapToOutput" >&2; exit 1; }
echo "$block" | grep -Fq 'mouseEmulation="yes"' || { echo "missing mouseEmulation yes" >&2; exit 1; }
echo "$block" | grep -Fq '<device category="touch">' || { echo "missing category touch" >&2; exit 1; }
echo "$block" | grep -Fq '<device category="yldzkj USB2IIC_CTP_CONTROL">' || { echo "missing named category" >&2; exit 1; }
echo "$block" | grep -Fq "<calibrationMatrix>${m90}</calibrationMatrix>" || { echo "missing matrix" >&2; exit 1; }

echo "OK: touch_config block + matrices"
exit 0

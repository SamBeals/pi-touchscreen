# Shared touch-calibration matrices for SellMate portrait provisioning.
# Sourced by install-portrait-display.sh (optional) and tests.
#
# Matrices follow labwc/libinput "clockwise" tables and match the usual
# xrandr/wlroots pairing for output transforms:
#   transform 90  -> 90° CW matrix
#   transform 270 -> 270° CW matrix

calibration_matrix_for_transform() {
  case "$1" in
    90)  printf '%s' "0.0 -1.0 1.0 1.0 0.0 0.0" ;;
    270) printf '%s' "0.0 1.0 0.0 -1.0 1.0 0.0" ;;
    180) printf '%s' "-1.0 0.0 1.0 0.0 -1.0 1.0" ;;
    *)   return 1 ;;
  esac
}

# Build the SellMate labwc rc.xml fragment (mapToOutput + calibration).
# Args: output touch_device cal_matrix
# touch_device may be the literal type "touch" meaning unnamed catch-all only.
build_labwc_touch_block() {
  local output="$1"
  local touch_device="$2"
  local cal_matrix="$3"

  cat <<EOF
<!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->
  <!-- Catch-all: bind every touchscreen to the portrait HDMI output. -->
  <touch deviceName="" mapToOutput="${output}" mouseEmulation="yes" />
EOF

  if [[ -n "$touch_device" && "$touch_device" != "touch" ]]; then
    cat <<EOF
  <!-- Named device (from libinput list-devices). -->
  <touch deviceName="${touch_device}" mapToOutput="${output}" mouseEmulation="yes" />
EOF
  fi

  cat <<EOF
  <libinput>
    <!-- Type-wide fallback so matrix applies even if the name string drifts. -->
    <device category="touch">
      <calibrationMatrix>${cal_matrix}</calibrationMatrix>
    </device>
EOF

  if [[ -n "$touch_device" && "$touch_device" != "touch" ]]; then
    cat <<EOF
    <device category="${touch_device}">
      <calibrationMatrix>${cal_matrix}</calibrationMatrix>
    </device>
EOF
  fi

  cat <<EOF
  </libinput>
  <!-- END SELLMATE-PORTRAIT-DISPLAY -->
EOF
}

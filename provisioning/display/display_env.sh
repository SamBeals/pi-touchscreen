# Shared helpers for writing / validating SellMate display.env files.
# Sourced by install-portrait-display.sh and tests.
#
# Values that may contain spaces (touch device names, calibration matrices)
# MUST be written with shell_quote so `source display.env` is safe.

shell_quote() {
  # Prefer readable single quotes when the value has no apostrophes; otherwise
  # fall back to bash printf %q (backslash escapes / $'...' forms).
  local s="$1"
  if [[ "$s" != *"'"* ]]; then
    printf "'%s'" "$s"
  else
    printf '%q' "$s"
  fi
}

write_display_env() {
  # write_display_env <path> <output> <transform> <touch_device> <cal_matrix>
  local path="$1"
  local output="$2"
  local transform="$3"
  local touch_device="$4"
  local cal_matrix="$5"

  cat > "$path" <<EOF
# Managed by pi-touchscreen provisioning/display/install-portrait-display.sh
# Values are shell-quoted so names/matrices with spaces source correctly.
SELLMATE_DISPLAY_OUTPUT=$(shell_quote "$output")
SELLMATE_DISPLAY_TRANSFORM=$(shell_quote "$transform")
SELLMATE_TOUCH_DEVICE=$(shell_quote "$touch_device")
SELLMATE_TOUCH_CALIBRATION_MATRIX=$(shell_quote "$cal_matrix")
EOF
}

validate_display_env() {
  # validate_display_env <path> <expected_output> <expected_transform> <expected_touch> <expected_matrix>
  # Returns 0 on success; prints errors and returns 1 on failure.
  local path="$1"
  local expect_output="$2"
  local expect_transform="$3"
  local expect_touch="$4"
  local expect_matrix="$5"

  if [[ ! -f "$path" ]]; then
    echo "display.env missing: $path" >&2
    return 1
  fi

  if ! bash -n "$path"; then
    echo "display.env failed bash -n syntax check: $path" >&2
    return 1
  fi

  # Round-trip in a clean subshell so sourcing cannot leak into the caller.
  # shellcheck disable=SC1090
  if ! (
    set -euo pipefail
    # Unset first so missing assignments are detected.
    unset SELLMATE_DISPLAY_OUTPUT SELLMATE_DISPLAY_TRANSFORM
    unset SELLMATE_TOUCH_DEVICE SELLMATE_TOUCH_CALIBRATION_MATRIX
    # shellcheck disable=SC1090
    source "$path"
    if [[ "${SELLMATE_DISPLAY_OUTPUT:-}" != "$expect_output" ]]; then
      echo "SELLMATE_DISPLAY_OUTPUT mismatch: got '${SELLMATE_DISPLAY_OUTPUT:-}' want '$expect_output'" >&2
      exit 1
    fi
    if [[ "${SELLMATE_DISPLAY_TRANSFORM:-}" != "$expect_transform" ]]; then
      echo "SELLMATE_DISPLAY_TRANSFORM mismatch: got '${SELLMATE_DISPLAY_TRANSFORM:-}' want '$expect_transform'" >&2
      exit 1
    fi
    if [[ "${SELLMATE_TOUCH_DEVICE:-}" != "$expect_touch" ]]; then
      echo "SELLMATE_TOUCH_DEVICE mismatch: got '${SELLMATE_TOUCH_DEVICE:-}' want '$expect_touch'" >&2
      exit 1
    fi
    if [[ "${SELLMATE_TOUCH_CALIBRATION_MATRIX:-}" != "$expect_matrix" ]]; then
      echo "SELLMATE_TOUCH_CALIBRATION_MATRIX mismatch: got '${SELLMATE_TOUCH_CALIBRATION_MATRIX:-}' want '$expect_matrix'" >&2
      exit 1
    fi
  ); then
    echo "display.env failed source round-trip validation: $path" >&2
    return 1
  fi

  return 0
}

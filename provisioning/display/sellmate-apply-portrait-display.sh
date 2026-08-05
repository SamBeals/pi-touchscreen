#!/usr/bin/env bash
# Apply SellMate portrait output transform via wlr-randr.
# Invoked from labwc autostart on every graphical session start.
set -euo pipefail

ENV_FILE="${SELLMATE_DISPLAY_ENV:-/etc/sellmate/display.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

OUTPUT="${SELLMATE_DISPLAY_OUTPUT:-HDMI-A-1}"
TRANSFORM="${SELLMATE_DISPLAY_TRANSFORM:-270}"

if ! command -v wlr-randr >/dev/null 2>&1; then
  echo "sellmate-apply-portrait-display: wlr-randr not found" >&2
  exit 1
fi

if [[ -z "${WAYLAND_DISPLAY:-}" && -z "${XDG_RUNTIME_DIR:-}" ]]; then
  echo "sellmate-apply-portrait-display: no Wayland session environment" >&2
  exit 1
fi

# Wait for the compositor to publish the output (labwc autostart can race).
ready=0
for _ in $(seq 1 50); do
  if wlr-randr 2>/dev/null | grep -qE "^${OUTPUT}(\s|$)"; then
    ready=1
    break
  fi
  sleep 0.1
done

if [[ "$ready" -ne 1 ]]; then
  echo "sellmate-apply-portrait-display: output ${OUTPUT} not found" >&2
  wlr-randr 2>/dev/null || true
  exit 1
fi

exec wlr-randr --output "$OUTPUT" --transform "$TRANSFORM"

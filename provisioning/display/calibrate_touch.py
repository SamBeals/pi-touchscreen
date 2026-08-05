"""
SellMate touchscreen calibration utility (Pi / Wayland / labwc).

Shows five on-screen targets, reads RAW absolute coordinates from the
evdev node (bypasses libinput calibration), fits a 3x3 affine calibration
matrix, and can apply it to udev + /etc/sellmate/display.env + labwc rc.xml.

Display transform is independent and must stay at 270 for SellMate hardware.
This tool only measures/writes the touch matrix.

Usage (on the Pi graphical session):
  python3 provisioning/display/calibrate_touch.py \\
    --device "yldzkj USB2IIC_CTP_CONTROL" --apply

Requires PySide6 and read access to /dev/input (user in group `input`, or sudo -E).
"""

from __future__ import annotations

import argparse
import array
import fcntl
import glob
import json
import math
import os
import re
import struct
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# region agent log
_AGENT_LOG_PATHS = (
    Path("/Users/sam/AndroidStudioProjects/.cursor/debug-898235.log"),
    Path("/tmp/debug-898235.log"),
)


def _agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict] = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": "898235",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, separators=(",", ":"))
    print(f"[calibrate-debug] {message} {json.dumps(data or {})}", flush=True)
    for path in _AGENT_LOG_PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            continue


# endregion

# ---------------------------------------------------------------------------
# Math: fit libinput calibration matrix (a b c d e f)
#   x' = a*x + b*y + c
#   y' = d*x + e*y + f
# ---------------------------------------------------------------------------


def fit_affine(
    raw: Sequence[Tuple[float, float]],
    targets: Sequence[Tuple[float, float]],
) -> Tuple[float, float, float, float, float, float]:
    if len(raw) != len(targets) or len(raw) < 3:
        raise ValueError("need at least 3 corresponding raw/target points")

    def solve_axis(vals: Sequence[float]) -> Tuple[float, float, float]:
        sxx = syy = sxy = sx = sy = n = 0.0
        sxv = syv = sv = 0.0
        for (x, y), v in zip(raw, vals):
            sxx += x * x
            syy += y * y
            sxy += x * y
            sx += x
            sy += y
            n += 1.0
            sxv += x * v
            syv += y * v
            sv += v
        m = [
            [sxx, sxy, sx],
            [sxy, syy, sy],
            [sx, sy, n],
        ]
        return _solve3(m, [sxv, syv, sv])

    a, b, c = solve_axis([t[0] for t in targets])
    d, e, f = solve_axis([t[1] for t in targets])
    return (a, b, c, d, e, f)


def _solve3(m: List[List[float]], rhs: List[float]) -> Tuple[float, float, float]:
    a = [row[:] + [rhs[i]] for i, row in enumerate(m)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-12:
            raise ValueError("singular calibration fit (degenerate touch points)")
        a[col], a[pivot] = a[pivot], a[col]
        div = a[col][col]
        for j in range(col, 4):
            a[col][j] /= div
        for r in range(3):
            if r == col:
                continue
            factor = a[r][col]
            for j in range(col, 4):
                a[r][j] -= factor * a[col][j]
    return (a[0][3], a[1][3], a[2][3])


Affine = Tuple[float, float, float, float, float, float]

# Normalized-space 90° counterclockwise about the unit square:
#   (x, y) -> (1 - y, x)
# Used only as a libinput correction composed with the empirical fit.
ROTATE_CCW_90: Affine = (0.0, -1.0, 1.0, 1.0, 0.0, 0.0)
ROTATE_CW_90: Affine = (0.0, 1.0, 0.0, -1.0, 0.0, 1.0)


def format_matrix(coeffs: Sequence[float]) -> str:
    return " ".join(f"{v:.6f}" for v in coeffs)


def parse_matrix(text: str) -> Affine:
    parts = [float(x) for x in text.split()]
    if len(parts) != 6:
        raise ValueError(f"expected 6 matrix coefficients, got {len(parts)}")
    return (parts[0], parts[1], parts[2], parts[3], parts[4], parts[5])


def apply_affine(coeffs: Sequence[float], x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = coeffs
    return (a * x + b * y + c, d * x + e * y + f)


def compose_affine(left: Sequence[float], right: Sequence[float]) -> Affine:
    """Return left ∘ right (apply right first, then left) as libinput a..f."""
    la, lb, lc, ld, le, lf = left
    ra, rb, rc, rd, re, rf = right
    return (
        la * ra + lb * rd,
        la * rb + lb * re,
        la * rc + lb * rf + lc,
        ld * ra + le * rd,
        ld * rb + le * re,
        ld * rc + le * rf + lf,
    )


def libinput_matrix_for_display(
    measured: Sequence[float],
    *,
    display_transform: str = "270",
) -> Affine:
    """Compose the empirical fit into the matrix written to libinput/udev/labwc.

    Pipeline finding (SellMate hardware, transform 270):
      - Calibrator fits M: raw evdev → logical on-screen targets (low RMS).
      - Display transform stays at 270 via wlr-randr (unchanged).
      - Writing M alone to LIBINPUT_CALIBRATION_MATRIX yields touch events
        that reach Qt rotated 90° clockwise vs the visual desktop.
      - Correction belongs in the *generated libinput matrix*: left-multiply
        a 90° CCW normalized rotation so libinput emits R_ccw90 ∘ M.
      - Do not change the app, display transform, or replace M with a generic
        90/270 preset.
    """
    measured_t = (
        float(measured[0]),
        float(measured[1]),
        float(measured[2]),
        float(measured[3]),
        float(measured[4]),
        float(measured[5]),
    )
    if display_transform == "270":
        return compose_affine(ROTATE_CCW_90, measured_t)
    return measured_t


def simulate_touch_to_qt(
    libinput_matrix: Sequence[float],
    raw_x: float,
    raw_y: float,
    *,
    stack_extra_cw90: bool = True,
) -> Tuple[float, float]:
    """Model observed compositor stack when feeding libinput a calibration matrix.

    Hardware: with display transform 270, installing the bare empirical matrix
    makes Qt see coordinates rotated 90° CW from the calibrator targets. The
    ``stack_extra_cw90`` flag models that residual so tests can verify the
    composed correction cancels it.
    """
    x, y = apply_affine(libinput_matrix, raw_x, raw_y)
    if stack_extra_cw90:
        x, y = apply_affine(ROTATE_CW_90, x, y)
    return (x, y)


def rms_error(
    coeffs: Sequence[float],
    raw: Sequence[Tuple[float, float]],
    targets: Sequence[Tuple[float, float]],
) -> float:
    err = 0.0
    for (x, y), (tx, ty) in zip(raw, targets):
        px, py = apply_affine(coeffs, x, y)
        err += (px - tx) ** 2 + (py - ty) ** 2
    return math.sqrt(err / max(1, len(raw)))


# ---------------------------------------------------------------------------
# Raw evdev reader (pre-libinput)
# ---------------------------------------------------------------------------


@dataclass
class AbsAxis:
    min: int
    max: int

    def normalize(self, value: int) -> float:
        span = self.max - self.min
        if span <= 0:
            return 0.0
        return max(0.0, min(1.0, (value - self.min) / span))


def _EVIOCGABS(code: int) -> int:
    # _IOR('E', 0x40 + code, struct input_absinfo) with sizeof=24
    return 0x80184540 + code


class RawTouchDevice:
    EV_SYN = 0x00
    EV_KEY = 0x01
    EV_ABS = 0x03
    SYN_REPORT = 0
    ABS_X = 0x00
    ABS_Y = 0x01
    ABS_MT_POSITION_X = 0x35
    ABS_MT_POSITION_Y = 0x36
    BTN_TOUCH = 0x14A
    BTN_LEFT = 0x110

    def __init__(self, device_name: str):
        self.device_name = device_name
        self.path = self._find_event_path(device_name)
        if not self.path:
            raise FileNotFoundError(
                f"No /dev/input/event* for device name {device_name!r}"
            )
        self._fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        self.axis_x, self.axis_y, self._use_mt = self._read_axes()
        self._x: Optional[int] = None
        self._y: Optional[int] = None
        self._touching = False
        self._fmt = "llHHi"
        self._size = struct.calcsize(self._fmt)

    @staticmethod
    def _find_event_path(device_name: str) -> Optional[str]:
        needle = device_name.strip()
        exact: Optional[str] = None
        partial: Optional[str] = None
        for name_path in sorted(glob.glob("/sys/class/input/event*/device/name")):
            try:
                with open(name_path, encoding="utf-8") as fh:
                    name = fh.read().strip()
            except OSError:
                continue
            event = Path(name_path).parent.parent.name
            dev = f"/dev/input/{event}"
            if name == needle:
                exact = dev
                break
            if needle.lower() in name.lower() and partial is None:
                partial = dev
        return exact or partial

    def _egabs(self, code: int) -> AbsAxis:
        buf = array.array("i", [0] * 6)
        fcntl.ioctl(self._fd, _EVIOCGABS(code), buf)
        # value, min, max, fuzz, flat, resolution
        return AbsAxis(min=int(buf[1]), max=int(buf[2]))

    def _read_axes(self) -> Tuple[AbsAxis, AbsAxis, bool]:
        try:
            mt_x = self._egabs(self.ABS_MT_POSITION_X)
            mt_y = self._egabs(self.ABS_MT_POSITION_Y)
            if mt_x.max > mt_x.min and mt_y.max > mt_y.min:
                return mt_x, mt_y, True
        except OSError:
            pass
        try:
            return self._egabs(self.ABS_X), self._egabs(self.ABS_Y), False
        except OSError:
            return AbsAxis(0, 4095), AbsAxis(0, 4095), False

    def close(self) -> None:
        try:
            os.close(self._fd)
        except OSError:
            pass

    def poll_sample(self, timeout_s: float = 60.0) -> Tuple[float, float]:
        deadline = time.monotonic() + timeout_s
        saw_down = False
        last: Optional[Tuple[float, float]] = None
        while time.monotonic() < deadline:
            sample = self._drain()
            if sample is not None:
                last = sample
                saw_down = True
            elif saw_down and last is not None and not self._touching:
                return last
            time.sleep(0.005)
        if last is not None:
            return last
        raise TimeoutError("timed out waiting for touch sample")

    def _drain(self) -> Optional[Tuple[float, float]]:
        got_report = False
        while True:
            try:
                data = os.read(self._fd, self._size)
            except BlockingIOError:
                break
            if len(data) < self._size:
                break
            _sec, _usec, typ, code, value = struct.unpack(self._fmt, data)
            if typ == self.EV_ABS:
                if self._use_mt:
                    if code == self.ABS_MT_POSITION_X:
                        self._x = value
                    elif code == self.ABS_MT_POSITION_Y:
                        self._y = value
                else:
                    if code == self.ABS_X:
                        self._x = value
                    elif code == self.ABS_Y:
                        self._y = value
            elif typ == self.EV_KEY and code in (self.BTN_TOUCH, self.BTN_LEFT):
                self._touching = value != 0
                if value != 0 and self._x is not None and self._y is not None:
                    # Some devices omit BTN until after coords; mark down.
                    pass
            elif typ == self.EV_SYN and code == self.SYN_REPORT:
                got_report = True
                # Devices without BTN_TOUCH: treat presence of coords as contact.
                if not self._use_mt and self._x is not None and self._y is not None:
                    self._touching = True
        if (
            got_report
            and self._touching
            and self._x is not None
            and self._y is not None
        ):
            return (self.axis_x.normalize(self._x), self.axis_y.normalize(self._y))
        return None


# ---------------------------------------------------------------------------
# Persist measured matrix (keeps display transform unchanged / 270)
# ---------------------------------------------------------------------------


def _shell_quote(s: str) -> str:
    if "'" not in s:
        return f"'{s}'"
    return "'" + s.replace("'", "'\\''") + "'"


def _grab_env(text: str, key: str, default: str) -> str:
    m = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
    if not m:
        return default
    raw = m.group(1).strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1]
    return raw


def apply_calibration(
    *,
    matrix: str,
    device_name: str,
    display_env: Path,
    udev_path: Path,
    rc_xml: Path,
    transform: str = "270",
    output: str = "HDMI-A-1",
    measured_matrix: Optional[str] = None,
) -> None:
    """Write libinput/labwc touch calibration. ``matrix`` is what libinput loads.

    For transform 270, callers should pass the *composed* matrix
    (R_ccw90 ∘ measured) as ``matrix``, and optionally the bare empirical fit
    as ``measured_matrix`` for diagnostics. Display transform is never derived
    from the touch matrix.
    """
    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:apply_calibration",
        "apply started",
        {
            "matrix": matrix,
            "measured_matrix": measured_matrix,
            "device": device_name,
            "display_env": str(display_env),
            "udev": str(udev_path),
            "rc_xml": str(rc_xml),
            "transform": transform,
            "uid": os.geteuid(),
        },
    )
    # endregion

    # Display transform is independent of the measured touch matrix.
    # SellMate assembly orientation is 270°; CLI default matches that.
    output_val = output
    touch_val = device_name
    transform_val = transform if transform in {"90", "270", "180"} else "270"
    if display_env.is_file():
        text = display_env.read_text(encoding="utf-8")
        output_val = _grab_env(text, "SELLMATE_DISPLAY_OUTPUT", output)
        touch_val = _grab_env(text, "SELLMATE_TOUCH_DEVICE", device_name) or device_name

    display_env.parent.mkdir(parents=True, exist_ok=True)
    measured_line = ""
    if measured_matrix:
        measured_line = (
            f"SELLMATE_TOUCH_CALIBRATION_MATRIX_MEASURED="
            f"{_shell_quote(measured_matrix)}\n"
        )
    env_body = (
        "# Managed by calibrate_touch.py\n"
        "# Display transform is independent of the touch matrix (keep 270).\n"
        "# SELLMATE_TOUCH_CALIBRATION_MATRIX is libinput-facing "
        "(empirical fit composed with 90° CCW for transform 270).\n"
        f"SELLMATE_DISPLAY_OUTPUT={_shell_quote(output_val)}\n"
        f"SELLMATE_DISPLAY_TRANSFORM={_shell_quote(transform_val)}\n"
        f"SELLMATE_TOUCH_DEVICE={_shell_quote(touch_val)}\n"
        f"{measured_line}"
        f"SELLMATE_TOUCH_CALIBRATION_MATRIX={_shell_quote(matrix)}\n"
    )
    _write_text_flushed(display_env, env_body)
    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:apply_calibration",
        "file written",
        {
            "path": str(display_env),
            "bytes": len(env_body),
            "has_matrix_key": True,
            "transform": transform_val,
        },
    )
    # endregion

    udev_path.parent.mkdir(parents=True, exist_ok=True)
    udev_body = (
        "# Managed by calibrate_touch.py\n"
        f"# Display transform stays {transform_val}.\n"
        "# LIBINPUT_CALIBRATION_MATRIX = empirical fit ∘ 90° CCW correction "
        "(not a generic transform preset).\n"
        f'ACTION=="add|change", KERNEL=="event[0-9]*", '
        f'ENV{{ID_INPUT_TOUCHSCREEN}}=="1", ATTRS{{name}}=="{touch_val}", '
        f'ENV{{LIBINPUT_CALIBRATION_MATRIX}}="{matrix}"\n'
    )
    _write_text_flushed(udev_path, udev_body)
    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:apply_calibration",
        "file written",
        {"path": str(udev_path), "bytes": len(udev_body)},
    )
    # endregion

    _patch_rc_xml(rc_xml, output_val, touch_val, matrix)
    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:apply_calibration",
        "file written",
        {"path": str(rc_xml), "exists": rc_xml.is_file()},
    )
    # endregion
    os.system("udevadm control --reload-rules 2>/dev/null || true")
    os.system("udevadm trigger --subsystem-match=input --action=add 2>/dev/null || true")


def _write_text_flushed(path: Path, body: str) -> None:
    with path.open("w", encoding="utf-8") as fh:
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    # Verify read-back so permission/path errors surface immediately.
    read_back = path.read_text(encoding="utf-8")
    if read_back != body:
        raise IOError(f"write verification failed for {path}")


def _patch_rc_xml(rc_xml: Path, output: str, touch: str, matrix: str) -> None:
    begin = "<!-- BEGIN SELLMATE-PORTRAIT-DISPLAY -->"
    end = "<!-- END SELLMATE-PORTRAIT-DISPLAY -->"
    block = (
        f"{begin}\n"
        f'  <touch deviceName="" mapToOutput="{output}" mouseEmulation="yes" />\n'
        f'  <touch deviceName="{touch}" mapToOutput="{output}" mouseEmulation="yes" />\n'
        f"  <libinput>\n"
        f'    <device category="touch">\n'
        f"      <calibrationMatrix>{matrix}</calibrationMatrix>\n"
        f"    </device>\n"
        f'    <device category="{touch}">\n'
        f"      <calibrationMatrix>{matrix}</calibrationMatrix>\n"
        f"    </device>\n"
        f"  </libinput>\n"
        f"  {end}\n"
    )
    if rc_xml.is_file():
        text = rc_xml.read_text(encoding="utf-8")
        if begin in text and end in text:
            pre, rest = text.split(begin, 1)
            _, post = rest.split(end, 1)
            rc_xml.write_text(pre + block + post, encoding="utf-8")
            return
    rc_xml.parent.mkdir(parents=True, exist_ok=True)
    rc_xml.write_text(
        '<?xml version="1.0"?>\n'
        '<openbox_config xmlns="http://openbox.org/3.4/rc">\n'
        f"{block}"
        "</openbox_config>\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Qt UI
# ---------------------------------------------------------------------------

TARGETS = [
    ("top-left", 0.1, 0.1),
    ("top-right", 0.9, 0.1),
    ("bottom-left", 0.1, 0.9),
    ("bottom-right", 0.9, 0.9),
    ("center", 0.5, 0.5),
]


def run_ui(device_name: str) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
    from PySide6.QtCore import (
        Qt,
        QThread,
        Signal,
        Slot,
        QObject,
        QTimer,
        QEventLoop,
    )
    from PySide6.QtGui import QColor, QPainter, QPen, QFont
    from PySide6.QtWidgets import QApplication, QWidget

    touch = RawTouchDevice(device_name)
    raw_points: List[Tuple[float, float]] = []
    target_points: List[Tuple[float, float]] = []
    state = {
        "index": 0,
        "message": "Preparing…",
        "error": "",
        "finished": False,
        "exit_requested": False,
        "exec_returned": False,
    }

    app = QApplication.instance() or QApplication(sys.argv)
    # We own shutdown via QEventLoop.quit(); window close must not block exit.
    app.setQuitOnLastWindowClosed(False)
    loop = QEventLoop()
    thread = QThread()

    class CaptureWorker(QObject):
        sample = Signal(float, float)
        failed = Signal(str)
        request = Signal()

        def __init__(self) -> None:
            super().__init__()
            # request is emitted from the GUI thread; QueuedConnection runs
            # poll_sample on this worker's thread.
            self.request.connect(self.run_one, Qt.ConnectionType.QueuedConnection)

        @Slot()
        def run_one(self) -> None:
            if state["finished"] or state["exit_requested"]:
                return
            try:
                x, y = touch.poll_sample(timeout_s=90.0)
                if state["finished"] or state["exit_requested"]:
                    return
                self.sample.emit(x, y)
            except Exception as exc:  # noqa: BLE001
                if not state["exit_requested"]:
                    self.failed.emit(f"{type(exc).__name__}: {exc}")

    class UiController(QObject):
        """All UI/state mutations and loop.quit() must run on the GUI thread.

        Connecting worker signals to plain Python callables uses DirectConnection
        (no receiver QObject affinity), so on_sample previously ran on the
        worker thread and loop.quit() was a no-op / hang.
        """

        # Emitted from any thread; always delivered Queued to this object.
        _exit = Signal(str)

        def __init__(self) -> None:
            super().__init__()
            self._exit.connect(self._do_exit, Qt.ConnectionType.QueuedConnection)

        def request_app_exit(self, reason: str) -> None:
            # Marshal onto the GUI thread even if already there (queued), so
            # quit never runs mid-slot on a foreign thread.
            if QThread.currentThread() != self.thread():
                # region agent log
                _agent_log(
                    "H1",
                    "calibrate_touch.py:request_app_exit",
                    "marshaling exit onto GUI thread",
                    {
                        "reason": reason,
                        "on_main_thread": False,
                    },
                )
                # endregion
            self._exit.emit(reason)

        @Slot(str)
        def _do_exit(self, reason: str) -> None:
            if state["exit_requested"]:
                # region agent log
                _agent_log(
                    "H1",
                    "calibrate_touch.py:_do_exit",
                    "app exit requested (duplicate ignored)",
                    {
                        "reason": reason,
                        "on_main_thread": QThread.currentThread() == app.thread(),
                    },
                )
                # endregion
                return
            state["exit_requested"] = True
            state["finished"] = True
            # region agent log
            _agent_log(
                "H1",
                "calibrate_touch.py:_do_exit",
                "app exit requested",
                {
                    "reason": reason,
                    "index": state["index"],
                    "samples": len(raw_points),
                    "finished": state["finished"],
                    "on_main_thread": QThread.currentThread() == app.thread(),
                },
            )
            # endregion
            if QThread.currentThread() != app.thread():
                # region agent log
                _agent_log(
                    "H1",
                    "calibrate_touch.py:_do_exit",
                    "refusing loop.quit off GUI thread",
                    {"reason": reason},
                )
                # endregion
                return

            # region agent log
            _agent_log(
                "H1",
                "calibrate_touch.py:_do_exit",
                "calling loop.quit",
                {"reason": reason, "on_main_thread": True},
            )
            # endregion
            loop.quit()

            try:
                canvas.hide()
            except Exception:  # noqa: BLE001
                pass
            try:
                touch.close()
            except Exception:  # noqa: BLE001
                pass
            thread.quit()

            # region agent log
            _agent_log(
                "H1",
                "calibrate_touch.py:_do_exit",
                "loop.quit issued; returning to event loop",
                {"reason": reason},
            )
            # endregion

        @Slot()
        def start_capture(self) -> None:
            idx = state["index"]
            if state["exit_requested"]:
                return
            if idx >= len(TARGETS):
                state["finished"] = True
                state["message"] = "Done."
                canvas.update()
                # region agent log
                _agent_log(
                    "H5",
                    "calibrate_touch.py:start_capture",
                    "all targets complete; scheduling exit",
                    {
                        "index": idx,
                        "samples": len(raw_points),
                        "on_main_thread": QThread.currentThread() == app.thread(),
                    },
                )
                # endregion
                QTimer.singleShot(0, lambda: self.request_app_exit("normal_done"))
                QTimer.singleShot(3000, lambda: self.request_app_exit("failsafe_after_done"))
                return
            name, _nx, _ny = TARGETS[idx]
            state["message"] = f"Tap and release: {name}"
            canvas.update()
            worker.request.emit()

        @Slot(float, float)
        def on_sample(self, x: float, y: float) -> None:
            # region agent log
            _agent_log(
                "H1",
                "calibrate_touch.py:on_sample",
                "on_sample entered",
                {
                    "on_main_thread": QThread.currentThread() == app.thread(),
                    "index": state["index"],
                },
            )
            # endregion
            idx = state["index"]
            if idx >= len(TARGETS) or state["finished"] or state["exit_requested"]:
                # region agent log
                _agent_log(
                    "H2",
                    "calibrate_touch.py:on_sample",
                    "late sample ignored",
                    {"index": idx, "x": x, "y": y},
                )
                # endregion
                return
            name, nx, ny = TARGETS[idx]
            raw_points.append((x, y))
            target_points.append((nx, ny))
            state["message"] = f"Recorded {name}: raw=({x:.3f}, {y:.3f})"
            state["index"] = idx + 1
            canvas.update()
            # region agent log
            _agent_log(
                "H5",
                "calibrate_touch.py:on_sample",
                "final target accepted"
                if state["index"] >= len(TARGETS)
                else "target accepted",
                {
                    "name": name,
                    "raw": [x, y],
                    "target": [nx, ny],
                    "index_after": state["index"],
                    "samples": len(raw_points),
                    "on_main_thread": QThread.currentThread() == app.thread(),
                },
            )
            # endregion
            QTimer.singleShot(400, self.start_capture)

        @Slot(str)
        def on_failed(self, msg: str) -> None:
            if state["exit_requested"]:
                return
            state["error"] = msg
            state["finished"] = True
            canvas.update()
            # region agent log
            _agent_log(
                "H2",
                "calibrate_touch.py:on_failed",
                "capture failed",
                {
                    "error": msg,
                    "on_main_thread": QThread.currentThread() == app.thread(),
                },
            )
            # endregion
            QTimer.singleShot(0, lambda: self.request_app_exit("capture_failed"))

    class Canvas(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("SellMate Touch Calibration")
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self.showFullScreen()

        def closeEvent(self, event) -> None:  # noqa: N802
            event.accept()
            if not state["exit_requested"]:
                controller.request_app_exit("close_event")

        def paintEvent(self, _event) -> None:  # noqa: N802
            p = QPainter(self)
            p.fillRect(self.rect(), QColor("#111111"))
            w, h = max(1, self.width()), max(1, self.height())
            idx = state["index"]
            p.setPen(QColor("#EEEEEE"))
            p.setFont(QFont("DejaVu Sans", 22))
            p.drawText(
                40,
                56,
                f"SellMate touch calibration ({min(idx + 1, len(TARGETS))}/{len(TARGETS)})",
            )
            p.setFont(QFont("DejaVu Sans", 16))
            p.drawText(40, 90, "Display transform stays 270°. Tap each crosshair, then release.")
            p.drawText(40, 120, state["message"])
            if state["error"]:
                p.setPen(QColor("#FF6666"))
                p.drawText(40, 150, state["error"])

            if idx < len(TARGETS):
                name, nx, ny = TARGETS[idx]
                cx, cy = int(nx * w), int(ny * h)
                p.setPen(QPen(QColor("#A3E635"), 4))
                p.drawLine(cx - 48, cy, cx + 48, cy)
                p.drawLine(cx, cy - 48, cx, cy + 48)
                p.drawEllipse(cx - 14, cy - 14, 28, 28)
                p.setPen(QColor("#A3E635"))
                p.setFont(QFont("DejaVu Sans", 18, QFont.Weight.Bold))
                p.drawText(cx + 24, cy - 24, name)

        def keyPressEvent(self, event) -> None:  # noqa: N802
            if event.key() == Qt.Key.Key_Escape:
                state["error"] = "cancelled"
                state["finished"] = True
                controller.request_app_exit("escape")

    controller = UiController()  # affinity: GUI thread
    canvas = Canvas()
    worker = CaptureWorker()
    worker.moveToThread(thread)
    thread.start()

    # CRITICAL: QueuedConnection so slots run on controller's (GUI) thread.
    # Plain callables previously ran on the worker thread (DirectConnection).
    worker.sample.connect(controller.on_sample, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(controller.on_failed, Qt.ConnectionType.QueuedConnection)
    QTimer.singleShot(400, controller.start_capture)
    # region agent log
    _agent_log(
        "H1",
        "calibrate_touch.py:run_ui",
        "entering app.exec",
        {
            "device": device_name,
            "loop": "QEventLoop",
            "controller_thread_is_app": controller.thread() == app.thread(),
        },
    )
    # endregion
    loop.exec()
    state["exec_returned"] = True
    # region agent log
    _agent_log(
        "H1",
        "calibrate_touch.py:run_ui",
        "app.exec returned",
        {
            "exit_requested": state["exit_requested"],
            "finished": state["finished"],
            "samples": len(raw_points),
            "thread_running": thread.isRunning(),
        },
    )
    # endregion

    # Safe to tear down the window now that the UI loop has returned.
    try:
        canvas.hide()
        canvas.deleteLater()
        app.processEvents()
    except Exception:  # noqa: BLE001
        pass

    if not thread.wait(2000):
        # region agent log
        _agent_log(
            "H3",
            "calibrate_touch.py:run_ui",
            "worker thread did not quit; terminating",
            {},
        )
        # endregion
        thread.terminate()
        thread.wait(1000)
    else:
        # region agent log
        _agent_log(
            "H3",
            "calibrate_touch.py:run_ui",
            "worker thread quit cleanly",
            {},
        )
        # endregion

    if state["error"] == "cancelled":
        raise RuntimeError("calibration cancelled")
    if state["error"]:
        raise RuntimeError(state["error"])
    if len(raw_points) != len(TARGETS):
        raise RuntimeError(
            f"incomplete calibration: got {len(raw_points)}/{len(TARGETS)} samples"
        )
    return raw_points, target_points


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--device",
        default=os.environ.get("SELLMATE_TOUCH_DEVICE", "yldzkj USB2IIC_CTP_CONTROL"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--transform", default="270")
    parser.add_argument(
        "--output", default=os.environ.get("SELLMATE_DISPLAY_OUTPUT", "HDMI-A-1")
    )
    parser.add_argument("--display-env", default="/etc/sellmate/display.env")
    parser.add_argument(
        "--udev", default="/etc/udev/rules.d/99-sellmate-touch-portrait.rules"
    )
    parser.add_argument(
        "--rc-xml", default=os.path.expanduser("~/.config/labwc/rc.xml")
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Read JSON {raw,targets} from stdin and print matrix (tests)",
    )
    args = parser.parse_args(argv)

    if args.print_only:
        payload = json.load(sys.stdin)
        transform = str(payload.get("transform", "270"))
        coeffs = fit_affine(payload["raw"], payload["targets"])
        composed = libinput_matrix_for_display(coeffs, display_transform=transform)
        # stdout: libinput-facing matrix (composed). stderr: diagnostics.
        print(format_matrix(composed))
        print(
            f"measured={format_matrix(coeffs)} "
            f"rms={rms_error(coeffs, payload['raw'], payload['targets']):.6f} "
            f"transform={transform}",
            file=sys.stderr,
        )
        return 0

    print(f"Opening raw device for {args.device!r}…", flush=True)
    try:
        raw_pts, tgt_pts = run_ui(args.device)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        print("Add user to 'input' group or use sudo -E.", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Calibration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        # region agent log
        _agent_log(
            "H1",
            "calibrate_touch.py:main",
            "run_ui failed",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        # endregion
        return 1

    try:
        measured = fit_affine(raw_pts, tgt_pts)
        composed = libinput_matrix_for_display(
            measured, display_transform=args.transform
        )
        measured_s = format_matrix(measured)
        matrix = format_matrix(composed)
        err = rms_error(measured, raw_pts, tgt_pts)
    except Exception as exc:  # noqa: BLE001
        print(f"Matrix fit failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        # region agent log
        _agent_log(
            "H4",
            "calibrate_touch.py:main",
            "matrix fit failed",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        # endregion
        return 1

    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:main",
        "matrix fit completed",
        {
            "measured": measured_s,
            "libinput_composed": matrix,
            "rms": err,
            "raw": raw_pts,
            "targets": tgt_pts,
            "transform": args.transform,
        },
    )
    # endregion
    print("Measured raw points:", raw_pts, flush=True)
    print("Target points:      ", tgt_pts, flush=True)
    print("Measured matrix:    ", measured_s, flush=True)
    print("Libinput matrix:    ", matrix, flush=True)
    print(
        "(libinput = 90° CCW ∘ measured when transform is 270; display stays 270)",
        flush=True,
    )
    print(f"Fit RMS (normalized): {err:.6f}", flush=True)

    if not args.apply:
        print(
            f"Re-run with --apply to write configs (keeps transform {args.transform}).",
            flush=True,
        )
        return 0

    needs_root = str(args.display_env).startswith("/etc/") or str(args.udev).startswith(
        "/etc/"
    )
    if needs_root and os.geteuid() != 0:
        print("Writing /etc paths requires root (sudo -E … --apply).", file=sys.stderr)
        return 1

    try:
        apply_calibration(
            matrix=matrix,
            measured_matrix=measured_s,
            device_name=args.device,
            display_env=Path(args.display_env),
            udev_path=Path(args.udev),
            rc_xml=Path(args.rc_xml),
            transform=args.transform,
            output=args.output,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"APPLY FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        # region agent log
        _agent_log(
            "H4",
            "calibrate_touch.py:main",
            "apply failed",
            {"error": f"{type(exc).__name__}: {exc}"},
        )
        # endregion
        return 1

    print("Wrote:", flush=True)
    print(f"  {args.display_env}", flush=True)
    print(f"  {args.udev}", flush=True)
    print(f"  {args.rc_xml}", flush=True)
    print("Reboot (or restart the graphical session) so touch reloads.", flush=True)
    # region agent log
    _agent_log(
        "H4",
        "calibrate_touch.py:main",
        "apply succeeded; exiting 0",
        {"matrix": matrix},
    )
    # endregion
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

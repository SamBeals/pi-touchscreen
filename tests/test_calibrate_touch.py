from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALIBRATE = ROOT / "provisioning" / "display" / "calibrate_touch.py"


def _load_calibrate():
    spec = importlib.util.spec_from_file_location("calibrate_touch", CALIBRATE)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["calibrate_touch"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestFitAffine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_calibrate()

    def test_identity(self) -> None:
        raw = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)]
        coeffs = self.mod.fit_affine(raw, raw)
        self.assertAlmostEqual(coeffs[0], 1.0, places=5)
        self.assertAlmostEqual(coeffs[1], 0.0, places=5)
        self.assertAlmostEqual(coeffs[2], 0.0, places=5)
        self.assertAlmostEqual(coeffs[3], 0.0, places=5)
        self.assertAlmostEqual(coeffs[4], 1.0, places=5)
        self.assertAlmostEqual(coeffs[5], 0.0, places=5)
        self.assertLess(self.mod.rms_error(coeffs, raw, raw), 1e-6)

    def test_swap_xy_for_270_style(self) -> None:
        # Classic 270 CW: x' = y, y' = 1 - x  =>  a=0 b=1 c=0  d=-1 e=0 f=1
        targets = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)]
        raw = [(1.0 - ty, tx) for tx, ty in targets]
        coeffs = self.mod.fit_affine(raw, targets)
        expected = (0.0, 1.0, 0.0, -1.0, 0.0, 1.0)
        for got, want in zip(coeffs, expected):
            self.assertAlmostEqual(got, want, places=5)
        self.assertLess(self.mod.rms_error(coeffs, raw, targets), 1e-6)

    def test_controller_style_shear_scale(self) -> None:
        # Non-generic affine (what we expect from empirical controllers).
        a, b, c, d, e, f = (0.02, -0.97, 0.98, 1.03, 0.04, -0.01)
        targets = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)]
        raw = []
        for tx, ty in targets:
            x, y = tx, ty
            for _ in range(8):
                px = a * x + b * y + c
                py = d * x + e * y + f
                det = a * e - b * d
                self.assertGreater(abs(det), 1e-9)
                dx = ((e * (tx - px)) - (b * (ty - py))) / det
                dy = ((-d * (tx - px)) + (a * (ty - py))) / det
                x += dx
                y += dy
            raw.append((x, y))

        coeffs = self.mod.fit_affine(raw, targets)
        for got, want in zip(coeffs, (a, b, c, d, e, f)):
            self.assertAlmostEqual(got, want, places=4)
        self.assertLess(self.mod.rms_error(coeffs, raw, targets), 1e-4)

    def test_print_only_cli_emits_composed_for_270(self) -> None:
        payload = {
            "transform": "270",
            "raw": [[0.1, 0.9], [0.1, 0.1], [0.9, 0.9], [0.9, 0.1], [0.5, 0.5]],
            "targets": [[0.1, 0.1], [0.9, 0.1], [0.1, 0.9], [0.9, 0.9], [0.5, 0.5]],
        }
        result = subprocess.run(
            [sys.executable, str(CALIBRATE), "--print-only"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        composed = [float(x) for x in result.stdout.strip().split()]
        self.assertEqual(len(composed), 6)
        self.assertTrue(math.isfinite(sum(composed)))
        self.assertIn("measured=", result.stderr)
        self.assertIn("transform=270", result.stderr)
        # stdout must be composed, not the bare measured fit.
        measured_line = [
            part for part in result.stderr.split() if part.startswith("measured=")
        ][0]
        measured = [float(x) for x in measured_line.split("=", 1)[1].split()]
        self.assertNotEqual(composed, measured)

    def test_apply_writes_quoted_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = tmp_path / "display.env"
            udev = tmp_path / "udev.rules"
            rc = tmp_path / "rc.xml"
            matrix = "0.123456 -0.987654 1.000000 1.111111 0.000000 -0.050000"
            measured = "1.000000 0.000000 0.000000 0.000000 1.000000 0.000000"
            self.mod.apply_calibration(
                matrix=matrix,
                measured_matrix=measured,
                device_name="yldzkj USB2IIC_CTP_CONTROL",
                display_env=env,
                udev_path=udev,
                rc_xml=rc,
                transform="270",
                output="HDMI-A-1",
            )
            text = env.read_text(encoding="utf-8")
            self.assertIn("SELLMATE_DISPLAY_TRANSFORM='270'", text)
            self.assertIn("SELLMATE_TOUCH_DEVICE='yldzkj USB2IIC_CTP_CONTROL'", text)
            self.assertIn(f"SELLMATE_TOUCH_CALIBRATION_MATRIX='{matrix}'", text)
            self.assertIn(
                f"SELLMATE_TOUCH_CALIBRATION_MATRIX_MEASURED='{measured}'", text
            )
            udev_text = udev.read_text(encoding="utf-8")
            self.assertIn(f'ENV{{LIBINPUT_CALIBRATION_MATRIX}}="{matrix}"', udev_text)
            self.assertIn("yldzkj USB2IIC_CTP_CONTROL", udev_text)
            rc_text = rc.read_text(encoding="utf-8")
            self.assertIn(f"<calibrationMatrix>{matrix}</calibrationMatrix>", rc_text)
            self.assertIn('mapToOutput="HDMI-A-1"', rc_text)


class TestTouchDisplayComposition(unittest.TestCase):
    """Regression: transform 270 + empirical fit + 90° CCW libinput correction."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_calibrate()

    def test_compose_ccw90_left_multiplies(self) -> None:
        measured = (0.02, -0.97, 0.98, 1.03, 0.04, -0.01)
        composed = self.mod.libinput_matrix_for_display(
            measured, display_transform="270"
        )
        expected = self.mod.compose_affine(self.mod.ROTATE_CCW_90, measured)
        for got, want in zip(composed, expected):
            self.assertAlmostEqual(got, want, places=9)
        # Must not collapse to a generic 270 preset.
        generic_270 = (0.0, 1.0, 0.0, -1.0, 1.0, 0.0)
        self.assertFalse(
            all(abs(a - b) < 1e-6 for a, b in zip(composed, generic_270)),
            "composed matrix must retain the empirical fit, not a generic preset",
        )

    def test_display_transform_270_unchanged_by_composition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            measured = self.mod.fit_affine(
                [(0.2, 0.8), (0.8, 0.8), (0.2, 0.2), (0.8, 0.2), (0.5, 0.5)],
                [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)],
            )
            composed = self.mod.libinput_matrix_for_display(
                measured, display_transform="270"
            )
            self.mod.apply_calibration(
                matrix=self.mod.format_matrix(composed),
                measured_matrix=self.mod.format_matrix(measured),
                device_name="yldzkj USB2IIC_CTP_CONTROL",
                display_env=tmp_path / "display.env",
                udev_path=tmp_path / "udev.rules",
                rc_xml=tmp_path / "rc.xml",
                transform="270",
            )
            env = (tmp_path / "display.env").read_text(encoding="utf-8")
            self.assertIn("SELLMATE_DISPLAY_TRANSFORM='270'", env)
            self.assertNotIn("SELLMATE_DISPLAY_TRANSFORM='90'", env)

    def test_final_qt_coords_align_after_stack_model(self) -> None:
        """Bare measured matrix → 90° CW error at Qt; composed matrix cancels it."""
        targets = [(0.1, 0.1), (0.9, 0.1), (0.1, 0.9), (0.9, 0.9), (0.5, 0.5)]
        # Empirical controller-style mapping (not a generic preset).
        measured = (0.05, -0.95, 0.96, 0.98, 0.03, 0.01)
        raw = []
        for tx, ty in targets:
            x, y = tx, ty
            a, b, c, d, e, f = measured
            for _ in range(10):
                px, py = self.mod.apply_affine(measured, x, y)
                det = a * e - b * d
                dx = ((e * (tx - px)) - (b * (ty - py))) / det
                dy = ((-d * (tx - px)) + (a * (ty - py))) / det
                x += dx
                y += dy
            raw.append((x, y))

        fitted = self.mod.fit_affine(raw, targets)
        self.assertLess(self.mod.rms_error(fitted, raw, targets), 1e-4)

        # Without correction: Qt sees 90° CW of the visual target.
        for (rx, ry), (tx, ty) in zip(raw, targets):
            qx, qy = self.mod.simulate_touch_to_qt(
                fitted, rx, ry, stack_extra_cw90=True
            )
            want_cw = self.mod.apply_affine(self.mod.ROTATE_CW_90, tx, ty)
            self.assertAlmostEqual(qx, want_cw[0], places=4)
            self.assertAlmostEqual(qy, want_cw[1], places=4)

        composed = self.mod.libinput_matrix_for_display(
            fitted, display_transform="270"
        )
        # With correction: Qt coords match the visual targets.
        for (rx, ry), (tx, ty) in zip(raw, targets):
            qx, qy = self.mod.simulate_touch_to_qt(
                composed, rx, ry, stack_extra_cw90=True
            )
            self.assertAlmostEqual(qx, tx, places=4)
            self.assertAlmostEqual(qy, ty, places=4)

        # Composed libinput output alone is 90° CCW of the measured mapping.
        for rx, ry in raw:
            mx, my = self.mod.apply_affine(fitted, rx, ry)
            cx, cy = self.mod.apply_affine(composed, rx, ry)
            expect = self.mod.apply_affine(self.mod.ROTATE_CCW_90, mx, my)
            self.assertAlmostEqual(cx, expect[0], places=6)
            self.assertAlmostEqual(cy, expect[1], places=6)


if __name__ == "__main__":
    unittest.main()

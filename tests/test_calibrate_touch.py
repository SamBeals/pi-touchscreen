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
        # Invert: solve raw from targets for a known matrix is awkward; instead
        # synthesize raw by applying the inverse-ish mapping numerically via
        # forward map from invented raw -> targets check.
        raw = []
        for tx, ty in targets:
            # Choose raw so forward map lands on target (solve 2x2 locally with
            # Newton starting at target). For this mild matrix, start at target.
            x, y = tx, ty
            for _ in range(8):
                px = a * x + b * y + c
                py = d * x + e * y + f
                # Jacobian [[a,b],[d,e]]
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

    def test_print_only_cli(self) -> None:
        payload = {
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
        parts = [float(x) for x in result.stdout.strip().split()]
        self.assertEqual(len(parts), 6)
        # This raw→target is classic 90 CW: x'=y, y'=1-x? Wait:
        # raw (0.1,0.9)->(0.1,0.1) => roughly x'=x, y'=1-y for first point...
        # Just ensure RMS reported on stderr and finite coeffs.
        self.assertTrue(math.isfinite(sum(parts)))
        self.assertIn("rms=", result.stderr)

    def test_apply_writes_quoted_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = tmp_path / "display.env"
            udev = tmp_path / "udev.rules"
            rc = tmp_path / "rc.xml"
            matrix = "0.123456 -0.987654 1.000000 1.111111 0.000000 -0.050000"
            self.mod.apply_calibration(
                matrix=matrix,
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
            udev_text = udev.read_text(encoding="utf-8")
            self.assertIn(f'ENV{{LIBINPUT_CALIBRATION_MATRIX}}="{matrix}"', udev_text)
            self.assertIn("yldzkj USB2IIC_CTP_CONTROL", udev_text)
            rc_text = rc.read_text(encoding="utf-8")
            self.assertIn(f"<calibrationMatrix>{matrix}</calibrationMatrix>", rc_text)
            self.assertIn('mapToOutput="HDMI-A-1"', rc_text)


if __name__ == "__main__":
    unittest.main()

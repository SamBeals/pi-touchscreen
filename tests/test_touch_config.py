from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_TEST = ROOT / "tests" / "test_touch_config.sh"


class TestTouchConfig(unittest.TestCase):
    def test_labwc_touch_block_for_spaced_device(self) -> None:
        self.assertTrue(SHELL_TEST.is_file(), f"missing {SHELL_TEST}")
        result = subprocess.run(
            ["bash", str(SHELL_TEST)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            self.fail(
                "touch_config shell test failed\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )


if __name__ == "__main__":
    unittest.main()

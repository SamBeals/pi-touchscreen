from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import ConfigurationError, load_settings


class TestConfig(unittest.TestCase):
    def test_requires_machine_id(self):
        env = {k: v for k, v in os.environ.items() if k not in {"MACHINE_ID", "CLOUD_BASE"}}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                load_settings(load_machine_env_file=False)

    def test_requires_cloud_base(self):
        env = {k: v for k, v in os.environ.items() if k not in {"MACHINE_ID", "CLOUD_BASE"}}
        env["MACHINE_ID"] = "machine_002"
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigurationError):
                load_settings(load_machine_env_file=False)

    def test_loads_from_machine_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "machine.env"
            path.write_text(
                "MACHINE_ID=machine_002\n"
                "CLOUD_BASE=https://example.run.app\n",
                encoding="utf-8",
            )
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in {"MACHINE_ID", "CLOUD_BASE", "THEME_ID"}
            }
            with patch.dict(os.environ, env, clear=True):
                settings = load_settings(
                    machine_env_path=str(path), load_machine_env_file=True
                )
            self.assertEqual(settings.machine_id, "machine_002")
            self.assertEqual(settings.cloud_base, "https://example.run.app")
            self.assertEqual(settings.theme_id, "sellmate-default")

    def test_theme_id_from_env(self):
        env = {k: v for k, v in os.environ.items() if k not in {"THEME_ID"}}
        env["MACHINE_ID"] = "machine_002"
        env["CLOUD_BASE"] = "https://example.run.app"
        env["THEME_ID"] = "sellmate-light"
        with patch.dict(os.environ, env, clear=True):
            settings = load_settings(load_machine_env_file=False)
        self.assertEqual(settings.theme_id, "sellmate-light")
        self.assertEqual(settings.idle_timeout_seconds, 90.0)


if __name__ == "__main__":
    unittest.main()

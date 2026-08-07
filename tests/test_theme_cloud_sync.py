from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.theme.cloud_sync import (
    ActiveThemePointer,
    install_theme_zip,
    read_active_theme,
    resolve_boot_theme,
    write_active_theme,
)


def _minimal_theme_zip(theme_id: str = "acme-cafe") -> bytes:
    payload = {
        "schema_version": 1,
        "id": theme_id,
        "display_name": "Acme",
        "mode": "light",
        "brand": {"business_name": "Acme", "logo": ""},
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{theme_id}/theme.json", json.dumps(payload))
    return buf.getvalue()


class TestCloudSync(unittest.TestCase):
    def test_install_and_active_pointer(self):
        data = _minimal_theme_zip()
        sha = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            packages_dir = data_dir / "themes"
            install_theme_zip(
                zip_bytes=data,
                expected_sha256=sha,
                expected_theme_id="acme-cafe",
                packages_dir=packages_dir,
            )
            self.assertTrue((packages_dir / "acme-cafe" / "theme.json").is_file())
            pointer = ActiveThemePointer(
                theme_id="acme-cafe",
                package_id="acme-cafe-abc",
                revision=2,
                sha256=sha,
                packages_dir=str(packages_dir),
            )
            write_active_theme(data_dir, pointer)
            loaded = read_active_theme(data_dir)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.revision, 2)
            theme_id, pkgs = resolve_boot_theme(
                data_dir=data_dir,
                fallback_theme_id="sellmate-default",
                fallback_packages_dir=Path("/etc/sellmate/themes"),
            )
            self.assertEqual(theme_id, "acme-cafe")
            self.assertEqual(pkgs, packages_dir)


if __name__ == "__main__":
    unittest.main()

"""Download and install Cloud-desired theme packages onto the Pi.

Packages install under the touchscreen data dir (user-writable). An
``active_theme.json`` pointer selects the package on boot. After a
successful install the process exits non-zero so systemd Restart=on-failure
brings the UI back with the new theme.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.logging_setup import log_event
from app.theme.loader import load_theme

logger = logging.getLogger(__name__)

ACTIVE_THEME_FILENAME = "active_theme.json"


@dataclass(frozen=True)
class ActiveThemePointer:
    theme_id: str
    package_id: str
    revision: int
    sha256: str
    packages_dir: str


def active_theme_path(data_dir: Path) -> Path:
    return Path(data_dir) / ACTIVE_THEME_FILENAME


def cloud_packages_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "themes"


def read_active_theme(data_dir: Path) -> Optional[ActiveThemePointer]:
    path = active_theme_path(data_dir)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return ActiveThemePointer(
            theme_id=str(raw["theme_id"]),
            package_id=str(raw["package_id"]),
            revision=int(raw["revision"]),
            sha256=str(raw["sha256"]),
            packages_dir=str(raw.get("packages_dir") or cloud_packages_dir(data_dir)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def write_active_theme(data_dir: Path, pointer: ActiveThemePointer) -> None:
    path = active_theme_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "theme_id": pointer.theme_id,
        "package_id": pointer.package_id,
        "revision": pointer.revision,
        "sha256": pointer.sha256,
        "packages_dir": pointer.packages_dir,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def resolve_boot_theme(
    *,
    data_dir: Path,
    fallback_theme_id: str,
    fallback_packages_dir: Path,
) -> tuple[str, Path]:
    """Prefer Cloud-applied active theme when the package is present on disk."""
    active = read_active_theme(data_dir)
    if active is None:
        return fallback_theme_id, fallback_packages_dir
    packages_dir = Path(active.packages_dir)
    package_root = packages_dir / active.theme_id
    if (package_root / "theme.json").is_file():
        return active.theme_id, packages_dir
    log_event(
        logger,
        "theme.active_missing_package",
        theme_id=active.theme_id,
        package_id=active.package_id,
    )
    return fallback_theme_id, fallback_packages_dir


def _find_theme_root(extract_dir: Path) -> Path:
    direct = extract_dir / "theme.json"
    if direct.is_file():
        return extract_dir
    matches = sorted(extract_dir.glob("*/theme.json"))
    if len(matches) == 1:
        return matches[0].parent
    raise RuntimeError("theme.json not found after extract")


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise RuntimeError(f"unsafe zip path: {name}")
        target = dest / name
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)


def install_theme_zip(
    *,
    zip_bytes: bytes,
    expected_sha256: str,
    expected_theme_id: str,
    packages_dir: Path,
) -> Path:
    actual = hashlib.sha256(zip_bytes).hexdigest()
    if actual != expected_sha256:
        raise RuntimeError("theme zip sha256 mismatch")

    packages_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sellmate-theme-") as tmp:
        tmp_path = Path(tmp)
        extract_root = tmp_path / "extract"
        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            _safe_extract(zf, extract_root)

        theme_root = _find_theme_root(extract_root)
        # Normalize into packages_dir/<theme_id>/
        staging = packages_dir / f".{expected_theme_id}.staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for child in theme_root.iterdir():
            dest = staging / child.name
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)

        # Validate staging as if packages_dir pointed at parent of theme_id folder.
        # Place staging temporarily as packages_dir/<theme_id> via a temp packages root.
        temp_packages = tmp_path / "packages"
        temp_packages.mkdir()
        temp_pkg = temp_packages / expected_theme_id
        shutil.copytree(staging, temp_pkg)
        result = load_theme(expected_theme_id, packages_dir=temp_packages)
        if result.errors:
            raise RuntimeError("; ".join(result.errors))
        if result.theme.id != expected_theme_id:
            raise RuntimeError(
                f"theme id mismatch: expected {expected_theme_id}, got {result.theme.id}"
            )

        final_dir = packages_dir / expected_theme_id
        if final_dir.exists():
            backup = packages_dir / f".{expected_theme_id}.bak"
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(final_dir, backup)
            try:
                os.replace(staging, final_dir)
            except Exception:
                os.replace(backup, final_dir)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        else:
            os.replace(staging, final_dir)

        verify = load_theme(expected_theme_id, packages_dir=packages_dir)
        if verify.errors:
            raise RuntimeError("; ".join(verify.errors))
        return final_dir


def sync_desired_theme(
    *,
    cloud_client: Any,
    machine_token: str,
    data_dir: Path,
    local_active: Optional[ActiveThemePointer] = None,
) -> Optional[ActiveThemePointer]:
    """
    Poll Cloud for desired theme; download/install when revision differs.

    Returns the new active pointer when an install completed, else None.
    """
    status = cloud_client.get_machine_theme(machine_token=machine_token)
    desired = status.get("desired_theme") or {}
    if not desired:
        return None

    revision = int(desired["revision"])
    package_id = str(desired["package_id"])
    theme_id = str(desired["theme_id"])
    sha256 = str(desired["sha256"])

    active = local_active if local_active is not None else read_active_theme(data_dir)
    if (
        active
        and active.revision == revision
        and active.package_id == package_id
        and active.sha256 == sha256
    ):
        return None

    packages_dir = cloud_packages_dir(data_dir)
    zip_bytes = cloud_client.download_machine_theme_package(
        machine_token=machine_token
    )
    install_theme_zip(
        zip_bytes=zip_bytes,
        expected_sha256=sha256,
        expected_theme_id=theme_id,
        packages_dir=packages_dir,
    )
    pointer = ActiveThemePointer(
        theme_id=theme_id,
        package_id=package_id,
        revision=revision,
        sha256=sha256,
        packages_dir=str(packages_dir),
    )
    write_active_theme(data_dir, pointer)
    cloud_client.ack_machine_theme(
        machine_token=machine_token,
        revision=revision,
        status="APPLIED",
        package_id=package_id,
        theme_id=theme_id,
        sha256=sha256,
    )
    log_event(
        logger,
        "theme.sync_applied",
        theme_id=theme_id,
        package_id=package_id,
        revision=revision,
    )
    return pointer


def ack_theme_failed(
    *,
    cloud_client: Any,
    machine_token: str,
    desired: Dict[str, Any],
    error: str,
) -> None:
    try:
        cloud_client.ack_machine_theme(
            machine_token=machine_token,
            revision=int(desired.get("revision") or 0),
            status="FAILED",
            package_id=str(desired.get("package_id") or ""),
            theme_id=str(desired.get("theme_id") or ""),
            sha256=str(desired.get("sha256") or ""),
            error=error[:500],
        )
    except Exception:  # noqa: BLE001
        logger.exception("theme.ack_failed_error")

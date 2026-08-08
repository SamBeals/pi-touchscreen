"""
Environment-driven configuration for the Pi touchscreen.

MACHINE_ID and CLOUD_BASE are expected from /etc/sellmate/machine.env
(via systemd EnvironmentFile) — same identity as sellmate-poller/health.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


DEFAULT_MACHINE_ENV_PATH = "/etc/sellmate/machine.env"


def parse_env_file(text: str) -> dict[str, str]:
    """
    Parse KEY=VALUE env file contents.

    Supports blank lines, # comments, surrounding whitespace, and single/double
    quotes around values. Does not expand variables or execute shell syntax.
    """
    result: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key or any(ch.isspace() for ch in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        result[key] = value
    return result


def _load_env_file(path: str) -> None:
    """Load KEY=VALUE lines into os.environ if not already set (no override)."""
    env_path = Path(path)
    if not env_path.is_file():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for key, value in parse_env_file(text).items():
        if key not in os.environ:
            os.environ[key] = value


def _require_str(name: str) -> str:
    raw = os.environ.get(name)
    if raw is None:
        raise ConfigurationError(
            f"{name} is not set. Configure /etc/sellmate/machine.env "
            f"(see services/machine.env.example) and restart the service."
        )
    value = raw.strip()
    if not value:
        raise ConfigurationError(f"{name} is empty.")
    return value


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw.strip())


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    machine_id: str
    cloud_base: str
    idle_timeout_seconds: float
    poll_interval_seconds: float
    poll_max_attempts: int
    vend_wait_seconds: float
    inventory_max_age_seconds: float
    inventory_idle_refresh_seconds: float
    fullscreen: bool
    log_level: str
    data_dir: Path
    google_application_credentials: Optional[str]
    firestore_project_id: Optional[str]
    inventory_fixture_path: Optional[str]
    theme_id: str
    theme_packages_dir: Path
    machine_shared_token: Optional[str]
    theme_sync_enabled: bool
    theme_poll_seconds: float

    @property
    def active_order_path(self) -> Path:
        return self.data_dir / "active_order.json"

    @property
    def inventory_cache_path(self) -> Path:
        return self.data_dir / "inventory_cache.json"


def load_settings(
    *,
    machine_env_path: Optional[str] = None,
    load_machine_env_file: bool = True,
) -> Settings:
    if load_machine_env_file:
        path = machine_env_path or os.environ.get(
            "SELLMATE_MACHINE_ENV", DEFAULT_MACHINE_ENV_PATH
        )
        _load_env_file(path)
        touchscreen_env = os.environ.get(
            "SELLMATE_TOUCHSCREEN_ENV", "/etc/sellmate/touchscreen.env"
        )
        _load_env_file(touchscreen_env)

    machine_id = _require_str("MACHINE_ID")
    cloud_base = os.environ.get("CLOUD_BASE", "").strip().rstrip("/")
    if not cloud_base:
        raise ConfigurationError(
            "CLOUD_BASE is not set. Add it to /etc/sellmate/machine.env."
        )

    data_dir = Path(
        os.environ.get(
            "TOUCHSCREEN_DATA_DIR",
            str(Path.home() / ".local" / "share" / "sellmate-touchscreen"),
        )
    ).expanduser()

    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip() or None
    project = os.environ.get("FIRESTORE_PROJECT_ID", "").strip() or None
    fixture = os.environ.get("INVENTORY_FIXTURE_PATH", "").strip() or None
    theme_id = os.environ.get("THEME_ID", "sellmate-default").strip() or "sellmate-default"
    theme_packages_dir = Path(
        os.environ.get("THEME_PACKAGES_DIR", "/etc/sellmate/themes")
    ).expanduser()
    machine_token = os.environ.get("MACHINE_SHARED_TOKEN", "").strip() or None

    return Settings(
        machine_id=machine_id,
        cloud_base=cloud_base,
        idle_timeout_seconds=_float_env("IDLE_TIMEOUT_SECONDS", 90.0),
        poll_interval_seconds=_float_env("POLL_INTERVAL_SECONDS", 2.0),
        # Cover card wait + VEND_WAIT_SECONDS + post-409 vend settle.
        poll_max_attempts=_int_env("POLL_MAX_ATTEMPTS", 120),
        vend_wait_seconds=_float_env("VEND_WAIT_SECONDS", 60.0),
        inventory_max_age_seconds=_float_env("INVENTORY_MAX_AGE_SECONDS", 300.0),
        inventory_idle_refresh_seconds=_float_env(
            "INVENTORY_IDLE_REFRESH_SECONDS", 120.0
        ),
        fullscreen=_bool_env("FULLSCREEN", True),
        log_level=os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        data_dir=data_dir,
        google_application_credentials=creds,
        firestore_project_id=project,
        inventory_fixture_path=fixture,
        theme_id=theme_id,
        theme_packages_dir=theme_packages_dir,
        machine_shared_token=machine_token,
        theme_sync_enabled=_bool_env("THEME_SYNC_ENABLED", True),
        theme_poll_seconds=_float_env("THEME_POLL_SECONDS", 60.0),
    )

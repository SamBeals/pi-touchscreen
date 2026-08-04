#!/usr/bin/env python3
"""
Headless UI smoke test for QML kiosk screens.

Usage (from repo root, with deps installed):
  FULLSCREEN=false \\
  INVENTORY_FIXTURE_PATH=$PWD/fixtures/inventory.json \\
  MACHINE_ID=machine_001 \\
  CLOUD_BASE=https://example.test \\
  THEME_ID=sellmate-default \\
  QT_QPA_PLATFORM=offscreen \\
  python scripts/smoke_ui.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("FULLSCREEN", "false")
os.environ.setdefault("MACHINE_ID", "machine_001")
os.environ.setdefault("CLOUD_BASE", "https://example.test")
os.environ.setdefault("THEME_ID", "sellmate-default")
os.environ.setdefault(
    "INVENTORY_FIXTURE_PATH", str(ROOT / "fixtures" / "inventory.json")
)


def main() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QGuiApplication
    except ImportError as exc:
        print(f"SKIP: PySide6 not installed ({exc})", file=sys.stderr)
        return 2

    from app.config import load_settings
    from app.state.app_state import AppScreen
    from app.ui.qml_host import QmlHost

    app = QGuiApplication(sys.argv)
    settings = load_settings(load_machine_env_file=False)
    host = QmlHost(settings)
    ctrl = host.controller

    errors: list[str] = []
    step = {"n": 0}

    def fail(msg: str) -> None:
        errors.append(msg)
        app.quit()

    def advance() -> None:
        step["n"] += 1
        n = step["n"]
        try:
            if n == 1:
                if ctrl.fsm.screen == AppScreen.BOOT:
                    QTimer.singleShot(200, advance)
                    return
                if ctrl.fsm.screen == AppScreen.FATAL:
                    fail(f"Boot fatal: {ctrl.fsm.fatal_reason}")
                    return
                if ctrl.fsm.screen not in {AppScreen.ATTRACT, AppScreen.PAYMENT}:
                    fail(f"Expected Attract after boot, got {ctrl.fsm.screen}")
                    return
                print("OK boot ->", ctrl.fsm.screen.value)
                print("OK theme ->", ctrl.theme.id)
                if ctrl.fsm.screen == AppScreen.ATTRACT:
                    ctrl.enterBrowse()
                QTimer.singleShot(50, advance)
            elif n == 2:
                if ctrl.fsm.screen != AppScreen.BROWSE:
                    fail(f"Expected Browse, got {ctrl.fsm.screen}")
                    return
                sellable = ctrl.snapshot.sellable() if ctrl.snapshot else []
                print("OK browse products=", len(sellable))
                if not sellable:
                    fail("No sellable products from fixture")
                    return
                ctrl.openDetail(sellable[0].slot_id)
                QTimer.singleShot(50, advance)
            elif n == 3:
                if ctrl.fsm.screen != AppScreen.PRODUCT_DETAIL:
                    fail(f"Expected Detail, got {ctrl.fsm.screen}")
                    return
                print("OK detail")
                ctrl.detailAdd()
                QTimer.singleShot(50, advance)
            elif n == 4:
                if ctrl.fsm.screen != AppScreen.BROWSE:
                    fail(f"Expected Browse after add, got {ctrl.fsm.screen}")
                    return
                ctrl.openCart()
                QTimer.singleShot(50, advance)
            elif n == 5:
                if ctrl.fsm.screen != AppScreen.CART:
                    fail(f"Expected Cart, got {ctrl.fsm.screen}")
                    return
                print("OK cart total_cents=", ctrl.cart.total_cents())
                print("OK checkoutEnabled=", ctrl.checkoutEnabled)
                host.shutdown()
                app.quit()
        except Exception as exc:  # noqa: BLE001
            fail(f"Exception during smoke: {type(exc).__name__}: {exc}")

    QTimer.singleShot(100, advance)
    code = app.exec()
    if errors:
        for err in errors:
            print("FAIL:", err, file=sys.stderr)
        return 1
    print("SMOKE PASS")
    return code


if __name__ == "__main__":
    raise SystemExit(main())

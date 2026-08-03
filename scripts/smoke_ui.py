#!/usr/bin/env python3
"""
Headless UI smoke test for Milestone 1 screens.

Usage (from repo root, with deps installed):
  FULLSCREEN=false \\
  INVENTORY_FIXTURE_PATH=$PWD/fixtures/inventory.json \\
  MACHINE_ID=machine_001 \\
  CLOUD_BASE=https://example.test \\
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
os.environ.setdefault(
    "INVENTORY_FIXTURE_PATH", str(ROOT / "fixtures" / "inventory.json")
)


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
    except ImportError as exc:
        print(f"SKIP: PySide6 not installed ({exc})", file=sys.stderr)
        return 2

    from app.config import load_settings
    from app.state.app_state import AppScreen
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    settings = load_settings(load_machine_env_file=False)
    window = MainWindow(settings)
    window.show()

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
                # Allow bootstrap workers to finish
                if window.fsm.screen == AppScreen.BOOT:
                    QTimer.singleShot(200, advance)
                    return
                if window.fsm.screen == AppScreen.FATAL:
                    fail(f"Boot fatal: {window.fsm.fatal_reason}")
                    return
                if window.fsm.screen not in {AppScreen.ATTRACT, AppScreen.PAYMENT}:
                    fail(f"Expected Attract after boot, got {window.fsm.screen}")
                    return
                print("OK boot ->", window.fsm.screen.value)
                if window.fsm.screen == AppScreen.ATTRACT:
                    window._enter_browse()
                QTimer.singleShot(50, advance)
            elif n == 2:
                if window.fsm.screen != AppScreen.BROWSE:
                    fail(f"Expected Browse, got {window.fsm.screen}")
                    return
                print("OK browse products=", len(window.snapshot.sellable() if window.snapshot else []))
                sellable = window.snapshot.sellable() if window.snapshot else []
                if not sellable:
                    fail("No sellable products from fixture")
                    return
                window._open_detail(sellable[0].slot_id)
                QTimer.singleShot(50, advance)
            elif n == 3:
                if window.fsm.screen != AppScreen.PRODUCT_DETAIL:
                    fail(f"Expected Detail, got {window.fsm.screen}")
                    return
                print("OK detail")
                window._detail_add()
                QTimer.singleShot(50, advance)
            elif n == 4:
                if window.fsm.screen != AppScreen.BROWSE:
                    fail(f"Expected Browse after add, got {window.fsm.screen}")
                    return
                window._open_cart()
                QTimer.singleShot(50, advance)
            elif n == 5:
                if window.fsm.screen != AppScreen.CART:
                    fail(f"Expected Cart, got {window.fsm.screen}")
                    return
                print("OK cart total_cents=", window.cart.total_cents())
                # Checkout entry path: gate may block without cloud; ensure button path exists
                if not hasattr(window, "cart_checkout_btn"):
                    fail("Missing checkout button")
                    return
                print("OK checkout entry control present enabled=", window.cart_checkout_btn.isEnabled())
                window.close()
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

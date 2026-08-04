"""python -m app"""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QGuiApplication

from app.config import ConfigurationError, load_settings
from app.logging_setup import log_event, setup_logging
from app.ui.qml_host import QmlHost

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    setup_logging(settings.log_level)
    log_event(
        logger,
        "app.start",
        machine_id=settings.machine_id,
        theme_id=settings.theme_id,
    )

    app = QGuiApplication(argv)
    app.setApplicationName("SellMate Touchscreen")
    host = QmlHost(settings)
    app.aboutToQuit.connect(host.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

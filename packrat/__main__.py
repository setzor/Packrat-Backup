"""Entry point for ``python -m packrat`` and the ``packrat`` GUI script."""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="packrat",
        description="Packrat Backup - restic-based backups for KDE Plasma",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="start minimised to the system tray",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="verbose logging to stderr",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication
    from importlib.resources import files

    from . import APP_ID, APP_NAME, __version__
    from .main import MainWindow
    from .settings import Settings

    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(
        QIcon(str(files("packrat").joinpath("assets", "packrat-mascot.svg")))
    )
    app.setQuitOnLastWindowClosed(False)

    settings = Settings()
    window = MainWindow(settings)
    if not args.tray:
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

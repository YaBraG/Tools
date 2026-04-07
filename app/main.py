from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _validate_environment() -> None:
    if sys.version_info < (3, 12):
        raise SystemExit("Tools requires Python 3.12 or newer.")

    if platform.system() != "Windows":
        raise SystemExit("Tools is currently supported on Windows only.")


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="Launch the Tools desktop application."
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Start the app briefly, then exit. Useful for automated checks.",
    )
    return parser.parse_known_args(argv)


def run(argv: list[str] | None = None) -> int:
    _validate_environment()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.metadata import APP_NAME
    from app.ui.main_window import MainWindow
    from app.ui.styles import APP_STYLESHEET

    args, qt_args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    application = QApplication([sys.argv[0], *qt_args])
    application.setApplicationName(APP_NAME)
    application.setOrganizationName(APP_NAME)
    application.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()

    if args.smoke_test:
        QTimer.singleShot(250, application.quit)

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(run())

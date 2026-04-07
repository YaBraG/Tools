from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_HOME_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else PROJECT_ROOT_DIR
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT_DIR))

ROOT_DIR = APP_HOME_DIR
APP_DIR = RESOURCE_DIR / "app"
ASSETS_DIR = RESOURCE_DIR / "assets"
DOCS_DIR = RESOURCE_DIR / "docs"
TOOLS_DIR = RESOURCE_DIR / "tools"

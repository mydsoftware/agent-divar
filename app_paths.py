# -*- coding: utf-8 -*-
"""مسیرهای سازگار با اجرای توسعه‌ای و نسخه بسته‌بندی‌شده ویندوز."""
from __future__ import annotations

import os
import sys
from pathlib import Path

IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

if IS_FROZEN:
    APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AgentDivar"
    EXECUTABLE_DIR = Path(sys.executable).resolve().parent
    PLAYWRIGHT_BROWSERS_DIR = EXECUTABLE_DIR / "ms-playwright"
    if PLAYWRIGHT_BROWSERS_DIR.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(PLAYWRIGHT_BROWSERS_DIR))
else:
    APP_DATA_DIR = Path(__file__).resolve().parent
    EXECUTABLE_DIR = APP_DATA_DIR
    PLAYWRIGHT_BROWSERS_DIR = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")) if os.environ.get("PLAYWRIGHT_BROWSERS_PATH") else None

DATA_DIR = APP_DATA_DIR / "data"
DATABASE_PATH = DATA_DIR / "leads.sqlite3"
SETTINGS_PATH = DATA_DIR / "settings.json"
BROWSER_PROFILE_PATH = DATA_DIR / "browser-profile"
BROWSER_STATUS_PATH = DATA_DIR / "browser-session.json"
MEDIA_PATH = DATA_DIR / "property-media"


def ensure_data_dirs() -> None:
    """ساخت مسیرهای نوشتنی مورد نیاز برنامه."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_PATH.mkdir(parents=True, exist_ok=True)

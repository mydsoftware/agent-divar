# -*- coding: utf-8 -*-
"""مسیرهای داده و مهاجرت امن داده‌های نسخه قدیمی به پوشه کاربر."""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
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


def _copy_file_if_missing(source: Path, destination: Path) -> bool:
    """کپی اتمی فایل بدون بازنویسی داده‌ای که قبلاً در مقصد وجود دارد."""
    if destination.exists() or not source.is_file() or source.is_symlink():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".migration", dir=str(destination.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        if destination.exists():
            return False
        os.replace(temporary, destination)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _copy_database_if_missing(source: Path, destination: Path) -> bool:
    """کپی snapshot سازگار SQLite و بررسی سلامت قبل از انتشار فایل."""
    if destination.exists() or not source.is_file():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".migration", dir=str(destination.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        source_db = sqlite3.connect(str(source), timeout=15)
        target_db = sqlite3.connect(str(temporary), timeout=15)
        try:
            source_db.backup(target_db)
            integrity = target_db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError("سلامت پایگاه‌داده قدیمی تأیید نشد؛ فایل اصلی دست‌نخورده ماند.")
        finally:
            target_db.close()
            source_db.close()
        if destination.exists():
            return False
        os.replace(temporary, destination)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def migrate_legacy_data(source_data_dir: str | Path,
                        destination_data_dir: str | Path) -> dict:
    """داده‌های قدیمی را بدون حذف یا بازنویسی داده مقصد منتقل/کپی می‌کند."""
    source = Path(source_data_dir).expanduser().resolve()
    destination = Path(destination_data_dir).expanduser().resolve()
    if source == destination or not source.is_dir():
        return {"copied_files": [], "skipped": [], "source": str(source)}

    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    skipped = []

    database = source / "leads.sqlite3"
    if database.exists():
        if _copy_database_if_missing(database, destination / database.name):
            copied.append(database.name)
        else:
            skipped.append(database.name)

    for name in ("settings.json", "browser-session.json"):
        old_file = source / name
        if old_file.exists():
            if _copy_file_if_missing(old_file, destination / name):
                copied.append(name)
            else:
                skipped.append(name)

    for name in ("property-media", "browser-profile"):
        old_directory = source / name
        if not old_directory.is_dir() or old_directory.is_symlink():
            continue
        for item in sorted(old_directory.rglob("*")):
            if item.is_symlink():
                skipped.append(str(item.relative_to(source)))
                continue
            if not item.is_file():
                continue
            relative = item.relative_to(source)
            if _copy_file_if_missing(item, destination / relative):
                copied.append(relative.as_posix())
            else:
                skipped.append(relative.as_posix())

    return {"copied_files": copied, "skipped": skipped, "source": str(source)}


def ensure_data_dirs() -> None:
    """ساخت مسیرهای نوشتنی و مهاجرت یک‌باره و غیرمخرب در نسخه اجرایی."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_PATH.mkdir(parents=True, exist_ok=True)
    if IS_FROZEN:
        migrate_legacy_data(EXECUTABLE_DIR / "data", DATA_DIR)

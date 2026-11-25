# -*- coding: utf-8 -*-
"""ساخت بسته عیب‌یابی محلی بدون درج اطلاعات شناسایی مشتریان."""
from __future__ import annotations

import json
import platform
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

APP_VERSION = "1.0.0"


def create_diagnostics_bundle(db_path: str | Path, destination: str | Path) -> Path:
    db = Path(db_path)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "app_version": APP_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database_exists": db.is_file(),
        "database_schema_version": None,
        "database_integrity": "not_checked",
        "event_counts": {},
    }
    if db.is_file():
        con = sqlite3.connect(str(db), timeout=5)
        try:
            report["database_schema_version"] = con.execute("PRAGMA user_version").fetchone()[0]
            report["database_integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0]
            try:
                rows = con.execute(
                    "SELECT event_type, COUNT(*) FROM event_logs GROUP BY event_type"
                ).fetchall()
                report["event_counts"] = {str(kind): count for kind, count in rows}
            except sqlite3.Error:
                report["event_counts"] = {}
        except sqlite3.Error as exc:
            report["database_integrity"] = "error: " + type(exc).__name__
        finally:
            con.close()
    # عمداً هیچ نام، شماره تماس، عنوان آگهی، یادداشت یا مسیر فایل کاربر صادر نمی‌شود.
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json",
                                     delete=False) as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        temp_report = Path(stream.name)
    try:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_report, "diagnostics.json")
    finally:
        temp_report.unlink(missing_ok=True)
    return target

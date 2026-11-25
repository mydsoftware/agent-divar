# -*- coding: utf-8 -*-
"""مدیریت تنظیمات محلی و اعتبارسنجی‌شده برنامه."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_SETTINGS = {
    "theme": "clam",
    "font_size": 10,
    "export_directory": "",
    "diagnostics_enabled": True,
}
ALLOWED_THEMES = {"clam", "default", "alt", "classic"}


def validate_settings(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("ساختار تنظیمات نامعتبر است.")
    result = dict(DEFAULT_SETTINGS)
    theme = value.get("theme", result["theme"])
    if theme not in ALLOWED_THEMES:
        raise ValueError("قالب نمایشی نامعتبر است.")
    size = value.get("font_size", result["font_size"])
    if isinstance(size, bool) or not isinstance(size, int) or not 8 <= size <= 16:
        raise ValueError("اندازه قلم باید عدد صحیح بین ۸ تا ۱۶ باشد.")
    export_dir = value.get("export_directory", result["export_directory"])
    if not isinstance(export_dir, str) or len(export_dir) > 2048:
        raise ValueError("مسیر خروجی نامعتبر است.")
    diagnostics = value.get("diagnostics_enabled", result["diagnostics_enabled"])
    if not isinstance(diagnostics, bool):
        raise ValueError("وضعیت گزارش عیب‌یابی نامعتبر است.")
    result.update(theme=theme, font_size=size, export_directory=export_dir,
                  diagnostics_enabled=diagnostics)
    return result


def load_settings(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        return validate_settings(json.loads(target.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return dict(DEFAULT_SETTINGS)


def save_settings(path: str | Path, settings: dict) -> dict:
    target = Path(path)
    clean = validate_settings(settings)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp",
                                     dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\\n") as stream:
            json.dump(clean, stream, ensure_ascii=False, indent=2)
            stream.write("\\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return clean

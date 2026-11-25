# -*- coding: utf-8 -*-
"""مدیریت محلی و امن تصاویر و مدارک مرتبط با آگهی‌ها."""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Iterable

from storage import connect, record_event

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024
CATEGORIES = ("نما", "پذیرایی", "اتاق", "آشپزخانه", "سند و مدارک", "سایر")


class MediaValidationError(ValueError):
    """خطای اعتبارسنجی فایل رسانه‌ای."""


def _safe_root(root: str | Path) -> Path:
    path = Path(root).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_source(source: str | Path) -> tuple[Path, str, int]:
    path = Path(source).expanduser().resolve(strict=True)
    if not path.is_file():
        raise MediaValidationError("مسیر انتخاب‌شده فایل نیست.")
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise MediaValidationError("فرمت فایل مجاز نیست.")
    size = path.stat().st_size
    if size <= 0 or size > MAX_FILE_SIZE:
        raise MediaValidationError("حجم فایل باید بین 1 بایت تا 20 مگابایت باشد.")
    if suffix in IMAGE_EXTENSIONS:
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
        except ImportError:
            pass
        except Exception as exc:
            raise MediaValidationError("فایل تصویر معتبر نیست.") from exc
    return path, suffix, size


def add_media(db_path: str | Path, storage_root: str | Path, *, lead_id: int,
              source_path: str | Path, category: str = "سایر",
              description: str = "", is_primary: bool = False) -> int:
    """کپی امن فایل در فضای برنامه و ثبت metadata؛ فایل اصلی دست‌نخورده می‌ماند."""
    if category not in CATEGORIES:
        raise MediaValidationError("دسته‌بندی فایل نامعتبر است.")
    source, suffix, size = _validate_source(source_path)
    root = _safe_root(storage_root)
    with connect(db_path) as con:
        if not con.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,)).fetchone():
            raise ValueError("آگهی انتخاب‌شده وجود ندارد.")
        existing = con.execute(
            "SELECT id FROM property_media WHERE lead_id=? AND sha256=?",
            (lead_id, hashlib.sha256(source.read_bytes()).hexdigest()),
        ).fetchone()
        if existing:
            raise MediaValidationError("این فایل قبلاً برای همین آگهی ثبت شده است.")
        media_id = uuid.uuid4().hex
        relative = Path(str(lead_id)) / (media_id + suffix)
        destination = (root / relative).resolve()
        if root not in destination.parents:
            raise MediaValidationError("مسیر مقصد نامعتبر است.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        try:
            if is_primary:
                con.execute("UPDATE property_media SET is_primary=0 WHERE lead_id=?", (lead_id,))
            cur = con.execute(
                """INSERT INTO property_media
                (lead_id, stored_path, original_name, category, description, mime_type,
                 file_size, sha256, is_primary)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (lead_id, relative.as_posix(), source.name, category, description.strip(),
                 mimetypes.guess_type(source.name)[0] or "application/octet-stream",
                 size, digest, int(is_primary)),
            )
            row_id = int(cur.lastrowid)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    record_event(db_path, "media.added", entity_type="lead", entity_id=lead_id,
                 message="فایل رسانه‌ای به پرونده آگهی افزوده شد",
                 details={"media_id": row_id, "category": category})
    return row_id


def list_media(db_path: str | Path, *, lead_id: int) -> list[dict]:
    with connect(db_path) as con:
        rows = con.execute(
            """SELECT id,lead_id,stored_path,original_name,category,description,
                      mime_type,file_size,sha256,is_primary,created_at
               FROM property_media WHERE lead_id=?
               ORDER BY is_primary DESC, id DESC""", (lead_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def resolve_media_path(storage_root: str | Path, stored_path: str) -> Path:
    """تبدیل مسیر نسبی metadata به مسیر مطمئن داخل پوشه رسانه."""
    root = Path(storage_root).expanduser().resolve()
    candidate = (root / stored_path).resolve()
    if candidate == root or root not in candidate.parents:
        raise MediaValidationError("مسیر ذخیره‌شده از محدوده پوشه رسانه خارج است.")
    return candidate


def set_primary(db_path: str | Path, *, lead_id: int, media_id: int) -> None:
    with connect(db_path) as con:
        exists = con.execute(
            "SELECT 1 FROM property_media WHERE id=? AND lead_id=?", (media_id, lead_id)
        ).fetchone()
        if not exists:
            raise ValueError("فایل متعلق به این آگهی نیست.")
        con.execute("UPDATE property_media SET is_primary=0 WHERE lead_id=?", (lead_id,))
        con.execute("UPDATE property_media SET is_primary=1 WHERE id=?", (media_id,))


def delete_media(db_path: str | Path, storage_root: str | Path, *, media_id: int) -> None:
    with connect(db_path) as con:
        row = con.execute("SELECT lead_id,stored_path FROM property_media WHERE id=?",
                          (media_id,)).fetchone()
        if row is None:
            raise ValueError("فایل پیدا نشد.")
        path = resolve_media_path(storage_root, row["stored_path"])
        con.execute("DELETE FROM property_media WHERE id=?", (media_id,))
    path.unlink(missing_ok=True)
    record_event(db_path, "media.deleted", entity_type="lead", entity_id=row["lead_id"],
                 message="فایل رسانه‌ای حذف شد", details={"media_id": media_id})


def audit_media(db_path: str | Path, storage_root: str | Path) -> dict:
    """گزارش فایل‌های مفقود و فایل‌های بدون metadata؛ بدون حذف خودکار."""
    root = _safe_root(storage_root)
    with connect(db_path) as con:
        rows = con.execute("SELECT id,stored_path FROM property_media").fetchall()
    known = set()
    missing = []
    for row in rows:
        path = resolve_media_path(root, row["stored_path"])
        known.add(path)
        if not path.is_file():
            missing.append(row["id"])
    orphans = [p.relative_to(root).as_posix() for p in root.rglob("*")
               if p.is_file() and p.resolve() not in known]
    return {"missing_ids": missing, "orphan_paths": sorted(orphans)}

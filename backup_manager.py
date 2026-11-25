# -*- coding: utf-8 -*-
"""پشتیبان‌گیری و بازیابی یکپارچه پایگاه داده و رسانه‌های محلی."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

FORMAT_VERSION = 1
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024


class BackupError(ValueError):
    """خطای اعتبارسنجی یا عملیات پشتیبان."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(db_path: str | Path, media_root: str | Path,
                  destination: str | Path) -> Path:
    """ساخت فایل ZIP شامل snapshot سازگار SQLite، رسانه‌ها و manifest."""
    db = Path(db_path).expanduser().resolve(strict=True)
    media = Path(media_root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BackupError("فایل مقصد از قبل وجود دارد.")
    with tempfile.TemporaryDirectory(prefix="agent-divar-backup-") as tmp:
        temp = Path(tmp)
        snapshot = temp / "database.sqlite3"
        source = sqlite3.connect(str(db))
        output = sqlite3.connect(str(snapshot))
        try:
            source.backup(output)
            check = output.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise BackupError("سلامت snapshot پایگاه داده تأیید نشد.")
        finally:
            output.close()
            source.close()
        entries = []
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "database.sqlite3")
            if media.exists():
                for item in sorted(media.rglob("*")):
                    if item.is_symlink():
                        raise BackupError("وجود پیوند نمادین در پوشه رسانه مجاز نیست.")
                    if item.is_file():
                        rel = item.relative_to(media).as_posix()
                        entries.append({"path": rel, "size": item.stat().st_size,
                                        "sha256": _sha256(item)})
                        archive.write(item, "media/" + rel)
            manifest = {"format_version": FORMAT_VERSION,
                        "created_at": datetime.now().astimezone().isoformat(),
                        "database_sha256": _sha256(snapshot),
                        "media": entries}
            archive.writestr("manifest.json",
                             json.dumps(manifest, ensure_ascii=False, indent=2))
    return target


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise BackupError("مسیر نامعتبر در فایل پشتیبان شناسایی شد.")
    if "\\" in name or (len(name) > 1 and name[1] == ":"):
        raise BackupError("مسیر ویندوزی نامعتبر در فایل پشتیبان شناسایی شد.")
    return path


def inspect_backup(archive_path: str | Path) -> dict:
    archive_path = Path(archive_path).expanduser().resolve(strict=True)
    if archive_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise BackupError("حجم فایل پشتیبان بیش از حد مجاز است.")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise BackupError("فایل پشتیبان شامل مسیر تکراری است.")
            for name in names:
                _safe_member(name)
            if "manifest.json" not in names or "database.sqlite3" not in names:
                raise BackupError("ساختار فایل پشتیبان کامل نیست.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format_version") != FORMAT_VERSION:
                raise BackupError("نسخه قالب پشتیبان پشتیبانی نمی‌شود.")
            db_bytes = archive.read("database.sqlite3")
            if hashlib.sha256(db_bytes).hexdigest() != manifest.get("database_sha256"):
                raise BackupError("کنترل صحت پایگاه داده ناموفق بود.")
            listed = {item["path"]: item for item in manifest.get("media", [])}
            actual = {n[6:] for n in names if n.startswith("media/") and not n.endswith("/")}
            if actual != set(listed):
                raise BackupError("فهرست رسانه‌ها با محتوای آرشیو مطابقت ندارد.")
            total = len(db_bytes)
            for rel, item in listed.items():
                _safe_member(rel)
                data = archive.read("media/" + rel)
                total += len(data)
                if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                    raise BackupError("کنترل صحت یکی از فایل‌های رسانه‌ای ناموفق بود.")
            if total > MAX_ARCHIVE_BYTES:
                raise BackupError("مجموع داده‌های پشتیبان بیش از حد مجاز است.")
            return manifest
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, TypeError) as exc:
        raise BackupError("فایل پشتیبان معتبر یا قابل‌خواندن نیست.") from exc


def restore_backup(archive_path: str | Path, db_path: str | Path,
                   media_root: str | Path) -> dict:
    """بازیابی پس از اعتبارسنجی کامل؛ پیش از جایگزینی از وضعیت فعلی نسخه ایمن می‌گیرد."""
    archive = Path(archive_path).expanduser().resolve(strict=True)
    db = Path(db_path).expanduser().resolve()
    media = Path(media_root).expanduser().resolve()
    manifest = inspect_backup(archive)
    db.parent.mkdir(parents=True, exist_ok=True)
    media.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="agent-divar-restore-") as tmp:
        stage = Path(tmp)
        staged_db = stage / "database.sqlite3"
        staged_media = stage / "media"
        staged_media.mkdir()
        with zipfile.ZipFile(archive) as zf:
            staged_db.write_bytes(zf.read("database.sqlite3"))
            for item in manifest.get("media", []):
                rel = _safe_member(item["path"])
                dest = (staged_media / Path(*rel.parts)).resolve()
                if staged_media.resolve() not in dest.parents:
                    raise BackupError("مسیر رسانه خارج از پوشه بازیابی است.")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read("media/" + item["path"]))
        check = sqlite3.connect(str(staged_db))
        try:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("پایگاه داده داخل پشتیبان سالم نیست.")
        finally:
            check.close()
        old_db = stage / "old.sqlite3"
        old_media = stage / "old-media"
        had_db, had_media = db.exists(), media.exists()
        if had_db:
            shutil.copy2(db, old_db)
        if had_media:
            shutil.copytree(media, old_media)
        media_swapped = False
        try:
            os.replace(staged_db, db)
            if had_media:
                shutil.rmtree(media)
            os.replace(staged_media, media)
            media_swapped = True
        except Exception:
            if had_db and old_db.exists():
                shutil.copy2(old_db, db)
            if media_swapped and media.exists():
                shutil.rmtree(media)
            if had_media and old_media.exists():
                shutil.copytree(old_media, media)
            raise
    return {"database_restored": True, "media_files": len(manifest.get("media", [])),
            "created_at": manifest.get("created_at")}

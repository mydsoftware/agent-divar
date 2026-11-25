# -*- coding: utf-8 -*-
"""آزمون پشتیبان‌گیری، صحت‌سنجی و بازیابی."""
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

import storage
from backup_manager import create_backup, inspect_backup, restore_backup, BackupError


class BackupManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "leads.sqlite3"
        self.media = self.root / "media"
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            con.execute("INSERT INTO leads(ad_url,title) VALUES (?,?)",
                        ("https://divar.ir/v/backup-test", "ملک داخل نسخه"))
        self.media.mkdir()
        (self.media / "photo.jpg").write_bytes(b"fake-image-bytes")

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_contains_database_and_media_manifest(self):
        target = create_backup(self.db, self.media, self.root / "backup.zip")
        manifest = inspect_backup(target)
        self.assertEqual(len(manifest["media"]), 1)
        with zipfile.ZipFile(target) as zf:
            self.assertIn("database.sqlite3", zf.namelist())
            self.assertIn("media/photo.jpg", zf.namelist())

    def test_restore_recovers_database_and_media(self):
        archive = create_backup(self.db, self.media, self.root / "backup.zip")
        with storage.connect(self.db) as con:
            con.execute("UPDATE leads SET title='تغییر بعد از پشتیبان'")
        (self.media / "photo.jpg").write_bytes(b"changed")
        (self.media / "new.txt").write_text("new", encoding="utf-8")
        result = restore_backup(archive, self.db, self.media)
        with storage.connect(self.db) as con:
            title = con.execute("SELECT title FROM leads").fetchone()[0]
        self.assertEqual(title, "ملک داخل نسخه")
        self.assertEqual((self.media / "photo.jpg").read_bytes(), b"fake-image-bytes")
        self.assertFalse((self.media / "new.txt").exists())
        self.assertEqual(result["media_files"], 1)

    def test_tampered_archive_is_rejected(self):
        archive = create_backup(self.db, self.media, self.root / "backup.zip")
        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == "media/photo.jpg":
                    data = b"tampered"
                dst.writestr(name, data)
        with self.assertRaises(BackupError):
            inspect_backup(tampered)

    def test_path_traversal_archive_is_rejected(self):
        bad = self.root / "bad.zip"
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("../outside.txt", "bad")
            zf.writestr("database.sqlite3", b"")
            zf.writestr("manifest.json", "{}")
        with self.assertRaises(BackupError):
            inspect_backup(bad)

    def test_existing_backup_is_not_overwritten(self):
        target = create_backup(self.db, self.media, self.root / "backup.zip")
        with self.assertRaises(BackupError):
            create_backup(self.db, self.media, target)


if __name__ == "__main__":
    unittest.main()

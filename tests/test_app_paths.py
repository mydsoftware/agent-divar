# -*- coding: utf-8 -*-
"""آزمون مسیرهای داده و مهاجرت غیرمخرب نسخه قدیمی."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app_paths import (
    APP_DATA_DIR, DATA_DIR, DATABASE_PATH, SETTINGS_PATH, migrate_legacy_data,
)


class AppPathsTests(unittest.TestCase):
    def test_data_paths_are_consistent(self):
        self.assertEqual(DATABASE_PATH, DATA_DIR / "leads.sqlite3")
        self.assertEqual(SETTINGS_PATH, DATA_DIR / "settings.json")
        self.assertTrue(str(APP_DATA_DIR))

    def test_data_directories_can_be_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.mkdir(parents=True)
            self.assertTrue(path.is_dir())

    def test_migration_copies_database_settings_and_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old" / "data"
            new = root / "local" / "data"
            old.mkdir(parents=True)
            (old / "property-media" / "12").mkdir(parents=True)
            (old / "property-media" / "12" / "photo.jpg").write_bytes(b"photo")
            (old / "browser-profile").mkdir()
            (old / "browser-profile" / "profile.dat").write_bytes(b"profile")
            (old / "settings.json").write_text('{"font_size": 12}', encoding="utf-8")
            (old / "browser-session.json").write_text('{"state":"closed"}', encoding="utf-8")
            db = sqlite3.connect(old / "leads.sqlite3")
            db.execute("CREATE TABLE sample(value TEXT)")
            db.execute("INSERT INTO sample VALUES ('داده قدیمی')")
            db.commit()
            db.close()

            result = migrate_legacy_data(old, new)

            self.assertIn("leads.sqlite3", result["copied_files"])
            self.assertEqual(
                (new / "property-media" / "12" / "photo.jpg").read_bytes(), b"photo"
            )
            self.assertEqual(
                (new / "browser-profile" / "profile.dat").read_bytes(), b"profile"
            )
            self.assertEqual(
                (new / "settings.json").read_text(encoding="utf-8"),
                '{"font_size": 12}',
            )
            copied_db = sqlite3.connect(new / "leads.sqlite3")
            try:
                self.assertEqual(
                    copied_db.execute("SELECT value FROM sample").fetchone()[0],
                    "داده قدیمی",
                )
                self.assertEqual(
                    copied_db.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
            finally:
                copied_db.close()
            # مهاجرت فقط کپی می‌کند؛ منبع قدیمی حذف نمی‌شود.
            self.assertTrue((old / "leads.sqlite3").is_file())

    def test_migration_never_overwrites_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            new.mkdir()
            (old / "settings.json").write_text("old", encoding="utf-8")
            (new / "settings.json").write_text("new", encoding="utf-8")
            result = migrate_legacy_data(old, new)
            self.assertEqual(
                (new / "settings.json").read_text(encoding="utf-8"), "new"
            )
            self.assertIn("settings.json", result["skipped"])

    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            (old / "settings.json").write_text("{}", encoding="utf-8")
            first = migrate_legacy_data(old, new)
            second = migrate_legacy_data(old, new)
            self.assertEqual(first["copied_files"], ["settings.json"])
            self.assertEqual(second["copied_files"], [])
            self.assertIn("settings.json", second["skipped"])

    def test_corrupt_legacy_database_is_not_published_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            old.mkdir()
            corrupt = old / "leads.sqlite3"
            corrupt.write_bytes(b"not a sqlite database")
            with self.assertRaises(sqlite3.DatabaseError):
                migrate_legacy_data(old, new)
            self.assertFalse((new / "leads.sqlite3").exists())
            self.assertEqual(corrupt.read_bytes(), b"not a sqlite database")


if __name__ == "__main__":
    unittest.main()

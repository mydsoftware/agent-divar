# -*- coding: utf-8 -*-
"""آزمون یکپارچگی پشتیبان و بازیابی در سناریوی انتشار ویندوز."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backup_manager import create_backup, inspect_backup, restore_backup


class WindowsReleaseBackupTests(unittest.TestCase):
    def test_backup_restore_preserves_database_and_media(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_db = root / "source.sqlite3"
            source_media = root / "source-media"
            source_media.mkdir()
            with sqlite3.connect(source_db) as con:
                con.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                con.execute("INSERT INTO sample VALUES ('نسخه پشتیبان')")
            (source_media / "photo.txt").write_text("media-from-backup", encoding="utf-8")

            archive = create_backup(source_db, source_media, root / "release.zip")
            manifest = inspect_backup(archive)
            self.assertEqual(len(manifest["media"]), 1)

            target_db = root / "target" / "leads.sqlite3"
            target_db.parent.mkdir()
            with sqlite3.connect(target_db) as con:
                con.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                con.execute("INSERT INTO sample VALUES ('داده قدیمی')")
            target_media = root / "target" / "property-media"
            target_media.mkdir()
            (target_media / "obsolete.txt").write_text("old", encoding="utf-8")

            result = restore_backup(archive, target_db, target_media)

            with sqlite3.connect(target_db) as con:
                self.assertEqual(
                    con.execute("SELECT value FROM sample").fetchone()[0],
                    "نسخه پشتیبان",
                )
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(
                (target_media / "photo.txt").read_text(encoding="utf-8"),
                "media-from-backup",
            )
            self.assertFalse((target_media / "obsolete.txt").exists())
            self.assertTrue(result["database_restored"])
            self.assertEqual(result["media_files"], 1)


if __name__ == "__main__":
    unittest.main()

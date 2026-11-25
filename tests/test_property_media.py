# -*- coding: utf-8 -*-
"""آزمون‌های کتابخانه رسانه محلی و مهاجرت نسخه ۶."""
import tempfile
import unittest
from pathlib import Path

import storage
from property_media import (
    add_media, list_media, resolve_media_path, set_primary, delete_media,
    audit_media, MediaValidationError,
)


class PropertyMediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "crm.sqlite3"
        self.media_root = self.root / "media"
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            con.execute("INSERT INTO leads(ad_url,title) VALUES (?,?)",
                        ("https://divar.ir/v/media-test", "ملک آزمایشی"))
        self.source = self.root / "document.pdf"
        self.source.write_bytes(b"%PDF-1.4\nmedia test\n")
        self.lead_id = 1

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_v6_preserves_existing_lead_and_creates_media_table(self):
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertEqual(con.execute("SELECT title FROM leads WHERE id=1").fetchone()[0],
                             "ملک آزمایشی")
            self.assertIsNotNone(con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='property_media'"
            ).fetchone())

    def test_add_list_primary_and_delete(self):
        first = add_media(self.db, self.media_root, lead_id=1,
                          source_path=self.source, category="سند و مدارک")
        second_source = self.root / "second.pdf"
        second_source.write_bytes(b"%PDF-1.4\nsecond\n")
        second = add_media(self.db, self.media_root, lead_id=1,
                           source_path=second_source, is_primary=True)
        rows = list_media(self.db, lead_id=1)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["id"], second)
        self.assertEqual(rows[0]["is_primary"], 1)
        set_primary(self.db, lead_id=1, media_id=first)
        self.assertEqual(next(r for r in list_media(self.db, lead_id=1)
                              if r["id"] == first)["is_primary"], 1)
        delete_media(self.db, self.media_root, media_id=second)
        self.assertEqual(len(list_media(self.db, lead_id=1)), 1)

    def test_reject_duplicate_and_invalid_extension(self):
        add_media(self.db, self.media_root, lead_id=1, source_path=self.source)
        with self.assertRaises(MediaValidationError):
            add_media(self.db, self.media_root, lead_id=1, source_path=self.source)
        bad = self.root / "script.exe"
        bad.write_bytes(b"not allowed")
        with self.assertRaises(MediaValidationError):
            add_media(self.db, self.media_root, lead_id=1, source_path=bad)

    def test_reject_unknown_owner_and_path_traversal(self):
        with self.assertRaises(ValueError):
            add_media(self.db, self.media_root, lead_id=999, source_path=self.source)
        with self.assertRaises(MediaValidationError):
            resolve_media_path(self.media_root, "../outside.pdf")

    def test_audit_reports_missing_and_orphan_without_deleting(self):
        media_id = add_media(self.db, self.media_root, lead_id=1, source_path=self.source)
        orphan = self.media_root / "orphan.pdf"
        orphan.write_bytes(b"orphan")
        row = list_media(self.db, lead_id=1)[0]
        resolve_media_path(self.media_root, row["stored_path"]).unlink()
        report = audit_media(self.db, self.media_root)
        self.assertEqual(report["missing_ids"], [media_id])
        self.assertEqual(report["orphan_paths"], ["orphan.pdf"])
        self.assertTrue(orphan.exists())


if __name__ == "__main__":
    unittest.main()

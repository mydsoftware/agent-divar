# -*- coding: utf-8 -*-
"""آزمون‌های مهاجرت، ثبت رویداد و چرخه عمر وظایف پایگاه‌داده."""
import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from pathlib import Path

import storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Path(self.temp_dir.name) / "test.sqlite3"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initialize_creates_schema_and_indexes(self):
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            self.assertEqual(
                con.execute("PRAGMA user_version").fetchone()[0],
                storage.CURRENT_SCHEMA_VERSION,
            )
            tables = {
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertTrue({"campaigns", "leads", "event_logs", "task_runs"} <= tables)
            indexes = {
                row["name"]
                for row in con.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                )
            }
            self.assertIn("idx_leads_campaign_stage", indexes)

    def test_migrates_legacy_campaign_table_without_losing_rows(self):
        self.db.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db)) as con, con:
            con.execute(
                """CREATE TABLE campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    city TEXT NOT NULL DEFAULT '',
                    keywords TEXT NOT NULL DEFAULT '',
                    message_template TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            con.execute(
                "INSERT INTO campaigns(name, city) VALUES (?, ?)",
                ("کمپین قدیمی", "دزفول"),
            )

        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            row = con.execute(
                "SELECT name, city, published_within_hours FROM campaigns"
            ).fetchone()
            self.assertEqual(tuple(row), ("کمپین قدیمی", "دزفول", 168))

    def test_migration_adds_listing_analysis_fields(self):
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            columns = {row["name"] for row in con.execute("PRAGMA table_info(leads)")}
        self.assertTrue({"price", "area", "rooms", "location", "features_json"} <= columns)

    def test_initialize_is_idempotent(self):
        storage.initialize(self.db)
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0], 0)

    def test_record_event_serializes_details(self):
        storage.initialize(self.db)
        event_id = storage.record_event(
            self.db,
            "lead.created",
            entity_type="lead",
            entity_id=7,
            message="سرنخ ثبت شد",
            details={"source": "manual", "city": "دزفول"},
        )
        with storage.connect(self.db) as con:
            row = con.execute(
                "SELECT event_type, entity_id, details_json FROM event_logs WHERE id=?",
                (event_id,),
            ).fetchone()
        self.assertEqual(row["event_type"], "lead.created")
        self.assertEqual(row["entity_id"], 7)
        self.assertEqual(json.loads(row["details_json"])["city"], "دزفول")

    def test_task_run_lifecycle_and_double_finish_guard(self):
        storage.initialize(self.db)
        task_id = storage.start_task(self.db, "search", {"campaign_id": 3})
        storage.finish_task(self.db, task_id, status="failed", error="نمونه خطا")
        with storage.connect(self.db) as con:
            row = con.execute(
                "SELECT status, finished_at, error FROM task_runs WHERE id=?",
                (task_id,),
            ).fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertIsNotNone(row["finished_at"])
        self.assertEqual(row["error"], "نمونه خطا")
        with self.assertRaises(ValueError):
            storage.finish_task(self.db, task_id)

    def test_invalid_task_status_is_rejected(self):
        storage.initialize(self.db)
        task_id = storage.start_task(self.db, "search")
        with self.assertRaises(ValueError):
            storage.finish_task(self.db, task_id, status="unknown")

    def test_foreign_keys_are_enabled(self):
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    """INSERT INTO leads(campaign_id, ad_url, title)
                       VALUES (?, ?, ?)""",
                    (9999, "https://divar.ir/v/test", "آگهی"),
                )


if __name__ == "__main__":
    unittest.main()

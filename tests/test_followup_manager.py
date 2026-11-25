# -*- coding: utf-8 -*-
"""آزمون‌های تاریخچه تعاملات و یادآورهای مشتری."""
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

import storage
from followup_manager import (
    add_interaction, list_interactions, add_reminder,
    update_reminder_status, list_reminders,
)


class FollowUpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "crm.sqlite3"
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            con.execute("INSERT INTO buyer_profiles(name) VALUES ('خریدار آزمایشی')")
            con.execute("""INSERT INTO leads(ad_url,title)
                           VALUES ('https://divar.ir/v/test-1','ملک آزمایشی')""")
        self.buyer_id = 1
        self.lead_id = 1

    def tearDown(self):
        self.tmp.cleanup()

    def test_schema_v5_and_tables(self):
        with storage.connect(self.db) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 5)
            tables = {r["name"] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"interaction_logs", "reminders"} <= tables)

    def test_interaction_crud_and_timeline_order(self):
        older = datetime(2026, 1, 1, tzinfo=timezone.utc)
        newer = older + timedelta(days=1)
        add_interaction(self.db, buyer_id=self.buyer_id, interaction_type="تماس",
                        summary="تماس اول", occurred_at=older)
        add_interaction(self.db, buyer_id=self.buyer_id, interaction_type="جلسه",
                        summary="جلسه دوم", outcome="بازدید تنظیم شد", occurred_at=newer)
        rows = list_interactions(self.db, buyer_id=self.buyer_id)
        self.assertEqual([r["summary"] for r in rows], ["جلسه دوم", "تماس اول"])
        self.assertEqual(rows[0]["outcome"], "بازدید تنظیم شد")

    def test_interaction_requires_exactly_one_owner(self):
        with self.assertRaises(ValueError):
            add_interaction(self.db, interaction_type="تماس", summary="تست")
        with self.assertRaises(ValueError):
            add_interaction(self.db, buyer_id=self.buyer_id, lead_id=self.lead_id,
                            interaction_type="تماس", summary="تست")

    def test_reminder_due_filter_and_completion(self):
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=1)
        future = now + timedelta(days=1)
        past_id = add_reminder(self.db, buyer_id=self.buyer_id,
                               title="پیگیری سررسید", due_at=past, priority="high")
        add_reminder(self.db, lead_id=self.lead_id,
                     title="پیگیری آینده", due_at=future)
        due = list_reminders(self.db, status="pending", due_before=now)
        self.assertEqual([r["id"] for r in due], [past_id])
        update_reminder_status(self.db, past_id, "done")
        self.assertEqual(list_reminders(self.db, status="pending", due_before=now), [])
        done = list_reminders(self.db, status="done")
        self.assertEqual(done[0]["id"], past_id)
        self.assertIsNotNone(done[0]["completed_at"])

    def test_reminder_status_cannot_be_changed_twice(self):
        rid = add_reminder(self.db, buyer_id=self.buyer_id,
                           title="یادآور", due_at=datetime.now(timezone.utc))
        update_reminder_status(self.db, rid, "cancelled")
        with self.assertRaises(ValueError):
            update_reminder_status(self.db, rid, "done")

    def test_invalid_priority_and_datetime_are_rejected(self):
        with self.assertRaises(ValueError):
            add_reminder(self.db, buyer_id=self.buyer_id, title="یادآور",
                         due_at="not-a-date", priority="urgent")
        with self.assertRaises(ValueError):
            add_reminder(self.db, buyer_id=self.buyer_id, title="یادآور",
                         due_at=datetime.now(timezone.utc), priority="urgent")


if __name__ == "__main__":
    unittest.main()

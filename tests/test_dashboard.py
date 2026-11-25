# -*- coding: utf-8 -*-
"""تست‌های داشبورد مدیریتی و گزارش CSV."""
import csv
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import storage
from dashboard import dashboard_data, export_report_csv
from followup_manager import add_interaction, add_reminder


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "dashboard.sqlite3"
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            con.execute("INSERT INTO campaigns(name) VALUES ('کمپین آزمایشی')")
            con.execute("""INSERT INTO leads(campaign_id,ad_url,title,stage,created_at)
                           VALUES (1,'https://divar.ir/v/dashboard-1','آگهی یک','جدید',?)""",
                        (datetime.now(timezone.utc).isoformat(timespec="seconds"),))
            con.execute("INSERT INTO buyer_profiles(name) VALUES ('خریدار یک')")
        add_interaction(self.db, buyer_id=1, interaction_type="تماس", summary="تماس آزمایشی")
        self.now = datetime.now(timezone.utc)
        add_reminder(self.db, buyer_id=1, title="یادآور سررسید",
                     due_at=self.now - timedelta(hours=1), priority="high")
        add_reminder(self.db, lead_id=1, title="یادآور آینده",
                     due_at=self.now + timedelta(days=2))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard_counts_and_grouping(self):
        data = dashboard_data(self.db, now=self.now)
        self.assertEqual(data["leads_total"], 1)
        self.assertEqual(data["buyers_total"], 1)
        self.assertEqual(data["campaigns_total"], 1)
        self.assertEqual(data["interactions_total"], 1)
        self.assertEqual(data["reminders_pending"], 2)
        self.assertEqual(data["reminders_overdue"], 1)
        self.assertEqual(data["reminders_next_week"], 1)
        self.assertEqual(data["stages"][0], {"label": "جدید", "count": 1})
        self.assertEqual(data["campaigns"][0]["leads_count"], 1)
        self.assertEqual(data["campaigns"][0]["converted_count"], 0)

    def test_csv_export_contains_summary_and_campaign(self):
        target = self.root / "report.csv"
        result = export_report_csv(self.db, target)
        self.assertTrue(result.exists())
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[0], ["نوع گزارش", "شاخص", "مقدار"])
        self.assertTrue(any(row[1] == "کل سرنخ‌ها" and row[2] == "1" for row in rows))
        self.assertTrue(any(row[0] == "عملکرد کمپین" and row[1] == "کمپین آزمایشی" for row in rows))

    def test_dashboard_read_only_does_not_change_schema_version(self):
        before = dashboard_data(self.db, now=self.now)
        with storage.connect(self.db) as con:
            version_before = con.execute("PRAGMA user_version").fetchone()[0]
        dashboard_data(self.db, now=self.now)
        with storage.connect(self.db) as con:
            version_after = con.execute("PRAGMA user_version").fetchone()[0]
        self.assertEqual(version_before, version_after)
        self.assertEqual(before["leads_total"], 1)


if __name__ == "__main__":
    unittest.main()

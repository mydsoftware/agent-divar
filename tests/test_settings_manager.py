# -*- coding: utf-8 -*-
"""آزمون تنظیمات و بسته عیب‌یابی."""
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from settings_manager import DEFAULT_SETTINGS, load_settings, save_settings, validate_settings
from diagnostics_manager import create_diagnostics_bundle


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_and_atomic_file(self):
        path = self.root / "config" / "settings.json"
        value = dict(DEFAULT_SETTINGS, font_size=12, export_directory=str(self.root))
        self.assertEqual(save_settings(path, value), value)
        self.assertEqual(load_settings(path), value)
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_invalid_values_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_settings(dict(DEFAULT_SETTINGS, font_size=99))
        with self.assertRaises(ValueError):
            validate_settings(dict(DEFAULT_SETTINGS, theme="unknown"))

    def test_corrupt_file_uses_defaults(self):
        path = self.root / "settings.json"
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(load_settings(path), DEFAULT_SETTINGS)

    def test_diagnostics_excludes_customer_content(self):
        db = self.root / "data.sqlite3"
        con = sqlite3.connect(db)
        con.execute("CREATE TABLE event_logs(event_type TEXT)")
        con.execute("INSERT INTO event_logs VALUES ('lead.created')")
        con.execute("CREATE TABLE leads(title TEXT, public_contact TEXT, notes TEXT)")
        con.execute("INSERT INTO leads VALUES ('PRIVATE_TITLE','09120000000','PRIVATE_NOTE')")
        con.commit()
        con.close()
        target = create_diagnostics_bundle(db, self.root / "diagnostics.zip")
        with zipfile.ZipFile(target) as archive:
            payload = archive.read("diagnostics.json").decode("utf-8")
        self.assertIn("lead.created", payload)
        self.assertNotIn("PRIVATE_TITLE", payload)
        self.assertNotIn("09120000000", payload)
        self.assertNotIn("PRIVATE_NOTE", payload)


if __name__ == "__main__":
    unittest.main()

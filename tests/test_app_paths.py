# -*- coding: utf-8 -*-
"""آزمون مسیرهای داده نسخه توسعه‌ای و نسخه اجرایی."""
import os
import tempfile
import unittest
from pathlib import Path

from app_paths import APP_DATA_DIR, DATA_DIR, DATABASE_PATH, SETTINGS_PATH


class AppPathsTests(unittest.TestCase):
    def test_data_paths_are_outside_repository_data_files(self):
        self.assertEqual(DATABASE_PATH, DATA_DIR / "leads.sqlite3")
        self.assertEqual(SETTINGS_PATH, DATA_DIR / "settings.json")
        self.assertTrue(str(APP_DATA_DIR))

    def test_data_directories_can_be_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.mkdir(parents=True)
            self.assertTrue(path.is_dir())


if __name__ == "__main__":
    unittest.main()

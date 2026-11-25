# -*- coding: utf-8 -*-
"""آزمون‌های پایه بدون نیاز به پنجره گرافیکی."""
import ast
from pathlib import Path
import unittest

APP = Path(__file__).resolve().parents[1] / "app.py"
RUNNER = Path(__file__).resolve().parents[1] / "browser_runner.py"

class SmokeTests(unittest.TestCase):
    def test_app_syntax(self):
        ast.parse(APP.read_text(encoding="utf-8"))

    def test_live_browser_runner_syntax_and_features(self):
        source = RUNNER.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("headless=False", source)
        self.assertIn("launch_persistent_context", source)
        self.assertIn("channel=\"msedge\"", source)

    def test_app_has_live_browser_entrypoint(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("browser_runner.py", source)
        self.assertIn("اجرای زنده در مرورگر ویندوز", source)

    def test_database_schema_contains_campaigns_and_leads(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS campaigns", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS leads", source)
        self.assertIn("UNIQUE", source)
        self.assertIn("published_within_hours", source)
        self.assertIn("۳ ساعت گذشته", source)
        self.assertIn("۱۲ ساعت گذشته", source)
        self.assertIn("۱ روز گذشته", source)
        self.assertIn("۳ روز گذشته", source)
        self.assertIn("۷ روز گذشته", source)

if __name__ == "__main__":
    unittest.main()

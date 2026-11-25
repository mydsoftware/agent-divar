# -*- coding: utf-8 -*-
"""آزمون‌های پایه و رگرسیون بدون نیاز به پنجره گرافیکی."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
RUNNER = ROOT / "browser_runner.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("browser_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeTests(unittest.TestCase):
    def test_app_syntax(self):
        ast.parse(APP.read_text(encoding="utf-8"))

    def test_runner_syntax_and_visible_persistent_configuration(self):
        source = RUNNER.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn('headless": False', source)
        self.assertIn("launch_persistent_context", source)
        self.assertIn('channel="msedge"', source)
        self.assertIn("user_data_dir", source)
        self.assertIn("context.pages", source)
        self.assertNotIn('wait_for_event("close", timeout=0)', source)

    def test_runner_waits_until_all_pages_are_closed(self):
        runner = load_runner()

        class FakePage:
            def __init__(self):
                self.closed = False

            def is_closed(self):
                return self.closed

        class FakeContext:
            def __init__(self):
                self.pages = [FakePage(), FakePage()]

        context = FakeContext()
        sleeps = []

        def fake_sleep(interval):
            sleeps.append(interval)
            if len(sleeps) == 1:
                context.pages[0].closed = True
            else:
                context.pages[1].closed = True

        runner.wait_for_browser_close(context, sleep=fake_sleep)
        self.assertEqual(len(sleeps), 2)
        self.assertFalse(runner.has_open_pages(context))
        self.assertTrue(all(value == runner.POLL_INTERVAL_SECONDS for value in sleeps))

    def test_runner_detects_disconnected_browser_even_if_pages_remain(self):
        runner = load_runner()

        class FakeBrowser:
            def is_connected(self):
                return False

        class FakePage:
            def is_closed(self):
                return False

        class FakeContext:
            browser = FakeBrowser()
            pages = [FakePage()]

        self.assertFalse(runner.has_open_pages(FakeContext()))

    def test_runner_detects_already_closed_pages(self):
        runner = load_runner()

        class ClosedPage:
            def is_closed(self):
                return True

        class FakeContext:
            pages = [ClosedPage()]

        self.assertFalse(runner.has_open_pages(FakeContext()))

    def test_runner_reports_lifecycle_state_atomically(self):
        runner = load_runner()
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            runner.STATUS_FILE = Path(directory) / "browser-session.json"
            runner.write_status("closing")
            status = json.loads(runner.STATUS_FILE.read_text(encoding="utf-8"))
            self.assertEqual(status["pid"], __import__("os").getpid())
            self.assertEqual(status["state"], "closing")
            self.assertTrue(status["updated_at"] > 0)

    def test_app_can_recover_only_a_closed_runner_tree(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("_read_browser_status", source)
        self.assertIn('_terminate_browser_tree()', source)
        self.assertIn('status.get("state") in ("closing", "closed")', source)
        self.assertIn('"taskkill", "/PID"', source)

    def test_app_has_explicit_browser_close_control(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn('text="بستن مرورگر",command=self.close_browser', source)
        self.assertIn("def close_browser(self):", source)
        self.assertIn("self._terminate_browser_tree()", source)
        self.assertIn("self.browser_process = None", source)
        self.assertIn('"state": "closed"', source)

    def test_app_has_live_browser_entrypoint(self):
        source = APP.read_text(encoding="utf-8")
        self.assertIn("browser_runner.py", source)
        self.assertIn("اجرای خودکار در مرورگر ویندوز", source)
        self.assertIn("subprocess.Popen", source)

    def test_database_schema_contains_campaigns_and_leads(self):
        storage_source = (ROOT / "storage.py").read_text(encoding="utf-8")
        app_source = APP.read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS campaigns", storage_source)
        self.assertIn("CREATE TABLE IF NOT EXISTS leads", storage_source)
        self.assertIn("UNIQUE", storage_source)
        self.assertIn("published_within_hours", storage_source)
        self.assertIn("۳ ساعت گذشته", app_source)
        self.assertIn("۱۲ ساعت گذشته", app_source)
        self.assertIn("۱ روز گذشته", app_source)
        self.assertIn("۳ روز گذشته", app_source)
        self.assertIn("۷ روز گذشته", app_source)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""آزمون گردش‌کار مرور قابل‌مشاهده آگهی‌ها."""
import unittest

from browser_automation import (
    collect_visible_listing_urls,
    is_challenge_page,
    is_divar_url,
    run_visible_search,
)


class FakeLocator:
    def __init__(self, values=None, text=""):
        self.values = values or []
        self.text = text

    def inner_text(self, timeout=None):
        return self.text

    def count(self):
        return len(self.values)

    def nth(self, index):
        return FakeLink(self.values[index])


class FakeLink:
    def __init__(self, href):
        self.href = href

    def is_visible(self):
        return True

    def get_attribute(self, name):
        return self.href if name == "href" else None


class FakePage:
    def __init__(self, urls, body=""):
        self.url = "https://divar.ir/s/dezful"
        self.urls = urls
        self.body = body
        self.closed = False
        self.visited = []

    def locator(self, selector):
        return FakeLocator(self.urls if 'href*="/v/"' in selector else [], self.body)

    def goto(self, url, **kwargs):
        self.url = url
        self.visited.append(url)

    def wait_for_timeout(self, value):
        pass

    def is_closed(self):
        return self.closed


class BrowserAutomationTests(unittest.TestCase):
    def test_only_https_divar_urls_are_supported(self):
        self.assertTrue(is_divar_url("https://divar.ir/s/dezful"))
        self.assertFalse(is_divar_url("http://divar.ir/s/dezful"))
        self.assertFalse(is_divar_url("https://example.com/v/123"))

    def test_collects_unique_visible_divar_listing_links_only(self):
        page = FakePage(["/v/one", "/v/two", "/v/one", "https://example.com/v/no"])
        self.assertEqual(
            collect_visible_listing_urls(page, 10),
            ["https://divar.ir/v/one", "https://divar.ir/v/two"],
        )

    def test_challenge_detection_stops_automation(self):
        page = FakePage(["/v/one"], body="لطفاً تأیید کنید ربات نیستید")
        self.assertTrue(is_challenge_page(page))
        result = run_visible_search(page, sleep=lambda _: None)
        self.assertEqual(result.status, "challenge")
        self.assertEqual(result.visited, 0)

    def test_visible_search_opens_each_listing_and_returns_to_results(self):
        page = FakePage(["/v/one", "/v/two"])
        result = run_visible_search(page, max_listings=5, dwell_seconds=0, sleep=lambda _: None)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.visited, 2)
        self.assertEqual(
            page.visited,
            [
                "https://divar.ir/v/one",
                "https://divar.ir/s/dezful",
                "https://divar.ir/v/two",
                "https://divar.ir/s/dezful",
            ],
        )

    def test_non_divar_page_is_not_touched(self):
        page = FakePage(["/v/one"])
        page.url = "https://example.com/"
        result = run_visible_search(page, sleep=lambda _: None)
        self.assertEqual(result.status, "unsupported_page")
        self.assertEqual(page.visited, [])


if __name__ == "__main__":
    unittest.main()

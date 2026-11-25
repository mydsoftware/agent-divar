# -*- coding: utf-8 -*-
"""آزمون‌های مستقل سازنده جست‌وجوی دیوار."""
import unittest

from search_engine import (
    SearchValidationError,
    build_search_plan,
    normalize_digits,
    resolve_city_slug,
)


class SearchEngineTests(unittest.TestCase):
    def test_persian_dezful_name_resolves_to_city_code(self):
        self.assertEqual(resolve_city_slug("دزفول"), "dezful")

    def test_known_persian_cities_are_mapped(self):
        self.assertEqual(resolve_city_slug("تهران"), "tehran")
        self.assertEqual(resolve_city_slug("بندرعباس"), "bandar-abbas")

    def test_ascii_city_slug_is_normalized(self):
        self.assertEqual(resolve_city_slug("DEZFUL"), "dezful")
        self.assertEqual(resolve_city_slug("new_york"), "new-york")

    def test_unknown_persian_city_does_not_fall_back_to_iran(self):
        with self.assertRaises(SearchValidationError):
            resolve_city_slug("شهر ناشناخته")

    def test_empty_city_is_rejected(self):
        with self.assertRaises(SearchValidationError):
            resolve_city_slug("  ")

    def test_search_query_is_encoded_and_combines_terms(self):
        plan = build_search_plan(
            city="دزفول", keywords="آپارتمان دو خواب", category="فروش",
        )
        self.assertEqual(plan.city_slug, "dezful")
        self.assertEqual(plan.query, "آپارتمان دو خواب فروش")
        self.assertIn("https://divar.ir/s/dezful?q=", plan.url)
        self.assertNotIn(" ", plan.url)

    def test_publish_filter_is_reported_as_local_only(self):
        plan = build_search_plan(city="dezful", published_within_hours=24)
        self.assertEqual(plan.published_within_hours, 24)
        self.assertTrue(any("هنوز" in note for note in plan.notes))

    def test_invalid_publish_window_is_rejected(self):
        with self.assertRaises(SearchValidationError):
            build_search_plan(city="dezful", published_within_hours=-1)

    def test_persian_and_arabic_digits_are_normalized(self):
        self.assertEqual(normalize_digits("۱۲۳٤٥"), "12345")


if __name__ == "__main__":
    unittest.main()

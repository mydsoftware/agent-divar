# -*- coding: utf-8 -*-
"""آزمون تطبیق چندحوزه‌ای عنوان آگهی."""
import unittest

from lead_matching import normalize_text, tokenize, match_listing


class LeadMatchingTests(unittest.TestCase):
    def test_persian_arabic_letters_digits_and_half_space(self):
        self.assertEqual(normalize_text("ي ك ۱۲۳‌متر"), "ی ک 123 متر")

    def test_category_and_keyword_match(self):
        result = match_listing("فروش گوشی سامسونگ A54", "موبایل", "سامسونگ, آیفون")
        self.assertTrue(result.matched)
        self.assertIn("سامسونگ", result.matched_keywords)

    def test_non_matching_title_is_rejected(self):
        result = match_listing("اجاره آپارتمان دو خوابه", "خودرو", "پراید, پژو")
        self.assertFalse(result.matched)

    def test_empty_campaign_criteria_never_matches(self):
        self.assertFalse(match_listing("فروش لپ تاپ", "", "").matched)

    def test_matching_is_case_and_punctuation_insensitive(self):
        self.assertTrue(match_listing("Laptop Dell- Inspiron", "لپ تاپ", "dell").matched)


if __name__ == "__main__":
    unittest.main()

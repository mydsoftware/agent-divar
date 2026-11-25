# -*- coding: utf-8 -*-
"""تست‌های امتیازدهی شفاف آگهی و مقایسه قیمت."""
import unittest

from listing_analyzer import (
    BuyerCriteria,
    Listing,
    analyze_listing,
    compare_price_per_area,
)


class ListingAnalyzerTests(unittest.TestCase):
    def test_perfect_match_scores_one_hundred(self):
        listing = Listing("واحد الف", 5_000_000_000, 120, 2, "پیام‌آوران", ("پارکینگ", "آسانسور"))
        criteria = BuyerCriteria(5_500_000_000, 110, 130, 2, "پیام‌آوران", ("پارکینگ", "آسانسور"))
        result = analyze_listing(listing, criteria)
        self.assertEqual(result.score, 100.0)
        self.assertEqual(result.status, "منطبق")
        self.assertEqual(result.compared_weight, 100)

    def test_missing_all_comparable_data_is_insufficient(self):
        result = analyze_listing(Listing(), BuyerCriteria())
        self.assertIsNone(result.score)
        self.assertEqual(result.status, "اطلاعات ناکافی")

    def test_missing_price_does_not_reduce_score_or_invent_price(self):
        result = analyze_listing(
            Listing(area=100, rooms=2),
            BuyerCriteria(max_budget=1_000_000, min_area=90, rooms=2),
        )
        self.assertEqual(result.score, 100.0)
        self.assertEqual(result.compared_weight, 40)
        self.assertFalse(any("قیمت" in reason for reason in result.reasons))

    def test_budget_penalty_is_deterministic(self):
        result = analyze_listing(
            Listing(price=1100),
            BuyerCriteria(max_budget=1000),
        )
        self.assertEqual(result.score, 80.0)
        self.assertIn("10.0٪", result.reasons[0])

    def test_budget_penalty_is_capped_at_zero(self):
        result = analyze_listing(Listing(price=2000), BuyerCriteria(max_budget=1000))
        self.assertEqual(result.score, 0.0)

    def test_area_range_mismatch_is_explained(self):
        result = analyze_listing(Listing(area=80), BuyerCriteria(min_area=90))
        self.assertEqual(result.score, 0.0)
        self.assertIn("متراژ خارج", result.reasons[0])

    def test_location_comparison_ignores_case_and_extra_spaces(self):
        result = analyze_listing(
            Listing(location="  پیام‌آوران  "),
            BuyerCriteria(location="پیام‌آوران"),
        )
        self.assertEqual(result.score, 100.0)

    def test_feature_coverage_is_partial(self):
        result = analyze_listing(
            Listing(features=("پارکینگ",)),
            BuyerCriteria(required_features=("پارکینگ", "انباری")),
        )
        self.assertEqual(result.score, 50.0)
        self.assertEqual(result.status, "نیازمند بررسی")

    def test_no_feature_score_when_listing_has_no_feature_data(self):
        result = analyze_listing(Listing(), BuyerCriteria(required_features=("پارکینگ",)))
        self.assertIsNone(result.score)

    def test_room_mismatch(self):
        result = analyze_listing(Listing(rooms=1), BuyerCriteria(rooms=2))
        self.assertEqual(result.score, 0.0)
        self.assertIn("متفاوت", result.reasons[0])

    def test_price_per_area_comparison(self):
        result = compare_price_per_area(
            Listing(price=10_000, area=100),
            Listing(price=12_000, area=100),
        )
        self.assertEqual(result["first_price_per_area"], 100.0)
        self.assertEqual(result["second_price_per_area"], 120.0)
        self.assertEqual(result["difference_percent"], 20.0)

    def test_price_comparison_returns_unknown_for_missing_data(self):
        result = compare_price_per_area(Listing(price=10_000, area=100), Listing(price=12_000))
        self.assertIsNone(result["second_price_per_area"])
        self.assertIsNone(result["difference_percent"])

    def test_invalid_zero_values_are_not_used(self):
        result = analyze_listing(
            Listing(price=0, area=0),
            BuyerCriteria(max_budget=1000, min_area=50),
        )
        self.assertIsNone(result.score)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""تحلیل توضیح‌پذیر و قطعی آگهی‌های ملکی؛ بدون حدس‌زدن داده‌های مفقود."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


WEIGHTS = {
    "budget": 30,
    "area": 25,
    "rooms": 15,
    "location": 20,
    "features": 10,
}


@dataclass(frozen=True)
class Listing:
    title: str = ""
    price: int | None = None
    area: float | None = None
    rooms: int | None = None
    location: str = ""
    features: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuyerCriteria:
    max_budget: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    rooms: int | None = None
    location: str = ""
    required_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnalysisResult:
    score: float | None
    status: str
    compared_weight: int
    reasons: tuple[str, ...]


def _clean(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _valid_positive(value: int | float | None) -> bool:
    return value is not None and value > 0


def analyze_listing(listing: Listing, criteria: BuyerCriteria) -> AnalysisResult:
    """امتیاز ۰ تا ۱۰۰ را فقط از معیارهایی می‌سازد که هر دو طرف داده دارند."""
    earned = 0.0
    compared_weight = 0
    reasons: list[str] = []

    if _valid_positive(listing.price) and _valid_positive(criteria.max_budget):
        weight = WEIGHTS["budget"]
        compared_weight += weight
        if listing.price <= criteria.max_budget:
            points = 100.0
            reasons.append("قیمت در محدوده بودجه است.")
        else:
            over_pct = (listing.price - criteria.max_budget) / criteria.max_budget * 100
            points = max(0.0, 100.0 - over_pct * 2)
            reasons.append(f"قیمت {over_pct:.1f}٪ بالاتر از سقف بودجه است.")
        earned += points * weight

    if _valid_positive(listing.area) and (
        _valid_positive(criteria.min_area) or _valid_positive(criteria.max_area)
    ):
        weight = WEIGHTS["area"]
        compared_weight += weight
        lower_ok = criteria.min_area is None or listing.area >= criteria.min_area
        upper_ok = criteria.max_area is None or listing.area <= criteria.max_area
        points = 100.0 if lower_ok and upper_ok else 0.0
        reasons.append(
            "متراژ در بازه درخواستی است." if points else "متراژ خارج از بازه درخواستی است."
        )
        earned += points * weight

    if listing.rooms is not None and listing.rooms >= 0 and criteria.rooms is not None:
        weight = WEIGHTS["rooms"]
        compared_weight += weight
        points = 100.0 if listing.rooms == criteria.rooms else 0.0
        reasons.append(
            "تعداد اتاق مطابق درخواست است." if points else "تعداد اتاق با درخواست متفاوت است."
        )
        earned += points * weight

    if _clean(listing.location) and _clean(criteria.location):
        weight = WEIGHTS["location"]
        compared_weight += weight
        points = 100.0 if _clean(listing.location) == _clean(criteria.location) else 0.0
        reasons.append(
            "محدوده مطابق درخواست است." if points else "محدوده با درخواست یکسان نیست."
        )
        earned += points * weight

    if listing.features and criteria.required_features:
        weight = WEIGHTS["features"]
        compared_weight += weight
        available = {_clean(item) for item in listing.features if _clean(item)}
        required = {_clean(item) for item in criteria.required_features if _clean(item)}
        coverage = len(available & required) / len(required) if required else 0.0
        points = coverage * 100
        reasons.append(f"{len(available & required)} مورد از {len(required)} ویژگی درخواستی موجود است.")
        earned += points * weight

    if compared_weight == 0:
        return AnalysisResult(
            score=None,
            status="اطلاعات ناکافی",
            compared_weight=0,
            reasons=("داده مشترکی برای مقایسه آگهی و نیاز مشتری ثبت نشده است.",),
        )

    score = round(earned / compared_weight, 1)
    status = "منطبق" if score >= 80 else "نیازمند بررسی" if score >= 50 else "انطباق کم"
    return AnalysisResult(score, status, compared_weight, tuple(reasons))


def compare_price_per_area(first: Listing, second: Listing) -> dict[str, float | None]:
    """مقایسه قیمت کل و قیمت هر متر؛ فقط با داده معتبر و کامل."""
    result: dict[str, float | None] = {
        "first_price_per_area": None,
        "second_price_per_area": None,
        "difference_percent": None,
    }
    if not all(
        _valid_positive(value)
        for value in (first.price, first.area, second.price, second.area)
    ):
        return result

    first_unit = first.price / first.area
    second_unit = second.price / second.area
    result["first_price_per_area"] = round(first_unit, 2)
    result["second_price_per_area"] = round(second_unit, 2)
    result["difference_percent"] = round((second_unit - first_unit) / first_unit * 100, 2)
    return result

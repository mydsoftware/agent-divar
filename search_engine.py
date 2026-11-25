# -*- coding: utf-8 -*-
"""ساخت امن و قابل‌آزمون نشانی جست‌وجوی دیوار از معیارهای کمپین."""
from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import quote_plus

BASE_URL = "https://divar.ir/s"
CITY_SLUGS = {
    "دزفول": "dezful",
    "تهران": "tehran",
    "مشهد": "mashhad",
    "اصفهان": "isfahan",
    "شیراز": "shiraz",
    "اهواز": "ahvaz",
    "تبریز": "tabriz",
    "کرج": "karaj",
    "قم": "qom",
    "اراک": "arak",
    "رشت": "rasht",
    "یزد": "yazd",
    "کرمان": "kerman",
    "قزوین": "qazvin",
    "بندرعباس": "bandar-abbas",
    "ساری": "sari",
    "گرگان": "gorgan",
    "اردبیل": "ardabil",
    "خرم‌آباد": "khorramabad",
    "زاهدان": "zahedan",
}
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


class SearchValidationError(ValueError):
    """معیار جست‌وجو قابل تبدیل به درخواست معتبر نیست."""


@dataclass(frozen=True)
class SearchPlan:
    url: str
    city_slug: str
    query: str
    published_within_hours: int
    notes: tuple[str, ...]


def normalize_digits(value: str) -> str:
    return value.translate(_DIGIT_TRANSLATION)


def resolve_city_slug(city: str) -> str:
    value = city.strip()
    if not value:
        raise SearchValidationError("کد یا نام شهر را وارد کنید.")
    if value in CITY_SLUGS:
        return CITY_SLUGS[value]
    slug = value.lower().replace("_", "-").replace(" ", "-")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SearchValidationError(
            "نام این شهر در نگاشت محلی نیست؛ کد انگلیسی شهر دیوار را وارد کنید."
        )
    return slug


def build_search_plan(
    *,
    city: str,
    keywords: str = "",
    category: str = "",
    published_within_hours: int = 168,
) -> SearchPlan:
    if published_within_hours < 0:
        raise SearchValidationError("بازه انتشار نمی‌تواند منفی باشد.")
    city_slug = resolve_city_slug(city)
    terms = [part.strip() for part in (keywords, category) if part.strip()]
    query = " ".join(terms)
    url = f"{BASE_URL}/{quote_plus(city_slug)}"
    if query:
        url += f"?q={quote_plus(query)}"

    notes: list[str] = []
    if published_within_hours:
        notes.append(
            "بازه انتشار در کمپین ذخیره شده است؛ این نسخه هنوز آن را به فیلتر سمت دیوار تبدیل نمی‌کند."
        )
    else:
        notes.append("همه بازه‌های انتشار در معیار کمپین انتخاب شده است.")
    return SearchPlan(
        url=url,
        city_slug=city_slug,
        query=query,
        published_within_hours=published_within_hours,
        notes=tuple(notes),
    )

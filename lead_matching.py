# -*- coding: utf-8 -*-
"""نرمال‌سازی و تطبیق عنوان آگهی‌ها با رسته و کلیدواژه‌های کمپین."""
from __future__ import annotations

import re
from dataclasses import dataclass

_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_STOP_WORDS = {"و", "در", "با", "برای", "از", "به", "یک", "این", "آن"}


def normalize_text(value: str) -> str:
    """یکسان‌سازی حروف فارسی/عربی، اعداد، فاصله و نشانه‌گذاری."""
    value = str(value or "").translate(_TRANSLATION)
    value = value.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه")
    value = value.replace("\u200c", " ").replace("\u200f", " ").replace("\u200e", " ")
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return " ".join(value.split()).casefold()


def tokenize(value: str) -> set[str]:
    return {part for part in normalize_text(value).split() if len(part) > 1 and part not in _STOP_WORDS}


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    score: int
    matched_category: bool
    matched_keywords: tuple[str, ...]
    reason: str


def match_listing(title: str, category: str = "", keywords: str | tuple[str, ...] = "",
                  *, threshold: int = 35) -> MatchResult:
    """تطبیق شفاف عنوان؛ دسته و کلیدواژه‌ها در نتیجه قابل مشاهده‌اند."""
    title_norm = normalize_text(title)
    title_tokens = tokenize(title)
    category_norm = normalize_text(category)
    category_tokens = tokenize(category)
    if isinstance(keywords, str):
        keyword_items = [item.strip() for item in keywords.split(",") if item.strip()]
    else:
        keyword_items = [str(item).strip() for item in keywords if str(item).strip()]
    category_hit = bool(category_norm and (
        category_norm in title_norm or bool(category_tokens & title_tokens)
    ))
    hits = tuple(item for item in keyword_items if (
        normalize_text(item) in title_norm or bool(tokenize(item) & title_tokens)
    ))
    # دسته و کلیدواژه‌ها امتیاز مستقل دارند؛ تطبیق بدون معیار رد می‌شود.
    score = min(100, (45 if category_hit else 0) + min(55, len(hits) * 35))
    configured = bool(category_norm or keyword_items)
    matched = configured and score >= threshold and (category_hit or bool(hits))
    reasons = []
    if category_hit:
        reasons.append("حوزه منطبق است")
    if hits:
        reasons.append("کلیدواژه: " + "، ".join(hits))
    if not reasons:
        reasons.append("معیار منطبقی در عنوان پیدا نشد")
    return MatchResult(matched, score, category_hit, hits, "؛ ".join(reasons))

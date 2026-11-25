# -*- coding: utf-8 -*-
"""گردش‌کار مرور قابل‌مشاهده آگهی‌ها؛ بدون استخراج داده یا تعامل با حساب‌ها."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from lead_matching import match_listing
import time

DIVAR_HOSTS = {"divar.ir", "www.divar.ir"}
LISTING_PATH_MARKER = "/v/"


@dataclass(frozen=True)
class AutomationSummary:
    visited: int
    status: str
    message: str
    listings: tuple[dict, ...] = ()


def is_divar_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and parsed.hostname in DIVAR_HOSTS
    except (TypeError, ValueError):
        return False


def is_challenge_page(page) -> bool:
    """وجود نشانه‌های کپچا/محدودیت را تشخیص می‌دهد؛ هرگز برای عبور تلاش نمی‌کند."""
    try:
        text = page.locator("body").inner_text(timeout=1500).casefold()
    except Exception:
        return False
    markers = ("captcha", "کپچا", "تأیید کنید ربات نیستید", "محدودیت دسترسی")
    return any(marker in text for marker in markers)


def collect_visible_listing_urls(page, limit: int = 20) -> list[str]:
    """فقط نشانی کارت‌های آگهی قابل مشاهده را برای پیمایش جمع می‌کند."""
    if limit < 1:
        return []
    urls: list[str] = []
    try:
        links = page.locator('a[href*="/v/"]')
        count = min(links.count(), limit * 3)
        for index in range(count):
            try:
                link = links.nth(index)
                if not link.is_visible():
                    continue
                href = link.get_attribute("href")
                if not href:
                    continue
                url = page.url.split("/s/")[0] + href if href.startswith("/") else href
                if is_divar_url(url) and LISTING_PATH_MARKER in urlparse(url).path and url not in urls:
                    urls.append(url)
                    if len(urls) >= limit:
                        break
            except Exception:
                continue
    except Exception:
        return []
    return urls


def collect_visible_listing_cards(page, limit: int = 20) -> list[dict]:
    """عنوان و قیمت عمومی کارت‌های قابل مشاهده را بدون اطلاعات تماس می‌خواند."""
    cards = []
    try:
        links = page.locator('a[href*="/v/"]')
        count = min(links.count(), limit * 4)
        for index in range(count):
            try:
                link = links.nth(index)
                if not link.is_visible():
                    continue
                href = link.get_attribute("href")
                title = link.inner_text(timeout=1000).strip()
                if not href or not title:
                    continue
                url = page.url.split("/s/")[0] + href if href.startswith("/") else href
                if not is_divar_url(url) or LISTING_PATH_MARKER not in urlparse(url).path:
                    continue
                if any(item["url"] == url for item in cards):
                    continue
                cards.append({"url": url, "title": title[:300], "price": ""})
                if len(cards) >= limit:
                    break
            except Exception:
                continue
    except Exception:
        return []
    return cards


def run_visible_search(page, *, max_listings: int = 15, dwell_seconds: float = 2.0,
                       category: str = "", keywords: str = "", sleep=time.sleep) -> AutomationSummary:
    """آگهی‌ها را در مرورگر قابل‌مشاهده یکی‌یکی باز و به نتایج بازمی‌گردد.

    متن آگهی، شماره تماس، پیام‌ها و داده‌های شخصی خوانده یا ذخیره نمی‌شوند.
    """
    if not is_divar_url(page.url):
        return AutomationSummary(0, "unsupported_page", "صفحه فعلی متعلق به دیوار نیست.")
    if is_challenge_page(page):
        return AutomationSummary(0, "challenge", "محدودیت یا کپچا دیده شد؛ ادامه متوقف شد.")
    cards = collect_visible_listing_cards(page, max_listings)
    matched_cards = (cards if not (category.strip() or keywords.strip()) else
                     [card for card in cards if match_listing(card["title"], category, keywords).matched])
    urls = [card["url"] for card in matched_cards]
    # با پیمایش دیداری صفحه، کارت‌های بعدی بارگذاری می‌شوند؛ سقف تلاش محدود است.
    scroll_attempts = 0
    while len(urls) < max_listings and scroll_attempts < 8 and hasattr(page, "mouse"):
        try:
            page.mouse.wheel(0, 650)
            page.wait_for_timeout(700)
            for card in collect_visible_listing_cards(page, max_listings):
                result = match_listing(card["title"], category, keywords)
                if (not (category.strip() or keywords.strip()) or result.matched) and card["url"] not in urls:
                    card["match_score"] = result.score
                    card["match_reason"] = result.reason
                    matched_cards.append(card)
                    urls.append(card["url"])
                    if len(urls) >= max_listings:
                        break
        except Exception:
            break
        scroll_attempts += 1
    if not urls:
        return AutomationSummary(0, "no_results", "کارت آگهی قابل پیمایش پیدا نشد؛ کنترل مرورگر در اختیار شماست.")

    visited = 0
    search_url = page.url
    for url in urls:
        if page.is_closed():
            return AutomationSummary(visited, "stopped", "مرورگر توسط کاربر بسته شد.")
        if is_challenge_page(page):
            return AutomationSummary(visited, "challenge", "محدودیت یا کپچا دیده شد؛ ادامه متوقف شد.")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            visited += 1
            sleep(max(0.0, dwell_seconds))
            if page.is_closed():
                return AutomationSummary(visited, "stopped", "مرورگر توسط کاربر بسته شد.")
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(500)
        except Exception as exc:
            return AutomationSummary(visited, "paused", f"پیمایش متوقف شد: {type(exc).__name__}")
    matched = tuple(card for card in matched_cards if card["url"] in urls)
    return AutomationSummary(visited, "completed", f"{visited} آگهی منطبق در مرورگر بازبینی شد.", matched)

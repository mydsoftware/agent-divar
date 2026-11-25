# -*- coding: utf-8 -*-
"""اجرای مرورگر قابل‌مشاهده با پروفایل پایدار و کنترل دستی کاربر."""
from __future__ import annotations

import sys
import time
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright
from app_paths import (BROWSER_PROFILE_PATH as PROFILE, BROWSER_STATUS_PATH as STATUS_FILE,
                        DATABASE_PATH as DB, ensure_data_dirs)
from browser_automation import run_visible_search
from storage import connect, initialize
from contact_chat_assistant import extract_visible_contact, detect_chat_composer, save_contact_for_review

ensure_data_dirs()
DEFAULT_URL = "https://divar.ir"
POLL_INTERVAL_SECONDS = 0.25


def write_status(state):
    """وضعیت runner را اتمی ثبت می‌کند تا برنامه اصلی پنجره بسته‌شده را تشخیص دهد."""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_FILE.with_suffix(".tmp")
    payload = {"pid": os.getpid(), "state": state, "updated_at": time.time()}
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(STATUS_FILE)


def launch_browser(playwright):
    """ابتدا Edge و در صورت در دسترس نبودن آن Chromium را اجرا می‌کند."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    common = {
        "user_data_dir": str(PROFILE),
        "headless": False,
        "viewport": None,
        "args": ["--start-maximized"],
    }
    try:
        context = playwright.chromium.launch_persistent_context(
            channel="msedge", **common
        )
        print("مرورگر Microsoft Edge اجرا شد.")
        return context
    except PlaywrightError as edge_error:
        print(f"اجرای Edge ممکن نشد؛ تلاش برای Chromium: {edge_error}")

    try:
        context = playwright.chromium.launch_persistent_context(**common)
        print("مرورگر Chromium اجرا شد.")
        return context
    except PlaywrightError as chromium_error:
        raise RuntimeError(
            "اجرای Edge و Chromium ناموفق بود. نصب مرورگر را بررسی کنید: "
            "python -m playwright install chromium"
        ) from chromium_error


def has_open_pages(context):
    """بسته‌شدن واقعی مرورگر یا همه صفحه‌ها را تشخیص می‌دهد."""
    try:
        # FakeContextها و برخی wrapperها browser property ندارند؛
        # در این حالت وضعیت صفحه‌ها معیار جایگزین است.
        browser = getattr(context, "browser", None)
        if browser is not None and not browser.is_connected():
            return False
        return any(not page.is_closed() for page in context.pages)
    except (PlaywrightError, AttributeError):
        return False


def wait_for_browser_close(context, sleep=time.sleep):
    """تا وقتی حداقل یک صفحه واقعاً باز است، پردازش را زنده نگه می‌دارد."""
    while has_open_pages(context):
        sleep(POLL_INTERVAL_SECONDS)


def save_matched_listings(listings, *, category="", city="", campaign_id=None):
    """ذخیره عنوان و URL عمومی آگهی‌های منطبق؛ بدون اطلاعات تماس."""
    if not listings:
        return 0
    initialize(DB)
    saved = 0
    with connect(DB) as con:
        for item in listings:
            try:
                cursor = con.execute(
                    """INSERT OR IGNORE INTO leads
                       (campaign_id, ad_url, title, category, city, listing_type,
                        discovered_at, match_score, match_reason, attributes_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')""",
                    (campaign_id, item["url"], item["title"], category, city,
                     category or "عمومی", datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     item.get("match_score"), item.get("match_reason", "")),
                )
                saved += cursor.rowcount
            except sqlite3.IntegrityError:
                continue
    return saved


def main(url=None, category="", keywords="", campaign_id=None, city=""):
    url = url or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL)
    write_status("starting")
    with sync_playwright() as playwright:
        context = launch_browser(playwright)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("صفحه مقصد بارگذاری شد.")
            except PlaywrightError as exc:
                print(f"بارگذاری خودکار صفحه ناموفق بود؛ مرورگر باز می‌ماند: {exc}")
            write_status("running")
            contact_observations = []

            def observe_visible_contact(listing_page, card):
                # فقط محتوای قابل مشاهده در صفحه آگهی خوانده می‌شود؛ هیچ دکمه‌ای کلیک نمی‌شود.
                phone = extract_visible_contact(listing_page)
                chat_available = detect_chat_composer(listing_page) is not None
                if phone or chat_available:
                    contact_observations.append({
                        "url": card["url"], "phone": phone,
                        "chat_available": chat_available,
                    })

            summary = run_visible_search(
                page, category=category, keywords=keywords,
                on_listing=observe_visible_contact,
            )
            saved = save_matched_listings(summary.listings, category=category, city=city,
                                          campaign_id=campaign_id)
            queued = 0
            if contact_observations:
                with connect(DB) as con:
                    for observation in contact_observations:
                        lead = con.execute(
                            "SELECT id FROM leads WHERE ad_url=?",
                            (observation["url"],),
                        ).fetchone()
                        if lead is None:
                            continue
                        try:
                            save_contact_for_review(
                                DB, lead_id=int(lead["id"]),
                                contact_value=observation["phone"],
                                chat_available=observation["chat_available"],
                            )
                            queued += 1
                        except (ValueError, PermissionError):
                            continue
            print(f"گزارش مرور خودکار: {summary.status} | {summary.message} | ثبت محلی: {saved} | صف بازبینی: {queued}")
            write_status("running")
            print("مرورگر زنده آماده است؛ برای پایان، همه پنجره‌های آن را ببندید.")
            wait_for_browser_close(context)
        except KeyboardInterrupt:
            print("درخواست توقف دریافت شد.")
        finally:
            write_status("closing")
            try:
                context.close()
            except PlaywrightError:
                pass
            finally:
                write_status("closed")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="مرور آگهی‌های منطبق دیوار")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL)
    parser.add_argument("--category", default="")
    parser.add_argument("--keywords", default="")
    parser.add_argument("--city", default="")
    parser.add_argument("--campaign-id", default="")
    args = parser.parse_args()
    try:
        main(args.url, category=args.category, keywords=args.keywords,
             campaign_id=int(args.campaign_id) if args.campaign_id.isdigit() else None,
             city=args.city)
    except (PlaywrightError, RuntimeError) as exc:
        print(f"خطای اجرای مرورگر: {exc}", file=sys.stderr)
        raise SystemExit(1)

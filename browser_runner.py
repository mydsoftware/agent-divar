# -*- coding: utf-8 -*-
"""اجرای مرورگر قابل‌مشاهده با پروفایل پایدار و کنترل دستی کاربر."""
from __future__ import annotations

import sys
import time
import json
import os
from pathlib import Path
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "data" / "browser-profile"
STATUS_FILE = ROOT / "data" / "browser-session.json"
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
    """فقط صفحه‌هایی را زنده حساب می‌کند که واقعاً بسته نشده‌اند."""
    try:
        return any(not page.is_closed() for page in context.pages)
    except PlaywrightError:
        return False


def wait_for_browser_close(context, sleep=time.sleep):
    """تا وقتی حداقل یک صفحه واقعاً باز است، پردازش را زنده نگه می‌دارد."""
    while has_open_pages(context):
        sleep(POLL_INTERVAL_SECONDS)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    with sync_playwright() as playwright:
        context = launch_browser(playwright)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print("صفحه مقصد بارگذاری شد.")
            except PlaywrightError as exc:
                # خطای شبکه نباید پنجره را ببندد؛ کاربر می‌تواند دستی ادامه دهد.
                print(f"بارگذاری خودکار صفحه ناموفق بود؛ مرورگر باز می‌ماند: {exc}")
            write_status("running")
            print("مرورگر زنده آماده است؛ برای پایان، همه پنجره‌های آن را ببندید.")
            wait_for_browser_close(context)
        except KeyboardInterrupt:
            print("درخواست توقف دریافت شد.")
        finally:
            # از این لحظه پنجره دیگر قابل استفاده نیست؛ اگر پاک‌سازی گیر کند،
            # برنامه اصلی می‌تواند فقط همین درخت پردازش را جمع‌آوری کند.
            write_status("closing")
            try:
                context.close()
            except PlaywrightError:
                pass
            finally:
                write_status("closed")


if __name__ == "__main__":
    try:
        main()
    except (PlaywrightError, RuntimeError) as exc:
        print(f"خطای اجرای مرورگر: {exc}", file=sys.stderr)
        raise SystemExit(1)

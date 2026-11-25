# -*- coding: utf-8 -*-
"""اجرای مرورگر قابل‌مشاهده با پروفایل محلی و امکان کنترل دستی کاربر."""
from __future__ import annotations
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
PROFILE = ROOT / "data" / "browser-profile"

def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://divar.ir"
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE), channel="msedge", headless=False,
                viewport=None, args=["--start-maximized"]
            )
        except Exception:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE), headless=False,
                viewport=None, args=["--start-maximized"]
            )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        print("مرورگر زنده آماده است. برای پایان، پنجره مرورگر را ببندید.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        finally:
            context.close()

if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""ثبت محدود اطلاعات تماسِ قابل مشاهده و آماده‌سازی پیش‌نویس چت؛ بدون ارسال پیام."""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlparse

from storage import connect, initialize

DIVAR_HOSTS = {"divar.ir", "www.divar.ir"}
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PHONE_CANDIDATE = re.compile(r"(?<!\d)(?:\+?98|0098|0)?9\d(?:[\s().-]*\d){9}(?!\d)")


def normalize_phone(value: str) -> str:
    """شماره موبایل ایران را به قالب 09xxxxxxxxx تبدیل می‌کند."""
    digits = re.sub(r"\D", "", str(value).translate(_DIGITS))
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits
    if len(digits) != 11 or not digits.startswith("09"):
        return ""
    return digits


def _is_divar_page(page) -> bool:
    try:
        parsed = urlparse(page.url)
        return parsed.scheme == "https" and parsed.hostname in DIVAR_HOSTS and "/v/" in parsed.path
    except (AttributeError, TypeError, ValueError):
        return False


def extract_visible_contact(page) -> str:
    """فقط شماره‌ای را می‌خواند که در متن قابل مشاهده یا پیوند tel صفحه آگهی باشد.

    نمایش شماره باید قبلاً توسط خود کاربر در رابط دیوار انجام شده باشد.
    این تابع هیچ دکمه‌ای را کلیک نمی‌کند و DOM پنهان/داده شبکه را نمی‌خواند.
    """
    if not _is_divar_page(page):
        return ""
    candidates = []
    try:
        links = page.locator('a[href^="tel:"]')
        for index in range(min(links.count(), 5)):
            link = links.nth(index)
            if link.is_visible():
                href = link.get_attribute("href") or ""
                candidates.append(href[4:])
    except Exception:
        pass
    try:
        visible_text = page.locator("body").inner_text(timeout=2000)
        candidates.extend(_PHONE_CANDIDATE.findall(visible_text))
    except Exception:
        pass
    for candidate in candidates:
        phone = normalize_phone(candidate)
        if phone:
            return phone
    return ""


def detect_chat_composer(page):
    """یک کادر نوشتنِ قابل مشاهده را برمی‌گرداند؛ هیچ دکمه ارسالی جست‌وجو یا فشرده نمی‌شود."""
    if not _is_divar_page(page):
        return None
    for selector in ('textarea', '[contenteditable="true"]'):
        try:
            locators = page.locator(selector)
            visible = [locators.nth(i) for i in range(min(locators.count(), 5))
                       if locators.nth(i).is_visible()]
            if len(visible) == 1:
                return visible[0]
        except Exception:
            continue
    return None


def fill_chat_draft(page, message: str) -> bool:
    """پیش‌نویس را در کادر چت یکتا قرار می‌دهد؛ ارسال پیام انجام نمی‌شود."""
    draft = str(message or "").strip()
    if not draft:
        raise ValueError("متن پیش‌نویس خالی است.")
    composer = detect_chat_composer(page)
    if composer is None:
        return False
    composer.fill(draft)
    return True


def save_contact_for_review(db_path, *, lead_id: int, contact_value: str = "",
                            chat_available: bool = False, message_draft: str = "",
                            captured_at: str | None = None) -> int:
    """اطلاعات تماس را در صف بازبینی محلی ثبت می‌کند؛ وضعیت اولیه نیازمند بررسی است."""
    phone = normalize_phone(contact_value) if contact_value else ""
    if contact_value and not phone:
        raise ValueError("شماره تماس معتبر نیست.")
    if not isinstance(lead_id, int) or lead_id < 1:
        raise ValueError("شناسه آگهی نامعتبر است.")
    initialize(db_path)
    timestamp = captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect(db_path) as con:
        if not con.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,)).fetchone():
            raise ValueError("آگهی موردنظر در CRM وجود ندارد.")
        existing = con.execute(
            "SELECT review_status FROM contact_review_queue WHERE lead_id=?",
            (lead_id,),
        ).fetchone()
        if existing and existing["review_status"] == "do_not_contact":
            raise PermissionError("این سرنخ در فهرست عدم تماس قرار دارد.")
        con.execute(
            """INSERT INTO contact_review_queue
               (lead_id,contact_value,captured_at,chat_available,message_draft)
               VALUES (?,?,?,?,?)
               ON CONFLICT(lead_id) DO UPDATE SET
                 contact_value=CASE WHEN excluded.contact_value='' THEN contact_review_queue.contact_value
                                    ELSE excluded.contact_value END,
                 captured_at=excluded.captured_at,
                 chat_available=excluded.chat_available,
                 message_draft=CASE WHEN excluded.message_draft='' THEN contact_review_queue.message_draft
                                    ELSE excluded.message_draft END,
                 updated_at=CURRENT_TIMESTAMP
               WHERE contact_review_queue.review_status != 'do_not_contact'""",
            (lead_id, phone, timestamp, int(bool(chat_available)), str(message_draft or "").strip()),
        )
        row = con.execute("SELECT id FROM contact_review_queue WHERE lead_id=?", (lead_id,)).fetchone()
        if row is None:
            raise PermissionError("این سرنخ در فهرست عدم تماس قرار دارد.")
        return int(row["id"])


def set_contact_review_status(db_path, queue_id: int, status: str) -> None:
    """ثبت تصمیم انسانی؛ عدم تماس قابل بازگشت خودکار نیست."""
    if status not in {"approved_for_manual_use", "do_not_contact"}:
        raise ValueError("وضعیت بازبینی نامعتبر است.")
    with connect(db_path) as con:
        cur = con.execute(
            """UPDATE contact_review_queue
               SET review_status=?, reviewed_at=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND review_status != 'do_not_contact'""",
            (status, datetime.now(timezone.utc).isoformat(timespec="seconds"), queue_id),
        )
        if cur.rowcount != 1:
            raise ValueError("رکورد یافت نشد یا در فهرست عدم تماس قرار دارد.")


def list_contact_review_queue(db_path, *, include_do_not_contact: bool = False):
    """فهرست صف بازبینی را بدون ثبت شماره در گزارش‌ها برمی‌گرداند."""
    with connect(db_path) as con:
        if include_do_not_contact:
            rows = con.execute(
                """SELECT q.*, l.title, l.ad_url FROM contact_review_queue q
                   JOIN leads l ON l.id=q.lead_id ORDER BY q.captured_at DESC"""
            ).fetchall()
        else:
            rows = con.execute(
                """SELECT q.*, l.title, l.ad_url FROM contact_review_queue q
                   JOIN leads l ON l.id=q.lead_id
                   WHERE q.review_status != 'do_not_contact'
                   ORDER BY q.captured_at DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

# -*- coding: utf-8 -*-
"""آزمون‌های ثبت تماس قابل مشاهده و پیش‌نویس چت."""
import tempfile
import unittest
from pathlib import Path

import storage
from contact_chat_assistant import (
    normalize_phone, extract_visible_contact, fill_chat_draft,
    save_contact_for_review, set_contact_review_status,
    list_contact_review_queue,
)


class FakeLocator:
    def __init__(self, text="", href=None, visible=True):
        self.text, self.href, self.visible = text, href, visible
        self.filled = None

    def count(self):
        return 1

    def nth(self, _index):
        return self

    def is_visible(self):
        return self.visible

    def get_attribute(self, name):
        return self.href if name == "href" else None

    def inner_text(self, **_kwargs):
        return self.text

    def fill(self, value):
        self.filled = value


class FakePage:
    def __init__(self, url="https://divar.ir/v/test", body="", tel=None, composer=None):
        self.url = url
        self.body = FakeLocator(text=body)
        self.tel = FakeLocator(href=tel) if tel else None
        self.composer = composer

    def locator(self, selector):
        if selector == "body":
            return self.body
        if selector == 'a[href^="tel:"]':
            return self.tel or EmptyLocator()
        if selector in ('textarea', '[contenteditable="true"]'):
            return self.composer or EmptyLocator()
        return EmptyLocator()


class EmptyLocator:
    def count(self):
        return 0

    def nth(self, _index):
        return self

    def is_visible(self):
        return False


class ContactAssistantTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "crm.sqlite3"
        storage.initialize(self.db)
        with storage.connect(self.db) as con:
            con.execute("INSERT INTO leads(ad_url,title) VALUES (?,?)",
                        ("https://divar.ir/v/test", "آگهی آزمایشی"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_normalizes_iranian_mobile_numbers(self):
        self.assertEqual(normalize_phone("۰۹۱۲ ۱۲۳ ۴۵۶۷"), "09121234567")
        self.assertEqual(normalize_phone("+989121234567"), "09121234567")
        self.assertEqual(normalize_phone("00989121234567"), "09121234567")
        self.assertEqual(normalize_phone("02112345678"), "")

    def test_extracts_only_visible_contact_from_divar_listing(self):
        page = FakePage(body="تماس با فروشنده: ۰۹۱۲۱۲۳۴۵۶۷")
        self.assertEqual(extract_visible_contact(page), "09121234567")
        external = FakePage(url="https://example.com/v/test",
                            body="09121234567")
        self.assertEqual(extract_visible_contact(external), "")

    def test_uses_visible_tel_link_and_ignores_hidden_link(self):
        page = FakePage(tel="tel:+989121234567")
        self.assertEqual(extract_visible_contact(page), "09121234567")
        page.tel.visible = False
        self.assertEqual(extract_visible_contact(page), "")

    def test_fills_chat_draft_without_send_action(self):
        composer = FakeLocator()
        page = FakePage(composer=composer)
        self.assertTrue(fill_chat_draft(page, "سلام، برای اطلاعات بیشتر پیام دادم."))
        self.assertEqual(composer.filled, "سلام، برای اطلاعات بیشتر پیام دادم.")
        self.assertIsNone(page.locator("button[type=submit]").filled)

    def test_requires_unique_visible_composer_and_nonempty_draft(self):
        page = FakePage()
        self.assertFalse(fill_chat_draft(page, "سلام"))
        with self.assertRaises(ValueError):
            fill_chat_draft(page, " ")

    def test_contact_is_saved_for_human_review_and_duplicate_is_updated(self):
        queue_id = save_contact_for_review(
            self.db, lead_id=1, contact_value="09121234567",
            chat_available=True, message_draft="سلام"
        )
        save_contact_for_review(
            self.db, lead_id=1, contact_value="",
            chat_available=True, message_draft=""
        )
        rows = list_contact_review_queue(self.db)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], queue_id)
        self.assertEqual(rows[0]["contact_value"], "09121234567")
        self.assertEqual(rows[0]["review_status"], "review_required")

    def test_do_not_contact_is_enforced(self):
        queue_id = save_contact_for_review(
            self.db, lead_id=1, contact_value="09121234567"
        )
        set_contact_review_status(self.db, queue_id, "do_not_contact")
        self.assertEqual(list_contact_review_queue(self.db), [])
        with self.assertRaises(PermissionError):
            save_contact_for_review(
                self.db, lead_id=1, contact_value="09129998877"
            )

    def test_rejects_invalid_phone_and_unknown_lead(self):
        with self.assertRaises(ValueError):
            save_contact_for_review(self.db, lead_id=1, contact_value="123")
        with self.assertRaises(ValueError):
            save_contact_for_review(self.db, lead_id=999, contact_value="")


if __name__ == "__main__":
    unittest.main()

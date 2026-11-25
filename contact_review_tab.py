# -*- coding: utf-8 -*-
"""رابط صف بازبینی اطلاعات تماس و پیش‌نویس پیام."""
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from contact_chat_assistant import list_contact_review_queue, set_contact_review_status


class ContactReviewTab(ttk.Frame):
    def __init__(self, master, db_path):
        super().__init__(master, padding=10)
        self.db_path = db_path
        self._build()
        self.refresh()

    def _build(self):
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 8))
        ttk.Button(actions, text="تازه‌سازی", command=self.refresh).pack(side="right", padx=3)
        ttk.Button(actions, text="تأیید برای استفاده دستی", command=self.approve).pack(side="right", padx=3)
        ttk.Button(actions, text="عدم تماس", command=self.do_not_contact).pack(side="right", padx=3)
        ttk.Button(actions, text="بازکردن آگهی", command=self.open_listing).pack(side="right", padx=3)
        ttk.Button(actions, text="کپی پیش‌نویس", command=self.copy_draft).pack(side="right", padx=3)

        columns = ("id", "title", "contact", "chat", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=12)
        headings = [
            ("id", "شناسه", 65), ("title", "عنوان آگهی", 340),
            ("contact", "شماره قابل مشاهده", 150), ("chat", "وضعیت چت", 110),
            ("status", "وضعیت بازبینی", 190),
        ]
        for key, label, width in headings:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="e")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        ttk.Label(self, text="پیش‌نویس پیام — فقط برای بررسی و استفاده دستی؛ برنامه پیام را ارسال نمی‌کند.",
                  foreground="#475569").pack(anchor="e", pady=(10, 3))
        self.draft = tk.Text(self, height=4, wrap="word")
        self.draft.pack(fill="x")
        self.draft.configure(state="disabled")
        self.rows = {}

    def refresh(self):
        self.rows = {row["id"]: row for row in list_contact_review_queue(self.db_path)}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.rows.values():
            self.tree.insert("", "end", iid=str(row["id"]), values=(
                row["id"], row["title"], row["contact_value"] or "—",
                "فعال" if row["chat_available"] else "در دسترس نیست",
                row["review_status"],
            ))

    def _selected(self):
        selected = self.tree.selection()
        if not selected:
            return None
        return self.rows.get(int(selected[0]))

    def _select(self, _event=None):
        row = self._selected()
        self.draft.configure(state="normal")
        self.draft.delete("1.0", "end")
        if row:
            self.draft.insert("1.0", row["message_draft"] or "")
        self.draft.configure(state="disabled")

    def approve(self):
        row = self._selected()
        if not row:
            return
        try:
            set_contact_review_status(self.db_path, row["id"], "approved_for_manual_use")
        except ValueError as exc:
            messagebox.showwarning("بازبینی", str(exc))
        self.refresh()

    def do_not_contact(self):
        row = self._selected()
        if not row:
            return
        if not messagebox.askyesno("عدم تماس", "این آگهی در فهرست عدم تماس قرار بگیرد؟"):
            return
        try:
            set_contact_review_status(self.db_path, row["id"], "do_not_contact")
        except ValueError as exc:
            messagebox.showwarning("بازبینی", str(exc))
        self.refresh()

    def open_listing(self):
        row = self._selected()
        if row:
            webbrowser.open(row["ad_url"])

    def copy_draft(self):
        row = self._selected()
        if not row or not row["message_draft"]:
            messagebox.showinfo("پیش‌نویس", "برای این کمپین پیش‌نویسی ثبت نشده است.")
            return
        self.clipboard_clear()
        self.clipboard_append(row["message_draft"])
        messagebox.showinfo("پیش‌نویس", "متن پیش‌نویس کپی شد؛ ارسال بر عهده شماست.")

# -*- coding: utf-8 -*-
"""رابط کاربری گالری تصاویر و مدارک پرونده آگهی."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from property_media import (
    CATEGORIES, add_media, list_media, resolve_media_path,
    set_primary, delete_media, audit_media,
)


class PropertyMediaTab(ttk.Frame):
    def __init__(self, master, db_path: str | Path, storage_root: str | Path):
        super().__init__(master, padding=12)
        self.db_path = Path(db_path)
        self.storage_root = Path(storage_root)
        self.leads = {}
        self.selected_media_id = None
        self._build()
        self.refresh_leads()

    def _build(self):
        top = ttk.LabelFrame(self, text="پرونده آگهی", padding=10)
        top.pack(fill="x")
        self.lead_var = tk.StringVar()
        self.lead_combo = ttk.Combobox(top, textvariable=self.lead_var,
                                       state="readonly", justify="right")
        self.lead_combo.pack(side="right", fill="x", expand=True, padx=5)
        self.lead_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_media())
        ttk.Button(top, text="به‌روزرسانی آگهی‌ها",
                   command=self.refresh_leads).pack(side="right")

        form = ttk.LabelFrame(self, text="افزودن تصویر یا مدرک", padding=10)
        form.pack(fill="x", pady=8)
        self.category = tk.StringVar(value="سایر")
        self.description = tk.StringVar()
        ttk.Label(form, text="دسته‌بندی").grid(row=0, column=0, sticky="e", padx=4)
        ttk.Combobox(form, textvariable=self.category, values=CATEGORIES,
                     state="readonly", justify="right").grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(form, text="توضیحات").grid(row=1, column=0, sticky="e", padx=4)
        ttk.Entry(form, textvariable=self.description, justify="right").grid(
            row=1, column=1, sticky="ew", padx=4)
        ttk.Button(form, text="انتخاب فایل و افزودن",
                   command=self.add_selected_file).grid(row=0, column=2, rowspan=2, padx=6)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=5)
        ttk.Button(actions, text="بازکردن فایل", command=self.open_selected).pack(side="right", padx=3)
        ttk.Button(actions, text="انتخاب به‌عنوان تصویر اصلی",
                   command=self.make_primary).pack(side="right", padx=3)
        ttk.Button(actions, text="حذف فایل", command=self.remove_selected).pack(side="right", padx=3)
        ttk.Button(actions, text="بررسی فایل‌های مفقود/یتیم",
                   command=self.run_audit).pack(side="left", padx=3)

        self.tree = ttk.Treeview(self, columns=("id", "name", "category", "size",
                                                "primary", "description"),
                                 show="headings", height=13)
        columns = [("id", "شناسه", 55), ("name", "نام فایل", 230),
                   ("category", "دسته", 110), ("size", "حجم (بایت)", 100),
                   ("primary", "تصویر اصلی", 90), ("description", "توضیحات", 260)]
        for key, title, width in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="e")
        self.tree.pack(fill="both", expand=True, pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._select)

        ttk.Label(self, text="فایل‌ها فقط در رایانه ذخیره می‌شوند؛ ارسال یا بارگذاری خودکار انجام نمی‌شود.",
                  foreground="#475569").pack(anchor="e")

    def refresh_leads(self):
        from storage import connect
        with connect(self.db_path) as con:
            rows = con.execute("SELECT id,title FROM leads ORDER BY id DESC").fetchall()
        self.leads = {f'{row["id"]} — {row["title"]}': row["id"] for row in rows}
        self.lead_combo["values"] = list(self.leads)
        if self.lead_var.get() not in self.leads:
            self.lead_var.set(next(iter(self.leads), ""))
        self.refresh_media()

    def _lead_id(self):
        return self.leads.get(self.lead_var.get())

    def refresh_media(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        lead_id = self._lead_id()
        if not lead_id:
            return
        for row in list_media(self.db_path, lead_id=lead_id):
            self.tree.insert("", "end", values=(
                row["id"], row["original_name"], row["category"], row["file_size"],
                "بله" if row["is_primary"] else "خیر", row["description"]
            ))

    def _select(self, _event=None):
        selected = self.tree.selection()
        self.selected_media_id = int(self.tree.item(selected[0], "values")[0]) if selected else None

    def add_selected_file(self):
        lead_id = self._lead_id()
        if not lead_id:
            messagebox.showwarning("انتخاب آگهی", "ابتدا یک آگهی ثبت یا انتخاب کنید.")
            return
        source = filedialog.askopenfilename(
            title="انتخاب تصویر یا مدرک",
            filetypes=[("تصویر و PDF", "*.jpg *.jpeg *.png *.webp *.pdf"), ("همه فایل‌ها", "*.*")]
        )
        if not source:
            return
        try:
            add_media(self.db_path, self.storage_root, lead_id=lead_id,
                      source_path=source, category=self.category.get(),
                      description=self.description.get())
        except (ValueError, OSError) as exc:
            messagebox.showerror("افزودن فایل ناموفق", str(exc))
            return
        self.description.set("")
        self.refresh_media()

    def _selected_row(self):
        if not self.selected_media_id:
            messagebox.showinfo("انتخاب فایل", "ابتدا یک فایل از فهرست انتخاب کنید.")
            return None
        return next((r for r in list_media(self.db_path, lead_id=self._lead_id())
                     if r["id"] == self.selected_media_id), None)

    def open_selected(self):
        row = self._selected_row()
        if not row:
            return
        path = resolve_media_path(self.storage_root, row["stored_path"])
        if not path.is_file():
            messagebox.showerror("فایل پیدا نشد", "فایل از مسیر ذخیره‌شده حذف شده است.")
            return
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def make_primary(self):
        row = self._selected_row()
        if not row:
            return
        set_primary(self.db_path, lead_id=self._lead_id(), media_id=row["id"])
        self.refresh_media()

    def remove_selected(self):
        row = self._selected_row()
        if not row:
            return
        if not messagebox.askyesno("حذف فایل", "فایل انتخاب‌شده از پرونده و پوشه محلی حذف شود؟"):
            return
        delete_media(self.db_path, self.storage_root, media_id=row["id"])
        self.selected_media_id = None
        self.refresh_media()

    def run_audit(self):
        report = audit_media(self.db_path, self.storage_root)
        messagebox.showinfo(
            "گزارش سلامت فایل‌ها",
            f"فایل مفقود: {len(report['missing_ids'])}\n"
            f"فایل بدون مشخصات: {len(report['orphan_paths'])}\n"
            "هیچ فایلی در بررسی خودکار حذف نمی‌شود."
        )

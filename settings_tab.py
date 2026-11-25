# -*- coding: utf-8 -*-
"""رابط تنظیمات و خروجی عیب‌یابی."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from settings_manager import save_settings
from diagnostics_manager import create_diagnostics_bundle


class SettingsTab(ttk.Frame):
    def __init__(self, master, settings_path, db_path, settings, on_saved):
        super().__init__(master, padding=16)
        self.settings_path = Path(settings_path)
        self.db_path = Path(db_path)
        self.settings = dict(settings)
        self.on_saved = on_saved
        self.theme = tk.StringVar(value=self.settings["theme"])
        self.font_size = tk.StringVar(value=str(self.settings["font_size"]))
        self.export_dir = tk.StringVar(value=self.settings["export_directory"])
        self.diagnostics = tk.BooleanVar(value=self.settings["diagnostics_enabled"])
        self._build()

    def _build(self):
        form = ttk.LabelFrame(self, text="تنظیمات برنامه", padding=12)
        form.pack(fill="x", anchor="n")
        ttk.Label(form, text="قالب نمایشی").grid(row=0, column=0, sticky="e", padx=6, pady=6)
        ttk.Combobox(form, textvariable=self.theme,
                     values=("clam", "default", "alt", "classic"),
                     state="readonly", justify="right").grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(form, text="اندازه قلم (۸ تا ۱۶)").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        ttk.Spinbox(form, from_=8, to=16, textvariable=self.font_size,
                    width=8, justify="right").grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(form, text="پوشه پیش‌فرض خروجی اکسل").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.export_dir, justify="left").grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Button(form, text="انتخاب پوشه", command=self.choose_export_dir).grid(row=2, column=2, padx=6)
        ttk.Checkbutton(form, text="فعال بودن ساخت بسته عیب‌یابی (با درخواست دستی)",
                        variable=self.diagnostics).grid(row=3, column=0, columnspan=3, sticky="e", padx=6, pady=8)
        form.columnconfigure(1, weight=1)
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=12)
        ttk.Button(actions, text="ذخیره تنظیمات", command=self.save).pack(side="right", padx=4)
        ttk.Button(actions, text="ساخت بسته عیب‌یابی", command=self.export_diagnostics).pack(side="right", padx=4)
        ttk.Label(self, text="تنظیمات فقط روی همین رایانه ذخیره می‌شوند. بسته عیب‌یابی شامل اطلاعات تماس، نام مشتری، عنوان آگهی و یادداشت‌ها نیست.",
                  wraplength=850, foreground="#475569").pack(anchor="e", pady=8)

    def choose_export_dir(self):
        selected = filedialog.askdirectory()
        if selected:
            self.export_dir.set(selected)

    def save(self):
        try:
            updated = save_settings(self.settings_path, {
                "theme": self.theme.get(),
                "font_size": int(self.font_size.get()),
                "export_directory": self.export_dir.get().strip(),
                "diagnostics_enabled": self.diagnostics.get(),
            })
        except (ValueError, OSError) as exc:
            messagebox.showerror("تنظیمات نامعتبر", str(exc))
            return
        self.settings = updated
        self.on_saved(updated)
        messagebox.showinfo("ذخیره شد", "تنظیمات ذخیره و اعمال شد.")

    def export_diagnostics(self):
        if not self.diagnostics.get():
            messagebox.showwarning("غیرفعال", "ساخت بسته عیب‌یابی در تنظیمات غیرفعال است.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", initialfile="agent-divar-diagnostics.zip",
            filetypes=[("بسته عیب‌یابی", "*.zip")])
        if not path:
            return
        try:
            create_diagnostics_bundle(self.db_path, path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("خطا", f"ساخت بسته عیب‌یابی ناموفق بود: {exc}")
            return
        messagebox.showinfo("آماده شد", f"بسته عیب‌یابی ساخته شد:\n{path}")

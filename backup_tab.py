# -*- coding: utf-8 -*-
"""رابط کاربری پشتیبان‌گیری و بازیابی محلی."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from backup_manager import create_backup, inspect_backup, restore_backup, BackupError


class BackupTab(ttk.Frame):
    def __init__(self, master, db_path: str | Path, media_root: str | Path):
        super().__init__(master, padding=18)
        self.db_path = Path(db_path)
        self.media_root = Path(media_root)
        ttk.Label(self, text="پشتیبان‌گیری و بازیابی اطلاعات",
                  font=("Tahoma", 14, "bold")).pack(anchor="e", pady=(0, 12))
        ttk.Label(self, text="نسخه پشتیبان شامل پایگاه داده SQLite و تمام تصاویر و مدارک محلی است.",
                  wraplength=780, justify="right").pack(anchor="e", pady=6)
        ttk.Button(self, text="ساخت نسخه پشتیبان", command=self.backup).pack(anchor="e", pady=8)
        ttk.Separator(self).pack(fill="x", pady=12)
        ttk.Label(self, text="بازیابی، اطلاعات فعلی را با نسخه انتخاب‌شده جایگزین می‌کند.",
                  foreground="#9a3412", wraplength=780, justify="right").pack(anchor="e", pady=6)
        ttk.Button(self, text="بررسی فایل پشتیبان", command=self.inspect).pack(anchor="e", pady=5)
        ttk.Button(self, text="بازیابی از فایل پشتیبان", command=self.restore).pack(anchor="e", pady=5)
        self.status = tk.StringVar(value="هنوز عملیاتی انجام نشده است.")
        ttk.Label(self, textvariable=self.status, wraplength=780,
                  justify="right").pack(anchor="e", pady=14)

    def backup(self):
        path = filedialog.asksaveasfilename(
            title="ذخیره نسخه پشتیبان", defaultextension=".zip",
            filetypes=[("پشتیبان Agent Divar", "*.zip")],
            initialfile="agent-divar-backup.zip")
        if not path:
            return
        try:
            result = create_backup(self.db_path, self.media_root, path)
        except (OSError, BackupError, ValueError) as exc:
            messagebox.showerror("پشتیبان‌گیری ناموفق", str(exc))
            return
        self.status.set(f"نسخه پشتیبان ساخته شد: {result}")
        messagebox.showinfo("پشتیبان‌گیری", "نسخه پشتیبان با موفقیت ساخته شد.")

    def _choose(self):
        return filedialog.askopenfilename(
            title="انتخاب فایل پشتیبان",
            filetypes=[("پشتیبان Agent Divar", "*.zip"), ("همه فایل‌ها", "*.*")])

    def inspect(self):
        path = self._choose()
        if not path:
            return
        try:
            manifest = inspect_backup(path)
        except (OSError, BackupError, ValueError) as exc:
            messagebox.showerror("پشتیبان نامعتبر", str(exc))
            return
        self.status.set(
            f"پشتیبان معتبر است | تاریخ: {manifest.get('created_at')} | "
            f"تعداد فایل‌های رسانه: {len(manifest.get('media', []))}")
        messagebox.showinfo("بررسی پشتیبان", "ساختار و صحت فایل‌های پشتیبان تأیید شد.")

    def restore(self):
        path = self._choose()
        if not path:
            return
        try:
            manifest = inspect_backup(path)
        except (OSError, BackupError, ValueError) as exc:
            messagebox.showerror("پشتیبان نامعتبر", str(exc))
            return
        if not messagebox.askyesno(
            "تأیید بازیابی",
            "اطلاعات فعلی با نسخه پشتیبان جایگزین می‌شود.\n"
            "قبل از ادامه، برنامه را ببندید و از فایل‌های مهم نسخه جداگانه داشته باشید.\n"
            "آیا ادامه می‌دهید؟"
        ):
            return
        try:
            result = restore_backup(path, self.db_path, self.media_root)
        except (OSError, BackupError, ValueError) as exc:
            messagebox.showerror("بازیابی ناموفق", str(exc))
            return
        self.status.set(f"بازیابی انجام شد | {result['media_files']} فایل رسانه")
        messagebox.showinfo("بازیابی", "اطلاعات بازیابی شد. برنامه را ببندید و دوباره اجرا کنید.")

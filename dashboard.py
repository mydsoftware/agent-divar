# -*- coding: utf-8 -*-
"""داشبورد مدیریتی و گزارش‌های آماری محلی برای Agent Divar."""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from storage import connect


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dashboard_data(db_path: str | Path, *, now: datetime | None = None) -> dict:
    """محاسبه شاخص‌های CRM بدون تغییر داده‌ها و بدون ارسال اطلاعات به بیرون."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    now_text = moment.astimezone(timezone.utc).isoformat(timespec="seconds")
    month_start = moment.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
    week_end = (moment.astimezone(timezone.utc) + timedelta(days=7)).isoformat(timespec="seconds")
    with connect(db_path) as con:
        leads_total = con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        buyers_total = con.execute("SELECT COUNT(*) FROM buyer_profiles").fetchone()[0]
        campaigns_total = con.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0]
        interactions_total = con.execute("SELECT COUNT(*) FROM interaction_logs").fetchone()[0]
        reminders_pending = con.execute("SELECT COUNT(*) FROM reminders WHERE status='pending'").fetchone()[0]
        reminders_overdue = con.execute(
            "SELECT COUNT(*) FROM reminders WHERE status='pending' AND due_at<=?", (now_text,)
        ).fetchone()[0]
        reminders_next_week = con.execute(
            "SELECT COUNT(*) FROM reminders WHERE status='pending' AND due_at>? AND due_at<=?",
            (now_text, week_end),
        ).fetchone()[0]
        leads_this_month = con.execute(
            "SELECT COUNT(*) FROM leads WHERE created_at>=?", (month_start,)
        ).fetchone()[0]
        stages = [dict(row) for row in con.execute(
            "SELECT stage AS label, COUNT(*) AS count FROM leads GROUP BY stage ORDER BY count DESC, label"
        )]
        campaign_rows = [dict(row) for row in con.execute(
            """SELECT c.id, c.name, COUNT(l.id) AS leads_count,
                      SUM(CASE WHEN l.stage IN ('موفق','معامله‌شده','فروخته‌شده','اجاره‌شده') THEN 1 ELSE 0 END) AS converted_count
               FROM campaigns c LEFT JOIN leads l ON l.campaign_id=c.id
               GROUP BY c.id, c.name ORDER BY leads_count DESC, c.id DESC"""
        )]
        recent = [dict(row) for row in con.execute(
            """SELECT id,title,stage,city,created_at FROM leads
               ORDER BY created_at DESC, id DESC LIMIT 10"""
        )]
        due = [dict(row) for row in con.execute(
            """SELECT id,title,due_at,priority,buyer_id,lead_id FROM reminders
               WHERE status='pending' AND due_at<=? ORDER BY due_at ASC LIMIT 20""", (now_text,)
        )]
    for row in campaign_rows:
        row["converted_count"] = row["converted_count"] or 0
    return {
        "leads_total": leads_total, "buyers_total": buyers_total,
        "campaigns_total": campaigns_total, "interactions_total": interactions_total,
        "reminders_pending": reminders_pending, "reminders_overdue": reminders_overdue,
        "reminders_next_week": reminders_next_week, "leads_this_month": leads_this_month,
        "stages": stages, "campaigns": campaign_rows, "recent_leads": recent,
        "overdue_items": due,
    }


def export_report_csv(db_path: str | Path, destination: str | Path) -> Path:
    """خروجی CSV شامل آمار کلی، مراحل سرنخ و عملکرد کمپین‌ها."""
    data = dashboard_data(db_path)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["نوع گزارش", "شاخص", "مقدار"])
        for key, label in [
            ("leads_total", "کل سرنخ‌ها"), ("buyers_total", "کل خریداران"),
            ("campaigns_total", "کل کمپین‌ها"), ("interactions_total", "کل تعاملات"),
            ("reminders_pending", "یادآورهای باز"), ("reminders_overdue", "یادآورهای سررسیدشده"),
            ("reminders_next_week", "یادآورهای ۷ روز آینده"), ("leads_this_month", "سرنخ‌های ماه جاری")
        ]:
            writer.writerow(["خلاصه", label, data[key]])
        for row in data["stages"]:
            writer.writerow(["قیف سرنخ", row["label"], row["count"]])
        for row in data["campaigns"]:
            writer.writerow(["عملکرد کمپین", row["name"], f"سرنخ: {row['leads_count']} | تبدیل: {row['converted_count']}"])
    return path


class DashboardTab(ttk.Frame):
    """نمایش شاخص‌ها و گزارش‌های خلاصه؛ داده‌ها فقط از SQLite محلی خوانده می‌شوند."""

    def __init__(self, master, db_path: str | Path):
        super().__init__(master, padding=12)
        self.db_path = db_path
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="داشبورد عملکرد CRM", font=("Tahoma", 15, "bold")).pack(side="right")
        ttk.Button(top, text="به‌روزرسانی", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="خروجی CSV", command=self.export_csv).pack(side="left", padx=4)
        self.metrics = ttk.Frame(self)
        self.metrics.pack(fill="x", pady=10)
        self.metric_vars = {}
        metric_defs = [
            ("leads_total", "کل سرنخ‌ها"), ("buyers_total", "خریداران"),
            ("campaigns_total", "کمپین‌ها"), ("interactions_total", "تعاملات"),
            ("reminders_pending", "یادآورهای باز"), ("reminders_overdue", "سررسیدشده"),
            ("reminders_next_week", "۷ روز آینده"), ("leads_this_month", "سرنخ‌های ماه جاری"),
        ]
        for i, (key, label) in enumerate(metric_defs):
            cell = ttk.LabelFrame(self.metrics, text=label, padding=8)
            cell.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            var = tk.StringVar(value="۰")
            self.metric_vars[key] = var
            ttk.Label(cell, textvariable=var, font=("Tahoma", 16, "bold")).pack()
        for col in range(4):
            self.metrics.columnconfigure(col, weight=1)
        panes = ttk.Panedwindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=6)
        stage_frame = ttk.LabelFrame(panes, text="قیف وضعیت سرنخ‌ها", padding=6)
        campaign_frame = ttk.LabelFrame(panes, text="عملکرد کمپین‌ها", padding=6)
        panes.add(stage_frame, weight=1)
        panes.add(campaign_frame, weight=2)
        self.stage_tree = ttk.Treeview(stage_frame, columns=("stage", "count"), show="headings", height=10)
        self.stage_tree.heading("stage", text="مرحله")
        self.stage_tree.heading("count", text="تعداد")
        self.stage_tree.column("stage", width=150, anchor="e")
        self.stage_tree.column("count", width=70, anchor="center")
        self.stage_tree.pack(fill="both", expand=True)
        self.campaign_tree = ttk.Treeview(campaign_frame, columns=("name", "leads", "converted"), show="headings", height=10)
        for key, label, width in [("name", "کمپین", 190), ("leads", "سرنخ", 75), ("converted", "تبدیل", 75)]:
            self.campaign_tree.heading(key, text=label)
            self.campaign_tree.column(key, width=width, anchor="e")
        self.campaign_tree.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="آمار از پایگاه داده محلی خوانده می‌شود.")
        ttk.Label(self, textvariable=self.status, foreground="#64748b").pack(anchor="e", pady=4)

    def refresh(self):
        try:
            data = dashboard_data(self.db_path)
            for key, var in self.metric_vars.items():
                var.set(f"{data[key]:,}".translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
            for tree in (self.stage_tree, self.campaign_tree):
                for item in tree.get_children():
                    tree.delete(item)
            for row in data["stages"]:
                self.stage_tree.insert("", "end", values=(row["label"], row["count"]))
            for row in data["campaigns"]:
                self.campaign_tree.insert("", "end", values=(row["name"], row["leads_count"], row["converted_count"]))
            self.status.set(f"یادآور سررسیدشده: {data['reminders_overdue']} | آخرین به‌روزرسانی: {_now_iso()}")
        except Exception as exc:
            messagebox.showerror("خطای داشبورد", str(exc))

    def export_csv(self):
        destination = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="agent_divar_report.csv"
        )
        if not destination:
            return
        try:
            path = export_report_csv(self.db_path, destination)
            messagebox.showinfo("گزارش آماده شد", f"گزارش ذخیره شد:\n{path}")
        except Exception as exc:
            messagebox.showerror("خطای خروجی", str(exc))

# -*- coding: utf-8 -*-
"""ثبت تعاملات و یادآورهای CRM؛ بدون ارسال پیام یا تماس خودکار."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

from storage import connect, record_event


def _utc_iso(value: str | datetime | None = None) -> str:
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise ValueError("تاریخ باید با قالب ISO مانند 2026-11-25T15:30 وارد شود.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _validate_owner(buyer_id: int | None, lead_id: int | None) -> None:
    if (buyer_id is None) == (lead_id is None):
        raise ValueError("دقیقاً یکی از شناسه خریدار یا سرنخ باید مشخص شود.")


def add_interaction(db_path: str | Path, *, interaction_type: str, summary: str,
                    buyer_id: int | None = None, lead_id: int | None = None,
                    outcome: str = "", occurred_at: str | datetime | None = None) -> int:
    _validate_owner(buyer_id, lead_id)
    kind, description = interaction_type.strip(), summary.strip()
    if kind not in {"تماس", "پیام", "جلسه", "یادداشت"}:
        raise ValueError("نوع تعامل نامعتبر است.")
    if not description:
        raise ValueError("شرح تعامل الزامی است.")
    with connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO interaction_logs
               (buyer_id, lead_id, interaction_type, summary, outcome, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (buyer_id, lead_id, kind, description, outcome.strip(), _utc_iso(occurred_at)),
        )
        interaction_id = int(cur.lastrowid)
    record_event(db_path, "interaction.created", entity_type="interaction",
                 entity_id=interaction_id, message="تعامل مشتری ثبت شد")
    return interaction_id


def list_interactions(db_path: str | Path, *, buyer_id: int | None = None,
                      lead_id: int | None = None) -> list[dict]:
    _validate_owner(buyer_id, lead_id)
    column, owner_id = ("buyer_id", buyer_id) if buyer_id is not None else ("lead_id", lead_id)
    with connect(db_path) as con:
        rows = con.execute(
            f"SELECT * FROM interaction_logs WHERE {column}=? ORDER BY occurred_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_reminder(db_path: str | Path, *, title: str, due_at: str | datetime,
                 buyer_id: int | None = None, lead_id: int | None = None,
                 priority: str = "normal") -> int:
    _validate_owner(buyer_id, lead_id)
    label = title.strip()
    if not label:
        raise ValueError("عنوان یادآور الزامی است.")
    if priority not in {"low", "normal", "high"}:
        raise ValueError("اولویت یادآور نامعتبر است.")
    due = _utc_iso(due_at)
    with connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO reminders(buyer_id, lead_id, title, due_at, priority)
               VALUES (?, ?, ?, ?, ?)""",
            (buyer_id, lead_id, label, due, priority),
        )
        reminder_id = int(cur.lastrowid)
    record_event(db_path, "reminder.created", entity_type="reminder",
                 entity_id=reminder_id, message="یادآور ثبت شد")
    return reminder_id


def update_reminder_status(db_path: str | Path, reminder_id: int, status: str) -> None:
    if status not in {"done", "cancelled"}:
        raise ValueError("وضعیت نهایی باید done یا cancelled باشد.")
    with connect(db_path) as con:
        cur = con.execute(
            """UPDATE reminders SET status=?, completed_at=?
               WHERE id=? AND status='pending'""",
            (status, _utc_iso() if status == "done" else None, reminder_id),
        )
        if cur.rowcount != 1:
            raise ValueError("یادآور پیدا نشد یا قبلاً تعیین تکلیف شده است.")
    record_event(db_path, "reminder.updated", entity_type="reminder",
                 entity_id=reminder_id, message=f"وضعیت یادآور: {status}")


def list_reminders(db_path: str | Path, *, status: str | None = "pending",
                   due_before: str | datetime | None = None) -> list[dict]:
    clauses, params = [], []
    if status is not None:
        if status not in {"pending", "done", "cancelled"}:
            raise ValueError("فیلتر وضعیت نامعتبر است.")
        clauses.append("status=?")
        params.append(status)
    if due_before is not None:
        clauses.append("due_at<=?")
        params.append(_utc_iso(due_before))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM reminders" + where + " ORDER BY due_at ASC, id ASC",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


class FollowUpTab(ttk.Frame):
    """رابط ساده ثبت تعامل و یادآور؛ تمام عملیات دستی و قابل مشاهده‌اند."""

    def __init__(self, master, db_path: str | Path):
        super().__init__(master, padding=12)
        self.db_path = db_path
        self._build()
        self.refresh()

    def _build(self):
        form = ttk.LabelFrame(self, text="ثبت تعامل یا یادآور", padding=10)
        form.pack(fill="x")
        self.owner_kind = tk.StringVar(value="buyer")
        self.owner_id = tk.StringVar()
        self.kind = tk.StringVar(value="تماس")
        self.summary = tk.StringVar()
        self.outcome = tk.StringVar()
        self.due_title = tk.StringVar()
        self.due_at = tk.StringVar()
        self.priority = tk.StringVar(value="normal")
        self._field(form, "نوع پرونده (buyer یا lead)", self.owner_kind, 0, 0)
        self._field(form, "شناسه پرونده", self.owner_id, 0, 1)
        self._field(form, "نوع تعامل", self.kind, 1, 0)
        self._field(form, "شرح تعامل", self.summary, 1, 1)
        self._field(form, "نتیجه", self.outcome, 2, 0)
        self._field(form, "عنوان یادآور", self.due_title, 2, 1)
        self._field(form, "موعد ISO (مثلاً 2026-11-26T10:00)", self.due_at, 3, 0)
        self._field(form, "اولویت (low/normal/high)", self.priority, 3, 1)
        actions = ttk.Frame(form)
        actions.grid(row=4, column=0, columnspan=2, sticky="e", pady=6)
        ttk.Button(actions, text="ثبت تعامل", command=self.save_interaction).pack(side="right", padx=4)
        ttk.Button(actions, text="ثبت یادآور", command=self.save_reminder).pack(side="right", padx=4)
        ttk.Button(actions, text="تازه‌سازی", command=self.refresh).pack(side="right", padx=4)
        self.tree = ttk.Treeview(self, columns=("id", "kind", "title", "due", "priority", "status"),
                                 show="headings", height=12)
        for col, label, width in [
            ("id", "شناسه", 60), ("kind", "نوع", 100), ("title", "شرح / عنوان", 360),
            ("due", "زمان", 190), ("priority", "اولویت", 100), ("status", "وضعیت", 100)
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="e")
        self.tree.pack(fill="both", expand=True, pady=10)
        buttons = ttk.Frame(self)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="تکمیل یادآور", command=lambda: self.finish("done")).pack(side="right", padx=4)
        ttk.Button(buttons, text="لغو یادآور", command=lambda: self.finish("cancelled")).pack(side="right", padx=4)
        ttk.Button(buttons, text="نمایش سررسیدشده‌ها", command=self.show_due).pack(side="right", padx=4)

    @staticmethod
    def _field(parent, label, variable, row, col):
        cell = ttk.Frame(parent)
        cell.grid(row=row, column=col, sticky="ew", padx=5, pady=3)
        ttk.Label(cell, text=label).pack(anchor="e")
        ttk.Entry(cell, textvariable=variable, justify="right").pack(fill="x")
        parent.columnconfigure(col, weight=1)

    def _owner(self):
        try:
            identifier = int(self.owner_id.get())
            if identifier <= 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError("شناسه پرونده باید عدد صحیح مثبت باشد.") from exc
        if self.owner_kind.get().strip() == "buyer":
            return {"buyer_id": identifier}
        if self.owner_kind.get().strip() == "lead":
            return {"lead_id": identifier}
        raise ValueError("نوع پرونده فقط buyer یا lead است.")

    def save_interaction(self):
        try:
            add_interaction(self.db_path, interaction_type=self.kind.get(),
                            summary=self.summary.get(), outcome=self.outcome.get(), **self._owner())
            self.summary.set("")
            self.refresh()
        except (ValueError, Exception) as exc:
            messagebox.showwarning("ثبت تعامل", str(exc))

    def save_reminder(self):
        try:
            add_reminder(self.db_path, title=self.due_title.get(), due_at=self.due_at.get(),
                         priority=self.priority.get(), **self._owner())
            self.due_title.set("")
            self.refresh()
        except Exception as exc:
            messagebox.showwarning("ثبت یادآور", str(exc))

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in list_reminders(self.db_path, status="pending"):
            self.tree.insert("", "end", iid=f"r{row['id']}",
                             values=(row["id"], "یادآور", row["title"], row["due_at"],
                                     row["priority"], row["status"]))

    def show_due(self):
        rows = list_reminders(self.db_path, status="pending", due_before=_utc_iso())
        messagebox.showinfo("یادآورهای سررسیدشده",
                            "\n".join(f"#{r['id']} — {r['title']}" for r in rows) or "مورد سررسیدشده‌ای وجود ندارد.")

    def finish(self, status):
        selected = self.tree.selection()
        if not selected or not selected[0].startswith("r"):
            messagebox.showinfo("انتخاب یادآور", "ابتدا یک یادآور انتخاب کنید.")
            return
        try:
            update_reminder_status(self.db_path, int(selected[0][1:]), status)
            self.refresh()
        except ValueError as exc:
            messagebox.showwarning("وضعیت یادآور", str(exc))

# -*- coding: utf-8 -*-
"""مدیریت سرنخ‌های مجاز و رضایت‌محور دیوار — نسخه پایه ویندوز"""
from __future__ import annotations
import sqlite3
import json
import webbrowser
import subprocess
import sys
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from storage import connect as open_database, initialize as initialize_database, record_event
from search_engine import SearchValidationError, build_search_plan
from listing_analyzer import Listing, BuyerCriteria, analyze_listing
from followup_manager import FollowUpTab
from dashboard import DashboardTab
from media_tab import PropertyMediaTab
from backup_tab import BackupTab
from settings_manager import load_settings
from settings_tab import SettingsTab
from app_paths import (
    RESOURCE_DIR as ROOT, DATA_DIR as DATA, DATABASE_PATH as DB,
    SETTINGS_PATH as SETTINGS_FILE, BROWSER_STATUS_PATH as BROWSER_STATUS,
    ensure_data_dirs,
)

# در حالت پنجره‌ای PyInstaller ممکن است stdout و stderr تعریف نشده باشند.
if getattr(sys, "frozen", False):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

try:
    ensure_data_dirs()
except Exception as exc:
    if getattr(sys, "frozen", False):
        messagebox.showerror(
            "خطا در انتقال اطلاعات",
            "انتقال اطلاعات نسخه قبلی انجام نشد. فایل‌های قدیمی دست‌نخورده باقی مانده‌اند. "
            "پوشه data را بررسی کنید یا از پشتیبان استفاده کنید.\n\n"
            f"جزئیات: {type(exc).__name__}",
        )
    raise

def connect():
    """اتصال سازگار با نسخه‌های قبلی از طریق لایه ذخیره‌سازی مرکزی."""
    return open_database(DB)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("مدیریت سرنخ دیوار | نسخه پایه")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.settings = load_settings(SETTINGS_FILE)
        self.option_add("*Font", f"Tahoma {self.settings['font_size']}")
        initialize_database(DB)
        self.campaign_id = None
        self.browser_process = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._style()
        self._build()
        self.refresh_campaigns()
        self.refresh_leads()

    def _style(self):
        s=ttk.Style(self)
        try: s.theme_use(self.settings["theme"])
        except tk.TclError: pass
        s.configure("Treeview", rowheight=28, font=("Tahoma",self.settings["font_size"]-1))
        s.configure("Treeview.Heading", font=("Tahoma",self.settings["font_size"]-1,"bold"))
        s.configure("TButton", padding=7)
        s.configure("Header.TLabel", font=("Tahoma",17,"bold"), foreground="#164e63")

    def _build(self):
        header=ttk.Frame(self,padding=14); header.pack(fill="x")
        ttk.Label(header,text="سامانه مدیریت سرنخ‌های دیوار",style="Header.TLabel").pack(side="right")
        ttk.Label(header,text="نسخه پایه • ذخیره محلی • خروجی اکسل",foreground="#64748b").pack(side="left")
        self.tabs=ttk.Notebook(self); self.tabs.pack(fill="both",expand=True,padx=12,pady=8)
        self.camp_tab=ttk.Frame(self.tabs,padding=12); self.tabs.add(self.camp_tab,text="کمپین‌ها و جستجو")
        self.lead_tab=ttk.Frame(self.tabs,padding=12); self.tabs.add(self.lead_tab,text="بانک سرنخ‌ها")
        self._build_campaign_tab(); self._build_leads_tab()
        self.buyer_tab=ttk.Frame(self.tabs,padding=12); self.tabs.add(self.buyer_tab,text="مشتریان خریدار")
        self._build_buyers_tab()
        self.followup_tab=FollowUpTab(self.tabs, DB); self.tabs.add(self.followup_tab,text="تعاملات و یادآورها")
        self.dashboard_tab=DashboardTab(self.tabs, DB); self.tabs.add(self.dashboard_tab,text="داشبورد و گزارش‌ها")
        self.media_tab=PropertyMediaTab(self.tabs, DB, DATA / "property-media"); self.tabs.add(self.media_tab,text="تصاویر و مدارک ملک")
        self.backup_tab=BackupTab(self.tabs, DB, DATA / "property-media"); self.tabs.add(self.backup_tab,text="پشتیبان‌گیری و بازیابی")
        self.settings_tab=SettingsTab(self.tabs, SETTINGS_FILE, DB, self.settings, self.apply_settings)
        self.tabs.add(self.settings_tab,text="تنظیمات و عیب‌یابی")
        footer=ttk.Label(self,text="یادآوری: پیام تبلیغاتی ناخواسته در چت دیوار ارسال نکنید. پیام‌رسانی فقط در جریان مجاز و با رضایت/درخواست مخاطب انجام شود.",foreground="#9a3412",padding=8)
        footer.pack(fill="x")

    def apply_settings(self, settings):
        self.settings = dict(settings)
        self.option_add("*Font", f"Tahoma {self.settings['font_size']}")
        style = ttk.Style(self)
        try:
            style.theme_use(self.settings["theme"])
        except tk.TclError:
            style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Tahoma", self.settings["font_size"] - 1))
        style.configure("Treeview.Heading", font=("Tahoma", self.settings["font_size"] - 1, "bold"))

    def _build_campaign_tab(self):
        f=self.camp_tab
        form=ttk.LabelFrame(f,text="تعریف کمپین",padding=12); form.pack(fill="x")
        self.c_name=tk.StringVar(); self.c_category=tk.StringVar(); self.c_city=tk.StringVar(value="دزفول"); self.c_keywords=tk.StringVar()
        self.c_age_filter=tk.StringVar(value="۷ روز گذشته")
        self.age_filter_hours={"همه آگهی‌ها":0,"۳ ساعت گذشته":3,"۱۲ ساعت گذشته":12,"۱ روز گذشته":24,"۳ روز گذشته":72,"۷ روز گذشته":168}
        fields=[("نام کمپین",self.c_name),("حوزه / دسته",self.c_category),("کد شهر در دیوار (مثلاً dezful)",self.c_city),("کلمات کلیدی (با ویرگول)",self.c_keywords)]
        for i,(label,var) in enumerate(fields):
            r,c=divmod(i,2)
            cell=ttk.Frame(form); cell.grid(row=r,column=c,sticky="ew",padx=6,pady=5)
            ttk.Label(cell,text=label).pack(anchor="e")
            ttk.Entry(cell,textvariable=var,justify="right").pack(fill="x")
        form.columnconfigure(0,weight=1); form.columnconfigure(1,weight=1)
        age_cell=ttk.Frame(form); age_cell.grid(row=2,column=0,columnspan=2,sticky="ew",padx=6,pady=(8,2))
        ttk.Label(age_cell,text="فیلتر تاریخ انتشار آگهی").pack(anchor="e")
        ttk.Combobox(age_cell,textvariable=self.c_age_filter,values=list(self.age_filter_hours),state="readonly",justify="right").pack(fill="x")
        ttk.Label(form,text="متن پیام پیشنهادی (صرفاً برای پاسخ به درخواست/مکالمه مجاز؛ نه تبلیغ سرد):").grid(row=3,column=0,columnspan=2,sticky="e",padx=6,pady=(8,2))
        self.c_message=tk.Text(form,height=3,wrap="word"); self.c_message.grid(row=4,column=0,columnspan=2,sticky="ew",padx=6)
        actions=ttk.Frame(form); actions.grid(row=5,column=0,columnspan=2,sticky="e",pady=8)
        ttk.Button(actions,text="ذخیره کمپین",command=self.save_campaign).pack(side="right",padx=4)
        ttk.Button(actions,text="اجرای زنده در مرورگر ویندوز",command=self.open_search).pack(side="right",padx=4)
        ttk.Button(actions,text="بستن مرورگر",command=self.close_browser).pack(side="right",padx=4)
        ttk.Button(actions,text="پاک‌کردن فرم",command=self.clear_campaign).pack(side="right",padx=4)
        lower=ttk.LabelFrame(f,text="کمپین‌های ذخیره‌شده",padding=8); lower.pack(fill="both",expand=True,pady=12)
        self.campaign_tree=ttk.Treeview(lower,columns=("id","name","category","city","age_filter","keywords"),show="headings",height=8)
        for col,title,w in [("id","شناسه",60),("name","نام کمپین",190),("category","حوزه",140),("city","شهر",100),("age_filter","تاریخ انتشار",130),("keywords","کلمات کلیدی",340)]:
            self.campaign_tree.heading(col,text=title); self.campaign_tree.column(col,width=w,anchor="e")
        self.campaign_tree.pack(fill="both",expand=True)
        self.campaign_tree.bind("<<TreeviewSelect>>",self.select_campaign)
        ttk.Label(f,text="جستجو در مرورگر به‌صورت هدایت به صفحه دیوار انجام می‌شود؛ ثبت اطلاعات آگهی در این نسخه با ورود دستی و بدون استخراج خودکار اطلاعات شخصی است.",foreground="#475569").pack(anchor="e")


    def _build_buyers_tab(self):
        f=self.buyer_tab
        form=ttk.LabelFrame(f,text="پروفایل خریدار",padding=12); form.pack(fill="x")
        self.b_name=tk.StringVar(); self.b_contact=tk.StringVar(); self.b_budget_saved=tk.StringVar()
        self.b_min_saved=tk.StringVar(); self.b_max_saved=tk.StringVar(); self.b_rooms_saved=tk.StringVar()
        self.b_location_saved=tk.StringVar(); self.b_features_saved=tk.StringVar()
        fields=[("نام خریدار",self.b_name),("راه تماس مجاز",self.b_contact),("سقف بودجه",self.b_budget_saved),
                ("حداقل متراژ",self.b_min_saved),("حداکثر متراژ",self.b_max_saved),("تعداد اتاق",self.b_rooms_saved),
                ("محدوده",self.b_location_saved),("امکانات (با ویرگول)",self.b_features_saved)]
        for i,(label,var) in enumerate(fields):
            rr,cc=divmod(i,2); cell=ttk.Frame(form); cell.grid(row=rr,column=cc,sticky="ew",padx=5,pady=4)
            ttk.Label(cell,text=label).pack(anchor="e"); ttk.Entry(cell,textvariable=var,justify="right").pack(fill="x")
        form.columnconfigure(0,weight=1); form.columnconfigure(1,weight=1)
        ttk.Label(form,text="یادداشت").grid(row=4,column=0,columnspan=2,sticky="e")
        self.b_notes=tk.Text(form,height=2); self.b_notes.grid(row=5,column=0,columnspan=2,sticky="ew")
        actions=ttk.Frame(form); actions.grid(row=6,column=0,columnspan=2,sticky="e",pady=6)
        ttk.Button(actions,text="ذخیره",command=self.save_buyer).pack(side="right",padx=4)
        ttk.Button(actions,text="حذف",command=self.delete_buyer).pack(side="right",padx=4)
        ttk.Button(actions,text="اعمال معیارها در تحلیل",command=self.apply_buyer).pack(side="right",padx=4)
        self.buyer_tree=ttk.Treeview(f,columns=("id","name","budget","area","rooms","location"),show="headings")
        for col,title,width in [("id","شناسه",55),("name","نام",180),("budget","بودجه",140),("area","متراژ",130),("rooms","اتاق",70),("location","محدوده",180)]:
            self.buyer_tree.heading(col,text=title); self.buyer_tree.column(col,width=width,anchor="e")
        self.buyer_tree.pack(fill="both",expand=True,pady=10)
        self.buyer_tree.bind("<<TreeviewSelect>>",self.select_buyer)
        self.refresh_buyers()

    def save_buyer(self):
        if not self.b_name.get().strip():
            messagebox.showwarning("ورودی ناقص","نام خریدار الزامی است."); return
        try:
            budget=self._optional_int(self.b_budget_saved.get(),"بودجه")
            minimum=self._optional_float(self.b_min_saved.get(),"حداقل متراژ")
            maximum=self._optional_float(self.b_max_saved.get(),"حداکثر متراژ")
            rooms=self._optional_int(self.b_rooms_saved.get(),"اتاق")
            if minimum is not None and maximum is not None and minimum>maximum:
                raise ValueError("حداقل متراژ از حداکثر متراژ بیشتر است.")
        except ValueError as exc:
            messagebox.showwarning("مقدار نامعتبر",str(exc)); return
        features=[x.strip() for x in self.b_features_saved.get().split(",") if x.strip()]
        values=(self.b_name.get().strip(),self.b_contact.get().strip(),budget,minimum,maximum,rooms,
                self.b_location_saved.get().strip(),json.dumps(features,ensure_ascii=False),
                self.b_notes.get("1.0","end").strip())
        selected=self.buyer_tree.selection()
        with connect() as con:
            if selected:
                buyer_id=int(self.buyer_tree.item(selected[0],"values")[0])
                con.execute("""UPDATE buyer_profiles SET name=?,public_contact=?,max_budget=?,min_area=?,max_area=?,
                    rooms=?,location=?,required_features_json=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",values+(buyer_id,))
            else:
                con.execute("""INSERT INTO buyer_profiles(name,public_contact,max_budget,min_area,max_area,rooms,
                    location,required_features_json,notes) VALUES(?,?,?,?,?,?,?,?,?)""",values)
        record_event(DB,"buyer.saved",entity_type="buyer",message="پروفایل خریدار ذخیره شد")
        self.refresh_buyers()

    def refresh_buyers(self):
        for item in self.buyer_tree.get_children(): self.buyer_tree.delete(item)
        with connect() as con:
            rows=con.execute("SELECT id,name,max_budget,min_area,max_area,rooms,location FROM buyer_profiles ORDER BY updated_at DESC,id DESC").fetchall()
        for row in rows:
            area=f"{row['min_area'] if row['min_area'] is not None else '—'} تا {row['max_area'] if row['max_area'] is not None else '—'}"
            self.buyer_tree.insert("","end",values=(row["id"],row["name"],row["max_budget"] if row["max_budget"] is not None else "—",area,row["rooms"] if row["rooms"] is not None else "—",row["location"] or "—"))

    def select_buyer(self,_event=None):
        selected=self.buyer_tree.selection()
        if not selected:return
        buyer_id=int(self.buyer_tree.item(selected[0],"values")[0])
        with connect() as con: row=con.execute("SELECT * FROM buyer_profiles WHERE id=?",(buyer_id,)).fetchone()
        if row is None:return
        self.b_name.set(row["name"]); self.b_contact.set(row["public_contact"])
        self.b_budget_saved.set(row["max_budget"] if row["max_budget"] is not None else "")
        self.b_min_saved.set(row["min_area"] if row["min_area"] is not None else "")
        self.b_max_saved.set(row["max_area"] if row["max_area"] is not None else "")
        self.b_rooms_saved.set(row["rooms"] if row["rooms"] is not None else "")
        self.b_location_saved.set(row["location"])
        self.b_features_saved.set(", ".join(json.loads(row["required_features_json"] or "[]")))
        self.b_notes.delete("1.0","end"); self.b_notes.insert("1.0",row["notes"])

    def delete_buyer(self):
        selected=self.buyer_tree.selection()
        if not selected:return
        if not messagebox.askyesno("حذف خریدار","پروفایل انتخاب‌شده حذف شود؟"):return
        buyer_id=int(self.buyer_tree.item(selected[0],"values")[0])
        with connect() as con: con.execute("DELETE FROM buyer_profiles WHERE id=?",(buyer_id,))
        record_event(DB,"buyer.deleted",entity_type="buyer",entity_id=buyer_id,message="پروفایل خریدار حذف شد")
        self.refresh_buyers()

    def apply_buyer(self):
        selected=self.buyer_tree.selection()
        if not selected:
            messagebox.showinfo("انتخاب خریدار","ابتدا خریدار را انتخاب کنید."); return
        self.select_buyer()
        self.b_budget.set(self.b_budget_saved.get()); self.b_min_area.set(self.b_min_saved.get())
        self.b_max_area.set(self.b_max_saved.get()); self.b_rooms.set(self.b_rooms_saved.get())
        self.b_location.set(self.b_location_saved.get()); self.b_features.set(self.b_features_saved.get())
        self.tabs.select(self.lead_tab)

    def compare_selected_listings(self):
        selected=self.lead_tree.selection()
        if len(selected)<2:
            messagebox.showinfo("انتخاب آگهی","حداقل دو آگهی را با Ctrl انتخاب کنید."); return
        try:
            criteria=BuyerCriteria(max_budget=self._optional_int(self.b_budget.get(),"بودجه"),
                min_area=self._optional_float(self.b_min_area.get(),"حداقل متراژ"),
                max_area=self._optional_float(self.b_max_area.get(),"حداکثر متراژ"),
                rooms=self._optional_int(self.b_rooms.get(),"اتاق"),location=self.b_location.get().strip(),
                required_features=tuple(x.strip() for x in self.b_features.get().split(",") if x.strip()))
            ranked=[]
            with connect() as con:
                for item in selected:
                    lead_id=int(self.lead_tree.item(item,"values")[0])
                    row=con.execute("SELECT title,price,area,rooms,location,features_json FROM leads WHERE id=?",(lead_id,)).fetchone()
                    if row is None:continue
                    listing=Listing(title=row["title"],price=row["price"],area=row["area"],rooms=row["rooms"],
                        location=row["location"] or "",features=tuple(json.loads(row["features_json"] or "[]")))
                    result=analyze_listing(listing,criteria)
                    ranked.append((result.score,listing.title,result.status))
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            messagebox.showwarning("معیار نامعتبر",str(exc)); return
        ranked.sort(key=lambda x:(x[0] is not None,x[0] if x[0] is not None else -1),reverse=True)
        lines=["رتبه‌بندی آگهی‌های انتخاب‌شده:"]
        for i,(score,title,status) in enumerate(ranked,1):
            lines.append(f"{i}. {title} — {score if score is not None else 'اطلاعات ناکافی'} — {status}")
        self.analysis_result.configure(text="\n".join(lines))

    def _build_leads_tab(self):
        f=self.lead_tab
        form=ttk.LabelFrame(f,text="ثبت سرنخ",padding=12); form.pack(fill="x")
        self.l_url=tk.StringVar(); self.l_title=tk.StringVar(); self.l_category=tk.StringVar(); self.l_city=tk.StringVar(); self.l_contact=tk.StringVar(); self.l_consent=tk.StringVar(value="نامشخص"); self.l_stage=tk.StringVar(value="جدید")
        self.l_price=tk.StringVar(); self.l_area=tk.StringVar(); self.l_rooms=tk.StringVar(); self.l_location=tk.StringVar(); self.l_features=tk.StringVar()
        self.b_budget=tk.StringVar(); self.b_min_area=tk.StringVar(); self.b_max_area=tk.StringVar(); self.b_rooms=tk.StringVar(); self.b_location=tk.StringVar(); self.b_features=tk.StringVar()
        items=[("لینک آگهی",self.l_url),("عنوان آگهی",self.l_title),("حوزه",self.l_category),("شهر",self.l_city),("راه تماس عمومی/مجاز",self.l_contact)]
        for i,(label,var) in enumerate(items):
            r,c=divmod(i,2); cell=ttk.Frame(form); cell.grid(row=r,column=c,sticky="ew",padx=6,pady=4)
            ttk.Label(cell,text=label).pack(anchor="e"); ttk.Entry(cell,textvariable=var,justify="right").pack(fill="x")
        r=3
        listing_fields=[("قیمت کل (تومان)",self.l_price),("متراژ (متر)",self.l_area),("تعداد اتاق",self.l_rooms),("محله / محدوده",self.l_location),("امکانات (با ویرگول)",self.l_features)]
        for i,(label,var) in enumerate(listing_fields):
            rr,cc=divmod(i,2); cell=ttk.Frame(form); cell.grid(row=rr+3,column=cc,sticky="ew",padx=6,pady=4)
            ttk.Label(cell,text=label).pack(anchor="e"); ttk.Entry(cell,textvariable=var,justify="right").pack(fill="x")
        cell=ttk.Frame(form); cell.grid(row=6,column=0,sticky="ew",padx=6,pady=4)
        ttk.Label(cell,text="وضعیت رضایت").pack(anchor="e")
        ttk.Combobox(cell,textvariable=self.l_consent,values=["نامشخص","رضایت ثبت‌شده","درخواست تماس داده","عدم رضایت"],state="readonly").pack(fill="x")
        cell=ttk.Frame(form); cell.grid(row=6,column=1,sticky="ew",padx=6,pady=4)
        ttk.Label(cell,text="مرحله فروش").pack(anchor="e")
        ttk.Combobox(cell,textvariable=self.l_stage,values=["جدید","بررسی‌شده","مشتری علاقه‌مند","مشتری","عدم تمایل","بایگانی"],state="readonly").pack(fill="x")
        form.columnconfigure(0,weight=1); form.columnconfigure(1,weight=1)
        ttk.Label(form,text="یادداشت").grid(row=7,column=0,columnspan=2,sticky="e",padx=6)
        self.l_notes=tk.Text(form,height=2,wrap="word"); self.l_notes.grid(row=8,column=0,columnspan=2,sticky="ew",padx=6)
        btns=ttk.Frame(form); btns.grid(row=9,column=0,columnspan=2,sticky="e",pady=7)
        ttk.Button(btns,text="ذخیره سرنخ",command=self.save_lead).pack(side="right",padx=4)
        ttk.Button(btns,text="بازکردن آگهی انتخاب‌شده",command=self.open_selected).pack(side="right",padx=4)
        ttk.Button(btns,text="خروجی اکسل",command=self.export_excel).pack(side="right",padx=4)
        ttk.Button(btns,text="به‌روزرسانی",command=self.refresh_leads).pack(side="right",padx=4)
        criteria=ttk.LabelFrame(f,text="تحلیل تطبیق آگهی انتخاب‌شده با نیاز خریدار",padding=10); criteria.pack(fill="x",pady=6)
        criteria_fields=[("سقف بودجه (تومان)",self.b_budget),("حداقل متراژ",self.b_min_area),("حداکثر متراژ",self.b_max_area),("تعداد اتاق",self.b_rooms),("محدوده دلخواه",self.b_location),("امکانات موردنیاز (ویرگول)",self.b_features)]
        for i,(label,var) in enumerate(criteria_fields):
            rr,cc=divmod(i,3); cell=ttk.Frame(criteria); cell.grid(row=rr,column=cc,sticky="ew",padx=5,pady=4)
            ttk.Label(cell,text=label).pack(anchor="e"); ttk.Entry(cell,textvariable=var,justify="right").pack(fill="x")
        for cc in range(3): criteria.columnconfigure(cc,weight=1)
        analysis_actions=ttk.Frame(criteria); analysis_actions.grid(row=2,column=0,columnspan=3,sticky="e",pady=4)
        ttk.Button(analysis_actions,text="تحلیل آگهی انتخاب‌شده",command=self.analyze_selected_listing).pack(side="right",padx=4)
        ttk.Button(analysis_actions,text="مقایسه چند آگهی",command=self.compare_selected_listings).pack(side="right",padx=4)
        self.analysis_result=ttk.Label(criteria,text="برای تحلیل، یک آگهی انتخاب و معیارهای خریدار را وارد کنید.",justify="right",wraplength=900)
        self.analysis_result.grid(row=3,column=0,columnspan=3,sticky="e",padx=5,pady=5)
        listing=ttk.LabelFrame(f,text="سرنخ‌های ثبت‌شده",padding=8); listing.pack(fill="both",expand=True,pady=10)
        cols=("id","title","category","city","contact","consent","stage","url")
        self.lead_tree=ttk.Treeview(listing,columns=cols,show="headings",selectmode="extended")
        titles={"id":"شناسه","title":"عنوان آگهی","category":"حوزه","city":"شهر","contact":"راه تماس","consent":"رضایت","stage":"وضعیت","url":"لینک"}
        widths={"id":55,"title":220,"category":100,"city":90,"contact":140,"consent":115,"stage":110,"url":300}
        for col in cols:
            self.lead_tree.heading(col,text=titles[col]); self.lead_tree.column(col,width=widths[col],anchor="e")
        self.lead_tree.pack(fill="both",expand=True)
        self.lead_tree.bind("<<TreeviewSelect>>",self._select_lead)

    def save_campaign(self):
        name=self.c_name.get().strip()
        if not name: messagebox.showwarning("ورودی ناقص","نام کمپین را وارد کنید."); return
        values=(name,self.c_category.get().strip(),self.c_city.get().strip(),self.c_keywords.get().strip(),self.c_message.get("1.0","end").strip(),self.age_filter_hours[self.c_age_filter.get()])
        with connect() as con:
            if self.campaign_id:
                con.execute("UPDATE campaigns SET name=?,category=?,city=?,keywords=?,message_template=?,published_within_hours=? WHERE id=?",values+(self.campaign_id,))
            else:
                cur=con.execute("INSERT INTO campaigns(name,category,city,keywords,message_template,published_within_hours) VALUES(?,?,?,?,?,?)",values)
                self.campaign_id=cur.lastrowid
        record_event(
            DB, "campaign.saved", entity_type="campaign",
            entity_id=self.campaign_id, message="کمپین ذخیره شد",
        )
        self.refresh_campaigns(); messagebox.showinfo("ذخیره شد","کمپین ذخیره شد.")

    def clear_campaign(self):
        for v in (self.c_name,self.c_category,self.c_keywords): v.set("")
        self.c_city.set("دزفول"); self.c_age_filter.set("۷ روز گذشته"); self.c_message.delete("1.0","end"); self.campaign_id=None

    def refresh_campaigns(self):
        for x in self.campaign_tree.get_children(): self.campaign_tree.delete(x)
        with connect() as con:
            for row in con.execute("SELECT id,name,category,city,published_within_hours,keywords FROM campaigns ORDER BY id DESC"):
                hours=row[4]
                age_label=next((label for label,value in self.age_filter_hours.items() if value==hours),"۷ روز گذشته")
                self.campaign_tree.insert("","end",values=(row[0],row[1],row[2],row[3],age_label,row[5]))

    def select_campaign(self,_event=None):
        selected=self.campaign_tree.selection()
        if not selected:return
        vals=self.campaign_tree.item(selected[0],"values")
        self.campaign_id=int(vals[0])
        with connect() as con:
            row=con.execute("SELECT name,category,city,keywords,message_template,published_within_hours FROM campaigns WHERE id=?",(self.campaign_id,)).fetchone()
        self.c_name.set(row[0]); self.c_category.set(row[1]); self.c_city.set(row[2]); self.c_keywords.set(row[3])
        self.c_age_filter.set(next((label for label,value in self.age_filter_hours.items() if value==row[5]),"۷ روز گذشته"))
        self.c_message.delete("1.0","end"); self.c_message.insert("1.0",row[4])

    def open_search(self):
        try:
            plan = build_search_plan(
                city=self.c_city.get(),
                keywords=self.c_keywords.get(),
                category=self.c_category.get(),
                published_within_hours=self.age_filter_hours[self.c_age_filter.get()],
            )
        except SearchValidationError as exc:
            messagebox.showwarning("معیار جستجوی نامعتبر", str(exc))
            return
        url = plan.url
        runner=ROOT / "browser_runner.py"
        if self.browser_process and self.browser_process.poll() is None:
            status = self._read_browser_status()
            if status and status.get("pid") == self.browser_process.pid and status.get("state") in ("closing", "closed"):
                self._terminate_browser_tree()
            else:
                try:
                    self.browser_process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    pass
            if self.browser_process.poll() is None:
                messagebox.showinfo("مرورگر فعال است","مرورگر هنوز باز است. ابتدا پنجره مرورگر را ببندید و چند لحظه صبر کنید.")
                return
            self.browser_process = None
        try:
            if getattr(sys, "frozen", False):
                command = [sys.executable, "--browser-runner", url]
                working_directory = str(Path(sys.executable).resolve().parent)
            else:
                command = [sys.executable, str(runner), url]
                working_directory = str(ROOT)
            self.browser_process=subprocess.Popen(command,cwd=working_directory)
            messagebox.showinfo("مرورگر زنده","مرورگر قابل‌مشاهده باز می‌شود. می‌توانید با موس و کیبورد خودتان کار کنید.\\n\\n" + " ".join(plan.notes))
        except Exception as exc:
            messagebox.showerror("خطای اجرا",f"اجرای مرورگر ناموفق بود:\\n{exc}")

    def close_browser(self):
        """مرورگر و runner متعلق به همین اجرای برنامه را متوقف و نشست را آزاد می‌کند."""
        process = self.browser_process
        if process is None:
            messagebox.showinfo("وضعیت مرورگر", "نشست فعالی از این برنامه ثبت نشده است.")
            return

        if process.poll() is None:
            self._terminate_browser_tree()

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            messagebox.showerror(
                "خطا در بستن مرورگر",
                "پردازش مرورگر هنوز بسته نشده است. یک بار دیگر دکمه بستن مرورگر را بزنید.",
            )
            return

        self.browser_process = None
        try:
            BROWSER_STATUS.write_text(
                json.dumps(
                    {"pid": process.pid, "state": "closed", "updated_at": __import__("time").time()},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        messagebox.showinfo(
            "مرورگر بسته شد",
            "نشست قبلی بسته و آزاد شد. اکنون می‌توانید دوباره اجرای زنده را بزنید.",
        )

    def _read_browser_status(self):
        try:
            return json.loads(BROWSER_STATUS.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def _terminate_browser_tree(self):
        process = self.browser_process
        if not process or process.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            else:
                process.terminate()
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass

    def on_close(self):
        if self.browser_process and self.browser_process.poll() is None:
            if messagebox.askyesno("خروج","مرورگر زنده نیز بسته شود؟"):
                self.browser_process.terminate()
        self.destroy()

    def save_lead(self):
        url=self.l_url.get().strip()
        if not url.startswith("https://divar.ir/"):
            messagebox.showwarning("لینک نامعتبر","لینک معتبر آگهی دیوار را وارد کنید."); return
        if not self.l_title.get().strip():
            messagebox.showwarning("ورودی ناقص","عنوان آگهی را وارد کنید."); return
        try:
            with connect() as con:
                price=self._optional_int(self.l_price.get(),"قیمت")
                area=self._optional_float(self.l_area.get(),"متراژ")
                rooms=self._optional_int(self.l_rooms.get(),"تعداد اتاق")
                features=[x.strip() for x in self.l_features.get().split(",") if x.strip()]
                con.execute("""INSERT INTO leads(campaign_id,ad_url,title,category,city,public_contact,notes,consent_status,stage,price,area,rooms,location,features_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(self.campaign_id,url,self.l_title.get().strip(),self.l_category.get().strip(),self.l_city.get().strip(),self.l_contact.get().strip(),self.l_notes.get("1.0","end").strip(),self.l_consent.get(),self.l_stage.get(),price,area,rooms,self.l_location.get().strip(),json.dumps(features,ensure_ascii=False)))
        except ValueError as exc:
            messagebox.showwarning("عدد نامعتبر",str(exc)); return
        except sqlite3.IntegrityError:
            messagebox.showwarning("تکراری","این لینک قبلاً ثبت شده است."); return
        with connect() as con:
            lead_id = con.execute("SELECT id FROM leads WHERE ad_url=?", (url,)).fetchone()[0]
        record_event(
            DB, "lead.created", entity_type="lead", entity_id=lead_id,
            message="سرنخ به‌صورت دستی ثبت شد",
            details={"campaign_id": self.campaign_id, "consent_status": self.l_consent.get()},
        )
        self.refresh_leads(); messagebox.showinfo("ذخیره شد","سرنخ ذخیره شد.")

    @staticmethod
    def _optional_int(value, label):
        value=value.strip()
        if not value:return None
        try:
            number=int(value.replace(",","").replace("٬",""))
            if number < 0: raise ValueError
            return number
        except ValueError:
            raise ValueError(f"{label} باید عدد صحیح نامنفی باشد.")

    @staticmethod
    def _optional_float(value, label):
        value=value.strip()
        if not value:return None
        try:
            number=float(value.replace(",","").replace("٬",""))
            if number <= 0: raise ValueError
            return number
        except ValueError:
            raise ValueError(f"{label} باید عددی بزرگ‌تر از صفر باشد.")

    def analyze_selected_listing(self):
        selected=self.lead_tree.selection()
        if not selected:
            messagebox.showinfo("انتخاب آگهی","ابتدا یک آگهی از فهرست انتخاب کنید.")
            return
        try:
            lead_id=int(self.lead_tree.item(selected[0],"values")[0])
            with connect() as con:
                row=con.execute("SELECT title,price,area,rooms,location,features_json FROM leads WHERE id=?",(lead_id,)).fetchone()
            if row is None:
                messagebox.showwarning("آگهی یافت نشد","اطلاعات آگهی در پایگاه داده پیدا نشد.")
                return
            features=json.loads(row["features_json"] or "[]")
            listing=Listing(title=row["title"],price=row["price"],area=row["area"],rooms=row["rooms"],location=row["location"] or "",features=tuple(features))
            criteria=BuyerCriteria(
                max_budget=self._optional_int(self.b_budget.get(),"سقف بودجه"),
                min_area=self._optional_float(self.b_min_area.get(),"حداقل متراژ"),
                max_area=self._optional_float(self.b_max_area.get(),"حداکثر متراژ"),
                rooms=self._optional_int(self.b_rooms.get(),"تعداد اتاق"),
                location=self.b_location.get().strip(),
                required_features=tuple(x.strip() for x in self.b_features.get().split(",") if x.strip()),
            )
            result=analyze_listing(listing,criteria)
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            messagebox.showwarning("معیار نامعتبر",str(exc))
            return
        if result.score is None:
            text="نتیجه: اطلاعات ناکافی\n"+"\n".join(result.reasons)
        else:
            text=f"امتیاز تطبیق: {result.score} از ۱۰۰ | وضعیت: {result.status} | پوشش معیارها: {result.compared_weight} از ۱۰۰\n"+"\n".join(result.reasons)
        self.analysis_result.configure(text=text)
        record_event(DB,"listing.analyzed",entity_type="lead",entity_id=lead_id,message="تحلیل تطبیق آگهی انجام شد",details={"score":result.score,"status":result.status,"compared_weight":result.compared_weight})

    def refresh_leads(self):
        for x in self.lead_tree.get_children(): self.lead_tree.delete(x)
        with connect() as con:
            rows=con.execute("SELECT id,title,category,city,public_contact,consent_status,stage,ad_url FROM leads ORDER BY id DESC").fetchall()
        for row in rows:self.lead_tree.insert("","end",values=row)

    def _select_lead(self,_event=None):
        sel=self.lead_tree.selection()
        if sel:self.selected_url=self.lead_tree.item(sel[0],"values")[-1]
    def open_selected(self):
        sel=self.lead_tree.selection()
        if not sel: messagebox.showinfo("انتخاب","ابتدا یک سرنخ انتخاب کنید."); return
        webbrowser.open(self.lead_tree.item(sel[0],"values")[-1])

    def export_excel(self):
        path=filedialog.asksaveasfilename(defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],initialfile="divar_leads.xlsx",initialdir=self.settings.get("export_directory") or str(DATA))
        if not path:return
        with connect() as con:
            rows=con.execute("""SELECT id,title,category,city,public_contact,notes,consent_status,stage,ad_url,created_at FROM leads ORDER BY id DESC""").fetchall()
        headers=["شناسه","عنوان آگهی","حوزه","شهر","راه تماس عمومی/مجاز","یادداشت","وضعیت رضایت","مرحله فروش","لینک آگهی","تاریخ ثبت"]
        wb=Workbook(); ws=wb.active; ws.title="سرنخ‌ها"; ws.sheet_view.rightToLeft=True
        ws.append(headers)
        for row in rows: ws.append(list(row))
        for cell in ws[1]:
            cell.font=Font(name="Tahoma",bold=True,color="FFFFFF")
            cell.fill=PatternFill("solid",fgColor="164E63")
            cell.alignment=Alignment(horizontal="center",vertical="center")
        for row in ws.iter_rows(min_row=2):
            for cell in row: cell.alignment=Alignment(horizontal="right",vertical="center")
            url=row[8]
            if url.value:
                url.hyperlink=url.value; url.style="Hyperlink"
        for i,w in enumerate([9,34,18,16,24,40,18,18,50,22],1): ws.column_dimensions[get_column_letter(i)].width=w
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
        wb.save(path); messagebox.showinfo("خروجی آماده شد",f"فایل اکسل ذخیره شد:\n{path}")

def run_self_test():
    """آزمون دود بدون نمایش پنجره و بدون دست‌کاری داده‌های واقعی کاربر."""
    import tempfile
    from storage import initialize
    with tempfile.TemporaryDirectory(prefix="agent-divar-smoke-") as temporary:
        test_db = Path(temporary) / "smoke.sqlite3"
        initialize(test_db)
        with open_database(test_db) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            schema_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError("بررسی سلامت پایگاه‌داده ناموفق بود.")
        print(json.dumps({"status": "ok", "database_integrity": integrity,
                          "schema_version": schema_version}, ensure_ascii=False))


if __name__=="__main__":
    if "--browser-runner" in sys.argv:
        from browser_runner import main as run_browser
        index = sys.argv.index("--browser-runner")
        run_browser(sys.argv[index + 1] if len(sys.argv) > index + 1 else None)
    elif "--self-test" in sys.argv:
        run_self_test()
    else:
        App().mainloop()

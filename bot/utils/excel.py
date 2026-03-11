"""
Monthly calendar-style Excel report.

Layout (one sheet):
  For each project:
    - Header row: project name + employee(s), days 1-31 each spanning 4 sub-cols
    - Sub-header: Нал | Без | Прох | ДР  (repeated per day) + Итого
    - Data rows fetched from Report table
    - Summary rows: Plan, %, ЗП фото, Расход хоз, Остаток, Из него нал

  Management block (bottom, red header):
    - Plan, %, ЗП всего, Расходник, УСН 6%, Налоги 35.6%, Аренда, Техника, Итог
    - Остаток, Из него нал
"""

from __future__ import annotations

import io
import calendar
from datetime import date
from collections import defaultdict
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from bot.database.models import Report, User, Plan, ManagementExpense


# ─── Palette ─────────────────────────────────────────────────────────────────
_F_BLACK  = Font(bold=False, color="000000", size=9)
_F_BOLD   = Font(bold=True,  color="000000", size=9)
_F_LABEL  = Font(bold=True,  color="000000", size=9)
_F_WHITE  = Font(bold=True,  color="FFFFFF", size=9)

_FILL_PROJECT   = PatternFill("solid", fgColor="B8CCE4")   # light blue — project header
_FILL_GREEN     = PatternFill("solid", fgColor="70AD47")   # green — labels/totals
_FILL_GRAY      = PatternFill("solid", fgColor="F2F2F2")   # alt row
_FILL_RED_HDR   = PatternFill("solid", fgColor="FF0000")   # Red header for ИТОГО
_FILL_BLUE_IN   = PatternFill("solid", fgColor="9DC3E6")   # input cell hint

_CTR  = Alignment(horizontal="center", vertical="center")
_LEFT = Alignment(horizontal="left",   vertical="center")

_thin = Side(border_style="thin", color="000000")
_BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

_NUM_FMT = '#,##0.00'
_INT_FMT = '#,##0'


def _cell(ws, row, col, value="", fill=None, font=None, align=None, fmt=None):
    c = ws.cell(row=row, column=col, value=value)
    if fill:  c.fill = fill
    if font:  c.font = font or _F_BLACK
    if align: c.alignment = align
    if fmt:   c.number_format = fmt
    c.border = _BORDER
    return c


def _merge(ws, r1, c1, r2, c2, value="", fill=None, font=None, align=None):
    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
    c = ws.cell(row=r1, column=c1, value=value)
    if fill:  c.fill = fill
    if font:  c.font = font
    if align: c.alignment = align
    # Apply border to entire merged range (openpyxl trick: border must be on every cell)
    for r in range(r1, r2 + 1):
        for col in range(c1, c2 + 1):
            ws.cell(row=r, column=col).border = _BORDER
    return c


async def generate_monthly_calendar(
    session: AsyncSession,
    year: int,
    month: int,
    city: str = "all"
) -> bytes:
    _, days_in_month = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end   = date(year, month, days_in_month)

    # ── Fetch all relevant data once ──────────────────────────────────────────
    # Reports
    q = select(Report).where(Report.date >= start, Report.date <= end)
    if city != "all": q = q.where(Report.city == city)
    res = await session.execute(q.order_by(Report.project_name, Report.date))
    all_reports = res.scalars().all()

    # Plans
    q_plans = select(Plan).where(Plan.is_active == True, Plan.period == "month")
    if city != "all": q_plans = q_plans.where(Plan.city == city)
    all_plans = (await session.execute(q_plans)).scalars().all()

    # Management Expenses
    mq = select(ManagementExpense).where(ManagementExpense.date >= start, ManagementExpense.date <= end)
    if city != "all": mq = mq.where(ManagementExpense.city == city)
    all_mgmt = (await session.execute(mq)).scalars().all()

    # Determine cities to process
    if city == "all":
        cities_to_process = ["gomel", "minsk"]
    else:
        cities_to_process = [city]

    wb = Workbook()
    # Remove default sheet
    default_sheet = wb.active
    wb.remove(default_sheet)

    # ── Helper to build a single city sheet ───────────────────────────────────
    def build_city_sheet(sheet_city: str, reports: list[Report], plans: list[Plan], mgmt_list: list[ManagementExpense]):
        city_label = {"gomel": "Гомель", "minsk": "Минск"}.get(sheet_city, sheet_city.title())
        ws = wb.create_sheet(title=city_label)
        
        row = 1
        
        # Projects: union of reported and planned for THIS city
        plan_by_project = {p.project_name: p.plan_amount for p in plans if p.project_name}
        global_plan = sum(p.plan_amount for p in plans if not p.project_name)
        project_set = {r.project_name for r in reports} | {p.project_name for p in plans if p.project_name}
        projects = sorted(project_set)

        # Group reports for THIS city
        by_project = defaultdict(lambda: defaultdict(list))
        for r in reports:
            by_project[r.project_name][r.date.day].append(r)

        # ─── Project Blocks ───────────────────────────────────────────────────
        for p_name in projects:
            p_data = by_project[p_name]
            p_plan = plan_by_project.get(p_name, 0)
            
            # Aggregated data per day for this project.
            # When multiple reports exist for the same day (2+ people in shift),
            # financial data is taken from the "master" report (highest revenue)
            # to avoid double-counting. Salaries are summed across all reporters.
            def _agg_day(reps):
                if not reps:
                    return {"names": "", "cash": 0, "acq": 0, "rev": 0,
                            "sal": 0, "tra": 0, "exp": 0, "bal": 0}
                master = max(reps, key=lambda r: r.revenue)
                # Unique first names in submission order, joined with " + "
                seen, unique_names = set(), []
                for rep in reps:
                    first = rep.employee_name.split()[0] if rep.employee_name else ""
                    # Use full name as dedup key to handle same-first-name cases
                    key = rep.employee_name or ""
                    if key and key not in seen:
                        seen.add(key)
                        unique_names.append(first)
                return {
                    "names": " + ".join(unique_names),
                    "rev":   master.revenue,
                    "cash":  master.cash,
                    "acq":   master.acquiring,
                    "exp":   master.expense,
                    "bal":   master.cash_balance,
                    # Salary is per-person already — sum gives total paid
                    "sal":   sum(r.salary_paid for r in reps),
                    "tra":   sum(r.trainee_salary for r in reps),
                }
            agg = {d: _agg_day(p_data.get(d, [])) for d in range(1, days_in_month + 1)}

            t_rev  = sum(a["rev"] for a in agg.values())
            t_cash = sum(a["cash"] for a in agg.values())
            t_acq  = sum(a["acq"] for a in agg.values())
            t_sal  = sum(a["sal"] for a in agg.values())
            t_tra  = sum(a["tra"] for a in agg.values())
            t_exp  = sum(a["exp"] for a in agg.values())
            pct    = (t_rev / p_plan) if p_plan else 0

            # Row 1: Dates
            _merge(ws, row, 1, row + 1, 1, p_name, fill=_FILL_PROJECT, font=_F_BOLD, align=_CTR)
            ws.cell(row=row, column=1).alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
            
            _cell(ws, row, 2, "", fill=_FILL_PROJECT)
            _cell(ws, row, 3, "", fill=_FILL_PROJECT)
            for d in range(1, days_in_month + 1):
                _cell(ws, row, 3 + d, f"{d}-{_month_label(month)}", fill=_FILL_PROJECT, font=_F_BOLD, align=_CTR)
            row += 1

            # Row 2: ФИО
            _cell(ws, row, 2, "ФИО", fill=_FILL_GRAY, font=_F_LABEL, align=_CTR)
            _cell(ws, row, 3, "", fill=_FILL_GRAY)
            for d in range(1, days_in_month + 1):
                _cell(ws, row, 3 + d, agg[d]["names"], align=_CTR)
                ws.cell(row=row, column=3+d).alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
            
            # Make the FIO row taller to accommodate multiple wrapped names
            ws.row_dimensions[row].height = 40
            row += 1

            # Row 3: План | Доходы
            _cell(ws, row, 1, "План", font=_F_BOLD)
            _cell(ws, row, 2, "Доходы", fill=_FILL_GREEN, font=_F_WHITE)
            _cell(ws, row, 3, t_rev, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            for i in range(1, days_in_month + 1):
                _cell(ws, row, 3 + i, agg[i]["rev"], fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            row += 1

            # Row 4: Plan Amount | нал.
            _cell(ws, row, 1, p_plan, fmt=_INT_FMT)
            _cell(ws, row, 2, "нал.")
            _cell(ws, row, 3, t_cash, fmt=_NUM_FMT)
            for i in range(1, days_in_month + 1):
                _cell(ws, row, 3 + i, agg[i]["cash"], fmt=_NUM_FMT)
            row += 1

            # Row 5: Выполнено | безнал.
            _cell(ws, row, 1, "Выполнено")
            _cell(ws, row, 2, "безнал.")
            _cell(ws, row, 3, t_acq, fmt=_NUM_FMT)
            for i in range(1, days_in_month + 1):
                _cell(ws, row, 3 + i, agg[i]["acq"], fmt=_NUM_FMT)
            row += 1

            # Row 6: % | Расходы
            _cell(ws, row, 1, pct, fmt='0%')
            _cell(ws, row, 2, "Расходы", fill=_FILL_GREEN, font=_F_WHITE)
            _cell(ws, row, 3, t_sal + t_tra + t_exp, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            for i in range(1, days_in_month + 1):
                _cell(ws, row, 3 + i, agg[i]["sal"]+agg[i]["tra"]+agg[i]["exp"], fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            row += 1

            # Expense breakdown rows
            def data_row(lbl, key):
                nonlocal row
                _cell(ws, row, 2, lbl)
                total = sum(a[key] for a in agg.values())
                _cell(ws, row, 3, total, fmt=_NUM_FMT)
                for i in range(1, days_in_month + 1):
                    _cell(ws, row, 3 + i, agg[i][key], fmt=_NUM_FMT)
                row += 1

            data_row("зарплата Фотографа", "sal")
            data_row("зарплата Стажера", "tra")
            data_row("хоз расход", "exp")
            
            # Placeholder/Manual expenses + Project-linked Mgmt expenses
            categories = [
                ("расходник", "расходник"), 
                ("УСН 6%", "усн_6"), 
                ("налоги по ЗП 35,6%", "налоги_зп"), 
                ("техника", "техника"), 
                ("аренда", "аренда")
            ]
            for label, cat_key in categories:
                _cell(ws, row, 2, label)
                
                # Base auto-calculated values
                auto_val = 0
                if cat_key == "усн_6": auto_val = t_rev * 0.06
                elif cat_key == "налоги_зп": auto_val = (t_sal + t_tra) * 0.356
                
                # Sum expenses specifically linked to this project
                linked_mgmt = [m for m in mgmt_list if m.project_name == p_name and m.category == cat_key]
                manual_val  = sum(m.amount for m in linked_mgmt)
                
                total_val = auto_val + manual_val
                _cell(ws, row, 3, total_val, fmt=_NUM_FMT)
                
                for d in range(1, days_in_month + 1):
                    d_auto = 0
                    if cat_key == "усн_6": d_auto = agg[d]["rev"] * 0.06
                    elif cat_key == "налоги_зп": d_auto = (agg[d]["sal"] + agg[d]["tra"]) * 0.356
                    
                    # Daily breakdown for linked mgmt (if multi-day, we only show on the specific date)
                    d_manual = sum(m.amount for m in linked_mgmt if m.date.day == d)
                    _cell(ws, row, 3 + d, d_auto + d_manual, fmt=_NUM_FMT)
                row += 1

            # Final total for project block (Ostatok)
            # Should subtract all linked mgmt expenses + auto expenses
            p_mgmt_sum = sum(m.amount for m in mgmt_list if m.project_name == p_name)
            p_auto_sum = (t_rev * 0.06) + ((t_sal + t_tra) * 0.356)
            
            # Остаток
            _cell(ws, row, 2, "Остаток конец дня", fill=_FILL_GREEN, font=_F_WHITE)
            total_residue = t_rev - (t_sal + t_tra + t_exp + p_mgmt_sum + p_auto_sum)
            _cell(ws, row, 3, total_residue, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            for d in range(1, days_in_month + 1):
                d_mgmt = sum(m.amount for m in mgmt_list if m.project_name == p_name and m.date.day == d)
                d_auto = (agg[d]["rev"] * 0.06) + ((agg[d]["sal"] + agg[d]["tra"]) * 0.356)
                # The 'bal' in agg is master.cash_balance, which might not include mgmt expenses or taxes
                # We calculate residue manually for consistency
                d_residue = agg[d]["rev"] - (agg[d]["sal"] + agg[d]["tra"] + agg[d]["exp"] + d_mgmt + d_auto)
                _cell(ws, row, 3 + d, d_residue, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            row += 1

            _cell(ws, row, 2, "из них нал.", fill=_FILL_GREEN, font=_F_WHITE)
            _cell(ws, row, 3, t_cash, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            for d in range(1, days_in_month + 1):
                _cell(ws, row, 3 + d, agg[d]["cash"], fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
            row += 1

            row += 1 # spacer

        # ─── CITY TOTAL ───────────────────────────────────────────────────────
        _merge(ws, row, 1, row, 3 + days_in_month, f"ИТОГО — {city_label}", fill=_FILL_RED_HDR, font=_F_WHITE, align=_CTR)
        row += 1

        city_rev  = sum(r.revenue for r in reports)
        city_cash = sum(r.cash for r in reports)
        city_acq  = sum(r.acquiring for r in reports)
        city_sal  = sum(r.salary_paid for r in reports)
        city_tra  = sum(r.trainee_salary for r in reports)
        city_exp  = sum(r.expense for r in reports)
        city_plan = sum(plan_by_project.values()) + global_plan
        city_pct  = (city_rev / city_plan * 100) if city_plan else 0

        # Mgmt totals for THIS city
        def get_mgmt(cat): return sum(m.amount for m in mgmt_list if m.category == cat)
        m_cons   = get_mgmt("расходник")
        m_rent   = get_mgmt("аренда")
        m_equi   = get_mgmt("техника")
        m_usn6   = get_mgmt("усн_6")
        m_tax_zp = get_mgmt("налоги_зп")
        m_other  = get_mgmt("другое")
        m_total  = sum(m.amount for m in mgmt_list)

        # Row 1: План / Доходы
        _cell(ws, row, 1, "План", fill=_FILL_GRAY, font=_F_LABEL)
        _cell(ws, row, 2, "Доходы", fill=_FILL_GRAY, font=_F_LABEL)
        _cell(ws, row, 3, city_rev, fill=_FILL_GRAY, font=_F_LABEL, fmt=_NUM_FMT)
        row += 1

        # Row 2: Plan Amount / нал.
        _cell(ws, row, 1, city_plan, fmt=_INT_FMT)
        _cell(ws, row, 2, "нал.")
        _cell(ws, row, 3, city_cash, fmt=_NUM_FMT)
        row += 1

        # Row 3: Выполнено / безнал.
        _cell(ws, row, 1, "Выполнено")
        _cell(ws, row, 2, "безнал.")
        _cell(ws, row, 3, city_acq, fmt=_NUM_FMT)
        row += 1

        # Row 4: % / Расходы
        _cell(ws, row, 1, f"{city_pct:.0f}%", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 2, "Расходы", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 3, city_sal + city_tra + city_exp + m_total, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        row += 1

        def t_row(lbl, val):
            nonlocal row
            _cell(ws, row, 2, lbl)
            _cell(ws, row, 3, val, fmt=_NUM_FMT)
            row += 1

        t_row("зарплата Фотографа", city_sal)
        t_row("зарплата Стажера", city_tra)
        t_row("хоз расход", city_exp)
        t_row("расходник", m_cons)
        t_row("УСН 6%", m_usn6 or (city_rev * 0.06))
        t_row("налоги по ЗП 35,6%", m_tax_zp or ((city_sal + city_tra) * 0.356))
        t_row("техника", m_equi)
        t_row("аренда", m_rent)
        t_row("другое", m_other)
        
        # Row: Остаток конец дня
        _cell(ws, row, 2, "Остаток конец дня", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 3, city_rev - (city_sal + city_tra + city_exp + m_total), fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        row += 1
        
        # Row: из них нал.
        _cell(ws, row, 2, "из них нал.", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 3, city_cash, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        row += 1

        # Styling
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 25
        ws.column_dimensions["C"].width = 15
        for d in range(1, days_in_month + 1):
            ws.column_dimensions[get_column_letter(3 + d)].width = 10

    # ── Process each city into its own sheet ──────────────────────────────────
    for c_id in cities_to_process:
        city_reports = [r for r in all_reports if r.city == c_id]
        city_plans   = [p for p in all_plans if p.city == c_id]
        city_mgmt    = [m for m in all_mgmt if m.city == c_id]
        
        # Only add sheet if there's data or plans, or if it's a specific city request
        if city_reports or city_plans or city != "all":
            build_city_sheet(c_id, city_reports, city_plans, city_mgmt)

    # ── Final global summary sheet (if all) ───────────────────────────────────
    if city == "all" and len(wb.sheetnames) > 0:
        ws = wb.create_sheet(title="ИТОГО ОБЩИЙ", index=0)
        row = 1
        
        total_rev  = sum(r.revenue for r in all_reports)
        total_cash = sum(r.cash for r in all_reports)
        total_acq  = sum(r.acquiring for r in all_reports)
        total_sal  = sum(r.salary_paid for r in all_reports)
        total_tra  = sum(r.trainee_salary for r in all_reports)
        total_exp  = sum(r.expense for r in all_reports)
        total_plan = sum(p.plan_amount for p in all_plans)
        total_pct  = (total_rev / total_plan * 100) if total_plan else 0
        total_mgmt = sum(m.amount for m in all_mgmt)

        _merge(ws, row, 1, row, 3, "СВОДНЫЙ ОТЧЕТ (ВСЕ ГОРОДА)", fill=_FILL_RED_HDR, font=_F_WHITE, align=_CTR)
        row += 1
        
        _cell(ws, row, 1, "Показатель", fill=_FILL_GRAY, font=_F_LABEL)
        _cell(ws, row, 2, "Значение", fill=_FILL_GRAY, font=_F_LABEL)
        row += 1
        
        def s_row(lbl, val, fmt=_NUM_FMT):
            nonlocal row
            _cell(ws, row, 1, lbl)
            _cell(ws, row, 2, val, fmt=fmt)
            row += 1

        s_row("Выручка общая", total_rev)
        s_row("План общий", total_plan, fmt=_INT_FMT)
        s_row("Выполнение", total_pct / 100, fmt='0%')
        row += 1
        s_row("Наличные", total_cash)
        s_row("Безнал", total_acq)
        row += 1
        s_row("ЗП Фотографы", total_sal)
        s_row("ЗП Стажеры", total_tra)
        s_row("Хоз расходы", total_exp)
        s_row("Упр. расходы", total_mgmt)
        row += 1
        s_row("ИТОГО ОСТАТОК", total_rev - (total_sal + total_tra + total_exp + total_mgmt))

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["B"].width = 20

    # Handle case where no sheets were created
    if len(wb.sheetnames) == 0:
        wb.create_sheet(title="No Data")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _month_label(m: int) -> str:
    return ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"][m-1]


# ── Keep old report for backward compat ───────────────────────────────────────
async def generate_excel_report(session: AsyncSession, start_date: date, end_date: date) -> bytes:
    """Legacy simple row-per-report export (still available in admin)."""
    from openpyxl import Workbook as WB
    res = await session.execute(
        select(Report, User)
        .join(User, Report.user_id == User.id)
        .where(Report.date >= start_date, Report.date <= end_date)
        .order_by(Report.date, Report.project_name)
    )
    rows = res.all()

    wb2 = WB()
    ws2 = wb2.active
    ws2.title = f"Отчет {start_date.strftime('%d.%m')}-{end_date.strftime('%d.%m.%Y')}"

    H_FONT = Font(bold=True, color="FFFFFF", size=11)
    H_FILL = PatternFill("solid", fgColor="1F4E79")
    ALT    = PatternFill("solid", fgColor="DEEAF1")
    TOT_F  = Font(bold=True, color="FFFFFF", size=11)
    TOT_FL = PatternFill("solid", fgColor="2E75B6")
    CENTER = Alignment(horizontal="center", vertical="center")
    thin   = Side(border_style="thin", color="AAAAAA")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        ("Дата", 13), ("Проект", 22), ("Сотрудник", 20), ("Чел.", 7),
        ("Выручка", 13), ("Нал", 13), ("Безнал", 13), ("ЗП", 13),
        ("Расход", 13), ("Остаток", 14), ("Посет.", 9), ("ДР", 6), ("Комментарий", 30),
    ]
    for col, (h, w) in enumerate(headers, 1):
        c = ws2.cell(row=1, column=col, value=h)
        c.font, c.fill, c.alignment, c.border = H_FONT, H_FILL, CENTER, BORDER
        ws2.column_dimensions[get_column_letter(col)].width = w
    ws2.row_dimensions[1].height = 24

    totals = dict(revenue=0.0, cash=0.0, acq=0.0, salary=0.0, expense=0.0, visitors=0, bdays=0)
    for ri, (rep, user) in enumerate(rows, 2):
        fill = ALT if ri % 2 == 0 else None
        data = [
            rep.date.strftime("%d.%m.%Y"), rep.project_name, rep.employee_name,
            rep.shift_count, rep.revenue, rep.cash, rep.acquiring,
            rep.salary_paid, rep.expense, rep.cash_balance,
            rep.visitors, rep.birthdays, rep.comment or "",
        ]
        for ci, v in enumerate(data, 1):
            c = ws2.cell(row=ri, column=ci, value=v)
            if fill: c.fill = fill
            c.border = BORDER
            if ci in (1, 4, 11, 12): c.alignment = CENTER
        totals["revenue"]  += rep.revenue
        totals["cash"]     += rep.cash
        totals["acq"]      += rep.acquiring
        totals["salary"]   += rep.salary_paid
        totals["expense"]  += rep.expense
        totals["visitors"] += rep.visitors
        totals["bdays"]    += rep.birthdays

    tr = len(rows) + 2
    summary = ["ИТОГО", "", "", "", totals["revenue"], totals["cash"], totals["acq"],
                totals["salary"], totals["expense"], "", totals["visitors"], totals["bdays"], ""]
    for ci, v in enumerate(summary, 1):
        c = ws2.cell(row=tr, column=ci, value=v)
        c.font, c.fill, c.alignment, c.border = TOT_F, TOT_FL, CENTER, BORDER

    ws2.freeze_panes = "A2"
    buf = io.BytesIO()
    wb2.save(buf)
    buf.seek(0)
    return buf.read()

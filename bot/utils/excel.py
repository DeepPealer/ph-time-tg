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
    - Остаток, Из него нал, Дивиденды
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
    month_str = f"{year}-{month:02d}"
    
    # Header cells for dates (Col 4 onwards)
    DATE_COLS = list(range(4, 4 + days_in_month))
    
    # ── Fetch data ────────────────────────────────────────────────────────────
    start = date(year, month, 1)
    end   = date(year, month, days_in_month)

    # Reports
    q = select(Report).where(Report.date >= start, Report.date <= end)
    if city != "all": q = q.where(Report.city == city)
    res = await session.execute(q.order_by(Report.project_name, Report.date))
    reports = res.scalars().all()

    # Projects: union of reported and planned
    q_plans = select(Plan).where(Plan.is_active == True, Plan.period == "month")
    if city != "all": q_plans = q_plans.where(Plan.city == city)
    plan_list = (await session.execute(q_plans)).scalars().all()
    
    plan_by_project = {p.project_name: p.plan_amount for p in plan_list if p.project_name}
    global_plan = sum(p.plan_amount for p in plan_list if not p.project_name)

    project_set = {r.project_name for r in reports} | {p.project_name for p in plan_list if p.project_name}
    projects = sorted(project_set)

    # Group reports: by_project[proj][day] = [Report, ...]
    by_project = defaultdict(lambda: defaultdict(list))
    for r in reports:
        by_project[r.project_name][r.date.day].append(r)

    # Mgmt Expenses
    mq = select(ManagementExpense).where(ManagementExpense.date >= start, ManagementExpense.date <= end)
    if city != "all": mq = mq.where(ManagementExpense.city == city)
    mgmt_list = (await session.execute(mq)).scalars().all()

    # ── Build ─────────────────────────────────────────────────────────────────
    wb = Workbook()
    ws = wb.active
    ws.title = f"Report {year}-{month:02d}"

    row = 1

    def add_project_block(p_name, p_data, p_plan):
        nonlocal row
        start_row = row
        
        # Aggregated data per day for this project
        agg = {d: {
            "names": ", ".join([rep.employee_name.split()[0] for rep in p_data.get(d, []) if rep.employee_name]),
            "cash":  sum(rep.cash for rep in p_data.get(d, [])),
            "acq":   sum(rep.acquiring for rep in p_data.get(d, [])),
            "rev":   sum(rep.revenue for rep in p_data.get(d, [])),
            "sal":   sum(rep.salary_paid for rep in p_data.get(d, [])),
            "tra":   sum(rep.trainee_salary for rep in p_data.get(d, [])),
            "exp":   sum(rep.expense for rep in p_data.get(d, [])),
            "bal":   max([rep.cash_balance for rep in p_data.get(d, [])] or [0]),
        } for d in range(1, days_in_month + 1)}

        t_rev  = sum(a["rev"] for a in agg.values())
        t_cash = sum(a["cash"] for a in agg.values())
        t_acq  = sum(a["acq"] for a in agg.values())
        t_sal  = sum(a["sal"] for a in agg.values())
        t_tra  = sum(a["tra"] for a in agg.values())
        t_exp  = sum(a["exp"] for a in agg.values())
        pct    = (t_rev / p_plan) if p_plan else 0 # formatting will handle % if fmt set to '0%'

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
            ws.cell(row=row, column=3+d).alignment = Alignment(text_rotation=90, vertical="center", horizontal="center")
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
        
        # Placeholder/Manual expenses
        for lbl in ["расходник", "УСН 6%", "налоги по ЗП 35,6%", "техника", "аренда"]:
            _cell(ws, row, 2, lbl)
            val = 0
            if lbl == "УСН 6%": val = t_rev * 0.06
            elif lbl == "налоги по ЗП 35,6%": val = (t_sal + t_tra) * 0.356
            
            _cell(ws, row, 3, val, fmt=_NUM_FMT)
            for d in range(1, days_in_month + 1):
                d_val = 0
                if lbl == "УСН 6%": d_val = agg[d]["rev"] * 0.06
                elif lbl == "налоги по ЗП 35,6%": d_val = (agg[d]["sal"] + agg[d]["tra"]) * 0.356
                _cell(ws, row, 3 + d, d_val, fmt=_NUM_FMT)
            row += 1

        # Остаток
        _cell(ws, row, 2, "Остаток конец дня", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 3, t_rev - (t_sal + t_tra + t_exp), fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        for d in range(1, days_in_month + 1):
            _cell(ws, row, 3 + d, agg[d]["bal"], fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        row += 1

        _cell(ws, row, 2, "из них нал.", fill=_FILL_GREEN, font=_F_WHITE)
        _cell(ws, row, 3, t_cash, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        for d in range(1, days_in_month + 1):
            _cell(ws, row, 3 + d, agg[d]["cash"], fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
        row += 1

        row += 1 # spacer

    # Add blocks
    for p in projects:
        add_project_block(p, by_project[p], plan_by_project.get(p, 0))

    # ── ИТОГО ─────────────────────────────────────────────────────────────────
    _merge(ws, row, 1, row, 3 + days_in_month, "ИТОГО", fill=_FILL_RED_HDR, font=_F_WHITE, align=_CTR)
    row += 1

    # Totals across all projects
    all_rev  = sum(r.revenue for r in reports)
    all_cash = sum(r.cash for r in reports)
    all_acq  = sum(r.acquiring for r in reports)
    all_sal  = sum(r.salary_paid for r in reports)
    all_tra  = sum(r.trainee_salary for r in reports)
    all_exp  = sum(r.expense for r in reports)
    all_plan = sum(plan_by_project.values()) + global_plan
    all_pct  = (all_rev / all_plan * 100) if all_plan else 0

    # Mgmt totals
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
    _cell(ws, row, 3, all_rev, fill=_FILL_GRAY, font=_F_LABEL, fmt=_NUM_FMT)
    row += 1

    # Row 2: Plan Amount / нал.
    _cell(ws, row, 1, all_plan, fmt=_INT_FMT)
    _cell(ws, row, 2, "нал.")
    _cell(ws, row, 3, all_cash, fmt=_NUM_FMT)
    row += 1

    # Row 3: Выполнено / безнал.
    _cell(ws, row, 1, "Выполнено")
    _cell(ws, row, 2, "безнал.")
    _cell(ws, row, 3, all_acq, fmt=_NUM_FMT)
    row += 1

    # Row 4: % / Расходы
    _cell(ws, row, 1, f"{all_pct:.0f}%", fill=_FILL_GREEN, font=_F_WHITE)
    _cell(ws, row, 2, "Расходы", fill=_FILL_GREEN, font=_F_WHITE)
    _cell(ws, row, 3, all_sal + all_tra + all_exp + m_total, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
    row += 1

    def t_row(lbl, val):
        nonlocal row
        _cell(ws, row, 2, lbl)
        _cell(ws, row, 3, val, fmt=_NUM_FMT)
        row += 1

    t_row("зарплата Фотографа", all_sal)
    t_row("зарплата Стажера", all_tra)
    t_row("хоз расход", all_exp)
    t_row("расходник", m_cons)
    t_row("УСН 6%", m_usn6 or (all_rev * 0.06)) # Use manual if set, else auto
    t_row("налоги по ЗП 34,6%", m_tax_zp or ((all_sal + all_tra) * 0.356))
    t_row("техника", m_equi)
    t_row("аренда", m_rent)
    t_row("другое", m_other)
    
    # Row: Остаток конец дня
    _cell(ws, row, 2, "Остаток конец дня", fill=_FILL_GREEN, font=_F_WHITE)
    _cell(ws, row, 3, all_rev - (all_sal + all_tra + all_exp + m_total), fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
    row += 1
    
    # Row: из них нал.
    _cell(ws, row, 2, "из них нал.", fill=_FILL_GREEN, font=_F_WHITE)
    _cell(ws, row, 3, all_cash, fill=_FILL_GREEN, font=_F_WHITE, fmt=_NUM_FMT)
    row += 1
    
    row += 1 # spacer

    # Row: Дивиденды 1/1
    _cell(ws, row, 2, "Дивиденды 1/1", fill=_FILL_GRAY, font=_F_LABEL)
    _cell(ws, row, 3, (all_rev - (all_sal + all_tra + all_exp + m_total)) / 2, fill=_FILL_GRAY, font=_F_LABEL, fmt=_NUM_FMT)
    row += 1

    # Styling
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 15
    for d in range(1, days_in_month + 1):
        ws.column_dimensions[get_column_letter(3 + d)].width = 10

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

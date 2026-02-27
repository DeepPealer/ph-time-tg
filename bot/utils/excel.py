import io
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from bot.database.models import Report, User


async def generate_excel_report(session: AsyncSession, start_date: date, end_date: date) -> bytes:
    result = await session.execute(
        select(Report, User)
        .join(User, Report.user_id == User.id)
        .where(Report.date >= start_date, Report.date <= end_date)
        .order_by(Report.date, Report.project_name)
    )
    rows = result.all()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Отчет {start_date.strftime('%d.%m')}-{end_date.strftime('%d.%m.%Y')}"

    # Styles
    H_FONT  = Font(bold=True, color="FFFFFF", size=11)
    H_FILL  = PatternFill("solid", fgColor="1F4E79")
    ALT     = PatternFill("solid", fgColor="DEEAF1")
    TOT_F   = Font(bold=True, color="FFFFFF", size=11)
    TOT_FL  = PatternFill("solid", fgColor="2E75B6")
    CENTER  = Alignment(horizontal="center", vertical="center")
    thin    = Side(border_style="thin", color="AAAAAA")
    BORDER  = Border(left=thin, right=thin, top=thin, bottom=thin)

    headers = [
        ("Дата", 13), ("Проект", 22), ("Сотрудник", 20), ("Чел.", 7),
        ("Выручка", 13), ("Нал", 13), ("Безнал", 13), ("ЗП", 13),
        ("Расход", 13), ("Остаток", 14), ("Посет.", 9), ("ДР", 6), ("Комментарий", 30),
    ]

    for col, (h, w) in enumerate(headers, 1):
        c = ws.cell(row=1, column=col, value=h)
        c.font, c.fill, c.alignment, c.border = H_FONT, H_FILL, CENTER, BORDER
        ws.column_dimensions[c.column_letter].width = w
    ws.row_dimensions[1].height = 24

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
            c = ws.cell(row=ri, column=ci, value=v)
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
        c = ws.cell(row=tr, column=ci, value=v)
        c.font, c.fill, c.alignment, c.border = TOT_F, TOT_FL, CENTER, BORDER

    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()

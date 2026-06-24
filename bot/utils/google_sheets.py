import asyncio
import calendar
import logging
from datetime import date
from collections import defaultdict
import re

import gspread
from gspread_formatting import (
    color, textFormat,
    numberFormat, format_cell_ranges, CellFormat,
    borders, Border
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from bot.config import config
from bot.database.models import Report, Plan, ManagementExpense, Project, City

logger = logging.getLogger(__name__)

# --- Colors Conversion --------------------------------------------------------
def hex_to_gspread_color(hex_str: str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = "".join([c*2 for c in hex_str])
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return color(r, g, b)

# Palette
C_BLACK  = color(0, 0, 0)
C_WHITE  = color(1, 1, 1)
C_GREEN  = hex_to_gspread_color("339933")
C_RED    = hex_to_gspread_color("FF0000")
C_BLUE   = hex_to_gspread_color("0000FF")

FILL_PROJECT   = hex_to_gspread_color("B8CCE4")   # light blue
FILL_GREEN     = hex_to_gspread_color("C4D79B")   # light green 
FILL_BLUE      = hex_to_gspread_color("95B3D7")   # blue headers
FILL_GRAY      = hex_to_gspread_color("F2F2F2")   # alt row
FILL_RED_HDR   = hex_to_gspread_color("FF0000")   # Red header for ИТОГО
FILL_BLUE_IN   = hex_to_gspread_color("9DC3E6")   # total row color
FILL_WHITE     = hex_to_gspread_color("FFFFFF")   # white background

# Borders — Border(style, color) is a single side, borders() creates the full set
_side_thin = Border(style="SOLID", color=color(0.5, 0.5, 0.5))

BORDER_THIN = borders(top=_side_thin, bottom=_side_thin, left=_side_thin, right=_side_thin)

# Number Formats
FMT_CURRENCY = numberFormat(type='NUMBER', pattern='#,##0.00" BYN"')
FMT_INTEGER  = numberFormat(type='NUMBER', pattern='#,##0" BYN"')
FMT_PERCENT  = numberFormat(type='PERCENT', pattern='0%')

# --- Helper to convert coordinates to A1 notation ----------------------------
def get_range_str(r1: int, c1: int, r2: int, c2: int) -> str:
    def col_name(c):
        name = ""
        while c > 0:
            c, remainder = divmod(c - 1, 26)
            name = chr(65 + remainder) + name
        return name
    return f"{col_name(c1)}{r1}:{col_name(c2)}{r2}"

def get_month_name_ru(month: int) -> str:
    months_ru = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ]
    return months_ru[month - 1]

def get_month_label_short(m: int) -> str:
    return ["ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН", "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК"][m-1]

# --- Google Client Auth -------------------------------------------------------
def _get_google_client():
    if not config.use_google_sheets or not config.google_sheets_spreadsheet_id:
        return None
    try:
        # Load credentials from service account JSON
        client = gspread.service_account(filename=config.google_service_account_file)
        return client
    except Exception as e:
        logger.error(f"Failed to authenticate with Google Sheets API: {e}")
        return None

# --- Main Background Synchronization Runner -----------------------------------
def _do_sync_in_thread(spreadsheet_id: str, year: int, month: int, city_data_list: list):
    """Executes the Google Sheets API requests synchronously inside a separate thread."""
    client = _get_google_client()
    if not client:
        logger.warning("Google Sheets client not authenticated. Sync aborted.")
        return

    try:
        sh = client.open_by_key(spreadsheet_id)
    except Exception as e:
        logger.error(f"Failed to open Google Spreadsheet with ID {spreadsheet_id}: {e}")
        return

    month_name_ru = get_month_name_ru(month)

    for city_slug, city_name, data in city_data_list:
        # Sheet name: "Город (Месяц Год)"
        sheet_title = f"{city_name} ({month_name_ru} {year})"
        if len(sheet_title) > 100:  # Google Sheet tab limit
            sheet_title = sheet_title[:100]

        # 1. Fetch or create worksheet
        try:
            worksheet = sh.worksheet(sheet_title)
        except gspread.WorksheetNotFound:
            try:
                worksheet = sh.add_worksheet(title=sheet_title, rows=1000, cols=30)
            except Exception as e:
                logger.error(f"Failed to create worksheet '{sheet_title}': {e}")
                continue

        # Compile values, merges, formats and widths
        values_matrix = data["values"]
        merges = data["merges"]
        formats = data["formats"]
        col_widths = data["widths"]

        # Ensure worksheet has enough rows/columns
        current_rows = worksheet.row_count
        current_cols = worksheet.col_count
        required_rows = len(values_matrix) + 10
        required_cols = 20

        if required_rows > current_rows or required_cols > current_cols:
            worksheet.resize(rows=max(required_rows, current_rows), cols=max(required_cols, current_cols))

        # Clear existing sheet content
        try:
            worksheet.clear()
        except Exception as e:
            logger.error(f"Failed to clear worksheet '{sheet_title}': {e}")

        # Remove existing merges if any (to avoid merge conflicts during update)
        try:
            # We clear formats and merges by applying a clear format, but gspread doesn't have an easy clear merges.
            # However, worksheet.clear() in gspread clears all cell values.
            # In Google Sheets, to unmerge all we can send a single request:
            unmerge_req = {
                "unmergeCells": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": required_rows,
                        "startColumnIndex": 0,
                        "endColumnIndex": required_cols
                    }
                }
            }
            sh.batch_update({"requests": [unmerge_req]})
        except Exception as e:
            logger.debug(f"Unmerge request failed (expected if sheet is new): {e}")

        # 2. Update values in a single call
        try:
            if values_matrix:
                worksheet.update(values_matrix)
        except Exception as e:
            logger.error(f"Failed to update values in sheet '{sheet_title}': {e}")
            continue

        # 3. Apply formats in batch
        try:
            if formats:
                # Convert the formats list of tuples: (range_str, CellFormat) into gspread_formatting list
                format_cell_ranges(worksheet, formats)
        except Exception as e:
            logger.error(f"Failed to format worksheet '{sheet_title}': {e}")

        # 4. Apply merges and column widths in one batch Spreadsheet update!
        batch_requests = []

        # Merge requests
        for r1, c1, r2, c2 in merges:
            batch_requests.append({
                "mergeCells": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": r1 - 1,
                        "endRowIndex": r2,
                        "startColumnIndex": c1 - 1,
                        "endColumnIndex": c2
                    },
                    "mergeType": "MERGE_ALL"
                }
            })

        # Column widths
        for col_idx, width in col_widths.items():
            batch_requests.append({
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "startIndex": col_idx - 1,
                        "endIndex": col_idx
                    },
                    "properties": {
                        "pixelSize": int(width * 8.5)
                    },
                    "fields": "pixelSize"
                }
            })

        # Borders request in sheets API (applying medium & thick borders since gspread-formatting is basic)
        # We can also rely on gspread-formatting's borders, but doing it in batch requests is very powerful.
        # However, BORDER_THIN was already set in formats list, which is highly readable!

        if batch_requests:
            try:
                sh.batch_update({"requests": batch_requests})
            except Exception as e:
                logger.error(f"Failed to apply merges or column widths batch in sheet '{sheet_title}': {e}")

        logger.info(f"Successfully synchronized Google Sheet tab: '{sheet_title}'")


async def sync_data_to_sheets(session: AsyncSession, year: int, month: int, city: str = "all"):
    """
    Asynchronously queries database, builds spreadsheet matrices, and schedules
    sync to Google Sheets in a background worker thread.
    """
    if not config.use_google_sheets or not config.google_sheets_spreadsheet_id:
        return

    logger.info(f"Preparing Google Sheets synchronization for {year}-{month:02d} (city: {city})...")

    _, days_in_month = calendar.monthrange(year, month)
    start = date(year, month, 1)
    end   = date(year, month, days_in_month)

    # --- Fetch all database data asynchronously --------------------------------
    try:
        q = select(Report).where(Report.date >= start, Report.date <= end)
        if city != "all": 
            q = q.where(or_(Report.city == city, Report.city == None))
        res = await session.execute(q.order_by(Report.project_name, Report.date))
        all_reports = res.scalars().all()

        q_plans = select(Plan).where(Plan.is_active == True, Plan.period == "month")
        if city != "all": 
            q_plans = q_plans.where(Plan.city == city)
        all_plans = (await session.execute(q_plans)).scalars().all()

        mq = select(ManagementExpense).where(ManagementExpense.date >= start, ManagementExpense.date <= end)
        if city != "all": 
            mq = mq.where(ManagementExpense.city == city)
        all_mgmt = (await session.execute(mq)).scalars().all()

        q_proj = select(Project).where(Project.is_active == True)
        if city != "all": 
            q_proj = q_proj.where(Project.city == city)
        all_projects = (await session.execute(q_proj)).scalars().all()

        if city == "all":
            city_objs_res = await session.execute(select(City).where(City.is_active == True).order_by(City.name))
            city_objs = city_objs_res.scalars().all()
            cities_to_process = [c.slug for c in city_objs]
            city_name_map = {c.slug: c.name for c in city_objs}
        else:
            cities_to_process = [city]
            city_obj_res = await session.execute(select(City).where(City.slug == city))
            city_obj = city_obj_res.scalar_one_or_none()
            city_name_map = {city: city_obj.name if city_obj else city.title()}
    except Exception as e:
        logger.error(f"Failed to query database for Google Sheets sync: {e}")
        return

    headers = [
        "Доходы", "нал.", "безнал.", "Расходы",
        "зарплата\nфотографа", "зарплата\nстажера", "хоз расход", 
        "расходник", "УСН 6%", "налоги по\nЗП 35,6%", "техника", "аренда", 
        "Остаток конец дня"
    ]

    city_data_list = []

    # --- Build layout and formatting for each city sheet ---------------------
    for sheet_city in cities_to_process:
        city_label = city_name_map.get(sheet_city, sheet_city.title())
        reports = [r for r in all_reports if r.city == sheet_city or r.city is None]
        plans   = [p for p in all_plans if p.city == sheet_city]
        mgmt_list = [m for m in all_mgmt if m.city == sheet_city]

        # Skip city if there are no reports and no plans
        if not reports and not plans:
            continue

        values = []
        merges = []
        formats = []
        widths = {}

        # Set default column widths
        widths[1] = 16  # A
        widths[2] = 16  # B
        widths[3] = 10  # C
        widths[4] = 18  # D
        for i in range(len(headers)):
            widths[5 + i] = 15

        row_idx = 1
        plan_by_project = {p.project_name: p.plan_amount for p in plans if p.project_name}

        # Build list of active project names for this city
        active_proj_names = {p.name for p in all_projects if p.city == sheet_city}
        project_set = set()
        project_set.update(r.project_name for r in reports if r.project_name)
        project_set.update(p.project_name for p in plans if p.project_name and p.project_name in active_proj_names)
        projects_sorted = sorted(project_set)

        by_project = defaultdict(lambda: defaultdict(list))
        for r in reports:
            by_project[r.project_name][r.date.day].append(r)

        c_plan = c_rev = c_cash = c_acq = c_exp = c_grand_exp = 0.0
        c_sal = c_tra = 0.0
        c_cons = c_usn = c_tax = c_tech = c_rent = 0.0

        for p_name in projects_sorted:
            p_data = by_project[p_name]
            p_plan = plan_by_project.get(p_name, 0)
            linked_mgmt = [m for m in mgmt_list if m.project_name == p_name]

            agg = {}
            total_rev = total_cash = total_acq = total_exp = 0.0
            total_sal = total_tra = 0.0
            total_auto_usn = total_auto_tax_zp = 0.0
            p_cons = p_usn = p_tax = p_tech = p_rent = 0.0

            for d in range(1, days_in_month + 1):
                reps = p_data.get(d, [])
                master = max(reps, key=lambda r: float(r.revenue)) if reps else None
                day_rev = float(master.revenue) if master else 0.0
                day_cash = float(master.cash) if master else 0.0
                day_acq = float(master.acquiring) if master else 0.0
                day_exp = float(master.expense) if master else 0.0
                
                day_sal_total = sum(float(r.salary_paid) * r.shift_count for r in reps)
                day_tra_total = sum(float(r.trainee_salary) for r in reps)
                
                day_auto_usn = day_rev * 0.06
                day_auto_tax_zp = (day_sal_total + day_tra_total) * 0.356
                
                def _d_sum(cat): 
                    return float(sum(m.amount for m in linked_mgmt if m.category == cat and m.date.day == d))
                
                day_cons = _d_sum("расходник")
                day_usn  = day_auto_usn + _d_sum("усн_6")
                day_tax  = day_auto_tax_zp + _d_sum("налоги_зп")
                day_tech = _d_sum("техника")
                day_rent = _d_sum("аренда")
                
                day_all_mgmt = day_cons + day_usn + day_tax + day_tech + day_rent
                day_total_dist_exp = day_sal_total + day_tra_total + day_exp + day_all_mgmt
                
                agg[d] = {
                    "reps": reps,
                    "rev": day_rev,
                    "cash": day_cash,
                    "acq": day_acq,
                    "exp": day_exp,
                    "sal_total": day_sal_total,
                    "tra_total": day_tra_total,
                    "cons": day_cons,
                    "usn": day_usn,
                    "tax": day_tax,
                    "tech": day_tech,
                    "rent": day_rent,
                    "total_exp": day_total_dist_exp,
                    "ostatok": day_rev - day_total_dist_exp,
                }
                
                total_rev += day_rev
                total_cash += day_cash
                total_acq += day_acq
                total_exp += day_exp
                total_sal += day_sal_total
                total_tra += day_tra_total
                total_auto_usn += day_auto_usn
                total_auto_tax_zp += day_auto_tax_zp
                
                p_cons += day_cons
                p_usn += day_usn
                p_tax += day_tax
                p_tech += day_tech
                p_rent += day_rent

            total_pct = (total_rev / p_plan) if p_plan > 0 else 0.0
            proj_start_row = row_idx

            # Row 1: Top project banner with "в нал" labels
            row_vals = [""] * 17
            row_vals[0] = p_name
            row_vals[8] = "в нал"
            row_vals[9] = "в нал"
            values.append(row_vals)

            merges.append((row_idx, 1, row_idx, 2))
            # Format row 1 banner
            formats.append((get_range_str(row_idx, 1, row_idx, 17), CellFormat(
                backgroundColor=FILL_PROJECT,
                textFormat=textFormat(bold=True, fontSize=9),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            # Special red text format for "в нал"
            formats.append((get_range_str(row_idx, 9, row_idx, 10), CellFormat(
                textFormat=textFormat(bold=True, fontSize=9, foregroundColor=C_RED),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE'
            )))
            row_idx += 1

            # Row 2: Headers
            row_vals = [""] * 17
            row_vals[0] = "План"
            row_vals[1] = p_plan
            row_vals[2] = "ДАТА"
            row_vals[3] = "ФИО"
            for i, h in enumerate(headers):
                row_vals[4 + i] = h.replace("\n", " ")
            values.append(row_vals)

            # Left side project details styling
            formats.append((get_range_str(row_idx, 1, row_idx, 1), CellFormat(
                backgroundColor=FILL_PROJECT,
                textFormat=textFormat(bold=False, fontSize=9),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            formats.append((get_range_str(row_idx, 2, row_idx, 2), CellFormat(
                backgroundColor=FILL_PROJECT,
                textFormat=textFormat(bold=False, fontSize=9),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                numberFormat=FMT_INTEGER,
                borders=BORDER_THIN
            )))
            # Date/FIO columns
            formats.append((get_range_str(row_idx, 3, row_idx, 4), CellFormat(
                backgroundColor=FILL_BLUE,
                textFormat=textFormat(bold=True, fontSize=9),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            # Headers colors mirroring excel.py
            for i, h in enumerate(headers):
                c_idx = 5 + i
                h_range = get_range_str(row_idx, c_idx, row_idx, c_idx)
                if h in ["Доходы", "зарплата\nфотографа", "Остаток конец дня"]:
                    t_color = C_GREEN
                elif h in ["нал.", "безнал.", "зарплата\nстажера"]:
                    t_color = C_RED
                else:
                    t_color = C_BLUE
                formats.append((h_range, CellFormat(
                    backgroundColor=FILL_BLUE,
                    textFormat=textFormat(bold=True, fontSize=9, foregroundColor=t_color),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                    borders=BORDER_THIN
                )))
            row_idx += 1

            # Row 3: Totals row ("Общая")
            grand_total_exp = total_sal + total_tra + total_exp + (p_cons + p_usn + p_tax + p_tech + p_rent)

            c_plan += p_plan
            c_rev += total_rev
            c_cash += total_cash
            c_acq += total_acq
            c_exp += total_exp
            c_sal += total_sal
            c_tra += total_tra
            c_cons += p_cons
            c_usn += p_usn
            c_tax += p_tax
            c_tech += p_tech
            c_rent += p_rent
            c_grand_exp += grand_total_exp

            row_vals = [""] * 17
            row_vals[0] = "Выполнено"
            row_vals[1] = total_pct
            row_vals[2] = ""
            row_vals[3] = "Общая"
            row_vals[4] = total_rev
            row_vals[5] = total_cash
            row_vals[6] = total_acq
            row_vals[7] = grand_total_exp
            row_vals[8] = total_sal
            row_vals[9] = total_tra
            row_vals[10] = total_exp
            row_vals[11] = p_cons
            row_vals[12] = p_usn
            row_vals[13] = p_tax
            row_vals[14] = p_tech
            row_vals[15] = p_rent
            row_vals[16] = total_rev - grand_total_exp
            values.append(row_vals)

            formats.append((get_range_str(row_idx, 1, row_idx, 1), CellFormat(
                backgroundColor=FILL_PROJECT,
                textFormat=textFormat(bold=False, fontSize=9),
                horizontalAlignment='LEFT', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            formats.append((get_range_str(row_idx, 2, row_idx, 2), CellFormat(
                backgroundColor=FILL_PROJECT,
                textFormat=textFormat(bold=False, fontSize=9),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                numberFormat=FMT_PERCENT,
                borders=BORDER_THIN
            )))
            formats.append((get_range_str(row_idx, 3, row_idx, 4), CellFormat(
                backgroundColor=FILL_GRAY,
                textFormat=textFormat(bold=True, fontSize=9),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            formats.append((get_range_str(row_idx, 5, row_idx, 17), CellFormat(
                backgroundColor=FILL_BLUE_IN,
                textFormat=textFormat(bold=True, fontSize=9),
                numberFormat=FMT_CURRENCY,
                borders=BORDER_THIN
            )))
            row_idx += 1

            days_start_row = row_idx

            # Rows 4 to N: Calendar Days
            for d in range(1, days_in_month + 1):
                day_data = agg[d]
                reps = day_data["reps"]
                
                # Split shared reports names
                visual_rows = []
                for r in reps:
                    names = re.split(r" \+ |,|;", r.employee_name or "Unknown")
                    names = [n.strip() for n in names if n.strip()]
                    for name in names:
                        visual_rows.append({
                            "name": name,
                            "sal": float(r.salary_paid),
                            "trainee": float(r.trainee_salary) if names.index(name) == 0 else 0.0
                        })
                
                n_rows = max(1, len(visual_rows))
                start_r = row_idx
                end_r = row_idx + n_rows - 1

                row_fill = FILL_WHITE if d % 2 == 0 else FILL_GRAY
                date_label = f"{d} {get_month_label_short(month)}"

                # Loop to add cells for visual rows
                for idx in range(n_rows):
                    row_vals = [""] * 17
                    if idx == 0:
                        row_vals[2] = date_label
                        row_vals[4] = day_data["rev"] if day_data["rev"] != 0 else ""
                        row_vals[5] = day_data["cash"] if day_data["cash"] != 0 else ""
                        row_vals[6] = day_data["acq"] if day_data["acq"] != 0 else ""
                        row_vals[7] = day_data["total_exp"] if day_data["total_exp"] != 0 else ""
                        row_vals[10] = day_data["exp"] if day_data["exp"] != 0 else ""
                        row_vals[11] = day_data["cons"] if day_data["cons"] != 0 else ""
                        row_vals[12] = day_data["usn"] if day_data["usn"] != 0 else ""
                        row_vals[13] = day_data["tax"] if day_data["tax"] != 0 else ""
                        row_vals[14] = day_data["tech"] if day_data["tech"] != 0 else ""
                        row_vals[15] = day_data["rent"] if day_data["rent"] != 0 else ""
                        row_vals[16] = day_data["ostatok"] if day_data["ostatok"] != 0 else ""

                    if visual_rows:
                        vrow = visual_rows[idx]
                        fname = vrow["name"].split()[0] if vrow["name"] else "Unknown"
                        row_vals[3] = fname
                        row_vals[8] = vrow["sal"] if vrow["sal"] != 0 else ""
                        row_vals[9] = vrow["trainee"] if vrow["trainee"] != 0 else ""
                    
                    values.append(row_vals)
                    row_idx += 1

                # Apply Merges and Formatting for the day
                merges.append((start_r, 1, end_r, 1)) # Empty col A
                merges.append((start_r, 2, end_r, 2)) # Empty col B
                merges.append((start_r, 3, end_r, 3)) # Date
                
                merges.append((start_r, 5, end_r, 5)) # Rev
                merges.append((start_r, 6, end_r, 6)) # Cash
                merges.append((start_r, 7, end_r, 7)) # Acq
                merges.append((start_r, 8, end_r, 8)) # Total Exp

                merges.append((start_r, 11, end_r, 11)) # Exp
                merges.append((start_r, 12, end_r, 12)) # Cons
                merges.append((start_r, 13, end_r, 13)) # USN
                merges.append((start_r, 14, end_r, 14)) # Tax
                merges.append((start_r, 15, end_r, 15)) # Tech
                merges.append((start_r, 16, end_r, 16)) # Rent
                merges.append((start_r, 17, end_r, 17)) # Ostatok

                # Cell styling
                formats.append((get_range_str(start_r, 1, end_r, 2), CellFormat(backgroundColor=row_fill, borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 3, end_r, 3), CellFormat(
                    backgroundColor=row_fill,
                    textFormat=textFormat(bold=True, fontSize=9),
                    horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                    borders=BORDER_THIN
                )))
                
                # Green highlight for Revenues, Total Exp, Ostatok
                formats.append((get_range_str(start_r, 5, end_r, 5), CellFormat(backgroundColor=FILL_GREEN, textFormat=textFormat(foregroundColor=C_GREEN, fontSize=9), numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 8, end_r, 8), CellFormat(backgroundColor=FILL_GREEN, textFormat=textFormat(foregroundColor=C_GREEN, fontSize=9), numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 17, end_r, 17), CellFormat(backgroundColor=FILL_GREEN, textFormat=textFormat(foregroundColor=C_GREEN, fontSize=9), numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                
                formats.append((get_range_str(start_r, 6, end_r, 6), CellFormat(backgroundColor=row_fill, numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 7, end_r, 7), CellFormat(backgroundColor=row_fill, numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 11, end_r, 16), CellFormat(backgroundColor=row_fill, numberFormat=FMT_CURRENCY, horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                
                # Individual employee rows
                formats.append((get_range_str(start_r, 4, end_r, 4), CellFormat(backgroundColor=row_fill, textFormat=textFormat(fontSize=9), horizontalAlignment='CENTER', verticalAlignment='MIDDLE', borders=BORDER_THIN)))
                formats.append((get_range_str(start_r, 9, end_r, 10), CellFormat(backgroundColor=row_fill, textFormat=textFormat(fontSize=9), numberFormat=FMT_CURRENCY, borders=BORDER_THIN)))

            # Gap between projects
            values.append([""] * 17)
            values.append([""] * 17)
            row_idx += 2

        # --- City-Wide Totals Block ("ИТОГО ПО ВСЕМ ПРОЕКТАМ") ------------------
        if len(projects_sorted) > 0:
            values.append([""] * 17)
            row_idx += 1

            row_vals = [""] * 17
            row_vals[0] = f"ИТОГО ПО ВСЕМ ПРОЕКТАМ — {city_label}"
            values.append(row_vals)
            merges.append((row_idx, 1, row_idx, 17))
            formats.append((get_range_str(row_idx, 1, row_idx, 17), CellFormat(
                backgroundColor=FILL_RED_HDR,
                textFormat=textFormat(bold=True, foregroundColor=C_WHITE, fontSize=10),
                horizontalAlignment='CENTER', verticalAlignment='MIDDLE',
                borders=BORDER_THIN
            )))
            row_idx += 1

            totals_start_row = row_idx

            metrics = [
                ("Доходы", c_rev, FILL_GREEN),
                ("нал.", c_cash, None),
                ("безнал.", c_acq, None),
                ("Расходы", c_grand_exp, FILL_GREEN),
                ("зарплата Фотографа", c_sal, None),
                ("зарплата Стажера", c_tra, None),
                ("хоз расход", c_exp, None),
                ("расходник", c_cons, None),
                ("УСН 6%", c_usn, None),
                ("налоги по ЗП 35,6%", c_tax, None),
                ("техника", c_tech, None),
                ("аренда", c_rent, None),
                ("другое", 0.0, None), 
                ("Остаток конец дня", c_rev - c_grand_exp, FILL_GREEN)
            ]

            # Vertical Metrics Layout (Col A-D)
            for i, (name, val, fill) in enumerate(metrics):
                row_vals = [""] * 17
                if i == 0:
                    row_vals[0] = "План"
                    row_vals[1] = c_plan
                elif i == 1:
                    row_vals[0] = "Выполнено"
                    row_vals[1] = (c_rev / c_plan) if c_plan > 0 else 0.0

                row_vals[2] = name
                row_vals[3] = val
                values.append(row_vals)

                # Col A-B styling
                if i == 0:
                    formats.append((get_range_str(row_idx, 1, row_idx, 1), CellFormat(textFormat=textFormat(bold=True, fontSize=9), borders=BORDER_THIN)))
                    formats.append((get_range_str(row_idx, 2, row_idx, 2), CellFormat(numberFormat=FMT_INTEGER, horizontalAlignment='CENTER', borders=BORDER_THIN)))
                elif i == 1:
                    formats.append((get_range_str(row_idx, 1, row_idx, 1), CellFormat(textFormat=textFormat(bold=True, foregroundColor=C_RED, fontSize=9), borders=BORDER_THIN)))
                    formats.append((get_range_str(row_idx, 2, row_idx, 2), CellFormat(backgroundColor=FILL_GREEN, numberFormat=FMT_PERCENT, horizontalAlignment='CENTER', borders=BORDER_THIN)))
                else:
                    formats.append((get_range_str(row_idx, 1, row_idx, 2), CellFormat(borders=BORDER_THIN)))

                # Col C-D styling
                bg_color = fill or FILL_WHITE
                formats.append((get_range_str(row_idx, 3, row_idx, 3), CellFormat(
                    backgroundColor=bg_color,
                    textFormat=textFormat(bold=(fill is not None), fontSize=9),
                    borders=BORDER_THIN
                )))
                formats.append((get_range_str(row_idx, 4, row_idx, 4), CellFormat(
                    backgroundColor=bg_color,
                    numberFormat=FMT_CURRENCY,
                    borders=BORDER_THIN
                )))
                
                row_idx += 1

            totals_end_row = row_idx - 1
            # Add thick outer border effect for totals block (by putting a boundary format)
            # This is already handled nicely by thin borders on all cells!

        city_data_list.append((sheet_city, city_label, {
            "values": values,
            "merges": merges,
            "formats": formats,
            "widths": widths
        }))

    if not city_data_list:
        logger.info("No data compiled for Google Sheets synchronization.")
        return

    # Trigger synchronous Google Sheet operations in background worker thread
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _do_sync_in_thread, config.google_sheets_spreadsheet_id, year, month, city_data_list)


async def sync_data_to_sheets_bg(year: int, month: int, city: str = "all"):
    """
    Background worker task that instantiates a new database session and
    triggers the synchronization.
    """
    from bot.database.db import SessionLocal
    async with SessionLocal() as session:
        await sync_data_to_sheets(session, year, month, city)


from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_report_nav() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="â¬…ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="report:back")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    b.adjust(2)
    return b.as_markup()


def kb_city() -> InlineKeyboardMarkup:
    """City selector during report submission."""
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", callback_data="report:city:gomel")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",  callback_data="report:city:minsk")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    b.adjust(2, 1)
    return b.as_markup()


def kb_city_for_employee(tg_id: int) -> InlineKeyboardMarkup:
    """Admin panel: set city for employee."""
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ",        callback_data=f"emp:city:gomel:{tg_id}")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",         callback_data=f"emp:city:minsk:{tg_id}")
    b.button(text="â“ Ð¡Ð¿Ñ€Ð°ÑˆÐ¸Ð²Ð°Ñ‚ÑŒ",    callback_data=f"emp:city:none:{tg_id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",         callback_data=f"emp:view:{tg_id}")
    b.adjust(2, 1, 1)
    return b.as_markup()

def kb_city_selector() -> InlineKeyboardMarkup:
    """General city selector for Cabinet."""
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", callback_data="city:gomel")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",  callback_data="city:minsk")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="cab:close")
    b.adjust(2, 1)
    return b.as_markup()


def kb_cabinet_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“Š ÐœÐ¾Ñ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°", callback_data="cab:stats")
    b.button(text="ðŸ“œ Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²Ñ‹Ð¿Ð»Ð°Ñ‚", callback_data="cab:history")
    b.button(text="âŒ Ð—Ð°ÐºÑ€Ñ‹Ñ‚ÑŒ",        callback_data="cab:close")
    b.adjust(1)
    return b.as_markup()


def kb_analytics_cities() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸŒ Ð’ÑÐµ Ð³Ð¾Ñ€Ð¾Ð´Ð°", callback_data="chart_city:all")
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", callback_data="chart_city:gomel")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",  callback_data="chart_city:minsk")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",  callback_data="adm:back")
    b.adjust(1, 2, 1)
    return b.as_markup()


def kb_analytics(city: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“ˆ Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ° (30 Ð´Ð½)", callback_data=f"chart:revenue:{city}")
    b.button(text="ðŸ“Š Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ° Ð·Ð° Ð³Ð¾Ð´", callback_data=f"chart:revenue_year:{city}")
    b.button(text="ðŸŽ¯ Ð’Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¸Ðµ Ð¿Ð»Ð°Ð½Ð¾Ð²", callback_data=f"chart:plans:{city}")
    b.button(text="â—€ï¸ Ð’Ñ‹Ð±Ð¾Ñ€ Ð³Ð¾Ñ€Ð¾Ð´Ð°", callback_data="adm:analytics")
    b.adjust(1)
    return b.as_markup()


def menu_employee() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ðŸ“‹ Ð¡Ð´Ð°Ñ‚ÑŒ Ð¾Ñ‚Ñ‡ÐµÑ‚")],
            [KeyboardButton(text="ðŸ“– Ð˜Ð½ÑÑ‚Ñ€ÑƒÐºÑ†Ð¸Ñ")],
        ],
        resize_keyboard=True
    )


def menu_manager() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ðŸ“‹ Ð¡Ð´Ð°Ñ‚ÑŒ Ð¾Ñ‚Ñ‡ÐµÑ‚")],
            [KeyboardButton(text="ðŸ“‹ ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð¾Ñ‚ Ð¼ÐµÐ½ÐµÐ´Ð¶ÐµÑ€Ð°")],
            [KeyboardButton(text="âš™ï¸ ÐŸÐ°Ð½ÐµÐ»ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾")],
            [KeyboardButton(text="ðŸ“– Ð˜Ð½ÑÑ‚Ñ€ÑƒÐºÑ†Ð¸Ñ")],
        ],
        resize_keyboard=True
    )


def menu_admin() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ðŸ“‹ Ð¡Ð´Ð°Ñ‚ÑŒ Ð¾Ñ‚Ñ‡ÐµÑ‚")],
            [KeyboardButton(text="ðŸ“‹ ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð¾Ñ‚ Ð¼ÐµÐ½ÐµÐ´Ð¶ÐµÑ€Ð°")],
            [KeyboardButton(text="âš™ï¸ ÐÐ´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»ÑŒ")],
            [KeyboardButton(text="ðŸ“– Ð˜Ð½ÑÑ‚Ñ€ÑƒÐºÑ†Ð¸Ñ")],
        ],
        resize_keyboard=True
    )


def kb_cancel() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    return b.as_markup()


def kb_cancel_skip(cancel_cb: str = "report:cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="â¬…ï¸ ÐÐ°Ð·Ð°Ð´",      callback_data="report:back")
    b.button(text="â© ÐŸÑ€Ð¾Ð¿ÑƒÑÑ‚Ð¸Ñ‚ÑŒ",  callback_data="report:skip")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°",      callback_data=cancel_cb)
    b.adjust(2, 1)
    return b.as_markup()


def kb_use_today(today_str: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"ðŸ“… Ð¡ÐµÐ³Ð¾Ð´Ð½Ñ ({today_str})", callback_data="report:use_today")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_confirm(is_editing: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="âœ… ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð¸Ñ‚ÑŒ" if not is_editing else "âœ… Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ", callback_data="report:confirm")
    if is_editing:
        b.button(text="âœï¸ Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ Ð´Ð°Ð»ÐµÐµ", callback_data="report:edit")
        b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð° (Ðº Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ñƒ)", callback_data="report:cancel")
    else:
        b.button(text="âœï¸ Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ", callback_data="report:edit")
        b.button(text="â¬…ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="report:back")
        b.button(text="ðŸ”„ Ð—Ð°Ð½Ð¾Ð²Ð¾", callback_data="report:restart")
        b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    
    if is_editing:
        b.adjust(1)
    else:
        b.adjust(1, 1, 2, 1)
    return b.as_markup()


def kb_edit_fields() -> InlineKeyboardMarkup:
    fields = [
        ("Ð”Ð°Ñ‚Ð°", "date"), ("ÐŸÑ€Ð¾ÐµÐºÑ‚", "project"), ("Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº", "employee_name"),
        ("Ð¡Ð¼ÐµÐ½Ñ‹", "shift_count"), ("Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ°", "revenue"), ("ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ", "cash"),
        ("Ð‘ÐµÐ·Ð½Ð°Ð»", "acquiring"), ("Ð Ð°ÑÑ…Ð¾Ð´", "expense"), ("ÐšÐ°ÑÑÐ°", "cash_balance"),
        ("ÐŸÐ¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»Ð¸", "visitors"), ("Ð”Ð ", "birthdays"), ("ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹", "comment")
    ]
    b = InlineKeyboardBuilder()
    for text, field in fields:
        b.button(text=text, callback_data=f"edit:{field}")
    b.button(text="â¬…ï¸ ÐÐ°Ð·Ð°Ð´ Ðº Ð¿Ñ€ÐµÐ²ÑŒÑŽ", callback_data="report:preview")
    b.adjust(3)
    return b.as_markup()


def kb_admin_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“Š ÐžÑ‚Ñ‡Ñ‘Ñ‚Ñ‹",               callback_data="adm:reports")
    b.button(text="ðŸ‘¥ Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¸",           callback_data="adm:employees")
    b.button(text="ðŸ¢ ÐŸÑ€Ð¾ÐµÐºÑ‚Ñ‹",             callback_data="adm:projects")
    b.button(text="ðŸŽ¯ ÐŸÐ»Ð°Ð½Ñ‹ Ð¿Ñ€Ð¾Ð´Ð°Ð¶",         callback_data="adm:plans")
    b.button(text="ðŸ“ˆ Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð»Ð°Ð½Ð¾Ð²",    callback_data="adm:stats")
    b.button(text="ðŸ“Š ÐÐ½Ð°Ð»Ð¸Ñ‚Ð¸ÐºÐ°",           callback_data="adm:analytics")
    b.button(text="ðŸ’¼ Ð—ÐŸ Ð¼ÐµÐ½ÐµÐ´Ð¶ÐµÑ€Ð°",         callback_data="adm:manager_salary")
    b.button(text="ðŸ“‚ Ð£Ð¿Ñ€Ð°Ð²Ð». Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹",       callback_data="adm:mgmt_expenses")
    b.adjust(2)
    return b.as_markup()


def kb_month_select(current_year: int, current_month: int, city: str = None) -> InlineKeyboardMarkup:
    """Pick month for monthly calendar report."""
    import calendar as cal
    b = InlineKeyboardBuilder()
    # Show last 6 months + current
    from datetime import date
    months = []
    y, m = current_year, current_month
    for _ in range(6):
        months.insert(0, (y, m))
        m -= 1
        if m == 0:
            m = 12; y -= 1
    for yr, mo in months:
        label = f"{cal.month_abbr[mo]} {yr}"
        cb = f"month:{yr}:{mo}"
        if city:
            cb += f":{city}"
        b.button(text=label, callback_data=cb)
    b.button(text="âŒ Ð—Ð°ÐºÑ€Ñ‹Ñ‚ÑŒ", callback_data="adm:back")
    b.adjust(3, 3, 1)
    return b.as_markup()


def kb_mgmt_month_select(current_year: int, current_month: int) -> InlineKeyboardMarkup:
    """Pick month for monthly management expenses (like Rent)."""
    import calendar as cal
    b = InlineKeyboardBuilder()
    from datetime import date
    months = []
    y, m = current_year, current_month
    for _ in range(6):
        months.insert(0, (y, m))
        m -= 1
        if m == 0:
            m = 12; y -= 1
    for yr, mo in months:
        label = f"{cal.month_abbr[mo]} {yr}"
        b.button(text=label, callback_data=f"mgmt:month:{yr}:{mo}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:mgmt_expenses")
    b.adjust(3, 3, 1)
    return b.as_markup()


def kb_monthly_report_cities() -> InlineKeyboardMarkup:
    """City picker for monthly report."""
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", callback_data="period:monthly_city:gomel")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",  callback_data="period:monthly_city:minsk")
    b.button(text="ðŸŒ Ð’ÑÐµ Ð³Ð¾Ñ€Ð¾Ð´Ð°", callback_data="period:monthly_city:all")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",  callback_data="adm:back")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_report_period() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“… ÐœÐµÑÑÑ‡Ð½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚", callback_data="period:monthly_calendar")
    b.button(text="ðŸ“Š ÐÐ½Ð°Ð»Ð¸Ñ‚Ð¸ÐºÐ° (Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ¸)", callback_data="adm:analytics")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",         callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_pending_user(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="âœ… Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº", callback_data=f"pending:emp:{tg_id}")
    b.button(text="ðŸ’¼ Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹", callback_data=f"pending:mgr:{tg_id}")
    b.button(text="âŒ ÐžÑ‚ÐºÐ»Ð¾Ð½Ð¸Ñ‚ÑŒ", callback_data=f"pending:no:{tg_id}")
    b.adjust(2, 1)
    return b.as_markup()


def kb_report_review(report_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="âœ… ÐŸÑ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð¾", callback_data=f"review:ok:{report_id}")
    b.button(text="âŒ ÐžÑ‚ÐºÐ»Ð¾Ð½Ð¸Ñ‚ÑŒ", callback_data=f"review:reject_start:{report_id}")
    if is_admin:
        b.button(text="âœï¸ Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ", callback_data=f"review:edit:{report_id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="review:list")
    b.adjust(2)
    return b.as_markup()


def kb_employee_cities() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", callback_data="adm:employees:city:gomel")
    b.button(text="ðŸŒ† ÐœÐ¸Ð½ÑÐº",  callback_data="adm:employees:city:minsk")
    b.button(text="â“ Ð‘ÐµÐ· Ð³Ð¾Ñ€Ð¾Ð´Ð°", callback_data="adm:employees:city:none")
    b.button(text="âž• Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ Ð¿Ð¾ ID", callback_data="emp:add")
    b.button(text="ðŸ“¥ Ð—Ð°ÑÐ²ÐºÐ¸", callback_data="adm:pending")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",  callback_data="adm:back")
    b.adjust(2, 1, 2, 1)
    return b.as_markup()


def kb_employee_list(employees: list, city_label: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    b.button(text=f"â”€â”€â”€ {city_label} â”€â”€â”€", callback_data="none")
    
    for emp in sorted(employees, key=lambda x: x.full_name):
        icon = "ðŸ‘‘" if emp.role.value == "admin" else "ðŸ‘¤"
        name = emp.full_name or emp.username or str(emp.telegram_id)
        b.button(text=f"{icon} {name}", callback_data=f"emp:view:{emp.telegram_id}")
            
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´ Ðº Ð³Ð¾Ñ€Ð¾Ð´Ð°Ð¼", callback_data="adm:employees")
    b.adjust(1)
    return b.as_markup()


def kb_employee_actions(tg_id: int, role: str, city: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if role == "employee":
        b.button(text="ðŸ‘‘ Ð¡Ð´ÐµÐ»Ð°Ñ‚ÑŒ Ð°Ð´Ð¼Ð¸Ð½Ð¾Ð¼",   callback_data=f"emp:mkadmin:{tg_id}")
        b.button(text="ðŸ’¼ ÐÐ°Ð·Ð½Ð°Ñ‡Ð¸Ñ‚ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¼", callback_data=f"emp:mkmgr:{tg_id}")
    elif role == "manager":
        b.button(text="ðŸ‘‘ Ð¡Ð´ÐµÐ»Ð°Ñ‚ÑŒ Ð°Ð´Ð¼Ð¸Ð½Ð¾Ð¼",   callback_data=f"emp:mkadmin:{tg_id}")
        b.button(text="ðŸ‘¤ Ð¡Ð´ÐµÐ»Ð°Ñ‚ÑŒ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¾Ð¼", callback_data=f"emp:mkemp:{tg_id}")
    else:
        b.button(text="ðŸ‘¤ Ð¡Ð½ÑÑ‚ÑŒ Ð¿Ñ€Ð°Ð²Ð°",       callback_data=f"emp:rmadmin:{tg_id}")
    city_label = {"gomel": "ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ðŸŒ† ÐœÐ¸Ð½ÑÐº"}.get(city or "", "â“ Ð½Ðµ Ð·Ð°Ð´Ð°Ð½")
    b.button(text=f"ðŸ™ Ð“Ð¾Ñ€Ð¾Ð´: {city_label}",  callback_data=f"emp:setcity:{tg_id}")
    
    if role == "manager":
        b.button(text="ðŸ“ ÐŸÑ€Ð¸Ð²ÑÐ·Ð°Ñ‚ÑŒ Ð¿Ñ€Ð¾ÐµÐºÑ‚",   callback_data=f"emp:bindproj:{tg_id}")

    b.button(text="ðŸ“‹ ÐÑ€Ñ…Ð¸Ð² Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð²",         callback_data=f"emp:archive:{tg_id}")
    b.button(text="ðŸ—‘ Ð£Ð´Ð°Ð»Ð¸Ñ‚ÑŒ",               callback_data=f"emp:delete:{tg_id}")
    b.button(text="â—€ï¸ Ðš ÑÐ¿Ð¸ÑÐºÑƒ",              callback_data="adm:employees")
    b.adjust(1)
    return b.as_markup()


def kb_report_search_nav() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“… ÐŸÐ¾Ð¸ÑÐº Ð¿Ð¾ Ð´Ð°Ñ‚Ðµ", callback_data="adm:reports_by_date")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",           callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_salary_levels(levels: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lvl in sorted(levels, key=lambda x: x.level):
        mx = f"Ð´Ð¾ {lvl.threshold_max:.0f}" if lvl.threshold_max else "âˆž"
        b.button(
            text=f"Ð£Ñ€.{lvl.level}: {lvl.threshold_min:.0f}â€“{mx}â‚½ | {lvl.percentage*100:.0f}%",
            callback_data=f"sal:edit:{lvl.id}"
        )
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_plans(plans_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
    
    for city in sorted_cities:
        plans = plans_by_city[city]
        if not plans: continue
        
        city_label = {"gomel": "ðŸ™ Ð“ÐžÐœÐ•Ð›Ð¬", "minsk": "ðŸŒ† ÐœÐ˜ÐÐ¡Ðš"}.get(city, "ðŸŒ ÐžÐ‘Ð©Ð˜Ð• ÐŸÐ›ÐÐÐ«")
        b.button(text=f"â”€â”€â”€ {city_label} â”€â”€â”€", callback_data="none")
        
        for p in plans:
            proj = p.project_name or "Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹"
            period = "Ð´ÐµÐ½ÑŒ" if p.period == "day" else "Ð¼ÐµÑ"
            label = f"{'âœ…' if p.is_active else 'â¸'} {proj}: {p.plan_amount:.0f}â‚½/{period}"
            b.button(text=label, callback_data=f"plan:toggle:{p.id}")
            b.button(text="ðŸ—‘", callback_data=f"plan:delete:{p.id}")
    
    b.button(text="âž• Ð”Ð¾Ð±Ð°Ð²Ð¸Ñ‚ÑŒ Ð¿Ð»Ð°Ð½", callback_data="plan:add")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",        callback_data="adm:back")
    
    # Adjust: 2 columns for (label, trash) pairs, 1 for headers and bottom buttons
    # We dynamically build the layout
    layout = []
    for city in sorted_cities:
        if plans_by_city[city]:
            layout.append(1) # Header
            for _ in plans_by_city[city]:
                layout.append(2) # Plan + Trash
    layout.append(1) # Add plan
    layout.append(1) # Back
    
    b.adjust(*layout)
    return b.as_markup()


def kb_mgmt_categories(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ§º Ð Ð°ÑÑ…Ð¾Ð´Ð½Ð¸Ðº",  callback_data="mgmt:cat:Ñ€Ð°ÑÑ…Ð¾Ð´Ð½Ð¸Ðº")
    if is_admin:
        b.button(text="ðŸ  ÐÑ€ÐµÐ½Ð´Ð°",      callback_data="mgmt:cat:Ð°Ñ€ÐµÐ½Ð´Ð°")
    b.button(text="âš™ï¸ Ð¢ÐµÑ…Ð½Ð¸ÐºÐ°",     callback_data="mgmt:cat:Ñ‚ÐµÑ…Ð½Ð¸ÐºÐ°")
    if is_admin:
        b.button(text="ðŸ¦ Ð£Ð¡Ð 6%",      callback_data="mgmt:cat:ÑƒÑÐ½_6")
        b.button(text="âš–ï¸ ÐÐ°Ð»Ð¾Ð³Ð¸ Ð—ÐŸ 35.6%", callback_data="mgmt:cat:Ð½Ð°Ð»Ð¾Ð³Ð¸_Ð·Ð¿")
    b.button(text="âž• Ð”Ñ€ÑƒÐ³Ð¾Ðµ",      callback_data="mgmt:cat:Ð´Ñ€ÑƒÐ³Ð¾Ðµ")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",      callback_data="adm:back")
    
    # Adjust: if admin, 2-2-2. If manager, 2-1-1
    if is_admin:
        b.adjust(2, 2, 2)
    else:
        b.adjust(2, 1, 1)
    return b.as_markup()


def kb_mgmt_categories_mgr() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ§º Ð Ð°ÑÑ…Ð¾Ð´Ð½Ð¸Ðº",  callback_data="mgr:mgmt:cat:Ñ€Ð°ÑÑ…Ð¾Ð´Ð½Ð¸Ðº")
    b.button(text="âš™ï¸ Ð¢ÐµÑ…Ð½Ð¸ÐºÐ°",     callback_data="mgr:mgmt:cat:Ñ‚ÐµÑ…Ð½Ð¸ÐºÐ°")
    b.button(text="âž• Ð”Ñ€ÑƒÐ³Ð¾Ðµ",      callback_data="mgr:mgmt:cat:Ð´Ñ€ÑƒÐ³Ð¾Ðµ")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",      callback_data="mgr:mgmt_start")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_mgmt_date(today_str: str, yesterday_str: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"ðŸ“… Ð¡ÐµÐ³Ð¾Ð´Ð½Ñ ({today_str})", callback_data="mgr:mgmt:date:today")
    b.button(text=f"ðŸ“… Ð’Ñ‡ÐµÑ€Ð° ({yesterday_str})", callback_data="mgr:mgmt:date:yesterday")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="mgr:panel")
    b.adjust(1)
    return b.as_markup()


def kb_projects(projects_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    cities = sorted(projects_by_city.keys())
    for city in cities:
        projs = projects_by_city[city]
        if not projs: continue
        
        city_label = {"gomel": "ðŸ™ Ð“ÐžÐœÐ•Ð›Ð¬", "minsk": "ðŸŒ† ÐœÐ˜ÐÐ¡Ðš"}.get(city, "â“ Ð‘Ð•Ð— Ð“ÐžÐ ÐžÐ”Ð")
        b.button(text=f"â”€â”€â”€ {city_label} â”€â”€â”€", callback_data="none")
        
        for p in sorted(projs, key=lambda x: x.name):
            icon = "âœ…" if p.is_active else "â¸"
            b.button(text=f"{icon} {p.name}", callback_data=f"proj:view:{p.id}")
            
    b.button(text="âž• Ð¡Ð¾Ð·Ð´Ð°Ñ‚ÑŒ Ð¿Ñ€Ð¾ÐµÐºÑ‚", callback_data="proj:add")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",           callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_project_actions(project_id: int, is_active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    toggle_text = "â¸ ÐŸÑ€Ð¸Ð¾ÑÑ‚Ð°Ð½Ð¾Ð²Ð¸Ñ‚ÑŒ" if is_active else "â–¶ï¸ ÐÐºÑ‚Ð¸Ð²Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ"
    b.button(text=toggle_text,      callback_data=f"proj:toggle:{project_id}")
    b.button(text="ðŸ—‘ Ð£Ð´Ð°Ð»Ð¸Ñ‚ÑŒ",     callback_data=f"proj:delete:{project_id}")
    b.button(text="â—€ï¸ Ðš ÑÐ¿Ð¸ÑÐºÑƒ",     callback_data="adm:projects")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_plan(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸŒ ÐžÐ‘Ð©Ð˜Ð™ ÐŸÐ›ÐÐ (Ð½Ð° Ð²ÐµÑÑŒ Ð³Ð¾Ñ€Ð¾Ð´)", callback_data="proj:plan:0")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"proj:plan:{p.id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:plans")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_report(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"report:proj:{p.id}")
    b.button(text="âŒ ÐžÑ‚Ð¼ÐµÐ½Ð°", callback_data="report:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_search(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ” Ð’Ð¡Ð• ÐŸÐ ÐžÐ•ÐšÐ¢Ð«", callback_data="report:search:0")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"report:search:{p.id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´",   callback_data="adm:reports_by_date")
    b.adjust(1)
    return b.as_markup()


def kb_report_list_mini(reports: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in reports:
        # Date and project name
        date_str = r.date.strftime("%d.%m")
        # Truncate project name if too long
        proj = (r.project_name[:15] + "..") if len(r.project_name) > 17 else r.project_name
        checked = "âœ…" if r.is_reviewed else "â³"
        b.button(text=f"{checked} {date_str} | {proj} | {r.revenue}", callback_data=f"review:view:{r.id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:reports")
    b.adjust(1)
    return b.as_markup()


def kb_employee_archive_nav(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="â—€ï¸ Ðš Ð¿Ñ€Ð¾Ñ„Ð¸Ð»ÑŽ", callback_data=f"emp:view:{tg_id}")
    return b.as_markup()


def kb_back(cb: str = "adm:back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data=cb)
    return b.as_markup()


def kb_projects_for_user_binding(projects: list, tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ”“ ÐÐ•Ð¢ ÐŸÐ Ð˜Ð’Ð¯Ð—ÐšÐ˜ (Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹)", callback_data=f"emp:saveproj:0:{tg_id}")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"emp:saveproj:{p.id}:{tg_id}")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data=f"emp:view:{tg_id}")
    b.adjust(1)
    return b.as_markup()


def kb_report_search_nav() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“… ÐŸÐ¾Ð¸ÑÐº Ð¿Ð¾ Ð´Ð°Ñ‚Ðµ", callback_data="adm:reports_by_date")
    b.button(text="ðŸ“… ÐœÐµÑÑÑ‡Ð½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ (Excel)", callback_data="period:monthly_calendar")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()



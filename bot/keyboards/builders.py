from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_report_nav() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="report:back")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(2)
    return b.as_markup()


def kb_city() -> InlineKeyboardMarkup:
    """City selector during report submission."""
    b = InlineKeyboardBuilder()
    b.button(text="🏙 Гомель", callback_data="report:city:gomel")
    b.button(text="🌆 Минск",  callback_data="report:city:minsk")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(2, 1)
    return b.as_markup()


def kb_city_for_employee(tg_id: int) -> InlineKeyboardMarkup:
    """Admin panel: set city for employee."""
    b = InlineKeyboardBuilder()
    b.button(text="🏙 Гомель",        callback_data=f"emp:city:gomel:{tg_id}")
    b.button(text="🌆 Минск",         callback_data=f"emp:city:minsk:{tg_id}")
    b.button(text="❓ Спрашивать",    callback_data=f"emp:city:none:{tg_id}")
    b.button(text="◀️ Назад",         callback_data=f"emp:view:{tg_id}")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_cabinet_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Моя статистика", callback_data="cab:stats")
    b.button(text="📜 История выплат", callback_data="cab:history")
    b.button(text="❌ Закрыть",        callback_data="cab:close")
    b.adjust(1)
    return b.as_markup()


def kb_analytics() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📈 Выручка (30 дн)", callback_data="chart:revenue")
    b.button(text="📊 Выручка за год", callback_data="chart:revenue_year")
    b.button(text="🎯 Выполнение планов", callback_data="chart:plans")
    b.button(text="◀️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def menu_employee() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Сдать отчет")],
            [KeyboardButton(text="👤 Личный кабинет")],
        ],
        resize_keyboard=True
    )


def menu_admin() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Сдать отчет")],
            [KeyboardButton(text="👤 Личный кабинет")],
            [KeyboardButton(text="⚙️ Админ-панель")],
        ],
        resize_keyboard=True
    )


def kb_cancel() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="report:cancel")
    return b.as_markup()


def kb_cancel_skip() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data="report:back")
    b.button(text="⏩ Пропустить", callback_data="report:skip")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(2, 1)
    return b.as_markup()


def kb_use_today(today_str: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"📅 Сегодня ({today_str})", callback_data="report:use_today")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить", callback_data="report:confirm")
    b.button(text="✏️ Редактировать", callback_data="report:edit")
    b.button(text="⬅️ Назад", callback_data="report:back")
    b.button(text="🔄 Заново", callback_data="report:restart")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(1, 1, 2, 1)
    return b.as_markup()


def kb_edit_fields() -> InlineKeyboardMarkup:
    fields = [
        ("Дата", "date"), ("Проект", "project"), ("Сотрудник", "employee_name"),
        ("Смены", "shift_count"), ("Выручка", "revenue"), ("Наличные", "cash"),
        ("Безнал", "acquiring"), ("Расход", "expense"), ("Касса", "cash_balance"),
        ("Посетители", "visitors"), ("ДР", "birthdays"), ("Комментарий", "comment")
    ]
    b = InlineKeyboardBuilder()
    for text, field in fields:
        b.button(text=text, callback_data=f"edit:{field}")
    b.button(text="⬅️ Назад к превью", callback_data="report:preview")
    b.adjust(3)
    return b.as_markup()


def kb_admin_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Отчёты",               callback_data="adm:reports")
    b.button(text="👥 Сотрудники",           callback_data="adm:employees")
    b.button(text="🎯 Планы продаж",         callback_data="adm:plans")
    b.button(text="📈 Статистика планов",    callback_data="adm:stats")
    b.button(text="💼 ЗП менеджера",         callback_data="adm:manager_salary")
    b.button(text="📂 Управл. расходы",       callback_data="adm:mgmt_expenses")
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
    b.button(text="❌ Закрыть", callback_data="adm:back")
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
    b.button(text="◀️ Назад", callback_data="adm:mgmt_expenses")
    b.adjust(3, 3, 1)
    return b.as_markup()


def kb_monthly_report_cities() -> InlineKeyboardMarkup:
    """City picker for monthly report."""
    b = InlineKeyboardBuilder()
    b.button(text="🏙 Гомель", callback_data="period:monthly_city:gomel")
    b.button(text="🌆 Минск",  callback_data="period:monthly_city:minsk")
    b.button(text="🌍 Все города", callback_data="period:monthly_city:all")
    b.button(text="◀️ Назад",  callback_data="adm:back")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_report_period() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Месячный отчёт", callback_data="period:monthly_calendar")
    b.button(text="📊 Аналитика (графики)", callback_data="adm:analytics")
    b.button(text="◀️ Назад",         callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_pending_user(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Одобрить", callback_data=f"pending:ok:{tg_id}")
    b.button(text="❌ Отклонить", callback_data=f"pending:no:{tg_id}")
    b.adjust(2)
    return b.as_markup()


def kb_employee_list(employees_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    # Sort cities: Gomel, Minsk, then None
    sorted_cities = sorted(employees_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
    
    for city in sorted_cities:
        emps = employees_by_city[city]
        if not emps: continue
        
        city_label = {"gomel": "🏙 ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "❓ БЕЗ ГОРОДА")
        b.button(text=f"─── {city_label} ───", callback_data="none")
        
        for emp in sorted(emps, key=lambda x: x.full_name):
            icon = "👑" if emp.role.value == "admin" else "👤"
            name = emp.full_name or emp.username or str(emp.telegram_id)
            b.button(text=f"{icon} {name}", callback_data=f"emp:view:{emp.telegram_id}")
            
    b.button(text="➕ Добавить по ID", callback_data="emp:add")
    b.button(text="📥 Заявки",               callback_data="adm:pending")
    b.button(text="◀️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_employee_actions(tg_id: int, role: str, city: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if role != "admin":
        b.button(text="👑 Сделать админом",   callback_data=f"emp:mkadmin:{tg_id}")
    else:
        b.button(text="👤 Снять права",       callback_data=f"emp:rmadmin:{tg_id}")
    city_label = {"gomel": "🏙 Гомель", "minsk": "🌆 Минск"}.get(city or "", "❓ не задан")
    b.button(text=f"🏙 Город: {city_label}",  callback_data=f"emp:setcity:{tg_id}")
    b.button(text="🗑 Удалить",               callback_data=f"emp:delete:{tg_id}")
    b.button(text="◀️ К списку",              callback_data="adm:employees")
    b.adjust(1)
    return b.as_markup()


def kb_salary_levels(levels: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lvl in sorted(levels, key=lambda x: x.level):
        mx = f"до {lvl.threshold_max:.0f}" if lvl.threshold_max else "∞"
        b.button(
            text=f"Ур.{lvl.level}: {lvl.threshold_min:.0f}–{mx}₽ | {lvl.percentage*100:.0f}%",
            callback_data=f"sal:edit:{lvl.id}"
        )
    b.button(text="◀️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_plans(plans_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
    
    for city in sorted_cities:
        plans = plans_by_city[city]
        if not plans: continue
        
        city_label = {"gomel": "🏙 ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌍 ОБЩИЕ ПЛАНЫ")
        b.button(text=f"─── {city_label} ───", callback_data="none")
        
        for p in plans:
            proj = p.project_name or "Все проекты"
            period = "день" if p.period == "day" else "мес"
            label = f"{'✅' if p.is_active else '⏸'} {proj}: {p.plan_amount:.0f}₽/{period}"
            b.button(text=label, callback_data=f"plan:toggle:{p.id}")
            b.button(text="🗑", callback_data=f"plan:delete:{p.id}")
    
    b.button(text="➕ Добавить план", callback_data="plan:add")
    b.button(text="◀️ Назад",        callback_data="adm:back")
    
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


def kb_mgmt_categories() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🧺 Расходник",  callback_data="mgmt:cat:расходник")
    b.button(text="🏠 Аренда",      callback_data="mgmt:cat:аренда")
    b.button(text="⚙️ Техника",     callback_data="mgmt:cat:техника")
    b.button(text="🏦 УСН 6%",      callback_data="mgmt:cat:усн_6")
    b.button(text="⚖️ Налоги ЗП 35.6%", callback_data="mgmt:cat:налоги_зп")
    b.button(text="➕ Другое",      callback_data="mgmt:cat:другое")
    b.button(text="❌ Отмена",      callback_data="adm:back")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def kb_back(cb: str = "adm:back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data=cb)
    return b.as_markup()

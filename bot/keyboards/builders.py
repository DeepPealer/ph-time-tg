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


def kb_city(cities: list) -> InlineKeyboardMarkup:
    """City selector during report submission."""
    b = InlineKeyboardBuilder()
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"report:city:{city.slug}")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(2, 1)
    return b.as_markup()


def kb_city_for_employee(tg_id: int, cities: list) -> InlineKeyboardMarkup:
    """Admin panel: set city for employee."""
    b = InlineKeyboardBuilder()
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"emp:city:{city.slug}:{tg_id}")
    b.button(text="❓ Спрашивать",    callback_data=f"emp:city:none:{tg_id}")
    b.button(text="⬅️ Назад",         callback_data=f"emp:view:{tg_id}")
    b.adjust(2, 1, 1)
    return b.as_markup()

def kb_city_selector(cities: list) -> InlineKeyboardMarkup:
    """General city selector for Cabinet."""
    b = InlineKeyboardBuilder()
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"city:{city.slug}")
    b.button(text="❌ Отмена", callback_data="cab:close")
    b.adjust(2, 1)
    return b.as_markup()



def kb_cabinet_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Моя статистика", callback_data="cab:stats")
    b.button(text="📜 История выплат", callback_data="cab:history")
    b.button(text="❌ Закрыть",        callback_data="cab:close")
    b.adjust(1)
    return b.as_markup()


def kb_analytics_cities(cities: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌍 Все города", callback_data="chart_city:all")
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"chart_city:{city.slug}")
    b.button(text="⬅️ Назад",  callback_data="adm:back")
    b.adjust(1, 2, 1)
    return b.as_markup()


def kb_analytics(city: str, project_name: str = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    suffix = f":{project_name}" if project_name else ""
    b.button(text="📈 Выручка (30 дн)",   callback_data=f"chart:revenue:{city}{suffix}")
    b.button(text="📅 Выполнение плана", callback_data=f"chart:plan:{city}{suffix}")
    b.button(text="📊 Годовая выручка",   callback_data=f"chart:revenue_year:{city}{suffix}")
    b.button(text="⬅️ Назад",           callback_data=f"chart_city:{city}")
    b.adjust(1)
    return b.as_markup()


def menu_employee() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Сдать отчет")],
            [KeyboardButton(text="📖 Инструкция")],
        ],
        resize_keyboard=True
    )


def menu_manager() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Сдать отчет")],
            [KeyboardButton(text="📋 Проверка отчётов от менеджера")],
            [KeyboardButton(text="⚙️ Панель управляющего")],
            [KeyboardButton(text="📖 Инструкция")],
        ],
        resize_keyboard=True
    )


def menu_admin() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Сдать отчет")],
            [KeyboardButton(text="📋 Проверка отчётов от менеджера")],
            [KeyboardButton(text="⚙️ Админ-панель")],
            [KeyboardButton(text="📖 Инструкция")],
        ],
        resize_keyboard=True
    )


def kb_cancel() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="report:cancel")
    return b.as_markup()


def kb_shift_type() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="☀️ Полная смена", callback_data="report:shift:full")
    # b.button(text="🌤️ Половина смены", callback_data="report:shift:half")
    b.button(text="⬅️ Назад", callback_data="report:back")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(1, 2)
    return b.as_markup()


def kb_cancel_skip(cancel_cb: str = "report:cancel") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад",      callback_data="report:back")
    b.button(text="⏩ Пропустить",  callback_data="report:skip")
    b.button(text="❌ Отмена",      callback_data=cancel_cb)
    b.adjust(2, 1)
    return b.as_markup()


def kb_use_today(today_str: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"📅 Сегодня ({today_str})", callback_data="report:use_today")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_confirm(is_editing: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Отправить" if not is_editing else "✅ Сохранить", callback_data="report:confirm")
    if is_editing:
        b.button(text="📝 Редактировать далее", callback_data="report:edit")
        b.button(text="❌ Отмена (к отчёту)", callback_data="report:cancel")
    else:
        b.button(text="📝 Редактировать", callback_data="report:edit")
        b.button(text="⬅️ Назад", callback_data="report:back")
        b.button(text="🔄 Заново", callback_data="report:restart")
        b.button(text="❌ Отмена", callback_data="report:cancel")
    
    if is_editing:
        b.adjust(1)
    else:
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
    b.button(text="🏙️ Города",               callback_data="adm:cities")
    b.button(text="🏢 Проекты",             callback_data="adm:projects")
    b.button(text="🎯 Планы продаж",         callback_data="adm:plans")
    b.button(text="📈 Статистика планов",    callback_data="adm:stats")
    b.button(text="📊 Аналитика",           callback_data="adm:analytics")
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
    b.button(text="⬅️ Назад", callback_data="adm:mgmt_expenses")
    b.adjust(3, 3, 1)
    return b.as_markup()


def kb_monthly_report_cities(cities: list) -> InlineKeyboardMarkup:
    """City picker for monthly report."""
    b = InlineKeyboardBuilder()
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"period:monthly_city:{city.slug}")
    b.button(text="🌐 Все города", callback_data="period:monthly_city:all")
    b.button(text="⬅️ Назад",  callback_data="adm:back")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_report_period() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Месячный отчёт", callback_data="period:monthly_calendar")
    b.button(text="📊 Аналитика (графики)", callback_data="adm:analytics")
    b.button(text="⬅️ Назад",         callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_pending_user(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сотрудник", callback_data=f"pending:emp:{tg_id}")
    b.button(text="💼 Управляющий", callback_data=f"pending:mgr:{tg_id}")
    b.button(text="❌ Отклонить", callback_data=f"pending:no:{tg_id}")
    b.adjust(2, 1)
    return b.as_markup()


def kb_report_review(report_id: int, is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Проверено", callback_data=f"review:ok:{report_id}")
    b.button(text="❌ Отклонить", callback_data=f"review:reject_start:{report_id}")
    if is_admin:
        b.button(text="📝 Редактировать", callback_data=f"review:edit:{report_id}")
    b.button(text="⬅️ Назад", callback_data="review:list")
    b.adjust(2)
    return b.as_markup()


def kb_employee_cities(cities: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for city in cities:
        b.button(text=f"{city.emoji} {city.name}", callback_data=f"adm:employees:city:{city.slug}")
    b.button(text="❓ Без города", callback_data="adm:employees:city:none")
    b.button(text="➕ Добавить по ID", callback_data="emp:add")
    b.button(text="📥 Заявки", callback_data="adm:pending")
    b.button(text="⬅️ Назад",  callback_data="adm:back")
    b.adjust(2, 1, 2, 1)
    return b.as_markup()


def kb_employee_list(employees: list, city_label: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    b.button(text=f"─── {city_label} ───", callback_data="none")
    
    for emp in sorted(employees, key=lambda x: x.pretty_name):
        if emp.role.value == "admin":
            icon = "👑"
        elif emp.role.value == "manager":
            icon = "💼"
        else:
            icon = "👤"
        name = emp.pretty_name
        b.button(text=f"{icon} {name}", callback_data=f"emp:view:{emp.telegram_id}")
            
    b.button(text="⬅️ Назад к городам", callback_data="adm:employees")
    b.adjust(1)
    return b.as_markup()


def kb_employee_actions(tg_id: int, role: str, city: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if role == "employee":
        b.button(text="👑 Сделать админом",   callback_data=f"emp:mkadmin:{tg_id}")
        b.button(text="💼 Назначить управляющим", callback_data=f"emp:mkmgr:{tg_id}")
    elif role == "manager":
        b.button(text="👑 Сделать админом",   callback_data=f"emp:mkadmin:{tg_id}")
        b.button(text="👤 Сделать сотрудником", callback_data=f"emp:mkemp:{tg_id}")
    else:
        b.button(text="👤 Снять права",       callback_data=f"emp:rmadmin:{tg_id}")
    city_label = {"gomel": "🏙️ Гомель", "minsk": "🌆 Минск"}.get(city or "", "❓ не задан")
    b.button(text=f"🏙️ Город: {city_label}",  callback_data=f"emp:setcity:{tg_id}")
    b.button(text="📌 Привязать проект", callback_data=f"emp:setproj:{tg_id}")
    
    b.button(text="📋 Архив отчётов",         callback_data=f"emp:archive:{tg_id}")
    b.button(text="🗑️ Удалить",               callback_data=f"emp:delete:{tg_id}")
    b.button(text="📅 Поиск по дате", callback_data="adm:reports_by_date")
    b.button(text="◀️ Назад",           callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_salary_levels(levels: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lvl in sorted(levels, key=lambda x: x.level):
        mx = f"до {lvl.threshold_max:.0f}" if lvl.threshold_max else "∞"
        b.button(
            text=f"Ур.{lvl.level}: {lvl.threshold_min:.0f}–{mx}BYN | {lvl.percentage*100:.0f}%",
            callback_data=f"sal:edit:{lvl.id}"
        )
    b.button(text="⬅️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_plans(plans_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
    
    for city in sorted_cities:
        plans = plans_by_city[city]
        if not plans: continue
        
        city_label = {"gomel": "🏙️ ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌐 ОБЩИЕ ПЛАНЫ")
        b.button(text=f"─── {city_label} ───", callback_data="none")
        
        for p in plans:
            proj = p.project_name or "Все проекты"
            period = "день" if p.period == "day" else "мес"
            label = f"{'✅' if p.is_active else '⏸'} {proj}: {p.plan_amount:.0f}BYN/{period}"
            b.button(text=label, callback_data=f"plan:toggle:{p.id}")
            b.button(text="🗑️", callback_data=f"plan:delete:{p.id}")
    
    b.button(text="➕ Добавить план", callback_data="plan:add")
    b.button(text="⬅️ Назад",        callback_data="adm:back")
    
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
    b.button(text="🧹 Расходник",  callback_data="mgmt:cat:расходник")
    if is_admin:
        b.button(text="🏠 Аренда",      callback_data="mgmt:cat:аренда")
    b.button(text="⚙️ Техника",     callback_data="mgmt:cat:техника")
    if is_admin:
        b.button(text="🏦 УСН 6%",      callback_data="mgmt:cat:усн_6")
        b.button(text="⚖️ Налоги ЗП 35.6%", callback_data="mgmt:cat:налоги_зп")
    b.button(text="➕ Другое",      callback_data="mgmt:cat:другое")
    if is_admin:
        b.button(text="🔍 Список/Удалить", callback_data="mgmt:list_start")
    b.button(text="⬅️ Назад",      callback_data="adm:back")
    
    # Adjust: if admin, 2-2-2-1-1. If manager, 2-1-1
    if is_admin:
        b.adjust(2, 2, 2, 1, 1)
    else:
        b.adjust(2, 1, 1)
    return b.as_markup()

def kb_mgmt_list(expenses: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for e in expenses:
        proj_part = f" [{e.project_name}]" if e.project_name else ""
        text = f"{e.category.title()} | {e.amount:,.0f} р{proj_part}"
        b.button(text=text, callback_data="none")
        b.button(text="🗑️", callback_data=f"mgmt:del:{e.id}")
    b.button(text="⬅️ Назад", callback_data="mgmt:list_start")
    b.adjust(2)
    return b.as_markup()


def kb_mgmt_categories_mgr() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🧹 Расходник",  callback_data="mgr:mgmt:cat:расходник")
    b.button(text="⚙️ Техника",     callback_data="mgr:mgmt:cat:техника")
    b.button(text="➕ Другое",      callback_data="mgr:mgmt:cat:другое")
    b.button(text="⬅️ Назад",      callback_data="mgr:mgmt_start")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_mgmt_date(today_str: str, yesterday_str: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=f"📅 Сегодня ({today_str})", callback_data="mgr:mgmt:date:today")
    b.button(text=f"📅 Вчера ({yesterday_str})", callback_data="mgr:mgmt:date:yesterday")
    b.button(text="⬅️ Назад", callback_data="mgr:panel")
    b.adjust(1)
    return b.as_markup()


def kb_projects(projects_by_city: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    
    cities = sorted(projects_by_city.keys())
    for city in cities:
        projs = projects_by_city[city]
        if not projs: continue
        
        city_label = {"gomel": "🏙️ ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "❓ БЕЗ ГОРОДА")
        b.button(text=f"─── {city_label} ───", callback_data="none")
        
        for p in sorted(projs, key=lambda x: x.name):
            icon = "✅" if p.is_active else "⏸"
            b.button(text=f"{icon} {p.name}", callback_data=f"proj:view:{p.id}")
            
    b.button(text="➕ Создать проект", callback_data="proj:add")
    b.button(text="⬅️ Назад",           callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_project_actions(project_id: int, is_active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    toggle_text = "⏸ Приостановить" if is_active else "▶️ Активировать"
    b.button(text=toggle_text,      callback_data=f"proj:toggle:{project_id}")
    b.button(text="🗑️ Удалить",     callback_data=f"proj:delete:{project_id}")
    b.button(text="⬅️ К списку",     callback_data="adm:projects")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_plan(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌐 ОБЩИЙ ПЛАН (на весь город)", callback_data="proj:plan:0")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"proj:plan:{p.id}")
    b.button(text="⬅️ Назад", callback_data="adm:plans")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_user_binding(projects: list, tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔓 НЕТ ПРИВЯЗКИ", callback_data=f"emp:proj:0:{tg_id}")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"emp:proj:{p.id}:{tg_id}")
    b.button(text="⬅️ Назад", callback_data=f"emp:view:{tg_id}")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_report(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"report:proj:{p.id}")
    b.button(text="❌ Отмена", callback_data="report:cancel")
    b.adjust(1)
    return b.as_markup()


def kb_projects_for_search(projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔍 ВСЕ ПРОЕКТЫ", callback_data="report:search:0")
    for p in sorted(projects, key=lambda x: x.name):
        b.button(text=p.name, callback_data=f"report:search:{p.id}")
    b.button(text="⬅️ Назад",   callback_data="adm:reports_by_date")
    b.adjust(1)
    return b.as_markup()


def kb_report_list_mini(reports: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in reports:
        # Date and project name
        date_str = r.date.strftime("%d.%m")
        # Truncate project name if too long
        proj = (r.project_name[:15] + "..") if len(r.project_name) > 17 else r.project_name
        checked = "✅" if r.is_reviewed else "⏳"
        b.button(text=f"{checked} {date_str} | {proj} | {r.revenue}", callback_data=f"review:view:{r.id}")
    b.button(text="⬅️ Назад", callback_data="adm:reports")
    b.adjust(1)
    return b.as_markup()


def kb_employee_archive_nav(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ К профилю", callback_data=f"emp:view:{tg_id}")
    return b.as_markup()


def kb_back(cb: str = "adm:back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=cb)
    return b.as_markup()



def kb_report_search_nav() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Поиск по дате", callback_data="adm:reports_by_date")
    b.button(text="📅 Месячный отчёт (Excel)", callback_data="period:monthly_calendar")
    b.button(text="⬅️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()

def kb_analytics_options(city: str, projects: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    city_lbl = {"gomel": "весь Гомель", "minsk": "весь Минск", "all": "все города"}.get(city, "весь город")
    b.button(text=f"📊 {city_lbl.upper()}", callback_data=f"chart_options:{city}:none")
    
    if city != "all":
        for p in sorted(projects, key=lambda x: x.name):
            b.button(text=f"📍 {p.name}", callback_data=f"chart_options:{city}:{p.name}")
            
    b.button(text="⬅️ Назад", callback_data="adm:analytics")
    b.adjust(1)
    return b.as_markup()


def kb_admin_cities(cities: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for c in cities:
        status = "✅" if c.is_active else "⏸️"
        b.button(text=f"{c.emoji} {c.name} {status}", callback_data=f"city:view:{c.id}")
    b.button(text="➕ Добавить город", callback_data="city:add")
    b.button(text="⬅️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_city_actions(city_id: int, is_active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    status_label = "⏸️ Деактивировать" if is_active else "✅ Активировать"
    b.button(text="📝 Изменить название", callback_data=f"city:edit_name:{city_id}")
    b.button(text="🌉 Изменить эмодзи", callback_data=f"city:edit_emoji:{city_id}")
    b.button(text="🧵 Изменить топик ID", callback_data=f"city:edit_thread:{city_id}")
    b.button(text="📊 Тарифная сетка ЗП", callback_data=f"city:rates:{city_id}")
    b.button(text=status_label, callback_data=f"city:toggle:{city_id}")
    b.button(text="❌ Удалить город", callback_data=f"city:delete:{city_id}")
    b.button(text="⬅️ Назад", callback_data="adm:cities")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def kb_city_presets() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏙️ Пресет Гомеля (разные по дням)", callback_data="city:preset:gomel")
    b.button(text="🌆 Пресет Минска (общие тарифы)", callback_data="city:preset:minsk")
    b.button(text="⚪ Без тарифов (пустой)", callback_data="city:preset:empty")
    b.button(text="❌ Отмена", callback_data="adm:cities")
    b.adjust(1)
    return b.as_markup()


def kb_salary_rules(city_id: int, rules: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    day_labels = {
        "weekday": "Пн-Пт",
        "saturday": "Сб",
        "sunday": "Вс",
        "all_days": "Пн-Вс"
    }
    
    # Sort rules: day_type (all_days, weekday, saturday, sunday), shift_type (full, half), threshold_min
    day_order = {"all_days": 0, "weekday": 1, "saturday": 2, "sunday": 3}
    sorted_rules = sorted(
        rules,
        key=lambda r: (day_order.get(r.day_type, 9), r.shift_type, r.threshold_min)
    )
    
    for r in sorted_rules:
        if r.shift_type == "half":
            continue
        day_lbl = day_labels.get(r.day_type, r.day_type)
        shift_lbl = " (1/2)" if r.shift_type == "half" else ""
        max_val = f"{r.threshold_max:.0f}" if r.threshold_max else "~"
        text = f"{day_lbl}{shift_lbl}: {r.threshold_min:.0f}-{max_val}р ➔ {r.base_salary:.0f}+{r.percentage*100:.0f}%"
        b.button(text=text, callback_data=f"rate:edit:{r.id}")
        
    b.button(text="➕ Добавить диапазон", callback_data=f"rate:add:{city_id}")
    b.button(text="⬅️ К профилю города", callback_data=f"city:view:{city_id}")
    b.adjust(1)
    return b.as_markup()


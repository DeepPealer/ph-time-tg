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
    b.button(text="📊 Отчёты (Excel)", callback_data="adm:reports")
    b.button(text="👥 Сотрудники",     callback_data="adm:employees")
    b.button(text="📥 Заявки",         callback_data="adm:pending")
    b.button(text="💰 Шкала ЗП",       callback_data="adm:salary")
    b.button(text="🎯 Планы продаж",   callback_data="adm:plans")
    b.button(text="📈 Статистика планов", callback_data="adm:stats")
    b.adjust(1)
    return b.as_markup()


def kb_report_period() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📅 Текущий месяц",    callback_data="period:cur_month")
    b.button(text="📅 Прошлый месяц",   callback_data="period:prev_month")
    b.button(text="🎯 Планы продаж",    callback_data="adm:plans")
    b.button(text="📈 Статистика планов", callback_data="adm:stats")
    b.button(text="📊 Аналитика",        callback_data="adm:analytics")
    b.button(text="💸 Долги по ЗП",       callback_data="adm:debt")
    b.button(text="◀️ Назад",            callback_data="adm:back")
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def kb_pending_user(tg_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Одобрить", callback_data=f"pending:ok:{tg_id}")
    b.button(text="❌ Отклонить", callback_data=f"pending:no:{tg_id}")
    b.adjust(2)
    return b.as_markup()


def kb_employee_list(employees: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for emp in employees:
        icon = "👑" if emp.role.value == "admin" else "👤"
        name = emp.full_name or emp.username or str(emp.telegram_id)
        b.button(text=f"{icon} {name}", callback_data=f"emp:view:{emp.telegram_id}")
    b.button(text="➕ Добавить по ID", callback_data="emp:add")
    b.button(text="◀️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_employee_actions(tg_id: int, role: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if role != "admin":
        b.button(text="👑 Сделать админом",   callback_data=f"emp:mkadmin:{tg_id}")
    else:
        b.button(text="👤 Снять права",       callback_data=f"emp:rmadmin:{tg_id}")
    b.button(text="💰 Премия / Штраф",       callback_data=f"emp:adj:{tg_id}")
    b.button(text="🗑 Удалить",              callback_data=f"emp:delete:{tg_id}")
    b.button(text="◀️ К списку",             callback_data="adm:employees")
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


def kb_debt_list(unpaid_grouped: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for user_id, name, amount in unpaid_grouped:
        b.button(text=f"{name}: {amount:,.0f} ₽", callback_data=f"debt:view:{user_id}")
    b.button(text="◀️ Назад", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_debt_actions(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Выплатить всё", callback_data=f"debt:payall:{user_id}")
    b.button(text="◀️ К списку долгов", callback_data="adm:debt")
    b.adjust(1)
    return b.as_markup()


def kb_plans(plans: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in plans:
        proj = p.project_name or "Все проекты"
        period = "день" if p.period == "day" else "месяц"
        b.button(
            text=f"{'✅' if p.is_active else '⏸'} {proj}: {p.plan_amount:.0f}₽/{period}",
            callback_data=f"plan:toggle:{p.id}"
        )
        b.button(text="🗑", callback_data=f"plan:delete:{p.id}")
    
    sizes = [2] * len(plans) + [1, 1]
    b.button(text="➕ Добавить план", callback_data="plan:add")
    b.button(text="◀️ Назад",        callback_data="adm:back")
    b.adjust(*sizes)
    return b.as_markup()


def kb_back(cb: str = "adm:back") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data=cb)
    return b.as_markup()

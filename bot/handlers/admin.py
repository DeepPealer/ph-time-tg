from datetime import date, timedelta, datetime
from calendar import monthrange
import html

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, BufferedInputFile, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from bot.database.models import User, UserRole, SalarySetting, Plan, Report, ManagementExpense, Project
from bot.keyboards.builders import (
    kb_admin_main, kb_report_period, kb_employee_list, kb_employee_actions,
    kb_salary_levels, kb_plans, kb_back, kb_analytics, kb_analytics_cities,
    menu_admin, menu_manager, kb_city_for_employee, kb_month_select,
    kb_monthly_report_cities, kb_report_review, kb_employee_cities,
    kb_projects, kb_project_actions, kb_projects_for_plan, kb_report_search_nav
)
from bot.utils.excel import generate_excel_report, generate_monthly_calendar
from bot.utils.salary import calculate_manager_salary
from bot.utils.logging import log_action
from bot.utils.charts import (
    generate_revenue_chart, generate_plan_performance_chart,
    generate_yearly_revenue_chart
)

router = Router()


class AdminForm(StatesGroup):
    add_emp_id        = State()
    sal_edit_id       = State()
    sal_edit_values   = State()
    plan_city         = State()
    plan_project      = State()
    plan_amount       = State()
    plan_period       = State()
    mgmt_city         = State()
    mgmt_project      = State()
    mgmt_date         = State()
    mgmt_category     = State()
    mgmt_amount       = State()
    mgmt_comment      = State()
    reject_reason     = State()
    report_search_date = State()
    report_search_city = State()
    report_search_proj = State()
    proj_city         = State()
    proj_name         = State()
    mgmt_list_date    = State()

class ManagerMgmtForm(StatesGroup):
    date     = State()
    category = State()
    amount   = State()
    comment  = State()

_fmt = lambda x: f"{x:,.0f}" if x is not None else "0"
def _require_admin(db_user: User) -> bool:
    return db_user.role == UserRole.admin and db_user.is_active


def _require_admin_or_manager(db_user: User) -> bool:
    return db_user.role in (UserRole.admin, UserRole.manager) and db_user.is_active


def _kb_manager_main() -> InlineKeyboardMarkup:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="📋 Проверка отчётов", callback_data="review:list:0")
    b.button(text="📈 Моя ЗП",            callback_data="mgr:my_salary")
    b.button(text="📂 Управл. расходы",    callback_data="mgr:mgmt_start")
    b.adjust(1)
    return b.as_markup()


# ——— Entry ——————————————————————————————————————————————————————————————————

@router.message(F.text == "⚙️ Админ-панель")
async def show_admin_panel(message: Message, db_user: User, state: FSMContext):
    if not _require_admin(db_user):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=kb_admin_main())


@router.message(F.text == "📋 Проверка отчётов от менеджера")
async def admin_review_reports(message: Message, db_user: User, session: AsyncSession):
    if not _require_admin_or_manager(db_user): return
    # Reuse the manager's review list logic
    from bot.handlers.admin import review_list
    # We need a dummy callback-like object or just call the logic
    # Actually it's cleaner to just call a helper or the function with message
    await review_list(None, session, db_user, message=message)


# ——— Back ———————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "admin":
        await call.message.edit_text("⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
                             parse_mode="HTML", reply_markup=kb_admin_main())
    else:
        # Redirect manager to their panel
        await call.message.edit_text("⚙️ <b>Панель управляющего</b>\n\nВыберите раздел:",
                             parse_mode="HTML", reply_markup=_kb_manager_main())
    await call.answer()


# ——— Reports / Excel ————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:reports")
async def adm_reports(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return await call.answer("Нет доступа", show_alert=True)
    try:
        await call.message.edit_text("📊 <b>Управление отчётами</b>\n\nВыберите действие:",
                                     parse_mode="HTML", reply_markup=kb_report_search_nav())
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {html.escape(str(e))}")
    await call.answer()


@router.callback_query(F.data == "adm:reports_by_date")
async def adm_reports_by_date_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not _require_admin(db_user): return
    await state.set_state(AdminForm.report_search_date)
    await call.message.edit_text(
        "📅 <b>Поиск отчётов по дате</b>\n\nВведите дату в формате ДД.ММ.ГГГГ\n(например: 26.03.2026):",
        parse_mode="HTML", reply_markup=kb_back("adm:reports")
    )
    await call.answer()


@router.message(AdminForm.report_search_date)
async def adm_reports_by_date_input(message: Message, state: FSMContext, db_user: User):
    if not _require_admin(db_user): return
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(search_date=dt.isoformat())
        await state.set_state(AdminForm.report_search_city)
        from bot.keyboards.builders import kb_city
        await message.answer("🏙️ Выберите город для фильтрации:", reply_markup=kb_city())
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату как ДД.ММ.ГГГГ (например, 26.03.2026)")


@router.callback_query(AdminForm.report_search_city)
async def adm_reports_by_date_city(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    city_val = city if city != "none" else None
    await state.update_data(search_city=city_val)
    
    # Fetch projects for this city
    res = await session.execute(
        select(Project).where(Project.city == city_val, Project.is_active == True)
    )
    projects = res.scalars().all()
    
    await state.set_state(AdminForm.report_search_proj)
    # Reusing plan selection keyboard logic but with different callback
    from bot.keyboards.builders import kb_projects_for_plan
    # We'll make a more generic one or just use this and check data
    # Actually let's add a specific one for search to builders.py
    from bot.keyboards.builders import kb_projects_for_search
    await call.message.edit_text(
        "📌 <b>Выберите проект</b> для поиска:",
        parse_mode="HTML", reply_markup=kb_projects_for_search(projects)
    )
    await call.answer()


@router.callback_query(AdminForm.report_search_proj)
async def adm_reports_by_date_finish(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    if not _require_admin(db_user): return
    data = call.data.split(":")
    proj_id_raw = data[2]
    
    s_data = await state.get_data()
    s_date = datetime.fromisoformat(s_data["search_date"]).date()
    s_city = s_data["search_city"]
    
    query = select(Report).where(Report.date == s_date)
    if s_city:
        query = query.where(Report.city == s_city)
    
    if proj_id_raw != "0":
        proj_id = int(proj_id_raw)
        query = query.where(Report.project_id == proj_id)
    
    # Manager restriction: only their project if bound
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and db_user.project_id:
        query = query.where(Report.project_id == db_user.project_id)
        
    res = await session.execute(query.order_by(Report.id.desc()))
    reports = res.scalars().all()
    await state.clear()
    
    if not reports:
        await call.message.edit_text("🤷‍♂️ Отчётов не найдено.", reply_markup=kb_back("adm:reports"))
        return
        
    # Show list of reports (mini-cards)
    text = f"📅 <b>Отчёты за {s_date.strftime('%d.%m.%Y')}</b>\nНайдено: {len(reports)}\n\n"
    from bot.keyboards.builders import kb_report_list_mini
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_list_mini(reports))
    await call.answer()





# ——— Employees ——————————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:employees")
async def adm_employees(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    
    res_count = await session.execute(
        select(func.count()).where(User.role != UserRole.pending)
    )
    total_emps = res_count.scalar() or 0

    await call.message.edit_text(
        f"👥 <b>Сотрудники</b> ({total_emps} чел.)\n\nВыберите город:",
        parse_mode="HTML", reply_markup=kb_employee_cities()
    )
    await call.answer()


@router.callback_query(F.data.startswith("adm:employees:city:"))
async def adm_employees_city(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[3]
    
    query = select(User).where(User.role != UserRole.pending)
    if city == "none":
        query = query.where(User.city == None)
        city_label = "❓ БЕЗ ГОРОДА"
    else:
        query = query.where(User.city == city)
        city_label = "🏙️ ГОМЕЛЬ" if city == "gomel" else "🌆 МИНСК"
        
    res = await session.execute(query.order_by(User.display_name, User.full_name))
    employees = res.scalars().all()
    
    await call.message.edit_text(
        f"👥 <b>Сотрудники — {city_label}</b> ({len(employees)} чел.)\n\n",
        parse_mode="HTML", reply_markup=kb_employee_list(employees, city_label)
    )
    await call.answer()


@router.callback_query(F.data.startswith("emp:view:"))
async def emp_view(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if not emp:
        await call.answer("Не найден", show_alert=True); return
    role_str = {"admin": "Администратор", "manager": "Управляющий", "employee": "Сотрудник"}.get(emp.role.value, emp.role.value)
    city_str = {"gomel": "🏙️ Гомель", "minsk": "🌆 Минск"}.get(emp.city or "", "❓ не задан")
    proj_str = "🔓 Нет привязки"
    if emp.project_id:
        pres = await session.execute(select(Project).where(Project.id == emp.project_id))
        p = pres.scalar_one_or_none()
        if p: proj_str = f"📌 {p.name}"

    text = (
        f"👤 <b>{emp.pretty_name}</b>\n"
        f"📎 @{emp.username or '—'}\n"
        f"🆔 {emp.telegram_id}\n"
        f"🎭 Роль: {role_str}\n"
        f"🏙️ Город: {city_str}\n"
        f"📂 Проект: {proj_str}\n"
        f"✅ Активен: {'Да' if emp.is_active else 'Нет'}"
    )
    await call.message.edit_text(text, parse_mode="HTML",
                                 reply_markup=kb_employee_actions(emp.telegram_id, emp.role.value, emp.city))
    await call.answer()


@router.callback_query(F.data.startswith("emp:archive:"))
async def emp_archive(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(
        select(Report).join(User, Report.user_id == User.id).where(User.telegram_id == tg_id).order_by(Report.date.desc()).limit(20)
    )
    reports = res.scalars().all()
    
    if not reports:
        await call.answer("🤷‍♂️ Нет отчётов в архиве", show_alert=True)
        return
        
    text = f"📂 <b>Архив последних отчётов</b>\n(последние 20 шт.)\n\n"
    from bot.keyboards.builders import kb_report_list_mini
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_list_mini(reports))
    await call.answer()



@router.callback_query(F.data == "emp:add")
async def emp_add_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.add_emp_id)
    await call.message.edit_text(
        "➕ Введите <b>Telegram ID</b> нового сотрудника\n"
        "(узнать можно через @userinfobot):",
        parse_mode="HTML", reply_markup=kb_back("adm:employees")
    )
    await call.answer()


@router.message(AdminForm.add_emp_id)
async def emp_add_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой Telegram ID:"); return

    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = res.scalar_one_or_none()

    if user:
        user.role = UserRole.employee
        user.is_active = True
        await session.commit()
        await message.answer(f"✅ {user.pretty_name} теперь сотрудник!", reply_markup=menu_admin())
    else:
        # Pre-create record; will be enriched on first /start
        new = User(telegram_id=tg_id, full_name=f"User_{tg_id}",
                   role=UserRole.employee, is_active=True)
        session.add(new)
        await session.commit()
        await message.answer(
            f"✅ ID {tg_id} добавлен как сотрудник.\n"
            "Попросите его написать /start боту.", reply_markup=menu_admin()
        )
    await state.clear()


@router.callback_query(F.data.startswith("emp:mkadmin:"))
async def emp_mkadmin(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.admin; emp.is_active = True
        await session.commit()
        await call.message.edit_text(f"✅ {emp.pretty_name} назначен администратором.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Готово")


@router.callback_query(F.data.startswith("emp:mkmgr:"))
async def emp_mkmgr(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.manager; emp.is_active = True
        await session.commit()
        await call.message.edit_text(f"✅ {emp.pretty_name} назначен управляющим.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Готово")


@router.callback_query(F.data.startswith("emp:mkemp:"))
async def emp_mkemp(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.employee; emp.is_active = True
        await session.commit()
        await call.message.edit_text(f"✅ {emp.pretty_name} снят с должности управляющего (теперь сотрудник).",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Готово")


@router.callback_query(F.data.startswith("emp:rmadmin:"))
async def emp_rmadmin(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.employee
        await session.commit()
        await call.message.edit_text(f"✅ {emp.pretty_name} теперь сотрудник.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Готово")


@router.callback_query(F.data.startswith("emp:delete:"))
async def emp_delete(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.is_active = False
        emp.role = UserRole.pending
        await session.commit()
        await call.message.edit_text(f"🗑️ {emp.pretty_name} лишён доступа.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Удалён")


# ——— Pending users ——————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:pending")
async def adm_pending(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(
        select(User).where(User.role == UserRole.pending).order_by(User.created_at.desc())
    )
    pending = res.scalars().all()
    if not pending:
        await call.message.edit_text("📥 Заявок нет.", reply_markup=kb_back())
        await call.answer(); return
    text = f"📥 <b>Заявки ({len(pending)})</b>\n\n"
    for u in pending:
        text += f"• {u.pretty_name} (@{u.username or '—'}) — <code>{u.telegram_id}</code>\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_back())
    await call.answer()


@router.callback_query(F.data.startswith("pending:emp:"))
async def pending_approve_employee(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        u.role = UserRole.employee; u.is_active = True
        await session.commit()
        name = u.pretty_name
        await call.message.edit_reply_markup()
        await call.message.answer(f"✅ {name} одобрен как Сотрудник.")
        try:
            await bot.send_message(tg_id, "🎉 Ваш доступ одобрен! Вы теперь Сотрудник. Напишите /start")
        except Exception: pass
    await call.answer("Одобрено")


@router.callback_query(F.data.startswith("pending:mgr:"))
async def pending_approve_manager(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        u.role = UserRole.manager; u.is_active = True
        await session.commit()
        name = u.pretty_name
        await call.message.edit_reply_markup()
        await call.message.answer(f"✅ {name} одобрен как Управляющий.")
        try:
            await bot.send_message(tg_id, "🎉 Ваш доступ одобрен! Вы теперь Управляющий. Напишите /start")
        except Exception: pass
    await call.answer("Одобрено")


@router.callback_query(F.data.startswith("pending:no:"))
async def pending_deny(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        await session.delete(u); await session.commit()
        await call.message.edit_reply_markup()
        await call.message.answer(f"🗑️ Заявка от {u.pretty_name} отклонена.")
        try:
            await bot.send_message(tg_id, "❌ Ваш запрос на доступ отклонён.")
        except Exception: pass
    await call.answer("Отклонено")


# ——— Employee City ——————————————————————————————————————————————————————————

@router.callback_query(F.data.startswith("emp:setcity:"))
async def emp_setcity_prompt(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    await call.message.edit_text(
        "🏙️ <b>Выберите город для сотрудника:</b>\n"
        "«Спрашивать» — бот будет спрашивать при каждом отчёте.",
        parse_mode="HTML",
        reply_markup=kb_city_for_employee(tg_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("emp:city:"))
async def emp_city_set(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")  # emp:city:<city>:<tg_id>
    city_raw, tg_id = parts[2], int(parts[3])
    city = None if city_raw == "none" else city_raw
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.city = city
        await session.commit()
        city_label = {"gomel": "Гомель", "minsk": "Минск"}.get(city or "", "спрашивать")
        await call.message.edit_text(
            f"✅ Город сотрудника <b>{emp.pretty_name}</b> установлен: <b>{city_label}</b>",
            parse_mode="HTML", reply_markup=kb_back(f"emp:view:{tg_id}")
        )
    await call.answer("Сохранено")


@router.callback_query(F.data.startswith("emp:bindproj:"))
async def emp_bindproj_prompt(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    
    # Fetch all active projects
    res = await session.execute(select(Project).where(Project.is_active == True))
    projects = res.scalars().all()
    
    from bot.keyboards.builders import kb_projects_for_user_binding
    await call.message.edit_text(
        "📌 <b>Привязка управляющего к проекту:</b>\n\n"
        "Если проект привязан, управляющий будет видеть ТОЛЬКО этот проект "
        "при сдаче отчётов и вводе упр. расходов.",
        parse_mode="HTML",
        reply_markup=kb_projects_for_user_binding(projects, tg_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("emp:saveproj:"))
async def emp_saveproj(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")  # emp:saveproj:<proj_id>:<tg_id>
    proj_id = int(parts[2])
    tg_id = int(parts[3])
    
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.project_id = proj_id if proj_id != 0 else None
        await session.commit()
        proj_name = "Нет привязки"
        if emp.project_id:
            pres = await session.execute(select(Project).where(Project.id == emp.project_id))
            p = pres.scalar_one_or_none()
            proj_name = p.name if p else "???"
            
        await call.message.edit_text(
            f"✅ Управляющий <b>{emp.pretty_name}</b> привязан к проекту: <b>{proj_name}</b>",
            parse_mode="HTML", reply_markup=kb_back(f"emp:view:{tg_id}")
        )
    await call.answer("Привязано")


# ——— Salary settings (legacy placeholder) ———————————————————————————————————

@router.callback_query(F.data == "adm:salary")
async def adm_salary(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text(
        "ℹ️ <b>Шкала ЗП</b>\n\n"
        "Правила расчёта зарплаты фотографов зафиксированы в системе:\n\n"
        "<b>Гомель Пн–Пт:</b> до 200 р → 25+10%; 200–300 → 20%; >300 → 22%\n"
        "<b>Гомель Сб:</b> до 400 р → 25+10%; 400–800 → 20%; >800 → 22%\n"
        "<b>Гомель Вс:</b> до 350 р → 25+10%; 350–600 → 20%; >600 → 22%\n"
        "<b>Минск (все дни):</b> до 450 р → 45+10%; 450–1000 → 20%; >1000 → 22%\n\n"
        "Процентная часть делится на число сотрудников в смене.",
        parse_mode="HTML", reply_markup=kb_back()
    )
    await call.answer()


# ——— Manager Salary —————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:manager_salary")
async def adm_manager_salary(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    try:
        today = date.today()
        month_start = today.replace(day=1)

        # Get all active monthly plans
        res = await session.execute(
            select(Plan).where(Plan.is_active == True, Plan.period == "month")
        )
        plans = res.scalars().all()

        # Get revenue grouped by city and project
        rev_res = await session.execute(
            select(Report.city, Report.project_name, func.sum(Report.revenue))
            .where(Report.date >= month_start, Report.date <= today)
            .group_by(Report.city, Report.project_name)
        )
        
        # city_rev[city][project] = sum
        from collections import defaultdict
        city_rev = defaultdict(lambda: defaultdict(float))
        total_rev_by_city = defaultdict(float)
        
        for r_city, proj, rev in rev_res.all():
            city_rev[r_city][proj] = float(rev or 0)
            total_rev_by_city[r_city] += float(rev or 0)

        lines = [f"💼 <b>ЗП Менеджера — {today.strftime('%B %Y')}</b>\n"]

        if not plans:
            lines.append("⚠️ Нет активных месячных планов.\nДобавьте план в разделе 🎯 Планы продаж.")
        else:
            # Group plans by city for display
            plans_by_city = defaultdict(list)
            for p in plans:
                plans_by_city[p.city].append(p)
                
            sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
            
            for city in sorted_cities:
                city_label = {"gomel": "🏙️ ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌐 ОБЩИЕ")
                lines.append(f"<b>{city_label}</b>")
                
                for plan in plans_by_city[city]:
                    proj_label = plan.project_name or "Все проекты"
                    if plan.project_name:
                        actual = city_rev[city].get(plan.project_name, 0.0)
                    else:
                        actual = total_rev_by_city[city]
                        
                    salary, desc = calculate_manager_salary(float(actual), plan.plan_amount)
                    pct = (actual * 100 / plan.plan_amount) if plan.plan_amount else 0
                    bar = _progress_bar(pct)
                    lines.append(
                        f"📊 {proj_label}\n"
                        f"   Оборот: <b>{actual:,.0f} р</b> / план <b>{plan.plan_amount:,.0f} р</b>\n"
                        f"   {bar} <b>{pct:.1f}%</b>\n"
                        f"   {desc}\n"
                        f"   💸 ЗП: <b>{salary:,.2f} р</b>\n"
                    )
                lines.append("")

        await call.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML", reply_markup=kb_back()
        )
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {html.escape(str(e))}")
    await call.answer()


@router.callback_query(F.data.startswith("sal:edit:"))
async def sal_edit_prompt(call: CallbackQuery, state: FSMContext):
    lvl_id = int(call.data.split(":")[2])
    await state.update_data(sal_edit_id=lvl_id)
    await state.set_state(AdminForm.sal_edit_values)
    await call.message.edit_text(
        "📝 Введите новые параметры уровня одной строкой:\n\n"
        "<code>мин_порог макс_порог оклад процент</code>\n\n"
        "Пример: <code>0 15000 2500 10</code>\n"
        "Для безлимитного верхнего порога введите 0:\n"
        "<code>30000 0 0 22</code>",
        parse_mode="HTML", reply_markup=kb_back("adm:salary")
    )
    await call.answer()


@router.message(AdminForm.sal_edit_values)
async def sal_edit_save(message: Message, state: FSMContext, session: AsyncSession):
    parts = message.text.strip().split()
    try:
        tmin, tmax_raw, base, pct = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
        tmax = None if tmax_raw == 0 else tmax_raw
    except (ValueError, IndexError):
        await message.answer("❌ Формат: <code>мин макс оклад процент</code>", parse_mode="HTML")
        return
    d = await state.get_data()
    res = await session.execute(select(SalarySetting).where(SalarySetting.id == d["sal_edit_id"]))
    lvl = res.scalar_one_or_none()
    if lvl:
        lvl.threshold_min = tmin; lvl.threshold_max = tmax
        lvl.base_salary = base; lvl.percentage = pct / 100
        await session.commit()
        await message.answer("✅ Уровень ЗП обновлён!", reply_markup=menu_admin())
    await state.clear()


# ——— Plans ——————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:plans")
async def adm_plans(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    try:
        res = await session.execute(select(Plan).order_by(Plan.created_at.desc()))
        plans = res.scalars().all()
        
        from collections import defaultdict
        by_city = defaultdict(list)
        for p in plans:
            by_city[p.city].append(p)
            
        await call.message.edit_text(
            "🎯 <b>Планы продаж</b>\n\nЗдесь можно настроить цели по выручке для проектов или общие.",
            parse_mode="HTML", reply_markup=kb_plans(by_city)
        )
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {html.escape(str(e))}")
    await call.answer()


@router.callback_query(F.data.startswith("plan:toggle:"))
async def plan_toggle(call: CallbackQuery, session: AsyncSession):
    plan_id = int(call.data.split(":")[2])
    res = await session.execute(select(Plan).where(Plan.id == plan_id))
    plan = res.scalar_one_or_none()
    if plan:
        plan.is_active = not plan.is_active
        await session.commit()
    res2 = await session.execute(select(Plan).order_by(Plan.created_at.desc()))
    plans = res2.scalars().all()
    from collections import defaultdict
    by_city = defaultdict(list)
    for p in plans:
        by_city[p.city].append(p)
    await call.message.edit_reply_markup(reply_markup=kb_plans(by_city))
    await call.answer("Изменено")


@router.callback_query(F.data.startswith("plan:delete:"))
async def plan_delete(call: CallbackQuery, session: AsyncSession):
    plan_id = int(call.data.split(":")[2])
    res = await session.execute(select(Plan).where(Plan.id == plan_id))
    plan = res.scalar_one_or_none()
    if plan:
        await session.delete(plan)
        await session.commit()
    
    res2 = await session.execute(select(Plan).order_by(Plan.created_at.desc()))
    plans = res2.scalars().all()
    from collections import defaultdict
    by_city = defaultdict(list)
    for p in plans:
        by_city[p.city].append(p)
    await call.message.edit_reply_markup(reply_markup=kb_plans(by_city))
    await call.answer("План удален")


@router.callback_query(F.data == "plan:add")
async def plan_add_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.plan_city)
    from bot.keyboards.builders import kb_city
    # We use building keyboard for reports city selection as it is same
    await call.message.edit_text("🏙️ Выберите город для плана:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.plan_city)
async def plan_add_city(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        return await adm_plans(call, session, db_user)
    
    city_val = city if city != "none" else None
    await state.update_data(plan_city=city_val)
    
    # Fetch projects for this city
    res = await session.execute(
        select(Project).where(Project.city == city_val, Project.is_active == True)
    )
    projects = res.scalars().all()
    
    await state.set_state(AdminForm.plan_project)
    await call.message.edit_text(
        "📌 <b>Выберите проект</b> для плана:",
        parse_mode="HTML", reply_markup=kb_projects_for_plan(projects)
    )
    await call.answer()


@router.callback_query(AdminForm.plan_project)
async def plan_add_project_callback(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = call.data.split(":")
    proj_id_raw = data[2]
    
    if proj_id_raw == "0":
        await state.update_data(plan_project_id=None, plan_project_name=None)
    else:
        proj_id = int(proj_id_raw)
        res = await session.execute(select(Project).where(Project.id == proj_id))
        p = res.scalar_one_or_none()
        if p:
            await state.update_data(plan_project_id=p.id, plan_project_name=p.name)
            
    await state.set_state(AdminForm.plan_amount)
    await call.message.edit_text("💰 Введите <b>сумму плана</b> (BYN):", parse_mode="HTML")
    await call.answer()


@router.message(AdminForm.plan_amount)
async def plan_add_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число:"); return
    await state.update_data(plan_amount=amount)
    await state.set_state(AdminForm.plan_period)
    await message.answer("Период плана: введите <b>день</b> или <b>месяц</b>:", parse_mode="HTML")


@router.message(AdminForm.plan_period)
async def plan_add_period(message: Message, state: FSMContext, session: AsyncSession):
    txt = message.text.strip().lower()
    period = "day" if "день" in txt or txt == "day" else "month"
    d = await state.get_data()
    session.add(Plan(
        city=d["plan_city"],
        project_id=d.get("plan_project_id"),
        project_name=d.get("plan_project_name"),
        plan_amount=d["plan_amount"],
        period=period
    ))
    await session.commit()
    await state.clear()
    proj_str = d.get("plan_project_name") or "Все проекты"
    period_str = "день" if period == "day" else "месяц"
    await message.answer(
        f"✅ План добавлен: {proj_str} — {d['plan_amount']:.0f}BYN / {period_str}",
        reply_markup=menu_admin()
    )


# ——— Plan stats ——————————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    try:
        today = date.today()
        month_start = today.replace(day=1)

        res = await session.execute(
            select(Plan).where(Plan.is_active == True)
        )
        plans = res.scalars().all()

        if not plans:
            await call.message.edit_text(
                "📈 <b>Статистика планов</b>\n\nАктивных планов нет.\n"
                "Добавьте их в разделе 🎯 Планы продаж.",
                parse_mode="HTML", reply_markup=kb_back()
            )
            await call.answer()
            return

        from collections import defaultdict
        plans_by_city = defaultdict(list)
        for p in plans:
            plans_by_city[p.city].append(p)

        lines = ["📈 <b>Статистика выполнения планов</b>\n"]

        sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))

        for city in sorted_cities:
            city_label = {"gomel": "🏙️ ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌐 ОБЩИЕ")
            lines.append(f"<b>{city_label}</b>")
            
            for plan in plans_by_city[city]:
                proj_label = plan.project_name or "Все проекты"
                period_label = "день" if plan.period == "day" else "месяц"
                period_start = today if plan.period == "day" else month_start

                # Project filter: specific project or all in city
                if plan.project_name:
                    proj_filter = Report.project_name == plan.project_name
                else:
                    proj_filter = True
                
                # City filter
                report_city_filter = Report.city == plan.city

                rev_res = await session.execute(
                    select(func.coalesce(func.sum(Report.revenue), 0.0))
                    .where(
                        Report.date >= period_start,
                        Report.date <= today,
                        report_city_filter if plan.city else Report.city.is_(None),
                        proj_filter,
                    )
                )
                actual = float(rev_res.scalar() or 0.0)
                pct = (actual * 100 / plan.plan_amount) if plan.plan_amount else 0
                bar = _progress_bar(pct)
                lines.append(
                    f"🎯 {proj_label} ({period_label}):\n"
                    f"   {bar} <b>{pct:.1f}%</b> ({actual:,.0f} / {plan.plan_amount:,.0f} р)"
                )
            lines.append("")

        lines.append(f"\n📅 По состоянию на: {today.strftime('%d.%m.%Y')}")

        await call.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=kb_back()
        )
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {html.escape(str(e))}")
    await call.answer()


def _progress_bar(pct: float, width: int = 10) -> str:
    filled = min(int(pct / 100 * width), width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


# ——— Debt / Payroll REMOVED (as requested) ——————————————————————————————————





# ——— Analytics / Charts ——————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:analytics")
async def adm_analytics(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("📊 <b>Аналитика и Графики</b>\n\nВыберите город:",
                                 parse_mode="HTML", reply_markup=kb_analytics_cities())
    await call.answer()


@router.callback_query(F.data.startswith("chart_city:"))
async def analytics_city_select(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[1]
    
    # Fetch projects for this city if not "all"
    projects = []
    if city != "all":
        res = await session.execute(select(Project).where(Project.city == city, Project.is_active == True))
        projects = res.scalars().all()
    
    from bot.keyboards.builders import kb_analytics_options
    city_lbl = {"gomel": "Гомель", "minsk": "Минск", "all": "Все города"}.get(city, city.title())
    await call.message.edit_text(
        f"📊 <b>Аналитика — {city_lbl}</b>\n\nВы хотите посмотреть данные по всему городу или по конкретному проекту?",
        parse_mode="HTML", reply_markup=kb_analytics_options(city, projects)
    )
    await call.answer()


@router.callback_query(F.data.startswith("chart_options:"))
async def analytics_options_select(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")
    city, project_name = parts[1], parts[2]
    if project_name == "none": project_name = None
    
    project_lbl = f" — {project_name}" if project_name else ""
    city_lbl = {"gomel": "Гомель", "minsk": "Минск", "all": "Все города"}.get(city, city.title())
    
    await call.message.edit_text(
        f"📊 <b>Аналитика: {city_lbl}{project_lbl}</b>\n\nВыберите тип визуализации:",
        parse_mode="HTML", reply_markup=kb_analytics(city, project_name)
    )
    await call.answer()


@router.callback_query(F.data.startswith("chart:revenue:"))
async def chart_revenue(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")
    city = parts[2]
    project_name = parts[3] if len(parts) > 3 and parts[3] != "None" else None
    
    city_val = None if city == "all" else city
    await call.message.edit_text("⏳ Генерирую график выручки…")
    
    buf = await generate_revenue_chart(session, days=30, city=city_val, project_name=project_name)
    if not buf:
        await call.message.edit_text("❌ Нет данных для построения графика.", reply_markup=kb_analytics(city))
        return
    
    city_lbl = f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="revenue.png"),
        caption=f"📈 <b>Выручка за последние 30 дней{city_lbl}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, f"Просмотр графика выручки {city}")
    await call.answer()


@router.callback_query(F.data.startswith("chart:revenue_year:"))
async def chart_revenue_year(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")
    city = parts[2]
    project_name = parts[3] if len(parts) > 3 and parts[3] != "None" else None
    
    city_val = None if city == "all" else city
    await call.message.edit_text("⏳ Генерирую годовой график…")
    
    buf = await generate_yearly_revenue_chart(session, city=city_val, project_name=project_name)
    if not buf:
        await call.message.edit_text("❌ Нет данных.", reply_markup=kb_analytics(city, project_name))
        return

    desc = f" — {project_name}" if project_name else f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="year.png"),
        caption=f"📊 <b>Годовая выручка{desc}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await call.answer()


@router.callback_query(F.data.startswith("chart:plan:"))
async def chart_plan(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")
    city = parts[2]
    project_name = parts[3] if len(parts) > 3 and parts[3] != "None" else None

    city_val = None if city == "all" else city
    await call.message.edit_text("⏳ Анализирую выполнение планов…")
    
    buf = await generate_plan_performance_chart(session, city=city_val, project_name=project_name)
    if not buf:
        await call.message.edit_text("❌ Нет данных.", reply_markup=kb_analytics(city, project_name))
        return

    desc = f" — {project_name}" if project_name else f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="plan.png"),
        caption=f"📈 <b>Выполнение планов{desc}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await call.answer()


# ——— Helpers —————————————————————————————————————————————————————————————————

def _parse_date(text: str) -> date:
    from datetime import datetime
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()


# ——— Monthly Calendar Report —————————————————————————————————————————————————

@router.callback_query(F.data == "period:monthly_calendar")
async def period_monthly_calendar(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text(
        "📅 <b>Месячный отчёт</b>\n\nВыберите город:",
        parse_mode="HTML",
        reply_markup=kb_monthly_report_cities()
    )
    await call.answer()


@router.callback_query(F.data.startswith("period:monthly_city:"))
async def monthly_city_select(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    today = date.today()
    city_lbl = {"gomel": "Гомель", "minsk": "Минск", "all": "Все города"}.get(city, city.title())
    await call.message.edit_text(
        f"📅 <b>Месячный отчёт — {city_lbl}</b>\n\nВыберите месяц:",
        parse_mode="HTML",
        reply_markup=kb_month_select(today.year, today.month, city=city)
    )
    await call.answer()


@router.callback_query(F.data.startswith("month:"))
async def send_monthly_calendar(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    parts = call.data.split(":")
    year, month = int(parts[1]), int(parts[2])
    city = parts[3] if len(parts) > 3 else "all"

    import calendar as cal
    month_name = f"{cal.month_name[month]} {year}"
    city_lbl = f" ({city})" if city != "all" else ""
    await call.message.edit_text(f"⏳ Генерирую отчёт за {month_name}{city_lbl}…")
    
    try:
        data = await generate_monthly_calendar(session, year, month, city=city)
        fname = f"report_{city}_{year}-{month:02d}.xlsx"
        await call.message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption=f"📅 Месячный отчёт: <b>{month_name}</b>{city_lbl}",
            parse_mode="HTML",
            reply_markup=menu_admin()
        )
        await call.message.delete()
    except Exception as e:
        import traceback
        traceback.print_exc()
        await call.message.answer(f"❌ Ошибка генерации: {html.quote(str(e))}\n\nПроверьте логи сервера.", reply_markup=menu_admin())
    await call.answer()


# ——— Management Expenses (Расходник / Аренда / Техника) —————————————————————

@router.callback_query(F.data == "adm:mgmt_expenses")
async def adm_mgmt_expenses(call: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext):
    if not _require_admin_or_manager(db_user): return
    await state.clear()
    
    # If manager has a bound project, skip city selection or force it
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and db_user.project_id:
        res = await session.execute(select(Project).where(Project.id == db_user.project_id))
        proj = res.scalar_one_or_none()
        if proj:
            await state.update_data(mgmt_city=proj.city, mgmt_project_id=proj.id, mgmt_project=proj.name)
            await state.set_state(AdminForm.mgmt_category)
            from bot.keyboards.builders import kb_mgmt_categories
            is_admin = db_user.role == UserRole.admin
            await call.message.edit_text(
                f"📂 <b>Упр. расходы — {proj.name} ({proj.city})</b>\n\nВыберите категорию:",
                parse_mode="HTML", reply_markup=kb_mgmt_categories(is_admin=is_admin)
            )
            await call.answer(); return

    await state.set_state(AdminForm.mgmt_city)
    from bot.keyboards.builders import kb_city
    await call.message.edit_text("🏙️ Выберите город для расхода:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.mgmt_city)
async def mgmt_city_select(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        if db_user.role == UserRole.admin:
            return await show_admin_panel(call.message, db_user, state)
        else:
            return await mgr_panel_callback(call, db_user)
    
    city_val = city if city != "none" else None
    await state.update_data(mgmt_city=city_val)
    
    # Get projects for this city from Project table
    q = select(Project.name).where(Project.is_active == True)
    if city_val: q = q.where(Project.city == city_val)
    res = await session.execute(q)
    projects = res.scalars().all()

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for p in sorted(projects):
        b.button(text=p, callback_data=f"mgmt:proj:{p}")
    b.button(text="🌐 Для всех проектов", callback_data="mgmt:proj:all")
    b.button(text="◀️ Назад", callback_data="adm:mgmt_expenses")
    b.adjust(1)

    await state.set_state(AdminForm.mgmt_project)
    await call.message.edit_text(
        "📌 <b>Выберите проект</b>, к которому относится расход,\n"
        "или выберите «Для всех проектов»:",
        parse_mode="HTML", reply_markup=b.as_markup()
    )
    await call.answer()


@router.callback_query(AdminForm.mgmt_project, F.data.startswith("mgmt:proj:"))
async def mgmt_project_select(call: CallbackQuery, state: FSMContext, db_user: User):
    proj = call.data.split(":")[2]
    await state.update_data(mgmt_project=None if proj == "all" else proj)
    
    from bot.keyboards.builders import kb_mgmt_categories
    await state.set_state(AdminForm.mgmt_category)
    is_admin = db_user.role == UserRole.admin
    await call.message.edit_text("📂 Выберите категорию расхода:", reply_markup=kb_mgmt_categories(is_admin=is_admin))
    await call.answer()


@router.callback_query(AdminForm.mgmt_category, F.data.startswith("mgmt:cat:"))
async def mgmt_category_select(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[2]
    await state.update_data(mgmt_category=cat)
    await state.set_state(AdminForm.mgmt_date)
    
    if cat == "аренда":
        from bot.keyboards.builders import kb_mgmt_month_select
        today = date.today()
        await call.message.edit_text(
            "🏠 <b>Аренда</b>\nВыберите месяц, за который вносится оплата:",
            parse_mode="HTML",
            reply_markup=kb_mgmt_month_select(today.year, today.month)
        )
    else:
        from bot.keyboards.builders import kb_use_today
        today_str = date.today().strftime("%d.%m.%Y")
        await call.message.edit_text(
            f"📅 Категория: <b>{cat}</b>\nВведите <b>дату</b> расхода (ДД.ММ.ГГГГ):",
            parse_mode="HTML", reply_markup=kb_use_today(today_str)
        )
    await call.answer()


@router.callback_query(AdminForm.mgmt_date, F.data.startswith("mgmt:month:"))
async def mgmt_month_select(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    year, month = int(parts[2]), int(parts[3])
    # Store as 1st day of month for monthly expenses
    d = date(year, month, 1)
    await state.update_data(mgmt_date=d.isoformat())
    await mgmt_ask_amount(call.message, state)
    await call.answer()


@router.callback_query(AdminForm.mgmt_date, F.data == "report:use_today")
async def mgmt_date_today(call: CallbackQuery, state: FSMContext):
    await state.update_data(mgmt_date=date.today().isoformat())
    await mgmt_ask_amount(call.message, state)
    await call.answer()


@router.message(AdminForm.mgmt_date)
async def mgmt_date_input(message: Message, state: FSMContext):
    try:
        d = _parse_date(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:"); return
    await state.update_data(mgmt_date=d.isoformat())
    await mgmt_ask_amount(message, state)


async def mgmt_ask_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    cat = data.get("mgmt_category", "расход")
    await state.set_state(AdminForm.mgmt_amount)
    await message.answer(f"💰 Введите <b>сумму</b> ({cat}):", parse_mode="HTML", reply_markup=kb_back())


# Handler removed as logic moved upstream


@router.message(AdminForm.mgmt_amount)
async def mgmt_amount_input(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip().replace(" ", "").replace(",", "."))
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите число:"); return
    await state.update_data(mgmt_amount=v)
    await state.set_state(AdminForm.mgmt_comment)
    from bot.keyboards.builders import kb_cancel_skip
    await message.answer("💬 Добавьте комментарий (или пропустите):", reply_markup=kb_cancel_skip())


@router.callback_query(AdminForm.mgmt_comment, F.data == "report:skip")
async def mgmt_comment_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user): return
    await state.update_data(mgmt_comment=None)
    await mgmt_save(call.message, state, session, db_user)
    await call.answer()


@router.message(AdminForm.mgmt_comment)
async def mgmt_comment_input(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user): return
    await state.update_data(mgmt_comment=message.text.strip())
    await mgmt_save(message, state, session, db_user)


async def mgmt_save(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user): return
    d = await state.get_data()
    expense = ManagementExpense(
        date=date.fromisoformat(d["mgmt_date"]),
        city=d["mgmt_city"],
        project_name=d.get("mgmt_project"),
        category=d["mgmt_category"],
        amount=d["mgmt_amount"],
        comment=d.get("mgmt_comment")
    )
    session.add(expense)
    await log_action(session, db_user.id, "Добавлен управл. расход", f"{d['mgmt_category']}: {d['mgmt_amount']} р")
    await session.commit()
    
    kb = menu_admin() if db_user.role == UserRole.admin else menu_manager()
    await message.answer("✅ Управленческий расход сохранён!", reply_markup=kb)


# ——— Management Expense List/Delete (Admin Only) ——————————————————————————————

@router.callback_query(F.data == "mgmt:list_start")
async def adm_mgmt_list_start(call: CallbackQuery, db_user: User, state: FSMContext):
    if not _require_admin(db_user): return
    await state.set_state(AdminForm.mgmt_list_date)
    from bot.keyboards.builders import kb_use_today
    today_str = date.today().strftime("%d.%m.%Y")
    await call.message.edit_text(
        "🔍 <b>Список расходов для удаления</b>\n\nВведите <b>дату</b> (ДД.ММ.ГГГГ):",
        parse_mode="HTML", reply_markup=kb_use_today(today_str)
    )
    await call.answer()


@router.callback_query(AdminForm.mgmt_list_date, F.data == "report:use_today")
@router.message(AdminForm.mgmt_list_date)
async def adm_mgmt_list_view(event: Message | CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    
    if isinstance(event, CallbackQuery):
        d_val = date.today()
        message = event.message
    else:
        try:
            d_val = _parse_date(event.text)
            message = event
        except ValueError:
            return await event.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:")

    res = await session.execute(
        select(ManagementExpense).where(ManagementExpense.date == d_val).order_by(ManagementExpense.created_at)
    )
    expenses = res.scalars().all()
    
    if not expenses:
        from bot.keyboards.builders import kb_back
        txt = f"📭 За <b>{d_val.strftime('%d.%m.%Y')}</b> расходов не найдено."
        if isinstance(event, CallbackQuery):
            await message.edit_text(txt, parse_mode="HTML", reply_markup=kb_back("adm:mgmt_expenses"))
        else:
            await message.answer(txt, parse_mode="HTML", reply_markup=kb_back("adm:mgmt_expenses"))
        return

    from bot.keyboards.builders import kb_mgmt_list
    txt = f"🔍 <b>Расходы за {d_val.strftime('%d.%m.%Y')}:</b>\n\nНажмите 🗑️ для удаления."
    if isinstance(event, CallbackQuery):
        await message.edit_text(txt, parse_mode="HTML", reply_markup=kb_mgmt_list(expenses))
    else:
        await message.answer(txt, parse_mode="HTML", reply_markup=kb_mgmt_list(expenses))
    await state.update_data(mgmt_list_date=d_val.isoformat())


@router.callback_query(F.data.startswith("mgmt:del:"))
async def adm_mgmt_delete(call: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext):
    if not _require_admin(db_user): return
    exp_id = int(call.data.split(":")[2])
    
    res = await session.execute(select(ManagementExpense).where(ManagementExpense.id == exp_id))
    exp = res.scalar_one_or_none()
    
    if exp:
        info = f"{exp.category}: {exp.amount} р ({exp.date})"
        await session.delete(exp)
        await log_action(session, db_user.id, "Удален управл. расход", info)
        await session.commit()
        await call.answer("✅ Удалено", show_alert=True)
        
        # Refresh the list
        data = await state.get_data()
        d_str = data.get("mgmt_list_date")
        if d_str:
            d_val = date.fromisoformat(d_str)
            res2 = await session.execute(
                select(ManagementExpense).where(ManagementExpense.date == d_val).order_by(ManagementExpense.created_at)
            )
            expenses = res2.scalars().all()
            if expenses:
                from bot.keyboards.builders import kb_mgmt_list
                await call.message.edit_reply_markup(reply_markup=kb_mgmt_list(expenses))
            else:
                from bot.keyboards.builders import kb_back
                await call.message.edit_text(f"📭 Расходов за {d_val.strftime('%d.%m.%Y')} больше нет.", 
                                            reply_markup=kb_back("adm:mgmt_expenses"))
    else:
        await call.answer("Ошибка: расход не найден")


# ——— Manager Panel ———————————————————————————————————————————————————————————

@router.message(F.text == "⚙️ Панель управляющего")
async def show_manager_panel(message: Message, db_user: User):
    if not _require_admin_or_manager(db_user):
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "⚙️ <b>Панель управляющего</b>\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=_kb_manager_main()
    )


@router.callback_query(F.data == "mgr:panel")
async def mgr_panel_callback(call: CallbackQuery, db_user: User):
    if not _require_admin_or_manager(db_user): return
    await call.message.edit_text(
        "⚙️ <b>Панель управляющего</b>\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=_kb_manager_main()
    )
    await call.answer()

# Keyboard is now defined at the top as _kb_manager_main


# ——— Manager Mgmt Expenses (Separate Flow) ———————————————————————————————————

@router.callback_query(F.data == "mgr:mgmt_start")
async def mgr_mgmt_start(call: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext):
    if not db_user.role.value == "manager": return
    if not db_user.project_id:
        from bot.keyboards.builders import kb_back
        await call.message.edit_text(
            "⚠️ Вы не привязаны к конкретному проекту. Пожалуйста, обратитесь к администратору для назначения проекта.",
            reply_markup=kb_back("mgr:panel")
        )
        await call.answer(); return
    
    await state.clear()
    res = await session.execute(select(Project).where(Project.id == db_user.project_id))
    proj = res.scalar_one_or_none()
    if not proj:
        return await call.answer("❌ Проект не найден.", show_alert=True)

    await state.update_data(mgmt_city=proj.city, mgmt_project_id=proj.id, mgmt_project=proj.name)
    await state.set_state(ManagerMgmtForm.date)
    
    from bot.keyboards.builders import kb_mgmt_date
    t = date.today().strftime("%d.%m.%Y")
    y = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
    await call.message.edit_text(
        f"📂 <b>Упр. расходы — {proj.name} ({proj.city})</b>\n\nВыберите дату:",
        parse_mode="HTML", reply_markup=kb_mgmt_date(t, y)
    )
    await call.answer()


@router.callback_query(ManagerMgmtForm.date, F.data.startswith("mgr:mgmt:date:"))
async def mgr_mgmt_date_select(call: CallbackQuery, state: FSMContext):
    action = call.data.split(":")[3]
    d_val = date.today() if action == "today" else date.today() - timedelta(days=1)
    
    await state.update_data(mgmt_date=d_val.isoformat())
    await state.set_state(ManagerMgmtForm.category)
    
    data = await state.get_data()
    proj_name = data.get("mgmt_project", "Проект")
    
    from bot.keyboards.builders import kb_mgmt_categories_mgr
    await call.message.edit_text(
        f"📂 <b>Упр. расходы — {proj_name}</b>\n📅 Дата: <b>{d_val.strftime('%d.%m.%Y')}</b>\n\nВыберите категорию:",
        parse_mode="HTML", reply_markup=kb_mgmt_categories_mgr()
    )
    await call.answer()


@router.callback_query(ManagerMgmtForm.category, F.data.startswith("mgr:mgmt:cat:"))
async def mgr_mgmt_cat_select(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[3]
    await state.update_data(mgmt_category=cat)
    await state.set_state(ManagerMgmtForm.amount)
    await call.message.edit_text(f"💰 Категория: <b>{cat}</b>\n\nВведите сумму (число):", parse_mode="HTML")
    await call.answer()


@router.message(ManagerMgmtForm.amount)
async def mgr_mgmt_amount_input(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(',', '.').strip())
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите число:"); return
    await state.update_data(mgmt_amount=v)
    await state.set_state(ManagerMgmtForm.comment)
    from bot.keyboards.builders import kb_cancel_skip
    await message.answer("💬 Добавьте комментарий (или пропустите):", reply_markup=kb_cancel_skip("mgr:mgmt_start"))


@router.callback_query(ManagerMgmtForm.comment, F.data == "report:skip")
async def mgr_mgmt_comment_skip(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    await state.update_data(mgmt_comment=None)
    await mgmt_save(call.message, state, session, db_user)
    await call.answer()


@router.message(ManagerMgmtForm.comment)
async def mgr_mgmt_comment_input(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    await state.update_data(mgmt_comment=message.text.strip())
    await mgmt_save(message, state, session, db_user)

@router.callback_query(F.data.startswith("review:list:"))
async def review_list(call: CallbackQuery | None, session: AsyncSession, db_user: User, message: Message | None = None):
    # review:list:<page>
    page = int(call.data.split(":")[2]) if call and ":" in call.data else 0
    if not session:
        from bot.database.db import SessionLocal
        async with SessionLocal() as session:
            return await _review_list_impl(call, session, db_user, message, page)
    return await _review_list_impl(call, session, db_user, message, page)


async def _review_list_impl(call: CallbackQuery | None, session: AsyncSession, db_user: User, message: Message | None = None, page: int = 0):
    if not _require_admin_or_manager(db_user):
        if call: return await call.answer("Нет доступа", show_alert=True)
        return await message.answer("Нет доступа")

    # Manager must be bound to a project to see reports
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and not db_user.project_id:
        from bot.keyboards.builders import kb_back
        txt = "⚠️ Вы не привязаны к конкретному проекту. Пожалуйста, обратитесь к администратору для назначения проекта."
        if call:
            await call.message.edit_text(txt, reply_markup=kb_back("mgr:panel"))
            await call.answer()
        else:
            await message.answer(txt, reply_markup=kb_back("mgr:panel"))
        return

    # Needs to match all unreviewed reports
    stmt = select(Report).where(Report.is_reviewed == False)
    
    # Manager restriction: only their project
    if role_val == "manager" and db_user.project_id:
        stmt = stmt.where(Report.project_id == db_user.project_id)
        
    stmt = stmt.order_by(Report.id.desc())
    res = await session.execute(stmt)
    reports = res.scalars().all()

    target = message or call.message
    if not reports:
        from bot.keyboards.builders import kb_back
        txt = "✅ Все доступные отчеты проверены!"
        if call:
            await call.message.edit_text(txt, reply_markup=kb_back())
            await call.answer()
        else:
            await message.answer(txt, reply_markup=kb_back())
        return

    # Pagination: 15 per page
    limit = 15
    total = len(reports)
    start = page * limit
    end = start + limit
    page_reports = reports[start:end]

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    for r in page_reports:
        date_str = r.date.strftime("%d.%m")
        proj_short = (r.project_name[:10] + "..") if len(r.project_name) > 12 else r.project_name
        btn_text = f"⏳ {date_str} | {proj_short} | {r.revenue:,.0f} BYN"
        b.button(text=btn_text, callback_data=f"review:view:{r.id}")
    
    b.adjust(1)
    
    b.adjust(1)
    
    # Paging buttons
    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(text="⬅️ Пред.", callback_data=f"review:list:{page-1}"))
    if end < total:
        nav_btns.append(InlineKeyboardButton(text="След. ➡", callback_data=f"review:list:{page+1}"))
    if nav_btns:
        b.row(*nav_btns)

    # Back button
    back_cb = "adm:back" if db_user.role == UserRole.admin else "mgr:panel"
    b.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_cb))
    
    txt = f"📋 <b>Непроверенные отчеты (Всего: {total}):</b>\nСтр. {page+1} из {(total-1)//limit + 1}"
    if call:
        await call.message.edit_text(txt, parse_mode="HTML", reply_markup=b.as_markup())
        await call.answer()
    else:
        await message.answer(txt, parse_mode="HTML", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("review:view:"))
async def review_view(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("Нет доступа")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if not r:
        return await call.answer("Отчет не найден", show_alert=True)

    # Format similar to confirming report
    city_label = r.city or "—"
    text = (
        f"📋 <b>Детали отчёта #{r.id}</b>\n\n"
        f"📅 Дата:              <b>{r.date.strftime('%d.%m.%Y')}</b>\n"
        f"🏙️ Город:              <b>{city_label}</b>\n"
        f"🎭 Проект:            <b>{r.project_name}</b>\n"
        f"👤 Сотрудник:         <b>{r.employee_name}</b>\n"
        f"👥 Чел. в смене:      <b>{r.shift_count}</b>\n\n"
        f"💰 Выручка:           <b>{r.revenue:,.0f} BYN</b>\n"
        f"💵 Наличные:          <b>{r.cash:,.0f} BYN</b>\n"
        f"💳 Эквайринг:         <b>{r.acquiring:,.0f} BYN</b>\n"
        f"📉 Хоз расход:        <b>{r.expense:,.0f} BYN</b>\n"
        f"🎓 ЗП стажёра:       <b>{r.trainee_salary:,.0f} BYN</b>\n"
        f"🏦 Остаток в кассе:   <b>{r.cash_balance:,.0f} BYN</b>\n"
        f"👣 Посетители:        <b>{r.visitors}</b>\n"
        f"🎂 Дней рождений:     <b>{r.birthdays}</b>\n"
        f"💬 Комментарий:       <b>{r.comment or '—'}</b>\n\n"
        f"Фактическая ЗП смены: {_fmt(r.salary_paid)} BYN\n"
    )

    is_admin = db_user.role == UserRole.admin
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_review(r.id, is_admin=is_admin))
    await call.answer()


@router.callback_query(F.data.startswith("review:ok:"))
async def review_ok(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("Нет доступа")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if r:
        r.is_reviewed = True
        r.reviewed_by_id = db_user.id
        await session.commit()
        await call.answer("Отчет проверен!", show_alert=True)
        # return to tree
        await review_list(call, session, db_user)
    else:
        await call.answer("Ошибка, отчет не найден")


@router.callback_query(F.data.startswith("review:edit:"))
async def review_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin(db_user):
        return await call.answer("Только для админов")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if not r:
        return await call.answer("Отчет не найден")

    await state.clear()
    # Load all data into state
    emp_name = r.employee_name
    partners = None
    if " + " in emp_name:
        parts = emp_name.split(" + ", 1)
        emp_name = parts[0]
        partners = parts[1]

    await state.update_data(
        admin_editing_report_id=r.id,
        date=r.date.isoformat(),
        project=r.project_name,
        project_id=r.project_id,
        city=r.city,
        employee_name=emp_name,
        partners=partners,
        shift_count=r.shift_count,
        revenue=r.revenue,
        cash=r.cash,
        acquiring=r.acquiring,
        expense=r.expense,
        trainee_salary=r.trainee_salary,
        cash_balance=r.cash_balance,
        visitors=r.visitors,
        birthdays=r.birthdays,
        comment=r.comment,
        salary=r.salary_paid,
        salary_level=r.salary_level
    )
    
    # Use ReportForm states to allow editing
    from bot.handlers.report import ReportForm
    await state.set_state(ReportForm.confirm) # Start at confirm point to show Edit Menu
    
    from bot.keyboards.builders import kb_edit_fields
    await call.message.edit_text(
        f"🛠️ <b>Редактирование отчёта #{r.id}</b>\n(Сотрудник: {r.employee_name}, Дата: {r.date.strftime('%d.%m.%Y')})\n\n"
        "Выберите поле для изменения:",
        parse_mode="HTML", reply_markup=kb_edit_fields()
    )
    await call.answer()

# ——— MY SALARY (MANAGER) —————————————————————————————————————————————————————

@router.callback_query(F.data == "mgr:my_salary")
async def mgr_my_salary(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("Нет доступа")

    # Managers MUST be bound to a project
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and not db_user.project_id:
        await call.message.edit_text("⚠️ Вы не привязаны к конкретному проекту. Пожалуйста, обратитесь к администратору для назначения проекта.", reply_markup=kb_back("mgr:panel"))
        await call.answer(); return

    city = db_user.city

    # Fast plan lookup
    filters = [Plan.is_active == True, Plan.period == 'month']
    if role_val == "manager" and db_user.project_id:
        filters.append(Plan.project_id == db_user.project_id)
    elif city:
        filters.append(Plan.city == city)
        
    res = await session.execute(select(Plan).where(*filters))
    plans = res.scalars().all()

    if not plans:
        back_cb = "adm:back" if role_val == "admin" else "mgr:panel"
        await call.message.edit_text("ℹ️ Для вашего профиля/проекта не найдено активных планов на этот месяц.", reply_markup=kb_back(back_cb))
        await call.answer()
        return

    today = date.today()
    start_of_month = today.replace(day=1)

    lines = [f"💼 <b>Ваша ЗП (как Управляющего) за {today.strftime('%m.%Y')}</b>\n"]
    total_salary = 0.0

    for plan in plans:
        project_name = plan.project_name or "Все проекты"
        city_lbl = plan.city or "Все города"
        
        # turn over
        rev_filters = [Report.date >= start_of_month]
        if plan.project_name:
            rev_filters.append(Report.project_name == plan.project_name)
        if plan.city:
            rev_filters.append(Report.city == plan.city)
            
        res_rev = await session.execute(select(func.sum(Report.revenue)).where(*rev_filters))
        actual = res_rev.scalar() or 0.0

        salary, desc = calculate_manager_salary(float(actual), plan.plan_amount)
        total_salary += salary
        lines.append(f"🎯 <b>План ({city_lbl} | {project_name}):</b> {_fmt(plan.plan_amount)} BYN")
        lines.append(f"💰 Факт: {_fmt(actual)} BYN")
        lines.append(f"📊 {desc}")
        lines.append(f"💵 <b>К выплате: {_fmt(salary)}</b> BYN\n")

    lines.append(f"────────────────")
    lines.append(f"🏆 <b>Итого ваша ЗП: {_fmt(total_salary)} BYN</b>")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    back_cb = "adm:manager_salary" if db_user.role.value == "admin" else "mgr:panel"
    b.button(text="◀️ Назад", callback_data=back_cb)

    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=b.as_markup())
    await call.answer()



# ——— Report Rejection ————————————————————————————————————————————————————————

@router.callback_query(F.data.startswith("review:reject_start:"))
async def review_reject_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("Нет доступа")

    report_id = int(call.data.split(":")[2])
    await state.update_data(reject_report_id=report_id)
    await state.set_state(AdminForm.reject_reason)
    
    await call.message.answer(
        "📝 <b>Причина отклонения</b>\n\nВведите причину (её увидит сотрудник).\n"
        "Например: <i>«Неверно указана выручка по безналу»</i>",
        parse_mode="HTML",
        reply_markup=kb_back("review:list") # Back button to list
    )
    await call.answer()


@router.message(AdminForm.reject_reason)
async def process_reject_reason(message: Message, state: FSMContext, session: AsyncSession, db_user: User, bot: Bot):
    reason = message.text.strip()
    data = await state.get_data()
    report_id = data.get("reject_report_id")
    await state.clear()

    if not report_id:
        await message.answer("Ошибка: ID отчета потерян. Начните сначала.")
        return

    # 1. Find report and employee
    res = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    r = res.scalar_one_or_none()
    
    if not r:
        await message.answer("❌ Отчет не найден (возможно, уже удален).")
        return

    emp_id = r.user_id
    date_str = r.date.strftime("%d.%m.%Y")
    proj_name = r.project_name

    # 2. Notify employee
    try:
        notify_text = (
            f"⚠️ <b>Ваш отчет отклонён!</b>\n\n"
            f"📅 Дата: {date_str}\n"
            f"🎭 Проект: {proj_name}\n"
            f"💬 Причина: <i>{reason}</i>\n\n"
            f"Пожалуйста, <b>сдайте отчет заново</b> с корректными данными."
        )
        await bot.send_message(emp_id, notify_text, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to notify employee {emp_id}: {e}")

    # 3. Delete report
    await session.delete(r)
    await log_action(session, db_user.id, "Отклонил отчет", f"ID {report_id}, Причина: {reason}")
    await session.commit()

    await message.answer(f"✅ Отчет #{report_id} успешно отклонен. Сотрудник уведомлен.")
    
    # Return to panel
    if db_user.role == UserRole.admin:
        await show_admin_panel(message, db_user, state)
    else:
        await show_manager_panel(message, db_user)


# ——— Projects ————————————————————————————————————————————————————————————————

@router.callback_query(F.data == "adm:projects")
async def adm_projects(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(select(Project).order_by(Project.city, Project.name))
    projs = res.scalars().all()
    
    from collections import defaultdict
    by_city = defaultdict(list)
    for p in projs:
        by_city[p.city].append(p)
        
    await call.message.edit_text(
        "🏢 <b>Управление проектами</b>\n\nЗдесь вы можете добавлять новые места работы.",
        parse_mode="HTML", reply_markup=kb_projects(by_city)
    )
    await call.answer()


@router.callback_query(F.data.startswith("proj:view:"))
async def proj_view(call: CallbackQuery, session: AsyncSession):
    proj_id = int(call.data.split(":")[2])
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if not p: return await call.answer("Не найден")
    
    city_str = {"gomel": "🏙️ Гомель", "minsk": "🌆 Минск"}.get(p.city, p.city)
    status = "✅ Активен" if p.is_active else "⏸ Приостановлен"
    text = (
        f"🏢 <b>Проект: {p.name}</b>\n"
        f"🏙️ Город: {city_str}\n"
        f"📊 Статус: {status}"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_project_actions(p.id, p.is_active))
    await call.answer()


@router.callback_query(F.data.startswith("proj:toggle:"))
async def proj_toggle(call: CallbackQuery, session: AsyncSession):
    proj_id = int(call.data.split(":")[2])
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if p:
        p.is_active = not p.is_active
        await session.commit()
    await proj_view(call, session)


@router.callback_query(F.data.startswith("proj:delete:"))
async def proj_delete(call: CallbackQuery, session: AsyncSession, db_user: User):
    proj_id = int(call.data.split(":")[2])
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if p:
        await session.delete(p)
        await session.commit()
    await adm_projects(call, session, db_user)


@router.callback_query(F.data == "proj:add")
async def proj_add_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.proj_city)
    from bot.keyboards.builders import kb_city
    await call.message.edit_text("🏙️ Выберите город для нового проекта:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.proj_city)
async def proj_add_city(call: CallbackQuery, state: FSMContext, db_user: User):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        return await adm_back(call, db_user, state)
        
    await state.update_data(proj_city=city)
    await state.set_state(AdminForm.proj_name)
    await call.message.edit_text("📌 Введите <b>название проекта</b> (например: Садик №5):", 
                                 parse_mode="HTML", reply_markup=kb_back("adm:projects"))
    await call.answer()


@router.message(AdminForm.proj_name)
async def proj_add_name(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    name = message.text.strip()
    data = await state.get_data()
    city = data.get("proj_city")
    
    session.add(Project(name=name, city=city))
    await session.commit()
    await state.clear()
    
    await message.answer(f"✅ Проект «{name}» добавлен!", reply_markup=menu_admin())

@router.message(Command("setproj"))
async def debug_set_proj(message: Message, session: AsyncSession, db_user: User):
    if message.from_user.id != 786320574: return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("❌ Usage: `/setproj <proj_id> [user_tg_id]`", parse_mode="Markdown")
    try:
        proj_id = int(args[1])
        target_id = int(args[2]) if len(args) > 2 else db_user.telegram_id
    except ValueError:
        return await message.answer("❌ IDs must be numbers.")
    if proj_id != 0:
        res = await session.execute(select(Project).where(Project.id == proj_id))
        proj = res.scalar_one_or_none()
        if not proj: return await message.answer(f"❌ Project ID {proj_id} not found.")
    res = await session.execute(select(User).where(User.telegram_id == target_id))
    target_user = res.scalar_one_or_none()
    if not target_user: return await message.answer(f"❌ User with TG ID {target_id} not found.")
    target_user.project_id = proj_id if proj_id != 0 else None
    await session.commit()
    proj_name = proj.name if proj_id != 0 else "None"
    await message.answer(f"✅ User {target_user.pretty_name} ({target_id}) bound to project: <b>{proj_name}</b> (ID: {proj_id})", parse_mode="HTML")

@router.message(Command("projects"))
async def debug_list_projects(message: Message, session: AsyncSession, db_user: User):
    if message.from_user.id != 786320574: return
    res = await session.execute(select(Project).order_by(Project.id))
    projects = res.scalars().all()
    if not projects: return await message.answer("🤷‍♂️ Проектов не найдено.")
    lines = ["📌 <b>Список проектов (для /setproj):</b>\n"]
    for p in projects:
        status = "✅" if p.is_active else "❌"
        lines.append(f"<code>{p.id}</code>: {p.name} ({p.city}) {status}")
    await message.answer("\n".join(lines), parse_mode="HTML")

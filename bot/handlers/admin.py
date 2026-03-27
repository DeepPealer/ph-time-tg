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


def _kb_manager_main() -> "InlineKeyboardMarkup":
    from bot.keyboards.builders import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardMarkup
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“‹ ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð²", callback_data="review:list")
    b.button(text="ðŸ’¼ ÐœÐ¾Ñ Ð—ÐŸ", callback_data="mgr:my_salary")
    b.button(text="ðŸ“‚ Ð£Ð¿Ñ€. Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹", callback_data="adm:mgmt_expenses")
    b.button(text="ðŸ“Š ÐÐ½Ð°Ð»Ð¸Ñ‚Ð¸ÐºÐ°", callback_data="adm:analytics")
    b.adjust(1)
    return b.as_markup()


# â”€â”€â”€ Entry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.message(F.text == "âš™ï¸ ÐÐ´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»ÑŒ")
async def show_admin_panel(message: Message, db_user: User, state: FSMContext):
    if not _require_admin(db_user):
        await message.answer("â›” ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°.")
        return
    await state.clear()
    await message.answer("âš™ï¸ <b>ÐÐ´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»ÑŒ</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ€Ð°Ð·Ð´ÐµÐ»:",
                         parse_mode="HTML", reply_markup=kb_admin_main())


@router.message(F.text == "ðŸ“‹ ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð¾Ñ‚ Ð¼ÐµÐ½ÐµÐ´Ð¶ÐµÑ€Ð°")
async def admin_review_reports(message: Message, db_user: User, session: AsyncSession):
    if not _require_admin_or_manager(db_user): return
    # Reuse the manager's review list logic
    from bot.handlers.admin import review_list
    # We need a dummy callback-like object or just call the logic
    # Actually it's cleaner to just call a helper or the function with message
    await review_list(None, session, db_user, message=message)


# â”€â”€â”€ Back â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "admin":
        await call.message.edit_text("âš™ï¸ <b>ÐÐ´Ð¼Ð¸Ð½-Ð¿Ð°Ð½ÐµÐ»ÑŒ</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ€Ð°Ð·Ð´ÐµÐ»:",
                             parse_mode="HTML", reply_markup=kb_admin_main())
    else:
        # Redirect manager to their panel
        await call.message.edit_text("âš™ï¸ <b>ÐŸÐ°Ð½ÐµÐ»ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ€Ð°Ð·Ð´ÐµÐ»:",
                             parse_mode="HTML", reply_markup=_kb_manager_main())
    await call.answer()


# â”€â”€â”€ Reports / Excel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:reports")
async def adm_reports(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°", show_alert=True)
    try:
        await call.message.edit_text("ðŸ“Š <b>Ð£Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð°Ð¼Ð¸</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð´ÐµÐ¹ÑÑ‚Ð²Ð¸Ðµ:",
                                     parse_mode="HTML", reply_markup=kb_report_search_nav())
    except Exception as e:
        await call.message.answer(f"âŒ ÐžÑˆÐ¸Ð±ÐºÐ°: {html.escape(str(e))}")
    await call.answer()


@router.callback_query(F.data == "adm:reports_by_date")
async def adm_reports_by_date_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.report_search_date)
    await call.message.edit_text(
        "ðŸ“… <b>ÐŸÐ¾Ð¸ÑÐº Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð¿Ð¾ Ð´Ð°Ñ‚Ðµ</b>\n\nÐ’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð´Ð°Ñ‚Ñƒ Ð² Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ðµ Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“\n(Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: 26.03.2026):",
        parse_mode="HTML", reply_markup=kb_back("adm:reports")
    )
    await call.answer()


@router.message(AdminForm.report_search_date)
async def adm_reports_by_date_input(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        await state.update_data(search_date=dt.isoformat())
        await state.set_state(AdminForm.report_search_city)
        from bot.keyboards.builders import kb_city
        await message.answer("ðŸ™ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´ Ð´Ð»Ñ Ñ„Ð¸Ð»ÑŒÑ‚Ñ€Ð°Ñ†Ð¸Ð¸:", reply_markup=kb_city())
    except ValueError:
        await message.answer("âŒ ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚. Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð´Ð°Ñ‚Ñƒ ÐºÐ°Ðº Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“ (Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€, 26.03.2026)")


@router.callback_query(AdminForm.report_search_city)
async def adm_reports_by_date_city(call: CallbackQuery, state: FSMContext, session: AsyncSession):
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
        "ðŸ“ <b>Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚</b> Ð´Ð»Ñ Ð¿Ð¾Ð¸ÑÐºÐ°:",
        parse_mode="HTML", reply_markup=kb_projects_for_search(projects)
    )
    await call.answer()


@router.callback_query(AdminForm.report_search_proj)
async def adm_reports_by_date_finish(call: CallbackQuery, state: FSMContext, session: AsyncSession):
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
        
    res = await session.execute(query.order_by(Report.id.desc()))
    reports = res.scalars().all()
    await state.clear()
    
    if not reports:
        await call.message.edit_text("ðŸ¤·â€â™‚ï¸ ÐžÑ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾.", reply_markup=kb_back("adm:reports"))
        return
        
    # Show list of reports (mini-cards)
    text = f"ðŸ“… <b>ÐžÑ‚Ñ‡Ñ‘Ñ‚Ñ‹ Ð·Ð° {s_date.strftime('%d.%m.%Y')}</b>\nÐÐ°Ð¹Ð´ÐµÐ½Ð¾: {len(reports)}\n\n"
    from bot.keyboards.builders import kb_report_list_mini
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_list_mini(reports))
    await call.answer()





# â”€â”€â”€ Employees â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:employees")
async def adm_employees(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    
    res_count = await session.execute(
        select(func.count()).where(User.role != UserRole.pending)
    )
    total_emps = res_count.scalar() or 0

    await call.message.edit_text(
        f"ðŸ‘¥ <b>Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¸</b> ({total_emps} Ñ‡ÐµÐ».)\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:",
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
        city_label = "â“ Ð‘Ð•Ð— Ð“ÐžÐ ÐžÐ”Ð"
    else:
        query = query.where(User.city == city)
        city_label = "ðŸ™ Ð“ÐžÐœÐ•Ð›Ð¬" if city == "gomel" else "ðŸŒ† ÐœÐ˜ÐÐ¡Ðš"
        
    res = await session.execute(query.order_by(User.full_name))
    employees = res.scalars().all()
    
    await call.message.edit_text(
        f"ðŸ‘¥ <b>Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¸ â€” {city_label}</b> ({len(employees)} Ñ‡ÐµÐ».)\n\n",
        parse_mode="HTML", reply_markup=kb_employee_list(employees, city_label)
    )
    await call.answer()


@router.callback_query(F.data.startswith("emp:view:"))
async def emp_view(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if not emp:
        await call.answer("ÐÐµ Ð½Ð°Ð¹Ð´ÐµÐ½", show_alert=True); return
    role_str = {"admin": "ÐÐ´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€", "manager": "Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹", "employee": "Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº"}.get(emp.role.value, emp.role.value)
    city_str = {"gomel": "ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ðŸŒ† ÐœÐ¸Ð½ÑÐº"}.get(emp.city or "", "â“ Ð½Ðµ Ð·Ð°Ð´Ð°Ð½")
    proj_str = "ðŸ”“ ÐÐµÑ‚ Ð¿Ñ€Ð¸Ð²ÑÐ·ÐºÐ¸"
    if emp.project_id:
        pres = await session.execute(select(Project).where(Project.id == emp.project_id))
        p = pres.scalar_one_or_none()
        if p: proj_str = f"ðŸ“ {p.name}"

    text = (
        f"ðŸ‘¤ <b>{emp.full_name}</b>\n"
        f"ðŸ“Ž @{emp.username or 'â€”'}\n"
        f"ðŸ†” {emp.telegram_id}\n"
        f"ðŸŽ­ Ð Ð¾Ð»ÑŒ: {role_str}\n"
        f"ðŸ™ Ð“Ð¾Ñ€Ð¾Ð´: {city_str}\n"
        f"ðŸ“‚ ÐŸÑ€Ð¾ÐµÐºÑ‚: {proj_str}\n"
        f"âœ… ÐÐºÑ‚Ð¸Ð²ÐµÐ½: {'Ð”Ð°' if emp.is_active else 'ÐÐµÑ‚'}"
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
        await call.answer("ðŸ¤·â€â™‚ï¸ ÐÐµÑ‚ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð² Ð°Ñ€Ñ…Ð¸Ð²Ðµ", show_alert=True)
        return
        
    text = f"ðŸ“‚ <b>ÐÑ€Ñ…Ð¸Ð² Ð¿Ð¾ÑÐ»ÐµÐ´Ð½Ð¸Ñ… Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð²</b>\n(Ð¿Ð¾ÑÐ»ÐµÐ´Ð½Ð¸Ðµ 20 ÑˆÑ‚.)\n\n"
    from bot.keyboards.builders import kb_report_list_mini
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_list_mini(reports))
    await call.answer()



@router.callback_query(F.data == "emp:add")
async def emp_add_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.add_emp_id)
    await call.message.edit_text(
        "âž• Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>Telegram ID</b> Ð½Ð¾Ð²Ð¾Ð³Ð¾ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°\n"
        "(ÑƒÐ·Ð½Ð°Ñ‚ÑŒ Ð¼Ð¾Ð¶Ð½Ð¾ Ñ‡ÐµÑ€ÐµÐ· @userinfobot):",
        parse_mode="HTML", reply_markup=kb_back("adm:employees")
    )
    await call.answer()


@router.message(AdminForm.add_emp_id)
async def emp_add_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾Ð²Ð¾Ð¹ Telegram ID:"); return

    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    user = res.scalar_one_or_none()

    if user:
        user.role = UserRole.employee
        user.is_active = True
        await session.commit()
        await message.answer(f"âœ… {user.full_name} Ñ‚ÐµÐ¿ÐµÑ€ÑŒ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº!", reply_markup=menu_admin())
    else:
        # Pre-create record; will be enriched on first /start
        new = User(telegram_id=tg_id, full_name=f"User_{tg_id}",
                   role=UserRole.employee, is_active=True)
        session.add(new)
        await session.commit()
        await message.answer(
            f"âœ… ID {tg_id} Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ ÐºÐ°Ðº ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº.\n"
            "ÐŸÐ¾Ð¿Ñ€Ð¾ÑÐ¸Ñ‚Ðµ ÐµÐ³Ð¾ Ð½Ð°Ð¿Ð¸ÑÐ°Ñ‚ÑŒ /start Ð±Ð¾Ñ‚Ñƒ.", reply_markup=menu_admin()
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
        await call.message.edit_text(f"âœ… {emp.full_name} Ð½Ð°Ð·Ð½Ð°Ñ‡ÐµÐ½ Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€Ð¾Ð¼.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Ð“Ð¾Ñ‚Ð¾Ð²Ð¾")


@router.callback_query(F.data.startswith("emp:mkmgr:"))
async def emp_mkmgr(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.manager; emp.is_active = True
        await session.commit()
        await call.message.edit_text(f"âœ… {emp.full_name} Ð½Ð°Ð·Ð½Ð°Ñ‡ÐµÐ½ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¼.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Ð“Ð¾Ñ‚Ð¾Ð²Ð¾")


@router.callback_query(F.data.startswith("emp:mkemp:"))
async def emp_mkemp(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.employee; emp.is_active = True
        await session.commit()
        await call.message.edit_text(f"âœ… {emp.full_name} ÑÐ½ÑÑ‚ Ñ Ð´Ð¾Ð»Ð¶Ð½Ð¾ÑÑ‚Ð¸ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾ (Ñ‚ÐµÐ¿ÐµÑ€ÑŒ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº).",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Ð“Ð¾Ñ‚Ð¾Ð²Ð¾")


@router.callback_query(F.data.startswith("emp:rmadmin:"))
async def emp_rmadmin(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.role = UserRole.employee
        await session.commit()
        await call.message.edit_text(f"âœ… {emp.full_name} Ñ‚ÐµÐ¿ÐµÑ€ÑŒ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Ð“Ð¾Ñ‚Ð¾Ð²Ð¾")


@router.callback_query(F.data.startswith("emp:delete:"))
async def emp_delete(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if emp:
        emp.is_active = False
        emp.role = UserRole.pending
        await session.commit()
        await call.message.edit_text(f"ðŸ—‘ {emp.full_name} Ð»Ð¸ÑˆÑ‘Ð½ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Ð£Ð´Ð°Ð»Ñ‘Ð½")


# â”€â”€â”€ Pending users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:pending")
async def adm_pending(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(
        select(User).where(User.role == UserRole.pending).order_by(User.created_at.desc())
    )
    pending = res.scalars().all()
    if not pending:
        await call.message.edit_text("ðŸ“¥ Ð—Ð°ÑÐ²Ð¾Ðº Ð½ÐµÑ‚.", reply_markup=kb_back())
        await call.answer(); return
    text = f"ðŸ“¥ <b>Ð—Ð°ÑÐ²ÐºÐ¸ ({len(pending)})</b>\n\n"
    for u in pending:
        text += f"â€¢ {u.full_name} (@{u.username or 'â€”'}) â€” <code>{u.telegram_id}</code>\n"
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
        name = u.display_name or u.full_name
        await call.message.edit_reply_markup()
        await call.message.answer(f"âœ… {name} Ð¾Ð´Ð¾Ð±Ñ€ÐµÐ½ ÐºÐ°Ðº Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº.")
        try:
            await bot.send_message(tg_id, "ðŸŽ‰ Ð’Ð°Ñˆ Ð´Ð¾ÑÑ‚ÑƒÐ¿ Ð¾Ð´Ð¾Ð±Ñ€ÐµÐ½! Ð’Ñ‹ Ñ‚ÐµÐ¿ÐµÑ€ÑŒ Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº. ÐÐ°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ /start")
        except Exception: pass
    await call.answer("ÐžÐ´Ð¾Ð±Ñ€ÐµÐ½Ð¾")


@router.callback_query(F.data.startswith("pending:mgr:"))
async def pending_approve_manager(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        u.role = UserRole.manager; u.is_active = True
        await session.commit()
        name = u.display_name or u.full_name
        await call.message.edit_reply_markup()
        await call.message.answer(f"âœ… {name} Ð¾Ð´Ð¾Ð±Ñ€ÐµÐ½ ÐºÐ°Ðº Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹.")
        try:
            await bot.send_message(tg_id, "ðŸŽ‰ Ð’Ð°Ñˆ Ð´Ð¾ÑÑ‚ÑƒÐ¿ Ð¾Ð´Ð¾Ð±Ñ€ÐµÐ½! Ð’Ñ‹ Ñ‚ÐµÐ¿ÐµÑ€ÑŒ Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹. ÐÐ°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ /start")
        except Exception: pass
    await call.answer("ÐžÐ´Ð¾Ð±Ñ€ÐµÐ½Ð¾")


@router.callback_query(F.data.startswith("pending:no:"))
async def pending_deny(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        await session.delete(u); await session.commit()
        await call.message.edit_reply_markup()
        await call.message.answer(f"ðŸ—‘ Ð—Ð°ÑÐ²ÐºÐ° Ð¾Ñ‚ {u.full_name} Ð¾Ñ‚ÐºÐ»Ð¾Ð½ÐµÐ½Ð°.")
        try:
            await bot.send_message(tg_id, "âŒ Ð’Ð°Ñˆ Ð·Ð°Ð¿Ñ€Ð¾Ñ Ð½Ð° Ð´Ð¾ÑÑ‚ÑƒÐ¿ Ð¾Ñ‚ÐºÐ»Ð¾Ð½Ñ‘Ð½.")
        except Exception: pass
    await call.answer("ÐžÑ‚ÐºÐ»Ð¾Ð½ÐµÐ½Ð¾")


# â”€â”€â”€ Employee City â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data.startswith("emp:setcity:"))
async def emp_setcity_prompt(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    await call.message.edit_text(
        "ðŸ™ <b>Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´ Ð´Ð»Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°:</b>\n"
        "Â«Ð¡Ð¿Ñ€Ð°ÑˆÐ¸Ð²Ð°Ñ‚ÑŒÂ» â€” Ð±Ð¾Ñ‚ Ð±ÑƒÐ´ÐµÑ‚ ÑÐ¿Ñ€Ð°ÑˆÐ¸Ð²Ð°Ñ‚ÑŒ Ð¿Ñ€Ð¸ ÐºÐ°Ð¶Ð´Ð¾Ð¼ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ðµ.",
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
        city_label = {"gomel": "Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ÐœÐ¸Ð½ÑÐº"}.get(city or "", "ÑÐ¿Ñ€Ð°ÑˆÐ¸Ð²Ð°Ñ‚ÑŒ")
        await call.message.edit_text(
            f"âœ… Ð“Ð¾Ñ€Ð¾Ð´ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ° <b>{emp.full_name}</b> ÑƒÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½: <b>{city_label}</b>",
            parse_mode="HTML", reply_markup=kb_back(f"emp:view:{tg_id}")
        )
    await call.answer("Ð¡Ð¾Ñ…Ñ€Ð°Ð½ÐµÐ½Ð¾")


@router.callback_query(F.data.startswith("emp:bindproj:"))
async def emp_bindproj_prompt(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    
    # Fetch all active projects
    res = await session.execute(select(Project).where(Project.is_active == True))
    projects = res.scalars().all()
    
    from bot.keyboards.builders import kb_projects_for_user_binding
    await call.message.edit_text(
        "ðŸ“ <b>ÐŸÑ€Ð¸Ð²ÑÐ·ÐºÐ° ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾ Ðº Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñƒ:</b>\n\n"
        "Ð•ÑÐ»Ð¸ Ð¿Ñ€Ð¾ÐµÐºÑ‚ Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½, ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹ Ð±ÑƒÐ´ÐµÑ‚ Ð²Ð¸Ð´ÐµÑ‚ÑŒ Ð¢ÐžÐ›Ð¬ÐšÐž ÑÑ‚Ð¾Ñ‚ Ð¿Ñ€Ð¾ÐµÐºÑ‚ "
        "Ð¿Ñ€Ð¸ ÑÐ´Ð°Ñ‡Ðµ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð² Ð¸ Ð²Ð²Ð¾Ð´Ðµ ÑƒÐ¿Ñ€. Ñ€Ð°ÑÑ…Ð¾Ð´Ð¾Ð².",
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
        proj_name = "ÐÐµÑ‚ Ð¿Ñ€Ð¸Ð²ÑÐ·ÐºÐ¸"
        if emp.project_id:
            pres = await session.execute(select(Project).where(Project.id == emp.project_id))
            p = pres.scalar_one_or_none()
            proj_name = p.name if p else "???"
            
        await call.message.edit_text(
            f"âœ… Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰Ð¸Ð¹ <b>{emp.full_name}</b> Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½ Ðº Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñƒ: <b>{proj_name}</b>",
            parse_mode="HTML", reply_markup=kb_back(f"emp:view:{tg_id}")
        )
    await call.answer("ÐŸÑ€Ð¸Ð²ÑÐ·Ð°Ð½Ð¾")


# â”€â”€â”€ Salary settings (legacy placeholder) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:salary")
async def adm_salary(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text(
        "â„¹ï¸ <b>Ð¨ÐºÐ°Ð»Ð° Ð—ÐŸ</b>\n\n"
        "ÐŸÑ€Ð°Ð²Ð¸Ð»Ð° Ñ€Ð°ÑÑ‡Ñ‘Ñ‚Ð° Ð·Ð°Ñ€Ð¿Ð»Ð°Ñ‚Ñ‹ Ñ„Ð¾Ñ‚Ð¾Ð³Ñ€Ð°Ñ„Ð¾Ð² Ð·Ð°Ñ„Ð¸ÐºÑÐ¸Ñ€Ð¾Ð²Ð°Ð½Ñ‹ Ð² ÑÐ¸ÑÑ‚ÐµÐ¼Ðµ:\n\n"
        "<b>Ð“Ð¾Ð¼ÐµÐ»ÑŒ ÐŸÐ½â€“ÐŸÑ‚:</b> Ð´Ð¾ 200 Ñ€ â†’ 25+10%; 200â€“300 â†’ 20%; >300 â†’ 22%\n"
        "<b>Ð“Ð¾Ð¼ÐµÐ»ÑŒ Ð¡Ð±:</b> Ð´Ð¾ 400 Ñ€ â†’ 25+10%; 400â€“800 â†’ 20%; >800 â†’ 22%\n"
        "<b>Ð“Ð¾Ð¼ÐµÐ»ÑŒ Ð’Ñ:</b> Ð´Ð¾ 350 Ñ€ â†’ 25+10%; 350â€“600 â†’ 20%; >600 â†’ 22%\n"
        "<b>ÐœÐ¸Ð½ÑÐº (Ð²ÑÐµ Ð´Ð½Ð¸):</b> Ð´Ð¾ 450 Ñ€ â†’ 45+10%; 450â€“1000 â†’ 20%; >1000 â†’ 22%\n\n"
        "ÐŸÑ€Ð¾Ñ†ÐµÐ½Ñ‚Ð½Ð°Ñ Ñ‡Ð°ÑÑ‚ÑŒ Ð´ÐµÐ»Ð¸Ñ‚ÑÑ Ð½Ð° Ñ‡Ð¸ÑÐ»Ð¾ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ¾Ð² Ð² ÑÐ¼ÐµÐ½Ðµ.",
        parse_mode="HTML", reply_markup=kb_back()
    )
    await call.answer()


# â”€â”€â”€ Manager Salary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

        lines = [f"ðŸ’¼ <b>Ð—ÐŸ ÐœÐµÐ½ÐµÐ´Ð¶ÐµÑ€Ð° â€” {today.strftime('%B %Y')}</b>\n"]

        if not plans:
            lines.append("âš ï¸ ÐÐµÑ‚ Ð°ÐºÑ‚Ð¸Ð²Ð½Ñ‹Ñ… Ð¼ÐµÑÑÑ‡Ð½Ñ‹Ñ… Ð¿Ð»Ð°Ð½Ð¾Ð².\nÐ”Ð¾Ð±Ð°Ð²ÑŒÑ‚Ðµ Ð¿Ð»Ð°Ð½ Ð² Ñ€Ð°Ð·Ð´ÐµÐ»Ðµ ðŸŽ¯ ÐŸÐ»Ð°Ð½Ñ‹ Ð¿Ñ€Ð¾Ð´Ð°Ð¶.")
        else:
            # Group plans by city for display
            plans_by_city = defaultdict(list)
            for p in plans:
                plans_by_city[p.city].append(p)
                
            sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))
            
            for city in sorted_cities:
                city_label = {"gomel": "ðŸ™ Ð“ÐžÐœÐ•Ð›Ð¬", "minsk": "ðŸŒ† ÐœÐ˜ÐÐ¡Ðš"}.get(city, "ðŸŒ ÐžÐ‘Ð©Ð˜Ð•")
                lines.append(f"<b>{city_label}</b>")
                
                for plan in plans_by_city[city]:
                    proj_label = plan.project_name or "Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹"
                    if plan.project_name:
                        actual = city_rev[city].get(plan.project_name, 0.0)
                    else:
                        actual = total_rev_by_city[city]
                        
                    salary, desc = calculate_manager_salary(float(actual), plan.plan_amount)
                    pct = (actual * 100 / plan.plan_amount) if plan.plan_amount else 0
                    bar = _progress_bar(pct)
                    lines.append(
                        f"ðŸª {proj_label}\n"
                        f"   ÐžÐ±Ð¾Ñ€Ð¾Ñ‚: <b>{actual:,.0f} Ñ€</b> / Ð¿Ð»Ð°Ð½ <b>{plan.plan_amount:,.0f} Ñ€</b>\n"
                        f"   {bar} <b>{pct:.1f}%</b>\n"
                        f"   {desc}\n"
                        f"   ðŸ’¸ Ð—ÐŸ: <b>{salary:,.2f} Ñ€</b>\n"
                    )
                lines.append("")

        await call.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML", reply_markup=kb_back()
        )
    except Exception as e:
        await call.message.answer(f"âŒ ÐžÑˆÐ¸Ð±ÐºÐ°: {html.escape(str(e))}")
    await call.answer()


@router.callback_query(F.data.startswith("sal:edit:"))
async def sal_edit_prompt(call: CallbackQuery, state: FSMContext):
    lvl_id = int(call.data.split(":")[2])
    await state.update_data(sal_edit_id=lvl_id)
    await state.set_state(AdminForm.sal_edit_values)
    await call.message.edit_text(
        "âœï¸ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð½Ð¾Ð²Ñ‹Ðµ Ð¿Ð°Ñ€Ð°Ð¼ÐµÑ‚Ñ€Ñ‹ ÑƒÑ€Ð¾Ð²Ð½Ñ Ð¾Ð´Ð½Ð¾Ð¹ ÑÑ‚Ñ€Ð¾ÐºÐ¾Ð¹:\n\n"
        "<code>Ð¼Ð¸Ð½_Ð¿Ð¾Ñ€Ð¾Ð³ Ð¼Ð°ÐºÑ_Ð¿Ð¾Ñ€Ð¾Ð³ Ð¾ÐºÐ»Ð°Ð´ Ð¿Ñ€Ð¾Ñ†ÐµÐ½Ñ‚</code>\n\n"
        "ÐŸÑ€Ð¸Ð¼ÐµÑ€: <code>0 15000 2500 10</code>\n"
        "Ð”Ð»Ñ Ð±ÐµÐ·Ð»Ð¸Ð¼Ð¸Ñ‚Ð½Ð¾Ð³Ð¾ Ð²ÐµÑ€Ñ…Ð½ÐµÐ³Ð¾ Ð¿Ð¾Ñ€Ð¾Ð³Ð° Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ 0:\n"
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
        await message.answer("âŒ Ð¤Ð¾Ñ€Ð¼Ð°Ñ‚: <code>Ð¼Ð¸Ð½ Ð¼Ð°ÐºÑ Ð¾ÐºÐ»Ð°Ð´ Ð¿Ñ€Ð¾Ñ†ÐµÐ½Ñ‚</code>", parse_mode="HTML")
        return
    d = await state.get_data()
    res = await session.execute(select(SalarySetting).where(SalarySetting.id == d["sal_edit_id"]))
    lvl = res.scalar_one_or_none()
    if lvl:
        lvl.threshold_min = tmin; lvl.threshold_max = tmax
        lvl.base_salary = base; lvl.percentage = pct / 100
        await session.commit()
        await message.answer("âœ… Ð£Ñ€Ð¾Ð²ÐµÐ½ÑŒ Ð—ÐŸ Ð¾Ð±Ð½Ð¾Ð²Ð»Ñ‘Ð½!", reply_markup=menu_admin())
    await state.clear()


# â”€â”€â”€ Plans â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
            "ðŸŽ¯ <b>ÐŸÐ»Ð°Ð½Ñ‹ Ð¿Ñ€Ð¾Ð´Ð°Ð¶</b>\n\nÐ—Ð´ÐµÑÑŒ Ð¼Ð¾Ð¶Ð½Ð¾ Ð½Ð°ÑÑ‚Ñ€Ð¾Ð¸Ñ‚ÑŒ Ñ†ÐµÐ»Ð¸ Ð¿Ð¾ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐµ Ð´Ð»Ñ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð¾Ð² Ð¸Ð»Ð¸ Ð¾Ð±Ñ‰Ð¸Ðµ.",
            parse_mode="HTML", reply_markup=kb_plans(by_city)
        )
    except Exception as e:
        await call.message.answer(f"âŒ ÐžÑˆÐ¸Ð±ÐºÐ°: {html.escape(str(e))}")
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
    await call.answer("Ð˜Ð·Ð¼ÐµÐ½ÐµÐ½Ð¾")


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
    await call.answer("ÐŸÐ»Ð°Ð½ ÑƒÐ´Ð°Ð»ÐµÐ½")


@router.callback_query(F.data == "plan:add")
async def plan_add_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.plan_city)
    from bot.keyboards.builders import kb_city
    # We use building keyboard for reports city selection as it is same
    await call.message.edit_text("ðŸ™ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´ Ð´Ð»Ñ Ð¿Ð»Ð°Ð½Ð°:", reply_markup=kb_city())
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
        "ðŸ“ <b>Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚</b> Ð´Ð»Ñ Ð¿Ð»Ð°Ð½Ð°:",
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
    await call.message.edit_text("ðŸ’° Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>ÑÑƒÐ¼Ð¼Ñƒ Ð¿Ð»Ð°Ð½Ð°</b> (â‚½):", parse_mode="HTML")
    await call.answer()


@router.message(AdminForm.plan_amount)
async def plan_add_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾:"); return
    await state.update_data(plan_amount=amount)
    await state.set_state(AdminForm.plan_period)
    await message.answer("ÐŸÐµÑ€Ð¸Ð¾Ð´ Ð¿Ð»Ð°Ð½Ð°: Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>Ð´ÐµÐ½ÑŒ</b> Ð¸Ð»Ð¸ <b>Ð¼ÐµÑÑÑ†</b>:", parse_mode="HTML")


@router.message(AdminForm.plan_period)
async def plan_add_period(message: Message, state: FSMContext, session: AsyncSession):
    txt = message.text.strip().lower()
    period = "day" if "Ð´ÐµÐ½ÑŒ" in txt or txt == "day" else "month"
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
    proj_str = d["plan_project"] or "Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹"
    period_str = "Ð´ÐµÐ½ÑŒ" if period == "day" else "Ð¼ÐµÑÑÑ†"
    await message.answer(
        f"âœ… ÐŸÐ»Ð°Ð½ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½: {proj_str} â€” {d['plan_amount']:.0f}â‚½ / {period_str}",
        reply_markup=menu_admin()
    )


# â”€â”€â”€ Plan stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                "ðŸ“ˆ <b>Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð¿Ð»Ð°Ð½Ð¾Ð²</b>\n\nÐÐºÑ‚Ð¸Ð²Ð½Ñ‹Ñ… Ð¿Ð»Ð°Ð½Ð¾Ð² Ð½ÐµÑ‚.\n"
                "Ð”Ð¾Ð±Ð°Ð²ÑŒÑ‚Ðµ Ð¸Ñ… Ð² Ñ€Ð°Ð·Ð´ÐµÐ»Ðµ ðŸŽ¯ ÐŸÐ»Ð°Ð½Ñ‹ Ð¿Ñ€Ð¾Ð´Ð°Ð¶.",
                parse_mode="HTML", reply_markup=kb_back()
            )
            await call.answer()
            return

        from collections import defaultdict
        plans_by_city = defaultdict(list)
        for p in plans:
            plans_by_city[p.city].append(p)

        lines = ["ðŸ“ˆ <b>Ð¡Ñ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ° Ð²Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¸Ñ Ð¿Ð»Ð°Ð½Ð¾Ð²</b>\n"]

        sorted_cities = sorted(plans_by_city.keys(), key=lambda x: (x is None, x != "gomel", x != "minsk"))

        for city in sorted_cities:
            city_label = {"gomel": "ðŸ™ Ð“ÐžÐœÐ•Ð›Ð¬", "minsk": "ðŸŒ† ÐœÐ˜ÐÐ¡Ðš"}.get(city, "ðŸŒ ÐžÐ‘Ð©Ð˜Ð•")
            lines.append(f"<b>{city_label}</b>")
            
            for plan in plans_by_city[city]:
                proj_label = plan.project_name or "Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹"
                period_label = "Ð´ÐµÐ½ÑŒ" if plan.period == "day" else "Ð¼ÐµÑÑÑ†"
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
                    f"ðŸŽ¯ {proj_label} ({period_label}):\n"
                    f"   {bar} <b>{pct:.1f}%</b> ({actual:,.0f} / {plan.plan_amount:,.0f} Ñ€)"
                )
            lines.append("")

        lines.append(f"\nðŸ—“ ÐŸÐ¾ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸ÑŽ Ð½Ð°: {today.strftime('%d.%m.%Y')}")

        await call.message.edit_text(
            "\n".join(lines),
            parse_mode="HTML",
            reply_markup=kb_back()
        )
    except Exception as e:
        await call.message.answer(f"âŒ ÐžÑˆÐ¸Ð±ÐºÐ°: {html.escape(str(e))}")
    await call.answer()


def _progress_bar(pct: float, width: int = 10) -> str:
    filled = min(int(pct / 100 * width), width)
    return "[" + "â–ˆ" * filled + "â–‘" * (width - filled) + "]"


# â”€â”€â”€ Debt / Payroll REMOVED (as requested) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€





# â”€â”€â”€ Analytics / Charts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "adm:analytics")
async def adm_analytics(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("ðŸ“Š <b>ÐÐ½Ð°Ð»Ð¸Ñ‚Ð¸ÐºÐ° Ð¸ Ð“Ñ€Ð°Ñ„Ð¸ÐºÐ¸</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:",
                                 parse_mode="HTML", reply_markup=kb_analytics_cities())
    await call.answer()


@router.callback_query(F.data.startswith("chart_city:"))
async def analytics_city_select(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[1]
    city_lbl = {"gomel": "Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ÐœÐ¸Ð½ÑÐº", "all": "Ð’ÑÐµ Ð³Ð¾Ñ€Ð¾Ð´Ð°"}.get(city, city.title())
    await call.message.edit_text(f"ðŸ“Š <b>ÐÐ½Ð°Ð»Ð¸Ñ‚Ð¸ÐºÐ° Ð¸ Ð“Ñ€Ð°Ñ„Ð¸ÐºÐ¸ â€” {city_lbl}</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ‚Ð¸Ð¿ Ð²Ð¸Ð·ÑƒÐ°Ð»Ð¸Ð·Ð°Ñ†Ð¸Ð¸:",
                                 parse_mode="HTML", reply_markup=kb_analytics(city))
    await call.answer()


@router.callback_query(F.data.startswith("chart:revenue:"))
async def chart_revenue(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    city_val = None if city == "all" else city
    await call.message.edit_text("â³ Ð“ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÑŽ Ð³Ñ€Ð°Ñ„Ð¸Ðº Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ¸â€¦")
    
    buf = await generate_revenue_chart(session, days=30, city=city_val)
    if not buf:
        await call.message.edit_text("âŒ ÐÐµÑ‚ Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð´Ð»Ñ Ð¿Ð¾ÑÑ‚Ñ€Ð¾ÐµÐ½Ð¸Ñ Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ°.", reply_markup=kb_analytics(city))
        return
    
    city_lbl = f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="revenue.png"),
        caption=f"ðŸ“ˆ <b>Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ° Ð·Ð° Ð¿Ð¾ÑÐ»ÐµÐ´Ð½Ð¸Ðµ 30 Ð´Ð½ÐµÐ¹{city_lbl}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, f"ÐŸÑ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ° Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ¸ {city}")
    await call.answer()


@router.callback_query(F.data.startswith("chart:revenue_year:"))
async def chart_revenue_year(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    city_val = None if city == "all" else city
    await call.message.edit_text("â³ Ð“ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÑŽ Ð³Ð¾Ð´Ð¾Ð²Ð¾Ð¹ Ð³Ñ€Ð°Ñ„Ð¸Ðºâ€¦")
    
    buf = await generate_yearly_revenue_chart(session, city=city_val)
    if not buf:
        await call.message.edit_text("âŒ ÐÐµÑ‚ Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð´Ð»Ñ Ð¿Ð¾ÑÑ‚Ñ€Ð¾ÐµÐ½Ð¸Ñ Ð³Ð¾Ð´Ð¾Ð²Ð¾Ð³Ð¾ Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ°.", reply_markup=kb_analytics(city))
        return
    
    city_lbl = f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="revenue_year.png"),
        caption=f"ðŸ“Š <b>Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ° Ð¿Ð¾ Ð¼ÐµÑÑÑ†Ð°Ð¼ Ð·Ð° {date.today().year} Ð³Ð¾Ð´{city_lbl}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, f"ÐŸÑ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ Ð³Ð¾Ð´Ð¾Ð²Ð¾Ð³Ð¾ Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ° Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ¸ {city}")
    await call.answer()


@router.callback_query(F.data.startswith("chart:plans:"))
async def chart_plans(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    city_val = None if city == "all" else city
    await call.message.edit_text("â³ Ð“ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÑŽ Ð³Ñ€Ð°Ñ„Ð¸Ðº Ð²Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¸Ñ Ð¿Ð»Ð°Ð½Ð¾Ð²â€¦")
    
    buf = await generate_plan_performance_chart(session, city=city_val)
    if not buf:
        await call.message.edit_text("âŒ ÐÐµÑ‚ Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ð¾ Ð¿Ð»Ð°Ð½Ð°Ð¼ Ð¿Ñ€Ð¾Ð´Ð°Ð¶.", reply_markup=kb_analytics(city))
        return
    
    city_lbl = f" ({city_val.title()})" if city_val else ""
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="plans.png"),
        caption=f"ðŸŽ¯ <b>Ð’Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¸Ðµ Ð¿Ð»Ð°Ð½Ð¾Ð² Ð¿Ñ€Ð¾Ð´Ð°Ð¶{city_lbl}</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, f"ÐŸÑ€Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ Ð³Ñ€Ð°Ñ„Ð¸ÐºÐ° Ð¿Ð»Ð°Ð½Ð¾Ð² {city}")
    await call.answer()


# â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _parse_date(text: str) -> date:
    from datetime import datetime
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()


# â”€â”€â”€ Monthly Calendar Report â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "period:monthly_calendar")
async def period_monthly_calendar(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text(
        "ðŸ“… <b>ÐœÐµÑÑÑ‡Ð½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:",
        parse_mode="HTML",
        reply_markup=kb_monthly_report_cities()
    )
    await call.answer()


@router.callback_query(F.data.startswith("period:monthly_city:"))
async def monthly_city_select(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    city = call.data.split(":")[2]
    today = date.today()
    city_lbl = {"gomel": "Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ÐœÐ¸Ð½ÑÐº", "all": "Ð’ÑÐµ Ð³Ð¾Ñ€Ð¾Ð´Ð°"}.get(city, city.title())
    await call.message.edit_text(
        f"ðŸ“… <b>ÐœÐµÑÑÑ‡Ð½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ â€” {city_lbl}</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¼ÐµÑÑÑ†:",
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
    await call.message.edit_text(f"â³ Ð“ÐµÐ½ÐµÑ€Ð¸Ñ€ÑƒÑŽ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ Ð·Ð° {month_name}{city_lbl}â€¦")
    
    try:
        data = await generate_monthly_calendar(session, year, month, city=city)
        fname = f"report_{city}_{year}-{month:02d}.xlsx"
        await call.message.answer_document(
            BufferedInputFile(data, filename=fname),
            caption=f"ðŸ“… ÐœÐµÑÑÑ‡Ð½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚: <b>{month_name}</b>{city_lbl}",
            parse_mode="HTML",
            reply_markup=menu_admin()
        )
        await call.message.delete()
    except Exception as e:
        import traceback
        traceback.print_exc()
        await call.message.answer(f"âŒ ÐžÑˆÐ¸Ð±ÐºÐ° Ð³ÐµÐ½ÐµÑ€Ð°Ñ†Ð¸Ð¸: {html.quote(str(e))}\n\nÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ Ð»Ð¾Ð³Ð¸ ÑÐµÑ€Ð²ÐµÑ€Ð°.", reply_markup=menu_admin())
    await call.answer()


# â”€â”€â”€ Management Expenses (Ð Ð°ÑÑ…Ð¾Ð´Ð½Ð¸Ðº / ÐÑ€ÐµÐ½Ð´Ð° / Ð¢ÐµÑ…Ð½Ð¸ÐºÐ°) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                f"ðŸ“‚ <b>Ð£Ð¿Ñ€. Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹ â€” {proj.name} ({proj.city})</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑŽ:",
                parse_mode="HTML", reply_markup=kb_mgmt_categories(is_admin=is_admin)
            )
            await call.answer(); return

    await state.set_state(AdminForm.mgmt_city)
    from bot.keyboards.builders import kb_city
    await call.message.edit_text("ðŸ™ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´ Ð´Ð»Ñ Ñ€Ð°ÑÑ…Ð¾Ð´Ð°:", reply_markup=kb_city())
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
    b.button(text="ðŸŒ Ð”Ð»Ñ Ð²ÑÐµÑ… Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð¾Ð²", callback_data="mgmt:proj:all")
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data="adm:mgmt_expenses")
    b.adjust(1)

    await state.set_state(AdminForm.mgmt_project)
    await call.message.edit_text(
        "ðŸ“ <b>Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚</b>, Ðº ÐºÐ¾Ñ‚Ð¾Ñ€Ð¾Ð¼Ñƒ Ð¾Ñ‚Ð½Ð¾ÑÐ¸Ñ‚ÑÑ Ñ€Ð°ÑÑ…Ð¾Ð´,\n"
        "Ð¸Ð»Ð¸ Ð²Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Â«Ð”Ð»Ñ Ð²ÑÐµÑ… Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð¾Ð²Â»:",
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
    await call.message.edit_text("ðŸ“‚ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑŽ Ñ€Ð°ÑÑ…Ð¾Ð´Ð°:", reply_markup=kb_mgmt_categories(is_admin=is_admin))
    await call.answer()


@router.callback_query(AdminForm.mgmt_category, F.data.startswith("mgmt:cat:"))
async def mgmt_category_select(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[2]
    await state.update_data(mgmt_category=cat)
    await state.set_state(AdminForm.mgmt_date)
    
    if cat == "Ð°Ñ€ÐµÐ½Ð´Ð°":
        from bot.keyboards.builders import kb_mgmt_month_select
        today = date.today()
        await call.message.edit_text(
            "ðŸ  <b>ÐÑ€ÐµÐ½Ð´Ð°</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¼ÐµÑÑÑ†, Ð·Ð° ÐºÐ¾Ñ‚Ð¾Ñ€Ñ‹Ð¹ Ð²Ð½Ð¾ÑÐ¸Ñ‚ÑÑ Ð¾Ð¿Ð»Ð°Ñ‚Ð°:",
            parse_mode="HTML",
            reply_markup=kb_mgmt_month_select(today.year, today.month)
        )
    else:
        from bot.keyboards.builders import kb_use_today
        today_str = date.today().strftime("%d.%m.%Y")
        await call.message.edit_text(
            f"ðŸ“… ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ: <b>{cat}</b>\nÐ’Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>Ð´Ð°Ñ‚Ñƒ</b> Ñ€Ð°ÑÑ…Ð¾Ð´Ð° (Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“):",
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
        await message.answer("âŒ ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚. Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“:"); return
    await state.update_data(mgmt_date=d.isoformat())
    await mgmt_ask_amount(message, state)


async def mgmt_ask_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    cat = data.get("mgmt_category", "Ñ€Ð°ÑÑ…Ð¾Ð´")
    await state.set_state(AdminForm.mgmt_amount)
    await message.answer(f"ðŸ’° Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>ÑÑƒÐ¼Ð¼Ñƒ</b> ({cat}):", parse_mode="HTML", reply_markup=kb_back())


# Handler removed as logic moved upstream


@router.message(AdminForm.mgmt_amount)
async def mgmt_amount_input(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip().replace(" ", "").replace(",", "."))
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾:"); return
    await state.update_data(mgmt_amount=v)
    await state.set_state(AdminForm.mgmt_comment)
    from bot.keyboards.builders import kb_cancel_skip
    await message.answer("ðŸ’¬ Ð”Ð¾Ð±Ð°Ð²ÑŒÑ‚Ðµ ÐºÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹ (Ð¸Ð»Ð¸ Ð¿Ñ€Ð¾Ð¿ÑƒÑÑ‚Ð¸Ñ‚Ðµ):", reply_markup=kb_cancel_skip())


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
    await log_action(session, db_user.id, "Ð”Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ ÑƒÐ¿Ñ€Ð°Ð²Ð». Ñ€Ð°ÑÑ…Ð¾Ð´", f"{d['mgmt_category']}: {d['mgmt_amount']} Ñ€")
    await session.commit()
    
    kb = menu_admin() if db_user.role == UserRole.admin else menu_manager()
    await message.answer("âœ… Ð£Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ñ‡ÐµÑÐºÐ¸Ð¹ Ñ€Ð°ÑÑ…Ð¾Ð´ ÑÐ¾Ñ…Ñ€Ð°Ð½Ñ‘Ð½!", reply_markup=kb)


# â”€â”€â”€ Manager Panel â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.message(F.text == "âš™ï¸ ÐŸÐ°Ð½ÐµÐ»ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾")
async def show_manager_panel(message: Message, db_user: User):
    if not _require_admin_or_manager(db_user):
        await message.answer("â›” ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°.")
        return
    await message.answer(
        "âš™ï¸ <b>ÐŸÐ°Ð½ÐµÐ»ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ€Ð°Ð·Ð´ÐµÐ»:",
        parse_mode="HTML",
        reply_markup=_kb_manager_main()
    )


@router.callback_query(F.data == "mgr:panel")
async def mgr_panel_callback(call: CallbackQuery, db_user: User):
    if not _require_admin_or_manager(db_user): return
    await call.message.edit_text(
        "âš™ï¸ <b>ÐŸÐ°Ð½ÐµÐ»ÑŒ ÑƒÐ¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ñ€Ð°Ð·Ð´ÐµÐ»:",
        parse_mode="HTML",
        reply_markup=_kb_manager_main()
    )
    await call.answer()

def _kb_manager_main() -> InlineKeyboardMarkup:
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    b.button(text="ðŸ“Š ÐžÑ‚Ñ‡Ñ‘Ñ‚Ñ‹",           callback_data="adm:reports")
    b.button(text="ðŸ“‹ ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð¾Ð²", callback_data="review:list:0")
    b.button(text="ðŸ“ˆ ÐœÐ¾Ñ Ð—ÐŸ",            callback_data="mgr:my_salary")
    b.button(text="ðŸ“‚ Ð£Ð¿Ñ€Ð°Ð²Ð». Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹",    callback_data="mgr:mgmt_start")
    b.adjust(1)
    return b.as_markup()


# â”€â”€â”€ Manager Mgmt Expenses (Separate Flow) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "mgr:mgmt_start")
async def mgr_mgmt_start(call: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext):
    if not db_user.role.value == "manager": return
    if not db_user.project_id:
        return await call.answer("âŒ Ð’Ñ‹ Ð½Ðµ Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½Ñ‹ Ðº Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñƒ.", show_alert=True)
    
    await state.clear()
    res = await session.execute(select(Project).where(Project.id == db_user.project_id))
    proj = res.scalar_one_or_none()
    if not proj:
        return await call.answer("âŒ ÐŸÑ€Ð¾ÐµÐºÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½.", show_alert=True)

    await state.update_data(mgmt_city=proj.city, mgmt_project_id=proj.id, mgmt_project=proj.name)
    await state.set_state(ManagerMgmtForm.date)
    
    from bot.keyboards.builders import kb_mgmt_date
    t = date.today().strftime("%d.%m.%Y")
    y = (date.today() - timedelta(days=1)).strftime("%d.%m.%Y")
    await call.message.edit_text(
        f"ðŸ“‚ <b>Ð£Ð¿Ñ€. Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹ â€” {proj.name} ({proj.city})</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð´Ð°Ñ‚Ñƒ:",
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
    proj_name = data.get("mgmt_project", "ÐŸÑ€Ð¾ÐµÐºÑ‚")
    
    from bot.keyboards.builders import kb_mgmt_categories_mgr
    await call.message.edit_text(
        f"ðŸ“‚ <b>Ð£Ð¿Ñ€. Ñ€Ð°ÑÑ…Ð¾Ð´Ñ‹ â€” {proj_name}</b>\nðŸ“… Ð”Ð°Ñ‚Ð°: <b>{d_val.strftime('%d.%m.%Y')}</b>\n\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ ÐºÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸ÑŽ:",
        parse_mode="HTML", reply_markup=kb_mgmt_categories_mgr()
    )
    await call.answer()


@router.callback_query(ManagerMgmtForm.category, F.data.startswith("mgr:mgmt:cat:"))
async def mgr_mgmt_cat_select(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[3]
    await state.update_data(mgmt_category=cat)
    await state.set_state(ManagerMgmtForm.amount)
    await call.message.edit_text(f"ðŸ’° ÐšÐ°Ñ‚ÐµÐ³Ð¾Ñ€Ð¸Ñ: <b>{cat}</b>\n\nÐ’Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÑÑƒÐ¼Ð¼Ñƒ (Ñ‡Ð¸ÑÐ»Ð¾):", parse_mode="HTML")
    await call.answer()


@router.message(ManagerMgmtForm.amount)
async def mgr_mgmt_amount_input(message: Message, state: FSMContext):
    try:
        v = float(message.text.replace(',', '.').strip())
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾:"); return
    await state.update_data(mgmt_amount=v)
    await state.set_state(ManagerMgmtForm.comment)
    from bot.keyboards.builders import kb_cancel_skip
    await message.answer("ðŸ’¬ Ð”Ð¾Ð±Ð°Ð²ÑŒÑ‚Ðµ ÐºÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹ (Ð¸Ð»Ð¸ Ð¿Ñ€Ð¾Ð¿ÑƒÑÑ‚Ð¸Ñ‚Ðµ):", reply_markup=kb_cancel_skip("mgr:mgmt_start"))


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
        if call: return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°", show_alert=True)
        return await message.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°")

    # Manager must be bound to a project to see reports
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and not db_user.project_id:
        txt = "âš ï¸ Ð—Ð° Ð²Ð°Ð¼Ð¸ Ð½Ðµ Ð·Ð°ÐºÑ€ÐµÐ¿Ð»ÐµÐ½ Ð¿Ñ€Ð¾ÐµÐºÑ‚. ÐŸÑ€Ð¾Ð²ÐµÑ€ÐºÐ° Ð¾Ñ‚Ñ‡ÐµÑ‚Ð¾Ð² Ð½ÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð°."
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
        txt = "âœ… Ð’ÑÐµ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ñ‹Ðµ Ð¾Ñ‚Ñ‡ÐµÑ‚Ñ‹ Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐµÐ½Ñ‹!"
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
        btn_text = f"â³ {date_str} | {proj_short} | {r.revenue:,.0f} â‚½"
        b.button(text=btn_text, callback_data=f"review:view:{r.id}")
    
    b.adjust(1)
    
    b.adjust(1)
    
    # Paging buttons
    nav_btns = []
    if page > 0:
        nav_btns.append(InlineKeyboardButton(text="â¬…ï¸ ÐŸÑ€ÐµÐ´.", callback_data=f"review:list:{page-1}"))
    if end < total:
        nav_btns.append(InlineKeyboardButton(text="Ð¡Ð»ÐµÐ´. âž¡ï¸", callback_data=f"review:list:{page+1}"))
    if nav_btns:
        b.row(*nav_btns)

    # Back button
    back_cb = "adm:back" if db_user.role == UserRole.admin else "mgr:panel"
    b.row(InlineKeyboardButton(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data=back_cb))
    
    txt = f"ðŸ“‹ <b>ÐÐµÐ¿Ñ€Ð¾Ð²ÐµÑ€ÐµÐ½Ð½Ñ‹Ðµ Ð¾Ñ‚Ñ‡ÐµÑ‚Ñ‹ (Ð’ÑÐµÐ³Ð¾: {total}):</b>\nÐ¡Ñ‚Ñ€. {page+1} Ð¸Ð· {(total-1)//limit + 1}"
    if call:
        await call.message.edit_text(txt, parse_mode="HTML", reply_markup=b.as_markup())
        await call.answer()
    else:
        await message.answer(txt, parse_mode="HTML", reply_markup=b.as_markup())


@router.callback_query(F.data.startswith("review:view:"))
async def review_view(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if not r:
        return await call.answer("ÐžÑ‚Ñ‡ÐµÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½", show_alert=True)

    # Format similar to confirming report
    city_label = r.city or "â€”"
    text = (
        f"ðŸ“‹ <b>Ð”ÐµÑ‚Ð°Ð»Ð¸ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð° #{r.id}</b>\n\n"
        f"ðŸ“… Ð”Ð°Ñ‚Ð°:              <b>{r.date.strftime('%d.%m.%Y')}</b>\n"
        f"ðŸ™ Ð“Ð¾Ñ€Ð¾Ð´:              <b>{city_label}</b>\n"
        f"ðŸŽª ÐŸÑ€Ð¾ÐµÐºÑ‚:            <b>{r.project_name}</b>\n"
        f"ðŸ‘¤ Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº:         <b>{r.employee_name}</b>\n"
        f"ðŸ‘¥ Ð§ÐµÐ». Ð² ÑÐ¼ÐµÐ½Ðµ:      <b>{r.shift_count}</b>\n\n"
        f"ðŸ’° Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ°:           <b>{r.revenue:,.0f} â‚½</b>\n"
        f"ðŸ’µ ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ:          <b>{r.cash:,.0f} â‚½</b>\n"
        f"ðŸ’³ Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³:         <b>{r.acquiring:,.0f} â‚½</b>\n"
        f"ðŸ“‰ Ð¥Ð¾Ð· Ñ€Ð°ÑÑ…Ð¾Ð´:        <b>{r.expense:,.0f} â‚½</b>\n"
        f"ðŸ§‘â€ðŸŽ“ Ð—ÐŸ ÑÑ‚Ð°Ð¶ÐµÑ€Ð°:       <b>{r.trainee_salary:,.0f} â‚½</b>\n"
        f"ðŸ– ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº Ð² ÐºÐ°ÑÑÐµ:   <b>{r.cash_balance:,.0f} â‚½</b>\n"
        f"ðŸ‘£ ÐŸÐ¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»Ð¸:        <b>{r.visitors}</b>\n"
        f"ðŸŽ‚ Ð”Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹:     <b>{r.birthdays}</b>\n"
        f"ðŸ’¬ ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹:       <b>{r.comment or 'â€”'}</b>\n\n"
        f"Ð¤Ð°ÐºÑ‚Ð¸Ñ‡ÐµÑÐºÐ°Ñ Ð—ÐŸ ÑÐ¼ÐµÐ½Ñ‹: {_fmt(r.salary_paid)} â‚½\n"
    )

    is_admin = db_user.role == UserRole.admin
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_report_review(r.id, is_admin=is_admin))
    await call.answer()


@router.callback_query(F.data.startswith("review:ok:"))
async def review_ok(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if r:
        r.is_reviewed = True
        r.reviewed_by_id = db_user.id
        await session.commit()
        await call.answer("ÐžÑ‚Ñ‡ÐµÑ‚ Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐµÐ½!", show_alert=True)
        # return to tree
        await review_list(call, session, db_user)
    else:
        await call.answer("ÐžÑˆÐ¸Ð±ÐºÐ°, Ð¾Ñ‚Ñ‡ÐµÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½")


@router.callback_query(F.data.startswith("review:edit:"))
async def review_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin(db_user):
        return await call.answer("Ð¢Ð¾Ð»ÑŒÐºÐ¾ Ð´Ð»Ñ Ð°Ð´Ð¼Ð¸Ð½Ð¾Ð²")

    report_id = int(call.data.split(":")[2])
    res = await session.execute(select(Report).where(Report.id == report_id))
    r = res.scalar_one_or_none()
    if not r:
        return await call.answer("ÐžÑ‚Ñ‡ÐµÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½")

    await state.clear()
    # Load all data into state
    await state.update_data(
        admin_editing_report_id=r.id,
        date=r.date.isoformat(),
        project=r.project_name,
        project_id=r.project_id,
        city=r.city,
        employee_name=r.employee_name,
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
        f"ðŸ›  <b>Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ðµ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð° #{r.id}</b>\n(Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº: {r.employee_name}, Ð”Ð°Ñ‚Ð°: {r.date.strftime('%d.%m.%Y')})\n\n"
        "Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ð¾Ð»Ðµ Ð´Ð»Ñ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ:",
        parse_mode="HTML", reply_markup=kb_edit_fields()
    )
    await call.answer()

# â”€â”€â”€ MY SALARY (MANAGER) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "mgr:my_salary")
async def mgr_my_salary(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°")

    # Managers MUST be bound to a project
    role_val = db_user.role.value if hasattr(db_user.role, "value") else str(db_user.role)
    if role_val == "manager" and not db_user.project_id:
        await call.message.edit_text("âš ï¸ Ð’Ñ‹ Ð½Ðµ Ð¿Ñ€Ð¸Ð²ÑÐ·Ð°Ð½Ñ‹ Ðº ÐºÐ¾Ð½ÐºÑ€ÐµÑ‚Ð½Ð¾Ð¼Ñƒ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñƒ. ÐŸÐ¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð°, Ð¾Ð±Ñ€Ð°Ñ‚Ð¸Ñ‚ÐµÑÑŒ Ðº Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€Ñƒ Ð´Ð»Ñ Ð½Ð°Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ñ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°.", reply_markup=kb_back("mgr:panel"))
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
        await call.message.edit_text("â„¹ï¸ Ð”Ð»Ñ Ð²Ð°ÑˆÐµÐ³Ð¾ Ð¿Ñ€Ð¾Ñ„Ð¸Ð»Ñ/Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾ Ð°ÐºÑ‚Ð¸Ð²Ð½Ñ‹Ñ… Ð¿Ð»Ð°Ð½Ð¾Ð² Ð½Ð° ÑÑ‚Ð¾Ñ‚ Ð¼ÐµÑÑÑ†.", reply_markup=kb_back(back_cb))
        await call.answer()
        return

    today = date.today()
    start_of_month = today.replace(day=1)

    lines = [f"ðŸ’¼ <b>Ð’Ð°ÑˆÐ° Ð—ÐŸ (ÐºÐ°Ðº Ð£Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‰ÐµÐ³Ð¾) Ð·Ð° {today.strftime('%m.%Y')}</b>\n"]
    total_salary = 0.0

    for plan in plans:
        project_name = plan.project_name or "Ð’ÑÐµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ñ‹"
        city_lbl = plan.city or "Ð’ÑÐµ Ð³Ð¾Ñ€Ð¾Ð´Ð°"
        
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
        lines.append(f"ðŸŽ¯ <b>ÐŸÐ»Ð°Ð½ ({city_lbl} | {project_name}):</b> {_fmt(plan.plan_amount)} â‚½")
        lines.append(f"ðŸ’° Ð¤Ð°ÐºÑ‚: {_fmt(actual)} â‚½")
        lines.append(f"ðŸ“Š {desc}")
        lines.append(f"ðŸ’µ <b>Ðš Ð²Ñ‹Ð¿Ð»Ð°Ñ‚Ðµ: {_fmt(salary)}</b> â‚½\n")

    lines.append(f"â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€")
    lines.append(f"ðŸ† <b>Ð˜Ñ‚Ð¾Ð³Ð¾ Ð²Ð°ÑˆÐ° Ð—ÐŸ: {_fmt(total_salary)} â‚½</b>")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b = InlineKeyboardBuilder()
    back_cb = "adm:manager_salary" if db_user.role.value == "admin" else "mgr:panel"
    b.button(text="â—€ï¸ ÐÐ°Ð·Ð°Ð´", callback_data=back_cb)

    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=b.as_markup())
    await call.answer()



# â”€â”€â”€ Report Rejection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data.startswith("review:reject_start:"))
async def review_reject_start(call: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    if not _require_admin_or_manager(db_user):
        return await call.answer("ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°")

    report_id = int(call.data.split(":")[2])
    await state.update_data(reject_report_id=report_id)
    await state.set_state(AdminForm.reject_reason)
    
    await call.message.answer(
        "ðŸ“ <b>ÐŸÑ€Ð¸Ñ‡Ð¸Ð½Ð° Ð¾Ñ‚ÐºÐ»Ð¾Ð½ÐµÐ½Ð¸Ñ</b>\n\nÐ’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¸Ñ‡Ð¸Ð½Ñƒ (ÐµÑ‘ ÑƒÐ²Ð¸Ð´Ð¸Ñ‚ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº).\n"
        "ÐÐ°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: <i>Â«ÐÐµÐ²ÐµÑ€Ð½Ð¾ ÑƒÐºÐ°Ð·Ð°Ð½Ð° Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ° Ð¿Ð¾ Ð±ÐµÐ·Ð½Ð°Ð»ÑƒÂ»</i>",
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
        await message.answer("ÐžÑˆÐ¸Ð±ÐºÐ°: ID Ð¾Ñ‚Ñ‡ÐµÑ‚Ð° Ð¿Ð¾Ñ‚ÐµÑ€ÑÐ½. ÐÐ°Ñ‡Ð½Ð¸Ñ‚Ðµ ÑÐ½Ð°Ñ‡Ð°Ð»Ð°.")
        return

    # 1. Find report and employee
    res = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    r = res.scalar_one_or_none()
    
    if not r:
        await message.answer("âŒ ÐžÑ‚Ñ‡ÐµÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½ (Ð²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾, ÑƒÐ¶Ðµ ÑƒÐ´Ð°Ð»ÐµÐ½).")
        return

    emp_id = r.user_id
    date_str = r.date.strftime("%d.%m.%Y")
    proj_name = r.project_name

    # 2. Notify employee
    try:
        notify_text = (
            f"âš ï¸ <b>Ð’Ð°Ñˆ Ð¾Ñ‚Ñ‡ÐµÑ‚ Ð¾Ñ‚ÐºÐ»Ð¾Ð½Ñ‘Ð½!</b>\n\n"
            f"ðŸ“… Ð”Ð°Ñ‚Ð°: {date_str}\n"
            f"ðŸŽª ÐŸÑ€Ð¾ÐµÐºÑ‚: {proj_name}\n"
            f"ðŸ’¬ ÐŸÑ€Ð¸Ñ‡Ð¸Ð½Ð°: <i>{reason}</i>\n\n"
            f"ÐŸÐ¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð°, <b>ÑÐ´Ð°Ð¹Ñ‚Ðµ Ð¾Ñ‚Ñ‡ÐµÑ‚ Ð·Ð°Ð½Ð¾Ð²Ð¾</b> Ñ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ñ‹Ð¼Ð¸ Ð´Ð°Ð½Ð½Ñ‹Ð¼Ð¸."
        )
        await bot.send_message(emp_id, notify_text, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to notify employee {emp_id}: {e}")

    # 3. Delete report
    await session.delete(r)
    await log_action(session, db_user.id, "ÐžÑ‚ÐºÐ»Ð¾Ð½Ð¸Ð» Ð¾Ñ‚Ñ‡ÐµÑ‚", f"ID {report_id}, ÐŸÑ€Ð¸Ñ‡Ð¸Ð½Ð°: {reason}")
    await session.commit()

    await message.answer(f"âœ… ÐžÑ‚Ñ‡ÐµÑ‚ #{report_id} ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ Ð¾Ñ‚ÐºÐ»Ð¾Ð½ÐµÐ½. Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº ÑƒÐ²ÐµÐ´Ð¾Ð¼Ð»ÐµÐ½.")
    
    # Return to panel
    if db_user.role == UserRole.admin:
        await show_admin_panel(message, db_user, state)
    else:
        await show_manager_panel(message, db_user)


# â”€â”€â”€ Projects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        "ðŸ¢ <b>Ð£Ð¿Ñ€Ð°Ð²Ð»ÐµÐ½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°Ð¼Ð¸</b>\n\nÐ—Ð´ÐµÑÑŒ Ð²Ñ‹ Ð¼Ð¾Ð¶ÐµÑ‚Ðµ Ð´Ð¾Ð±Ð°Ð²Ð»ÑÑ‚ÑŒ Ð½Ð¾Ð²Ñ‹Ðµ Ð¼ÐµÑÑ‚Ð° Ñ€Ð°Ð±Ð¾Ñ‚Ñ‹.",
        parse_mode="HTML", reply_markup=kb_projects(by_city)
    )
    await call.answer()


@router.callback_query(F.data.startswith("proj:view:"))
async def proj_view(call: CallbackQuery, session: AsyncSession):
    proj_id = int(call.data.split(":")[2])
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if not p: return await call.answer("ÐÐµ Ð½Ð°Ð¹Ð´ÐµÐ½")
    
    city_str = {"gomel": "ðŸ™ Ð“Ð¾Ð¼ÐµÐ»ÑŒ", "minsk": "ðŸŒ† ÐœÐ¸Ð½ÑÐº"}.get(p.city, p.city)
    status = "âœ… ÐÐºÑ‚Ð¸Ð²ÐµÐ½" if p.is_active else "â¸ ÐŸÑ€Ð¸Ð¾ÑÑ‚Ð°Ð½Ð¾Ð²Ð»ÐµÐ½"
    text = (
        f"ðŸ¢ <b>ÐŸÑ€Ð¾ÐµÐºÑ‚: {p.name}</b>\n"
        f"ðŸ™ Ð“Ð¾Ñ€Ð¾Ð´: {city_str}\n"
        f"ðŸ“Š Ð¡Ñ‚Ð°Ñ‚ÑƒÑ: {status}"
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
    await call.message.edit_text("ðŸ™ Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´ Ð´Ð»Ñ Ð½Ð¾Ð²Ð¾Ð³Ð¾ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.proj_city)
async def proj_add_city(call: CallbackQuery, state: FSMContext, db_user: User):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        return await adm_back(call, db_user, state)
        
    await state.update_data(proj_city=city)
    await state.set_state(AdminForm.proj_name)
    await call.message.edit_text("ðŸ“ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ <b>Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b> (Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: Ð¡Ð°Ð´Ð¸Ðº â„–5):", 
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
    
    await message.answer(f"âœ… ÐŸÑ€Ð¾ÐµÐºÑ‚ Â«{name}Â» Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½!", reply_markup=menu_admin())

@router.message(Command("setproj"))
async def debug_set_proj(message: Message, session: AsyncSession, db_user: User):
    if message.from_user.id != 786320574: return
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("âŒ Usage: `/setproj <proj_id> [user_tg_id]`", parse_mode="Markdown")
    try:
        proj_id = int(args[1])
        target_id = int(args[2]) if len(args) > 2 else db_user.telegram_id
    except ValueError:
        return await message.answer("âŒ IDs must be numbers.")
    if proj_id != 0:
        res = await session.execute(select(Project).where(Project.id == proj_id))
        proj = res.scalar_one_or_none()
        if not proj: return await message.answer(f"âŒ Project ID {proj_id} not found.")
    res = await session.execute(select(User).where(User.telegram_id == target_id))
    target_user = res.scalar_one_or_none()
    if not target_user: return await message.answer(f"âŒ User with TG ID {target_id} not found.")
    target_user.project_id = proj_id if proj_id != 0 else None
    await session.commit()
    proj_name = proj.name if proj_id != 0 else "None"
    await message.answer(f"âœ… User {target_user.full_name} ({target_id}) bound to project: <b>{proj_name}</b> (ID: {proj_id})", parse_mode="HTML")

@router.message(Command("projects"))
async def debug_list_projects(message: Message, session: AsyncSession, db_user: User):
    if message.from_user.id != 786320574: return
    res = await session.execute(select(Project).order_by(Project.id))
    projects = res.scalars().all()
    if not projects: return await message.answer("ðŸ¤·â€â™‚ï¸ ÐŸÑ€Ð¾ÐµÐºÑ‚Ð¾Ð² Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð¾.")
    lines = ["ðŸ“ <b>Ð¡Ð¿Ð¸ÑÐ¾Ðº Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð¾Ð² (Ð´Ð»Ñ /setproj):</b>\n"]
    for p in projects:
        status = "âœ…" if p.is_active else "âŒ"
        lines.append(f"<code>{p.id}</code>: {p.name} ({p.city}) {status}")
    await message.answer("\n".join(lines), parse_mode="HTML")



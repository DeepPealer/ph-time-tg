from datetime import date, datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from bot.database.models import User, UserRole, Report, Plan
from bot.keyboards.builders import (
    kb_cancel, kb_cancel_skip, kb_use_today, kb_confirm, kb_report_nav, kb_edit_fields,
    menu_employee, menu_admin, menu_manager, kb_city, kb_projects_for_report
)
from bot.utils.salary import calculate_photographer_salary, CITY_LABELS
from bot.config import config

router = Router()


class ReportForm(StatesGroup):
    date          = State()
    project       = State()
    project_id    = State()
    city          = State()  # asked if user has no default city
    employee_name = State()
    shift_count   = State()
    revenue       = State()
    cash          = State()
    acquiring     = State()
    expense       = State()
    trainee_salary = State()
    cash_balance  = State()
    visitors      = State()
    birthdays     = State()
    comment       = State()
    confirm       = State()


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ")


def _menu(role: str):
    if role == "admin": return menu_admin()
    if role == "manager": return menu_manager()
    return menu_employee()


# â”€â”€â”€ Entry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.message(F.text == "ðŸ“‹ Ð¡Ð´Ð°Ñ‚ÑŒ Ð¾Ñ‚Ñ‡ÐµÑ‚")
async def start_report(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    if not db_user.is_active:
        await message.answer("â›” Ð£ Ð²Ð°Ñ Ð½ÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°. ÐžÐ±Ñ€Ð°Ñ‚Ð¸Ñ‚ÐµÑÑŒ Ðº Ð°Ð´Ð¼Ð¸Ð½Ð¸ÑÑ‚Ñ€Ð°Ñ‚Ð¾Ñ€Ñƒ.")
        return
    await state.clear()
    today = date.today().strftime("%d.%m.%Y")
    await state.set_state(ReportForm.date)

    is_employee = db_user.role.value == "employee"

    if is_employee:
        # Employees: auto-set today, skip date step
        await state.update_data(date=date.today().isoformat())
        if db_user.city:
            await state.update_data(city=db_user.city)
            # Find projects for city
            from bot.database.models import Project
            res = await session.execute(select(Project).where(Project.city == db_user.city, Project.is_active == True))
            projs = res.scalars().all()
            await _finalize_step(message, state, db_user, session,
                                 f"ðŸ“‹ <b>Ð¡Ð´Ð°Ñ‡Ð° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð°</b> Ð·Ð° <b>{today}</b>\n\n"
                                 "Ð¨Ð°Ð³ 2/12 â€” <b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚:",
                                 ReportForm.project, kb=kb_projects_for_report(projs))
        else:
            await _finalize_step(message, state, db_user, session,
                                 f"ðŸ“‹ <b>Ð¡Ð´Ð°Ñ‡Ð° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð°</b> Ð·Ð° <b>{today}</b>\n\n"
                                 "Ð¨Ð°Ð³ 2/12 â€” <b>Ð“Ð¾Ñ€Ð¾Ð´</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:",
                                 ReportForm.city, kb=kb_city())
    else:
        # Managers and admins: choose any date
        await message.answer(
            "ðŸ“‹ <b>Ð¡Ð´Ð°Ñ‡Ð° Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð°</b>\n\n"
            "Ð¨Ð°Ð³ 1/12 â€” <b>Ð”Ð°Ñ‚Ð° ÑÐ¼ÐµÐ½Ñ‹</b>\n"
            "ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ Â«Ð¡ÐµÐ³Ð¾Ð´Ð½ÑÂ» Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð´Ð°Ñ‚Ñƒ Ð² Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚Ðµ <code>Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“</code>:",
            parse_mode="HTML",
            reply_markup=kb_use_today(today)
        )


# â”€â”€â”€ Step 1: Date â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "report:use_today", ReportForm.date)
async def use_today(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(date=date.today().isoformat())
    await call.message.edit_text("âœ… Ð”Ð°Ñ‚Ð°: <b>ÑÐµÐ³Ð¾Ð´Ð½Ñ</b>", parse_mode="HTML")
    
    if db_user.city:
        await state.update_data(city=db_user.city)
        
        # If bound to a project, jump straight to name
        if db_user.role == UserRole.manager and db_user.project_id:
            from bot.database.models import Project
            res = await session.execute(select(Project).where(Project.id == db_user.project_id))
            proj = res.scalar_one_or_none()
            if proj:
                await state.update_data(project=proj.name, project_id=proj.id)
                await call.message.edit_text(f"âœ… ÐŸÑ€Ð¾ÐµÐºÑ‚: <b>{proj.name}</b>", parse_mode="HTML")
                suggested = db_user.full_name
                return await _finalize_step(call.message, state, db_user, session,
                    f"Ð¨Ð°Ð³ 4/12 â€” <b>Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°</b>\nÐŸÑ€ÐµÐ´Ð»Ð¾Ð¶ÐµÐ½Ð¸Ðµ: Â«{suggested}Â»\nÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /use_name Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð²Ñ€ÑƒÑ‡Ð½ÑƒÑŽ:",
                    ReportForm.employee_name)

        from bot.database.models import Project
        res = await session.execute(select(Project).where(Project.city == db_user.city, Project.is_active == True))
        projs = res.scalars().all()
        await _finalize_step(call.message, state, db_user, session,
                             "Ð¨Ð°Ð³ 2/12 â€” <b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚:", ReportForm.project, kb=kb_projects_for_report(projs))
    else:
        await _finalize_step(call.message, state, db_user, session,
                             "Ð¨Ð°Ð³ 2/12 â€” <b>Ð“Ð¾Ñ€Ð¾Ð´</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:", ReportForm.city, kb=kb_city())
    await call.answer()


@router.message(ReportForm.date)
async def process_date(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        today = date.today()
        if d > today:
            await message.answer("âŒ Ð”Ð°Ñ‚Ð° Ð½Ðµ Ð¼Ð¾Ð¶ÐµÑ‚ Ð±Ñ‹Ñ‚ÑŒ Ð² Ð±ÑƒÐ´ÑƒÑ‰ÐµÐ¼. Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½ÑƒÑŽ Ð´Ð°Ñ‚Ñƒ:")
            return
        if d < today.replace(year=today.year - (1 if today.month <= 2 else 0), month=(today.month - 2) % 12 or 12):
             # Simple check for ~60 days, but let's be more precise
             from datetime import timedelta
             if d < today - timedelta(days=60):
                 await message.answer("âŒ Ð”Ð°Ñ‚Ð° ÑÐ»Ð¸ÑˆÐºÐ¾Ð¼ ÑÑ‚Ð°Ñ€Ð°Ñ (Ð±Ð¾Ð»ÐµÐµ 60 Ð´Ð½ÐµÐ¹). Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½ÑƒÑŽ Ð´Ð°Ñ‚Ñƒ:")
                 return
    except ValueError:
        await message.answer("âŒ ÐÐµÐ²ÐµÑ€Ð½Ñ‹Ð¹ Ñ„Ð¾Ñ€Ð¼Ð°Ñ‚. Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð´Ð°Ñ‚Ñƒ ÐºÐ°Ðº <code>Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“</code>:", parse_mode="HTML")
        return
    await state.update_data(date=d.isoformat())
    msg_prefix = f"âœ… Ð”Ð°Ñ‚Ð°: <b>{d.strftime('%d.%m.%Y')}</b>\n\n"
    
    if db_user.city:
        await state.update_data(city=db_user.city)
        
        # If bound to a project, jump straight to name
        if db_user.role == UserRole.manager and db_user.project_id:
            from bot.database.models import Project
            res = await session.execute(select(Project).where(Project.id == db_user.project_id))
            proj = res.scalar_one_or_none()
            if proj:
                await state.update_data(project=proj.name, project_id=proj.id)
                await message.answer(f"{msg_prefix}âœ… ÐŸÑ€Ð¾ÐµÐºÑ‚: <b>{proj.name}</b>", parse_mode="HTML")
                suggested = db_user.full_name
                return await _finalize_step(message, state, db_user, session,
                    f"Ð¨Ð°Ð³ 4/12 â€” <b>Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°</b>\nÐŸÑ€ÐµÐ´Ð»Ð¾Ð¶ÐµÐ½Ð¸Ðµ: Â«{suggested}Â»\nÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /use_name Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð²Ñ€ÑƒÑ‡Ð½ÑƒÑŽ:",
                    ReportForm.employee_name)

        from bot.database.models import Project
        res = await session.execute(select(Project).where(Project.city == db_user.city, Project.is_active == True))
        projs = res.scalars().all()
        await _finalize_step(message, state, db_user, session, 
                             f"{msg_prefix}Ð¨Ð°Ð³ 2/12 â€” <b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚:",
                             ReportForm.project, kb=kb_projects_for_report(projs))
    else:
        await _finalize_step(message, state, db_user, session,
                             f"{msg_prefix}Ð¨Ð°Ð³ 2/12 â€” <b>Ð“Ð¾Ñ€Ð¾Ð´</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð³Ð¾Ñ€Ð¾Ð´:",
                             ReportForm.city, kb=kb_city())




# â”€â”€â”€ Step 3 (optional): City â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data.startswith("report:city:"), ReportForm.city)
async def process_city(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    city = call.data.split(":")[2]  # 'gomel' or 'minsk'
    await state.update_data(city=city)
    city_label = CITY_LABELS.get(city, city)
    await call.message.edit_text(f"âœ… Ð“Ð¾Ñ€Ð¾Ð´: <b>{city_label}</b>", parse_mode="HTML")
    
    from bot.database.models import Project
    res = await session.execute(select(Project).where(Project.city == city, Project.is_active == True))
    projs = res.scalars().all()
    
    await _finalize_step(call.message, state, db_user, session,
                         "Ð¨Ð°Ð³ 3/12 â€” <b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>\nÐ’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚:",
                         ReportForm.project, kb=kb_projects_for_report(projs))
    await call.answer()


@router.callback_query(F.data.startswith("report:proj:"), ReportForm.project)
async def process_project_callback(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    proj_id = int(call.data.split(":")[2])
    from bot.database.models import Project
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if not p: return await call.answer("ÐŸÑ€Ð¾ÐµÐºÑ‚ Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½")
    
    await state.update_data(project=p.name, project_id=p.id)
    await call.message.edit_text(f"âœ… ÐŸÑ€Ð¾ÐµÐºÑ‚: <b>{p.name}</b>", parse_mode="HTML")
    
    suggested = db_user.full_name
    await _finalize_step(call.message, state, db_user, session,
        f"Ð¨Ð°Ð³ 4/12 â€” <b>Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°</b>\n"
        f"ÐŸÑ€ÐµÐ´Ð»Ð¾Ð¶ÐµÐ½Ð¸Ðµ: Â«{suggested}Â»\n"
        "ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ /use_name Ñ‡Ñ‚Ð¾Ð±Ñ‹ Ð¸ÑÐ¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÑŒ, Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð²Ñ€ÑƒÑ‡Ð½ÑƒÑŽ:",
        ReportForm.employee_name)
    await call.answer()


@router.message(F.text == "/use_name", ReportForm.employee_name)
async def use_suggested_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(employee_name=db_user.full_name)
    await _finalize_step(message, state, db_user, session,
        "Ð¨Ð°Ð³ 5/13 â€” <b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº Ð² ÑÐ¼ÐµÐ½Ðµ</b> (1-20):", ReportForm.shift_count)


@router.message(ReportForm.employee_name)
async def process_employee_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(employee_name=message.text.strip())
    await _finalize_step(message, state, db_user, session,
        "Ð¨Ð°Ð³ 5/13 â€” <b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº Ð² ÑÐ¼ÐµÐ½Ðµ</b> (1-20):", ReportForm.shift_count)


# â”€â”€â”€ Step 4: Shift count â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.message(ReportForm.shift_count)
async def process_shift_count(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if not (1 <= n <= 20):
            await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾ Ð¾Ñ‚ 1 Ð´Ð¾ 20:")
            return
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ†ÐµÐ»Ð¾Ðµ Ñ‡Ð¸ÑÐ»Ð¾ (Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: 3):")
        return
    await state.update_data(shift_count=n)
    if n > 1:
        await message.answer(
            f"ðŸ‘¥ <b>Ð¡Ð¾Ð²Ð¼ÐµÑÑ‚Ð½Ð°Ñ ÑÐ¼ÐµÐ½Ð° ({n} Ñ‡ÐµÐ».)</b>\n\n"
            "ðŸ“Œ <b>ÐšÐ°Ðº ÑÐ´Ð°Ð²Ð°Ñ‚ÑŒ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ Ð¿Ñ€Ð¸ Ñ€Ð°Ð±Ð¾Ñ‚Ðµ Ð²Ð´Ð²Ð¾Ñ‘Ð¼:</b>\n"
            "â€¢ ÐšÐ°Ð¶Ð´Ñ‹Ð¹ ÑÐ´Ð°Ñ‘Ñ‚ <b>ÑÐ²Ð¾Ð¹ Ð¾Ñ‚Ð´ÐµÐ»ÑŒÐ½Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚</b>\n"
            "â€¢ ÐšÐ°Ð¶Ð´Ñ‹Ð¹ Ð²Ð²Ð¾Ð´Ð¸Ñ‚ <b>Ð¿Ð¾Ð»Ð½ÑƒÑŽ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÑƒ</b> ÑÐ¼ÐµÐ½Ñ‹\n"
            "â€¢ Ð—ÐŸ Ð´ÐµÐ»Ð¸Ñ‚ÑÑ Ð°Ð²Ñ‚Ð¾Ð¼Ð°Ñ‚Ð¸Ñ‡ÐµÑÐºÐ¸ Ð½Ð° ÐºÐ¾Ð»-Ð²Ð¾ Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº\n"
            "â€¢ Ð’ Excel Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ° ÑƒÑ‡Ð¸Ñ‚Ñ‹Ð²Ð°ÐµÑ‚ÑÑ Ð¾Ð´Ð¸Ð½ Ñ€Ð°Ð· âœ…",
            parse_mode="HTML"
        )
    await _finalize_step(message, state, db_user, session,
        "Ð¨Ð°Ð³ 6/13 â€” <b>ÐžÐ±Ñ‰Ð°Ñ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ°</b> (â‚½, Ñ‚Ð¾Ð»ÑŒÐºÐ¾ Ñ‡Ð¸ÑÐ»Ð¾):", ReportForm.revenue)


# â”€â”€â”€ Helper for numeric steps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _clean_num(text: str) -> float:
    return float(text.strip().replace(" ", "").replace(",", "."))


async def _ask_number(message: Message, state: FSMContext, db_user: User, session: AsyncSession,
                       key: str, next_state: State, next_prompt: str, max_val: float = 10_000_000):
    try:
        v = _clean_num(message.text)
        if v < 0: raise ValueError
        if v > max_val:
            await message.answer(f"âŒ Ð—Ð½Ð°Ñ‡ÐµÐ½Ð¸Ðµ ÑÐ»Ð¸ÑˆÐºÐ¾Ð¼ Ð±Ð¾Ð»ÑŒÑˆÐ¾Ðµ (Ð»Ð¸Ð¼Ð¸Ñ‚ {_fmt(max_val)} â‚½). ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ Ð²Ð²Ð¾Ð´:")
            return
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ð¾Ðµ Ñ‡Ð¸ÑÐ»Ð¾ (Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€: 15000):")
        return
    await state.update_data(**{key: v})
    await _finalize_step(message, state, db_user, session, next_prompt, next_state)


# â”€â”€â”€ Steps 5â€“10: Numeric fields â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.message(ReportForm.revenue)
async def process_revenue(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "revenue", ReportForm.cash,
                      "Ð¨Ð°Ð³ 7/13 â€” <b>ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ</b> (â‚½):")


@router.message(ReportForm.cash)
async def process_cash(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "cash", ReportForm.acquiring,
                      "Ð¨Ð°Ð³ 8/13 â€” <b>Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³ (Ð±ÐµÐ·Ð½Ð°Ð»)</b> (â‚½):")


@router.message(ReportForm.acquiring)
async def process_acquiring(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        v = _clean_num(message.text)
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ð¾Ðµ Ñ‡Ð¸ÑÐ»Ð¾:")
        return

    data = await state.get_data()
    revenue = data["revenue"]
    cash = data["cash"]

    if abs((cash + v) - revenue) > 0.01:
        await message.answer(
            f"âŒ <b>ÐžÑˆÐ¸Ð±ÐºÐ° Ð² ÑÑƒÐ¼Ð¼Ðµ!</b>\n\n"
            f"Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ°: {_fmt(revenue)} â‚½\n"
            f"ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ: {_fmt(cash)} â‚½\n"
            f"Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³: {_fmt(v)} â‚½\n\n"
            f"Ð¡ÑƒÐ¼Ð¼Ð° ({_fmt(cash+v)} â‚½) Ð½Ðµ ÑÐ¾Ð²Ð¿Ð°Ð´Ð°ÐµÑ‚ Ñ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ¾Ð¹. "
            "ÐŸÐ¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð°, Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ ÐºÐ¾Ñ€Ñ€ÐµÐºÑ‚Ð½Ð¾Ðµ Ð·Ð½Ð°Ñ‡ÐµÐ½Ð¸Ðµ ÑÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³Ð° Ð¸Ð»Ð¸ Ð½Ð°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ /cancel Ð¸ Ð½Ð°Ñ‡Ð½Ð¸Ñ‚Ðµ Ð·Ð°Ð½Ð¾Ð²Ð¾:",
            parse_mode="HTML"
        )
        return

    await state.update_data(acquiring=v)
    await _finalize_step(message, state, db_user, session, "Ð¨Ð°Ð³ 9/14 â€” <b>Ð¥Ð¾Ð· Ñ€Ð°ÑÑ…Ð¾Ð´</b> (â‚½):", ReportForm.expense)


@router.message(ReportForm.expense)
async def process_expense(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "expense", ReportForm.trainee_salary,
                      "Ð¨Ð°Ð³ 10/14 â€” <b>Ð—Ð°Ñ€Ð¿Ð»Ð°Ñ‚Ð° ÑÑ‚Ð°Ð¶ÐµÑ€Ð°</b> (â‚½, 0 ÐµÑÐ»Ð¸ Ð½ÐµÑ‚):")


@router.message(ReportForm.trainee_salary)
async def process_trainee_salary(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "trainee_salary", ReportForm.cash_balance,
                      "Ð¨Ð°Ð³ 11/14 â€” <b>ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº Ð² ÐºÐ°ÑÑÐµ</b> (â‚½):")


@router.message(ReportForm.cash_balance)
async def process_cash_balance(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "cash_balance", ReportForm.visitors,
                      "Ð¨Ð°Ð³ 12/14 â€” <b>ÐŸÑ€Ð¾Ñ…Ð¾Ð´Ð¸Ð¼Ð¾ÑÑ‚ÑŒ (ÐºÐ¾Ð»-Ð²Ð¾ Ð¿Ð¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»ÐµÐ¹)</b>:", max_val=1_000_000)


@router.message(ReportForm.visitors)
async def process_visitors(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if not (0 <= n <= 10000):
            await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾ Ð¾Ñ‚ 0 Ð´Ð¾ 10 000:")
            return
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ†ÐµÐ»Ð¾Ðµ Ñ‡Ð¸ÑÐ»Ð¾:")
        return
    await state.update_data(visitors=n)
    await _finalize_step(message, state, db_user, session, "Ð¨Ð°Ð³ 13/14 â€” <b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ð´Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹</b>:", ReportForm.birthdays)


@router.message(ReportForm.birthdays)
async def process_birthdays(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if n < 0: raise ValueError
        data = await state.get_data()
        if n > data["visitors"]:
            await message.answer(f"âŒ Ð”Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹ ({n}) Ð½Ðµ Ð¼Ð¾Ð¶ÐµÑ‚ Ð±Ñ‹Ñ‚ÑŒ Ð±Ð¾Ð»ÑŒÑˆÐµ, Ñ‡ÐµÐ¼ Ð¿Ð¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»ÐµÐ¹ ({data['visitors']}). Ð˜ÑÐ¿Ñ€Ð°Ð²ÑŒÑ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾:")
            return
        if n > 1000:
            await message.answer("âŒ Ð¡Ð»Ð¸ÑˆÐºÐ¾Ð¼ Ð¼Ð½Ð¾Ð³Ð¾ Ð´Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹. ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ Ñ‡Ð¸ÑÐ»Ð¾:")
            return
    except ValueError:
        await message.answer("âŒ Ð’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ñ†ÐµÐ»Ð¾Ðµ Ñ‡Ð¸ÑÐ»Ð¾ (0 ÐµÑÐ»Ð¸ Ð½ÐµÑ‚):")
        return
    await state.update_data(birthdays=n)
    await _finalize_step(message, state, db_user, session,
                         "Ð¨Ð°Ð³ 14/14 â€” <b>ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹</b>\nÐÐ°Ð¿Ð¸ÑˆÐ¸Ñ‚Ðµ Ñ‡Ñ‚Ð¾-Ð½Ð¸Ð±ÑƒÐ´ÑŒ (Ð¸Ð»Ð¸ ÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ Â«ÐŸÑ€Ð¾Ð¿ÑƒÑÑ‚Ð¸Ñ‚ÑŒÂ»):",
                         ReportForm.comment, kb=kb_cancel_skip())


# â”€â”€â”€ Step 12: Comment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "report:skip", ReportForm.comment)
async def skip_comment(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.update_data(comment="")
    data = await state.get_data()
    await _show_confirm(call.message, state, session)
    await call.answer()


@router.message(ReportForm.comment)
async def process_comment(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(comment=message.text.strip())
    data = await state.get_data()
    await _show_confirm(message, state, session)


# â”€â”€â”€ Confirm preview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def _get_plan_line(session: AsyncSession, project_id: int | None, city: str | None, revenue: float) -> str | None:
    """Find active plan for project or global, return formatted fulfillment line."""
    query = select(Plan).where(Plan.is_active == True)
    
    if project_id:
        # Specific project plan or city-wide general plan
        query = query.where(or_(Plan.project_id == project_id, (Plan.project_id == None) & (Plan.city == city)))
    else:
        # City-wide general plan only
        query = query.where(Plan.project_id == None, Plan.city == city)
        
    res = await session.execute(query.order_by(Plan.project_id.nulls_last()))
    plan = res.scalars().first()
    if not plan:
        return None
    pct = (revenue / plan.plan_amount * 100) if plan.plan_amount else 0
    period_str = "Ð´ÐµÐ½ÑŒ" if plan.period == "day" else "Ð¼ÐµÑÑÑ†"
    return (
        f"ðŸŽ¯ ÐŸÐ»Ð°Ð½ ({period_str}):     <b>{_fmt(plan.plan_amount)} â‚½</b>\n"
        f"ðŸ“ˆ Ð¤Ð°ÐºÑ‚:              <b>{_fmt(revenue)} â‚½</b>\n"
        f"âœ… Ð’Ñ‹Ð¿Ð¾Ð»Ð½ÐµÐ½Ð¸Ðµ:        <b>{pct:.0f}%</b>"
    )


async def _show_confirm(msg: Message, state: FSMContext, session: AsyncSession):
    d = await state.get_data()
    is_editing = "admin_editing_report_id" in d
    city = d.get("city", "gomel")
    report_date = datetime.fromisoformat(d["date"]).date()
    weekday = report_date.weekday()  # 0=Mon, 6=Sun
    salary, sal_desc = calculate_photographer_salary(d["revenue"], d["shift_count"], city, weekday)
    plan_line = await _get_plan_line(session, d.get("project_id"), city, d["revenue"])

    date_str = report_date.strftime("%d.%m.%Y")
    city_label = CITY_LABELS.get(city, city)
    plan_block = f"\n{plan_line}\n" if plan_line else ""
    text = (
        "ðŸ“‹ <b>ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒÑ‚Ðµ Ð´Ð°Ð½Ð½Ñ‹Ðµ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚Ð°:</b>\n\n"
        f"ðŸ“… Ð”Ð°Ñ‚Ð°:              <b>{date_str}</b>\n"
        f"ðŸ™ Ð“Ð¾Ñ€Ð¾Ð´:              <b>{city_label}</b>\n"
        f"ðŸŽª ÐŸÑ€Ð¾ÐµÐºÑ‚:            <b>{d['project']}</b>\n"
        f"ðŸ‘¤ Ð¡Ð¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸Ðº:         <b>{d['employee_name']}</b>\n"
        f"ðŸ‘¥ Ð§ÐµÐ». Ð² ÑÐ¼ÐµÐ½Ðµ:      <b>{d['shift_count']}</b>\n\n"
        f"ðŸ’° Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ°:           <b>{_fmt(d['revenue'])} â‚½</b>\n"
        f"ðŸ’µ ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ:          <b>{_fmt(d['cash'])} â‚½</b>\n"
        f"ðŸ’³ Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³:         <b>{_fmt(d['acquiring'])} â‚½</b>\n"
        f"ðŸ“‰ Ð¥Ð¾Ð· Ñ€Ð°ÑÑ…Ð¾Ð´:        <b>{_fmt(d['expense'])} â‚½</b>\n"
        f"ðŸ§‘â€ðŸŽ“ Ð—ÐŸ ÑÑ‚Ð°Ð¶ÐµÑ€Ð°:       <b>{_fmt(d['trainee_salary'])} â‚½</b>\n"
        f"ðŸ– ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº Ð² ÐºÐ°ÑÑÐµ:   <b>{_fmt(d['cash_balance'])} â‚½</b>\n"
        f"ðŸ‘£ ÐŸÐ¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»Ð¸:        <b>{d['visitors']}</b>\n"
        f"ðŸŽ‚ Ð”Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹:     <b>{d['birthdays']}</b>\n"
        f"ðŸ’¬ ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹:       <b>{d.get('comment') or 'â€”'}</b>\n\n"
        f"â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”â”"
        f"{plan_block}\n"
        f"ðŸ“Š Ð¨ÐºÐ°Ð»Ð°: <i>{sal_desc}</i>\n"
        f"ðŸ’¸ <b>Ð’Ð°ÑˆÐ° Ð—ÐŸ Ð·Ð° ÑÐ¼ÐµÐ½Ñƒ: {_fmt(salary)} â‚½</b>\n\n"
        "Ð’ÑÑ‘ Ð²ÐµÑ€Ð½Ð¾?"
    )
    await state.update_data(salary=salary, salary_level=1)
    await state.set_state(ReportForm.confirm)
    await msg.answer(text, parse_mode="HTML", reply_markup=kb_confirm(is_editing=is_editing))


# â”€â”€â”€ Confirm callbacks â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.callback_query(F.data == "report:confirm", ReportForm.confirm)
async def confirm_report(call: CallbackQuery, state: FSMContext, db_user: User,
                         session: AsyncSession, bot: Bot):
    d = await state.get_data()
    await state.clear()

    edit_id = d.get("admin_editing_report_id")
    
    if edit_id:
        res = await session.execute(select(Report).where(Report.id == edit_id))
        report = res.scalar_one()
        report.date = datetime.fromisoformat(d["date"]).date()
        report.project_name = d["project"]
        report.employee_name = d["employee_name"]
        report.shift_count = d["shift_count"]
        report.revenue = d["revenue"]
        report.cash = d["cash"]
        report.acquiring = d["acquiring"]
        report.salary_paid = d["salary"]
        report.expense = d["expense"]
        report.cash_balance = d["cash_balance"]
        report.visitors = d["visitors"]
        report.birthdays = d["birthdays"]
        report.comment = d.get("comment")
        report.salary_level = d["salary_level"]
        report.trainee_salary = d["trainee_salary"]
        report.city = d.get("city")
        report.project_id = d.get("project_id")
        report.is_reviewed = True
        report.reviewed_by_id = db_user.id
    else:
        report = Report(
            user_id=db_user.id,
            date=datetime.fromisoformat(d["date"]).date(),
            project_name=d["project"],
            employee_name=d["employee_name"],
            shift_count=d["shift_count"],
            revenue=d["revenue"],
            cash=d["cash"],
            acquiring=d["acquiring"],
            salary_paid=d["salary"],
            expense=d["expense"],
            cash_balance=d["cash_balance"],
            visitors=d["visitors"],
            birthdays=d["birthdays"],
            comment=d.get("comment"),
            salary_level=d["salary_level"],
            trainee_salary=d["trainee_salary"],
            city=d.get("city"),
            project_id=d.get("project_id"),
        )
        session.add(report)
        
    await session.commit()

    plan_line = await _get_plan_line(session, d.get("project_id"), d.get("city"), d["revenue"])

    await call.message.edit_reply_markup()
    plan_part = f"\n{plan_line}" if plan_line else ""
    
    if edit_id:
        await call.message.answer("âœ… ÐžÑ‚Ñ‡Ñ‘Ñ‚ ÑƒÑÐ¿ÐµÑˆÐ½Ð¾ Ð¾Ñ‚Ñ€ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½ Ð¸ ÑÐ¾Ñ…Ñ€Ð°Ð½Ñ‘Ð½!", reply_markup=_menu(db_user.role.value))
        await call.answer()
        return

    await call.message.answer(
        f"âœ… ÐžÑ‚Ñ‡Ñ‘Ñ‚ Ð¿Ñ€Ð¸Ð½ÑÑ‚!{plan_part}\n\n"
        f"ðŸ’¸ <b>Ð’Ð¾Ð·ÑŒÐ¼Ð¸ Ð¸Ð· ÐºÐ°ÑÑÑ‹: {_fmt(d['salary'])} â‚½</b>",
        parse_mode="HTML",
        reply_markup=_menu(db_user.role.value)
    )

    # Forward to admin chat / admin DMs
    fwd = _build_admin_notification(d, db_user, plan_line)
    if config.admin_chat_id:
        try:
            await bot.send_message(config.admin_chat_id, fwd, parse_mode="HTML")
        except Exception:
            pass
    else:
        from sqlalchemy import select as sel
        from bot.database.models import User as U
        admins = await session.execute(
            sel(U).where(U.role == UserRole.admin, U.is_active == True)
        )
        for adm in admins.scalars().all():
            if adm.telegram_id != db_user.telegram_id:
                try:
                    await bot.send_message(adm.telegram_id, fwd, parse_mode="HTML")
                except Exception:
                    pass
    await call.answer()


@router.callback_query(F.data == "report:restart", ReportForm.confirm)
async def restart_report(call: CallbackQuery, state: FSMContext, db_user: User):
    d = await state.get_data()
    if d.get("admin_editing_report_id"):
        return await call.answer("ÐÐµÐ´Ð¾ÑÑ‚ÑƒÐ¿Ð½Ð¾ Ð¿Ñ€Ð¸ Ñ€ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ð¸", show_alert=True)
    await state.clear()
    await call.message.edit_reply_markup()
    today = date.today().strftime("%d.%m.%Y")
    await state.set_state(ReportForm.date)
    await call.message.answer(
        "ðŸ”„ ÐÐ°Ñ‡Ð¸Ð½Ð°ÐµÐ¼ Ð·Ð°Ð½Ð¾Ð²Ð¾.\n\nÐ¨Ð°Ð³ 1/12 â€” <b>Ð”Ð°Ñ‚Ð° ÑÐ¼ÐµÐ½Ñ‹</b>:",
        parse_mode="HTML",
        reply_markup=kb_use_today(today)
    )
    await call.answer()


@router.callback_query(F.data == "report:cancel")
async def cancel_report(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    d = await state.get_data()
    edit_id = d.get("admin_editing_report_id")
    await state.clear()
    await call.message.edit_reply_markup()
    
    if edit_id:
        from bot.handlers.admin import review_view
        return await review_view(call, session, db_user, explicitly_view_id=edit_id)

    await call.message.answer("âŒ ÐžÑ‚Ð¼ÐµÐ½ÐµÐ½Ð¾.", reply_markup=_menu(db_user.role.value))
    await call.answer()


@router.callback_query(F.data == "report:edit")
async def edit_report_menu(call: CallbackQuery):
    await call.message.edit_text("Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ð¾Ð»Ðµ Ð´Ð»Ñ Ñ€ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ñ:", reply_markup=kb_edit_fields())
    await call.answer()


@router.callback_query(F.data == "report:preview")
async def back_to_preview(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    await _show_confirm(call.message, state, session)
    await call.answer()


@router.callback_query(F.data.startswith("edit:"))
async def jump_to_edit(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    field = call.data.split(":")[1]
    
    # Map field names to states and prompts
    field_map = {
        "date": (ReportForm.date, "<b>Ð”Ð°Ñ‚Ð° ÑÐ¼ÐµÐ½Ñ‹</b> (Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“):"),
        "project": (ReportForm.project, "<b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>:"),
        "employee_name": (ReportForm.employee_name, "<b>Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°</b>:"),
        "shift_count": (ReportForm.shift_count, "<b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº Ð² ÑÐ¼ÐµÐ½Ðµ</b>:"),
        "revenue": (ReportForm.revenue, "<b>ÐžÐ±Ñ‰Ð°Ñ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ°</b> (â‚½):"),
        "cash": (ReportForm.cash, "<b>ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ</b> (â‚½):"),
        "acquiring": (ReportForm.acquiring, "<b>Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³ (Ð±ÐµÐ·Ð½Ð°Ð»)</b> (â‚½):"),
        "expense": (ReportForm.expense, "<b>Ð¥Ð¾Ð· Ñ€Ð°ÑÑ…Ð¾Ð´</b> (â‚½):"),
        "trainee_salary": (ReportForm.trainee_salary, "<b>Ð—Ð°Ñ€Ð¿Ð»Ð°Ñ‚Ð° ÑÑ‚Ð°Ð¶ÐµÑ€Ð°</b> (â‚½):"),
        "cash_balance": (ReportForm.cash_balance, "<b>ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº Ð² ÐºÐ°ÑÑÐµ</b> (â‚½):"),
        "visitors": (ReportForm.visitors, "<b>ÐŸÑ€Ð¾Ñ…Ð¾Ð´Ð¸Ð¼Ð¾ÑÑ‚ÑŒ (Ñ‡ÐµÐ»)</b>:"),
        "birthdays": (ReportForm.birthdays, "<b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ð´Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹</b>:"),
        "comment": (ReportForm.comment, "<b>ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹</b>:"),
    }
    
    if field not in field_map:
        return await call.answer("Неизвестное поле", show_alert=True)
        
    target_state, prompt = field_map[field]
    await state.set_state(target_state)
    
    # We add a special flag so that after editing we return to preview if we were there
    await state.update_data(editing_from_preview=True)
    
    kb = kb_report_nav()
    if target_state == ReportForm.date:
        kb = kb_use_today(date.today().strftime("%d.%m.%Y"))
    elif target_state == ReportForm.comment:
        kb = kb_cancel_skip()
    elif target_state == ReportForm.project:
        d = await state.get_data()
        city = d.get("city")
        from bot.database.models import Project
        from sqlalchemy import select
        res = await session.execute(select(Project).where(Project.city == city, Project.is_active == True))
        projs = res.scalars().all()
        from bot.keyboards.builders import kb_projects_for_report
        kb = kb_projects_for_report(projs)
    elif target_state == ReportForm.city:
        from bot.keyboards.builders import kb_city
        kb = kb_city()
        
    await call.message.edit_text(f"Ð ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ðµ: {prompt}", parse_mode="HTML", reply_markup=kb)
    await call.answer()


async def _finalize_step(message: Message, state: FSMContext, db_user: User, session: AsyncSession, next_prompt: str = None, next_state: State = None, kb = None):
    data = await state.get_data()
    if data.get("editing_from_preview"):
        await state.update_data(editing_from_preview=False)
        await _show_confirm(message, state, session)
        return

    if next_prompt and next_state:
        await message.answer(next_prompt, parse_mode="HTML", reply_markup=kb or kb_report_nav())
        await state.set_state(next_state)


@router.callback_query(F.data == "report:back")
async def back_report(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if data.get("admin_editing_report_id"):
        # When editing, Back from ANYWHERE (including confirm) goes to edit fields menu
        await state.set_state(ReportForm.confirm) # To ensure edit menu logic works
        from bot.keyboards.builders import kb_edit_fields
        await call.message.edit_text("Ð’Ñ‹Ð±ÐµÑ€Ð¸Ñ‚Ðµ Ð¿Ð¾Ð»Ðµ Ð´Ð»Ñ Ñ€ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð¸Ñ:", reply_markup=kb_edit_fields())
        return await call.answer()

    curr = await state.get_state()
    if not curr:
        return await call.answer()
    
    # State mapping for "Back" button
    prev_map = {
        ReportForm.project: (ReportForm.date, "Ð¨Ð°Ð³ 1/12 â€” <b>Ð”Ð°Ñ‚Ð° ÑÐ¼ÐµÐ½Ñ‹</b>:\nÐÐ°Ð¶Ð¼Ð¸Ñ‚Ðµ Â«Ð¡ÐµÐ³Ð¾Ð´Ð½ÑÂ» Ð¸Ð»Ð¸ Ð²Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð”Ð”.ÐœÐœ.Ð“Ð“Ð“Ð“:"),
        ReportForm.employee_name: (ReportForm.project, "Ð¨Ð°Ð³ 2/12 â€” <b>ÐÐ°Ð·Ð²Ð°Ð½Ð¸Ðµ Ð¿Ñ€Ð¾ÐµÐºÑ‚Ð°</b>\nÐ’Ð²ÐµÐ´Ð¸Ñ‚Ðµ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ðµ:"),
        ReportForm.shift_count: (ReportForm.employee_name, "Ð¨Ð°Ð³ 3/12 â€” <b>Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ ÑÐ¾Ñ‚Ñ€ÑƒÐ´Ð½Ð¸ÐºÐ°</b>:"),
        ReportForm.revenue: (ReportForm.shift_count, "Ð¨Ð°Ð³ 4/12 â€” <b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ñ‡ÐµÐ»Ð¾Ð²ÐµÐº Ð² ÑÐ¼ÐµÐ½Ðµ</b>:"),
        ReportForm.cash: (ReportForm.revenue, "Ð¨Ð°Ð³ 5/12 â€” <b>ÐžÐ±Ñ‰Ð°Ñ Ð²Ñ‹Ñ€ÑƒÑ‡ÐºÐ°</b> (â‚½):"),
        ReportForm.acquiring: (ReportForm.cash, "Ð¨Ð°Ð³ 6/12 â€” <b>ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ</b> (â‚½):"),
        ReportForm.expense: (ReportForm.acquiring, "Ð¨Ð°Ð³ 7/12 â€” <b>Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³ (Ð±ÐµÐ·Ð½Ð°Ð»)</b> (â‚½):"),
        ReportForm.cash_balance: (ReportForm.expense, "Ð¨Ð°Ð³ 8/12 â€” <b>Ð Ð°ÑÑ…Ð¾Ð´</b> (â‚½):"),
        ReportForm.visitors: (ReportForm.cash_balance, "Ð¨Ð°Ð³ 9/12 â€” <b>ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº Ð² ÐºÐ°ÑÑÐµ</b> (â‚½):"),
        ReportForm.birthdays: (ReportForm.visitors, "Ð¨Ð°Ð³ 10/12 â€” <b>ÐŸÑ€Ð¾Ñ…Ð¾Ð´Ð¸Ð¼Ð¾ÑÑ‚ÑŒ (Ñ‡ÐµÐ»)</b>:"),
        ReportForm.comment: (ReportForm.birthdays, "Ð¨Ð°Ð³ 11/12 â€” <b>ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ð´Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹</b>:"),
        ReportForm.confirm: (ReportForm.comment, "Ð¨Ð°Ð³ 12/12 â€” <b>ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹</b> (Ð¸Ð»Ð¸ Ð¿Ñ€Ð¾Ð¿ÑƒÑÑ‚Ð¸Ñ‚ÑŒ):"),
    }
    
    target = prev_map.get(curr)
    if not target:
        await call.answer("Ð”Ð°Ð»ÑŒÑˆÐµ Ð½ÐµÐºÑƒÐ´Ð°", show_alert=True)
        return
    
    prev_state, prompt = target
    await state.set_state(prev_state)
    
    # Handle Date step specifically (needs kb_today)
    kb = kb_report_nav()
    if prev_state == ReportForm.date:
        today = date.today().strftime("%d.%m.%Y")
        kb = kb_use_today(today)
    elif prev_state == ReportForm.comment:
        kb = kb_cancel_skip()
    
    await call.message.edit_text(prompt, parse_mode="HTML", reply_markup=kb)
    await call.answer()


# â”€â”€â”€ Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _build_admin_notification(d: dict, db_user: User, plan_line: str | None = None) -> str:
    report_date = datetime.fromisoformat(d["date"]).strftime("%d.%m.%Y")
    plan_block = f"\n{plan_line}\n" if plan_line else ""
    return (
        f"ðŸ“‹ <b>ÐÐ¾Ð²Ñ‹Ð¹ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚!</b>\n\n"
        f"ðŸ‘¤ ÐžÑ‚: {db_user.full_name}\n"
        f"ðŸ“… Ð”Ð°Ñ‚Ð°:           {report_date}\n"
        f"ðŸª ÐŸÑ€Ð¾ÐµÐºÑ‚:         {d['project']}\n"
        f"ðŸ‘¥ Ð§ÐµÐ». Ð² ÑÐ¼ÐµÐ½Ðµ:   {d['shift_count']}\n\n"
        f"ðŸ’° Ð’Ñ‹Ñ€ÑƒÑ‡ÐºÐ°:        {_fmt(d['revenue'])} â‚½\n"
        f"ðŸ’µ ÐÐ°Ð»Ð¸Ñ‡Ð½Ñ‹Ðµ:       {_fmt(d['cash'])} â‚½\n"
        f"ðŸ’³ Ð­ÐºÐ²Ð°Ð¹Ñ€Ð¸Ð½Ð³:      {_fmt(d['acquiring'])} â‚½\n"
        f"ðŸ“‰ Ð Ð°ÑÑ…Ð¾Ð´:         {_fmt(d['expense'])} â‚½\n"
        f"ðŸ¦ ÐžÑÑ‚Ð°Ñ‚Ð¾Ðº:        {_fmt(d['cash_balance'])} â‚½\n"
        f"ðŸ‘£ ÐŸÐ¾ÑÐµÑ‚Ð¸Ñ‚ÐµÐ»Ð¸:     {d['visitors']}\n"
        f"ðŸŽ‚ Ð”Ð½ÐµÐ¹ Ñ€Ð¾Ð¶Ð´ÐµÐ½Ð¸Ð¹:  {d['birthdays']}\n"
        f"ðŸ’¬ ÐšÐ¾Ð¼Ð¼ÐµÐ½Ñ‚Ð°Ñ€Ð¸Ð¹:    {d.get('comment') or 'â€”'}\n"
        f"{plan_block}\n"
        f"ðŸ’¸ Ð’Ñ‹Ð¿Ð»Ð°Ñ‡ÐµÐ½Ð¾ Ð—ÐŸ:   {_fmt(d['salary'])} â‚½ (ÑƒÑ€.{d['salary_level']})"
    )



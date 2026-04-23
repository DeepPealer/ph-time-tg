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
    partners      = State()
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


# ——— Entry ——————————————————————————————————————————————————————————————

@router.message(F.text == "📋 Сдать отчет")
async def start_report(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    if not db_user.is_active:
        await message.answer("⛔ У вас нет доступа. Обратитесь к администратору.")
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
                                 f"📋 <b>Сдача отчёта</b> за <b>{today}</b>\n\n"
                                 "Шаг 3/14 — <b>Название проекта</b>\nВыберите проект:",
                                 ReportForm.project, kb=kb_projects_for_report(projs))
        else:
            await _finalize_step(message, state, db_user, session,
                                 f"📋 <b>Сдача отчёта</b> за <b>{today}</b>\n\n"
                                 "Шаг 2/14 — <b>Город</b>\nВыберите город:",
                                 ReportForm.city, kb=kb_city())
    else:
        # Managers and admins: choose any date
        await message.answer(
            "📋 <b>Сдача отчёта</b>\n\n"
            "Шаг 1/14 — <b>Дата смены</b>\n"
            "Нажмите «Сегодня» или введите дату в формате <code>ДД.ММ.ГГГГ</code>:",
            parse_mode="HTML",
            reply_markup=kb_use_today(today)
        )


# ——— Step 1: Date —————————————————————————————————————————————————————————

@router.callback_query(F.data == "report:use_today", ReportForm.date)
async def use_today(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(date=date.today().isoformat())
    await call.message.edit_text("✅ Дата: <b>сегодня</b>", parse_mode="HTML")
    
    if db_user.city:
        await state.update_data(city=db_user.city)
        
        # If bound to a project, jump straight to name
        if db_user.role == UserRole.manager and db_user.project_id:
            from bot.database.models import Project
            res = await session.execute(select(Project).where(Project.id == db_user.project_id))
            proj = res.scalar_one_or_none()
            if proj:
                await state.update_data(project=proj.name, project_id=proj.id)
                await call.message.edit_text(f"✅ Проект: <b>{proj.name}</b>", parse_mode="HTML")
                
                name_to_use = db_user.pretty_name
                if db_user.role == UserRole.employee:
                    await state.update_data(employee_name=name_to_use)
                    return await _finalize_step(call.message, state, db_user, session,
                        "Шаг 5/14 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)
                
                return await _finalize_step(call.message, state, db_user, session,
                    f"Шаг 4/14 — <b>Фамилия сотрудника</b>\nПредложение: «{name_to_use}»\nНажмите /use_name или введите вручную:",
                    ReportForm.employee_name)

        from bot.database.models import Project
        res = await session.execute(select(Project).where(Project.city == db_user.city, Project.is_active == True))
        projs = res.scalars().all()
        await _finalize_step(call.message, state, db_user, session,
                             "Шаг 3/14 — <b>Название проекта</b>\nВыберите проект:", ReportForm.project, kb=kb_projects_for_report(projs))
    else:
        await _finalize_step(call.message, state, db_user, session,
                             "Шаг 2/14 — <b>Город</b>\nВыберите город:", ReportForm.city, kb=kb_city())
    await call.answer()


@router.message(ReportForm.date)
async def process_date(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        d = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        today = date.today()
        if d > today:
            await message.answer("❌ Дата не может быть в будущем. Введите корректную дату:")
            return
        if d < today.replace(year=today.year - (1 if today.month <= 2 else 0), month=(today.month - 2) % 12 or 12):
             # Simple check for ~60 days, but let's be more precise
             from datetime import timedelta
             if d < today - timedelta(days=60):
                 await message.answer("❌ Дата слишком старая (более 60 дней). Введите корректную дату:")
                 return
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату как <code>ДД.ММ.ГГГГ</code>:", parse_mode="HTML")
        return
    await state.update_data(date=d.isoformat())
    msg_prefix = f"✅ Дата: <b>{d.strftime('%d.%m.%Y')}</b>\n\n"
    
    if db_user.city:
        await state.update_data(city=db_user.city)
        
        # If bound to a project, jump straight to name
        if db_user.role == UserRole.manager and db_user.project_id:
            from bot.database.models import Project
            res = await session.execute(select(Project).where(Project.id == db_user.project_id))
            proj = res.scalar_one_or_none()
            if proj:
                await state.update_data(project=proj.name, project_id=proj.id)
                await message.answer(f"{msg_prefix}✅ Проект: <b>{proj.name}</b>", parse_mode="HTML")
                
                name_to_use = db_user.pretty_name
                if db_user.role == UserRole.employee:
                    await state.update_data(employee_name=name_to_use)
                    return await _finalize_step(message, state, db_user, session,
                        "Шаг 5/14 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)

                return await _finalize_step(message, state, db_user, session,
                    f"Шаг 4/14 — <b>Фамилия сотрудника</b>\nПредложение: «{name_to_use}»\nНажмите /use_name или введите вручную:",
                    ReportForm.employee_name)

        from bot.database.models import Project
        res = await session.execute(select(Project).where(Project.city == db_user.city, Project.is_active == True))
        projs = res.scalars().all()
        await _finalize_step(message, state, db_user, session, 
                             f"{msg_prefix}Шаг 3/14 — <b>Название проекта</b>\nВыберите проект:",
                             ReportForm.project, kb=kb_projects_for_report(projs))
    else:
        await _finalize_step(message, state, db_user, session,
                             f"{msg_prefix}Шаг 2/14 — <b>Город</b>\nВыберите город:",
                             ReportForm.city, kb=kb_city())




# ——— Step 3 (optional): City ——————————————————————————————————————————————

@router.callback_query(F.data.startswith("report:city:"), ReportForm.city)
async def process_city(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    city = call.data.split(":")[2]  # 'gomel' or 'minsk'
    await state.update_data(city=city)
    city_label = CITY_LABELS.get(city, city)
    await call.message.edit_text(f"✅ Город: <b>{city_label}</b>", parse_mode="HTML")
    
    from bot.database.models import Project
    res = await session.execute(select(Project).where(Project.city == city, Project.is_active == True))
    projs = res.scalars().all()
    
    await _finalize_step(call.message, state, db_user, session,
                         "Шаг 3/14 — <b>Название проекта</b>\nВыберите проект:",
                         ReportForm.project, kb=kb_projects_for_report(projs))
    await call.answer()


@router.callback_query(F.data.startswith("report:proj:"), ReportForm.project)
async def process_project_callback(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    proj_id = int(call.data.split(":")[2])
    from bot.database.models import Project
    res = await session.execute(select(Project).where(Project.id == proj_id))
    p = res.scalar_one_or_none()
    if not p: return await call.answer("Проект не найден")
    
    await state.update_data(project=p.name, project_id=p.id)
    await call.message.edit_text(f"✅ Проект: <b>{p.name}</b>", parse_mode="HTML")
    
    name_to_use = db_user.pretty_name
    
    # Auto-fill for employees
    if db_user.role == UserRole.employee:
        await state.update_data(employee_name=name_to_use)
        return await _finalize_step(call.message, state, db_user, session,
            "Шаг 5/14 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)

    await _finalize_step(call.message, state, db_user, session,
        f"Шаг 4/14 — <b>Фамилия сотрудника</b>\n"
        f"Предложение: «{name_to_use}»\n"
        "Нажмите /use_name чтобы использовать, или введите вручную:",
        ReportForm.employee_name)
    await call.answer()


@router.message(F.text == "/use_name", ReportForm.employee_name)
async def use_suggested_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    name_to_use = db_user.pretty_name
    await state.update_data(employee_name=name_to_use)
    await _finalize_step(message, state, db_user, session,
        "Шаг 5/14 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)


@router.message(ReportForm.employee_name)
async def process_employee_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    name = message.text.strip()
    if len(name) < 2 or name.isdigit():
        await message.answer(
            "❌ Введите корректную <b>фамилию</b> сотрудника (минимум 2 символа, не число).\n"
            f"Или нажмите /use_name чтобы использовать <b>{db_user.pretty_name}</b>.",
            parse_mode="HTML"
        )
        return
    await state.update_data(employee_name=name)
    await _finalize_step(message, state, db_user, session,
        "Шаг 5/13 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)


# ——— Step 4: Shift count ——————————————————————————————————————————————————

@router.message(ReportForm.shift_count)
async def process_shift_count(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if not (1 <= n <= 20):
            await message.answer("❌ Введите число от 1 до 20:")
            return
    except ValueError:
        await message.answer("❌ Введите целое число (например: 3):")
        return
    await state.update_data(shift_count=n)
    if n > 1:
        # Ask for partners but do NOT touch employee_name yet
        await message.answer(
            f"👥 <b>Совместная смена ({n} чел.)</b>\n\n"
            "📌 <b>Правила сдачи:</b>\n"
            "• Отчёт сдает <b>только один</b> из вас\n"
            "• Введите фамилии остальных сотрудников\n"
            "• Общий доход (22%) будет рассчитан на всех\n"
            "• В конце вы увидите <b>общую сумму</b> для кассы ✅",
            parse_mode="HTML"
        )
        await state.set_state(ReportForm.partners)
        await message.answer("👥 Введите <b>фамилии напарников</b> (через пробел или запятую):", 
                             reply_markup=kb_report_nav())
        return

    # If n=1, ensure partners are cleared
    await state.update_data(partners=None)
    await _finalize_step(message, state, db_user, session,
        "Шаг 6/14 — <b>Общая выручка</b> (BYN, только число):", ReportForm.revenue)


@router.message(ReportForm.partners)
async def process_partners(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    partners_text = message.text.strip()
    await state.update_data(partners=partners_text)
    
    # We do NOT combine names into employee_name here anymore.
    # We keep them separate in the state (employee_name + partners).
    
    await _finalize_step(message, state, db_user, session,
        "Шаг 6/14 — <b>Общая выручка</b> (BYN, только число):", ReportForm.revenue)

def _clean_num(text: str) -> float:
    return float(text.strip().replace(" ", "").replace(",", "."))


async def _ask_number(message: Message, state: FSMContext, db_user: User, session: AsyncSession,
                       key: str, next_state: State, next_prompt: str, max_val: float = 10_000_000):
    try:
        v = _clean_num(message.text)
        if v < 0: raise ValueError
        if v > max_val:
            await message.answer(f"❌ Значение слишком большое (лимит {_fmt(max_val)} BYN). Проверьте ввод:")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 15000):")
        return
    await state.update_data(**{key: v})
    await _finalize_step(message, state, db_user, session, next_prompt, next_state)


# ——— Steps 5–10: Numeric fields ———————————————————————————————————————————

@router.message(ReportForm.revenue)
async def process_revenue(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "revenue", ReportForm.cash,
                      "Шаг 7/14 — <b>Наличные</b> (BYN):")


@router.message(ReportForm.cash)
async def process_cash(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "cash", ReportForm.acquiring,
                      "Шаг 8/14 — <b>Эквайринг (безнал)</b> (BYN):")


@router.message(ReportForm.acquiring)
async def process_acquiring(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        v = _clean_num(message.text)
        if v < 0: raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное число:")
        return

    data = await state.get_data()
    revenue = data["revenue"]
    cash = data["cash"]

    if abs((cash + v) - revenue) > 0.01:
        await message.answer(
            f"❌ <b>Ошибка в сумме!</b>\n\n"
            f"Выручка: {_fmt(revenue)} BYN\n"
            f"Наличные: {_fmt(cash)} BYN\n"
            f"Эквайринг: {_fmt(v)} BYN\n\n"
            f"Сумма ({_fmt(cash+v)} BYN) не совпадает с выручкой. "
            "Пожалуйста, введите корректное значение эквайринга или напишите /cancel и начните заново:",
            parse_mode="HTML"
        )
        return

    await state.update_data(acquiring=v)
    await _finalize_step(message, state, db_user, session, "Шаг 9/14 — <b>Хоз расход</b> (BYN):", ReportForm.expense)


@router.message(ReportForm.expense)
async def process_expense(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "expense", ReportForm.trainee_salary,
                      "Шаг 10/14 — <b>Зарплата стажёра</b> (BYN, 0 если нет):")


@router.message(ReportForm.trainee_salary)
async def process_trainee_salary(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "trainee_salary", ReportForm.cash_balance,
                      "Шаг 11/14 — <b>Остаток в кассе</b> (BYN):")


@router.message(ReportForm.cash_balance)
async def process_cash_balance(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "cash_balance", ReportForm.visitors,
                      "Шаг 12/14 — <b>Проходимость (кол-во посетителей)</b>:", max_val=1_000_000)


@router.message(ReportForm.visitors)
async def process_visitors(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if not (0 <= n <= 10000):
            await message.answer("❌ Введите число от 0 до 10 000:")
            return
    except ValueError:
        await message.answer("❌ Введите целое число:")
        return
    await state.update_data(visitors=n)
    await _finalize_step(message, state, db_user, session, "Шаг 13/14 — <b>Количество дней рождений</b>:", ReportForm.birthdays)


@router.message(ReportForm.birthdays)
async def process_birthdays(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    try:
        n = int(message.text.strip())
        if n < 0: raise ValueError
        data = await state.get_data()
        if n > data["visitors"]:
            await message.answer(f"❌ Дней рождений ({n}) не может быть больше, чем посетителей ({data['visitors']}). Исправьте число:")
            return
        if n > 1000:
            await message.answer("❌ Слишком много дней рождений. Проверьте число:")
            return
    except ValueError:
        await message.answer("❌ Введите целое число (0 если нет):")
        return
    await state.update_data(birthdays=n)
    await _finalize_step(message, state, db_user, session,
                         "Шаг 14/14 — <b>Комментарий</b>\nНапишите что-нибудь (или Нажмите «Пропустить»):",
                         ReportForm.comment, kb=kb_cancel_skip())


# ——— Step 12: Comment —————————————————————————————————————————————————————

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


# ——— Confirm preview ——————————————————————————————————————————————————————

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
    period_str = "день" if plan.period == "day" else "месяц"
    return (
        f"🎯 План ({period_str}):     <b>{_fmt(plan.plan_amount)} BYN</b>\n"
        f"📈 Факт:              <b>{_fmt(revenue)} BYN</b>\n"
        f"✅ Выполнение:        <b>{pct:.0f}%</b>"
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
    total_salary = salary * d["shift_count"]
    
    # Combined name for display
    display_name = d['employee_name']
    if d.get("partners"):
        display_name += f" + {d['partners']}"

    text = (
        "📋 <b>Проверьте данные отчёта:</b>\n\n"
        f"📅 Дата:              <b>{date_str}</b>\n"
        f"🏙️ Город:              <b>{city_label}</b>\n"
        f"🎭 Проект:            <b>{d['project']}</b>\n"
        f"👤 Сотрудник:         <b>{display_name}</b>\n"
        f"👥 Чел. в смене:      <b>{d['shift_count']}</b>\n\n"
        f"💰 Выручка:           <b>{_fmt(d['revenue'])} BYN</b>\n"
        f"💵 Наличные:          <b>{_fmt(d['cash'])} BYN</b>\n"
        f"💳 Эквайринг:         <b>{_fmt(d['acquiring'])} BYN</b>\n"
        f"📉 Хоз расход:        <b>{_fmt(d['expense'])} BYN</b>\n"
        f"🎓 ЗП стажёра:       <b>{_fmt(d['trainee_salary'])} BYN</b>\n"
        f"🏦 Остаток в кассе:   <b>{_fmt(d['cash_balance'])} BYN</b>\n"
        f"👣 Посетители:        <b>{d['visitors']}</b>\n"
        f"🎂 Дней рождений:     <b>{d['birthdays']}</b>\n"
        f"💬 Комментарий:       <b>{d.get('comment') or '—'}</b>\n\n"
        f"────────────────\n"
        f"📊 Шкала: <i>{sal_desc}</i>\n"
        f"💸 <b>ЗП на человека: {_fmt(salary)} BYN</b>\n"
        f"💰 <b>ИТОГО (на всех): {_fmt(total_salary)} BYN</b>\n\n"
        "Всё верно?"
    )
    await state.update_data(salary=salary, salary_level=1)
    await state.set_state(ReportForm.confirm)
    await msg.answer(text, parse_mode="HTML", reply_markup=kb_confirm(is_editing=is_editing))


# ——— Confirm callbacks ————————————————————————————————————————————————————

@router.callback_query(F.data == "report:confirm", ReportForm.confirm)
async def confirm_report(call: CallbackQuery, state: FSMContext, db_user: User,
                         session: AsyncSession, bot: Bot):
    d = await state.get_data()
    await state.clear()

    edit_id = d.get("admin_editing_report_id")
    
    # Final combined name for DB
    full_name = d["employee_name"]
    if d.get("partners"):
        full_name = f"{full_name} + {d['partners']}"

    if edit_id:
        res = await session.execute(select(Report).where(Report.id == edit_id))
        report = res.scalar_one()
        report.date = datetime.fromisoformat(d["date"]).date()
        report.project_name = d["project"]
        report.employee_name = full_name
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
            employee_name=full_name,
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
        await call.message.answer("✅ Отчёт успешно отредактирован и сохранён!", reply_markup=_menu(db_user.role.value))
        await call.answer()
        return

    await call.message.answer(
        f"✅ Отчет принят!{plan_part}\n\n",
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

    # Forward to shared city chat (in the correct topic thread per city)
    if config.city_chat_id:
        report_city = d.get("city", "")
        thread_id = None
        if report_city == "gomel":
            thread_id = config.city_thread_gomel
        elif report_city == "minsk":
            thread_id = config.city_thread_minsk
        try:
            await bot.send_message(
                config.city_chat_id,
                fwd,
                parse_mode="HTML",
                message_thread_id=thread_id,
            )
        except Exception:
            pass

    await call.answer()


@router.callback_query(F.data == "report:restart", ReportForm.confirm)
async def restart_report(call: CallbackQuery, state: FSMContext, db_user: User):
    d = await state.get_data()
    if d.get("admin_editing_report_id"):
        return await call.answer("Недоступно при редактировании", show_alert=True)
    await state.clear()
    await call.message.edit_reply_markup()
    today = date.today().strftime("%d.%m.%Y")
    await state.set_state(ReportForm.date)
    await call.message.answer(
        "🔄 Начинаем заново.\n\nШаг 1/14 — <b>Дата смены</b>:",
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

    await call.message.answer("❌ Отменено.", reply_markup=_menu(db_user.role.value))
    await call.answer()


@router.callback_query(F.data == "report:edit")
async def edit_report_menu(call: CallbackQuery):
    await call.message.edit_text("Выберите поле для редактирования:", reply_markup=kb_edit_fields())
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
        "date": (ReportForm.date, "<b>Дата смены</b> (ДД.ММ.ГГГГ):"),
        "project": (ReportForm.project, "<b>Название проекта</b>:"),
        "employee_name": (ReportForm.employee_name, "<b>Фамилия сотрудника</b>:"),
        "shift_count": (ReportForm.shift_count, "<b>Количество человек в смене</b>:"),
        "revenue": (ReportForm.revenue, "<b>Общая выручка</b> (BYN):"),
        "cash": (ReportForm.cash, "<b>Наличные</b> (BYN):"),
        "acquiring": (ReportForm.acquiring, "<b>Эквайринг (безнал)</b> (BYN):"),
        "expense": (ReportForm.expense, "<b>Хоз расход</b> (BYN):"),
        "trainee_salary": (ReportForm.trainee_salary, "<b>Зарплата стажёра</b> (BYN):"),
        "cash_balance": (ReportForm.cash_balance, "<b>Остаток в кассе</b> (BYN):"),
        "visitors": (ReportForm.visitors, "<b>Проходимость (чел)</b>:"),
        "birthdays": (ReportForm.birthdays, "<b>Количество дней рождений</b>:"),
        "comment": (ReportForm.comment, "<b>Комментарий</b>:"),
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
        
    await call.message.edit_text(f"Редактирование: {prompt}", parse_mode="HTML", reply_markup=kb)
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
async def back_report(call: CallbackQuery, state: FSMContext, db_user: User):
    data = await state.get_data()
    if data.get("admin_editing_report_id"):
        # When editing, Back from ANYWHERE (including confirm) goes to edit fields menu
        await state.set_state(ReportForm.confirm) # To ensure edit menu logic works
        from bot.keyboards.builders import kb_edit_fields
        await call.message.edit_text("Выберите поле для редактирования:", reply_markup=kb_edit_fields())
        return await call.answer()

    curr = await state.get_state()
    if not curr:
        return await call.answer()
    
    # State mapping for "Back" button
    prev_map = {
        ReportForm.city: (ReportForm.date, "Шаг 1/14 — <b>Дата смены</b>:\nНажмите «Сегодня» или введите ДД.ММ.ГГГГ:"),
        ReportForm.project: (ReportForm.city, "Шаг 2/14 — <b>Город</b>\nВыберите город:"),
        ReportForm.employee_name: (ReportForm.project, "Шаг 3/14 — <b>Название проекта</b>:"),
        ReportForm.shift_count: (ReportForm.employee_name, "Шаг 4/14 — <b>Фамилия сотрудника</b>:"),
        ReportForm.revenue: (ReportForm.shift_count, "Шаг 5/14 — <b>Количество человек в смене</b>:"),
        ReportForm.cash: (ReportForm.revenue, "Шаг 6/14 — <b>Общая выручка</b> (BYN):"),
        ReportForm.acquiring: (ReportForm.cash, "Шаг 7/14 — <b>Наличные</b> (BYN):"),
        ReportForm.expense: (ReportForm.acquiring, "Шаг 8/14 — <b>Эквайринг (безнал)</b> (BYN):"),
        ReportForm.trainee_salary: (ReportForm.expense, "Шаг 9/14 — <b>Хоз расход</b> (BYN):"),
        ReportForm.cash_balance: (ReportForm.trainee_salary, "Шаг 10/14 — <b>Зарплата стажёра</b> (BYN):"),
        ReportForm.visitors: (ReportForm.cash_balance, "Шаг 11/14 — <b>Остаток в кассе</b> (BYN):"),
        ReportForm.birthdays: (ReportForm.visitors, "Шаг 12/14 — <b>Проходимость (чел)</b>:"),
        ReportForm.comment: (ReportForm.birthdays, "Шаг 13/14 — <b>Количество дней рождений</b>:"),
        ReportForm.confirm: (ReportForm.comment, "Шаг 14/14 — <b>Комментарий</b> (или пропустить):"),
    }
    
    target = prev_map.get(curr)
    if not target:
        await call.answer("Дальше некуда", show_alert=True)
        return
    
    prev_state, prompt = target
    
    # If going back to employee_name but user is employee, skip back further to project
    if prev_state == ReportForm.employee_name and db_user.role == UserRole.employee:
        target = prev_map.get(ReportForm.employee_name)
        if target:
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


# ——— Helper ———————————————————————————————————————————————————————————————

def _build_admin_notification(d: dict, db_user: User, plan_line: str | None = None) -> str:
    report_date = datetime.fromisoformat(d["date"]).strftime("%d.%m.%Y")
    plan_block = f"\n{plan_line}\n" if plan_line else ""
    # Build employee display: show partners if joint shift
    employee_display = d.get("employee_name", "—")
    if d.get("partners"):
        employee_display += f" + {d['partners']}"
    # Show submitter separately only if they differ from the employee
    submitter_line = ""
    if db_user.pretty_name.lower() not in employee_display.lower():
        submitter_line = f"📨 Сдал:           {db_user.pretty_name}\n"
    return (
        f"📋 <b>Новый отчёт!</b>\n\n"
        f"👤 Сотрудник:      {employee_display}\n"
        f"{submitter_line}"
        f"📅 Дата:           {report_date}\n"
        f"🎭 Проект:         {d['project']}\n"
        f"👥 Чел. в смене:   {d['shift_count']}\n\n"
        f"💰 Выручка:        {_fmt(d['revenue'])} BYN\n"
        f"💵 Наличные:       {_fmt(d['cash'])} BYN\n"
        f"💳 Эквайринг:      {_fmt(d['acquiring'])} BYN\n"
        f"📉 Расход:         {_fmt(d['expense'])} BYN\n"
        f"🏦 Остаток:        {_fmt(d['cash_balance'])} BYN\n"
        f"👣 Посетители:     {d['visitors']}\n"
        f"🎂 Дней рождений:  {d['birthdays']}\n"
        f"💬 Комментарий:    {d.get('comment') or '—'}\n"
        f"{plan_block}\n"
        f"💸 Выплачено ЗП:   {_fmt(d['salary'])} BYN (ур.{d['salary_level']})"
    )

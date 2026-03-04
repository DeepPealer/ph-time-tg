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
    menu_employee, menu_admin, kb_city
)
from bot.utils.salary import calculate_photographer_salary, CITY_LABELS
from bot.config import config

router = Router()


class ReportForm(StatesGroup):
    date          = State()
    project       = State()
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
    return menu_admin() if role == "admin" else menu_employee()


# ─── Entry ────────────────────────────────────────────────────────────────────

@router.message(F.text == "📋 Сдать отчет")
async def start_report(message: Message, state: FSMContext, db_user: User):
    if not db_user.is_active:
        await message.answer("⛔ У вас нет доступа. Обратитесь к администратору.")
        return
    await state.clear()
    today = date.today().strftime("%d.%m.%Y")
    await state.set_state(ReportForm.date)
    await message.answer(
        "📋 <b>Сдача отчёта</b>\n\n"
        "Шаг 1/12 — <b>Дата смены</b>\n"
        "Нажмите «Сегодня» или введите дату в формате <code>ДД.ММ.ГГГГ</code>:",
        parse_mode="HTML",
        reply_markup=kb_use_today(today)
    )


# ─── Step 1: Date ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "report:use_today", ReportForm.date)
async def use_today(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(date=date.today().isoformat())
    await call.message.edit_text("✅ Дата: <b>сегодня</b>", parse_mode="HTML")
    await _finalize_step(call.message, state, db_user, session,
                         "Шаг 2/12 — <b>Название проекта</b>\nВведите название:", ReportForm.project)
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
    await _finalize_step(message, state, db_user, session, 
                         f"✅ Дата: <b>{d.strftime('%d.%m.%Y')}</b>\n\nШаг 2/12 — <b>Название проекта</b>\nВведите название:",
                         ReportForm.project)


# ─── Step 2: Project ──────────────────────────────────────────────────────────

@router.message(ReportForm.project)
async def process_project(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(project=message.text.strip())
    # If user has a default city, skip the city step
    if db_user.city:
        await state.update_data(city=db_user.city)
        city_label = CITY_LABELS.get(db_user.city, db_user.city)
        suggested = db_user.full_name
        await _finalize_step(message, state, db_user, session,
            f"✅ Город: <b>{city_label}</b>\n\nШаг 3/13 — <b>Фамилия сотрудника</b>\n"
            f"Предложение: «{suggested}»\n"
            "Нажмите /use_name чтобы использовать, или введите вручную:",
            ReportForm.employee_name)
    else:
        await _finalize_step(message, state, db_user, session,
            "Шаг 3/13 — <b>Город</b>\nВыберите город:",
            ReportForm.city, kb=kb_city())


# ─── Step 3 (optional): City ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("report:city:"), ReportForm.city)
async def process_city(call: CallbackQuery, state: FSMContext, db_user: User, session: AsyncSession):
    city = call.data.split(":")[2]  # 'gomel' or 'minsk'
    await state.update_data(city=city)
    city_label = CITY_LABELS.get(city, city)
    suggested = db_user.full_name
    await call.message.edit_text(f"✅ Город: <b>{city_label}</b>", parse_mode="HTML")
    await _finalize_step(call.message, state, db_user, session,
        f"Шаг 4/13 — <b>Фамилия сотрудника</b>\n"
        f"Предложение: «{suggested}»\n"
        "Нажмите /use_name чтобы использовать, или введите вручную:",
        ReportForm.employee_name)
    await call.answer()


@router.message(F.text == "/use_name", ReportForm.employee_name)
async def use_suggested_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(employee_name=db_user.full_name)
    await _finalize_step(message, state, db_user, session,
        "Шаг 5/13 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)


@router.message(ReportForm.employee_name)
async def process_employee_name(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await state.update_data(employee_name=message.text.strip())
    await _finalize_step(message, state, db_user, session,
        "Шаг 5/13 — <b>Количество человек в смене</b> (1-20):", ReportForm.shift_count)


# ─── Step 4: Shift count ──────────────────────────────────────────────────────

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
    await _finalize_step(message, state, db_user, session,
        "Шаг 6/13 — <b>Общая выручка</b> (₽, только число):", ReportForm.revenue)


# ─── Helper for numeric steps ─────────────────────────────────────────────────

def _clean_num(text: str) -> float:
    return float(text.strip().replace(" ", "").replace(",", "."))


async def _ask_number(message: Message, state: FSMContext, db_user: User, session: AsyncSession,
                       key: str, next_state: State, next_prompt: str, max_val: float = 10_000_000):
    try:
        v = _clean_num(message.text)
        if v < 0: raise ValueError
        if v > max_val:
            await message.answer(f"❌ Значение слишком большое (лимит {_fmt(max_val)} ₽). Проверьте ввод:")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 15000):")
        return
    await state.update_data(**{key: v})
    await _finalize_step(message, state, db_user, session, next_prompt, next_state)


# ─── Steps 5–10: Numeric fields ───────────────────────────────────────────────

@router.message(ReportForm.revenue)
async def process_revenue(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "revenue", ReportForm.cash,
                      "Шаг 7/13 — <b>Наличные</b> (₽):")


@router.message(ReportForm.cash)
async def process_cash(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "cash", ReportForm.acquiring,
                      "Шаг 8/13 — <b>Эквайринг (безнал)</b> (₽):")


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
            f"Выручка: {_fmt(revenue)} ₽\n"
            f"Наличные: {_fmt(cash)} ₽\n"
            f"Эквайринг: {_fmt(v)} ₽\n\n"
            f"Сумма ({_fmt(cash+v)} ₽) не совпадает с выручкой. "
            "Пожалуйста, введите корректное значение эквайринга или напишите /cancel и начните заново:",
            parse_mode="HTML"
        )
        return

    await state.update_data(acquiring=v)
    await _finalize_step(message, state, db_user, session, "Шаг 9/14 — <b>Хоз расход</b> (₽):", ReportForm.expense)


@router.message(ReportForm.expense)
async def process_expense(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "expense", ReportForm.trainee_salary,
                      "Шаг 10/14 — <b>Зарплата стажера</b> (₽, 0 если нет):")


@router.message(ReportForm.trainee_salary)
async def process_trainee_salary(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    await _ask_number(message, state, db_user, session, "trainee_salary", ReportForm.cash_balance,
                      "Шаг 11/14 — <b>Остаток в кассе</b> (₽):")


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


# ─── Step 12: Comment ─────────────────────────────────────────────────────────

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


# ─── Confirm preview ──────────────────────────────────────────────────────────

async def _get_plan_line(session: AsyncSession, project: str, revenue: float) -> str | None:
    """Find active plan for project or global, return formatted fulfillment line."""
    res = await session.execute(
        select(Plan).where(
            Plan.is_active == True,
            or_(Plan.project_name == project, Plan.project_name == None)
        ).order_by(Plan.project_name.nulls_last())  # project-specific first
    )
    plan = res.scalars().first()
    if not plan:
        return None
    pct = (revenue / plan.plan_amount * 100) if plan.plan_amount else 0
    period_str = "день" if plan.period == "day" else "месяц"
    return (
        f"🎯 План ({period_str}):     <b>{_fmt(plan.plan_amount)} ₽</b>\n"
        f"📈 Факт:              <b>{_fmt(revenue)} ₽</b>\n"
        f"✅ Выполнение:        <b>{pct:.0f}%</b>"
    )


async def _show_confirm(msg: Message, state: FSMContext, session: AsyncSession):
    d = await state.get_data()
    city = d.get("city", "gomel")
    report_date = datetime.fromisoformat(d["date"]).date()
    weekday = report_date.weekday()  # 0=Mon, 6=Sun
    salary, sal_desc = calculate_photographer_salary(d["revenue"], d["shift_count"], city, weekday)
    plan_line = await _get_plan_line(session, d["project"], d["revenue"])

    date_str = report_date.strftime("%d.%m.%Y")
    city_label = CITY_LABELS.get(city, city)
    plan_block = f"\n{plan_line}\n" if plan_line else ""
    text = (
        "📋 <b>Проверьте данные отчёта:</b>\n\n"
        f"📅 Дата:              <b>{date_str}</b>\n"
        f"🏙 Город:              <b>{city_label}</b>\n"
        f"🎪 Проект:            <b>{d['project']}</b>\n"
        f"👤 Сотрудник:         <b>{d['employee_name']}</b>\n"
        f"👥 Чел. в смене:      <b>{d['shift_count']}</b>\n\n"
        f"💰 Выручка:           <b>{_fmt(d['revenue'])} ₽</b>\n"
        f"💵 Наличные:          <b>{_fmt(d['cash'])} ₽</b>\n"
        f"💳 Эквайринг:         <b>{_fmt(d['acquiring'])} ₽</b>\n"
        f"📉 Хоз расход:        <b>{_fmt(d['expense'])} ₽</b>\n"
        f"🧑‍🎓 ЗП стажера:       <b>{_fmt(d['trainee_salary'])} ₽</b>\n"
        f"🏖 Остаток в кассе:   <b>{_fmt(d['cash_balance'])} ₽</b>\n"
        f"👣 Посетители:        <b>{d['visitors']}</b>\n"
        f"🎂 Дней рождений:     <b>{d['birthdays']}</b>\n"
        f"💬 Комментарий:       <b>{d.get('comment') or '—'}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━"
        f"{plan_block}\n"
        f"📊 Шкала: <i>{sal_desc}</i>\n"
        f"💸 <b>Ваша ЗП за смену: {_fmt(salary)} ₽</b>\n\n"
        "Всё верно?"
    )
    await state.update_data(salary=salary, salary_level=1)
    await state.set_state(ReportForm.confirm)
    await msg.answer(text, parse_mode="HTML", reply_markup=kb_confirm())


# ─── Confirm callbacks ────────────────────────────────────────────────────────

@router.callback_query(F.data == "report:confirm", ReportForm.confirm)
async def confirm_report(call: CallbackQuery, state: FSMContext, db_user: User,
                         session: AsyncSession, bot: Bot):
    d = await state.get_data()
    await state.clear()

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
    )
    session.add(report)
    await session.commit()

    plan_line = await _get_plan_line(session, d["project"], d["revenue"])

    await call.message.edit_reply_markup()
    plan_part = f"\n{plan_line}" if plan_line else ""
    await call.message.answer(
        f"✅ Отчёт принят!{plan_part}\n\n"
        f"💸 <b>Возьми из кассы: {_fmt(d['salary'])} ₽</b>",
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
    await state.clear()
    await call.message.edit_reply_markup()
    today = date.today().strftime("%d.%m.%Y")
    await state.set_state(ReportForm.date)
    await call.message.answer(
        "🔄 Начинаем заново.\n\nШаг 1/12 — <b>Дата смены</b>:",
        parse_mode="HTML",
        reply_markup=kb_use_today(today)
    )
    await call.answer()


@router.callback_query(F.data == "report:cancel")
async def cancel_report(call: CallbackQuery, state: FSMContext, db_user: User):
    await state.clear()
    await call.message.edit_reply_markup()
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
async def jump_to_edit(call: CallbackQuery, state: FSMContext):
    field = call.data.split(":")[1]
    
    # Map field names to states and prompts
    field_map = {
        "date": (ReportForm.date, "<b>Дата смены</b> (ДД.ММ.ГГГГ):"),
        "project": (ReportForm.project, "<b>Название проекта</b>:"),
        "employee_name": (ReportForm.employee_name, "<b>Фамилия сотрудника</b>:"),
        "shift_count": (ReportForm.shift_count, "<b>Количество человек в смене</b>:"),
        "revenue": (ReportForm.revenue, "<b>Общая выручка</b> (₽):"),
        "cash": (ReportForm.cash, "<b>Наличные</b> (₽):"),
        "acquiring": (ReportForm.acquiring, "<b>Эквайринг (безнал)</b> (₽):"),
        "expense": (ReportForm.expense, "<b>Хоз расход</b> (₽):"),
        "trainee_salary": (ReportForm.trainee_salary, "<b>Зарплата стажера</b> (₽):"),
        "cash_balance": (ReportForm.cash_balance, "<b>Остаток в кассе</b> (₽):"),
        "visitors": (ReportForm.visitors, "<b>Проходимость (чел)</b>:"),
        "birthdays": (ReportForm.birthdays, "<b>Количество дней рождений</b>:"),
        "comment": (ReportForm.comment, "<b>Комментарий</b>:"),
    }
    
    target_state, prompt = field_map[field]
    await state.set_state(target_state)
    
    # We add a special flag so that after editing we return to preview if we were there
    await state.update_data(editing_from_preview=True)
    
    kb = kb_report_nav()
    if target_state == ReportForm.date:
        kb = kb_use_today(date.today().strftime("%d.%m.%Y"))
    elif target_state == ReportForm.comment:
        kb = kb_cancel_skip()
        
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
async def back_report(call: CallbackQuery, state: FSMContext):
    curr = await state.get_state()
    if not curr:
        return await call.answer()
    
    # State mapping for "Back" button
    prev_map = {
        ReportForm.project: (ReportForm.date, "Шаг 1/12 — <b>Дата смены</b>:\nНажмите «Сегодня» или введите ДД.ММ.ГГГГ:"),
        ReportForm.employee_name: (ReportForm.project, "Шаг 2/12 — <b>Название проекта</b>\nВведите название:"),
        ReportForm.shift_count: (ReportForm.employee_name, "Шаг 3/12 — <b>Фамилия сотрудника</b>:"),
        ReportForm.revenue: (ReportForm.shift_count, "Шаг 4/12 — <b>Количество человек в смене</b>:"),
        ReportForm.cash: (ReportForm.revenue, "Шаг 5/12 — <b>Общая выручка</b> (₽):"),
        ReportForm.acquiring: (ReportForm.cash, "Шаг 6/12 — <b>Наличные</b> (₽):"),
        ReportForm.expense: (ReportForm.acquiring, "Шаг 7/12 — <b>Эквайринг (безнал)</b> (₽):"),
        ReportForm.cash_balance: (ReportForm.expense, "Шаг 8/12 — <b>Расход</b> (₽):"),
        ReportForm.visitors: (ReportForm.cash_balance, "Шаг 9/12 — <b>Остаток в кассе</b> (₽):"),
        ReportForm.birthdays: (ReportForm.visitors, "Шаг 10/12 — <b>Проходимость (чел)</b>:"),
        ReportForm.comment: (ReportForm.birthdays, "Шаг 11/12 — <b>Количество дней рождений</b>:"),
        ReportForm.confirm: (ReportForm.comment, "Шаг 12/12 — <b>Комментарий</b> (или пропустить):"),
    }
    
    target = prev_map.get(curr)
    if not target:
        await call.answer("Дальше некуда", show_alert=True)
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


# ─── Helper ───────────────────────────────────────────────────────────────────

def _build_admin_notification(d: dict, db_user: User, plan_line: str | None = None) -> str:
    report_date = datetime.fromisoformat(d["date"]).strftime("%d.%m.%Y")
    plan_block = f"\n{plan_line}\n" if plan_line else ""
    return (
        f"📋 <b>Новый отчёт!</b>\n\n"
        f"👤 От: {db_user.full_name}\n"
        f"📅 Дата:           {report_date}\n"
        f"🏪 Проект:         {d['project']}\n"
        f"👥 Чел. в смене:   {d['shift_count']}\n\n"
        f"💰 Выручка:        {_fmt(d['revenue'])} ₽\n"
        f"💵 Наличные:       {_fmt(d['cash'])} ₽\n"
        f"💳 Эквайринг:      {_fmt(d['acquiring'])} ₽\n"
        f"📉 Расход:         {_fmt(d['expense'])} ₽\n"
        f"🏦 Остаток:        {_fmt(d['cash_balance'])} ₽\n"
        f"👣 Посетители:     {d['visitors']}\n"
        f"🎂 Дней рождений:  {d['birthdays']}\n"
        f"💬 Комментарий:    {d.get('comment') or '—'}\n"
        f"{plan_block}\n"
        f"💸 Выплачено ЗП:   {_fmt(d['salary'])} ₽ (ур.{d['salary_level']})"
    )

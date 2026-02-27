from datetime import date, timedelta
from calendar import monthrange

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from bot.database.models import User, UserRole, SalarySetting, Plan, Report
from bot.keyboards.builders import (
    kb_admin_main, kb_report_period, kb_employee_list, kb_employee_actions,
    kb_salary_levels, kb_plans, kb_back, kb_analytics, menu_admin
)
from bot.utils.excel import generate_excel_report
from bot.utils.salary import get_salary_levels, salary_level_description
from bot.utils.logging import log_action
from bot.utils.charts import generate_revenue_chart, generate_plan_performance_chart

router = Router()


class AdminForm(StatesGroup):
    add_emp_id        = State()
    custom_start      = State()
    custom_end        = State()
    sal_edit_id       = State()  # stores level DB id in state data
    sal_edit_values   = State()
    plan_project      = State()
    plan_amount       = State()
    plan_period       = State()
    adj_amount        = State()  # For bonus/fine
    adj_reason        = State()


def _require_admin(db_user: User) -> bool:
    return db_user.role == UserRole.admin and db_user.is_active


# ─── Entry ────────────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Админ-панель")
async def show_admin_panel(message: Message, db_user: User, state: FSMContext):
    if not _require_admin(db_user):
        await message.answer("⛔ Нет доступа.")
        return
    await state.clear()
    await message.answer("⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
                         parse_mode="HTML", reply_markup=kb_admin_main())


# ─── Back ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, db_user: User, state: FSMContext):
    await state.clear()
    await call.message.edit_text("⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
                                 parse_mode="HTML", reply_markup=kb_admin_main())
    await call.answer()


# ─── Reports / Excel ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:reports")
async def adm_reports(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return await call.answer("Нет доступа", show_alert=True)
    await call.message.edit_text("📊 <b>Выгрузка отчёта</b>\n\nВыберите период:",
                                 parse_mode="HTML", reply_markup=kb_report_period())
    await call.answer()


async def _send_excel(call: CallbackQuery, session: AsyncSession, start: date, end: date):
    await call.message.edit_text(f"⏳ Генерирую отчёт за {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}…")
    data = await generate_excel_report(session, start, end)
    fname = f"report_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.xlsx"
    await call.message.answer_document(
        BufferedInputFile(data, filename=fname),
        caption=f"📊 Отчёт: {start.strftime('%d.%m.%Y')} – {end.strftime('%d.%m.%Y')}"
    )
    await call.message.delete()


@router.callback_query(F.data == "period:cur_month")
async def period_cur_month(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    today = date.today()
    start = today.replace(day=1)
    await _send_excel(call, session, start, today)
    await call.answer()


@router.callback_query(F.data == "period:prev_month")
async def period_prev_month(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    today = date.today()
    first = today.replace(day=1) - timedelta(days=1)
    start = first.replace(day=1)
    end   = first
    await _send_excel(call, session, start, end)
    await call.answer()


@router.callback_query(F.data == "period:cur_year")
async def period_cur_year(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    today = date.today()
    start = today.replace(month=1, day=1)
    await _send_excel(call, session, start, today)
    await call.answer()


@router.callback_query(F.data == "period:custom")
async def period_custom(call: CallbackQuery, state: FSMContext, db_user: User):
    if not _require_admin(db_user): return
    await state.set_state(AdminForm.custom_start)
    await call.message.edit_text(
        "📝 Введите <b>начало</b> периода (ДД.ММ.ГГГГ):",
        parse_mode="HTML", reply_markup=kb_back()
    )
    await call.answer()


@router.message(AdminForm.custom_start)
async def adm_custom_start(message: Message, state: FSMContext):
    try:
        d = _parse_date(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:")
        return
    await state.update_data(custom_start=d.isoformat())
    await state.set_state(AdminForm.custom_end)
    await message.answer("📝 Введите <b>конец</b> периода (ДД.ММ.ГГГГ):", parse_mode="HTML")


@router.message(AdminForm.custom_end)
async def adm_custom_end(message: Message, state: FSMContext, session: AsyncSession, db_user: User, bot: Bot):
    try:
        end = _parse_date(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:")
        return
    d = await state.get_data()
    start = date.fromisoformat(d["custom_start"])
    await state.clear()
    data = await generate_excel_report(session, start, end)
    fname = f"report_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.xlsx"
    await message.answer_document(
        BufferedInputFile(data, filename=fname),
        caption=f"📊 Отчёт: {start.strftime('%d.%m.%Y')} – {end.strftime('%Y%m%d')}",
        reply_markup=menu_admin()
    )


# ─── Employees ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:employees")
async def adm_employees(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(
        select(User).where(User.role != UserRole.pending).order_by(User.full_name)
    )
    employees = res.scalars().all()
    await call.message.edit_text(
        f"👥 <b>Сотрудники</b> ({len(employees)} чел.)\n\nВыберите для управления:",
        parse_mode="HTML", reply_markup=kb_employee_list(employees)
    )
    await call.answer()


@router.callback_query(F.data.startswith("emp:view:"))
async def emp_view(call: CallbackQuery, session: AsyncSession):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    emp = res.scalar_one_or_none()
    if not emp:
        await call.answer("Не найден", show_alert=True); return
    role_str = {"admin": "Администратор", "employee": "Сотрудник"}.get(emp.role.value, emp.role.value)
    text = (
        f"👤 <b>{emp.full_name}</b>\n"
        f"📎 @{emp.username or '—'}\n"
        f"🆔 {emp.telegram_id}\n"
        f"🎭 Роль: {role_str}\n"
        f"✅ Активен: {'Да' if emp.is_active else 'Нет'}"
    )
    await call.message.edit_text(text, parse_mode="HTML",
                                 reply_markup=kb_employee_actions(tg_id, emp.role.value))
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
        await message.answer(f"✅ {user.full_name} теперь сотрудник!", reply_markup=menu_admin())
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
        await call.message.edit_text(f"✅ {emp.full_name} назначен администратором.",
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
        await call.message.edit_text(f"✅ {emp.full_name} теперь сотрудник.",
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
        await call.message.edit_text(f"🗑 {emp.full_name} лишён доступа.",
                                     reply_markup=kb_back("adm:employees"))
    await call.answer("Удалён")


# ─── Pending users ────────────────────────────────────────────────────────────

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
        text += f"• {u.full_name} (@{u.username or '—'}) — <code>{u.telegram_id}</code>\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_back())
    await call.answer()


@router.callback_query(F.data.startswith("pending:ok:"))
async def pending_approve(call: CallbackQuery, session: AsyncSession, bot: Bot):
    tg_id = int(call.data.split(":")[2])
    res = await session.execute(select(User).where(User.telegram_id == tg_id))
    u = res.scalar_one_or_none()
    if u:
        u.role = UserRole.employee; u.is_active = True
        await session.commit()
        await call.message.edit_reply_markup()
        await call.message.answer(f"✅ {u.full_name} одобрен как сотрудник.")
        try:
            await bot.send_message(tg_id, "🎉 Ваш доступ одобрен! Напишите /start")
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
        await call.message.answer(f"🗑 Заявка от {u.full_name} отклонена.")
        try:
            await bot.send_message(tg_id, "❌ Ваш запрос на доступ отклонён.")
        except Exception: pass
    await call.answer("Отклонено")


# ─── Salary settings ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:salary")
async def adm_salary(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    levels = await get_salary_levels(session)
    lines = "\n".join(f"• {salary_level_description(l)}" for l in levels)
    await call.message.edit_text(
        f"💰 <b>Шкала ЗП</b>\n\n{lines}\n\nВыберите уровень для редактирования:",
        parse_mode="HTML", reply_markup=kb_salary_levels(levels)
    )
    await call.answer()


@router.callback_query(F.data.startswith("sal:edit:"))
async def sal_edit_prompt(call: CallbackQuery, state: FSMContext):
    lvl_id = int(call.data.split(":")[2])
    await state.update_data(sal_edit_id=lvl_id)
    await state.set_state(AdminForm.sal_edit_values)
    await call.message.edit_text(
        "✏️ Введите новые параметры уровня одной строкой:\n\n"
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


# ─── Plans ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:plans")
async def adm_plans(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(select(Plan).order_by(Plan.project_name))
    plans = res.scalars().all()
    text = "🎯 <b>Планы продаж</b>\n\nНажмите для вкл/выкл или добавьте новый:"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb_plans(plans))
    await call.answer()


@router.callback_query(F.data.startswith("plan:toggle:"))
async def plan_toggle(call: CallbackQuery, session: AsyncSession):
    plan_id = int(call.data.split(":")[2])
    res = await session.execute(select(Plan).where(Plan.id == plan_id))
    plan = res.scalar_one_or_none()
    if plan:
        plan.is_active = not plan.is_active
        await session.commit()
    res2 = await session.execute(select(Plan).order_by(Plan.project_name))
    plans = res2.scalars().all()
    await call.message.edit_reply_markup(reply_markup=kb_plans(plans))
    await call.answer("Изменено")


@router.callback_query(F.data.startswith("plan:delete:"))
async def plan_delete(call: CallbackQuery, session: AsyncSession):
    plan_id = int(call.data.split(":")[2])
    res = await session.execute(select(Plan).where(Plan.id == plan_id))
    plan = res.scalar_one_or_none()
    if plan:
        await session.delete(plan)
        await session.commit()
    
    res2 = await session.execute(select(Plan).order_by(Plan.project_name))
    plans = res2.scalars().all()
    await call.message.edit_reply_markup(reply_markup=kb_plans(plans))
    await call.answer("План удален")


@router.callback_query(F.data == "plan:add")
async def plan_add_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminForm.plan_project)
    await call.message.edit_text(
        "➕ <b>Добавить план</b>\n\n"
        "Введите название проекта (или «все» для общего плана):",
        parse_mode="HTML", reply_markup=kb_back("adm:plans")
    )
    await call.answer()


@router.message(AdminForm.plan_project)
async def plan_add_project(message: Message, state: FSMContext):
    project = None if message.text.strip().lower() == "все" else message.text.strip()
    await state.update_data(plan_project=project)
    await state.set_state(AdminForm.plan_amount)
    await message.answer("Введите <b>сумму плана</b> (₽):", parse_mode="HTML")


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
    session.add(Plan(project_name=d["plan_project"], plan_amount=d["plan_amount"], period=period))
    await session.commit()
    await state.clear()
    proj_str = d["plan_project"] or "Все проекты"
    period_str = "день" if period == "day" else "месяц"
    await message.answer(
        f"✅ План добавлен: {proj_str} — {d['plan_amount']:.0f}₽ / {period_str}",
        reply_markup=menu_admin()
    )


# ─── Plan stats ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return

    today = date.today()
    month_start = today.replace(day=1)

    res = await session.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.project_name)
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

    lines = ["📈 <b>Статистика выполнения планов</b>\n"]

    for plan in plans:
        proj_label = plan.project_name or "Все проекты"
        period_label = "день" if plan.period == "day" else "месяц"
        period_start = today if plan.period == "day" else month_start

        # Build filter: project-specific or global (sum all projects)
        proj_filter = (
            Report.project_name == plan.project_name
            if plan.project_name
            else True  # global plan — sum everything
        )

        rev_res = await session.execute(
            select(func.coalesce(func.sum(Report.revenue), 0.0))
            .where(
                Report.date >= period_start,
                Report.date <= today,
                proj_filter,
            )
        )
        actual = float(rev_res.scalar())
        pct = (actual / plan.plan_amount * 100) if plan.plan_amount else 0
        bar = _progress_bar(pct)

        lines.append(
            f"🏪 <b>{proj_label}</b> ({period_label})\n"
            f"   План:    <b>{actual:,.0f} / {plan.plan_amount:,.0f} ₽</b>\n"
            f"   {bar} <b>{pct:.0f}%</b>\n"
        )

    lines.append(f"\n🗓 По состоянию на: {today.strftime('%d.%m.%Y')}")

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await call.answer()


def _progress_bar(pct: float, width: int = 10) -> str:
    filled = min(int(pct / 100 * width), width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


# ─── Debt / Payroll ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:debt")
async def adm_debt(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    
    # Query unpaid reports
    stmt_rep = (
        select(User.telegram_id, User.full_name, func.sum(Report.salary_paid))
        .join(Report, User.id == Report.user_id)
        .where(Report.is_paid == False)
        .group_by(User.telegram_id, User.full_name)
    )
    res_rep = await session.execute(stmt_rep)
    unpaid_rep = {r[0]: {"name": r[1], "amount": r[2]} for r in res_rep.all()}

    # Query unpaid adjustments
    from bot.database.models import Adjustment
    stmt_adj = (
        select(User.telegram_id, User.full_name, func.sum(Adjustment.amount))
        .join(Adjustment, User.id == Adjustment.user_id)
        .where(Adjustment.is_paid == False)
        .group_by(User.telegram_id, User.full_name)
    )
    res_adj = await session.execute(stmt_adj)
    unpaid_adj = {r[0]: {"name": r[1], "amount": r[2]} for r in res_adj.all()}

    # Merge
    all_tg_ids = set(unpaid_rep.keys()).union(unpaid_adj.keys())
    merged = []
    for tid in all_tg_ids:
        name = unpaid_rep.get(tid, unpaid_adj.get(tid))["name"]
        total = unpaid_rep.get(tid, {}).get("amount", 0) + unpaid_adj.get(tid, {}).get("amount", 0)
        if total != 0:
            merged.append((tid, name, total))
    
    if not merged:
        await call.message.edit_text("✅ Все зарплаты и премии выплачены!", reply_markup=kb_back())
        return

    await call.message.edit_text(
        "💸 <b>Задолженность по зарплате</b>\n(отчеты + премии/штрафы)",
        parse_mode="HTML",
        reply_markup=kb_debt_list(merged)
    )
    await call.answer()


@router.callback_query(F.data.startswith("debt:view:"))
async def debt_view_user(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    
    stmt_rep = select(Report).join(User).where(User.telegram_id == tg_id, Report.is_paid == False).order_by(Report.date)
    res_rep = await session.execute(stmt_rep)
    reports = res_rep.scalars().all()
    
    from bot.database.models import Adjustment
    stmt_adj = select(Adjustment).join(User).where(User.telegram_id == tg_id, Adjustment.is_paid == False).order_by(Adjustment.date)
    res_adj = await session.execute(stmt_adj)
    adjs = res_adj.scalars().all()
    
    total = sum(r.salary_paid for r in reports) + sum(a.amount for a in adjs)
    name = reports[0].employee_name if reports else adjs[0].user.full_name
    
    lines = [f"👤 <b>{name}</b>\nИТОГО к выплате: <b>{total:,.0f} ₽</b>\n"]
    
    if reports:
        lines.append("📅 <b>Отчеты:</b>")
        for r in reports:
            lines.append(f"▫️ {r.date.strftime('%d.%m.%Y')}: {r.salary_paid:,.0f} ₽")
    
    if adjs:
        lines.append("\n💰 <b>Корректировки:</b>")
        for a in adjs:
            label = "Премия" if a.amount > 0 else "Штраф"
            lines.append(f"▫️ {a.date.strftime('%d.%m.%Y')} {label}: {a.amount:,.0f} ₽ ({a.reason})")
    
    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=kb_debt_actions(tg_id)
    )
    await call.answer()


@router.callback_query(F.data.startswith("debt:payall:"))
async def debt_pay_all(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    
    # Mark reports
    stmt_rep = select(Report).join(User).where(User.telegram_id == tg_id, Report.is_paid == False)
    res_rep = await session.execute(stmt_rep)
    reports = res_rep.scalars().all()
    for r in reports:
        r.is_paid = True
        r.payment_date = datetime.now()
        
    # Mark adjustments
    from bot.database.models import Adjustment
    stmt_adj = select(Adjustment).join(User).where(User.telegram_id == tg_id, Adjustment.is_paid == False)
    res_adj = await session.execute(stmt_adj)
    adjs = res_adj.scalars().all()
    for a in adjs:
        a.is_paid = True
    
    total = sum(r.salary_paid for r in reports) + sum(a.amount for a in adjs)
    
    await log_action(session, db_user.id, "Выплата ЗП", f"Сотрудник ID {tg_id}, Сумма: {total} ₽, Отчетов: {len(reports)}, Корр: {len(adjs)}")
    await session.commit()
    
    await call.answer(f"✅ Выплачено {total:,.0f} ₽", show_alert=True)
    await adm_debt(call, session, db_user)


# ─── Adjustments (Bonus/Fine) ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emp:adj:"))
async def emp_adj_start(call: CallbackQuery, state: FSMContext, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    await state.update_data(adj_user_tg_id=tg_id)
    await call.message.edit_text(
        "💰 <b>Премия или Штраф</b>\n\nВведите сумму (положительная — премия, отрицательная — штраф):\nНапример: 1000 или -500",
        parse_mode="HTML",
        reply_markup=kb_back()
    )
    await state.set_state(AdminForm.adj_amount)
    await call.answer()


@router.message(AdminForm.adj_amount)
async def process_adj_amount(message: Message, state: FSMContext):
    try:
        val = float(message.text.strip().replace(" ", "").replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите корректное число:")
        return
    await state.update_data(adj_amount=val)
    await message.answer("Введите причину (кратко):")
    await state.set_state(AdminForm.adj_reason)


@router.message(AdminForm.adj_reason)
async def process_adj_reason(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    data = await state.get_data()
    tg_id = data["adj_user_tg_id"]
    amount = data["adj_amount"]
    reason = message.text.strip()
    
    from bot.database.models import Adjustment
    
    stmt = select(User).where(User.telegram_id == tg_id)
    res = await session.execute(stmt)
    target_user = res.scalar_one()
    
    adj = Adjustment(
        user_id=target_user.id,
        amount=amount,
        reason=reason,
        date=date.today()
    )
    session.add(adj)
    await log_action(session, db_user.id, "Добавлена корректировка", f"User: {target_user.full_name}, Amount: {amount}, Reason: {reason}")
    await session.commit()
    
    label = "Премия" if amount > 0 else "Штраф"
    await message.answer(f"✅ {label} ({amount:,.0f} ₽) начислена {target_user.full_name}.", reply_markup=menu_admin())
    await state.clear()


# ─── Analytics / Charts ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:analytics")
async def adm_analytics(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("📊 <b>Аналитика и Графики</b>\n\nВыберите тип визуализации:",
                                 parse_mode="HTML", reply_markup=kb_analytics())
    await call.answer()


@router.callback_query(F.data == "chart:revenue")
async def chart_revenue(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("⏳ Генерирую график выручки…")
    
    buf = await generate_revenue_chart(session, days=30)
    if not buf:
        await call.message.edit_text("❌ Нет данных для построения графика.", reply_markup=kb_analytics())
        return
    
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="revenue.png"),
        caption="📈 <b>Выручка за последние 30 дней</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, "Просмотр графика выручки")
    await call.answer()


@router.callback_query(F.data == "chart:plans")
async def chart_plans(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("⏳ Генерирую график выполнения планов…")
    
    buf = await generate_plan_performance_chart(session)
    if not buf:
        await call.message.edit_text("❌ Нет данных по планам продаж.", reply_markup=kb_analytics())
        return
    
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="plans.png"),
        caption="🎯 <b>Выполнение планов продаж</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, "Просмотр графика планов")
    await call.answer()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(text: str) -> date:
    from datetime import datetime
    return datetime.strptime(text.strip(), "%d.%m.%Y").date()

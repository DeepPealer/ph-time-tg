from datetime import date, timedelta
from calendar import monthrange
import html

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from bot.database.models import User, UserRole, SalarySetting, Plan, Report, ManagementExpense
from bot.keyboards.builders import (
    kb_admin_main, kb_report_period, kb_employee_list, kb_employee_actions,
    kb_salary_levels, kb_plans, kb_back, kb_analytics, menu_admin,
    kb_city_for_employee, kb_month_select, kb_monthly_report_cities
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
    mgmt_date         = State()
    mgmt_category     = State()
    mgmt_amount       = State()
    mgmt_comment      = State()


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
    try:
        await call.message.edit_text("📊 <b>Выгрузка отчёта</b>\n\nВыберите период:",
                                     parse_mode="HTML", reply_markup=kb_report_period())
    except Exception as e:
        await call.message.answer(f"❌ Ошибка: {html.escape(str(e))}")
    await call.answer()



@router.callback_query(F.data == "period:monthly_calendar")
async def period_monthly_calendar(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    today = date.today()
    await call.message.edit_text(
        "📅 <b>Выберите месяц для отчёта:</b>",
        parse_mode="HTML",
        reply_markup=kb_month_select(today.year, today.month)
    )
    await call.answer()



# ─── Employees ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:employees")
async def adm_employees(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    res = await session.execute(
        select(User).where(User.role != UserRole.pending).order_by(User.full_name)
    )
    employees = res.scalars().all()
    
    from collections import defaultdict
    by_city = defaultdict(list)
    for e in employees:
        by_city[e.city].append(e)
    
    await call.message.edit_text(
        f"👥 <b>Сотрудники</b> ({len(employees)} чел.)\n\nВыберите для управления:",
        parse_mode="HTML", reply_markup=kb_employee_list(by_city)
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
    city_str = {"gomel": "🏙 Гомель", "minsk": "🌆 Минск"}.get(emp.city or "", "❓ не задан")
    text = (
        f"👤 <b>{emp.full_name}</b>\n"
        f"📎 @{emp.username or '—'}\n"
        f"🆔 {emp.telegram_id}\n"
        f"🎭 Роль: {role_str}\n"
        f"🏙 Город: {city_str}\n"
        f"✅ Активен: {'Да' if emp.is_active else 'Нет'}"
    )
    await call.message.edit_text(text, parse_mode="HTML",
                                 reply_markup=kb_employee_actions(emp.telegram_id, emp.role.value, emp.city))
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


# ─── Employee City ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("emp:setcity:"))
async def emp_setcity_prompt(call: CallbackQuery, db_user: User):
    if not _require_admin(db_user): return
    tg_id = int(call.data.split(":")[2])
    await call.message.edit_text(
        "🏙 <b>Выберите город для сотрудника:</b>\n"
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
            f"✅ Город сотрудника <b>{emp.full_name}</b> установлен: <b>{city_label}</b>",
            parse_mode="HTML", reply_markup=kb_back(f"emp:view:{tg_id}")
        )
    await call.answer("Сохранено")


# ─── Salary settings (legacy placeholder) ─────────────────────────────────────

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


# ─── Manager Salary ───────────────────────────────────────────────────────────

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
                city_label = {"gomel": "🏙 ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌍 ОБЩИЕ")
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
                        f"🏪 {proj_label}\n"
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
    await call.message.edit_text("🏙 Выберите город для плана:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.plan_city)
async def plan_add_city(call: CallbackQuery, state: FSMContext):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        return await adm_plans(call, None, None) # session and user not needed for simple back
    
    await state.update_data(plan_city=city if city != "none" else None)
    await state.set_state(AdminForm.plan_project)
    await call.message.edit_text(
        "📝 Введите название проекта (например 'Бассейн')\nили 0 для общего плана на город:",
        reply_markup=kb_back("adm:plans")
    )
    await call.answer()


@router.message(AdminForm.plan_project)
async def plan_add_project(message: Message, state: FSMContext):
    project = None if message.text.strip().lower() == "все" or message.text.strip() == "0" else message.text.strip()
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
    session.add(Plan(
        city=d["plan_city"],
        project_name=d["plan_project"],
        plan_amount=d["plan_amount"],
        period=period
    ))
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
            city_label = {"gomel": "🏙 ГОМЕЛЬ", "minsk": "🌆 МИНСК"}.get(city, "🌍 ОБЩИЕ")
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

        lines.append(f"\n🗓 По состоянию на: {today.strftime('%d.%m.%Y')}")

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


# ─── Debt / Payroll REMOVED (as requested) ───────────────────────────────────





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


@router.callback_query(F.data == "chart:revenue_year")
async def chart_revenue_year(call: CallbackQuery, session: AsyncSession, db_user: User):
    if not _require_admin(db_user): return
    await call.message.edit_text("⏳ Генерирую годовой график…")
    
    buf = await generate_yearly_revenue_chart(session)
    if not buf:
        await call.message.edit_text("❌ Нет данных для построения годового графика.", reply_markup=kb_analytics())
        return
    
    await call.message.answer_photo(
        BufferedInputFile(buf.getvalue(), filename="revenue_year.png"),
        caption=f"📊 <b>Выручка по месяцам за {date.today().year} год</b>",
        parse_mode="HTML"
    )
    await call.message.delete()
    await log_action(session, db_user.id, "Просмотр годового графика выручки")
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


# ─── Monthly Calendar Report ───────────────────────────────────────────────────

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
    await call.message.edit_text(
        f"📅 <b>Месячный отчёт — {city.title()}</b>\n\nВыберите месяц:",
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
        await call.message.answer(f"❌ Ошибка генерации: {html.escape(str(e))}\n\nПроверьте логи сервера.", reply_markup=menu_admin())
    await call.answer()


# ─── Management Expenses (Расходник / Аренда / Техника) ───────────────────────

@router.callback_query(F.data == "adm:mgmt_expenses")
async def adm_mgmt_expenses(call: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext):
    if not _require_admin(db_user): return
    await state.set_state(AdminForm.mgmt_city)
    from bot.keyboards.builders import kb_city
    await call.message.edit_text("🏙 Выберите город для расхода:", reply_markup=kb_city())
    await call.answer()


@router.callback_query(AdminForm.mgmt_city)
async def mgmt_city_select(call: CallbackQuery, state: FSMContext):
    city = call.data.split(":")[2]
    if city == "cancel":
        await state.clear()
        return await show_admin_panel(call.message, None, state) # will clear state but menu needs role
    
    await state.update_data(mgmt_city=city if city != "none" else None)
    await state.set_state(AdminForm.mgmt_date)
    from bot.keyboards.builders import kb_use_today
    today_str = date.today().strftime("%d.%m.%Y")
    await call.message.edit_text(
        f"📅 Введите <b>дату</b> расхода (ДД.ММ.ГГГГ):",
        parse_mode="HTML", reply_markup=kb_use_today(today_str)
    )
    await call.answer()


@router.callback_query(AdminForm.mgmt_date, F.data == "report:use_today")
async def mgmt_date_today(call: CallbackQuery, state: FSMContext):
    await state.update_data(mgmt_date=date.today().isoformat())
    await mgmt_ask_category(call.message, state)
    await call.answer()


@router.message(AdminForm.mgmt_date)
async def mgmt_date_input(message: Message, state: FSMContext):
    try:
        d = _parse_date(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ:"); return
    await state.update_data(mgmt_date=d.isoformat())
    await mgmt_ask_category(message, state)


async def mgmt_ask_category(message: Message, state: FSMContext):
    from bot.keyboards.builders import kb_mgmt_categories
    await state.set_state(AdminForm.mgmt_category)
    await message.answer("📂 Выберите категорию расхода:", reply_markup=kb_mgmt_categories())


@router.callback_query(AdminForm.mgmt_category, F.data.startswith("mgmt:cat:"))
async def mgmt_category_select(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[2]
    await state.update_data(mgmt_category=cat)
    await state.set_state(AdminForm.mgmt_amount)
    await call.message.edit_text(f"💰 Введите <b>сумму</b> ({cat}):", parse_mode="HTML", reply_markup=kb_back())
    await call.answer()


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
    await state.update_data(mgmt_comment=None)
    await mgmt_save(call.message, state, session, db_user)
    await call.answer()


@router.message(AdminForm.mgmt_comment)
async def mgmt_comment_input(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    await state.update_data(mgmt_comment=message.text.strip())
    await mgmt_save(message, state, session, db_user)


async def mgmt_save(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    d = await state.get_data()
    expense = ManagementExpense(
        date=date.fromisoformat(d["mgmt_date"]),
        city=d["mgmt_city"],
        category=d["mgmt_category"],
        amount=d["mgmt_amount"],
        comment=d.get("mgmt_comment")
    )
    session.add(expense)
    await log_action(session, db_user.id, "Добавлен управл. расход", f"{d['mgmt_category']}: {d['mgmt_amount']} р")
    await session.commit()
    await state.clear()
    await message.answer("✅ Управленческий расход сохранён!", reply_markup=menu_admin())

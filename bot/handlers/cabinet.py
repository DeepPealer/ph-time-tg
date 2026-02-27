from datetime import date, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func

from bot.database.models import User, Report, Adjustment
from bot.keyboards.builders import kb_cabinet_main

router = Router()

@router.message(F.text == "👤 Личный кабинет")
async def show_cabinet(message: Message, db_user: User):
    await message.answer(
        f"👤 <b>Личный кабинет: {db_user.full_name}</b>\n\n"
        "Здесь вы можете посмотреть свою статистику и историю выплат.",
        parse_mode="HTML",
        reply_markup=kb_cabinet_main()
    )

@router.callback_query(F.data == "cab:stats")
async def cab_stats(call: CallbackQuery, session: "AsyncSession", db_user: User):
    today = date.today()
    start_of_month = today.replace(day=1)
    
    # Reports sum (all this month)
    stmt_month = select(func.sum(Report.salary_paid)).where(
        Report.user_id == db_user.id,
        Report.date >= start_of_month
    )
    res_month = await session.execute(stmt_month)
    total_month = res_month.scalar() or 0.0
    
    # Unpaid balance (reports + adjustments)
    stmt_unpaid_rep = select(func.sum(Report.salary_paid)).where(
        Report.user_id == db_user.id,
        Report.is_paid == False
    )
    res_unpaid_rep = await session.execute(stmt_unpaid_rep)
    unpaid_rep = res_unpaid_rep.scalar() or 0.0
    
    stmt_unpaid_adj = select(func.sum(Adjustment.amount)).where(
        Adjustment.user_id == db_user.id,
        Adjustment.is_paid == False
    )
    res_unpaid_adj = await session.execute(stmt_unpaid_adj)
    unpaid_adj = res_unpaid_adj.scalar() or 0.0
    
    balance = unpaid_rep + unpaid_adj
    
    msg = (
        f"📊 <b>Ваша статистика</b>\n\n"
        f"📈 Заработано в этом месяце: <b>{total_month:,.0f} ₽</b>\n"
        f"💸 Текущий баланс к выплате: <b>{balance:,.0f} ₽</b>\n"
        f"   (отчеты: {unpaid_rep:,.0f}, корректировки: {unpaid_adj:,.0f})\n\n"
        f"🗓 Данные на {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=kb_cabinet_main())
    await call.answer()

@router.callback_query(F.data == "cab:history")
async def cab_history(call: CallbackQuery, session: "AsyncSession", db_user: User):
    # Fetch last 10 paid reports
    stmt = select(Report).where(
        Report.user_id == db_user.id,
        Report.is_paid == True
    ).order_by(Report.payment_date.desc()).limit(10)
    
    res = await session.execute(stmt)
    reports = res.scalars().all()
    
    if not reports:
        await call.answer("История выплат пуста", show_alert=True)
        return
    
    lines = ["📜 <b>Последние выплаты:</b>\n"]
    for r in reports:
        pdate = r.payment_date.strftime("%d.%m.%Y") if r.payment_date else "?"
        lines.append(f"▫️ {pdate}: <b>{r.salary_paid:,.0f} ₽</b> ({r.date.strftime('%d.%m')})")
        
    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb_cabinet_main())
    await call.answer()

@router.callback_query(F.data == "cab:close")
async def cab_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

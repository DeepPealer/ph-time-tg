from datetime import date, datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, Report
from bot.keyboards.builders import kb_cabinet_main

router = Router()

from bot.database.models import UserRole

@router.message(F.text == "ðŸ‘¤ Ð›Ð¸Ñ‡Ð½Ñ‹Ð¹ ÐºÐ°Ð±Ð¸Ð½ÐµÑ‚")
async def show_cabinet(message: Message, db_user: User):
    if db_user.role != UserRole.admin:
        await message.answer("â›” ÐÐµÑ‚ Ð´Ð¾ÑÑ‚ÑƒÐ¿Ð°.")
        return

    await message.answer(
        f"ðŸ‘¤ <b>Ð›Ð¸Ñ‡Ð½Ñ‹Ð¹ ÐºÐ°Ð±Ð¸Ð½ÐµÑ‚: {db_user.full_name}</b>\n\n"
        "Ð—Ð´ÐµÑÑŒ Ð²Ñ‹ Ð¼Ð¾Ð¶ÐµÑ‚Ðµ Ð¿Ð¾ÑÐ¼Ð¾Ñ‚Ñ€ÐµÑ‚ÑŒ ÑÐ²Ð¾ÑŽ ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÑƒ Ð¸ Ð¸ÑÑ‚Ð¾Ñ€Ð¸ÑŽ Ð²Ñ‹Ð¿Ð»Ð°Ñ‚.",
        parse_mode="HTML",
        reply_markup=kb_cabinet_main()
    )

@router.callback_query(F.data == "cab:stats")
async def cab_stats(call: CallbackQuery, session: AsyncSession, db_user: User):
    today = date.today()
    start_of_month = today.replace(day=1)
    
    # Reports sum (all this month)
    stmt_month = select(func.sum(Report.salary_paid)).where(
        Report.user_id == db_user.id,
        Report.date >= start_of_month
    )
    res_month = await session.execute(stmt_month)
    total_month = res_month.scalar() or 0.0
    
    msg = (
        f"ðŸ“Š <b>Ð’Ð°ÑˆÐ° ÑÑ‚Ð°Ñ‚Ð¸ÑÑ‚Ð¸ÐºÐ°</b>\n\n"
        f"ðŸ“ˆ Ð—Ð°Ñ€Ð°Ð±Ð¾Ñ‚Ð°Ð½Ð¾ Ð² ÑÑ‚Ð¾Ð¼ Ð¼ÐµÑÑÑ†Ðµ: <b>{total_month:,.0f} â‚½</b>\n\n"
        f"ðŸ—“ Ð”Ð°Ð½Ð½Ñ‹Ðµ Ð½Ð° {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await call.message.edit_text(msg, parse_mode="HTML", reply_markup=kb_cabinet_main())
    await call.answer()

@router.callback_query(F.data == "cab:history")
async def cab_history(call: CallbackQuery, session: AsyncSession, db_user: User):
    # Fetch last 10 paid reports
    stmt = select(Report).where(
        Report.user_id == db_user.id,
        Report.is_paid == True
    ).order_by(Report.payment_date.desc()).limit(10)
    
    res = await session.execute(stmt)
    reports = res.scalars().all()
    
    if not reports:
        await call.answer("Ð˜ÑÑ‚Ð¾Ñ€Ð¸Ñ Ð²Ñ‹Ð¿Ð»Ð°Ñ‚ Ð¿ÑƒÑÑ‚Ð°", show_alert=True)
        return
    
    lines = ["ðŸ“œ <b>ÐŸÐ¾ÑÐ»ÐµÐ´Ð½Ð¸Ðµ Ð²Ñ‹Ð¿Ð»Ð°Ñ‚Ñ‹:</b>\n"]
    for r in reports:
        pdate = r.payment_date.strftime("%d.%m.%Y") if r.payment_date else "?"
        lines.append(f"â–«ï¸ {pdate}: <b>{r.salary_paid:,.0f} â‚½</b> ({r.date.strftime('%d.%m')})")
        
    await call.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb_cabinet_main())
    await call.answer()

@router.callback_query(F.data == "cab:close")
async def cab_close(call: CallbackQuery):
    await call.message.delete()
    await call.answer()



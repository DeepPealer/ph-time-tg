import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from sqlalchemy import select

from bot.database.db import SessionLocal
from bot.database.models import User, UserRole, Report
from bot.keyboards.builders import menu_employee

logger = logging.getLogger(__name__)

async def send_report_reminders(bot: Bot):
    """Notify employees who haven't submitted a report today."""
    logger.info("Running daily report reminders...")
    
    async with SessionLocal() as session:
        # 1. Get all active employees
        stmt_users = select(User).where(
            User.role != UserRole.pending,
            User.is_active == True
        )
        res_users = await session.execute(stmt_users)
        users = res_users.scalars().all()
        
        # 2. Get users who ALREADY submitted today
        today = date.today()
        stmt_reports = select(Report.user_id).where(Report.date == today)
        res_reports = await session.execute(stmt_reports)
        submitted_ids = set(res_reports.scalars().all())
        
        # 3. Filter and send
        count = 0
        for user in users:
            if user.id not in submitted_ids:
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "ðŸ”” <b>ÐÐ°Ð¿Ð¾Ð¼Ð¸Ð½Ð°Ð½Ð¸Ðµ!</b>\n\nÐ’Ñ‹ ÐµÑ‰Ðµ Ð½Ðµ ÑÐ´Ð°Ð»Ð¸ ÑÐµÐ³Ð¾Ð´Ð½ÑÑˆÐ½Ð¸Ð¹ Ð¾Ñ‚Ñ‡ÐµÑ‚. ÐŸÐ¾Ð¶Ð°Ð»ÑƒÐ¹ÑÑ‚Ð°, ÑÐ´ÐµÐ»Ð°Ð¹Ñ‚Ðµ ÑÑ‚Ð¾ Ð´Ð¾ ÐºÐ¾Ð½Ñ†Ð° Ð´Ð½Ñ.",
                        parse_mode="HTML",
                        reply_markup=menu_employee()
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to send reminder to {user.telegram_id}: {e}")
        
        logger.info(f"Reminders sent to {count} users.")

def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    
    # Schedule daily reminder at 20:00 (8 PM)
    scheduler.add_job(send_report_reminders, 'cron', hour=20, minute=0, args=[bot])
    
    return scheduler


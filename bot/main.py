import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import config
from bot.database.db import init_db
from bot.middlewares.auth import DatabaseMiddleware
from bot.handlers import common, report, admin, cabinet
from bot.utils.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Initializing databaseâ€¦")
    await init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register middleware on all updates
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Register routers (order matters â€” common first for global commands)
    dp.include_router(common.router)
    dp.include_router(report.router)
    dp.include_router(admin.router)
    dp.include_router(cabinet.router)

    logger.info("Starting schedulerâ€¦")
    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info("Starting botâ€¦")
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logger.error(f"Ð‘Ð¾Ñ‚ ÑƒÐ¿Ð°Ð» Ñ Ð¾ÑˆÐ¸Ð±ÐºÐ¾Ð¹: {e}. ÐŸÐµÑ€ÐµÐ·Ð°Ð¿ÑƒÑÐº Ñ‡ÐµÑ€ÐµÐ· 5 ÑÐµÐºÑƒÐ½Ð´â€¦")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


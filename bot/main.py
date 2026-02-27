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
    logger.info("Initializing database…")
    await init_db()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register middleware on all updates
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Register routers (order matters — common last so FSM states take priority)
    dp.include_router(report.router)
    dp.include_router(admin.router)
    dp.include_router(cabinet.router)
    dp.include_router(common.router)

    logger.info("Starting scheduler…")
    scheduler = setup_scheduler(bot)
    scheduler.start()

    logger.info("Starting bot…")
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            logger.error(f"Бот упал с ошибкой: {e}. Перезапуск через 5 секунд…")
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

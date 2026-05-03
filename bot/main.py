import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
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
    logger.info("Initializing database")
    await init_db()

    # Auto-detect proxy if not set manually
    proxy_url = config.proxy_url
    if not proxy_url:
        logger.info("PROXY_URL not set, trying to auto-find a working proxy...")
        from bot.utils.proxy_finder import find_working_proxy
        proxy_url = await find_working_proxy()
        if proxy_url:
            logger.info(f"Auto-selected proxy: {proxy_url}")
        else:
            logger.info("No proxy found, connecting directly to Telegram.")

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=AiohttpSession(proxy=proxy_url) if proxy_url else None,
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register middleware on all updates
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())

    # Register routers (order matters — common first for global commands)
    dp.include_router(common.router)
    dp.include_router(report.router)
    dp.include_router(admin.router)
    dp.include_router(cabinet.router)

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


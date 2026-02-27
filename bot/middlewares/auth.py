from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from bot.database.models import User, UserRole
from bot.database.db import SessionLocal
from bot.config import config


class DatabaseMiddleware(BaseMiddleware):
    """Opens a DB session per request and handles user registration."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        async with SessionLocal() as session:
            data["session"] = session
            db_user = None

            if tg_user:
                res = await session.execute(
                    select(User).where(User.telegram_id == tg_user.id)
                )
                db_user = res.scalar_one_or_none()
                is_new = db_user is None

                if is_new:
                    db_user = User(
                        telegram_id=tg_user.id,
                        username=tg_user.username,
                        full_name=tg_user.full_name or f"User_{tg_user.id}",
                        role=UserRole.pending,
                        is_active=False,
                    )
                    session.add(db_user)
                    await session.commit()
                    await session.refresh(db_user)
                    data["is_new_user"] = True
                else:
                    # Keep name in sync
                    if tg_user.full_name and tg_user.full_name != db_user.full_name:
                        db_user.full_name = tg_user.full_name
                        await session.commit()
                    data["is_new_user"] = False

                # Auto-promote pre-configured admins
                if tg_user.id in config.admin_ids and (
                    db_user.role != UserRole.admin or not db_user.is_active
                ):
                    db_user.role = UserRole.admin
                    db_user.is_active = True
                    await session.commit()
                    await session.refresh(db_user)

            data["db_user"] = db_user
            return await handler(event, data)

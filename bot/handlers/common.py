from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from bot.database.models import User, UserRole
from bot.keyboards.builders import menu_employee, menu_admin, kb_pending_user
from bot.config import config

router = Router()


def _get_menu(role: str):
    return menu_admin() if role == "admin" else menu_employee()


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, is_new_user: bool, bot: Bot, session):
    if db_user.role == UserRole.pending:
        await message.answer(
            "👋 Привет! Ваша заявка на доступ отправлена администратору.\n"
            "Ожидайте подтверждения."
        )
        # Notify all admins
        admins = await session.execute(
            select(User).where(User.role == UserRole.admin, User.is_active == True)
        )
        admin_mention = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
        text = (
            f"📥 <b>Новая заявка на доступ!</b>\n\n"
            f"👤 Имя: {db_user.full_name}\n"
            f"📎 Аккаунт: {admin_mention}\n"
            f"🆔 Telegram ID: <code>{db_user.telegram_id}</code>"
        )
        for admin in admins.scalars().all():
            try:
                await bot.send_message(
                    admin.telegram_id, text,
                    parse_mode="HTML",
                    reply_markup=kb_pending_user(db_user.telegram_id)
                )
            except Exception:
                pass

        if config.admin_chat_id:
            try:
                await bot.send_message(config.admin_chat_id, text, parse_mode="HTML",
                                        reply_markup=kb_pending_user(db_user.telegram_id))
            except Exception:
                pass
        return

    name = db_user.full_name.split()[0] if db_user.full_name else "!"
    role_label = "Администратор" if db_user.role == UserRole.admin else "Сотрудник"
    await message.answer(
        f"👋 Привет, {name}! ({role_label})\n\nВыберите действие:",
        reply_markup=_get_menu(db_user.role.value)
    )


@router.message(Command("help"))
async def cmd_help(message: Message, db_user: User):
    await message.answer(
        "ℹ️ <b>Справка</b>\n\n"
        "• <b>Сдать отчет</b> — пошаговое заполнение ежедневного отчёта\n"
        "• <b>Админ-панель</b> — управление командой, отчёты, настройки ЗП\n\n"
        "Для отмены любого действия отправьте /cancel",
        parse_mode="HTML",
        reply_markup=_get_menu(db_user.role.value) if db_user.is_active else None
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: User):
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("✅ Действие отменено.", reply_markup=_get_menu(db_user.role.value))
    else:
        await message.answer("Нет активного действия.", reply_markup=_get_menu(db_user.role.value))

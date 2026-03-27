from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, UserRole
from bot.keyboards.builders import menu_employee, menu_manager, menu_admin, kb_pending_user
from bot.config import config

router = Router()


class NameInputForm(StatesGroup):
    waiting_name = State()


def _get_menu(role: str):
    if role == "admin":
        return menu_admin()
    if role == "manager":
        return menu_manager()
    return menu_employee()


# ─── /start ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, is_new_user: bool, bot: Bot,
                    session, state: FSMContext):
    await state.clear()

    # New or pending user without a display_name → ask for their name
    if db_user.role == UserRole.pending and not db_user.display_name:
        await state.set_state(NameInputForm.waiting_name)
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Введите свою <b>фамилию</b>, чтобы руководство могло вас идентифицировать:\n"
            "<i>(Например: Иванов)</i>",
            parse_mode="HTML"
        )
        return

    # Pending but name already given — just wait
    if db_user.role == UserRole.pending:
        await message.answer(
            "⏳ Ваша заявка отправлена администратору.\n"
            "Ожидайте подтверждения."
        )
        return

    name = db_user.display_name or db_user.full_name.split()[0]
    role_labels = {
        "admin": "Администратор",
        "manager": "Управляющий",
        "employee": "Сотрудник",
    }
    role_label = role_labels.get(db_user.role.value, "")
    await message.answer(
        f"👋 Привет, {name}! ({role_label})\n\nВыберите действие:",
        reply_markup=_get_menu(db_user.role.value)
    )


# ─── Name input FSM ──────────────────────────────────────────────────────────

@router.message(NameInputForm.waiting_name)
async def process_name_input(message: Message, state: FSMContext, db_user: User,
                               bot: Bot, session):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Слишком коротко. Введите фамилию:")
        return
    if len(name) > 100:
        await message.answer("❌ Слишком длинно. Попробуйте ещё раз:")
        return

    db_user.display_name = name
    await session.commit()
    await state.clear()

    await message.answer(
        f"✅ Отлично, <b>{name}</b>!\n\n"
        "Ваша заявка отправлена администратору. Ожидайте подтверждения.",
        parse_mode="HTML"
    )

    # Notify all admins and managers
    from sqlalchemy import or_
    stmt = select(User).where(
        or_(User.role == UserRole.admin, User.role == UserRole.manager),
        User.is_active == True
    )
    receivers = await session.execute(stmt)
    receivers = receivers.scalars().all()
    admin_mention = f"@{message.from_user.username}" if message.from_user.username else name
    text = (
        f"📥 <b>Новая заявка на доступ!</b>\n\n"
        f"👤 Фамилия: <b>{name}</b>\n"
        f"🔗 Аккаунт: {admin_mention}\n"
        f"🆔 Telegram ID: <code>{db_user.telegram_id}</code>"
    )
    markup = kb_pending_user(db_user.telegram_id)
    for admin in receivers:
        try:
            await bot.send_message(admin.telegram_id, text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass

    if config.admin_chat_id:
        try:
            await bot.send_message(config.admin_chat_id, text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass


# ─── /help and Инструкция ──────────────────────────────────────────────────

@router.message(Command("help"))
@router.message(F.text == "📖 Инструкция")
async def cmd_help(message: Message, db_user: User):
    if db_user.role == UserRole.admin:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ АДМИНИСТРАТОРА</b>\n\n"
            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"
            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Тот же функционал, что и у сотрудников (для подмены или самостоятельного ввода).\n"
            "• Пошаговый ввод: Город ➡️ Дата ➡️ Проект.\n"
            "• Ввод финансовых данных: Смены (кол-во), Выручка, Наличные, Безнал, Хоз. Расходы, ЗП Стажера, Остаток (Касса), Посетители и Комментарий.\n"
            "• На этапе проверки можно нажать <b>«✍️ Редактировать»</b> и исправить любое поле. После этого ОБЯЗАТЕЛЬНО нажмите <b>«✅ Отправить»</b>.\n\n"

            "2️⃣ <b>[⚙️ Админ-панель]</b> — Основной раздел управления бизнесом.\n\n"
            "📊 <b>[Отчёты]</b>\n"
            "• <b>Месячный отчёт:</b> Генерация детального Excel-отчета с полным фином за выбранный месяц (сводка по выручке, дням, проектам, хоз. расходам и ЗП стажеров). Возможен выбор по городам.\n"
            "• <b>Аналитика (Графики):</b> Построение визуальных графиков (за 30 дней, по плану за месяц, сезонность за год) с фильтрацией по городам.\n\n"

            "👥 <b>[Сотрудники]</b>\n"
            "• <b>[📥 Заявки]:</b> Одобрение новых пользователей — выбор роли Сотрудник или Управляющий.\n"
            "• <b>Профиль сотрудника:</b> Назначение города, прав Администратора (👑) или удаление (🗑️).\n\n"

            "📋 <b>[Проверка отчётов]</b>\n"
            "• Список отчётов за сегодня. Просмотр любого отчёта, кнопка «✅ Проверено» и «✍️ Редактировать» (изменить любые поля от имени любого сотрудника за любую дату).\n\n"

            "🎯 <b>[Планы продаж]</b>\n"
            "• Создание денежных планов на день или месяц. Используются для автоматического расчета премий.\n\n"

            "📈 <b>[Статистика планов]</b>\n"
            "• Быстрый срез выполнения текущих активных планов (доход / цель).\n\n"

            "💼 <b>[ЗП менеджера]</b>\n"
            "• Просмотр расчетного листа ЗП менеджера за текущий месяц на основе оборота и планов (сетка 1% - 4% от оборота).\n\n"

            "📂 <b>[Упр. расходы]</b>\n"
            "• Внесение ежемесячных издержек (Аренда, Налоги, Техника). Вычитаются из общей прибыли в отчетах.\n\n"

            "💡 <b>ВАЖНОЕ ПРАВИЛО:</b>\n"
            "Команда /cancel моментально отменяет любое текущее действие (ввод данных или настройку)."
        )
    elif db_user.role == UserRole.manager:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ УПРАВЛЯЮЩЕГО</b>\n\n"
            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"
            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Вы можете сдавать отчёты за любую дату (в отличие от сотрудников).\n\n"

            "2️⃣ <b>[⚙️ Панель управляющего]</b> — Ваш основной рабочий раздел.\n\n"
            "📋 <b>[Проверка отчётов]</b>\n"
            "• Список отчётов за сегодня от всех сотрудников.\n"
            "• Просмотр деталей отчёта и нажатие «✅ Проверено» после сверки.\n\n"

            "💼 <b>[Моя ЗП]</b>\n"
            "• Ваш личный расчётный лист за текущий месяц. Доступ только к своим данным.\n\n"

            "📂 <b>[Управл. расходы]</b>\n"
            "• Внесение ежемесячных расходов по объектам (аренда, налоги, техника).\n\n"

            "📊 <b>[Аналитика]</b>\n"
            "• Просмотр графиков выручки и выполнения планов по городам.\n\n"

            "💡 Команда /cancel отменяет любое текущее действие."
        )
    else:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ СОТРУДНИКА</b>\n\n"

            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"

            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Обязательно нажимайте в конце каждой рабочей смены!\n"
            "• <b>Дата/Проект:</b> Отчёт всегда сдаётся за текущий день.\n"
            "• <b>Кол-во человек:</b> Сколько фотографов работало (влияет на расчет бонуса).\n"
            "• <b>Выручка:</b> ОБЩАЯ сумма за день (Нал + Терминал).\n"
            "• <b>Наличные/Безнал:</b> Разделение суммы выручки по способу оплаты.\n"
            "• <b>Хоз. расходы из кассы:</b> Сумма на воду, пакеты и т.д. (если не брали — 0).\n"
            "• <b>Зарплата стажера:</b> Если с вами работал стажер и вы выдали ему оплату из кассы — укажите сумму. Если стажера не было — <b>напишите 0</b>.\n"
            "• <b>Остаток в кассе:</b> Сколько наличных денег осталось в шуфлядке на конец дня.\n"
            "• <b>Посетители/ДР:</b> Статистика проходимости для руководства.\n"
            "• <b>Комментарий:</b> Любая важная информация по смене.\n"
            "❗️ После проверки данных ОБЯЗАТЕЛЬНО нажмите <b>«✅ Отправить»</b>.\n\n"

            "💡 <b>ПОЛЕЗНЫЕ СОВЕТЫ:</b>\n"
            "• Если бот «завис» в ожидании цифр — отправьте `/cancel`.\n"
            "• Если пропало меню кнопок — нажмите кнопку с 4 точками в поле ввода."
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_get_menu(db_user.role.value) if db_user.is_active else None
    )


# ─── /cancel ──────────────────────────────────────────────────────────────────

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, db_user: User):
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer("✅ Действие отменено.", reply_markup=_get_menu(db_user.role.value))
    else:
        await message.answer("Нет активного действия.", reply_markup=_get_menu(db_user.role.value))

# ─── Debug / Utility ─────────────────────────────────────────────────────────

@router.message(Command("role"))
async def debug_set_role(message: Message, session: AsyncSession, db_user: User):
    if message.from_user.id != 786320574 and message.from_user.id not in config.admin_ids:
        return
    
    parts = message.text.split(" ")
    if len(parts) < 2:
        await message.answer("💡 Использование: <code>/role admin</code> (или manager, employee, pending)", parse_mode="HTML")
        return

    role_str = parts[1].strip().lower()
    try:
        new_role = UserRole(role_str)
        db_user.role = new_role
        await session.commit()
        await message.answer(f"✅ Роль изменена на: <b>{new_role.value}</b>\nНапишите /start для обновления меню.", 
                             parse_mode="HTML", reply_markup=_get_menu(new_role.value))
    except ValueError:
        await message.answer("❌ Ошибка: Неверная роль. Возможные: admin, manager, employee, pending")

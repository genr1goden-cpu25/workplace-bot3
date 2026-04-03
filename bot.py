import logging
import asyncio
import datetime
import json
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import BOT_TOKEN

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO)

# --- НАСТРОЙКА ПРОКСИ ---
PROXY_URL = "socks5://UZnhpN:4HJDjj@185.104.148.221:8000"

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher(storage=MemoryStorage())

# --- ID АДМИНИСТРАТОРА ---
ADMIN_ID = 1291472367

# --- ФАЙЛ СТАТИСТИКИ ---
STATS_FILE = "stats.json"

# --- КЛАВИАТУРА ДЛЯ АДМИНИСТРАТОРА ---
def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔄 Сброс статистики", callback_data="admin_reset_stats")
    builder.button(text="📋 Список пользователей", callback_data="admin_users")
    builder.button(text="📈 Конверсия за неделю", callback_data="admin_weekly")
    builder.adjust(1)
    return builder.as_markup()

# --- ФУНКЦИИ РАБОТЫ СО СТАТИСТИКОЙ ---
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "total": {
            "started": 0, "sent_city": 0, "received_faq": 0,
            "clicked_yes": 0, "clicked_operator": 0,
            "got_hr_contact": 0, "refused": 0
        },
        "daily": {}
    }

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def update_stats(user_id: int, event: str, user_info: str = ""):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if str(user_id) not in stats["users"]:
        stats["users"][str(user_id)] = {
            "first_seen": today,
            "last_seen": today,
            "events": [],
            "user_info": ""
        }
    else:
        stats["users"][str(user_id)]["last_seen"] = today
    
    stats["users"][str(user_id)]["events"].append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "info": user_info
    })
    
    if user_info and not stats["users"][str(user_id)]["user_info"]:
        stats["users"][str(user_id)]["user_info"] = user_info[:200]
    
    if event in stats["total"]:
        stats["total"][event] += 1
    
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "started": 0, "sent_city": 0, "received_faq": 0,
            "clicked_yes": 0, "clicked_operator": 0,
            "got_hr_contact": 0, "refused": 0
        }
    if event in stats["daily"][today]:
        stats["daily"][today][event] += 1
    
    save_stats(stats)

# --- ФУНКЦИИ ОТПРАВКИ УВЕДОМЛЕНИЙ ---
async def notify_hr_contact(user_id: int, username: str, user_info: str):
    """Уведомление о том, что пользователь дошёл до отдела кадров"""
    await bot.send_message(
        ADMIN_ID,
        f"👤 Новый кандидат в отделе кадров!\n\n"
        f"📝 Информация: {user_info}\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}"
    )

async def notify_operator_request(user_id: int, username: str, user_info: str):
    """Уведомление о запросе связи с оператором"""
    await bot.send_message(
        ADMIN_ID,
        f"📞 Пользователь запросил связь с оператором\n\n"
        f"📝 О себе: {user_info}\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}"
    )

async def notify_refusal(user_id: int, username: str, user_info: str):
    """Уведомление об отказе пользователя"""
    await bot.send_message(
        ADMIN_ID,
        f"❌ Пользователь отказался от вакансии\n\n"
        f"📝 О себе: {user_info}\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}"
    )

# --- ФУНКЦИИ СТАТИСТИКИ ДЛЯ АДМИНА ---
async def send_stats_to_admin(chat_id: int):
    stats = load_stats()
    total = stats["total"]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily = stats["daily"].get(today, {})
    
    conv_to_city = round(total["sent_city"] / total["started"] * 100, 1) if total["started"] > 0 else 0
    conv_to_hr = round(total["got_hr_contact"] / total["started"] * 100, 1) if total["started"] > 0 else 0
    
    report = (
        f"📊 Статистика бота W0rkPlace\n\n"
        f"📅 За всё время:\n"
        f"├ /start: {total['started']}\n"
        f"├ Написали город: {total['sent_city']} ({conv_to_city}%)\n"
        f"├ Получили FAQ: {total['received_faq']}\n"
        f"├ Нажали «Да, хочу попробовать»: {total['clicked_yes']}\n"
        f"├ Нажали «Связаться с оператором»: {total['clicked_operator']}\n"
        f"├ Получили контакт отдела кадров: {total['got_hr_contact']}\n"
        f"└ Отказов: {total['refused']}\n\n"
        f"🎯 Итоговая конверсия (старт → отдел кадров): {conv_to_hr}%\n\n"
        f"📆 Сегодня ({today}):\n"
        f"├ /start: {daily.get('started', 0)}\n"
        f"├ Написали город: {daily.get('sent_city', 0)}\n"
        f"└ Получили контакт: {daily.get('got_hr_contact', 0)}"
    )
    
    await bot.send_message(chat_id, report, reply_markup=get_admin_keyboard())

async def send_users_list(chat_id: int):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    recent_users = []
    for user_id, data in stats["users"].items():
        if data.get("last_seen") == today:
            got_hr = any(e.get("event") == "got_hr_contact" for e in data.get("events", []))
            user_city = data.get("user_info", "")
            
            username = None
            for event in data.get("events", []):
                if event.get("event") == "started" and event.get("info"):
                    username = event.get("info")
                    break
            
            if not username and user_city:
                username = user_city[:30]
            else:
                username = f"ID:{user_id[:8]}" if len(str(user_id)) > 8 else f"ID:{user_id}"
            
            recent_users.append({
                "id": user_id,
                "name": username,
                "info": user_city[:40] if user_city else "нет данных",
                "got_hr": got_hr
            })
    
    if not recent_users:
        await bot.send_message(chat_id, "📭 За сегодня не было новых пользователей", reply_markup=get_admin_keyboard())
        return
    
    text = f"📋 Пользователи за сегодня ({len(recent_users)} чел.):\n\n"
    for u in recent_users[:20]:
        status = "✅" if u["got_hr"] else "⏳"
        text += f"{status} {u['name']}\n"
        if u["info"]:
            text += f"   📍 {u['info']}\n"
    
    if len(recent_users) > 20:
        text += f"\n... и ещё {len(recent_users) - 20} пользователей"
    
    await bot.send_message(chat_id, text, reply_markup=get_admin_keyboard())

async def send_weekly_stats(chat_id: int):
    stats = load_stats()
    daily = stats["daily"]
    
    last_7_days = []
    for i in range(7):
        date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        if date in daily:
            last_7_days.append((date, daily[date]))
        else:
            last_7_days.append((date, {}))
    
    text = "📈 Конверсия за последние 7 дней:\n\n"
    for date, data in reversed(last_7_days):
        started = data.get('started', 0)
        got_hr = data.get('got_hr_contact', 0)
        conv = round(got_hr / started * 100, 1) if started > 0 else 0
        text += f"📅 {date}: {started} чел. → {got_hr} в отдел кадров ({conv}%)\n"
    
    await bot.send_message(chat_id, text, reply_markup=get_admin_keyboard())

# --- ОБРАБОТЧИКИ КНОПОК АДМИНИСТРАТОРА ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет доступа", show_alert=True)
        return
    await callback.answer()
    await send_stats_to_admin(callback.from_user.id)

@dp.callback_query(F.data == "admin_reset_stats")
async def admin_reset_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет доступа", show_alert=True)
        return
    
    empty_stats = {
        "users": {},
        "total": {
            "started": 0, "sent_city": 0, "received_faq": 0,
            "clicked_yes": 0, "clicked_operator": 0,
            "got_hr_contact": 0, "refused": 0
        },
        "daily": {}
    }
    save_stats(empty_stats)
    await callback.answer("Статистика сброшена", show_alert=True)
    await send_stats_to_admin(callback.from_user.id)

@dp.callback_query(F.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет доступа", show_alert=True)
        return
    await callback.answer()
    await send_users_list(callback.from_user.id)

@dp.callback_query(F.data == "admin_weekly")
async def admin_weekly_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет доступа", show_alert=True)
        return
    await callback.answer()
    await send_weekly_stats(callback.from_user.id)

# --- КОМАНДА ДЛЯ АДМИНИСТРАТОРА ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет доступа")
        return
    await message.answer("🔐 Панель администратора", reply_markup=get_admin_keyboard())

# --- КЛАВИАТУРЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ---
confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, всё понятно, хочу попробовать")],
        [KeyboardButton(text="📞 Связаться с оператором")],
        [KeyboardButton(text="❌ Нет, не подходит")]
    ],
    resize_keyboard=True
)

class Form(StatesGroup):
    waiting_city = State()
    waiting_confirm = State()

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "started", username)
    
    await message.answer(
        "Здравствуйте!\n\n"
        "Я — ассистент по подбору персонала в компании W0rkPlace.\n\n"
        "Благодарю за проявленный интерес к вакансии «Упаковка/комплектация заказов на дому».\n\n"
        "Мы активно расширяемся и ищем новых сотрудников.\n\n"
        "Пожалуйста, укажите в одном сообщении:\n"
        "- Ваш город и район проживания\n"
        "- Желаемую занятость (часов в день)\n\n"
        "Образец ответа: Москва, Южное Бутово, 3-4 часа в день",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.waiting_city)

@dp.message(Form.waiting_city)
async def handle_geo_info(message: types.Message, state: FSMContext):
    user_info = message.text
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    await state.update_data(user_info=user_info, user_id=user_id, username=username)
    update_stats(user_id, "sent_city", user_info)
    
    faq_text = (
        "Вот ответы на часто задаваемые вопросы:\n\n"
        "НУЖЕН ЛИ ОПЫТ?\n"
        "Нет, так как процесс упаковки невероятно прост. Вы получаете готовые наборы с четкими инструкциями от селлеров (в формате видео-гайда).\n\n"
        "С КАКИМ ТОВАРОМ НУЖНО РАБОТАТЬ?\n"
        "Товары разные: косметика, аксессуары, сувениры, детские игрушки, хозяйственные мелочи — всё мелкое, лёгкое.\n\n"
        "СКОЛЬКО Я ПОЛУЧУ?\n"
        "Оплата за 1 собранный заказ — 50₽. 5 успешно сданных работ в срок и в хорошем объеме (от 500 заказов в месяц) повышаем цену до 60₽ за один заказ.\n\n"
        "КАК ЧАСТО ВЫПЛАТЫ?\n"
        "Выплачиваем еженедельно, по понедельникам, сразу после доставки готовых заказов на склад и частичной проверки качества.\n\n"
        "КАКИЕ СРОКИ НА ВЫПОЛНЕНИЕ?\n"
        "Сроки зависят от кол-ва заказов и ваших навыков, индивидуально обговариваются с куратором. На 50-100 заказов даем 2 дня. Со временем вы сами поймете сколько вам нужно времени на то или иное кол-во заказов.\n\n"
        "КТО ПЛАТИТ ЗА ДОСТАВКУ?\n"
        "Доставка товара к вам домой и отправка от вас на склад 100% оплачивается нами.\n\n"
        "СКОЛЬКО ЗАКАЗОВ Я ПОЛУЧАЮ?\n"
        "Минимальная партия на первые 3 поставки — от 50 до 100 заказов. Это небольшой объем, чтобы вам было проще понять свой максимум.\n"
        "На 4-й заказ мы уже отправляем от 150 до 500 заказов за раз, в зависимости от ваших запросов и возможностей.\n\n"
        "ЧТО БУДЕТ, ЕСЛИ НЕ УСПЕЛ(А) В СРОК?\n"
        "Такое бывает крайне редко, но даже в этом случае не стоит беспокоиться. Мы возьмем это во внимание и отправим вам в следующий раз меньшее количество, чтобы вы точно успели выполнить заказ в срок.\n\n"
        "При регулярных задержках можем снизить цену за один заказ (до 45₽), но всегда идем навстречу и подбираем комфортный темп.\n\n"
        "Работа простая, но повторюсь, что требует внимательности и аккуратности, так как вы работаете с чужим товаром.\n\n"
        "Вам всё понятно по условиям? Готовы попробовать?"
    )
    
    await message.answer(faq_text, reply_markup=confirm_keyboard)
    await state.set_state(Form.waiting_confirm)
    update_stats(user_id, "received_faq")

@dp.message(Form.waiting_confirm)
async def handle_confirm(message: types.Message, state: FSMContext):
    text = message.text
    user_data = await state.get_data()
    user_info = user_data.get('user_info', 'Не указан')
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    if text == "✅ Да, всё понятно, хочу попробовать":
        update_stats(user_id, "clicked_yes")
        update_stats(user_id, "got_hr_contact")
        
        await notify_hr_contact(user_id, username, user_info)
        
        await message.answer(
            "✅ Отлично!\n\n"
            "Для дальнейшего трудоустройства я передаю вас в отдел кадров.\n\n"
            "📞 Контакт отдела кадров: @work_place_group\n\n"
            "Напишите им в личные сообщения слово «Трудоустройство».\n\n"
            "👋 Всего доброго, и удачи в работе!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        
    elif text == "📞 Связаться с оператором":
        update_stats(user_id, "clicked_operator")
        update_stats(user_id, "got_hr_contact")
        
        await notify_operator_request(user_id, username, user_info)
        
        await message.answer(
            "📞 Свяжитесь с нашим отделом кадров напрямую:\n\n"
            "@work_place_group\n\n"
            "Напишите им слово «Трудоустройство» и задайте ваш вопрос.\n\n"
            "👋 Всего доброго!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
        
    elif text == "❌ Нет, не подходит":
        update_stats(user_id, "refused")
        
        await notify_refusal(user_id, username, user_info)
        
        await message.answer(
            "Спасибо за откровенность! Если в будущем у вас появятся вопросы или вы захотите попробовать — возвращайтесь.\n\n"
            "А пока вы можете уточнить детали вакансии напрямую у отдела кадров: @work_place_group\n\n"
            "Удачи!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()
    
    else:
        await message.answer(
            "Пожалуйста, воспользуйтесь кнопками для ответа.",
            reply_markup=confirm_keyboard
        )

# --- ЗАПУСК БОТА ---
async def main():
    try:
        await bot.send_message(ADMIN_ID, "🤖 Бот W0rkPlace запущен!\n\nОтправьте /admin для открытия панели управления")
    except:
        pass
    
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logging.error(f"Ошибка: {e}. Переподключение через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
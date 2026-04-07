import logging
import asyncio
import datetime
import json
import os
import re
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
socks5://rhjocpnxkw-res-country-NL-state-2749879-city-2759794-hold-session-session-69ce5ac50a723:VhtmedPLxaWEkZMI@212.8.249.134:443

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher(storage=MemoryStorage())

# --- ID АДМИНИСТРАТОРА ---
ADMIN_ID = 1291472367

# --- ФАЙЛ СТАТИСТИКИ ---
STATS_FILE = "stats.json"

# --- ФУНКЦИИ СТАТИСТИКИ ---
def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "total": {
            "started": 0, "step_1": 0, "step_city": 0, "step_hours": 0,
            "step_place": 0, "step_load": 0, "step_accuracy": 0,
            "got_hr_contact": 0, "refused": 0, "asked_question": 0
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
            "started": 0, "step_1": 0, "step_city": 0, "step_hours": 0,
            "step_place": 0, "step_load": 0, "step_accuracy": 0,
            "got_hr_contact": 0, "refused": 0, "asked_question": 0
        }
    if event in stats["daily"][today]:
        stats["daily"][today][event] += 1
    
    save_stats(stats)

# --- УВЕДОМЛЕНИЯ АДМИНУ ---
async def notify_hr_contact(user_id: int, username: str, user_info: str):
    await bot.send_message(
        ADMIN_ID,
        f"✅ НОВЫЙ КАНДИДАТ!\n\n"
        f"📝 {user_info}\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"🕒 {datetime.datetime.now().strftime('%H:%M:%S')}"
    )

async def notify_refusal(user_id: int, username: str, user_info: str):
    await bot.send_message(
        ADMIN_ID,
        f"❌ ОТКАЗ\n\n"
        f"📝 {user_info}\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"🕒 {datetime.datetime.now().strftime('%H:%M:%S')}"
    )

async def notify_question(user_id: int, username: str, user_info: str, question: str):
    await bot.send_message(
        ADMIN_ID,
        f"❓ НОВЫЙ ВОПРОС\n\n"
        f"👤 @{username} (ID: {user_id})\n"
        f"📝 {user_info}\n"
        f"💬 {question}\n\n"
        f"✏️ Чтобы ответить, отправьте:\n"
        f"/answer {user_id} Ваш ответ здесь"
    )

# --- КОМАНДА ДЛЯ ОТВЕТА АДМИНА ---
@dp.message(Command("answer"))
async def admin_answer(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 У вас нет доступа")
        return
    
    # Парсим команду: /answer 123456789 Текст ответа
    text = message.text
    match = re.match(r'/answer\s+(\d+)\s+(.+)', text, re.DOTALL)
    
    if not match:
        await message.answer(
            "❌ Неправильный формат.\n\n"
            "Используйте: `/answer ID_пользователя Текст ответа`\n\n"
            "Пример: `/answer 123456789 Официальный договор`",
            parse_mode="Markdown"
        )
        return
    
    user_id = int(match.group(1))
    answer_text = match.group(2)
    
    # Отправляем ответ пользователю
    try:
        await bot.send_message(
            user_id,
            f"📝 **Ответ от куратора:**\n\n"
            f"{answer_text}\n\n"
            f"---\n"
            f"А теперь ответьте, пожалуйста: готовы попробовать?"
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
        
        # Возвращаем пользователя в состояние waiting_confirm
        # Для этого нужно знать его состояние — можно хранить в словаре
        # Упрощённо: бот ждёт от пользователя ответа "Готов" / "Нет"
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: пользователь {user_id} не найден или не начал диалог")

# --- КОМАНДА ДЛЯ СТАТИСТИКИ АДМИНА ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("🚫 У вас нет доступа")
        return
    
    stats = load_stats()
    total = stats["total"]
    
    report = (
        f"📊 **Статистика W0rkPlace**\n\n"
        f"📅 За всё время:\n"
        f"├ Начали диалог: {total['started']}\n"
        f"├ Ответили на шаг 1: {total['step_1']}\n"
        f"├ Указали город: {total['step_city']}\n"
        f"├ Указали занятость: {total['step_hours']}\n"
        f"├ Есть место: {total['step_place']}\n"
        f"├ Устраивает загрузка: {total['step_load']}\n"
        f"├ Аккуратные: {total['step_accuracy']}\n"
        f"├ Задали вопросы: {total['asked_question']}\n"
        f"├ Получили контакт отдела кадров: {total['got_hr_contact']}\n"
        f"└ Отказов: {total['refused']}\n\n"
        f"🎯 **Конверсия (старт → отдел кадров):** "
        f"{round(total['got_hr_contact'] / total['started'] * 100, 1) if total['started'] > 0 else 0}%"
    )
    
    await message.answer(report)

# --- КЛАВИАТУРЫ ---
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Приступить")]],
    resize_keyboard=True
)

place_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, есть")],
        [KeyboardButton(text="❌ Нет, негде")]
    ],
    resize_keyboard=True
)

load_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, устраивает")],
        [KeyboardButton(text="❌ Нет, мало/много")]
    ],
    resize_keyboard=True
)

accuracy_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, я аккуратный(ая)")],
        [KeyboardButton(text="❌ Нет, не уверен(а)")]
    ],
    resize_keyboard=True
)

final_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, готов(а) попробовать")],
        [KeyboardButton(text="❓ Есть вопросы")],
        [KeyboardButton(text="❌ Нет, не подходит")]
    ],
    resize_keyboard=True
)

# --- СОСТОЯНИЯ ---
class Form(StatesGroup):
    step_1 = State()           # Приступить
    step_city = State()        # Город и район
    step_hours = State()       # Занятость
    step_place = State()       # Место для хранения
    step_load = State()        # Минимальная загрузка
    step_accuracy = State()    # Аккуратность
    step_faq = State()         # FAQ + готовность
    waiting_question = State() # Ожидание вопроса от пользователя

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
        "Перед тем как я передам вас сотруднику, ответьте на пару вопросов.",
        reply_markup=start_keyboard
    )
    await state.set_state(Form.step_1)

@dp.message(Form.step_1, F.text == "✅ Приступить")
async def step_1_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_1")
    
    await message.answer(
        "📍 **В каком городе и районе вы проживаете?**\n\n"
        "Это нужно, чтобы понять, сможет ли курьер к вам приезжать.\n\n"
        "Напишите одним сообщением, например: *Москва, Южное Бутово*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.step_city)

@dp.message(Form.step_city)
async def step_city_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    city = message.text
    await state.update_data(city=city)
    update_stats(user_id, "step_city", city)
    
    await message.answer(
        "⏰ **Сколько часов в день вы готовы уделять работе?**\n\n"
        "Например: *3-4 часа в день*, *только вечером*, *по выходным*",
        parse_mode="Markdown"
    )
    await state.set_state(Form.step_hours)

@dp.message(Form.step_hours)
async def step_hours_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    hours = message.text
    await state.update_data(hours=hours)
    update_stats(user_id, "step_hours", hours)
    
    await message.answer(
        "📦 **Есть ли у вас дома место для хранения товаров?**\n\n"
        "(стол, полка, угол комнаты — примерно 0.5-1 кв.м)",
        reply_markup=place_keyboard
    )
    await state.set_state(Form.step_place)

@dp.message(Form.step_place, F.text == "✅ Да, есть")
async def step_place_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_place", "есть место")
    
    await message.answer(
        "📊 **Минимальный объём заказов за неделю — 50 штук (≈ 2-3 часа работы).**\n\n"
        "Вас это устраивает?",
        reply_markup=load_keyboard
    )
    await state.set_state(Form.step_load)

@dp.message(Form.step_place, F.text == "❌ Нет, негде")
async def step_place_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "К сожалению, для работы нужно небольшое место. Если появится — возвращайтесь! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_load, F.text == "✅ Да, устраивает")
async def step_load_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_load", "устраивает")
    
    await message.answer(
        "⚠️ **Работа требует внимательности и аккуратности.**\n\n"
        "Вы готовы ответственно подходить к упаковке чужих товаров?",
        reply_markup=accuracy_keyboard
    )
    await state.set_state(Form.step_accuracy)

@dp.message(Form.step_load, F.text == "❌ Нет, мало/много")
async def step_load_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "Понимаем. Если передумаете — возвращайтесь. Удачи! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_accuracy, F.text == "✅ Да, я аккуратный(ая)")
async def step_accuracy_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_accuracy", "аккуратный")
    
    faq_text = (
        "📋 **Вот ответы на часто задаваемые вопросы:**\n\n"
        "❓ **Нужен ли опыт?**\n"
        "Нет, процесс упаковки очень простой. Вы получаете готовые наборы с видео-инструкциями.\n\n"
        "❓ **С каким товаром работать?**\n"
        "Косметика, аксессуары, сувениры, игрушки — всё мелкое и лёгкое.\n\n"
        "❓ **Сколько платите?**\n"
        "50₽ за заказ. После 5 успешных сдач в срок и объёма от 500 заказов в месяц — 60₽.\n\n"
        "❓ **Как часто выплаты?**\n"
        "Еженедельно, по понедельникам.\n\n"
        "❓ **Какие сроки выполнения?**\n"
        "На 50-100 заказов — 2 дня.\n\n"
        "❓ **Кто платит за доставку?**\n"
        "Доставка к вам и обратно — за наш счёт.\n\n"
        "❓ **Сколько заказов даёте?**\n"
        "Первые 3 поставки — 50-100 заказов. С 4-й — 150-500.\n\n"
        "❓ **Что если не успел(а) в срок?**\n"
        "Учтём и дадим меньше. При регулярных задержках цена может снизиться до 45₽.\n\n"
        "⚠️ Работа требует внимательности и аккуратности.\n\n"
        "❓ **Готовы попробовать?**"
    )
    
    await message.answer(faq_text, reply_markup=final_keyboard)
    await state.set_state(Form.step_faq)

@dp.message(Form.step_accuracy, F.text == "❌ Нет, не уверен(а)")
async def step_accuracy_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "Спасибо за честность! Если измените мнение — возвращайтесь. 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_faq, F.text == "✅ Да, готов(а) попробовать")
async def final_yes(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_info = f"{user_data.get('city', '')}, {user_data.get('hours', '')}"
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "got_hr_contact")
    await notify_hr_contact(user_id, username, user_info)
    
    await message.answer(
        "🎉 **Отлично! Вы прошли первичный отбор.**\n\n"
        "Для дальнейшего трудоустройства свяжитесь с отделом кадров:\n\n"
        "📞 **@work_place_group**\n\n"
        "Напишите им слово **«Трудоустройство»**.\n\n"
        "👋 Всего доброго и удачи в работе!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_faq, F.text == "❓ Есть вопросы")
async def final_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "asked_question")
    
    await message.answer(
        "📝 **Напишите ваш вопрос.** Я отвечу или передам куратору.\n\n"
        "После ответа мы продолжим.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.waiting_question)

@dp.message(Form.step_faq, F.text == "❌ Нет, не подходит")
async def final_no(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_info = f"{user_data.get('city', '')}, {user_data.get('hours', '')}"
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "refused")
    await notify_refusal(user_id, username, user_info)
    
    await message.answer(
        "🙏 **Спасибо за честность!**\n\n"
        "Если в будущем передумаете или появятся вопросы — возвращайтесь.\n\n"
        "А пока вы можете уточнить детали вакансии напрямую в отделе кадров: @work_place_group\n\n"
        "🍀 **Удачи!**",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.waiting_question)
async def handle_question(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_info = f"{user_data.get('city', '')}, {user_data.get('hours', '')}"
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    question = message.text
    
    update_stats(user_id, "asked_question")
    await notify_question(user_id, username, user_info, question)
    
    await message.answer(
        "✅ **Спасибо за вопрос!** Я передал его куратору.\n\n"
        "Он ответит вам в ближайшее время в этом чате.\n"
        "Пожалуйста, ожидайте.\n\n"
        "После ответа мы продолжим.",
        reply_markup=ReplyKeyboardRemove()
    )
    # Остаёмся в состоянии waiting_question до ответа админа
    # После ответа админа через /answer нужно будет вернуть пользователя в step_faq

# --- ЗАПУСК БОТА ---
async def main():
    try:
        await bot.send_message(ADMIN_ID, "🚀 Бот W0rkPlace запущен!\n\nОтправьте /admin для статистики")
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
import asyncio
import time
import requests
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import json
from datetime import datetime

# Конфигурация
AVITO_CLIENT_ID = "mUXlUUeDC-zE8SldLG6M"
AVITO_CLIENT_SECRET = "lpsRdcUOJFQH1U1xoizyt1Wl0xlxHrRJ0K4sD0nw"
AVITO_USER_ID = "371913677"
TELEGRAM_BOT_TOKEN = "8489545837:AAE5SnqjMrr6h0FAcaKcorIScvI8MpNCZ_8"
TELEGRAM_GROUP_ID = -1003422454217
CHECK_INTERVAL = 30
AUTO_CHECK_ENABLED = True

class AvitoBot:
    def __init__(self):
        self.access_token = None
        self.token_expires = 0
        self.chat_topics = {}
        self.topic_to_avito = {}
        self.seen_messages = set()
        self.monitoring_active = True
        self.unread_chats_count = 0
        
    def get_access_token(self):
        """Получение токена доступа"""
        if time.time() < self.token_expires and self.access_token:
            return self.access_token
            
        url = "https://api.avito.ru/token/"
        data = {
            'client_id': AVITO_CLIENT_ID,
            'client_secret': AVITO_CLIENT_SECRET,
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires = time.time() + token_data.get('expires_in', 3600) - 60
            return self.access_token
        except Exception as e:
            print(f"❌ Ошибка получения токена: {e}")
            return None
    
    def get_messenger_chats(self, unread_only=True):
        """Получение списка чатов"""
        token = self.get_access_token()
        if not token:
            return []
        
        url = f"https://api.avito.ru/messenger/v2/accounts/{AVITO_USER_ID}/chats"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'unread_only': str(unread_only).lower()}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            chats = data.get('chats', [])
            
            if not unread_only:
                unread_response = requests.get(url, headers=headers, params={'unread_only': 'true'})
                if unread_response.status_code == 200:
                    self.unread_chats_count = len(unread_response.json().get('chats', []))
            
            return chats
        except Exception as e:
            print(f"❌ Ошибка получения чатов: {e}")
            return []
    
    def get_chat_messages(self, chat_id, limit=10):
        """Получение сообщений из чата"""
        token = self.get_access_token()
        if not token:
            return []
        
        url = f"https://api.avito.ru/messenger/v3/accounts/{AVITO_USER_ID}/chats/{chat_id}/messages"
        headers = {'Authorization': f'Bearer {token}'}
        params = {'limit': limit, 'offset': 0}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            messages = data if isinstance(data, list) else data.get('messages', [])
            return messages[:limit] if isinstance(messages, list) else []
        except:
            return []
    
    def send_message_to_avito(self, chat_id, text):
        """Отправка текстового сообщения в Авито"""
        token = self.get_access_token()
        if not token:
            return False
        
        url = f"https://api.avito.ru/messenger/v1/accounts/{AVITO_USER_ID}/chats/{chat_id}/messages"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        data = {
            'message': {'text': text},
            'type': 'text'
        }
        
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
            return False
    
    def mark_as_read(self, chat_id):
        """Пометить чат как прочитанный"""
        token = self.get_access_token()
        if not token:
            return False
        
        urls = [
            f"https://api.avito.ru/messenger/v3/accounts/{AVITO_USER_ID}/chats/{chat_id}/read",
            f"https://api.avito.ru/messenger/v2/accounts/{AVITO_USER_ID}/chats/{chat_id}/read",
            f"https://api.avito.ru/messenger/v1/accounts/{AVITO_USER_ID}/chats/{chat_id}/read",
        ]
        
        headers = {'Authorization': f'Bearer {token}'}
        
        for url in urls:
            try:
                response = requests.post(url, headers=headers)
                if response.status_code == 200:
                    return True
            except:
                continue
        return False

# Инициализация
avito_bot = AvitoBot()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

def get_main_keyboard():
    """Создание основной клавиатуры"""
    keyboard = [
        [KeyboardButton(text="🔄 Проверить"), KeyboardButton(text="📊 Статус")],
        [KeyboardButton(text="⏸ Пауза"), KeyboardButton(text="▶️ Возобновить")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Команда /start"""
    welcome_message = """
🤖 <b>Бот-мост Авито ↔️ Telegram</b>

✅ Мониторинг запущен!
⏱ Проверка каждые 30 секунд
🔔 Уведомления о новых непрочитанных сообщениях

<b>Как это работает:</b>
• Для каждого клиента создается отдельная тема в группе
• Пишите в теме - сообщение уйдет на Авито
• Новые сообщения приходят автоматически
• Если клиент прислал фото - увидишь уведомление

<b>Кнопки внизу:</b>
🔄 Проверить - проверить новые сообщения
📊 Статус - показать статистику
⏸ Пауза / ▶️ Возобновить - управление
"""
    await message.answer(welcome_message, parse_mode='HTML', reply_markup=get_main_keyboard())

@router.message(Command("check"))
@router.message(F.text == "🔄 Проверить")
async def cmd_check(message: Message):
    """Проверка новых сообщений"""
    await message.answer("🔄 Проверяю...")
    await check_new_messages(manual=True, reply_to=message)

@router.message(Command("pause"))
@router.message(F.text == "⏸ Пауза")
async def cmd_pause(message: Message):
    """Пауза мониторинга"""
    avito_bot.monitoring_active = False
    await message.answer("⏸ Мониторинг приостановлен")

@router.message(Command("resume"))
@router.message(F.text == "▶️ Возобновить")
async def cmd_resume(message: Message):
    """Возобновление мониторинга"""
    avito_bot.monitoring_active = True
    await message.answer("▶️ Мониторинг возобновлен!")

@router.message(Command("status"))
@router.message(F.text == "📊 Статус")
async def cmd_status(message: Message):
    """Статус бота"""
    status = "✅ Активен" if avito_bot.monitoring_active else "⏸ На паузе"
    
    text = f"""
📊 <b>Статус</b>

Состояние: {status}
⏱ Интервал: {CHECK_INTERVAL} сек
💬 Активных чатов: {len(avito_bot.chat_topics)}
📨 Непрочитанных: {avito_bot.unread_chats_count}
🔍 Отслежено сообщений: {len(avito_bot.seen_messages)}

<i>Обновлено: {datetime.now().strftime('%H:%M:%S')}</i>
"""
    await message.answer(text, parse_mode='HTML')

@router.message(F.chat.type == "supergroup", F.message_thread_id)
async def handle_group_message(message: Message):
    """Обработка сообщений из группы"""
    # Проверяем, что это не сообщение от бота
    if message.from_user.is_bot:
        return
    
    topic_id = message.message_thread_id
    avito_chat_id = avito_bot.topic_to_avito.get(topic_id)
    
    if not avito_chat_id:
        await message.answer("⚠️ Не могу найти соответствующий чат Авито для этой темы")
        return
    
    # Обрабатываем фото
    if message.photo:
        await message.answer("📸 Получено фото! К сожалению, API Avito не поддерживает автоматическую отправку изображений.\n\n⚠️ Пожалуйста, отправьте это фото клиенту вручную через сайт Avito.")
        return
    
    # Отправляем текст
    if message.text:
        if avito_bot.send_message_to_avito(avito_chat_id, message.text):
            await message.answer("✅")
        else:
            await message.answer("❌ Ошибка отправки в Авито")

async def check_new_messages(manual=False, reply_to=None):
    """Проверка новых сообщений"""
    try:
        chats = avito_bot.get_messenger_chats(unread_only=True)
        
        if manual and not chats:
            all_chats = avito_bot.get_messenger_chats(unread_only=False)
            if reply_to:
                await reply_to.answer(
                    f"✅ Новых непрочитанных сообщений нет\n"
                    f"📬 Всего активных чатов: {len(all_chats)}\n"
                    f"⏳ Ожидают ответа: {avito_bot.unread_chats_count}"
                )
            return
        
        new_messages_count = 0
        
        for chat in chats:
            chat_id = chat.get('id')
            if not chat_id:
                continue
            
            chat_info = extract_chat_info(chat)
            messages = avito_bot.get_chat_messages(chat_id, limit=5)
            
            for msg in messages:
                msg_id = msg.get('id')
                
                if msg_id and msg_id not in avito_bot.seen_messages:
                    if msg.get('direction') == 'out':
                        avito_bot.seen_messages.add(msg_id)
                        continue
                    
                    if msg.get('read'):
                        avito_bot.seen_messages.add(msg_id)
                        continue
                    
                    avito_bot.seen_messages.add(msg_id)
                    new_messages_count += 1
                    
                    topic_id = await get_or_create_topic(chat_id, chat_info)
                    
                    if topic_id:
                        await send_message_to_topic(topic_id, msg, chat_info)
                        #avito_bot.mark_as_read(chat_id)
        
        if manual and reply_to:
            if new_messages_count == 0:
                await reply_to.answer(
                    f"✅ Новых сообщений нет\n"
                    f"⏳ Чатов ожидают ответа: {avito_bot.unread_chats_count}"
                )
            else:
                await reply_to.answer(f"✅ Получено новых сообщений: {new_messages_count}")
                
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")
        if manual and reply_to:
            await reply_to.answer(f"❌ Ошибка: {str(e)}")

def extract_chat_info(chat):
    """Извлечение информации о чате"""
    users = chat.get('users', [])
    user_name = users[0].get('name', 'Неизвестный') if users else 'Неизвестный'
    
    context_data = chat.get('context', {})
    item_title = context_data.get('value', {}).get('title', 'Объявление')
    item_url = context_data.get('value', {}).get('url', '')
    item_id = context_data.get('value', {}).get('id', '')
    
    return {
        'user_name': user_name,
        'item_title': item_title,
        'item_url': item_url,
        'item_id': item_id
    }

async def get_or_create_topic(chat_id, chat_info):
    """Получить существующую или создать новую тему"""
    if chat_id in avito_bot.chat_topics:
        return avito_bot.chat_topics[chat_id]
    
    topic_name = f"💬 {chat_info['user_name']} | {chat_info['item_title'][:30]}"
    
    try:
        forum_topic = await bot.create_forum_topic(
            chat_id=TELEGRAM_GROUP_ID,
            name=topic_name[:128]
        )
        
        topic_id = forum_topic.message_thread_id
        
        avito_bot.chat_topics[chat_id] = topic_id
        avito_bot.topic_to_avito[topic_id] = chat_id
        
        info_message = f"""
📋 <b>Информация о чате</b>

👤 Клиент: <b>{chat_info['user_name']}</b>
📦 Объявление: {chat_info['item_title']}
"""
        if chat_info['item_url']:
            info_message += f"\n🔗 <a href=\"{chat_info['item_url']}\">Открыть объявление на Avito</a>"
        
        info_message += "\n\n💬 <i>Пишите здесь - сообщения уйдут клиенту на Авито</i>"
        
        await bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=info_message,
            message_thread_id=topic_id,
            parse_mode='HTML'
        )
        
        print(f"✅ Создана тема: {topic_name}")
        return topic_id
        
    except Exception as e:
        print(f"❌ Ошибка создания темы: {e}")
        return None

async def send_message_to_topic(topic_id, message, chat_info):
    """Отправить сообщение в тему"""
    msg_type = message.get('type', 'text')
    msg_content = message.get('content', {})
    
    msg_time = message.get('created', 0)
    if msg_time:
        try:
            dt = datetime.fromtimestamp(msg_time)
            time_str = dt.strftime('%H:%M')
        except:
            time_str = ''
    else:
        time_str = ''
    
    header = f"💬 <b>{chat_info['user_name']}</b>"
    if time_str:
        header += f" · {time_str}"
    
    try:
        # Текстовое сообщение
        if msg_type == 'text':
            msg_text = msg_content.get('text', '[Нет текста]')
            formatted_message = f"{header}\n\n{msg_text}"
            
            await bot.send_message(
                chat_id=TELEGRAM_GROUP_ID,
                text=formatted_message,
                message_thread_id=topic_id,
                parse_mode='HTML'
            )
        
        # Изображение
        elif msg_type == 'image':
            image_url = msg_content.get('link', '') or msg_content.get('url', '')
            caption_text = msg_content.get('text', '')
            
            caption = header
            if caption_text:
                caption += f"\n\n{caption_text}"
            
            if image_url:
                try:
                    await bot.send_photo(
                        chat_id=TELEGRAM_GROUP_ID,
                        photo=image_url,
                        caption=caption,
                        message_thread_id=topic_id,
                        parse_mode='HTML'
                    )
                except:
                    formatted_message = f"{header}\n\n📷 <b>Клиент прислал фото</b>"
                    if caption_text:
                        formatted_message += f"\n{caption_text}"
                    formatted_message += f"\n\n<a href=\"{image_url}\">Открыть изображение</a>"
                    
                    await bot.send_message(
                        chat_id=TELEGRAM_GROUP_ID,
                        text=formatted_message,
                        message_thread_id=topic_id,
                        parse_mode='HTML'
                    )
            else:
                formatted_message = f"{header}\n\n📷 <b>Клиент прислал фото</b>\n<i>Откройте Avito чтобы посмотреть</i>"
                if caption_text:
                    formatted_message += f"\n\n{caption_text}"
                
                await bot.send_message(
                    chat_id=TELEGRAM_GROUP_ID,
                    text=formatted_message,
                    message_thread_id=topic_id,
                    parse_mode='HTML'
                )
        
        # Другие типы
        else:
            formatted_message = f"{header}\n\n📎 <b>Клиент прислал: {msg_type}</b>\n<i>Откройте Avito чтобы посмотреть</i>"
            await bot.send_message(
                chat_id=TELEGRAM_GROUP_ID,
                text=formatted_message,
                message_thread_id=topic_id,
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"❌ Ошибка отправки в тему: {e}")

async def periodic_check():
    """Периодическая проверка новых сообщений"""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        if avito_bot.monitoring_active:
            try:
                await check_new_messages(manual=False)
            except Exception as e:
                print(f"❌ Ошибка периодической проверки: {e}")

async def main():
    """Главная функция запуска бота"""
    print("="*60)
    print("🚀 Бот-мост Авито ↔️ Telegram (Aiogram)")
    print("="*60)
    
    print("🔑 Получаю токен...")
    token = avito_bot.get_access_token()
    if not token:
        print("❌ Не удалось получить токен!")
        return
    
    print("✅ Токен получен!")
    print(f"👤 User ID: {AVITO_USER_ID}")
    print(f"📱 Group ID: {TELEGRAM_GROUP_ID}")
    
    # Регистрируем роутер
    dp.include_router(router)
    
    # Запускаем периодическую проверку
    if AUTO_CHECK_ENABLED:
        asyncio.create_task(periodic_check())
        print("✅ Автопроверка включена")
    
    print("="*60)
    print("🤖 Бот запущен!")
    print(f"⏱ Проверка каждые {CHECK_INTERVAL} сек")
    print("="*60)
    
    # Запускаем polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

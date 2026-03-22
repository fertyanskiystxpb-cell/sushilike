"""
Точка входа приложения бота. LongPoll цикл и диспетчеризация событий.
"""
import time

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from requests.exceptions import ReadTimeout, ConnectionError, RequestException

from config import settings
from database.models import init_db
from bot import core
from bot.handlers import user as user_handlers
from bot.handlers import admin as admin_handlers


def handle_event(vk, event):
    """Обработать одно событие (новое сообщение)."""
    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    user_id = event.obj.message["from_id"]
    text = event.obj.message.get("text", "").strip()
    payload = event.obj.message.get("payload")
    attachments = event.obj.message.get("attachments", [])
    message_id = event.obj.message.get("id")

    if user_id in core.get_operator_ids():
        if admin_handlers.handle_admin_flow(vk, user_id, text, payload, event):
            return

    user_handlers.handle_user_message(vk, user_id, text, payload, attachments, message_id)


def run_bot():
    """Запуск бота (LongPoll цикл)."""
    vk_session = vk_api.VkApi(token=settings.VK_GROUP_TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, group_id=settings.VK_GROUP_ID)

    print("Бот запущен и ожидает события...")

    try:
        init_db()
    except Exception as e:
        print(f"Ошибка init_db: {e}")

    while True:
        try:
            for event in longpoll.listen():
                try:
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        handle_event(vk, event)
                except Exception as e:
                    print(f"Ошибка обработки события: {e}")
        except (ReadTimeout, ConnectionError, RequestException) as e:
            print(f"Сеть: {type(e).__name__}, переподключение через 5 сек...")
            time.sleep(5)
            longpoll = VkBotLongPoll(vk_session, group_id=settings.VK_GROUP_ID)
            continue
        except Exception as e:
            print(f"Ошибка LongPoll: {e}")
            time.sleep(5)
            longpoll = VkBotLongPoll(vk_session, group_id=settings.VK_GROUP_ID)
            continue

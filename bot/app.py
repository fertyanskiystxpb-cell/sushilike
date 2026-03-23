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


def handle_event(vk, event):
    """Обработать одно событие (новое сообщение)."""
    if event.type != VkBotEventType.MESSAGE_NEW:
        return

    user_id = event.obj.message["from_id"]
    text = event.obj.message.get("text", "").strip()
    payload = event.obj.message.get("payload")
    attachments = event.obj.message.get("attachments", [])
    message_id = event.obj.message.get("id")

    # Проверяем состояние пользователя - если он в процессе заказа, обрабатываем все сообщения
    from bot import store
    user_state = store.user_states.get(user_id, {})
    current_state = user_state.get("state", "IDLE")
    expecting_order = bool(user_state.get("expecting_order", False))
    
    # Проверяем флаг - если бот только что ответил, пропускаем следующее сообщение
    if store.user_just_replied.get(user_id, False):
        store.user_just_replied[user_id] = False  # Сбрасываем флаг
        return  # Пропускаем это сообщение
    
    # Для клиентов проверяем, является ли сообщение командой или кнопкой,
    # или пользователь в процессе заказа
    if text and (
        text in ("Начать", "Старт", "🛒 Заказ", "🎁 Наши акции", "📍 Адрес для самовывоза") or
        text in ("⬅ Назад", "❌ Отменить заказ", "🏠 В главное меню") or
        text.startswith("!") or  # Админские команды
        payload or  # Сообщения с payload (кнопки)
        current_state != "IDLE" or  # Любые сообщения в процессе заказа
        expecting_order  # Сообщение с заполненной формой заказа
    ):
        user_handlers.handle_user_message(vk, user_id, text, payload, attachments, message_id)
    # Иначе игнорируем сообщение клиента - бот его не читает


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

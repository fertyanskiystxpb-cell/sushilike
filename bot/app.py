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

    # Диагностика - логируем информацию о пользователе
    from bot import store
    print(f"[DEBUG] Сообщение от {user_id}: '{text}'")
    print(f"[DEBUG] Пользователь в user_states: {user_id in store.user_states}")
    print(f"[DEBUG] Пользователь в user_last_message: {user_id in store.user_last_message}")
    
    if user_id in store.user_last_message:
        print(f"[DEBUG] Последнее сообщение: {store.user_last_message[user_id]}")
    if user_id in store.user_states:
        print(f"[DEBUG] Состояние: {store.user_states[user_id]}")

    # Проверяем состояние пользователя - если он в процессе заказа, обрабатываем все сообщения
    user_state = store.user_states.get(user_id, {})
    current_state = user_state.get("state", "IDLE")
    expecting_order = bool(user_state.get("expecting_order", False))
    
    # Проверяем флаг - если бот только что ответил, пропускаем следующее сообщение
    if store.user_just_replied.get(user_id, False):
        store.user_just_replied[user_id] = False  # Сбрасываем флаг
        return  # Пропускаем это сообщение
    
    # Для клиентов обрабатываем только кнопки и команды, игнорируем обычные сообщения
    if text and (
        text in ("Начать", "Старт", " Адрес для самовывоза") or
        text in ("⬅ Назад", "❌ Отменить заказ", "🏠 В главное меню") or
        text.startswith("!") or  # Админские команды
        payload or  # Сообщения с payload (кнопки)
        current_state != "IDLE" or  # Любые сообщения в процессе заказа
        expecting_order  # Сообщение с заполненной формой заказа
    ):
        print(f"[DEBUG] Обрабатываем сообщение от {user_id}")
        user_handlers.handle_user_message(vk, user_id, text, payload, attachments, message_id)
        # Обновляем время последнего сообщения ПОСЛЕ обработки
        store.user_last_message[user_id] = core.now_utc5()
    else:
        print(f"[DEBUG] Игнорируем сообщение от {user_id} - не команда/кнопка")
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

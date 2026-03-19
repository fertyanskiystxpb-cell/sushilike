"""
Общие утилиты, состояния FSM и функции для бота.
"""
import re
from datetime import datetime, time, timedelta, timezone

from config import settings
from bot import store
from bot.states import (
    STATE_IDLE,
    STATE_CHOOSING_FOOD,
    STATE_SET_CUTLERY,
    STATE_SET_CUTLERY_CUSTOM,
    STATE_SET_EXTRA_SET,
    STATE_SET_ADDRESS,
    STATE_SET_PHONE,
    STATE_SET_PAYMENT_METHOD,
    STATE_SET_CASH_CHANGE,
    STATE_CONFIRM_ORDER,
    STATE_PREORDER_CONFIRM,
    STATE_SET_ORDER_TIME,
)
from bot import keyboards as kbd


ADMIN_ID = settings.VK_ADMIN_ID

TRANSFER_INFO_LINES = [
    f"💳 Перевод: {settings.PAYMENT_BANK}",
    f"Номер: {settings.PAYMENT_ACCOUNT_NUMBER}",
    f"Получатель: {settings.PAYMENT_RECEIVER_NAME}",
]

PAYMENT_REQUEST_LINES = [
    "💳 Оплата переводом:",
    f"Номер: {settings.PAYMENT_ACCOUNT_NUMBER}",
    f"Банк: {settings.PAYMENT_BANK}",
    f"Получатель: {settings.PAYMENT_RECEIVER_NAME}",
    "",
    "Пожалуйста, пришлите скриншот чека в ответ на это сообщение.",
]

ORDER_END_TIME = time(21, 0)


def now_utc5():
    """Текущее время в часовом поясе доставки (по умолчанию UTC+5)."""
    return datetime.now(timezone.utc) + timedelta(hours=settings.TIMEZONE_OFFSET_HOURS)


def order_start_time_for_date(date_obj):
    """Время начала работы (UTC+5): Пн-Пт 10:00, Сб-Вс 12:00."""
    if date_obj.weekday() <= 4:
        return time(10, 0)
    return time(12, 0)


def get_user_state(user_id):
    """Получить состояние пользователя."""
    if user_id not in store.user_states:
        store.user_states[user_id] = {
            "state": STATE_IDLE,
            "order": {},
            "history": [],
            "active_order_id": None,
        }
    return store.user_states[user_id]


def reset_user_state(user_id):
    """Сбросить состояние пользователя."""
    store.user_states[user_id] = {
        "state": STATE_IDLE,
        "order": {},
        "history": [],
        "active_order_id": None,
    }


def send_message(vk, user_id, text, keyboard=None):
    """Универсальная отправка сообщения."""
    return vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=0,
        keyboard=keyboard.get_keyboard() if keyboard else None,
    )


def edit_admin_order_message(vk, order_id, text, keyboard):
    """Редактировать сообщение админа с заказом."""
    entry = store.orders.get(order_id)
    if not entry:
        return False
    msg_id = entry.get("admin_message_id")
    if not msg_id:
        return False
    try:
        vk.messages.edit(
            peer_id=ADMIN_ID,
            message_id=msg_id,
            message=text,
            keyboard=keyboard.get_keyboard() if keyboard else None,
        )
        return True
    except Exception:
        return False


def build_order_summary(order_data):
    """Собрать текстовый итог заказа."""
    lines = [
        "🧾 Ваш заказ:",
        f"— Заказ: {order_data.get('food')}",
        f"— Приборы: {order_data.get('cutlery')}",
        f"— Доп. набор (имбирь/васаби): {order_data.get('extra_set')}",
        f"— Время заказа: {order_data.get('delivery_time')}",
        f"— Адрес доставки: {order_data.get('address')}",
        f"— Телефон: {order_data.get('phone')}",
        f"— Оплата: {order_data.get('payment_method')}",
    ]
    if order_data.get("payment_method") == "Оплата при получении" and order_data.get("cash_change"):
        lines.append(f"— Сдача: {order_data.get('cash_change')}")
    if order_data.get("is_preorder"):
        lines.append("— Флаг: ПРЕДЗАКАЗ")
    return "\n".join(lines)


def push_history(state_info, prev_state):
    """Запомнить предыдущее состояние."""
    state_info["history"].append(prev_state)


def go_back(vk, user_id, state_info):
    """Вернуться на предыдущий шаг оформления заказа."""
    if not state_info["history"]:
        state_info["state"] = STATE_IDLE
        send_message(vk, user_id, "Вы в главном меню.", keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
        return
    prev_state = state_info["history"].pop()
    state_info["state"] = prev_state
    prompt_for_state(vk, user_id, prev_state)


def cancel_order(vk, user_id):
    """Полностью отменить создание заказа."""
    reset_user_state(user_id)
    send_message(
        vk,
        user_id,
        "Заказ отменён. Вы вернулись в главное меню.",
        keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
    )


def prompt_for_state(vk, user_id, state):
    """Отправить пользователю вопрос для текущего шага."""
    if state == STATE_CHOOSING_FOOD:
        send_message(
            vk,
            user_id,
            "Что вы хотите заказать?\nНапишите, пожалуйста, название.",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_ORDER_TIME:
        send_message(
            vk,
            user_id,
            "Во сколько нужен заказ?",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_CUTLERY:
        send_message(
            vk,
            user_id,
            "Сколько приборов (палочек) положить?",
            keyboard=kbd.create_cutlery_keyboard(),
        )
        return
    if state == STATE_SET_CUTLERY_CUSTOM:
        send_message(
            vk,
            user_id,
            "Приборы свыше 4-х штук платные (10₽/шт). Сколько всего приборов вам нужно? (Введите число)",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_EXTRA_SET:
        send_message(
            vk,
            user_id,
            "Имбирь, васаби и соевый соус не входят в стоимость. Общий доп набор рассчитан на 3-4 человека, стоит 100₽. Будете брать?",
            keyboard=kbd.create_yes_no_keyboard(),
        )
        return
    if state == STATE_SET_ADDRESS:
        hint = f"\n{settings.DELIVERY_ZONE_HINT}" if settings.DELIVERY_ZONE_HINT else ""
        send_message(
            vk,
            user_id,
            f"Введите адрес доставки:{hint}".strip(),
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_PHONE:
        send_message(vk, user_id, "Введите номер телефона:", keyboard=kbd.create_order_nav_keyboard())
        return
    if state == STATE_SET_PAYMENT_METHOD:
        send_message(vk, user_id, "Выберите способ оплаты:", keyboard=kbd.create_payment_keyboard())
        return
    if state == STATE_SET_CASH_CHANGE:
        send_message(
            vk,
            user_id,
            "От какой суммы потребуется сдача?",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_PREORDER_CONFIRM:
        now_dt = now_utc5()
        start_today = order_start_time_for_date(now_dt.date())
        now_t = now_dt.time()
        if now_t < start_today:
            question = "Мы еще не работаем, оформить предзаказ на сегодня?"
        else:
            question = "Мы уже закрыты, оформить предзаказ на завтра?"
        send_message(vk, user_id, question, keyboard=kbd.create_preorder_keyboard())
        return
    if state == STATE_CONFIRM_ORDER:
        state_info = get_user_state(user_id)
        summary = build_order_summary(state_info["order"])
        send_message(
            vk,
            user_id,
            summary + "\n\nПроверьте, все ли верно.\nНажмите «Подтвердить заказ» или «Отменить».",
            keyboard=kbd.create_confirm_keyboard(),
        )
        return


def handle_start_or_menu(vk, user_id):
    """Показать главное меню пользователю."""
    reset_user_state(user_id)
    now = now_utc5().time()
    if now < time(12, 0):
        greeting = "Доброе утро"
    elif now < time(18, 0):
        greeting = "Доброго дня"
    else:
        greeting = "Доброго вечера"
    name = ""
    try:
        info = vk.users.get(user_ids=user_id)
        if info:
            name = info[0].get("first_name", "")
    except Exception:
        pass
    send_message(
        vk,
        user_id,
        f"{greeting}, {name}! ✨\n\nДобро пожаловать в Суши Лайк — место, где каждый ролл заслуживает твоего сердечка! 🍣❤️\n\nГотовим из-под ножа, везем быстро, кормим вкусно.\n\nЧто делаем дальше? 👇",
        keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
    )


def register_and_send_order_to_admin(vk, user_id, order_data):
    """Регистрирует заказ и отправляет админу."""
    from database.models import save_order_stub

    summary = build_order_summary(order_data)
    order_id = store.next_order_id
    store.next_order_id += 1
    store.orders[order_id] = {
        "client_id": user_id,
        "order": dict(order_data),
        "summary": summary,
        "status": "NEW",
        "price": None,
        "admin_message_id": None,
        "created_at": now_utc5().date().isoformat(),
    }
    try:
        save_order_stub(order_id=order_id, user_id=user_id, payload=dict(order_data), status="NEW")
    except Exception as e:
        print(f"[DB_STUB] save_order_stub error: {e}")

    if order_data.get("is_preorder"):
        preorder_flag = "\n\n🗓 ПРЕДЗАКАЗ (на сегодня)" if order_data.get("preorder_same_day") else "\n\n🗓 ПРЕДЗАКАЗ (на завтра)"
    else:
        preorder_flag = ""
    text = f"📩 Новый заказ #{order_id} от пользователя ID {user_id}:\n\n{summary}{preorder_flag}"
    keyboard = kbd.create_admin_new_order_keyboard(order_id=order_id, client_id=user_id)

    msg_id = vk.messages.send(
        user_id=ADMIN_ID,
        message=text,
        random_id=0,
        keyboard=keyboard.get_keyboard(),
    )
    store.orders[order_id]["admin_message_id"] = msg_id
    send_message(vk, ADMIN_ID, "Меню администратора.", keyboard=kbd.create_admin_menu_keyboard())


def get_daily_stats():
    """Статистика заказов за сегодня: (новых, принято, отказано, сумма оплаченных)."""
    today = now_utc5().date().isoformat()
    new_count = 0
    accepted = 0
    cancelled = 0
    paid_sum = 0
    for o in store.orders.values():
        created = o.get("created_at")
        if created != today:
            continue
        status = o.get("status")
        if status == "NEW":
            new_count += 1
        elif status == "CANCELLED":
            cancelled += 1
        elif status in ("PAID", "WAIT_1_1_5", "WAIT_1_5_2", "ACCEPTED", "WAITING_FOR_CHECK", "IN_PROGRESS"):
            accepted += 1
        if status == "PAID" and o.get("price"):
            try:
                paid_sum += int(re.sub(r"\D", "", str(o["price"])))
            except (ValueError, TypeError):
                pass
    return new_count, accepted, cancelled, paid_sum

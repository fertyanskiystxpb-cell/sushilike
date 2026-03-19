"""
Обработка сообщений пользователей (FSM оформления заказа).
"""
from datetime import datetime, time, timedelta

from config import settings
from bot import store
from bot import core
from bot import keyboards as kbd
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
    STATE_CONTACT_ADMIN,
    STATE_WAITING_FOR_CHECK,
    CANCEL_ORDER_TEXT,
    BACK_TEXT,
    MENU_TEXT,
    CONTACT_ADMIN_TEXT,
    ADMIN_MENU_TEXT,
)
from bot.services.promos_service import read_promos_text


def handle_user_message(vk, user_id, text, payload, attachments, message_id):
    """Главный обработчик сообщений от обычных пользователей (не админа)."""
    state_info = core.get_user_state(user_id)
    state = state_info["state"]
    order = state_info["order"]

    if state == STATE_WAITING_FOR_CHECK:
        return _handle_waiting_for_check(vk, user_id, text, attachments, message_id, state_info)

    now_t = core.now_utc5().time()

    if text == CANCEL_ORDER_TEXT:
        core.cancel_order(vk, user_id)
        return
    if text == BACK_TEXT:
        core.go_back(vk, user_id, state_info)
        return
    if text == MENU_TEXT:
        core.handle_start_or_menu(vk, user_id)
        return

    if state == STATE_IDLE:
        _handle_idle(vk, user_id, text, state_info, now_t)
        return

    if state == STATE_CONTACT_ADMIN:
        _handle_contact_admin(vk, user_id, text)
        return

    if state == STATE_PREORDER_CONFIRM:
        _handle_preorder_confirm(vk, user_id, text, state_info, order)
        return

    if state == STATE_CHOOSING_FOOD:
        if not text:
            core.send_message(vk, user_id, "Напишите, пожалуйста, что хотите заказать.", keyboard=kbd.create_order_nav_keyboard())
            return
        order["food"] = text
        core.push_history(state_info, STATE_CHOOSING_FOOD)
        state_info["state"] = STATE_SET_ORDER_TIME
        core.prompt_for_state(vk, user_id, STATE_SET_ORDER_TIME)
        return

    if state == STATE_SET_ORDER_TIME:
        _handle_set_order_time(vk, user_id, text, state_info, order)
        return

    if state == STATE_SET_CUTLERY:
        _handle_set_cutlery(vk, user_id, text, state_info, order)
        return

    if state == STATE_SET_CUTLERY_CUSTOM:
        try:
            n = int(text.strip())
            if n < 5:
                core.send_message(vk, user_id, "Введите число от 5 и выше.", keyboard=kbd.create_order_nav_keyboard())
                return
            if n > 50:
                core.send_message(vk, user_id, "Слишком большое число. Введите до 50.", keyboard=kbd.create_order_nav_keyboard())
                return
        except ValueError:
            core.send_message(vk, user_id, "Введите число (например: 6).", keyboard=kbd.create_order_nav_keyboard())
            return
        order["cutlery"] = str(n)
        core.push_history(state_info, STATE_SET_CUTLERY_CUSTOM)
        state_info["state"] = STATE_SET_EXTRA_SET
        core.prompt_for_state(vk, user_id, STATE_SET_EXTRA_SET)
        return

    if state == STATE_SET_EXTRA_SET:
        order["extra_set"] = text
        core.push_history(state_info, STATE_SET_EXTRA_SET)
        state_info["state"] = STATE_SET_ADDRESS
        core.prompt_for_state(vk, user_id, STATE_SET_ADDRESS)
        return

    if state == STATE_SET_ADDRESS:
        if not text.strip():
            core.send_message(vk, user_id, "Введите адрес доставки.", keyboard=kbd.create_order_nav_keyboard())
            return
        order["address"] = text.strip()
        core.push_history(state_info, STATE_SET_ADDRESS)
        state_info["state"] = STATE_SET_PHONE
        core.prompt_for_state(vk, user_id, STATE_SET_PHONE)
        return

    if state == STATE_SET_PHONE:
        digit_count = sum(1 for c in text if c.isdigit())
        if digit_count < 10:
            core.send_message(vk, user_id, "Введите корректный номер телефона (минимум 10 цифр).", keyboard=kbd.create_order_nav_keyboard())
            return
        order["phone"] = text.strip()
        core.push_history(state_info, STATE_SET_PHONE)
        state_info["state"] = STATE_SET_PAYMENT_METHOD
        core.prompt_for_state(vk, user_id, STATE_SET_PAYMENT_METHOD)
        return

    if state == STATE_SET_PAYMENT_METHOD:
        _handle_set_payment_method(vk, user_id, text, state_info, order)
        return

    if state == STATE_SET_CASH_CHANGE:
        order["cash_change"] = text
        core.push_history(state_info, STATE_SET_CASH_CHANGE)
        state_info["state"] = STATE_CONFIRM_ORDER
        core.prompt_for_state(vk, user_id, STATE_CONFIRM_ORDER)
        return

    if state == STATE_CONFIRM_ORDER:
        _handle_confirm_order(vk, user_id, text, order)
        return


def _handle_waiting_for_check(vk, user_id, text, attachments, message_id, state_info):
    has_media = any(att.get("type") in ("photo", "doc") for att in attachments)
    if has_media and message_id:
        order_id = state_info.get("active_order_id")
        if not order_id:
            for oid in sorted(store.orders.keys(), reverse=True):
                o = store.orders[oid]
                if o.get("client_id") == user_id and o.get("status") in ("ACCEPTED", "WAITING_FOR_CHECK"):
                    order_id = oid
                    break
        if not order_id:
            core.send_message(vk, user_id, "Не найден заказ для прикрепления чека. Обратитесь к администратору.")
            return
        name = ""
        try:
            info = vk.users.get(user_ids=user_id)
            if info:
                name = info[0].get("first_name", "")
        except Exception:
            pass
        vk.messages.send(
            peer_id=core.ADMIN_ID,
            message=f"Поступил скриншот оплаты по заказу #{order_id} от клиента {name} (ID {user_id})",
            random_id=0,
            forward_messages=message_id,
            keyboard=kbd.create_admin_check_confirm_keyboard(order_id, user_id).get_keyboard(),
        )
        core.send_message(vk, user_id, "✅ Чек получен. Ожидайте подтверждения оплаты администратором.")
    else:
        core.send_message(vk, user_id, "Пожалуйста, пришлите скриншот чека (фото/документ).")


def _handle_idle(vk, user_id, text, state_info, now_t):
    if text in ("/start", "Начать", "Старт"):
        core.handle_start_or_menu(vk, user_id)
        return

    if text == "🛍 Сделать заказ":
        if not store.accepting_orders_enabled:
            reason = store.accepting_orders_reason.strip() or "приём заказов временно отключён."
            core.send_message(vk, user_id, f"❌ Сейчас мы не принимаем заказы.\nПричина: {reason}")
            return
        start_today = core.order_start_time_for_date(core.now_utc5().date())
        if now_t < start_today or now_t >= core.ORDER_END_TIME:
            state_info["state"] = STATE_PREORDER_CONFIRM
            state_info["history"] = []
            core.prompt_for_state(vk, user_id, STATE_PREORDER_CONFIRM)
            return
        state_info["state"] = STATE_CHOOSING_FOOD
        state_info["history"] = []
        core.prompt_for_state(vk, user_id, STATE_CHOOSING_FOOD)
        return

    if text == "🎁 Акции":
        core.send_message(vk, user_id, read_promos_text(), keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
        return

    if text == "📍 Адрес":
        core.send_message(vk, user_id, f"📍 Мы находимся по адресу:\n{settings.ORDER_ADDRESS_TEXT}")
        return

    if text == CONTACT_ADMIN_TEXT:
        state_info["state"] = STATE_CONTACT_ADMIN
        core.send_message(
            vk,
            user_id,
            "Напишите ваше сообщение администратору. Я перешлю его.\n"
            "Чтобы отменить — нажмите «🏠 В главное меню».",
            keyboard=kbd.create_contact_admin_keyboard(),
        )
        return

    if text == ADMIN_MENU_TEXT and user_id == core.ADMIN_ID:
        core.send_message(vk, core.ADMIN_ID, "Меню администратора.", keyboard=kbd.create_admin_menu_keyboard())
        return

    core.handle_start_or_menu(vk, user_id)


def _handle_contact_admin(vk, user_id, text):
    if not text.strip():
        core.send_message(vk, user_id, "Напишите ваше сообщение.", keyboard=kbd.create_contact_admin_keyboard())
        return
    core.send_message(
        vk,
        core.ADMIN_ID,
        f"👨‍💬 Обращение к администратору от пользователя ID {user_id}:\n\n{text}",
        keyboard=kbd.create_admin_menu_keyboard(),
    )
    core.send_message(
        vk,
        user_id,
        "Сообщение отправлено администратору. Ожидайте ответа.",
        keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
    )
    core.reset_user_state(user_id)


def _handle_preorder_confirm(vk, user_id, text, state_info, order):
    if text.lower() == "да":
        order["is_preorder"] = True
        now_t = core.now_utc5().time()
        start_today = core.order_start_time_for_date(core.now_utc5().date())
        if now_t < start_today:
            order["preorder_tomorrow"] = False
            order["preorder_same_day"] = True
        else:
            order["preorder_tomorrow"] = True
            order["preorder_same_day"] = False
        state_info["state"] = STATE_CHOOSING_FOOD
        core.prompt_for_state(vk, user_id, STATE_CHOOSING_FOOD)
        return
    if text.lower() == "нет":
        core.cancel_order(vk, user_id)
        return
    core.send_message(vk, user_id, "Пожалуйста, выберите Да или Нет.", keyboard=kbd.create_preorder_keyboard())


def _handle_set_order_time(vk, user_id, text, state_info, order):
    raw = text.replace(".", ":").replace(" ", "")
    if ":" in raw:
        parts = raw.split(":")
        if len(parts) != 2:
            core.send_message(vk, user_id, "Неверный формат времени. Пример: 18:30", keyboard=kbd.create_order_nav_keyboard())
            return
        try:
            hh, mm = int(parts[0]), int(parts[1])
        except Exception:
            core.send_message(vk, user_id, "Неверный формат времени. Пример: 18:30", keyboard=kbd.create_order_nav_keyboard())
            return
    else:
        try:
            hh, mm = int(raw), 0
        except Exception:
            core.send_message(vk, user_id, "Неверный формат времени. Пример: 18:30", keyboard=kbd.create_order_nav_keyboard())
            return

    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        core.send_message(
            vk, user_id,
            "Время вне диапазона. Используйте формат ЧЧ:ММ (например 09:30 или 18:30).",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return

    requested_time = time(hh, mm)
    now_dt = core.now_utc5()
    start_today = core.order_start_time_for_date(now_dt.date())

    if order.get("preorder_same_day"):
        delivery_date = now_dt.date()
    elif order.get("preorder_tomorrow"):
        delivery_date = now_dt.date() + timedelta(days=1)
    elif requested_time < start_today or requested_time >= core.ORDER_END_TIME:
        delivery_date = now_dt.date() + timedelta(days=1)
    else:
        delivery_date = now_dt.date() + timedelta(days=1) if requested_time <= now_dt.time() else now_dt.date()

    delivery_dt = datetime.combine(delivery_date, requested_time)
    order["delivery_time"] = requested_time.strftime("%H:%M")
    order["delivery_datetime"] = delivery_dt.strftime("%Y-%m-%d %H:%M")
    start_delivery = core.order_start_time_for_date(delivery_date)
    order["is_preorder"] = bool(order.get("preorder_tomorrow")) or (
        requested_time < start_delivery or requested_time >= core.ORDER_END_TIME
    )

    core.push_history(state_info, STATE_SET_ORDER_TIME)
    state_info["state"] = STATE_SET_CUTLERY
    core.prompt_for_state(vk, user_id, STATE_SET_CUTLERY)


def _handle_set_cutlery(vk, user_id, text, state_info, order):
    if text in ("1", "2", "3", "4"):
        order["cutlery"] = text
        core.push_history(state_info, STATE_SET_CUTLERY)
        state_info["state"] = STATE_SET_EXTRA_SET
        core.prompt_for_state(vk, user_id, STATE_SET_EXTRA_SET)
        return
    if text == "5+":
        core.push_history(state_info, STATE_SET_CUTLERY)
        state_info["state"] = STATE_SET_CUTLERY_CUSTOM
        core.prompt_for_state(vk, user_id, STATE_SET_CUTLERY_CUSTOM)
        return
    core.send_message(vk, user_id, "Пожалуйста, выберите количество приборов кнопкой.", keyboard=kbd.create_cutlery_keyboard())


def _handle_set_payment_method(vk, user_id, text, state_info, order):
    order["payment_method"] = text
    core.push_history(state_info, STATE_SET_PAYMENT_METHOD)
    if order["payment_method"] == "Оплата при получении":
        state_info["state"] = STATE_SET_CASH_CHANGE
        core.prompt_for_state(vk, user_id, STATE_SET_CASH_CHANGE)
        return
    if order["payment_method"] == "Предоплата переводом":
        state_info["state"] = STATE_CONFIRM_ORDER
        core.prompt_for_state(vk, user_id, STATE_CONFIRM_ORDER)
        return
    state_info["history"].pop()
    order.pop("payment_method", None)
    core.send_message(
        vk,
        user_id,
        "Пожалуйста, выберите способ оплаты кнопкой: Оплата при получении или Предоплата переводом.",
        keyboard=kbd.create_payment_keyboard(),
    )


def _handle_confirm_order(vk, user_id, text, order):
    if "подтверд" in text.lower():
        core.register_and_send_order_to_admin(vk, user_id, order)
        core.reset_user_state(user_id)
        core.send_message(
            vk,
            user_id,
            "Спасибо! Ваш заказ отправлен администратору.\nОжидайте сообщения о времени доставки 🙌",
            keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
        )
        return
    if "отмен" in text.lower():
        core.cancel_order(vk, user_id)
        return
    core.send_message(
        vk,
        user_id,
        "Пожалуйста, подтвердите или отмените заказ с помощью кнопок ниже.",
        keyboard=kbd.create_confirm_keyboard(),
    )

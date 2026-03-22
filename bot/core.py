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
    STATE_SET_PAYMENT_TRANSFER_TIMING,
    STATE_CONFIRM_ORDER,
    STATE_PREORDER_CONFIRM,
    STATE_SET_ORDER_TIME,
)
from bot import keyboards as kbd


def get_admin_ids():
    """Список ID операторов из конфига (.env), без учёта БД."""
    ids_str = getattr(settings, "VK_ADMIN_IDS", "") or ""
    if ids_str.strip():
        try:
            return [int(x.strip()) for x in ids_str.split(",") if x.strip()]
        except (ValueError, AttributeError):
            pass
    return [settings.VK_ADMIN_ID]


def get_operator_ids():
    """Актуальный список операторов: из SQLite (employees), иначе из конфига."""
    if getattr(settings, "DB_ENABLED", False):
        try:
            from database.models import list_employee_ids

            ids = list_employee_ids()
            if ids:
                return ids
        except Exception:
            pass
    return get_admin_ids()


def get_admin_id():
    """Первый ID из списка операторов для обратной совместимости."""
    ids = get_operator_ids()
    return ids[0] if ids else settings.VK_ADMIN_ID

TRANSFER_INFO_LINES = [
    f"💳 Перевод: Т-банк/Сбербанк",
    f"Номер: {settings.PAYMENT_ACCOUNT_NUMBER}",
    f"Получатель: {settings.PAYMENT_RECEIVER_NAME}",
]

PAYMENT_REQUEST_LINES = [
    "💳 Оплата переводом:",
    f"Номер: {settings.PAYMENT_ACCOUNT_NUMBER}",
    f"Банк: Т-банк/Сбербанк",
    f"Получатель: {settings.PAYMENT_RECEIVER_NAME}",
    "",
    "Пожалуйста, пришлите скриншот чека в ответ на это сообщение.",
]

# Только просьба о чеке (реквизиты уже отправлены при оформлении заказа).
PAYMENT_CHECK_ONLY_LINES = [
    "Пожалуйста, пришлите скриншот чека в ответ на это сообщение (фото или документ).",
]

ORDER_END_TIME = time(21, 0)


def GetTimeBasedGreeting():
    t = now_utc5().time()
    if time(0, 0) <= t < time(6, 0):
        return "Доброй ночи"
    if time(6, 0) <= t < time(12, 0):
        return "Доброе утро"
    if time(12, 0) <= t < time(18, 0):
        return "Добрый день"
    return "Добрый вечер"


def get_order_thanks_closing():
    """Фраза благодарности в конце сообщения при принятии заказа (по времени суток)."""
    t = now_utc5().time()
    if time(0, 0) <= t < time(6, 0):
        return "Спасибо за заказ, хорошей вам ночи! 😊"
    if time(6, 0) <= t < time(18, 0):
        return "Спасибо за заказ, хорошего вам дня! 😊"
    return "Спасибо за заказ, хорошего вам вечера! 😊"


def parse_price_to_int(price_val):
    """Извлечь целую сумму из строки цены (например «1 490₽» → 1490)."""
    if price_val is None:
        return None
    try:
        n = int(re.sub(r"\D", "", str(price_val)))
        return n if n > 0 else None
    except (ValueError, TypeError):
        return None


def build_client_order_placed_message(order_data):
    """
    Сообщение клиенту сразу после подтверждения заказа: всегда реквизиты.
    Просьба прислать чек — только при оплате «Переводом сейчас».
    """
    pm = (order_data or {}).get("payment_method") or ""
    lines = [
        "Спасибо! Ваш заказ отправлен оператору.\nОжидайте сообщения о сумме и времени ожидания 🙌",
        "",
        "💳 Реквизиты для оплаты:",
        *TRANSFER_INFO_LINES,
    ]
    if pm == "Переводом сейчас":
        lines.extend(
            [
                "",
                "После того как оператор укажет сумму заказа, переведите оплату по реквизитам выше "
                "и пришлите сюда скриншот чека (фото или документ).",
            ]
        )
    return "\n".join(lines)


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


def get_user_full_name(vk, user_id):
    """Вернуть имя и фамилию пользователя VK."""
    try:
        info = vk.users.get(user_ids=user_id)
        if info:
            first_name = (info[0].get("first_name") or "").strip()
            last_name = (info[0].get("last_name") or "").strip()
            full_name = f"{first_name} {last_name}".strip()
            if full_name:
                return full_name
    except Exception:
        pass
    return f"ID {user_id}"


def format_user_mention(vk, user_id):
    """Вернуть кликабельное имя пользователя в формате VK."""
    full_name = get_user_full_name(vk, user_id)
    return f"[id{user_id}|{full_name}]"


def edit_admin_order_message(vk, order_id, text, keyboard):
    """Редактировать сообщение админа с заказом (у всех админов, кому оно было отправлено)."""
    entry = store.orders.get(order_id)
    if not entry:
        return False
    admin_msgs = entry.get("admin_message_ids") or {}
    if not admin_msgs and entry.get("admin_message_id"):
        fallback = get_operator_ids()
        aid0 = fallback[0] if fallback else get_admin_id()
        admin_msgs = {aid0: entry["admin_message_id"]}
    if not admin_msgs:
        return False
    ok = False
    for aid, msg_id in admin_msgs.items():
        try:
            vk.messages.edit(
                peer_id=aid,
                message_id=msg_id,
                message=text,
                keyboard=keyboard.get_keyboard() if keyboard else None,
            )
            ok = True
        except Exception:
            pass
    return ok


def build_order_summary(order_data):
    """Собрать текстовый итог заказа."""
    lines = [
        "🧾 Ваш заказ:",
        f"— Заказ: {order_data.get('food')}",
        f"— Приборы: {order_data.get('cutlery')}",
        f"— Доп. набор: {order_data.get('extra_set', '—')}",
        f"— Адрес доставки: {order_data.get('address')}",
        f"— Телефон: {order_data.get('phone')}",
        f"— Оплата: {order_data.get('payment_method')}",
        f"— Комментарий к заказу: {order_data.get('order_time', '—')}",
    ]
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
            "Что будете заказывать?\n Укажите название или номер.",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_CUTLERY:
        send_message(
            vk,
            user_id,
            "Сколько приборов (палочек) положить?",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_CUTLERY_CUSTOM:
        send_message(
            vk,
            user_id,
            "Сколько всего приборов вам нужно?",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_SET_EXTRA_SET:
        send_message(
            vk,
            user_id,
            "Имбирь, васаби и соевый соус не входят в стоимость. Общий доп набор рассчитан на 3-4 человека, стоит 100₽. Будете брать?",
            keyboard=kbd.create_order_nav_keyboard(),
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
    if state == STATE_SET_PAYMENT_TRANSFER_TIMING:
        send_message(
            vk,
            user_id,
            "Оплатить сейчас или при получении?",
            keyboard=kbd.create_payment_transfer_timing_keyboard(),
        )
        return
    if state == STATE_SET_ORDER_TIME:
        send_message(
            vk,
            user_id,
            "Комментарий к заказу.",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    if state == STATE_PREORDER_CONFIRM:
        now_dt = now_utc5()
        start_today = order_start_time_for_date(now_dt.date())
        now_t = now_dt.time()
        if now_t < start_today:
            question = "Мы еще не не открылись, хотите оформить предзаказ?"
        else:
            question = "Мы уже закрыты, хотите оформить предзаказ?"
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
    greeting = GetTimeBasedGreeting()
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
        f"{greeting}, {name}! ✨\n\nДобро пожаловать в Суши Лайк — место, где каждый ролл заслуживает твоего сердечка! 🍣❤️\n\nДоставка со вкусом.\n\nЧто делаем дальше? 👇",
        keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
    )


def sync_order_to_db(order_id: int) -> None:
    """Записать в SQLite текущее состояние заказа из памяти."""
    if not getattr(settings, "DB_ENABLED", False):
        return
    entry = store.orders.get(order_id)
    if not entry:
        return
    try:
        from database.models import update_order_record

        update_order_record(
            order_id,
            user_id=int(entry["client_id"]),
            payload=dict(entry.get("order") or {}),
            status=str(entry.get("status") or "NEW"),
            price=entry.get("price"),
            gift=entry.get("gift"),
            business_date=entry.get("created_at"),
        )
    except Exception as e:
        print(f"[DB] sync_order_to_db error: {e}")


def register_and_send_order_to_admin(vk, user_id, order_data):
    """Регистрирует заказ и отправляет админу."""
    from database.models import save_order_stub

    summary = build_order_summary(order_data)
    order_id = store.next_order_id
    store.next_order_id += 1
    business_date = now_utc5().date().isoformat()
    store.orders[order_id] = {
        "client_id": user_id,
        "order": dict(order_data),
        "summary": summary,
        "status": "NEW",
        "price": None,
        "gift": None,
        "admin_message_id": None,
        "created_at": business_date,
    }
    try:
        save_order_stub(
            order_id=order_id,
            user_id=user_id,
            payload=dict(order_data),
            status="NEW",
            business_date=business_date,
        )
    except Exception as e:
        print(f"[DB_STUB] save_order_stub error: {e}")

    if order_data.get("is_preorder"):
        preorder_flag = "\n\n🗓 ПРЕДЗАКАЗ" if order_data.get("preorder_same_day") else "\n\n🗓 ПРЕДЗАКАЗ (на завтра)"
    else:
        preorder_flag = ""
    client_mention = format_user_mention(vk, user_id)
    text = f"📩 Новый заказ #{order_id} от клиента {client_mention}:\n\n{summary}{preorder_flag}"
    keyboard = kbd.create_admin_new_order_keyboard(order_id=order_id, client_id=user_id)
    kbd_json = keyboard.get_keyboard()

    admin_message_ids = {}
    for aid in get_operator_ids():
        try:
            msg_id = vk.messages.send(
                user_id=aid,
                message=text,
                random_id=0,
                keyboard=kbd_json,
            )
            admin_message_ids[aid] = msg_id
        except Exception:
            pass
    store.orders[order_id]["admin_message_ids"] = admin_message_ids
    if not admin_message_ids and get_operator_ids():
        store.orders[order_id]["admin_message_id"] = None
    for aid in get_operator_ids():
        try:
            send_message(vk, aid, "Меню оператора.", keyboard=kbd.create_admin_menu_keyboard())
        except Exception:
            pass

    # Сразу после оформления — реквизиты всем; просьба о чеке только при «Переводом сейчас».
    send_message(
        vk,
        user_id,
        build_client_order_placed_message(order_data),
        keyboard=kbd.create_main_menu_keyboard_for_user(user_id),
    )


def get_daily_stats():
    """Статистика заказов за сегодня: (новых, принято, отказано, сумма оплаченных). Сброс по календарной дате UTC+5."""
    today = now_utc5().date().isoformat()
    if getattr(settings, "DB_ENABLED", False):
        try:
            from database.models import fetch_daily_stats

            return fetch_daily_stats(today)
        except Exception:
            pass
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

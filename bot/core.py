"""
Общие утилиты, состояния FSM и функции для бота.
"""
import re
from datetime import datetime, time, timedelta, timezone

from config import settings
from bot import store
from bot.states import (
    STATE_IDLE,
    STATE_WAITING_FOR_CHECK,
)
from bot import keyboards as kbd


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
    """Приветствие по времени суток с использованием настроек из конфига."""
    t = now_utc5().time()
    if time(0, 0) <= t < time(6, 0):
        base_greeting = settings.GREETING_NIGHT
    elif time(6, 0) <= t < time(12, 0):
        base_greeting = settings.GREETING_MORNING
    elif time(12, 0) <= t < time(18, 0):
        base_greeting = settings.GREETING_DAY
    else:
        base_greeting = settings.GREETING_EVENING
    
    return base_greeting


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
    # Если есть полный текст заказа, используем его
    if order_data.get('full_text'):
        lines = [
            "🧾 Заказ клиента:",
            order_data.get('full_text'),
        ]
    else:
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


def get_setting_from_db(key, default=""):
    """Получает настройку из базы данных."""
    if not settings.DB_ENABLED:
        return default
        
    try:
        from database.models import _connect
        with _connect() as conn:
            # Создаем таблицу настроек если нет
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row['value'] if row else default
    except Exception as e:
        print(f"[DEBUG] Ошибка получения настройки {key} из БД: {e}")
        return default


def save_setting_to_db(key, value):
    """Сохраняет настройку в базу данных."""
    if not settings.DB_ENABLED:
        return
        
    try:
        from database.models import _connect
        with _connect() as conn:
            # Создаем таблицу настроек если нет
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Сохраняем или обновляем настройку
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
            """, (key, value))
            
            conn.commit()
        
        # Обновляем в runtime
        if hasattr(settings, key):
            setattr(settings, key, value)
            
        print(f"[DEBUG] Настройка {key} сохранена в БД: {value}")
    except Exception as e:
        print(f"[DEBUG] Ошибка сохранения настройки {key} в БД: {e}")


def handle_start_or_menu(vk, user_id):
    """Показать главное меню пользователю."""
    reset_user_state(user_id)
    
    # Проверяем, нужно ли показывать приветствие (только раз в сутки)
    from datetime import date
    today = date.today()
    show_greeting = True
    
    if user_id in store.user_last_message:
        if store.user_last_message[user_id] == today:
            show_greeting = False
    
    if show_greeting:
        try:
            # Получаем базовое приветствие по времени суток
            greeting_message = GetTimeBasedGreeting()
            
            # Получаем информацию о пользователе
            user_info = vk.users.get(user_ids=user_id)[0]
            first_name = user_info.get('first_name', 'Гость')
            
            # Получаем дополнительный текст из БД
            extra_text = get_setting_from_db('GREETING_EXTRA') or ''
            
            # Формируем приветствие
            if extra_text.strip():
                full_greeting = f"{greeting_message}, {first_name}! ✨\n\n{extra_text}"
            else:
                full_greeting = f"{greeting_message}, {first_name}! ✨"
            
            # Отправляем приветствие с главным меню
            send_message(vk, user_id, full_greeting, keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
            
        except Exception as e:
            print(f"[DEBUG] Ошибка при отправке приветствия: {e}")
            send_message(vk, user_id, "Добро пожаловать!", keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
    else:
        # Если приветствие не нужно, просто отправляем меню
        send_message(vk, user_id, "Главное меню:", keyboard=kbd.create_main_menu_keyboard_for_user(user_id))


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

from __future__ import annotations

from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from config import settings
from bot.states import (
    BACK_TEXT,
    CANCEL_ORDER_TEXT,
    CONTACT_ADMIN_TEXT,
    MENU_TEXT,
    ADMIN_MENU_TEXT,
    ADMIN_TO_USER_MENU_TEXT,
    STATE_SET_CUTLERY,
    STATE_SET_CUTLERY_CUSTOM,
)


def create_main_menu_keyboard() -> VkKeyboard:
    """Главное меню. Кнопка «Акции» — ссылка на стену группы."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("🛍 Сделать заказ", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_openlink_button("📋 Наше меню", "https://vk.com/market-175111431")
    keyboard.add_line()
    keyboard.add_openlink_button("🎁 Акции", settings.GROUP_WALL_URL)
    keyboard.add_line()
    keyboard.add_button("📍 Адрес", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button(CONTACT_ADMIN_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_main_menu_keyboard_for_user(user_id: int) -> VkKeyboard:
    from bot import core
    keyboard = create_main_menu_keyboard()
    if user_id in core.get_operator_ids():
        keyboard.add_line()
        keyboard.add_button(ADMIN_MENU_TEXT, color=VkKeyboardColor.PRIMARY)
    return keyboard


def create_contact_admin_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_order_nav_keyboard(one_time: bool = False) -> VkKeyboard:
    keyboard = VkKeyboard(one_time=one_time, inline=False)
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(CANCEL_ORDER_TEXT, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_yes_no_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("Да", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("Нет", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(CANCEL_ORDER_TEXT, color=VkKeyboardColor.NEGATIVE)
    return keyboard


def create_payment_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("Наличными", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("Переводом", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(CANCEL_ORDER_TEXT, color=VkKeyboardColor.NEGATIVE)
    return keyboard


def create_payment_transfer_timing_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("Сейчас", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("При получении", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(CANCEL_ORDER_TEXT, color=VkKeyboardColor.NEGATIVE)
    return keyboard


def create_preorder_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("Да", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("Нет", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_cutlery_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("1", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("2", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("3", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("4", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("5+", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(CANCEL_ORDER_TEXT, color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_confirm_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=True, inline=False)
    keyboard.add_button("✅ Подтвердить заказ", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("❌ Отменить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button(BACK_TEXT, color=VkKeyboardColor.SECONDARY)
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_admin_reply_keyboard(user_id: int) -> VkKeyboard:
    """Клавиатура с кнопкой "Ответить" для сообщений от клиентов."""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "✉ Ответить",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_REPLY", "user_id": user_id},
    )
    return keyboard


def create_admin_order_list_keyboard(order_id: int, client_id: int, payment_method: str) -> VkKeyboard:
    """Клавиатура для заказа в списке активных заказов."""
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "✅ Готов",
        color=VkKeyboardColor.POSITIVE,
        payload={"type": "ADMIN_ACTION", "action": "MARK_READY", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "⏱ Время",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "CUSTOM_WAIT_TIME", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_line()
    keyboard.add_button(
        "✉ Ответ",
        color=VkKeyboardColor.SECONDARY,
        payload={"type": "ADMIN_ACTION", "action": "START_REPLY", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "❌ Отменить",
        color=VkKeyboardColor.NEGATIVE,
        payload={"type": "ADMIN_ACTION", "action": "CANCEL_ORDER", "order_id": order_id, "client_id": client_id},
    )
    if payment_method in ("Наличными", "Переводом при получении"):
        keyboard.add_line()
        keyboard.add_button(
            "💵 Оплата получена",
            color=VkKeyboardColor.POSITIVE,
            payload={"type": "ADMIN_ACTION", "action": "PAYMENT_CONFIRMED", "order_id": order_id, "client_id": client_id},
        )
    keyboard.add_line()
    keyboard.add_button(
        "🎁 Подарки",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "OPEN_GIFTS_MENU", "order_id": order_id, "client_id": client_id},
    )
    return keyboard


def create_admin_gifts_management_keyboard() -> VkKeyboard:
    """Клавиатура для управления подарками в меню админа."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("📋 Список подарков", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("➕ Добавить подарок", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🗑 Удалить подарок", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_button(ADMIN_MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_admin_menu_keyboard() -> VkKeyboard:
    """Обычная клавиатура админа (не инлайн)."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("📋 Текущие заказы", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Статистика за день", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button("🎁 Управление подарками", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("✉ Написать клиенту", color=VkKeyboardColor.PRIMARY)
    keyboard.add_line()
    keyboard.add_button(ADMIN_TO_USER_MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_admin_new_order_keyboard(order_id: int, client_id: int) -> VkKeyboard:
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "✅ Принять",
        color=VkKeyboardColor.POSITIVE,
        payload={"type": "ADMIN_ACTION", "action": "ACCEPT_FLOW", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "❌ Отменить",
        color=VkKeyboardColor.NEGATIVE,
        payload={"type": "ADMIN_ACTION", "action": "CANCEL_ORDER", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_line()
    keyboard.add_button(
        "✉ Ответ",
        color=VkKeyboardColor.SECONDARY,
        payload={"type": "ADMIN_ACTION", "action": "START_REPLY", "order_id": order_id, "client_id": client_id},
    )
    return keyboard


# Подарки: id -> (мин. сумма чека, полное название для клиента)
ADMIN_GIFT_CATALOG: dict[str, tuple[int, str]] = {
    "none": (0, "Без подарка"),
    "from_1500": (1500, "Футоролл с лососем 5шт"),
    "from_2000": (2000, "Запеченный острый футоролл 5шт"),
    "from_3000": (3000, "Пицца чикен спайси"),
    "bday_2000": (2000, "Пицца пепперони (день рождения)"),
    "bday_2500": (2500, "Сет фишки (день рождения)"),
}

# Порядок кнопок в подменю (короткие подписи до 40 символов)
ADMIN_GIFT_BUTTON_ORDER: list[tuple[str, str]] = [
    ("none", "Без подарка"),
    ("from_1500", "От 1500 — футоролл лосось 5шт"),
    ("from_2000", "От 2000 — запеч. острый футо 5шт"),
    ("from_3000", "От 3000 — пицца чикен спайси"),
    ("bday_2000", "Др от 2000 — пицца пепперони"),
    ("bday_2500", "Др от 2500 — сет фишки"),
]


def create_admin_gifts_keyboard(order_id: int, client_id: int, price_int: int) -> VkKeyboard:
    """Инлайн-кнопки подарков: доступны варианты, где сумма чека >= порога."""
    keyboard = VkKeyboard(inline=True)
    first = True
    for gift_id, label in ADMIN_GIFT_BUTTON_ORDER:
        min_sum, _ = ADMIN_GIFT_CATALOG[gift_id]
        if gift_id != "none" and price_int < min_sum:
            continue
        if not first:
            keyboard.add_line()
        first = False
        keyboard.add_button(
            label[:40],
            color=VkKeyboardColor.SECONDARY,
            payload={
                "type": "ADMIN_ACTION",
                "action": "SELECT_GIFT",
                "order_id": order_id,
                "client_id": client_id,
                "gift_id": gift_id,
            },
        )
    return keyboard


def create_admin_processing_keyboard(order_id: int, client_id: int, payment_method: str | None = None) -> VkKeyboard:
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "⌛ Час - час тридцать",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "REPLY_TEMPLATE", "template": "WAIT_1_1_5", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "⌛ Час тридцать - два часа",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "REPLY_TEMPLATE", "template": "WAIT_1_5_2", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_line()
    keyboard.add_button(
        "⏱ Своё время",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "CUSTOM_WAIT_TIME", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_line()
    if payment_method in ("Наличными", "Переводом при получении"):
        keyboard.add_button(
            "💵 Оплата получена",
            color=VkKeyboardColor.POSITIVE,
            payload={"type": "ADMIN_ACTION", "action": "PAYMENT_CONFIRMED", "order_id": order_id, "client_id": client_id},
        )
        keyboard.add_line()
    keyboard.add_button(
        "🎁 Подарки",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "OPEN_GIFTS_MENU", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_line()
    keyboard.add_button(
        "✉ Ответ",
        color=VkKeyboardColor.SECONDARY,
        payload={"type": "ADMIN_ACTION", "action": "START_REPLY", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "❌ Отменить",
        color=VkKeyboardColor.NEGATIVE,
        payload={"type": "ADMIN_ACTION", "action": "CANCEL_ORDER", "order_id": order_id, "client_id": client_id},
    )
    return keyboard


def create_admin_check_confirm_keyboard(order_id: int, client_id: int) -> VkKeyboard:
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "👌 Оплата подтверждена",
        color=VkKeyboardColor.POSITIVE,
        payload={"type": "ADMIN_ACTION", "action": "PAYMENT_CONFIRMED", "order_id": order_id, "client_id": client_id},
    )
    return keyboard


def create_client_reply_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button(
        "Ответить",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "CLIENT_ACTION", "action": "REPLY_TO_ADMIN"},
    )
    keyboard.add_line()
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


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
    keyboard.add_openlink_button("🎁 Акции", settings.GROUP_WALL_URL)
    keyboard.add_line()
    keyboard.add_button("📍 Адрес", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button(CONTACT_ADMIN_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_main_menu_keyboard_for_user(user_id: int) -> VkKeyboard:
    from bot import core
    keyboard = create_main_menu_keyboard()
    if user_id in core.ADMIN_IDS:
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


def create_admin_menu_keyboard() -> VkKeyboard:
    """Обычная клавиатура админа (не инлайн)."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("📋 Текущие заказы", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("📊 Статистика за день", color=VkKeyboardColor.PRIMARY)
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
    keyboard.add_button(
        "✉ Ответ",
        color=VkKeyboardColor.SECONDARY,
        payload={"type": "ADMIN_ACTION", "action": "START_REPLY", "order_id": order_id, "client_id": client_id},
    )
    return keyboard


def create_admin_processing_keyboard(order_id: int, client_id: int, payment_method: str | None = None) -> VkKeyboard:
    keyboard = VkKeyboard(inline=True)
    keyboard.add_button(
        "⌛ 1-1.5ч",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "REPLY_TEMPLATE", "template": "WAIT_1_1_5", "order_id": order_id, "client_id": client_id},
    )
    keyboard.add_button(
        "⌛ 1.5-2ч",
        color=VkKeyboardColor.PRIMARY,
        payload={"type": "ADMIN_ACTION", "action": "REPLY_TEMPLATE", "template": "WAIT_1_5_2", "order_id": order_id, "client_id": client_id},
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


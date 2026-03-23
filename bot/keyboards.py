from __future__ import annotations

from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from config import settings
from bot.states import (
    BACK_TEXT,
    CANCEL_ORDER_TEXT,
    MENU_TEXT,
)


def create_main_menu_keyboard() -> VkKeyboard:
    """Главное меню. Только требуемые кнопки."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("🎁 Наши акции", "https://vk.com/wall-175111431_2701")
    keyboard.add_line()
    keyboard.add_openlink_button("📋 Наше меню", "https://vk.com/market-175111431")
    keyboard.add_line()
    keyboard.add_button("📍 Адрес для самовывоза", color=VkKeyboardColor.SECONDARY)
    return keyboard


def create_main_menu_keyboard_for_user(user_id: int) -> VkKeyboard:
    """Главное меню для пользователя (без админ кнопок)."""
    return create_main_menu_keyboard()


def create_cancel_order_keyboard() -> VkKeyboard:
    """Клавиатура с кнопкой отмены заказа."""
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button("❌ Отменить заказ", color=VkKeyboardColor.NEGATIVE)
    return keyboard


def create_contact_admin_keyboard() -> VkKeyboard:
    keyboard = VkKeyboard(one_time=False, inline=False)
    keyboard.add_button(MENU_TEXT, color=VkKeyboardColor.SECONDARY)
    return keyboard




"""
Обработка команд и сообщений оператора.
"""
import json

from bot import store
from bot import core
from bot import keyboards as kbd
from bot.states import (
    STATE_WAITING_FOR_CHECK,
    ADMIN_MENU_TEXT,
    ADMIN_TO_USER_MENU_TEXT,
)


def handle_admin_flow(vk, user_id, text, payload, event):
    """
    Обработка сообщений от оператора.
    Возвращает True, если сообщение обработано.
    """
    if text == ADMIN_TO_USER_MENU_TEXT:
        core.handle_start_or_menu(vk, user_id)
        return True

    if text == ADMIN_MENU_TEXT:
        core.send_message(vk, user_id, "Меню оператора.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if handle_admin_commands(vk, user_id, text):
        return True

    if payload and handle_admin_payload(vk, user_id, payload):
        return True

    if handle_admin_message(vk, event):
        return True

    return False


def handle_admin_commands(vk, user_id, text):
    """Команды оператора."""
    if text.startswith("!прием выключить"):
        reason = text[len("!прием выключить"):].strip()
        store.accepting_orders_enabled = False
        store.accepting_orders_reason = reason
        core.send_message(
            vk, user_id,
            f"✅ Приём заказов выключен.\nПричина: {reason or 'не указана'}",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if text == "!прием включить":
        store.accepting_orders_enabled = True
        store.accepting_orders_reason = ""
        core.send_message(vk, user_id, "✅ Приём заказов включен.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text.startswith("!акция добавить "):
        promo_text = text[len("!акция добавить "):].strip()
        if not promo_text:
            core.send_message(vk, user_id, "Формат: !акция добавить <текст>", keyboard=kbd.create_admin_menu_keyboard())
            return True
        from bot.services.promos_service import add_promo_line
        add_promo_line(promo_text)
        core.send_message(vk, user_id, "✅ Акция добавлена.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text.startswith("!акция удалить "):
        raw = text[len("!акция удалить "):].strip()
        try:
            n = int(raw)
        except Exception:
            core.send_message(vk, user_id, "Формат: !акция удалить <номер_строки>", keyboard=kbd.create_admin_menu_keyboard())
            return True
        from bot.services.promos_service import delete_promo_line
        ok, total = delete_promo_line(n)
        if ok:
            core.send_message(vk, user_id, f"✅ Удалено. Осталось строк: {total}", keyboard=kbd.create_admin_menu_keyboard())
        else:
            core.send_message(vk, user_id, f"❌ Нет строки #{n}. Всего строк: {total}", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text == "📊 Статистика за день":
        new_count, accepted, cancelled, paid_sum = core.get_daily_stats()
        today_str = core.now_utc5().strftime("%d.%m.%Y")
        msg = (
            f"📊 Статистика за {today_str}\n\n"
            f"🆕 Новых (ожидают): {new_count}\n"
            f"✅ Принято: {accepted}\n"
            f"❌ Отказано: {cancelled}\n"
            f"💰 Сумма подтверждённых (оплачено): {paid_sum}₽"
        )
        core.send_message(vk, user_id, msg, keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text == "📋 Текущие заказы":
        active = []
        for oid, o in store.orders.items():
            if o.get("status") in ("NEW", "IN_PROGRESS", "WAIT_1_1_5", "WAIT_1_5_2", "ACCEPTED", "WAITING_FOR_CHECK"):
                active.append((oid, o))
        if not active:
            core.send_message(vk, user_id, "Сейчас нет активных заказов.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        lines = ["📋 Текущие заказы (подробнее):"]
        for oid, o in sorted(active, key=lambda x: x[0], reverse=True):
            order_data = o.get("order") or {}
            delivery_info = order_data.get("delivery_datetime") or order_data.get("delivery_time") or "-"
            lines.append(
                f"\n🧾 Заказ #{oid}\n"
                f"— Клиент: {o.get('client_id')}\n"
                f"— Статус: {o.get('status')}\n"
                f"— Оплата: {order_data.get('payment_method', '-')}\n"
                f"— Цена: {o.get('price') or '-'}\n"
                f"— Предзаказ: {'ДА' if order_data.get('is_preorder') else 'нет'}\n"
                f"— Время доставки: {delivery_info}\n"
                f"— Что заказали: {order_data.get('food') or '-'}\n"
                f"— Адрес: {order_data.get('address') or '-'}"
            )
        core.send_message(vk, user_id, "\n".join(lines).strip(), keyboard=kbd.create_admin_menu_keyboard())
        return True

    return False


def handle_admin_payload(vk, admin_user_id, payload):
    """Обработка payload от инлайн-кнопок админа."""
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except Exception:
            return False
    elif isinstance(payload, dict):
        data = payload
    else:
        return False

    if data.get("type") != "ADMIN_ACTION":
        return False

    action = data.get("action")
    order_id = data.get("order_id")
    client_id = data.get("client_id")
    if not client_id or not order_id:
        return True

    order_entry = store.orders.get(int(order_id)) if isinstance(order_id, int) or (isinstance(order_id, str) and order_id.isdigit()) else None
    if order_entry is None and isinstance(order_id, str) and order_id.isdigit():
        order_entry = store.orders.get(int(order_id))
    if order_entry is None:
        core.send_message(vk, admin_user_id, f"Не нашёл заказ #{order_id}.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    oid = int(order_id) if isinstance(order_id, str) and order_id.isdigit() else order_id

    if action == "REPLY_TEMPLATE":
        template = data.get("template")
        if template == "WAIT_1_1_5":
            base_msg = "⌛ Ваш заказ принят! Ожидание доставки 1–1.5 часа."
            new_status = "WAIT_1_1_5"
        elif template == "WAIT_1_5_2":
            base_msg = "⌛ Ваш заказ принят! Ожидание доставки 1.5–2 часа."
            new_status = "WAIT_1_5_2"
        elif template == "ACCEPTED":
            base_msg = "✅ Заказ принят. Готовим и скоро передадим курьеру."
            new_status = "ACCEPTED"
        else:
            base_msg = "Сообщение от оператора."
            new_status = None

        if new_status:
            order_entry["status"] = new_status
        store.admin_states[admin_user_id] = {
            "state": "AWAITING_PRICE_WITH_MSG",
            "client_id": client_id,
            "order_id": oid,
            "base_msg": base_msg,
        }
        core.send_message(
            vk, admin_user_id,
            f"Ок. Теперь укажите цену для клиента ID {client_id} (например: 1490).",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "ACCEPT_FLOW":
        order_entry["status"] = "IN_PROGRESS"
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}"
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        return True

    if action == "CANCEL_ORDER":
        store.admin_states[admin_user_id] = {"state": "AWAITING_CANCEL_REASON", "client_id": client_id, "order_id": oid}
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n❌ Отмена: ожидаю причину от оператора."
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        core.send_message(
            vk, admin_user_id,
            f"Введите причину отмены для клиента ID {client_id}.\nЕсли причины нет — напишите: без причины",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "START_REPLY":
        store.admin_states[admin_user_id] = {"state": "AWAITING_REPLY_TEXT", "client_id": client_id, "order_id": oid}
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n✉ Ожидаю текст ответа админа."
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        core.send_message(
            vk, admin_user_id,
            f"Введите текст ответа клиенту ID {client_id}.",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "SET_PRICE":
        store.admin_states[admin_user_id] = {"state": "AWAITING_PRICE", "client_id": client_id, "order_id": oid}
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n💰 Ожидаю цену от оператора."
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        core.send_message(
            vk, admin_user_id,
            f"Введите цену для клиента ID {client_id} (например: 1490).",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "ACCEPT_AND_REQUEST_PAYMENT":
        store.admin_states[admin_user_id] = {
            "state": "AWAITING_PRICE_ACCEPT_AND_REQUEST_PAYMENT",
            "client_id": client_id,
            "order_id": oid,
        }
        order_entry["status"] = "ACCEPTED"
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n✅ Принятие с запросом предоплаты: ожидаю цену."
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        core.send_message(
            vk, admin_user_id,
            f"Введите цену для клиента ID {client_id} (после этого бот запросит оплату переводом).",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "PAYMENT_CONFIRMED":
        order_entry["status"] = "PAID"
        core.send_message(vk, client_id, "Спасибо! Оплата получена, ваш заказ передан на кухню")
        core.reset_user_state(client_id)
        core.send_message(vk, admin_user_id, "Клиенту отправлено подтверждение оплаты.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    return False


def handle_admin_message(vk, event):
    """Обработка текстовых ответов админа (причина отмены, ответ клиенту, цена)."""
    user_id = event.obj.message["from_id"]
    text = event.obj.message.get("text", "").strip()
    state = store.admin_states.get(user_id)
    if not state:
        return False

    client_id = state.get("client_id")

    if state.get("state") == "AWAITING_CANCEL_REASON":
        reason = text or "без причины"
        core.send_message(vk, client_id, f"❌ Ваш заказ отменён.\nПричина: {reason}")
        for oid, o in store.orders.items():
            if o["client_id"] == client_id and o["status"] != "CANCELLED":
                o["status"] = "CANCELLED"
        core.send_message(
            vk, user_id,
            f"Ок. Заказ клиента ID {client_id} отменён. Причина: {reason}",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_REPLY_TEXT":
        if text:
            core.send_message(vk, client_id, f"✉ Сообщение от оператора:\n{text}")
            core.send_message(vk, user_id, f"Ответ отправлен клиенту ID {client_id}.", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_PRICE":
        if not text.strip():
            return True
        price_text = text.strip()
        payment_method = None
        for oid, o in store.orders.items():
            if o["client_id"] == client_id and o.get("status") != "CANCELLED":
                o["price"] = price_text
                payment_method = (o.get("order") or {}).get("payment_method")
        msg_lines = [f"💰 Стоимость вашего заказа: {price_text}₽"]
        if payment_method == "Переводом сейчас":
            msg_lines.append("")
            msg_lines.append("Реквизиты для перевода:")
            msg_lines.extend(core.TRANSFER_INFO_LINES)
        core.send_message(vk, client_id, "\n".join(msg_lines))
        core.send_message(vk, user_id, f"Цена отправлена клиенту ID {client_id}.", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_PRICE_WITH_MSG":
        price_text = text.strip()
        base_msg = state.get("base_msg", "").strip()
        order_id = state.get("order_id")
        if not price_text:
            return True
        if order_id in store.orders:
            store.orders[order_id]["price"] = price_text
        payment_method = (store.orders.get(order_id, {}).get("order") or {}).get("payment_method")
        summary = store.orders.get(order_id, {}).get("summary", "")
        if payment_method == "Переводом сейчас":
            msg_lines = [base_msg or "✅ Заказ принят.", f"💰 Сумма к оплате: {price_text}₽", "", *core.PAYMENT_REQUEST_LINES]
            u = core.get_user_state(client_id)
            u["state"] = STATE_WAITING_FOR_CHECK
            u["active_order_id"] = order_id
            if order_id in store.orders:
                store.orders[order_id]["status"] = "WAITING_FOR_CHECK"
        else:
            msg_lines = [base_msg or "✅ Заказ принят.", f"💰 Сумма: {price_text}₽", "", "Детали заказа:", summary]
        core.send_message(vk, client_id, "\n".join([line for line in msg_lines if line is not None]))
        core.send_message(vk, user_id, "Статус и цена отправлены клиенту.", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_PRICE_ACCEPT_AND_REQUEST_PAYMENT":
        price_text = text.strip()
        order_id = state.get("order_id")
        if not price_text:
            return True
        payment_method = None
        if order_id in store.orders:
            store.orders[order_id]["price"] = price_text
            payment_method = (store.orders[order_id].get("order") or {}).get("payment_method")
        msg_lines = [f"✅ Заказ принят.\n💰 Стоимость: {price_text}₽"]
        if payment_method == "Переводом сейчас":
            msg_lines.append("")
            msg_lines.extend(core.PAYMENT_REQUEST_LINES)
            u = core.get_user_state(client_id)
            u["state"] = STATE_WAITING_FOR_CHECK
            u["active_order_id"] = order_id
            if order_id in store.orders:
                store.orders[order_id]["status"] = "WAITING_FOR_CHECK"
        core.send_message(vk, client_id, "\n".join(msg_lines))
        core.send_message(vk, user_id, "Цена отправлена, оплата запрошена (если перевод сейчас).", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    return False

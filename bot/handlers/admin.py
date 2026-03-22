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


ACTIVE_ORDER_STATUSES = ("NEW", "IN_PROGRESS", "WAIT_1_1_5", "WAIT_1_5_2", "ACCEPTED", "WAITING_FOR_CHECK", "READY")


def _get_user_display(vk, user_id):
    """Вернуть кликабельное ФИО в формате VK mention."""
    return core.format_user_mention(vk, user_id)


def _build_active_clients_list(vk):
    """Собрать список активных клиентов: [(idx, client_id, mention, order_id)]."""
    active_orders = []
    for oid, order_entry in sorted(store.orders.items(), key=lambda x: x[0], reverse=True):
        if order_entry.get("status") in ACTIVE_ORDER_STATUSES:
            active_orders.append((oid, order_entry))

    client_to_order = {}
    for oid, order_entry in active_orders:
        cid = order_entry.get("client_id")
        if cid and cid not in client_to_order:
            client_to_order[cid] = oid

    result = []
    for idx, (cid, oid) in enumerate(client_to_order.items(), start=1):
        result.append((idx, cid, _get_user_display(vk, cid), oid))
    return result


def _parse_message_payload(payload):
    if not payload:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return None
    return None


def handle_admin_flow(vk, user_id, text, payload, event):
    """
    Обработка сообщений от оператора.
    Возвращает True, если сообщение обработано.
    """
    pdata = _parse_message_payload(payload)
    if pdata and pdata.get("type") == "CLIENT_ACTION":
        return False

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

    if text.startswith("!сотрудник добавить "):
        raw = text[len("!сотрудник добавить "):].strip()
        try:
            target_id = int(raw)
        except Exception:
            core.send_message(vk, user_id, "Формат: !сотрудник добавить <ID пользователя>", keyboard=kbd.create_admin_menu_keyboard())
            return True
        from database.models import add_employee, list_employee_ids
        success = add_employee(target_id)
        if success:
            current_ids = list_employee_ids()
            core.send_message(vk, user_id, f"✅ Сотрудник {target_id} добавлен.\nТекущий список: {current_ids}", keyboard=kbd.create_admin_menu_keyboard())
        else:
            core.send_message(vk, user_id, "❌ Не удалось добавить сотрудника (проверьте настройки БД).", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text.startswith("!сотрудник удалить "):
        raw = text[len("!сотрудник удалить "):].strip()
        try:
            target_id = int(raw)
        except Exception:
            core.send_message(vk, user_id, "Формат: !сотрудник удалить <ID пользователя>", keyboard=kbd.create_admin_menu_keyboard())
            return True
        from database.models import remove_employee, list_employee_ids
        success, remaining = remove_employee(target_id)
        if success:
            current_ids = list_employee_ids()
            core.send_message(vk, user_id, f"✅ Сотрудник {target_id} удалён.\nОсталось: {remaining}\nТекущий список: {current_ids}", keyboard=kbd.create_admin_menu_keyboard())
        else:
            if remaining <= 1:
                core.send_message(vk, user_id, "❌ Нельзя удалить последнего сотрудника!", keyboard=kbd.create_admin_menu_keyboard())
            else:
                core.send_message(vk, user_id, f"❌ Сотрудник {target_id} не найден.", keyboard=kbd.create_admin_menu_keyboard())
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
            if o.get("status") in ACTIVE_ORDER_STATUSES:
                active.append((oid, o))
        if not active:
            core.send_message(vk, user_id, "Сейчас нет активных заказов.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        
        for oid, o in sorted(active, key=lambda x: x[0], reverse=True):
            order_data = o.get("order") or {}
            delivery_info = order_data.get("order_time") or order_data.get("delivery_datetime") or order_data.get("delivery_time") or "-"
            payment_method = order_data.get('payment_method', '')
            
            lines = [
                f"🧾 Заказ #{oid}",
                f"— Клиент: {_get_user_display(vk, o.get('client_id'))}",
                f"— Статус: {o.get('status')}",
                f"— Оплата: {payment_method or '-'}",
                f"— Цена: {o.get('price') or '-'}",
                f"— Предзаказ: {'ДА' if order_data.get('is_preorder') else 'нет'}",
                f"— Комментарий к заказу: {delivery_info}",
                f"— Что заказали: {order_data.get('food') or '-'}",
                f"— Адрес: {order_data.get('address') or '-'}",
                f"— Подарок: {o.get('gift') or '—'}"
            ]
            
            core.send_message(
                vk, 
                user_id, 
                "\n".join(lines),
                keyboard=kbd.create_admin_order_list_keyboard(oid, o.get('client_id'), payment_method)
            )
        return True

    if text == "✉ Написать клиенту":
        clients = _build_active_clients_list(vk)
        if not clients:
            core.send_message(vk, user_id, "Сейчас нет клиентов с активными заказами.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        lines = ["Выберите клиента по номеру:"]
        choices = {}
        for idx, cid, mention, oid in clients:
            lines.append(f"{idx}. {mention} (заказ #{oid})")
            choices[str(idx)] = cid
        store.admin_states[user_id] = {"state": "AWAITING_CLIENT_SELECTION", "choices": choices}
        core.send_message(vk, user_id, "\n".join(lines), keyboard=kbd.create_admin_menu_keyboard())
        return True

    if text == "🎁 Управление подарками":
        core.send_message(vk, user_id, "🎁 Управление подарками:", keyboard=kbd.create_admin_gifts_management_keyboard())
        return True

    if text == "📋 Список подарков":
        lines = ["🎁 Текущие подарки:\n"]
        for i, (gift_id, (min_sum, title)) in enumerate(kbd.ADMIN_GIFT_CATALOG.items(), 1):
            if gift_id == "none":
                continue
            lines.append(f"{i}. {title} (от {min_sum}₽)")
        if len(lines) == 1:
            lines.append("Подарков пока нет.")
        core.send_message(vk, user_id, "\n".join(lines), keyboard=kbd.create_admin_gifts_management_keyboard())
        return True

    if text == "➕ Добавить подарок":
        store.admin_states[user_id] = {"state": "AWAITING_GIFT_ADD"}
        core.send_message(
            vk, user_id,
            "Введите данные подарка в формате:\n<минимальная сумма>;<название подарка>\n\nПример:\n1500;Футоролл с лососем 5шт",
            keyboard=kbd.create_admin_gifts_management_keyboard()
        )
        return True

    if text == "🗑 Удалить подарок":
        store.admin_states[user_id] = {"state": "AWAITING_GIFT_DELETE"}
        lines = ["🗑 Удаление подарка. Выберите номер:\n"]
        gift_list = []
        for i, (gift_id, (min_sum, title)) in enumerate(kbd.ADMIN_GIFT_CATALOG.items(), 1):
            if gift_id == "none":
                continue
            gift_list.append(gift_id)
            lines.append(f"{i}. {title} (от {min_sum}₽)")
        if not gift_list:
            core.send_message(vk, user_id, "Подарков для удаления нет.", keyboard=kbd.create_admin_gifts_management_keyboard())
            return True
        lines.append("\nВведите номер подарка для удаления:")
        store.admin_states[user_id]["gift_choices"] = gift_list
        core.send_message(vk, user_id, "\n".join(lines), keyboard=kbd.create_admin_gifts_management_keyboard())
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

    # Обработка кнопки "Ответить" из уведомлений от клиентов
    if data.get("type") == "ADMIN_REPLY":
        client_id = data.get("user_id")
        if client_id:
            store.admin_states[admin_user_id] = {
                "state": "AWAITING_CLIENT_MESSAGE_REPLY", 
                "client_id": client_id
            }
            core.send_message(
                vk, 
                admin_user_id,
                f"Введите ответ для клиента {_get_user_display(vk, client_id)}:",
                keyboard=kbd.create_admin_menu_keyboard()
            )
        return True

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
            base_msg = "⌛ Ваш заказ принят! Ожидание заказа: час - час тридцать."
            new_status = "WAIT_1_1_5"
        elif template == "WAIT_1_5_2":
            base_msg = "⌛ Ваш заказ принят! Ожидание заказа: час тридцать - два часа."
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
            f"Ок. Теперь укажите цену для клиента {_get_user_display(vk, client_id)} (например: 1490).",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "MARK_READY":
        order_entry["status"] = "ACCEPTED"
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n✅ Заказ готов к выдаче!"
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        
        # Отправляем уведомление клиенту
        core.send_message(
            vk, 
            client_id, 
            f"✅ Ваш заказ #{oid} готов и ожидает вас!\n\n{core.get_order_thanks_closing()}",
            keyboard=kbd.create_main_menu_keyboard_for_user(client_id)
        )
        core.send_message(vk, admin_user_id, "✅ Заказ отмечен как готовый.", keyboard=kbd.create_admin_menu_keyboard())
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
            f"Введите причину отмены для клиента {_get_user_display(vk, client_id)}.\nЕсли причины нет — напишите: без причины",
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
            f"Введите текст ответа клиенту {_get_user_display(vk, client_id)}.",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "CUSTOM_WAIT_TIME":
        store.admin_states[admin_user_id] = {
            "state": "AWAITING_CUSTOM_WAIT_TIME",
            "client_id": client_id,
            "order_id": oid,
        }
        order_entry["status"] = "ACCEPTED"
        text = f"📩 Заказ #{oid}\n\n{order_entry.get('summary')}\n\n⏱ Ожидаю текст времени ожидания (свободный ввод)."
        pm = (order_entry.get("order") or {}).get("payment_method")
        core.edit_admin_order_message(vk, oid, text, kbd.create_admin_processing_keyboard(oid, client_id, pm))
        core.send_message(
            vk,
            admin_user_id,
            f"Введите время ожидания заказа для клиента {_get_user_display(vk, client_id)} "
            "(как увидит клиент, например: «около 45 минут»). "
            "Следующим сообщением укажите сумму заказа числом (например: 1490).",
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
            f"Введите цену для клиента {_get_user_display(vk, client_id)} (после этого бот запросит оплату переводом).",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if action == "PAYMENT_CONFIRMED":
        order_entry["status"] = "PAID"
        core.send_message(vk, client_id, "Спасибо!")
        core.reset_user_state(client_id)
        core.send_message(vk, admin_user_id, "Клиенту отправлено подтверждение оплаты.", keyboard=kbd.create_admin_menu_keyboard())
        return True

    if action == "OPEN_GIFTS_MENU":
        price_int = core.parse_price_to_int(order_entry.get("price"))
        if price_int is None:
            core.send_message(
                vk,
                admin_user_id,
                "Чтобы выбрать подарок, сначала укажите сумму заказа (шаблон с ожиданием цены или ввод цены).",
                keyboard=kbd.create_admin_menu_keyboard(),
            )
            return True
        core.send_message(
            vk,
            admin_user_id,
            f"🎁 Заказ #{oid}. Сумма чека: ~{price_int}₽\nВыберите подарок:",
            keyboard=kbd.create_admin_gifts_keyboard(oid, client_id, price_int),
        )
        return True

    if action == "SELECT_GIFT":
        gift_id = data.get("gift_id")
        info = kbd.ADMIN_GIFT_CATALOG.get(gift_id)
        if not info:
            core.send_message(vk, admin_user_id, "Неизвестный подарок.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        min_sum, title = info
        price_int = core.parse_price_to_int(order_entry.get("price"))
        if price_int is None:
            core.send_message(vk, admin_user_id, "Сначала укажите сумму заказа.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        if gift_id != "none" and price_int < min_sum:
            core.send_message(
                vk,
                admin_user_id,
                f"Сумма заказа ({price_int}₽) меньше порога для этого подарка ({min_sum}₽).",
                keyboard=kbd.create_admin_menu_keyboard(),
            )
            return True
        order_entry["gift"] = None if gift_id == "none" else title
        if gift_id == "none":
            core.send_message(vk, admin_user_id, "Выбрано: без подарка.", keyboard=kbd.create_admin_menu_keyboard())
        else:
            core.send_message(
                vk,
                admin_user_id,
                f"Сохранено: «{title}». Клиенту отправлено уведомление.",
                keyboard=kbd.create_admin_menu_keyboard(),
            )
            core.send_message(
                vk,
                client_id,
                f"🎁 К вашему заказу #{oid} добавлен подарок:\n{title}",
                keyboard=kbd.create_main_menu_keyboard_for_user(client_id),
            )
        return True

    return False


def handle_admin_message(vk, event):
    """Обработка текстовых ответов админа (причина отмены, ответ клиенту, цена)."""
    user_id = event.obj.message["from_id"]
    text = event.obj.message.get("text", "").strip()
    msg_payload = _parse_message_payload(event.obj.message.get("payload"))
    if msg_payload and msg_payload.get("type") == "CLIENT_ACTION":
        return False

    state = store.admin_states.get(user_id)
    if not state:
        return False

    client_id = state.get("client_id")

    if state.get("state") == "AWAITING_CLIENT_SELECTION":
        selected_client_id = (state.get("choices") or {}).get(text.strip())
        if not selected_client_id:
            core.send_message(vk, user_id, "Введите номер клиента из списка.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        store.admin_states[user_id] = {"state": "AWAITING_BROADCAST_TEXT", "client_id": selected_client_id}
        core.send_message(
            vk,
            user_id,
            f"Введите сообщение для клиента {_get_user_display(vk, selected_client_id)}.",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        return True

    if state.get("state") == "AWAITING_BROADCAST_TEXT":
        if not text:
            core.send_message(vk, user_id, "Введите текст сообщения.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        core.send_message(
            vk,
            client_id,
            f"✉ Сообщение от оператора:\n{text}",
            keyboard=kbd.create_client_reply_keyboard(),
        )
        core.send_message(
            vk,
            user_id,
            f"Сообщение отправлено клиенту {_get_user_display(vk, client_id)}.",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_CANCEL_REASON":
        reason = text or "без причины"
        core.send_message(vk, client_id, f"❌ Ваш заказ отменён.\nПричина: {reason}")
        for oid, o in store.orders.items():
            if o["client_id"] == client_id and o["status"] != "CANCELLED":
                o["status"] = "CANCELLED"
        core.send_message(
            vk, user_id,
            f"Ок. Заказ клиента {_get_user_display(vk, client_id)} отменён. Причина: {reason}",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_REPLY_TEXT":
        if text.strip().lower() in ("ответить", "↩ ответить"):
            return False
        if text:
            core.send_message(vk, client_id, f"✉ Сообщение от оператора:\n{text}", keyboard=kbd.create_client_reply_keyboard())
            core.send_message(vk, user_id, f"Ответ отправлен клиенту {_get_user_display(vk, client_id)}.", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_CUSTOM_WAIT_TIME":
        wait_text = (text or "").strip()
        if not wait_text:
            core.send_message(
                vk,
                user_id,
                "Введите текст времени ожидания для клиента (не пустое сообщение).",
                keyboard=kbd.create_admin_menu_keyboard(),
            )
            return True
        base_msg = f"⌛ Ваш заказ принят! Ожидание заказа: {wait_text}"
        store.admin_states[user_id] = {
            "state": "AWAITING_PRICE_WITH_MSG",
            "client_id": client_id,
            "order_id": state.get("order_id"),
            "base_msg": base_msg,
        }
        core.send_message(vk, user_id, "Ок.", keyboard=kbd.create_admin_menu_keyboard())
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
            msg_lines = [
                base_msg or "✅ Заказ принят.",
                f"💰 Сумма к оплате: {price_text}₽",
                "",
                "Детали заказа:",
                summary,
                "",
                *core.PAYMENT_CHECK_ONLY_LINES,
                "",
                core.get_order_thanks_closing(),
            ]
            u = core.get_user_state(client_id)
            u["state"] = STATE_WAITING_FOR_CHECK
            u["active_order_id"] = order_id
            if order_id in store.orders:
                store.orders[order_id]["status"] = "WAITING_FOR_CHECK"
        else:
            msg_lines = [
                base_msg or "✅ Заказ принят.",
                f"💰 Сумма: {price_text}₽",
                "",
                "Детали заказа:",
                summary,
                "",
                core.get_order_thanks_closing(),
            ]
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
            msg_lines.append("Детали заказа:")
            if order_id in store.orders:
                msg_lines.append(store.orders[order_id].get("summary", ""))
                msg_lines.append("")
            msg_lines.extend(core.PAYMENT_CHECK_ONLY_LINES)
            u = core.get_user_state(client_id)
            u["state"] = STATE_WAITING_FOR_CHECK
            u["active_order_id"] = order_id
            if order_id in store.orders:
                store.orders[order_id]["status"] = "WAITING_FOR_CHECK"
        msg_lines.extend(["", core.get_order_thanks_closing()])
        core.send_message(vk, client_id, "\n".join(msg_lines))
        core.send_message(vk, user_id, "Цена отправлена, оплата запрошена (если перевод сейчас).", keyboard=kbd.create_admin_menu_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_CLIENT_MESSAGE_REPLY":
        if not text.strip():
            core.send_message(vk, user_id, "Введите текст ответа.", keyboard=kbd.create_admin_menu_keyboard())
            return True
        
        client_id = state.get("client_id")
        core.send_message(
            vk,
            client_id,
            f"✉ Ответ оператора:\n{text}",
            keyboard=kbd.create_main_menu_keyboard_for_user(client_id),
        )
        core.send_message(
            vk,
            user_id,
            f"Ответ отправлен клиенту {_get_user_display(vk, client_id)}.",
            keyboard=kbd.create_admin_menu_keyboard(),
        )
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_GIFT_ADD":
        parts = text.split(";")
        if len(parts) != 2:
            core.send_message(vk, user_id, "❌ Неверный формат. Используйте: <минимальная сумма>;<название подарка>", keyboard=kbd.create_admin_gifts_management_keyboard())
            return True
        try:
            min_sum = int(parts[0].strip())
            title = parts[1].strip()
            if min_sum <= 0 or not title:
                raise ValueError()
        except ValueError:
            core.send_message(vk, user_id, "❌ Неверные данные. Сумма должна быть положительным числом.", keyboard=kbd.create_admin_gifts_management_keyboard())
            return True
        
        # Добавляем подарок в каталог
        gift_id = f"custom_{min_sum}_{len(kbd.ADMIN_GIFT_CATALOG)}"
        kbd.ADMIN_GIFT_CATALOG[gift_id] = (min_sum, title)
        kbd.ADMIN_GIFT_BUTTON_ORDER.append((gift_id, f"От {min_sum} — {title[:30]}"))
        
        core.send_message(vk, user_id, f"✅ Подарок добавлен: {title} (от {min_sum}₽)", keyboard=kbd.create_admin_gifts_management_keyboard())
        store.admin_states.pop(user_id, None)
        return True

    if state.get("state") == "AWAITING_GIFT_DELETE":
        try:
            idx = int(text.strip()) - 1
            gift_choices = state.get("gift_choices", [])
            if idx < 0 or idx >= len(gift_choices):
                core.send_message(vk, user_id, f"❌ Неверный номер. Выберите от 1 до {len(gift_choices)}", keyboard=kbd.create_admin_gifts_management_keyboard())
                return True
            gift_id = gift_choices[idx]
            min_sum, title = kbd.ADMIN_GIFT_CATALOG[gift_id]
            
            # Удаляем подарок
            del kbd.ADMIN_GIFT_CATALOG[gift_id]
            kbd.ADMIN_GIFT_BUTTON_ORDER = [(gid, label) for gid, label in kbd.ADMIN_GIFT_BUTTON_ORDER if gid != gift_id]
            
            core.send_message(vk, user_id, f"✅ Подарок удален: {title}", keyboard=kbd.create_admin_gifts_management_keyboard())
            store.admin_states.pop(user_id, None)
            return True
        except (ValueError, IndexError):
            core.send_message(vk, user_id, "❌ Неверный номер. Введите число из списка.", keyboard=kbd.create_admin_gifts_management_keyboard())
            return True

    return False

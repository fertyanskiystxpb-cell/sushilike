"""
Обработка сообщений пользователей (FSM оформления заказа).
"""
import json
import re
import time

import vk_api
from config import settings
from bot import store
from bot import core
from bot import keyboards as kbd
from bot.states import (
    STATE_IDLE,
    STATE_CONTACT_ADMIN,
    STATE_WAITING_FOR_CHECK,
    CANCEL_ORDER_TEXT,
    BACK_TEXT,
    MENU_TEXT,
)
from bot.services.promos_service import read_promos_text


def _is_complete_order(text):
    """Проверяет, содержит ли текст все поля для заказа."""
    text_lower = text.lower()
    
    # Проверяем еду - более гибкие ключевые слова
    has_food = any(keyword in text_lower for keyword in [
        'сет', 'сети', 'сетов', 'сет', 'ролл', 'роллы', 'роллов', 
        'суши', 'пицца', 'пицц', 'пиццу', 'пиццы', 'пицце',
        'заказ', 'хочу', 'васаби', 'имбирь', 'салат', 'суп',
        'горячее', 'напитки', 'десерт', 'рол', 'сет'
    ])
    
    # Проверяем телефон - ищем 10+ цифр подряд
    import re
    phone_match = re.search(r'\d{10,}', text.replace(' ', '').replace('-', ''))
    has_phone = bool(phone_match)
    
    # Проверяем адрес - более гибкие ключевые слова
    has_address = any(keyword in text_lower for keyword in [
        'ул', 'улица', 'дом', 'кв', 'квартира', 'улица', 'пукук', 
        'адрес', 'улице', 'дом', 'квартира', 'переулок', 'проспект'
    ])
    
    # Проверяем способ оплаты
    has_payment = any(keyword in text_lower for keyword in [
        'наличные', 'перевод', 'картой', 'онлайн', 'при получении'
    ])
    
    # Достаточно иметь телефон и адрес. Еда может быть подразумеваема.
    result = has_phone and has_address
    print(f"[DEBUG] Проверка заказа: еда={has_food}, телефон={has_phone}, адрес={has_address}, оплата={has_payment}, результат={result}")
    print(f"[DEBUG] Текст для анализа: '{text_lower}'")
    return result


def _process_complete_order(vk, user_id, text, state_info, order):
    """Обрабатывает полный заказ от клиента."""
    # Сохраняем полный текст заказа
    order["full_text"] = text.strip()
    order["food"] = "Полный заказ в сообщении"
    
    # Извлекаем номер телефона и количество приборов для проверки
    # Ищем телефон - 10+ цифр подряд
    import re
    phone_match = re.search(r'\d{10,}', text.replace(' ', '').replace('-', ''))
    phone = phone_match.group() if phone_match else ''
    
    # Ищем количество приборов (1-2 цифры подряд)
    cutlery_matches = re.findall(r'\b[1-9][0-9]?\b', text)
    cutlery_count = ', '.join(cutlery_matches) if cutlery_matches else ''
    
    # Получаем имя клиента
    try:
        user_info = vk.users.get(user_ids=user_id)
        if user_info:
            first_name = user_info[0].get("first_name", "")
            last_name = user_info[0].get("last_name", "")
            name = f"[id{user_id}|{first_name} {last_name}]"
        else:
            name = f"[id{user_id}|Клиент]"
    except Exception as e:
        print(f"[DEBUG] Ошибка получения имени клиента: {e}")
        name = f"[id{user_id}|Клиент]"
    
    # Отправляем уведомление администраторам
    notification = f"📩 {name} сделал заявку, ответьте.\n\n"
    notification += f"📋 Телефон: {phone}\n"
    if cutlery_count:
        notification += f"🔢 Приборы: {cutlery_count}\n"
    notification += f"📝 Полная заявка:\n{text}"
    
    # Отправляем уведомление всем операторам из конфига
    admin_ids = [settings.VK_ADMIN_ID]
    # Проверяем дополнительных админов в VK_ADMIN_IDS
    ids_str = getattr(settings, "VK_ADMIN_IDS", "") or ""
    if ids_str.strip():
        try:
            additional_ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
            admin_ids.extend(additional_ids)
        except (ValueError, AttributeError):
            pass
    
    print(f"[DEBUG] Отправка уведомления администраторам: {admin_ids}")
    print(f"[DEBUG] Текст уведомления: {notification}")
    
    success_count = 0
    for admin_id in admin_ids:
        try:
            # VK ожидает уникальный random_id в допустимом диапазоне.
            # Используем округление к секундам и ограничиваем размер.
            random_id = (int(time.time()) + int(user_id)) % (2**31 - 1)
            result = vk.messages.send(
                user_id=admin_id,
                message=notification,
                random_id=random_id,
            )
            success_count += 1
            print(f"[DEBUG] Успешно отправлено админу {admin_id}: {result}")
        except Exception as e:
            # На случай, если admin_id задан как peer_id (например, чат/диалог),
            # пробуем отправить через peer_id.
            print(f"[DEBUG] Ошибка отправки админу {admin_id} (user_id): {e}")
            try:
                result = vk.messages.send(
                    peer_id=admin_id,
                    message=notification,
                    random_id=(int(time.time()) + int(user_id)) % (2**31 - 1),
                )
                success_count += 1
                print(f"[DEBUG] Успешно отправлено админу {admin_id} (peer_id): {result}")
            except Exception as e2:
                print(f"[DEBUG] Ошибка отправки админу {admin_id} (peer_id): {e2}")

    if success_count == 0:
        print("[DEBUG] Не удалось отправить уведомление ни одному администратору.")
    
    # Сбрасываем состояние пользователя
    core.reset_user_state(user_id)
    
    # Возвращаем в главное меню БЕЗ сообщения
    core.handle_start_or_menu(vk, user_id)


def _handle_admin_command(vk, user_id, text):
    """Обработка админских команд."""
    parts = text.split()
    if not parts:
        return None
    
    command = parts[0].lower()
    
    if command == "!диагностика":
        # Показываем информацию о всех пользователях
        from bot import store
        from bot.core import now_utc5
        from datetime import timedelta
        
        msg = "📊 Диагностика пользователей:\n\n"
        
        # Информация о user_states
        msg += f"👥 Всего пользователей в user_states: {len(store.user_states)}\n"
        msg += f"📨 Всего пользователей в user_last_message: {len(store.user_last_message)}\n\n"
        
        # Показываем последние 10 пользователей из user_states
        msg += "🔍 Последние пользователи в user_states:\n"
        for uid, state in list(store.user_states.items())[-10:]:
            msg += f"• ID{uid}: {state.get('state', 'IDLE')}\n"
        
        msg += "\n🕐 Последние сообщения:\n"
        for uid, timestamp in list(store.user_last_message.items())[-10:]:
            if isinstance(timestamp, str):
                msg += f"• ID{uid}: {timestamp}\n"
            else:
                time_diff = now_utc5() - timestamp
                msg += f"• ID{uid}: {time_diff} назад\n"
        
        core.send_message(vk, user_id, msg)
        return
    
    if command == "!добавить_пользователя" and len(parts) >= 2:
        try:
            target_user_id = int(parts[1])
            from bot import store
            from bot.core import now_utc5
            
            # Создаем состояние пользователя
            if target_user_id not in store.user_states:
                store.user_states[target_user_id] = {
                    "state": "IDLE",
                    "order": {},
                    "history": [],
                    "active_order_id": None,
                }
                print(f"[DEBUG] Создано состояние для пользователя {target_user_id}")
            
            # Устанавливаем время последнего сообщения (чтобы не было приветствия)
            store.user_last_message[target_user_id] = now_utc5()
            
            core.send_message(vk, user_id, f"✅ Пользователь ID{target_user_id} добавлен в систему")
            print(f"[DEBUG] Пользователь {target_user_id} добавлен в систему")
            
        except ValueError:
            core.send_message(vk, user_id, "❌ Неверный формат ID пользователя. Используйте: !добавить_пользователя 123456789")
        except Exception as e:
            core.send_message(vk, user_id, f"❌ Ошибка: {e}")
        return
    
    if command == "!приветствие" and len(parts) >= 2:
        action = parts[1].lower()
        
        if action == "удалить":
            # Удаляем дополнительный текст приветствия
            try:
                core.save_setting_to_db('GREETING_EXTRA', '')
                core.send_message(vk, user_id, "✅ Дополнительный текст приветствия удалён.")
                print(f"[DEBUG] Дополнительный текст приветствия удалён")
                
                # Отправляем приветствие без дополнительного текста
                greeting_message = core.GetTimeBasedGreeting()
                user_info = vk.users.get(user_ids=user_id)[0]
                first_name = user_info.get('first_name', 'Гость')
                full_greeting = f"{greeting_message}, {first_name}! ✨"
                core.send_message(vk, user_id, full_greeting, keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
                
            except Exception as e:
                core.send_message(vk, user_id, f"❌ Ошибка при удалении приветствия: {e}")
                print(f"[DEBUG] Ошибка удаления приветствия: {e}")
        
        else:
            # Изменяем приветствие (старый формат)
            new_text = parts[1] if len(parts) == 2 else ' '.join(parts[1:])
            
            # Сохраняем в базу данных
            try:
                core.save_setting_to_db('GREETING_EXTRA', new_text)
                core.send_message(vk, user_id, f"✅ Приветствие обновлено:\n\n{new_text}")
                print(f"[DEBUG] Приветствие обновлено на: {new_text}")
                
                # Отправляем обновленное приветствие
                greeting_message = core.GetTimeBasedGreeting()
                user_info = vk.users.get(user_ids=user_id)[0]
                first_name = user_info.get('first_name', 'Гость')
                full_greeting = f"{greeting_message}, {first_name}! ✨\n\n{new_text}"
                core.send_message(vk, user_id, full_greeting, keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
                
            except Exception as e:
                core.send_message(vk, user_id, f"❌ Ошибка при обновлении приветствия: {e}")
                print(f"[DEBUG] Ошибка обновления приветствия: {e}")
    
    elif command == "!сотрудник" and len(parts) >= 3:
        action = parts[1].lower()
        
        if action == "добавить" and len(parts) >= 3:
            try:
                from database.models import add_employee
                employee_id = int(parts[2])
                success = add_employee(employee_id)
                if success:
                    core.send_message(vk, user_id, f"✅ Сотрудник {employee_id} добавлен.")
                    print(f"[DEBUG] Добавлен сотрудник: {employee_id}")
                else:
                    core.send_message(vk, user_id, f"❌ Не удалось добавить сотрудника {employee_id}")
            except ValueError:
                core.send_message(vk, user_id, f"❌ Неверный формат ID: {parts[2]}")
            except Exception as e:
                core.send_message(vk, user_id, f"❌ Ошибка при добавлении сотрудника: {e}")
        
        elif action == "удалить" and len(parts) >= 3:
            try:
                from database.models import remove_employee
                employee_id = int(parts[2])
                success, remaining = remove_employee(employee_id)
                if success:
                    core.send_message(vk, user_id, f"✅ Сотрудник {employee_id} удален. Осталось: {remaining}")
                    print(f"[DEBUG] Удален сотрудник: {employee_id}")
                else:
                    core.send_message(vk, user_id, f"❌ Не удалось удалить сотрудника {employee_id}")
            except ValueError:
                core.send_message(vk, user_id, f"❌ Неверный формат ID: {parts[2]}")
            except Exception as e:
                core.send_message(vk, user_id, f"❌ Ошибка при удалении сотрудника: {e}")
    
    elif command == "!акция" and len(parts) >= 3:
        action = parts[1].lower()
        
        if action == "добавить" and len(parts) >= 3:
            promo_text = parts[2] if len(parts) == 3 else ' '.join(parts[2:])
            try:
                from database.models import add_promo_line_db
                add_promo_line_db(promo_text)
                core.send_message(vk, user_id, f"✅ Акция добавлена:\n\n{promo_text}")
                print(f"[DEBUG] Добавлена акция: {promo_text}")
            except Exception as e:
                core.send_message(vk, user_id, f"❌ Ошибка при добавлении акции: {e}")
        
        elif action == "удалить" and len(parts) >= 3:
            try:
                from database.models import delete_promo_line_db
                line_num = int(parts[2])
                success, remaining = delete_promo_line_db(line_num)
                if success:
                    core.send_message(vk, user_id, f"✅ Акция #{line_num} удалена. Осталось: {remaining}")
                else:
                    core.send_message(vk, user_id, f"❌ Не удалось удалить акцию #{line_num}")
            except (ValueError, Exception) as e:
                core.send_message(vk, user_id, f"❌ Ошибка: {e}")
    
    else:
        core.send_message(vk, user_id, "❌ Неизвестная команда. Доступные команды:\n\n!приветствие [текст] - добавить текст\n!приветствие удалить - убрать текст\n!сотрудник добавить [ID]\n!сотрудник удалить [ID]\n!акция добавить [текст]\n!акция удалить [номер]")
        print(f"[DEBUG] Неизвестная команда: {command}")


def _parse_client_payload(payload):
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


def handle_user_message(vk, user_id, text, payload, attachments, message_id):
    """Главный обработчик сообщений от пользователей."""
    
    state_info = core.get_user_state(user_id)
    state = state_info["state"]
    order = state_info["order"]

    # Проверяем админские команды (для всех администраторов из БД)
    if text.startswith('!'):
        try:
            from database.models import list_employee_ids
            admin_ids = list_employee_ids()
            if user_id in admin_ids:
                return _handle_admin_command(vk, user_id, text)
            else:
                core.send_message(vk, user_id, "❌ У вас нет прав для выполнения админских команд.")
                print(f"[DEBUG] Попытка выполнить админ команду не админом {user_id}: {text}")
                print(f"[DEBUG] Текущие администраторы: {admin_ids}")
                return
        except Exception as e:
            print(f"[DEBUG] Ошибка проверки прав доступа: {e}")
            core.send_message(vk, user_id, "❌ Ошибка проверки прав доступа.")
            return

    # Проверяем кнопку "Заказ" (кнопка убрана из меню, но обработка остаётся)
    if text == "🛒 Заказ":
        print(f"[DEBUG] Нажата кнопка 'Заказ' пользователем {user_id}")
        # Отправляем сообщение с формой заказа
        order_form = """Укажите:
- что будете заказывать;
- количество приборов;
- требуется ли доп набор (имбирь васаби и соевый соус);
- адрес доставки;
- номер для связи;
- способ оплаты;
После того, как заполните форму ожидайте ответа оператора"""
        
        # Создаем клавиатуру только с кнопкой "Отменить заказ"
        cancel_keyboard = kbd.create_cancel_order_keyboard()
        core.send_message(vk, user_id, order_form, keyboard=cancel_keyboard)
        
        # Устанавливаем флаг, чтобы пропустить следующее сообщение
        store.user_just_replied[user_id] = True
        
        # НЕ переходим в состояние заказа - ждем полного заказа от клиента
        # Оставляем пользователя в состоянии IDLE но с флагом что ожидаем заказ
        state_info["expecting_order"] = True
        return

    print(f"[DEBUG] Получено сообщение от {user_id}: '{text}'")
    print(f"[DEBUG] Состояние пользователя: {state}")
    print(f"[DEBUG] Ожидание заказа: {state_info.get('expecting_order', False)}")

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
        # Если ожидаем полный заказ, проверяем его
        if state_info.get("expecting_order"):
            # Проверяем кнопку отмены
            if text == CANCEL_ORDER_TEXT:
                core.cancel_order(vk, user_id)
                return

            # Проверяем, является ли сообщение полным заказом
            if _is_complete_order(text):
                # Если клиент прислал полный заказ, обрабатываем его
                _process_complete_order(vk, user_id, text, state_info, order)
                return
            else:
                # Если заказ неполный, сообщаем об ошибке
                cancel_keyboard = kbd.create_cancel_order_keyboard()
                core.send_message(vk, user_id, "❌ Заявка неправильная! Укажите все необходимые поля:\n\n• Что заказываете\n• Номер телефона\n• Адрес доставки\n\nОтправьте полный заказ одним сообщением.", keyboard=cancel_keyboard)
                return
        
        # Обычная обработка состояния IDLE - НО команды уже обработаны выше
        _handle_idle(vk, user_id, text, state_info, now_t)
        return

    if state == STATE_CONTACT_ADMIN:
        _handle_contact_admin(vk, user_id, text)
        return

    # Все остальные состояния больше не используются
    core.send_message(vk, user_id, "Пожалуйста, отправьте полный заказ одним сообщением по форме выше.", keyboard=kbd.create_main_menu_keyboard_for_user(user_id))
    return


def _handle_idle(vk, user_id, text, state_info, now_t):
    # Проверяем на пустое сообщение - возвращаем в главное меню
    if not text or not text.strip():
        core.handle_start_or_menu(vk, user_id)
        return

    # Команды (!) уже обработаны выше, сюда не должны доходить
    if text.startswith('!'):
        print(f"[DEBUG] Команда попала в _handle_idle: {text}")
        return

    if text in ("Начать", "Старт"):
        core.handle_start_or_menu(vk, user_id)
        return

    # Кнопка "Заказ" обрабатывается выше, здесь её не проверяем

    if text == "📍 Адрес для самовывоза":
        address_text = settings.ORDER_ADDRESS_TEXT.replace('\\n', '\n')
        core.send_message(vk, user_id, f"📍 Адрес для самовывоза:\n{address_text}")
        return

    # Если это не известная команда или кнопка, возвращаем в главное меню
    core.handle_start_or_menu(vk, user_id)


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
            core.send_message(vk, user_id, "Не найден заказ для прикрепления чека. Обратитесь к оператору.")
            return
        client_mention = f"Клиент {user_id}"
        for admin_id in [settings.VK_ADMIN_ID]:
            try:
                vk.messages.send(
                    user_id=admin_id,
                    message=f"Поступил скриншот оплаты по заказу #{order_id} от клиента {client_mention}",
                    random_id=0,
                    forward_messages=message_id,
                )
            except Exception as e:
                print(f"[DEBUG] Ошибка отправки скриншота: {e}")
        core.send_message(vk, user_id, "✅ Чек получен. Ожидайте подтверждения оплаты оператором.")
    else:
        core.send_message(vk, user_id, "Пожалуйста, пришлите скриншот чека (фото/документ).")


def _handle_contact_admin(vk, user_id, text):
    if not text.strip():
        core.send_message(vk, user_id, "Напишите ваше сообщение.", keyboard=kbd.create_contact_admin_keyboard())
        return
    
    # Отправляем сообщение основному админу
    admin_id = settings.VK_ADMIN_ID
    try:
        vk.messages.send(
            user_id=admin_id,
            message=f"📩 Вопрос от клиента {user_id}:\n\n{text}",
            random_id=0,
        )
        print(f"[DEBUG] Вопрос клиента отправлен админу {admin_id}")
    except Exception as e:
        print(f"[DEBUG] Ошибка отправки вопроса админу: {e}")
    
    core.send_message(
        vk,
        user_id,
        "✅ Ваше сообщение отправлено оператору. Ожидайте ответа.",
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


def _handle_set_cutlery(vk, user_id, text, state_info, order):
    try:
        n = int((text or "").strip())
    except ValueError:
        core.send_message(
            vk,
            user_id,
            "Какое количество приборов вам нужно? (палочек)",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return

    if n < 1 or n > 50:
        core.send_message(
            vk,
            user_id,
            "Введите число от 1 до 50.",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return

    # Упрощаем ввод: пользователь вводит число палочек текстом.
    order["cutlery"] = str(n)
    core.push_history(state_info, STATE_SET_CUTLERY)
    state_info["state"] = STATE_SET_EXTRA_SET
    core.prompt_for_state(vk, user_id, STATE_SET_EXTRA_SET)


def _handle_set_payment_method(vk, user_id, text, state_info, order):
    if text not in ("Наличными", "Переводом"):
        core.send_message(
            vk,
            user_id,
            "Пожалуйста, выберите способ оплаты кнопкой: Наличными или Переводом.",
            keyboard=kbd.create_payment_keyboard(),
        )
        return
    order["payment_method"] = text
    core.push_history(state_info, STATE_SET_PAYMENT_METHOD)
    if text == "Наличными":
        state_info["state"] = STATE_SET_ORDER_TIME
        core.prompt_for_state(vk, user_id, STATE_SET_ORDER_TIME)
        return
    if text == "Переводом":
        state_info["state"] = STATE_SET_PAYMENT_TRANSFER_TIMING
        core.prompt_for_state(vk, user_id, STATE_SET_PAYMENT_TRANSFER_TIMING)
        return


def _handle_set_payment_transfer_timing(vk, user_id, text, state_info, order):
    raw = (text or "").strip().lower()
    if "сейчас" in raw or raw == "сейчас":
        order["payment_method"] = "Переводом сейчас"
        core.push_history(state_info, STATE_SET_PAYMENT_TRANSFER_TIMING)
        state_info["state"] = STATE_SET_ORDER_TIME
        core.prompt_for_state(vk, user_id, STATE_SET_ORDER_TIME)
        return
    if "при получении" in raw or "получении" in raw or raw == "при получении":
        order["payment_method"] = "Переводом при получении"
        core.push_history(state_info, STATE_SET_PAYMENT_TRANSFER_TIMING)
        state_info["state"] = STATE_SET_ORDER_TIME
        core.prompt_for_state(vk, user_id, STATE_SET_ORDER_TIME)
        return
    core.send_message(
        vk,
        user_id,
        "Пожалуйста, выберите: Сейчас или При получении.",
        keyboard=kbd.create_payment_transfer_timing_keyboard(),
    )


def _handle_set_order_time(vk, user_id, text, state_info, order):
    order_time_text = (text or "").strip()
    if not order_time_text:
        core.send_message(
            vk,
            user_id,
            "Комментарий к заказу:",
            keyboard=kbd.create_order_nav_keyboard(),
        )
        return
    order["order_time"] = order_time_text
    core.push_history(state_info, STATE_SET_ORDER_TIME)
    state_info["state"] = STATE_CONFIRM_ORDER
    core.prompt_for_state(vk, user_id, STATE_CONFIRM_ORDER)


def _handle_confirm_order(vk, user_id, text, order):
    if "подтверд" in text.lower():
        core.register_and_send_order_to_admin(vk, user_id, order)
        core.reset_user_state(user_id)
        # Текст с реквизитами уже отправлен в register_and_send_order_to_admin
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

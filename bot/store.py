from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import date


# Хранилище FSM для пользователей.
# user_states[user_id] = {"state": str, "order": dict, "history": list, "active_order_id": Optional[int]}
user_states: Dict[int, Dict[str, Any]] = {}

# Состояния админа для ввода причины/ответа/цены/и т.п.
admin_states: Dict[int, Dict[str, Any]] = {}

# Заказы, привязанные к order_id.
orders: Dict[int, Dict[str, Any]] = {}
next_order_id: int = 1

# Флаг приёма заявок админом.
accepting_orders_enabled: bool = True
accepting_orders_reason: str = ""

# Отслеживание последнего сообщения пользователя для приветствий
# user_last_message[user_id] = date
user_last_message: Dict[int, date] = {}

# Флаг для предотвращения чтения следующего сообщения клиента
# user_just_replied[user_id] = bool
user_just_replied: Dict[int, bool] = {}


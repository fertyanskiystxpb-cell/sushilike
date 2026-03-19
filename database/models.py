from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, Optional

from config import settings


# TODO: Database integration is prepared but requires license activation/additional configuration to persist data.


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Инициализация таблиц SQLite (только если DB_ENABLED=True)."""
    if not settings.DB_ENABLED:
        return

    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                phone TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                payload_json TEXT,
                status TEXT,
                price TEXT,
                created_at TEXT
            );
            """
        )
        conn.commit()


def save_order_stub(order_id: int, user_id: int, payload: Dict[str, Any], status: str) -> None:
    """
    Stub-сохранение заказа.
    По умолчанию DB_ENABLED=False: ничего не сохраняем, только печатаем в консоль.
    """
    if not settings.DB_ENABLED:
        print("[DB_STUB] Order placed:", {"order_id": order_id, "user_id": user_id, "status": status})
        print("[DB_STUB] Payload:", payload)
        return

    # При включенной БД: сохраняем в SQLite.
    import json
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO orders (id, user_id, payload_json, status, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (order_id, user_id, json.dumps(payload, ensure_ascii=False), status, payload.get("price"), now_iso),
        )
        conn.commit()


@dataclass
class OrderView:
    id: int
    user_id: int
    status: str
    price: Optional[str] = None
    preorder: bool = False


from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import settings


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _config_fallback_admin_ids() -> List[int]:
    ids_str = getattr(settings, "VK_ADMIN_IDS", "") or ""
    if ids_str.strip():
        try:
            return [int(x.strip()) for x in ids_str.split(",") if x.strip()]
        except (ValueError, AttributeError):
            pass
    return [int(settings.VK_ADMIN_ID)]


def _ensure_column(conn: sqlite3.Connection, table: str, col: str, coltype: str) -> None:
    cur = conn.execute(f"PRAGMA table_info({table})")
    names = {row[1] for row in cur.fetchall()}
    if col not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")


def init_db() -> None:
    if not settings.DB_ENABLED:
        return

    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                user_id INTEGER PRIMARY KEY NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS promos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0
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
                created_at TEXT,
                gift TEXT,
                business_date TEXT
            );
            """
        )
        _ensure_column(conn, "orders", "gift", "TEXT")
        _ensure_column(conn, "orders", "business_date", "TEXT")

        cur = conn.execute("SELECT COUNT(*) AS c FROM employees")
        if cur.fetchone()["c"] == 0:
            for uid in _config_fallback_admin_ids():
                conn.execute("INSERT OR IGNORE INTO employees (user_id) VALUES (?)", (uid,))

        cur = conn.execute("SELECT COUNT(*) AS c FROM promos")
        if cur.fetchone()["c"] == 0:
            _import_promos_from_file(conn)

        conn.commit()

    _sync_next_order_id_from_db()


def _import_promos_from_file(conn: sqlite3.Connection) -> None:
    import os

    path = settings.PROMOS_FILE
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n\r") for ln in f.readlines() if ln.strip()]
    except OSError:
        return
    for i, body in enumerate(lines):
        conn.execute(
            "INSERT INTO promos (body, sort_order) VALUES (?, ?)",
            (body, i),
        )


def _sync_next_order_id_from_db() -> None:
    if not settings.DB_ENABLED:
        return
    from bot import store

    with _connect() as conn:
        row = conn.execute("SELECT MAX(id) AS m FROM orders").fetchone()
        m = row["m"] if row else None
        if m is not None:
            store.next_order_id = max(store.next_order_id, int(m) + 1)


def list_employee_ids() -> List[int]:
    if not settings.DB_ENABLED:
        return _config_fallback_admin_ids()
    with _connect() as conn:
        rows = conn.execute("SELECT user_id FROM employees ORDER BY user_id").fetchall()
        return [int(r["user_id"]) for r in rows]


def add_employee(user_id: int) -> bool:
    """Добавить сотрудника (идемпотентно). Возвращает True, если ID теперь в списке."""
    if not settings.DB_ENABLED:
        return False
    uid = int(user_id)
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO employees (user_id) VALUES (?)", (uid,))
        conn.commit()
        return _employee_exists(conn, uid)


def _employee_exists(conn: sqlite3.Connection, user_id: int) -> bool:
    r = conn.execute("SELECT 1 FROM employees WHERE user_id = ?", (int(user_id),)).fetchone()
    return r is not None


def remove_employee(user_id: int) -> Tuple[bool, int]:
    """Удалить сотрудника. Возвращает (успех, оставшееся число)."""
    if not settings.DB_ENABLED:
        return False, 0
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
        if n <= 1:
            return False, n
        cur = conn.execute("DELETE FROM employees WHERE user_id = ?", (int(user_id),))
        conn.commit()
        left = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
        return cur.rowcount > 0, left


def count_employees() -> int:
    if not settings.DB_ENABLED:
        return len(_config_fallback_admin_ids())
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"])


def list_promo_lines() -> List[str]:
    if not settings.DB_ENABLED:
        return []
    with _connect() as conn:
        rows = conn.execute("SELECT body FROM promos ORDER BY sort_order ASC, id ASC").fetchall()
        return [r["body"] for r in rows]


def add_promo_line_db(line_text: str) -> None:
    if not settings.DB_ENABLED:
        return
    with _connect() as conn:
        row = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM promos").fetchone()
        nxt = int(row["m"]) + 1
        conn.execute("INSERT INTO promos (body, sort_order) VALUES (?, ?)", (line_text, nxt))
        conn.commit()


def delete_promo_line_db(line_number: int) -> Tuple[bool, int]:
    if not settings.DB_ENABLED:
        return False, 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id FROM promos ORDER BY sort_order ASC, id ASC"
        ).fetchall()
        total = len(rows)
        idx = line_number - 1
        if idx < 0 or idx >= total:
            return False, total
        pid = rows[idx]["id"]
        conn.execute("DELETE FROM promos WHERE id = ?", (pid,))
        conn.commit()
        return True, total - 1


def save_order_stub(
    order_id: int,
    user_id: int,
    payload: Dict[str, Any],
    status: str,
    business_date: Optional[str] = None,
) -> None:
    if not settings.DB_ENABLED:
        print("[DB_STUB] Order placed:", {"order_id": order_id, "user_id": user_id, "status": status})
        print("[DB_STUB] Payload:", payload)
        return

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()
    bd = business_date or ""
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO orders
            (id, user_id, payload_json, status, price, created_at, gift, business_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                user_id,
                json.dumps(payload, ensure_ascii=False),
                status,
                payload.get("price"),
                now_iso,
                None,
                bd or None,
            ),
        )
        conn.commit()


def update_order_record(
    order_id: int,
    user_id: int,
    payload: Dict[str, Any],
    status: str,
    price: Optional[str] = None,
    gift: Optional[str] = None,
    business_date: Optional[str] = None,
) -> None:
    if not settings.DB_ENABLED:
        return
    with _connect() as conn:
        conn.execute(
            """
            UPDATE orders SET
                user_id = ?,
                payload_json = ?,
                status = ?,
                price = ?,
                gift = ?,
                business_date = COALESCE(?, business_date)
            WHERE id = ?
            """,
            (
                user_id,
                json.dumps(payload, ensure_ascii=False),
                status,
                price,
                gift,
                business_date,
                order_id,
            ),
        )
        conn.commit()


def fetch_daily_stats(business_date: str) -> Tuple[int, int, int, int]:
    """Статистика за календарный день (business_date = дата в часовом поясе доставки)."""
    accepted_statuses = (
        "PAID",
        "WAIT_1_1_5",
        "WAIT_1_5_2",
        "ACCEPTED",
        "WAITING_FOR_CHECK",
        "IN_PROGRESS",
    )
    if not settings.DB_ENABLED:
        return 0, 0, 0, 0
    new_count = 0
    accepted = 0
    cancelled = 0
    paid_sum = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT status, price FROM orders WHERE business_date = ?",
            (business_date,),
        ).fetchall()
    import re

    for r in rows:
        st = r["status"] or ""
        if st == "NEW":
            new_count += 1
        elif st == "CANCELLED":
            cancelled += 1
        elif st in accepted_statuses:
            accepted += 1
        if st == "PAID" and r["price"]:
            try:
                n = int(re.sub(r"\D", "", str(r["price"])))
                if n > 0:
                    paid_sum += n
            except (ValueError, TypeError):
                pass
    return new_count, accepted, cancelled, paid_sum


@dataclass
class OrderView:
    id: int
    user_id: int
    status: str
    price: Optional[str] = None
    preorder: bool = False

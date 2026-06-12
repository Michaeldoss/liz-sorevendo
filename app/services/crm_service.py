"""
crm_service.py — CRM SQLite para leads da So Revendo
Localização: app/services/crm_service.py
"""

import sqlite3
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("CRM_DB_PATH", "/tmp/sorevendo_crm.db"))


class CRMService:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS customers (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone       TEXT UNIQUE NOT NULL,
                    name        TEXT DEFAULT '',
                    source      TEXT DEFAULT '',
                    status      TEXT DEFAULT 'novo',
                    notes       TEXT DEFAULT '',
                    created_at  TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at  TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone       TEXT NOT NULL,
                    role        TEXT NOT NULL,
                    content     TEXT NOT NULL,
                    created_at  TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone           TEXT NOT NULL,
                    produto         TEXT NOT NULL,
                    quantidade      TEXT DEFAULT '',
                    dimensoes       TEXT DEFAULT '',
                    valor_total     REAL DEFAULT 0,
                    valor_entrada   REAL DEFAULT 0,
                    status          TEXT DEFAULT 'orcamento',
                    arte_status     TEXT DEFAULT 'aguardando',
                    obs             TEXT DEFAULT '',
                    created_at      TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
                );
            """)
        logger.info(f"[CRM] Banco iniciado em {self.db_path}")

    def get_or_create_customer(self, phone: str, name: str = "", source: str = "") -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
            if row:
                if name and not row["name"]:
                    conn.execute(
                        "UPDATE customers SET name=?, updated_at=datetime('now','localtime') WHERE phone=?",
                        (name, phone),
                    )
                return dict(row)
            conn.execute(
                "INSERT INTO customers (phone, name, source) VALUES (?, ?, ?)",
                (phone, name, source),
            )
            row = conn.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()
            logger.info(f"[CRM] Novo cliente: {phone} ({name})")
            return dict(row)

    def update_customer(self, phone: str, **kwargs):
        allowed = {"name", "source", "status", "notes"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [phone]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE customers SET {set_clause}, updated_at=datetime('now','localtime') WHERE phone=?",
                values,
            )

    def save_message(self, phone: str, role: str, content: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (phone, role, content) VALUES (?, ?, ?)",
                (phone, role, content),
            )

    def get_conversation_history(self, phone: str, limit: int = 30) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content FROM messages WHERE phone=? ORDER BY id DESC LIMIT ?",
                (phone, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def create_order(self, phone: str, produto: str, **kwargs) -> int:
        valor_total = kwargs.get("valor_total", 0)
        campos = {
            "phone": phone,
            "produto": produto,
            "quantidade": kwargs.get("quantidade", ""),
            "dimensoes": kwargs.get("dimensoes", ""),
            "valor_total": valor_total,
            "valor_entrada": round(valor_total * 0.5, 2),
            "obs": kwargs.get("obs", ""),
        }
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO orders (phone, produto, quantidade, dimensoes, valor_total, valor_entrada, obs)
                   VALUES (:phone, :produto, :quantidade, :dimensoes, :valor_total, :valor_entrada, :obs)""",
                campos,
            )
            return cur.lastrowid

    def update_order_status(self, order_id: int, status: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE orders SET status=?, updated_at=datetime('now','localtime') WHERE id=?",
                (status, order_id),
            )

    def get_orders(self, phone: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM orders WHERE phone=? ORDER BY id DESC", (phone,)
            ).fetchall()
        return [dict(r) for r in rows]

import sqlite3
import json
import contextlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "emails.db"


class Database:
    """Banco de dados SQLite local para histórico, métricas e controle de duplicidade."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Cria as tabelas caso não existam."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT,
                    message_date TEXT,
                    sender_name TEXT,
                    sender_email TEXT,
                    sender_domain TEXT,
                    subject TEXT,
                    category_id TEXT,
                    category_name TEXT,
                    target_folder TEXT,
                    score REAL,
                    reasons TEXT,
                    status TEXT,
                    summary TEXT,
                    urgency TEXT,
                    estimated_value TEXT,
                    auto_replied INTEGER DEFAULT 0,
                    is_dry_run INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uid ON processed_emails(uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON processed_emails(category_id)")
            conn.commit()

    def save_email(self, data: Dict[str, Any]) -> int:
        """Salva ou atualiza um e-mail processado no banco."""
        reasons_json = json.dumps(data.get("reasons", []), ensure_ascii=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processed_emails (
                    uid, message_date, sender_name, sender_email, sender_domain,
                    subject, category_id, category_name, target_folder, score,
                    reasons, status, summary, urgency, estimated_value,
                    auto_replied, is_dry_run
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(data.get("uid", "")),
                str(data.get("date", "")),
                str(data.get("sender_name", "")),
                str(data.get("sender_email", "")),
                str(data.get("sender_domain", "")),
                str(data.get("subject", "")),
                str(data.get("category_id", "")),
                str(data.get("category_name", "")),
                str(data.get("target_folder", "")),
                float(data.get("score", 0.0)),
                reasons_json,
                str(data.get("status", "")),
                str(data.get("summary", "")),
                str(data.get("urgency", "Média")),
                str(data.get("estimated_value", "Não identificado")),
                1 if data.get("auto_replied") else 0,
                1 if data.get("is_dry_run") else 0
            ))
            conn.commit()
            return cursor.lastrowid

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retorna os e-mails processados mais recentes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM processed_emails 
                ORDER BY id DESC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["reasons"] = json.loads(d["reasons"])
                except Exception:
                    d["reasons"] = []
                result.append(d)
            return result

    def get_metrics(self) -> Dict[str, Any]:
        """Calcula métricas consolidadas para o Dashboard."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total geral
            cursor.execute("SELECT COUNT(*) FROM processed_emails")
            total = cursor.fetchone()[0]

            # Por Categoria
            cursor.execute("""
                SELECT category_name, COUNT(*) as qtd 
                FROM processed_emails 
                GROUP BY category_name
            """)
            by_category = {row["category_name"]: row["qtd"] for row in cursor.fetchall()}

            # Por Urgência
            cursor.execute("""
                SELECT urgency, COUNT(*) as qtd 
                FROM processed_emails 
                WHERE urgency IS NOT NULL AND urgency != ''
                GROUP BY urgency
            """)
            by_urgency = {row["urgency"]: row["qtd"] for row in cursor.fetchall()}

            # Total de auto-respostas
            cursor.execute("SELECT COUNT(*) FROM processed_emails WHERE auto_replied = 1")
            total_replied = cursor.fetchone()[0]

            return {
                "total_emails": total,
                "by_category": by_category,
                "by_urgency": by_urgency,
                "auto_replies_sent": total_replied
            }

    def is_replied(self, uid: str) -> bool:
        """Verifica se já respondemos este UID para evitar envios duplicados."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM processed_emails WHERE uid = ? AND auto_replied = 1", (str(uid),))
            return cursor.fetchone() is not None

import json
import logging
import os
import sqlite3
import time
from pathlib import Path

log = logging.getLogger("chem-agent.storage")

def get_appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = Path.home() / "AppData" / "Local"
    path = Path(base) / "chem-agent"
    path.mkdir(parents=True, exist_ok=True)
    return path

class HistoryDB:
    def __init__(self):
        self.db_path = get_appdata_dir() / "history.db"
        self._init_db()

    def _get_conn(self):
        # check_same_thread=False нужен, так как PyWebView может вызывать методы из разных потоков
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    reaction_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    reagents TEXT,
                    status TEXT,
                    main_product TEXT,
                    equation TEXT,
                    full_json TEXT
                )
            """)
            conn.commit()

    def add_entry(self, data: dict):
        try:
            rid = data.get("reaction_id", str(time.time()))
            reagents = json.dumps([r.get("formula") for r in data.get("input", {}).get("reagents", [])], ensure_ascii=False)
            eqs = data.get("balanced_equations") or []
            eq_text = eqs[0].get("equation") if eqs else None
            summary = data.get("summary") or {}
            main_prod = summary.get("main_product")
            status = data.get("status")
            
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO history (reaction_id, timestamp, reagents, status, main_product, equation, full_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (rid, time.time(), reagents, status, main_prod, eq_text, json.dumps(data, ensure_ascii=False))
                )
                conn.commit()
            log.info(f"История сохранена: {rid}")
        except Exception as e:
            log.error(f"Ошибка сохранения истории: {e}")

    def get_history(self, limit: int = 50) -> list[dict]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT reaction_id, timestamp, reagents, status, main_product, equation FROM history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "reaction_id": row["reaction_id"],
                    "timestamp": row["timestamp"],
                    "reagents": json.loads(row["reagents"]),
                    "status": row["status"],
                    "main_product": row["main_product"],
                    "equation": row["equation"]
                } for row in rows
            ]

    def get_entry(self, reaction_id: str) -> dict | None:
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT full_json FROM history WHERE reaction_id = ?", (reaction_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def delete_entry(self, reaction_id: str):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM history WHERE reaction_id = ?", (reaction_id,))
            conn.commit()

    def clear(self):
        with self._get_conn() as conn:
            conn.execute("DELETE FROM history")
            conn.commit()
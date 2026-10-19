import json
import logging
import traceback
from typing import Any, Callable

from chem_agent.storage.history import HistoryDB
from chem_agent.storage.settings import SettingsManager

log = logging.getLogger("chem-agent.bridge")

APP_VERSION = "2.0.0-dev"
CORE_VERSION = "1.0"

class Bridge:
    def __init__(self) -> None:
        self._window = None
        self._agent = None
        self.history_db = HistoryDB()
        self.settings = SettingsManager()
        log.info("Bridge initialized")

    def attach_window(self, window) -> None:
        self._window = window

    @property
    def agent(self):
        if self._agent is None:
            from chem_agent.agent import Agent
            self._agent = Agent(offline=True)
        return self._agent

    def _ok(self, data: Any = None) -> dict:
        safe_data = json.loads(json.dumps(data, default=float))
        return {"status": "ok", "data": safe_data, "error": None}

    def _err(self, code: str, message: str, details: str = "") -> dict:
        return {"status": "error", "data": None, "error": {"code": code, "message": message, "details": details}}

    def _safe(self, fn: Callable, *args, **kwargs) -> dict:
        try:
            return self._ok(fn(*args, **kwargs))
        except Exception as e:
            log.exception("Bridge error in %s", getattr(fn, "__name__", "?"))
            return self._err("INTERNAL_ERROR", str(e), traceback.format_exc())

    # --- Core ---
    def ping(self) -> dict:
        return self._ok({"message": "pong", "app_version": APP_VERSION, "core_version": CORE_VERSION})

    def get_version(self) -> dict:
        return self._ok({"app": "Chem-Agent", "version": APP_VERSION, "core": CORE_VERSION})

    def predict(self, request_data: dict) -> dict:
        def _do_predict():
            result = self.agent.predict(request=request_data)
            # Сохраняем в SQLite при любом статусе (ok, error, no_reaction)
            self.history_db.add_entry(result.data)
            return result.data
        return self._safe(_do_predict)

    # --- History ---
    def get_history(self, limit: int = 50) -> dict:
        return self._safe(self.history_db.get_history, limit)

    def get_history_entry(self, reaction_id: str) -> dict:
        def _get():
            entry = self.history_db.get_entry(reaction_id)
            if not entry:
                raise ValueError("Запись не найдена")
            return entry
        return self._safe(_get)

    def delete_history_entry(self, reaction_id: str) -> dict:
        return self._safe(self.history_db.delete_entry, reaction_id)

    def clear_history(self) -> dict:
        return self._safe(self.history_db.clear)

    # --- Settings ---
    def get_settings(self) -> dict:
        return self._ok(self.settings.get_all())

    def save_settings(self, new_settings: dict) -> dict:
        self._safe(self.settings.save, new_settings)
        return self._ok(self.settings.get_all())
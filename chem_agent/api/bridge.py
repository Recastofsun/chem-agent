"""
Bridge между UI (JS) и ядром (Python).
Контракт ответа: {status: 'ok' | 'error', data: Any, error: {code, message, details} | None}.
"""
from __future__ import annotations

import json
import logging
import traceback
from typing import Any, Callable

log = logging.getLogger("chem-agent.bridge")

APP_VERSION = "2.0.0-dev"
CORE_VERSION = "1.0"


class Bridge:
    def __init__(self) -> None:
        self._window = None
        self._agent = None
        log.info("Bridge initialized")

    def attach_window(self, window) -> None:
        self._window = window

    @property
    def agent(self):
        """Ленивая инициализация ядра (чтобы не тормозить запуск окна)."""
        if self._agent is None:
            log.info("Инициализация Agent (загрузка базы данных)...")
            from chem_agent.agent import Agent
            self._agent = Agent(offline=True)
            log.info("Agent готов к работе.")
        return self._agent

    # --- контракт -----------------------------------------------------
    def _ok(self, data: Any = None) -> dict:
        # Очищаем данные от возможных numpy-типов, чтобы JSON.stringify в JS не падал
        safe_data = json.loads(json.dumps(data, default=float))
        return {"status": "ok", "data": safe_data, "error": None}

    def _err(self, code: str, message: str, details: str = "") -> dict:
        return {"status": "error", "data": None,
                "error": {"code": code, "message": message, "details": details}}

    def _safe(self, fn: Callable, *args, **kwargs) -> dict:
        try:
            return self._ok(fn(*args, **kwargs))
        except Exception as e:
            log.exception("Bridge error in %s", getattr(fn, "__name__", "?"))
            return self._err("INTERNAL_ERROR", str(e), traceback.format_exc())

    # --- публичные методы ---------------------------------------------
    def ping(self) -> dict:
        return self._ok({"message": "pong", "app_version": APP_VERSION, "core_version": CORE_VERSION})

    def get_version(self) -> dict:
        return self._ok({"app": "Chem-Agent", "version": APP_VERSION, "core": CORE_VERSION})

    def predict(self, request_data: dict) -> dict:
        """Принимает запрос из UI, вызывает ядро, возвращает результат."""
        def _do_predict():
            result = self.agent.predict(request=request_data)
            return result.data
        return self._safe(_do_predict)

    def get_history(self, limit: int = 50) -> dict:
        return self._err("NOT_IMPLEMENTED", "get_history() появится на шаге 3")

    def get_element_compounds(self, element: str) -> dict:
        return self._err("NOT_IMPLEMENTED", "появится на шаге 4")
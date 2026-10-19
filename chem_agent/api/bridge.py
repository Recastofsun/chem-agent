"""
Bridge между UI (JS) и ядром (Python).
Контракт ответа: {status: 'ok' | 'error', data: Any, error: {code, message, details} | None}.
UI никогда не получает исключение Python.
"""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

log = logging.getLogger("chem-agent.bridge")

APP_VERSION = "2.0.0-dev"
CORE_VERSION = "1.0"


class Bridge:
    def __init__(self) -> None:
        self._window = None
        log.info("Bridge initialized")

    def attach_window(self, window) -> None:
        """Даёт Bridge доступ к окну (закрытие, диалоги и т.п. — на будущее)."""
        self._window = window

    # --- контракт -----------------------------------------------------
    def _ok(self, data: Any = None) -> dict:
        return {"status": "ok", "data": data, "error": None}

    def _err(self, code: str, message: str, details: str = "") -> dict:
        return {"status": "error", "data": None,
                "error": {"code": code, "message": message, "details": details}}

    def _safe(self, fn: Callable, *args, **kwargs) -> dict:
        try:
            return self._ok(fn(*args, **kwargs))
        except Exception as e:
            log.exception("Bridge error in %s", getattr(fn, "__name__", "?"))
            return self._err("INTERNAL_ERROR", str(e), traceback.format_exc())

    # --- публичные методы (доступны из JS как pywebview.api.*) --------
    def ping(self) -> dict:
        return self._ok({"message": "pong", "app_version": APP_VERSION,
                         "core_version": CORE_VERSION})

    def get_version(self) -> dict:
        return self._ok({"app": "Chem-Agent", "version": APP_VERSION,
                         "core": CORE_VERSION})

    # --- заглушки следующих шагов -------------------------------------
    def predict(self, reactants: list[str], conditions: dict | None = None) -> dict:
        return self._err("NOT_IMPLEMENTED", "predict() появится на шаге 2")

    def get_history(self, limit: int = 50) -> dict:
        return self._err("NOT_IMPLEMENTED", "get_history() появится на шаге 3")

    def get_element_compounds(self, element: str) -> dict:
        return self._err("NOT_IMPLEMENTED", "появится на шаге 4 (таблица Менделеева)")
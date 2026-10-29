"""MCP-сервер Chem-Agent (W-12, ТЗ п. 8): 6 инструментов для внешних агентов.

Своя реализация протокола Model Context Protocol поверх stdio (JSON-RPC 2.0, по сообщению на строку),
без пакета mcp: ядро поставляется офлайн, лишняя зависимость не нужна. Методы протокола:
initialize, notifications/initialized, ping, tools/list, tools/call.

Инструменты (ТЗ 8.1):
- predict(request) - P0, тот же запрос, что Agent.predict(request=...); результат пишется в историю;
- get_version() - P0;
- get_history(limit) - P1;
- get_compounds_by_element(element) - P1;
- search(query, limit) - P2, поиск по базе: формула (в любом порядке элементов), название ru/en;
- benchmark(reference, limit) - P2, Accuracy@3 на эталонном наборе.

Запуск: python -m chem_agent.mcp
Подключение (например, Claude Desktop): {"command": "python", "args": ["-m", "chem_agent.mcp"], "cwd": "<папка проекта>"}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "chem-agent", "version": "2.5.0"}

TOOLS = [
    {"name": "predict", "description": "Предсказать продукты, уравнения и термодинамику реакции. "
     "request: {reagents: [{formula, moles, phase}], conditions: {...}, options: {...}}",
     "inputSchema": {"type": "object", "properties": {"request": {"type": "object"}}, "required": ["request"]}},
    {"name": "get_version", "description": "Версии ядра, базы и сервера",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_history", "description": "Последние расчеты из истории",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}},
    {"name": "get_compounds_by_element", "description": "Вещества базы, содержащие элемент",
     "inputSchema": {"type": "object", "properties": {"element": {"type": "string"}}, "required": ["element"]}},
    {"name": "search", "description": "Поиск веществ в базе по формуле или названию (ru/en)",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                       "limit": {"type": "integer", "default": 20}},
                     "required": ["query"]}},
    {"name": "benchmark", "description": "Точность Accuracy@3 на эталонном наборе (holdout_100 по умолчанию)",
     "inputSchema": {"type": "object", "properties": {"reference": {"type": "string"},
                                                       "limit": {"type": "integer"}}}},
]

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


class ToolError(Exception):
    pass


def _species_row(s) -> dict:
    return {"formula": s.formula, "phase": s.phase, "name_ru": s.name_ru, "name_en": s.name_en,
            "dGf_kJ_mol": s.dGf, "dHf_kJ_mol": s.dHf, "source": s.source}


class MCPServer:
    def __init__(self, agent=None, history=None):
        self._agent = agent
        self._history = history
        self.handlers: dict[str, Callable[[dict], Any]] = {
            "predict": self.predict, "get_version": self.get_version, "get_history": self.get_history,
            "get_compounds_by_element": self.get_compounds_by_element, "search": self.search,
            "benchmark": self.benchmark,
        }

    @property
    def agent(self):
        if self._agent is None:
            from ..agent import Agent
            self._agent = Agent()
        return self._agent

    @property
    def history(self):
        if self._history is None:
            from ..storage.history import HistoryDB
            self._history = HistoryDB()
        return self._history

    # ---- инструменты
    def predict(self, args: dict) -> dict:
        req = args.get("request")
        if not isinstance(req, dict):
            raise ToolError("request: ожидается объект JSON")
        data = self.agent.predict(request=req).data
        try:
            self.history.add_entry(data)
        except Exception:  # история не должна ломать расчет
            pass
        return data

    def get_version(self, args: dict) -> dict:
        from .. import __version__
        return {"server": SERVER_INFO["version"], "core": __version__, "protocol": PROTOCOL_VERSION,
                "database": {k: v for k, v in self.agent.db.meta.items()}}

    def get_history(self, args: dict) -> list:
        return self.history.get_history(int(args.get("limit", 20)))

    def get_compounds_by_element(self, args: dict) -> list:
        el = str(args.get("element", "")).strip()
        if not el:
            raise ToolError("element: обязательный параметр")
        return [_species_row(s) for s in self.agent.db.find_compounds_by_element(el)]

    def search(self, args: dict) -> list:
        q = str(args.get("query", "")).strip()
        if not q:
            raise ToolError("query: обязательный параметр")
        return [_species_row(s) for s in self.agent.db.search(q, int(args.get("limit", 20)))]

    def benchmark(self, args: dict) -> dict:
        from ..benchmark import evaluate, load_reference
        ref = args.get("reference") or str(PROJECT_DIR / "tests" / "fixtures" / "holdout_100.json")
        rx = load_reference(Path(ref))
        if args.get("limit"):
            rx = rx[: int(args["limit"])]
        res = evaluate(self.agent, rx)
        res["failed"] = [r for r in res.pop("rows") if r["in_scope"] and not r["ok"]]
        return res

    # ---- протокол
    def handle(self, msg: dict) -> dict | None:
        """Одно сообщение JSON-RPC -> ответ (None для уведомлений)."""
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None:  # уведомление: notifications/initialized и др.
            return None
        try:
            if method == "initialize":
                result = {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO,
                          "capabilities": {"tools": {"listChanged": False}}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                name = params.get("name")
                if name not in self.handlers:
                    return _error(mid, -32602, f"Неизвестный инструмент: {name}")
                try:
                    out = self.handlers[name](params.get("arguments") or {})
                    result = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False, default=_json)}],
                              "isError": False}
                except Exception as e:  # ошибка инструмента - в результате, не в протоколе
                    result = {"content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}], "isError": True}
            else:
                return _error(mid, -32601, f"Метод не поддерживается: {method}")
        except Exception as e:  # noqa: BLE001
            return _error(mid, -32603, f"{type(e).__name__}: {e}")
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def serve(self, stdin=None, stdout=None) -> None:
        stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                resp = _error(None, -32700, f"Parse error: {e}")
            else:
                resp = self.handle(msg)
            if resp is not None:
                stdout.write(json.dumps(resp, ensure_ascii=False, default=_json) + "\n")
                stdout.flush()


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _json(o):
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass
    return str(o)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdin.reconfigure(encoding="utf-8")
    MCPServer().serve()

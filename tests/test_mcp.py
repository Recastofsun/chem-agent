"""W-12: MCP-сервер - протокол JSON-RPC через stdio и 6 инструментов."""
import io
import json

import pytest

from chem_agent.mcp import TOOLS, MCPServer


class FakeHistory:
    def __init__(self):
        self.rows = []

    def add_entry(self, data):
        self.rows.append({"reaction_id": data["reaction_id"], "status": data["status"]})

    def get_history(self, limit=50):
        return self.rows[-limit:][::-1]


@pytest.fixture
def server(agent):
    return MCPServer(agent=agent, history=FakeHistory())


def _call(server, name, args=None, mid=1):
    r = server.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": args or {}}})
    res = r["result"]
    return res["isError"], (json.loads(res["content"][0]["text"]) if not res["isError"] else res["content"][0]["text"])


def test_six_tools_listed(server):
    r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = [t["name"] for t in r["result"]["tools"]]
    assert names == ["predict", "get_version", "get_history", "get_compounds_by_element", "search", "benchmark"]
    assert all("inputSchema" in t for t in TOOLS)


def test_initialize_and_notification(server):
    r = server.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
    assert r["result"]["capabilities"]["tools"] is not None
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_predict_and_history(server):
    req = {"reagents": [{"formula": "NaOH", "moles": 0.1, "phase": "aq"}, {"formula": "HCl", "moles": 0.1, "phase": "aq"}],
           "options": {"include_uncertainty": False}}
    err, d = _call(server, "predict", {"request": req})
    assert not err and d["summary"]["main_product"] == "NaCl"
    err, h = _call(server, "get_history", {"limit": 5})
    assert h[0]["reaction_id"] == d["reaction_id"]


def test_version_compounds_search(server):
    _, v = _call(server, "get_version")
    assert v["server"] == "2.5.0" and v["protocol"]
    _, comp = _call(server, "get_compounds_by_element", {"element": "Ba"})
    assert any(c["formula"] == "BaSO4" for c in comp)
    _, s = _call(server, "search", {"query": "ClNa"})     # та же брутто-формула в другой записи
    assert s[0]["formula"] == "NaCl"
    _, s = _call(server, "search", {"query": "волластонит"})
    assert s[0]["formula"] == "CaSiO3"


def test_benchmark_limited(server):
    _, b = _call(server, "benchmark", {"limit": 5})
    assert b["n_total"] == 5 and 0 <= b["accuracy_at_k"] <= 1 and "failed" in b


def test_errors(server):
    err, msg = _call(server, "predict", {"request": "NaCl"})
    assert err and "request" in msg
    r = server.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "nope"}})
    assert r["error"]["code"] == -32602
    assert server.handle({"jsonrpc": "2.0", "id": 9, "method": "resources/list"})["error"]["code"] == -32601


def test_stdio_roundtrip(server):
    inp = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"ping"}\nnot json\n')
    out = io.StringIO()
    server.serve(inp, out)
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert lines[0] == {"jsonrpc": "2.0", "id": 1, "result": {}} and lines[1]["error"]["code"] == -32700

"""No network: the guard blocks sockets; the package never imports network clients."""
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from chem_agent.utils import offline_guard

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = ("requests", "httpx", "aiohttp", "urllib.request", "openai", "anthropic", "google.generativeai",
             "cohere", "mistralai", "huggingface_hub", "wandb", "mlflow")


def test_guard_active():
    assert offline_guard.is_active()


@pytest.mark.parametrize("target", [("93.184.216.34", 80), ("api.anthropic.com", 443), ("8.8.8.8", 53)])
def test_outbound_blocked(target):
    with pytest.raises(offline_guard.NetworkBlockedError):
        socket.create_connection(target, timeout=1)


def test_getaddrinfo_blocked():
    with pytest.raises(offline_guard.NetworkBlockedError):
        socket.getaddrinfo("huggingface.co", 443)


def test_raw_socket_connect_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(offline_guard.NetworkBlockedError):
            s.connect(("1.1.1.1", 443))
    finally:
        s.close()


def test_loopback_allowed():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    c = socket.create_connection(("127.0.0.1", port), timeout=2)
    c.close()
    srv.close()


def test_prediction_runs_offline(agent):
    offline_guard.assert_offline()
    r = agent.predict(reagents=[{"formula": "NaOH", "moles": 0.01, "phase": "aq"},
                                {"formula": "HCl", "moles": 0.01, "phase": "aq"}],
                      options={"accuracy": "fast"}).data
    assert r["metadata"]["offline"] is True
    assert r["status"] == "ok"


def test_no_network_imports_in_source():
    bad = []
    for p in (ROOT / "chem_agent").rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        for mod in FORBIDDEN:
            if f"import {mod}" in text or f"from {mod} " in text or f"from {mod}." in text:
                bad.append(f"{p.name}: {mod}")
    assert not bad, bad


def test_subprocess_import_does_not_load_network_libs():
    code = ("import os; os.environ['CHEM_AGENT_OFFLINE']='1'; import sys; import chem_agent.agent, chem_agent.report; "
            "bad=[m for m in ('requests','httpx','aiohttp','openai','anthropic','huggingface_hub') if m in sys.modules]; "
            "print(','.join(bad))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""


def test_env_flag_enables_guard_in_fresh_process():
    code = ("import os; os.environ['CHEM_AGENT_OFFLINE']='1'; import chem_agent, socket\n"
            "try:\n    socket.create_connection(('1.1.1.1', 80), timeout=1); print('LEAK')\n"
            "except RuntimeError: print('BLOCKED')")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "BLOCKED", out.stdout + out.stderr

"""Launcher: starts local chem-agent server.

При старте:
  - проверяет, не занят ли порт 8000;
  - если занят нашим сервером (отвечает /health) — просит его завершиться;
  - если занят посторонним — предупреждает и предлагает выбрать другой порт.
"""
from __future__ import annotations

import logging as _logging
import os
import sys
import time
import urllib.error
import urllib.request

from chem_agent.logging_setup import setup as setup_logging

log = setup_logging()
log.info("=" * 60)
log.info("chem-agent server starting")
log.info(f"Python: {sys.version.split()[0]}")
log.info(f"Working directory: {os.getcwd()}")
log.info("=" * 60)

os.environ.setdefault("CHEM_AGENT_OFFLINE", "1")

HOST = "127.0.0.1"
PORT = 8000


def _is_our_server_alive() -> bool:
    """True, если на порту отвечает наш /health с признаком offline."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=2) as r:
            body = r.read().decode("utf-8", errors="replace")
            return '"offline"' in body or "offline" in body
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return False


def _is_port_busy() -> bool:
    """True, если порт вообще слушается кем-то."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1.0)
        return s.connect_ex((HOST, PORT)) == 0
    finally:
        s.close()


def ensure_port_available() -> None:
    """Проверяем порт перед запуском.

    Логика:
      - порт свободен                  -> ок
      - порт занят нашим сервером      -> предупреждаем, просим закрыть
      - порт занят посторонним         -> предупреждаем, выходим
    """
    if not _is_port_busy():
        return

    if _is_our_server_alive():
        msg = (
            f"\n[!] Порт {PORT} занят работающим chem-agent.\n"
            f"    Пожалуйста, закройте предыдущее окно сервера (Ctrl+C)\n"
            f"    и запустите run_server.bat заново.\n"
        )
        print(msg)
        log.warning("Port %d busy by our own server", PORT)
        sys.exit(1)

    msg = (
        f"\n[!] Порт {PORT} занят посторонним процессом.\n"
        f"    Мы его НЕ трогаем.\n"
        f"    Либо закройте его вручную, либо смените PORT в run_server.py.\n"
    )
    print(msg)
    log.error("Port %d busy by foreign process", PORT)
    sys.exit(1)


def main() -> None:
    print("=" * 60)
    print("  chem-agent — локальный предсказатель реакций")
    print(f"  Сервер: http://{HOST}:{PORT}/")
    print("  Для остановки нажмите Ctrl+C")
    print("=" * 60)

    ensure_port_available()

    # Логи uvicorn и его дочерних логгеров — в тот же файл
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = _logging.getLogger(name)
        for h in log.handlers:
            lg.addHandler(h)
        lg.setLevel(_logging.INFO)
        lg.propagate = False

    import uvicorn  # type: ignore
    from chem_agent.api.server import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
"""Launcher: starts local chem-agent server and opens browser."""
import logging as _logging
import os
import sys
import threading
import time
import webbrowser

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


def open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}/")


def main():
    print("=" * 60)
    print("  chem-agent — локальный предсказатель реакций")
    print(f"  Откройте http://{HOST}:{PORT}/ в браузере")
    print("  Для остановки нажмите Ctrl+C")
    print("=" * 60)
    
     # Логи uvicorn и его дочерних логгеров — в тот же файл
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = _logging.getLogger(name)
        for h in log.handlers:
            lg.addHandler(h)
        lg.setLevel(_logging.INFO)
        lg.propagate = False

    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn  # type: ignore
    from chem_agent.api.server import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
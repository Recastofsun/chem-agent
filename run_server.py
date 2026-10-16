"""Launcher: starts local chem-agent server and opens browser."""
import os
import sys
import threading
import time
import webbrowser

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

    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    from chem_agent.api.server import app
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
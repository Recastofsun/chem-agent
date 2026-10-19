"""
Chem-Agent v2.0 — Desktop launcher (PyWebView).
Открывает нативное окно Windows с WebView2. Без HTTP-сервера и браузера.
"""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("chem-agent")


def resource_path(rel: str) -> Path:
    """Учитывает PyInstaller one-file (_MEIPASS) и обычный запуск."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) / rel if base else Path(__file__).parent / rel


def show_webview2_error(details: str = ""):
    msg = (
        "Chem-Agent требует Microsoft Edge WebView2 Runtime.\n\n"
        "Установите Evergreen Bootstrapper:\n"
        "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
        "Для полностью офлайн-поставки используйте Fixed Version Runtime "
        "и переменную окружения WEBVIEW2_BROWSER_EXECUTABLE_FOLDER.\n\n"
        f"Детали: {details}"
    )
    log.error(msg)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Chem-Agent — WebView2 не найден", 0x10)
            return
        except Exception:
            pass
    print(msg, file=sys.stderr)


def main() -> int:
    try:
        import webview
    except ImportError:
        log.error("Не установлен pywebview. Выполните: pip install pywebview pythonnet")
        return 3

    from chem_agent.api.bridge import Bridge

    index_html = resource_path("static/index.html")
    if not index_html.exists():
        log.error("Не найден static/index.html: %s", index_html)
        return 4

    bridge = Bridge()
    window = webview.create_window(
        title="Chem-Agent 2.0",
        url=str(index_html),
        js_api=bridge,
        width=1280,
        height=820,
        min_size=(960, 640),
    )
    bridge.attach_window(window)

    try:
        webview.start(debug=False)
    except Exception as e:
        show_webview2_error(str(e))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
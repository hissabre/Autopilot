"""Autopilot desktop app entry point.

Starts the local API on 127.0.0.1, opens a native window (Edge WebView2 on Windows), runs the autopilot
in the background and, if enabled, keeps running in the system tray when the window is closed.
"""
import os
import platform
import secrets
import sys
import threading
from pathlib import Path

APP_NAME = "Autopilot"


def data_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


# Must be set before the engine is imported (it resolves its folders at import time).
os.environ.setdefault("AUTOPILOT_HOME", str(data_dir()))

# A windowed .exe has no console: send output to a log file so problems can be diagnosed.
if getattr(sys, "frozen", False):
    _log = open(Path(os.environ["AUTOPILOT_HOME"]) / "autopilot.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = _log

_LOCK = None


def single_instance() -> bool:
    """Only one Autopilot may run — two would send every email twice."""
    import socket
    global _LOCK
    _LOCK = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _LOCK.bind(("127.0.0.1", 47821))
        _LOCK.listen(1)
        return True
    except OSError:
        return False


def already_running_notice():
    msg = "Autopilot is already running.\n\nLook for its icon in the system tray (bottom-right, near the clock)."
    if platform.system() == "Windows":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, "Autopilot", 0x40)
    else:
        print(msg)
if getattr(sys, "frozen", False):
    sys.path.insert(0, getattr(sys, "_MEIPASS", ""))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server  # noqa: E402

from desktop.runner import Runner  # noqa: E402
from desktop.server import create_app, free_port  # noqa: E402
from engine.config import RES, Config  # noqa: E402


def start_server(runner, token):
    port = int(os.environ.get("AUTOPILOT_PORT") or free_port())
    os.environ["AUTOPILOT_LOCAL_BASE"] = f"http://127.0.0.1:{port}"
    srv = make_server("127.0.0.1", port, create_app(runner, token), threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return port


def main():
    if not single_instance():
        already_running_notice()
        return
    minimized = "--minimized" in sys.argv
    token = secrets.token_urlsafe(24)
    runner = Runner()
    port = start_server(runner, token)
    url = f"http://127.0.0.1:{port}/?t={token}"

    cfg = Config()
    runner.interval_min = int(cfg.get("interval_min", 60))
    if cfg.get("autopilot_on_launch") and cfg.get("setup_done"):
        runner.set_enabled(True)

    try:
        import webview
    except ImportError:  # dev fallback: plain browser
        import webbrowser
        print(f"pywebview not installed — opening {url} in your browser. Ctrl+C to quit.")
        webbrowser.open(url)
        threading.Event().wait()
        return

    window = webview.create_window(
        APP_NAME, url, width=1360, height=880, min_size=(1040, 680),
        background_color="#F4F3EF", hidden=minimized, text_select=True,
    )
    state = {"quitting": False, "tray": None}

    def quit_app():
        state["quitting"] = True
        if state["tray"]:
            state["tray"].stop()
        window.destroy()

    def on_closing():
        keep = Config().get("keep_running_in_tray", True)
        if keep and state["tray"] and not state["quitting"]:
            window.hide()
            return False  # cancel close — keep running in the tray
        return True

    window.events.closing += on_closing

    try:
        import pystray
        from PIL import Image

        icon_img = Image.open(RES / "desktop" / "ui" / "icon.png")

        def show(*_):
            window.show()
            window.restore()

        def toggle(*_):
            runner.set_enabled(not runner.enabled)

        menu = pystray.Menu(
            pystray.MenuItem("Open Autopilot", show, default=True),
            pystray.MenuItem(lambda _: "Pause autopilot" if runner.enabled else "Start autopilot", toggle),
            pystray.MenuItem("Run now", lambda *_: runner.run_now()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda *_: quit_app()),
        )
        tray = pystray.Icon(APP_NAME, icon_img, APP_NAME, menu)
        tray.run_detached()
        state["tray"] = tray
    except Exception as e:  # noqa: BLE001 — tray is a nice-to-have
        print("Tray unavailable:", e)

    webview.start(private_mode=False, storage_path=str(data_dir() / "webview"))


if __name__ == "__main__":
    main()

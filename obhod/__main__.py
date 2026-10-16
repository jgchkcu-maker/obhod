from __future__ import annotations

import ctypes
import logging
import logging.handlers
import os
import subprocess
import sys
import traceback
from pathlib import Path

SINGLE_INSTANCE = "obhod-single-instance"


def message_box(text, title="Обход"):
    ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def relaunch_elevated() -> bool:
    """Restart through UAC. Returns False if the user declined."""
    if getattr(sys, "frozen", False):
        exe, params, cwd = sys.executable, sys.argv[1:], Path(sys.executable).parent
    else:
        exe = sys.executable
        windowed = Path(exe).with_name("pythonw.exe")
        if windowed.exists():
            exe = str(windowed)
        params, cwd = ["-m", "obhod", *sys.argv[1:]], Path(__file__).resolve().parents[1]
    code = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(params), str(cwd), 1)
    return code > 32


def setup_logging(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(folder / "obhod.log", maxBytes=1_000_000, backupCount=3,
                                                   encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main():
    if os.name != "nt":
        print("Обход работает только в Windows")
        return 1
    if not is_admin() and "--no-elevate" not in sys.argv:
        if not relaunch_elevated():
            message_box("Для работы обхода (драйвер WinDivert) нужны права администратора.\n"
                        "Запустите программу ещё раз и нажмите «Да» в окне контроля учётных записей.")
            return 1
        return 0

    from PySide6.QtCore import Qt
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication
    from qfluentwidgets import Theme, setTheme, setThemeColor

    from obhod.controller import Controller
    from obhod.ui.main_window import MainWindow
    from obhod.ui.pages.logs import QtLogHandler

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Obhod")
    app.setQuitOnLastWindowClosed(False)

    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE)
    if probe.waitForConnected(300):
        probe.write(b"show")
        probe.flush()
        probe.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(SINGLE_INSTANCE)
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE)

    controller = Controller()
    setup_logging(controller.paths.logs)
    qt_handler = QtLogHandler()
    logging.getLogger().addHandler(qt_handler)
    logging.info("Запуск, права администратора: %s", is_admin())

    theme = controller.state.get("theme")
    setTheme({"dark": Theme.DARK, "light": Theme.LIGHT}.get(theme, Theme.AUTO))
    setThemeColor("#3b8bff")

    window = MainWindow(controller, qt_handler)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), window.show_normal()))

    def excepthook(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        logging.error("Необработанная ошибка:\n%s", text)
        window.notify("error", f"Ошибка: {value}")
    sys.excepthook = excepthook

    if not controller.state.get("start_minimized"):
        window.show()
    return app.exec()


def run():
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        text = traceback.format_exc()
        try:
            log = Path(__file__).resolve().parents[1] / ".state" / "crash.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(text, encoding="utf-8")
        except OSError:
            pass
        message_box("Обход не смог запуститься:\n\n" + text[-1500:])
        sys.exit(1)


if __name__ == "__main__":
    run()

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from qfluentwidgets import FluentIcon, FluentWindow, InfoBar, InfoBarPosition, NavigationItemPosition, SystemTrayMenu

from obhod.ui.pages.diagnostics import DiagnosticsPage
from obhod.ui.pages.home import HomePage
from obhod.ui.pages.lists import ListsPage
from obhod.ui.pages.logs import LogsPage
from obhod.ui.pages.services import ServicesPage
from obhod.ui.pages.settings import SettingsPage
from obhod.ui.pages.strategy import StrategyPage
from obhod.ui.pages.tuner import TunerPage
from obhod.ui.widgets import app_icon


class MainWindow(FluentWindow):
    def __init__(self, controller, log_handler):
        super().__init__()
        self.c = controller
        self.quitting = False
        self.setWindowTitle("Обход · YouTube, Discord, Fortnite")
        self.setWindowIcon(app_icon())
        self.resize(1080, 760)
        self.setMinimumSize(900, 640)

        self.tuner = TunerPage(controller, self.notify, self)
        self.home = HomePage(controller, lambda: self.switchTo(self.tuner), self)
        self.addSubInterface(self.home, FluentIcon.HOME, "Главная")
        self.addSubInterface(ServicesPage(controller, self.notify, self), FluentIcon.APPLICATION, "Сервисы")
        self.addSubInterface(StrategyPage(controller, self.notify, self), FluentIcon.LIBRARY, "Стратегия")
        self.addSubInterface(self.tuner, FluentIcon.ROBOT, "Автоподбор")
        self.addSubInterface(DiagnosticsPage(controller, self.notify, self), FluentIcon.SEARCH, "Диагностика")
        self.addSubInterface(ListsPage(controller, self.notify, self), FluentIcon.DOCUMENT, "Списки")
        self.addSubInterface(LogsPage(log_handler, self), FluentIcon.HISTORY, "Журнал", NavigationItemPosition.BOTTOM)
        self.addSubInterface(SettingsPage(controller, self.notify, self), FluentIcon.SETTING, "Настройки",
                             NavigationItemPosition.BOTTOM)
        self.navigationInterface.setExpandWidth(220)

        self.tray = QSystemTrayIcon(app_icon(64, False), self)
        self.tray.setToolTip("Обход")
        menu = SystemTrayMenu(parent=self)
        self.toggle_action = QAction("Включить обход", self)
        self.toggle_action.triggered.connect(self.home.toggle)
        show = QAction("Открыть", self)
        show.triggered.connect(self.show_normal)
        quit_ = QAction("Выход", self)
        quit_.triggered.connect(self.quit)
        menu.addActions([self.toggle_action, show, quit_])
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_normal() if reason == QSystemTrayIcon.Trigger else None)
        self.tray.show()

        controller.message.connect(self.notify)
        controller.statusChanged.connect(self.refresh_tray)
        controller.busyChanged.connect(lambda _: self.refresh_tray())
        self.refresh_tray()

    def notify(self, level, text):
        make = {"success": InfoBar.success, "warning": InfoBar.warning,
                "error": InfoBar.error}.get(level, InfoBar.info)
        make("", text, duration=6000 if level == "error" else 3500, position=InfoBarPosition.TOP_RIGHT,
             parent=self, isClosable=True)
        if self.isHidden() and level in {"error", "warning"}:
            self.tray.showMessage("Обход", text, QSystemTrayIcon.Warning)

    def refresh_tray(self):
        running = self.c.running
        self.tray.setIcon(app_icon(64, running))
        self.tray.setToolTip("Обход: включён" if running else "Обход: выключен")
        self.toggle_action.setText("Выключить обход" if running else "Включить обход")
        self.toggle_action.setEnabled(not self.c.busy)

    def show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit(self):
        self.quitting = True
        self.close()

    def closeEvent(self, event):
        if not self.quitting and self.c.state.get("close_to_tray"):
            event.ignore()
            self.hide()
            if not self.c.state.get("tray_hint_shown"):
                self.tray.showMessage("Обход", "Программа свёрнута в трей и продолжает работать.")
                self.c.state.update(tray_hint_shown=True)
            return
        self.c.stop_now()
        self.tray.hide()
        event.accept()
        QApplication.instance().quit()


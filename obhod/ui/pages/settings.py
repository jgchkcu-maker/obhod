from __future__ import annotations

import subprocess

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (FluentIcon, PushButton, SettingCardGroup, Theme, setTheme)

from obhod import __version__
from .base import Page
from .services import ComboCard, SwitchCard

THEMES = [("dark", "Тёмная"), ("light", "Светлая"), ("auto", "Как в системе")]


class SettingsPage(Page):
    def __init__(self, controller, notify, parent=None):
        super().__init__("settings", "Настройки", parent=parent)
        self.c, self.notify = controller, notify
        s = controller.state
        group = SettingCardGroup("Запуск", self.view)
        self.autostart = SwitchCard(FluentIcon.POWER_BUTTON, "Автозапуск с Windows",
                                    "Обход работает как служба, даже когда программа закрыта",
                                    bool(s.get("autostart")), group)
        self.autostart.switch.checkedChanged.connect(self.c.set_autostart)
        self.tray = SwitchCard(FluentIcon.MINIMIZE, "Сворачивать в трей при закрытии",
                               "Иначе закрытие окна выключит обход (если не включён автозапуск)",
                               bool(s.get("close_to_tray")), group)
        self.tray.switch.checkedChanged.connect(lambda v: s.update(close_to_tray=v))
        self.minimized = SwitchCard(FluentIcon.HIDE, "Запускать свёрнутым", "Сразу в трей",
                                    bool(s.get("start_minimized")), group)
        self.minimized.switch.checkedChanged.connect(lambda v: s.update(start_minimized=v))
        for card in (self.autostart, self.tray, self.minimized):
            group.addSettingCard(card)
        self.add(group)

        look = SettingCardGroup("Оформление", self.view)
        self.theme = ComboCard(FluentIcon.BRUSH, "Тема", "", THEMES, s.get("theme"), look)
        self.theme.combo.currentIndexChanged.connect(self.set_theme)
        look.addSettingCard(self.theme)
        self.add(look)

        row = QHBoxLayout()
        copy = PushButton(FluentIcon.COPY, "Скопировать аргументы winws", self.view)
        copy.clicked.connect(self.copy_args)
        folder = PushButton(FluentIcon.FOLDER, "Открыть папку данных", self.view)
        folder.clicked.connect(lambda: subprocess.Popen(["explorer", str(self.c.paths.state)]))
        reset = PushButton(FluentIcon.CANCEL, "Сбросить профиль", self.view)
        reset.clicked.connect(self.reset_profile)
        for b in (copy, folder, reset):
            row.addWidget(b)
        row.addStretch(1)
        self.layout_.addLayout(row)
        self.layout_.addStretch(1)
        self.c.statusChanged.connect(self.sync)

    def sync(self):
        self.autostart.switch.blockSignals(True)
        self.autostart.switch.setChecked(bool(self.c.state.get("autostart")))
        self.autostart.switch.blockSignals(False)

    def set_theme(self, *_):
        value = self.theme.value()
        self.c.state.update(theme=value)
        setTheme({"dark": Theme.DARK, "light": Theme.LIGHT}.get(value, Theme.AUTO))

    def copy_args(self):
        try:
            QGuiApplication.clipboard().setText(subprocess.list2cmdline(["winws.exe", *self.c.argv()]))
            self.notify("success", "Командная строка скопирована")
        except ValueError as exc:
            self.notify("error", str(exc))

    def reset_profile(self):
        self.c.state.update(profile=None, profile_name="Сбалансированный")
        self.c.statusChanged.emit()
        self.notify("success", f"Профиль по умолчанию · версия {__version__}")
        self.c.restart_if_running()

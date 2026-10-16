from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, FluentIcon, LargeTitleLabel, MessageBox,
                            PrimaryPushButton, PushButton)

from obhod.ui.widgets import PowerButton, ServiceCard
from .base import Page
from .guard import ensure_direct

NAMES = {"youtube": ("YouTube", FluentIcon.VIDEO), "discord": ("Discord", FluentIcon.CHAT),
         "fortnite": ("Fortnite", FluentIcon.GAME)}


class HomePage(Page):
    def __init__(self, controller, goto_tuner, parent=None):
        super().__init__("home", "Главная", parent=parent)
        self.c = controller
        hero = QWidget(self.view)
        col = QVBoxLayout(hero)
        col.setAlignment(Qt.AlignHCenter)
        col.setSpacing(8)
        self.power = PowerButton(hero)
        self.power.clicked.connect(self.toggle)
        self.title = LargeTitleLabel("Обход выключен", hero)
        self.title.setAlignment(Qt.AlignCenter)
        self.profile = CaptionLabel("", hero)
        self.profile.setAlignment(Qt.AlignCenter)
        col.addWidget(self.power, 0, Qt.AlignHCenter)
        col.addWidget(self.title)
        col.addWidget(self.profile)
        self.add(hero)
        self.layout_.addSpacing(10)

        grid_host = QWidget(self.view)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        self.cards = {}
        for i, (key, (name, icon)) in enumerate(NAMES.items()):
            self.cards[key] = ServiceCard(icon, name, grid_host)
            grid.addWidget(self.cards[key], 0, i)
        self.add(grid_host)

        row = QHBoxLayout()
        self.check = PushButton(FluentIcon.SYNC, "Проверить доступность", self.view)
        self.check.clicked.connect(self.c.probe)
        self.tune = PrimaryPushButton(FluentIcon.ROBOT, "Автоподбор стратегии", self.view)
        self.tune.clicked.connect(goto_tuner)
        row.addStretch(1)
        row.addWidget(self.check)
        row.addWidget(self.tune)
        row.addStretch(1)
        self.layout_.addLayout(row)
        note = BodyLabel("Fortnite: проверяются вход и сервисы Epic. Подключение к матчу (UDP) "
                         "можно проверить только в самой игре.", self.view)
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        note.setTextColor("#707070", "#9a9a9a")
        self.add(note)

        controller.statusChanged.connect(self.refresh)
        controller.busyChanged.connect(lambda _: self.refresh())
        controller.probed.connect(lambda _: self.refresh())
        self.refresh()

    def toggle(self):
        if self.c.running:
            self.c.stop()
            return
        ensure_direct(self.window(), self.c, "обход", self._start)

    def _start(self):
        try:
            conflicts = self.c.conflicts()
        except Exception:
            logging.getLogger("obhod").exception("Не удалось проверить другие обходы")
            conflicts = []
        stop = False
        if conflicts:
            names = ", ".join(str(x.get("name") or x["id"]) for x in conflicts)
            box = MessageBox("Запущен другой обход",
                             f"Уже работает: {names}.\nДва обхода одновременно мешают друг другу. "
                             "Остановить их и включить «Обход»?", self.window())
            box.yesButton.setText("Остановить и включить")
            box.cancelButton.setText("Отмена")
            if not box.exec():
                return
            stop = True
        self.c.start(stop_conflicts=stop)

    def refresh(self):
        running = self.c.running
        busy = self.c.busy
        self.power.setState("busy" if busy else ("on" if running else "off"))
        self.title.setText("Подождите…" if busy else ("Обход включён" if running else "Обход выключен"))
        mode = "служба автозапуска" if self.c.state.get("autostart") else "пока открыта программа"
        self.profile.setText(f"Профиль: {self.c.state.get('profile_name')} · {mode}")
        enabled = set(self.c.state.get("services"))
        for key, card in self.cards.items():
            card.setHealth(key in enabled, self.c.health[key], running)
        self.check.setEnabled(running and not busy)
        self.tune.setEnabled(not busy)

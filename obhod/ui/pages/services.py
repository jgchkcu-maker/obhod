from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import (ComboBox, FluentIcon, LineEdit, PrimaryPushButton, SettingCard,
                            SettingCardGroup, SwitchButton)

from obhod.core.strategy import port_intervals
from .base import Page

GAME_MODES = [("all", "TCP + UDP"), ("udp", "Только UDP"), ("tcp", "Только TCP"), ("none", "Выключен")]
IPSET_MODES = [("loaded", "По списку (рекомендуется)"), ("any", "Все IP (только игровые порты)"),
               ("none", "Выключен")]


class SwitchCard(SettingCard):
    def __init__(self, icon, title, content, checked, parent=None):
        super().__init__(icon, title, content, parent)
        self.switch = SwitchButton(self)
        self.switch.setOnText("Вкл")
        self.switch.setOffText("Выкл")
        self.switch.setChecked(checked)
        self.hBoxLayout.addWidget(self.switch)
        self.hBoxLayout.addSpacing(16)


class ComboCard(SettingCard):
    def __init__(self, icon, title, content, options, current, parent=None):
        super().__init__(icon, title, content, parent)
        self.options = options
        self.combo = ComboBox(self)
        for _, text in options:
            self.combo.addItem(text)
        self.combo.setCurrentIndex(next((i for i, (k, _) in enumerate(options) if k == current), 0))
        self.combo.setMinimumWidth(240)
        self.hBoxLayout.addWidget(self.combo)
        self.hBoxLayout.addSpacing(16)

    def value(self):
        return self.options[self.combo.currentIndex()][0]


class EditCard(SettingCard):
    def __init__(self, icon, title, content, text, parent=None):
        super().__init__(icon, title, content, parent)
        self.edit = LineEdit(self)
        self.edit.setText(text)
        self.edit.setFixedWidth(240)
        self.hBoxLayout.addWidget(self.edit)
        self.hBoxLayout.addSpacing(16)


class ServicesPage(Page):
    def __init__(self, controller, notify, parent=None):
        super().__init__("services", "Сервисы",
                         "Что обходить. После изменений нажмите «Применить» — если обход включён, "
                         "он перезапустится с новыми настройками.", parent)
        self.c, self.notify = controller, notify
        s = controller.state
        enabled = set(s.get("services"))
        group = SettingCardGroup("Сервисы", self.view)
        self.youtube = SwitchCard(FluentIcon.VIDEO, "YouTube", "Сайт, видео (TCP) и QUIC", "youtube" in enabled, group)
        self.discord = SwitchCard(FluentIcon.CHAT, "Discord", "Сайт, клиент и голосовые каналы", "discord" in enabled, group)
        self.fortnite = SwitchCard(FluentIcon.GAME, "Fortnite", "Сервисы Epic и игровой трафик", "fortnite" in enabled, group)
        for card in (self.youtube, self.discord, self.fortnite):
            group.addSettingCard(card)
        self.add(group)

        games = SettingCardGroup("Игры (Game Filter)", self.view)
        self.game_mode = ComboCard(FluentIcon.GAME, "Game Filter", "Какой игровой трафик (порты ≥1024) обрабатывать",
                                   GAME_MODES, s.get("game_mode"), games)
        self.ipset_mode = ComboCard(FluentIcon.GLOBE, "IPSet", "«Все IP» действует только на игровые порты, сайты не ломаются",
                                    IPSET_MODES, s.get("ipset_mode"), games)
        self.tcp = EditCard(FluentIcon.CONNECT, "Игровые порты TCP", "Например 1024-65535", s.get("tcp_ports"), games)
        self.udp = EditCard(FluentIcon.CONNECT, "Игровые порты UDP", "Например 1024-65535", s.get("udp_ports"), games)
        for card in (self.game_mode, self.ipset_mode, self.tcp, self.udp):
            games.addSettingCard(card)
        self.add(games)

        row = QHBoxLayout()
        apply = PrimaryPushButton(FluentIcon.ACCEPT, "Применить", self.view)
        apply.clicked.connect(self.apply)
        row.addStretch(1)
        row.addWidget(apply)
        self.layout_.addLayout(row)

    def apply(self):
        services = [k for k, card in (("youtube", self.youtube), ("discord", self.discord),
                                      ("fortnite", self.fortnite)) if card.switch.isChecked()]
        if not services:
            self.notify("warning", "Включите хотя бы один сервис")
            return
        tcp, udp = self.tcp.edit.text().strip(), self.udp.edit.text().strip()
        try:
            port_intervals(tcp, 1024)
            port_intervals(udp, 1024)
        except ValueError as exc:
            self.notify("error", str(exc))
            return
        self.c.state.update(services=services, game_mode=self.game_mode.value(),
                            ipset_mode=self.ipset_mode.value(), tcp_ports=tcp, udp_ports=udp)
        try:
            self.c.argv()
        except ValueError as exc:
            self.notify("error", str(exc))
            return
        self.c.statusChanged.emit()
        if self.c.running:
            self.c.start(then_probe=True)
        else:
            self.notify("success", "Настройки сохранены")


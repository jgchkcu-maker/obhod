from __future__ import annotations

import subprocess

from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import FluentIcon, PlainTextEdit, PrimaryPushButton, PushButton, SettingCardGroup, StrongBodyLabel

from .base import Page
from .services import ComboCard

FROM_BASE = "base"


class StrategyPage(Page):
    """Manual choice: a Flowseal strategy as the base plus Fortnite blocks on top."""

    def __init__(self, controller, notify, parent=None):
        super().__init__("strategy", "Стратегия",
                         "Выберите стратегию вручную, как в .bat-файлах Flowseal. Основа отвечает за YouTube и "
                         "Discord, а для Fortnite можно отдельно подобрать вход Epic и игровой трафик. "
                         "Если стратегия не помогает — пробуйте следующую или запустите автоподбор.", parent)
        self.c, self.notify = controller, notify
        catalog = controller.catalog
        strategies = sorted(catalog.strategies, key=lambda s: (s.id != "general", s.name))
        self.bases = {s.id: s for s in strategies}
        custom = {cat: [b for b in catalog.custom if b.category == cat] for cat in ("epic-tcp", "game-udp", "game-tcp")}
        saved = controller.state.get("manual") or {}

        group = SettingCardGroup("Основа (YouTube + Discord)", self.view)
        self.base = ComboCard(FluentIcon.LIBRARY, "Стратегия Flowseal", "Те же 22 варианта, что и general*.bat",
                              [(s.id, s.name) for s in strategies], saved.get("base", "general"), group)
        group.addSettingCard(self.base)
        self.add(group)

        fortnite = SettingCardGroup("Fortnite", self.view)
        self.epic = ComboCard(FluentIcon.PEOPLE, "Вход и сервисы Epic", "TCP 443 к доменам Epic",
                              [(b.id, f"{b.id} · {b.label}") for b in custom["epic-tcp"]], saved.get("epic", "E2"), fortnite)
        self.udp = ComboCard(FluentIcon.GAME, "Игровой трафик UDP", "Соединение с сервером матча",
                             [(FROM_BASE, "Из стратегии Flowseal")] + [(b.id, f"{b.id} · {b.label}") for b in custom["game-udp"]],
                             saved.get("udp", "U1"), fortnite)
        self.tcp = ComboCard(FluentIcon.CONNECT, "Игровой трафик TCP", "Порты выше 1024",
                             [(FROM_BASE, "Из стратегии Flowseal")] + [(b.id, f"{b.id} · {b.label}") for b in custom["game-tcp"]],
                             saved.get("tcp", "T1"), fortnite)
        for card in (self.epic, self.udp, self.tcp):
            fortnite.addSettingCard(card)
        self.add(fortnite)

        row = QHBoxLayout()
        apply = PrimaryPushButton(FluentIcon.ACCEPT, "Применить стратегию", self.view)
        apply.clicked.connect(self.apply)
        tuned = PushButton(FluentIcon.ROBOT, "Вернуть «Мой профиль» из автоподбора", self.view)
        tuned.clicked.connect(self.restore_tuned)
        tuned.setEnabled(bool(controller.state.get("tuned_profile")))
        self.tuned = tuned
        row.addWidget(apply)
        row.addWidget(tuned)
        row.addStretch(1)
        self.layout_.addLayout(row)

        self.add(StrongBodyLabel("Командная строка winws", self.view))
        self.preview = PlainTextEdit(self.view)
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(170)
        self.add(self.preview)
        for card in (self.base, self.epic, self.udp, self.tcp):
            card.combo.currentIndexChanged.connect(self.update_preview)
        controller.statusChanged.connect(lambda: self.tuned.setEnabled(bool(controller.state.get("tuned_profile"))))
        self.update_preview()

    def selection(self):
        base = self.bases[self.base.value()]
        blocks = [b for b in base.blocks if b.category not in {"game-tcp", "game-udp"}]
        for card, category in ((self.tcp, "game-tcp"), (self.udp, "game-udp")):
            if card.value() == FROM_BASE:
                blocks += [b for b in base.blocks if b.category == category]
            else:
                blocks.append(self.c.catalog.blocks[card.value()])
        blocks.append(self.c.catalog.blocks[self.epic.value()])
        name = f"{base.name} · {self.epic.value()}"
        extra = [c.value() for c in (self.udp, self.tcp) if c.value() != FROM_BASE]
        if extra:
            name += " · " + " · ".join(extra)
        return blocks, name

    def update_preview(self, *_):
        blocks, _ = self.selection()
        try:
            self.preview.setPlainText(subprocess.list2cmdline(["winws.exe", *self.c.argv(blocks)]))
        except ValueError as exc:
            self.preview.setPlainText(f"Ошибка: {exc}")

    def apply(self):
        blocks, name = self.selection()
        try:
            self.c.argv(blocks)
        except ValueError as exc:
            self.notify("error", str(exc))
            return
        self.c.state.update(profile=[b.id for b in blocks], profile_name=name,
                            manual={"base": self.base.value(), "epic": self.epic.value(),
                                    "udp": self.udp.value(), "tcp": self.tcp.value()})
        self.c.statusChanged.emit()
        if self.c.running:
            self.c.start()
        else:
            self.notify("success", f"Выбрана стратегия «{name}». Включите обход на главной")

    def restore_tuned(self):
        self.c.state.update(profile=self.c.state.get("tuned_profile"), profile_name="Мой профиль")
        self.c.statusChanged.emit()
        if self.c.running:
            self.c.start()
        else:
            self.notify("success", "Выбран «Мой профиль»")

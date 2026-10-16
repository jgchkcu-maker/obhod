from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHBoxLayout
from qfluentwidgets import ComboBox, FluentIcon, PlainTextEdit, PrimaryPushButton, PushButton

from obhod.core.lists import EDITABLE
from .base import Page

TITLES = {"list-general-user.txt": "Свои домены для обхода",
          "list-epic-user.txt": "Свои домены Epic / Fortnite",
          "list-exclude-user.txt": "Домены-исключения (не трогать)",
          "ipset-exclude-user.txt": "IP-исключения",
          "ipset-fortnite.txt": "IP игровых серверов Fortnite"}


class _Relay(QObject):
    ready = Signal(str, str)


class ListsPage(Page):
    def __init__(self, controller, notify, parent=None):
        super().__init__("lists", "Списки",
                         "Одна запись на строку. Поддомены включаются автоматически. "
                         "Обновление подтягивает свежие списки Flowseal, ваши правки не трогает.", parent)
        self.c, self.notify = controller, notify
        self.relay = _Relay()
        self.relay.ready.connect(lambda level, text: (self.notify(level, text), self.c.restart_if_running()
                                                      if level == "success" else None))
        row = QHBoxLayout()
        self.combo = ComboBox(self.view)
        for name in EDITABLE:
            self.combo.addItem(TITLES.get(name, name), userData=name)
        self.combo.setMinimumWidth(320)
        self.combo.currentIndexChanged.connect(self.load)
        save = PrimaryPushButton(FluentIcon.SAVE, "Сохранить", self.view)
        save.clicked.connect(self.save)
        update = PushButton(FluentIcon.DOWNLOAD, "Обновить списки Flowseal", self.view)
        update.clicked.connect(self.update_lists)
        row.addWidget(self.combo)
        row.addWidget(save)
        row.addStretch(1)
        row.addWidget(update)
        self.layout_.addLayout(row)
        self.edit = PlainTextEdit(self.view)
        self.edit.setMinimumHeight(420)
        self.add(self.edit, 1)
        self.load()

    def current(self):
        return self.combo.currentData() or EDITABLE[self.combo.currentIndex()]

    def load(self, *_):
        path = self.c.paths.lists / self.current()
        self.edit.setPlainText(path.read_text(encoding="utf-8-sig") if path.exists() else "")

    def save(self):
        try:
            self.c.lists.save(self.current(), self.edit.toPlainText())
        except ValueError as exc:
            self.notify("error", str(exc))
            return
        self.load()
        self.notify("success", "Список сохранён")
        self.c.restart_if_running()

    def update_lists(self):
        def work():
            try:
                counts = self.c.lists.update()
                self.relay.ready.emit("success", "Списки обновлены: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
            except Exception as exc:
                self.relay.ready.emit("error", f"Не удалось обновить списки: {exc}")
        threading.Thread(target=work, daemon=True).start()

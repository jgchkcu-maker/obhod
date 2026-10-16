from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (BodyLabel, CaptionLabel, CardWidget, FluentIcon, IconWidget, MessageBox, PrimaryPushButton,
                            PushButton, StrongBodyLabel)

from obhod.core import diagnostics
from obhod.core.conflicts import stop_conflict
from .base import Page

ICONS = {"ok": FluentIcon.ACCEPT, "warning": FluentIcon.INFO, "error": FluentIcon.CLOSE,
         "info": FluentIcon.INFO, "unknown": FluentIcon.HELP}


class _Relay(QObject):
    ready = Signal(object, object)


class CheckCard(CardWidget):
    def __init__(self, item, on_fix, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(12)
        icon = IconWidget(ICONS.get(item["status"], FluentIcon.HELP), self)
        icon.setFixedSize(20, 20)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(StrongBodyLabel(item["title"], self))
        detail = CaptionLabel(item["detail"][:400], self)
        detail.setWordWrap(True)
        detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(detail)
        row.addWidget(icon, 0, Qt.AlignTop)
        row.addLayout(col, 1)
        if item.get("fix"):
            button = PushButton("Исправить", self)
            button.clicked.connect(lambda: on_fix(item["fix"]))
            row.addWidget(button)


class DiagnosticsPage(Page):
    def __init__(self, controller, notify, parent=None):
        super().__init__("diagnostics", "Диагностика",
                         "Проверки из service.bat Flowseal: то, что чаще всего мешает обходу.", parent)
        self.c, self.notify = controller, notify
        self.relay = _Relay()
        self.relay.ready.connect(self.show_results)
        row = QHBoxLayout()
        self.run_btn = PrimaryPushButton(FluentIcon.SEARCH, "Запустить проверку", self.view)
        self.run_btn.clicked.connect(self.run)
        self.conflicts_btn = PushButton(FluentIcon.DELETE, "Остановить другие обходы", self.view)
        self.conflicts_btn.clicked.connect(self.stop_conflicts)
        self.tunnels_btn = PushButton(FluentIcon.WIFI, "Отключить VPN / туннели", self.view)
        self.tunnels_btn.clicked.connect(self.close_tunnels)
        row.addWidget(self.run_btn)
        row.addWidget(self.tunnels_btn)
        row.addWidget(self.conflicts_btn)
        row.addStretch(1)
        self.layout_.addLayout(row)
        self.hint = BodyLabel("", self.view)
        self.add(self.hint)
        self.cards = []

    def _thread(self, fn):
        def work():
            try:
                self.relay.ready.emit(fn(), None)
            except Exception as exc:
                self.relay.ready.emit(None, exc)
        threading.Thread(target=work, daemon=True).start()

    def run(self):
        self.run_btn.setEnabled(False)
        self.hint.setText("Проверяю…")
        pid = self.c.runner.process.pid if self.c.runner.running else None
        self._thread(lambda: diagnostics.diagnose(self.c.paths, pid))

    def show_results(self, items, error):
        self.run_btn.setEnabled(True)
        if error:
            self.hint.setText("")
            self.notify("error", f"Диагностика: {error}")
            return
        if isinstance(items, str):
            self.notify("success", items)
            self.run()
            return
        for card in self.cards:
            card.deleteLater()
        self.cards = [self.add(CheckCard(item, self.fix, self.view)) for item in items]
        bad = sum(i["status"] in {"warning", "error"} for i in items)
        self.hint.setText("Проблем не найдено" if not bad else f"Обратите внимание: {bad}")

    def fix(self, key):
        self._thread(lambda: (diagnostics.fix(key), "Исправлено")[1])

    def close_tunnels(self):
        from obhod.core.tunnels import find_clients
        clients = find_clients()
        if not clients:
            self.notify("info", "VPN- и прокси-клиенты не найдены")
            return
        text = "Будут закрыты:\n" + "\n".join(c.describe() for c in clients)
        text += "\n\nСлужбы остановятся до перезагрузки, их автозапуск не меняется."
        box = MessageBox("Отключить туннели?", text, self.window())
        box.yesButton.setText("Отключить")
        box.cancelButton.setText("Отмена")
        if box.exec():
            self.c.close_tunnels(then=lambda _: self.run())

    def stop_conflicts(self):
        def work():
            items = self.c.conflicts()
            for item in items:
                stop_conflict(item)
            return f"Остановлено: {len(items)}" if items else "Других обходов не найдено"
        self._thread(work)

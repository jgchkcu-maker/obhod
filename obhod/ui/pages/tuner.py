from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHBoxLayout, QHeaderView, QTableWidgetItem
from qfluentwidgets import (BodyLabel, FluentIcon, PrimaryPushButton, ProgressBar, PushButton,
                            TableWidget)

from obhod.tester.probes import ProbeResult
from .base import Page
from .guard import ensure_direct

COLUMNS = ["Стратегия", "YouTube", "Discord", "Fortnite (Epic)", "Время", "Ошибка"]


class TunerPage(Page):
    def __init__(self, controller, notify, parent=None):
        super().__init__("tuner", "Автоподбор",
                         "Перебирает все стратегии Flowseal и варианты для Epic (около 6–7 минут) и собирает "
                         "лучший блок для каждого сервиса. Пока идёт подбор, интернет может моргать.", parent)
        self.c, self.notify = controller, notify
        row = QHBoxLayout()
        self.start = PrimaryPushButton(FluentIcon.PLAY, "Начать подбор", self.view)
        self.cancel = PushButton(FluentIcon.CLOSE, "Отменить", self.view)
        self.cancel.setEnabled(False)
        self.start.clicked.connect(self.run)
        self.cancel.clicked.connect(self.c.cancel_tuning)
        row.addWidget(self.start)
        row.addWidget(self.cancel)
        row.addStretch(1)
        self.layout_.addLayout(row)
        self.progress = ProgressBar(self.view)
        self.progress.setValue(0)
        self.add(self.progress)
        self.status = BodyLabel("Готов к запуску", self.view)
        self.status.setWordWrap(True)
        self.add(self.status)
        self.table = TableWidget(self.view)
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setMinimumHeight(380)
        self.add(self.table, 1)
        controller.tunerRound.connect(self.on_round)
        controller.tunerFinished.connect(self.on_finished)
        controller.busyChanged.connect(lambda busy: self.start.setEnabled(not busy))

    def run(self):
        ensure_direct(self.window(), self.c, "автоподбор", self._run)

    def _run(self):
        self.table.setRowCount(0)
        self.progress.setValue(0)
        if self.c.tune():
            self.cancel.setEnabled(True)
            self.status.setText("Замер без обхода…")

    def on_round(self, row, index, total):
        results = [ProbeResult(**r) for r in row["results"]]
        self.progress.setValue(int(index * 100 / total))
        self.status.setText(f"{index} из {total}: {row['name']}")
        r = self.table.rowCount()
        self.table.insertRow(r)
        values = [row["name"], *(str(self.c.service_score(results, s)) for s in ("youtube", "discord", "fortnite")),
                  f"{row['elapsed']} с", row["error"][:160]]
        for col, value in enumerate(values):
            self.table.setItem(r, col, QTableWidgetItem(value))
        self.table.scrollToBottom()

    def on_finished(self, result):
        self.cancel.setEnabled(False)
        if isinstance(result, Exception):
            self.status.setText(str(result))
            self.notify("warning" if isinstance(result, InterruptedError) else "error", str(result))
            return
        self.progress.setValue(100)
        self.status.setText(f"{result.reason} ({result.elapsed} с)")
        if result.verified:
            self.notify("success", "Готово: «Мой профиль» сохранён и будет использоваться при включении")
        else:
            self.notify("warning", "Подходящую комбинацию найти не удалось, оставлен прежний профиль")

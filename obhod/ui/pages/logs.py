from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from qfluentwidgets import PlainTextEdit

from .base import Page


class QtLogHandler(logging.Handler, QObject):
    line = Signal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            self.line.emit(self.format(record))
        except RuntimeError:
            pass


class LogsPage(Page):
    def __init__(self, handler: QtLogHandler, parent=None):
        super().__init__("logs", "Журнал", "События программы и вывод winws.", parent)
        self.text = PlainTextEdit(self.view)
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(520)
        self.text.setMaximumBlockCount(3000)
        self.add(self.text, 1)
        handler.line.connect(self.text.appendPlainText)

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, ScrollArea, TitleLabel


class Page(ScrollArea):
    """Scrollable page with a title, subtitle and a vertical content layout."""

    def __init__(self, object_name: str, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.layout_ = QVBoxLayout(self.view)
        self.layout_.setContentsMargins(36, 28, 36, 28)
        self.layout_.setSpacing(12)
        self.layout_.setAlignment(Qt.AlignTop)
        self.layout_.addWidget(TitleLabel(title, self.view))
        if subtitle:
            label = BodyLabel(subtitle, self.view)
            label.setWordWrap(True)
            label.setTextColor("#606060", "#a0a0a0")
            self.layout_.addWidget(label)
            self.layout_.addSpacing(6)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.enableTransparentBackground()

    def add(self, widget, stretch=0):
        self.layout_.addWidget(widget, stretch)
        return widget

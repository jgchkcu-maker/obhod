from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, CardWidget, IconWidget, StrongBodyLabel, isDarkTheme

ON = QColor("#2ecc8f")
OFF = QColor("#8a8f98")
BUSY = QColor("#f0b429")
FAIL = QColor("#ff5c5c")


def app_icon(size=256, active=True) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QRadialGradient(QPointF(size * .35, size * .3), size * .8)
    grad.setColorAt(0, QColor("#4fd1ff" if active else "#9aa3ad"))
    grad.setColorAt(1, QColor("#3b5bff" if active else "#4a5058"))
    p.setBrush(grad)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(size * .04, size * .04, size * .92, size * .92))
    pen = QPen(QColor("white"), size * .085, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    r = QRectF(size * .27, size * .27, size * .46, size * .46)
    p.drawArc(r, 120 * 16, 300 * 16)
    p.drawLine(QPointF(size / 2, size * .2), QPointF(size / 2, size * .47))
    p.end()
    return QIcon(pix)


class PowerButton(QWidget):
    """Big round toggle with an animated glow ring."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self.setCursor(Qt.PointingHandCursor)
        self._state = "off"          # off | on | busy
        self._glow = 0.0
        self._spin = 0.0
        self._hover = False
        self.glowAnim = QPropertyAnimation(self, b"glow", self)
        self.glowAnim.setDuration(450)
        self.glowAnim.setEasingCurve(QEasingCurve.OutCubic)
        self.spinAnim = QPropertyAnimation(self, b"spin", self)
        self.spinAnim.setStartValue(0.0)
        self.spinAnim.setEndValue(360.0)
        self.spinAnim.setDuration(1100)
        self.spinAnim.setLoopCount(-1)

    def getGlow(self):
        return self._glow

    def setGlow(self, value):
        self._glow = value
        self.update()

    def getSpin(self):
        return self._spin

    def setSpin(self, value):
        self._spin = value
        self.update()

    glow = Property(float, getGlow, setGlow)
    spin = Property(float, getSpin, setSpin)

    def setState(self, state: str):
        if state == self._state:
            return
        self._state = state
        self.glowAnim.stop()
        self.glowAnim.setStartValue(self._glow)
        self.glowAnim.setEndValue(1.0 if state == "on" else 0.0)
        self.glowAnim.start()
        if state == "busy":
            self.spinAnim.start()
        else:
            self.spinAnim.stop()
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()) and self._state != "busy":
            self.clicked.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        c = QPointF(w / 2, w / 2)
        dark = isDarkTheme()
        color = {"on": ON, "busy": BUSY}.get(self._state, OFF)

        # outer glow
        if self._glow > 0:
            g = QRadialGradient(c, w / 2)
            glow = QColor(ON)
            glow.setAlphaF(.45 * self._glow)
            g.setColorAt(.55, glow)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g)
            p.setPen(Qt.NoPen)
            p.drawEllipse(c, w / 2, w / 2)

        # disc
        radius = w * .34 + (3 if self._hover else 0)
        base = QColor("#23262d" if dark else "#f4f6fa")
        disc = QRadialGradient(QPointF(c.x(), c.y() - radius * .4), radius * 1.6)
        disc.setColorAt(0, base.lighter(135 if dark else 102))
        disc.setColorAt(1, base)
        p.setBrush(disc)
        p.setPen(QPen(QColor(255, 255, 255, 20) if dark else QColor(0, 0, 0, 25), 1))
        p.drawEllipse(c, radius, radius)

        # ring
        ring = QRectF(c.x() - radius - 9, c.y() - radius - 9, (radius + 9) * 2, (radius + 9) * 2)
        track = QColor(color)
        track.setAlphaF(.25)
        p.setPen(QPen(track, 5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(ring)
        p.setPen(QPen(color, 5, Qt.SolidLine, Qt.RoundCap))
        if self._state == "busy":
            p.drawArc(ring, int(-self._spin * 16), 90 * 16)
        elif self._state == "on":
            p.drawEllipse(ring)

        # power glyph
        s = radius * .9
        glyph = QRectF(c.x() - s / 2, c.y() - s / 2, s, s)
        p.setPen(QPen(color, 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(glyph, 125 * 16, 290 * 16)
        p.drawLine(QPointF(c.x(), c.y() - s * .62), QPointF(c.x(), c.y() - s * .12))
        p.end()


class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self.color = OFF

    def setColor(self, color: QColor):
        self.color = color
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        halo = QColor(self.color)
        halo.setAlphaF(.3)
        p.setBrush(halo)
        p.drawEllipse(0, 0, 12, 12)
        p.setBrush(self.color)
        p.drawEllipse(3, 3, 6, 6)
        p.end()


class ServiceCard(CardWidget):
    def __init__(self, icon, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(78)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(14)
        self.icon = IconWidget(icon, self)
        self.icon.setFixedSize(28, 28)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = StrongBodyLabel(title, self)
        self.detail = CaptionLabel("Не проверено", self)
        text.addWidget(self.title)
        text.addWidget(self.detail)
        self.dot = StatusDot(self)
        layout.addWidget(self.icon)
        layout.addLayout(text, 1)
        layout.addWidget(self.dot)

    def setHealth(self, enabled: bool, health: dict, running: bool):
        if not enabled:
            self.dot.setColor(OFF)
            self.detail.setText("Выключен в «Сервисах»")
        elif health["status"] == "ok":
            self.dot.setColor(ON)
            self.detail.setText(f"Доступен · {health['latency']} мс")
        elif health["status"] == "fail":
            self.dot.setColor(FAIL)
            self.detail.setText("Недоступен — попробуйте автоподбор")
        else:
            self.dot.setColor(BUSY if running else OFF)
            self.detail.setText("Не проверено" if running else "Обход выключен")


"""Interactive Qt drawing of the configurable controls on the G995W."""
from math import sin, tau

from PyQt6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QTimer, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PyQt6.QtWidgets import QPushButton, QWidget

from .protocol import BUTTONS

ACCENT = "#d7fa79"
# Marker and connector coordinates, in the same space as the mouse silhouette.
POINTS = (
    (70, 92, 141, 105), (318, 92, 247, 105), (194, 28, 194, 96),
    (319, 180, 194, 164), (52, 172, 107, 175), (52, 224, 106, 210),
)


def outline(start, curves):
    path = QPainterPath(QPointF(*start))
    for curve in curves:
        path.cubicTo(*curve)
    path.closeSubpath()
    return path


class MouseMap(QWidget):
    selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(270, 286)
        self.selection = 0
        self.interactive = False
        self.halo = 0.0
        self.mode = 0
        self.phase = 0
        self.color = QColor(ACCENT)
        self.brightness = 1.0
        self.pins = []
        for index, name in enumerate(BUTTONS.values()):
            pin = QPushButton(str(index + 1), self)
            pin.setProperty("mapPin", True)
            pin.setCheckable(True)
            pin.setCursor(Qt.CursorShape.PointingHandCursor)
            pin.setAccessibleName(name)
            pin.setToolTip(name)
            pin.clicked.connect(lambda checked, i=index: self.selected.emit(i))
            self.pins.append(pin)
        self.transition = QVariantAnimation(self)
        self.transition.setStartValue(0.0)
        self.transition.setEndValue(1.0)
        self.transition.setDuration(240)
        self.transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.transition.valueChanged.connect(self.set_halo)
        self.timer = QTimer(self, interval=40)
        self.timer.timeout.connect(self.advance)
        self.set_interactive(False)

    def set_halo(self, value):
        self.halo = value
        self.update()

    def set_selection(self, index):
        self.selection = index
        for i, pin in enumerate(self.pins):
            pin.setChecked(i == index)
        if self.interactive:
            self.transition.stop()
            self.transition.start()
        self.update()

    def set_interactive(self, enabled):
        self.interactive = enabled
        for pin in self.pins:
            pin.setVisible(enabled)
        if enabled:
            self.set_selection(self.selection)
        self.update()

    def set_light(self, mode, color, brightness):
        self.mode = mode
        self.color = QColor("#" + color)
        self.brightness = 0.18 + 0.82 * brightness / 8
        if mode in (2, 3, 4, 6):
            if not self.timer.isActive() and self.isVisible():
                self.timer.start()
        else:
            self.timer.stop()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self.mode in (2, 3, 4, 6):
            self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def advance(self):
        self.phase = (self.phase + 0.026) % 1
        self.update()

    def canvas(self):
        scale = min(self.width() / 388, self.height() / 390)
        return scale, (self.width() - 388 * scale) / 2, (self.height() - 390 * scale) / 2

    def resizeEvent(self, event):
        super().resizeEvent(event)
        scale, x, y = self.canvas()
        for pin, (px, py, _, _) in zip(self.pins, POINTS):
            pin.setGeometry(round(x + px * scale) - 15, round(y + py * scale) - 15, 30, 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale, x, y = self.canvas()
        painter.translate(x, y)
        painter.scale(scale, scale)

        for gy in range(24, 380, 16):
            for gx in range(18, 380, 16):
                radius = ((gx - 194) / 197) ** 2 + ((gy - 204) / 190) ** 2
                color = QColor("#8c978b")
                color.setAlphaF(max(0, 0.22 * (1 - radius)))
                painter.setPen(color)
                painter.drawPoint(QPointF(gx, gy))

        shadow = QRadialGradient(194, 212, 154)
        shadow.setColorAt(0, QColor("#050606"))
        shadow.setColorAt(1, QColor(5, 6, 6, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(QRectF(39, 52, 310, 322))

        shell = outline((194, 59), (
            (138, 56, 107, 69, 103, 111), (94, 163, 111, 199, 101, 244),
            (96, 300, 130, 347, 194, 349), (255, 348, 287, 311, 287, 254),
            (284, 211, 291, 157, 285, 113), (281, 71, 250, 57, 194, 59),
        ))
        rim = QLinearGradient(100, 75, 280, 321)
        rim.setColorAt(0, QColor("#566057"))
        rim.setColorAt(0.45, QColor("#292f2a"))
        rim.setColorAt(1, QColor("#141817"))
        surface = QRadialGradient(163, 134, 245)
        surface.setColorAt(0, QColor("#383e38"))
        surface.setColorAt(0.54, QColor("#262c28"))
        surface.setColorAt(1, QColor("#141817"))
        painter.setPen(QPen(rim, 2.4))
        painter.setBrush(surface)
        painter.drawPath(shell)

        left = outline((190, 65), (
            (153, 61, 115, 71, 110, 108), (107, 127, 106, 144, 110, 163),
            (143, 159, 166, 152, 183, 140), (187, 136, 190, 130, 190, 124),
            (190, 103, 190, 81, 190, 65),
        ))
        right = outline((199, 65), (
            (237, 61, 273, 74, 279, 110), (282, 129, 283, 146, 281, 163),
            (247, 159, 224, 152, 207, 140), (202, 135, 199, 130, 199, 124),
            (199, 103, 199, 81, 199, 65),
        ))
        painter.setPen(QPen(QColor("#101311"), 2.5))
        painter.drawPath(left)
        painter.drawPath(right)

        def inset(rect, radius, fill):
            painter.setPen(QPen(QColor("#111512"), 1.5))
            painter.setBrush(QColor(fill))
            painter.drawRoundedRect(QRectF(*rect), radius, radius)

        inset((178, 78, 32, 64), 14, "#151916")
        inset((184, 85, 20, 47), 8, "#3d4640")
        painter.setPen(QPen(QColor("#1b201c"), 2))
        for gy in range(92, 129, 5):
            painter.drawLine(QPointF(187, gy), QPointF(201, gy))
        inset((183, 154, 22, 19), 7, "#424c43")
        inset((100, 160, 16, 30), 7, "#4a554a")
        inset((99, 196, 16, 28), 7, "#3d463e")

        if self.mode:
            self.paint_light(painter)

        if self.interactive:
            self.paint_connections(painter)

    def paint_light(self, painter):
        color = QColor(self.color)
        if self.mode == 2:
            color = QColor("#ef5276")
        elif self.mode in (3, 4):
            color = QColor.fromHsvF(self.phase, 0.74, 1)
        strength = self.brightness
        if self.mode in (2, 4, 6):
            strength *= 0.53 + 0.47 * sin(tau * self.phase)
        # Small rear lighting detail, separate from the button hit targets.
        edge = QPainterPath(QPointF(151, 320))
        edge.cubicTo(171, 335, 218, 335, 237, 320)
        for width, opacity in ((15, 0.06), (9, 0.12), (4, 0.33), (2, 1.0)):
            color.setAlphaF(opacity * strength)
            painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(edge)

    def paint_connections(self, painter):
        for i in sorted(range(len(POINTS)), key=lambda index: index == self.selection):
            px, py, tx, ty = POINTS[i]
            active = i == self.selection
            if active:
                color = QColor(ACCENT)
                color.setAlphaF(0.48 + 0.52 * self.halo)
            else:
                color = QColor("#606c60")
            painter.setPen(QPen(color, 1.3))
            painter.drawLine(QPointF(px, py), QPointF(tx, ty))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(tx, ty), 3 if active else 2, 3 if active else 2)

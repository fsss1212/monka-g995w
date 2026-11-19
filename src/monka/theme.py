"""Theme and small native widgets for the configurator."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QCheckBox, QComboBox, QSpinBox, QStyle, QStyleOptionSpinBox

STYLE = """
QWidget {
    background: #121514; color: #eef1e9; font-family: "Adwaita Sans", "Noto Sans";
    font-size: 13px;
}
QDialog { background: #191d19; }
QLabel { background: transparent; }
QLabel#brand { font-size: 18px; font-weight: 800; }
QLabel#model, QLabel#label, QLabel#notice, QLabel#connection, QLabel#source {
    color: #a1aaa0;
}
QLabel#title { font-size: 35px; font-weight: 750; }
QLabel#section { font-size: 18px; font-weight: 700; }
QLabel#metric { font-size: 16px; font-weight: 700; }
QLabel#status { color: #d7fa79; }
QLabel#status[failed="true"] { color: #ff9f9f; }
QLabel#connectionDot { color: #89928a; font-size: 13px; }
QLabel#connectionDot[online="true"] { color: #d7fa79; }
QFrame#sidebar { background: #181c18; border-right: 1px solid #282e28; }
QFrame#card { background: #1a1e1a; border: 1px solid #2a3229; border-radius: 18px; }
QFrame#card QWidget#content, QWidget#viewport, QStackedWidget { background: transparent; }
QFrame#footer { background: #181c18; border: 1px solid #282e28; border-radius: 14px; }
QPushButton, QComboBox, QSpinBox, QLineEdit, QPlainTextEdit {
    padding: 7px 10px; border: 1px solid #364037; border-radius: 8px;
    background: #232a24; min-height: 19px; selection-background-color: #526239;
}
QPushButton { font-weight: 600; }
QPushButton:hover, QComboBox:hover { background: #2e382e; border-color: #4d5b4c; }
QPushButton:pressed { background: #3b493b; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border-color: #a6bf6b;
}
QPushButton:disabled, QSpinBox:disabled, QLineEdit:disabled { color: #858f84; background: #202520; }
QPushButton#apply { background: #d7fa79; border-color: #d7fa79; color: #192008; }
QPushButton#apply:hover { background: #e6ffa5; }
QPushButton#apply:pressed { background: #badb61; }
QPushButton#apply:disabled { background: #303a27; border-color: #35412a; color: #a0aa93; }
QPushButton[nav="true"] {
    text-align: left; padding: 10px; background: transparent; border-color: transparent; color: #b6c0b5;
}
QPushButton[nav="true"]:hover { background: #242e24; color: #edf3e6; }
QPushButton[nav="true"]:focus { border-color: #82945e; }
QPushButton[nav="true"]:checked { background: #2b3922; color: #d7fa79; }
QPushButton[mapPin="true"] {
    border-radius: 15px; min-height: 0px; padding: 0; background: #262e26; border-color: #5c6a5a;
}
QPushButton[mapPin="true"]:hover, QPushButton[mapPin="true"]:focus { border-color: #d7fa79; }
QPushButton[mapPin="true"]:checked { background: #d7fa79; border-color: #d7fa79; color: #192008; }
QPushButton[selector="true"] { padding: 0; min-height: 29px; background: #202620; }
QPushButton[selector="true"]:hover { background: #293429; }
QLabel#assignmentValue { color: #abb7aa; }
QLabel#assignmentName { font-weight: 600; }
QPushButton[selector="true"]:checked { background: #2b3922; border-color: #6c844d; color: #d7fa79; }
QPushButton#quiet { background: transparent; border-color: transparent; color: #aab6a8; }
QPushButton#quiet:hover, QPushButton#quiet:focus { background: #283228; color: #eff6e9; }
QPushButton::menu-indicator { image: none; width: 0px; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down { border: 0px; width: 26px; }
QComboBox::down-arrow { image: none; }
QComboBox QAbstractItemView, QMenu {
    background: #222a23; border: 1px solid #414e41; color: #eef1e9;
    selection-background-color: #34452b;
}
QMenu::item { padding: 8px 23px 8px 12px; }
QMenu::item:selected { background: #34452b; }
QMenu::item:disabled { color: #858f84; }
QMenu::separator { height: 1px; background: #414e41; margin: 4px 8px; }
QSpinBox { padding-right: 24px; }
QSpinBox::up-button, QSpinBox::down-button { width: 22px; border: none; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #354135; }
QSpinBox::up-arrow, QSpinBox::down-arrow { image: none; }
QScrollArea { border: 0px; background: transparent; }
QScrollBar:vertical { background: #1a1e1a; width: 7px; }
QScrollBar::handle:vertical { background: #4a5649; border-radius: 3px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
"""


def draw_chevron(painter, x, y):
    painter.drawLine(QPointF(x - 3, y - 1), QPointF(x, y + 2))
    painter.drawLine(QPointF(x, y + 2), QPointF(x + 3, y - 1))


class ComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#aab6a8"), 1.4, cap=Qt.PenCapStyle.RoundCap))
        draw_chevron(painter, self.width() - 15, self.height() / 2)


class SpinBox(QSpinBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        for control, direction, flag in (
            (QStyle.SubControl.SC_SpinBoxUp, -1, self.StepEnabledFlag.StepUpEnabled),
            (QStyle.SubControl.SC_SpinBoxDown, 1, self.StepEnabledFlag.StepDownEnabled),
        ):
            rect = self.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, option, control, self)
            color = "#aab6a8" if self.isEnabled() and option.stepEnabled & flag else "#626b60"
            painter.setPen(QPen(QColor(color), 1.3, cap=Qt.PenCapStyle.RoundCap))
            painter.save()
            painter.translate(rect.center())
            painter.scale(1, direction)
            draw_chevron(painter, 0, 0)
            painter.restore()


class Toggle(QCheckBox):
    def __init__(self, name):
        super().__init__()
        self.setAccessibleName(name)
        self.setFixedSize(40, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, point):
        return self.rect().contains(point)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        active = self.isChecked()
        painter.setPen(QPen(QColor("#d7fa79" if self.hasFocus() else "#526151")))
        painter.setBrush(QColor("#354427" if active else "#252c26"))
        painter.drawRoundedRect(QRectF(2, 3, 35, 20), 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d7fa79" if active else "#a1aaa0"))
        painter.drawEllipse(QRectF(20 if active else 6, 7, 12, 12))


def icon(kind, color="#becab9"):
    pixmap = QPixmap(40, 40)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.45, cap=Qt.PenCapStyle.RoundCap,
                        join=Qt.PenJoinStyle.RoundJoin))
    if kind == "mouse":
        painter.drawRoundedRect(QRectF(4, 2, 12, 16), 5, 5)
        painter.drawLine(QPointF(4, 8), QPointF(16, 8))
        painter.drawLine(QPointF(10, 3), QPointF(10, 8))
    elif kind == "sensor":
        painter.drawArc(QRectF(3, 4, 14, 14), 0, 180 * 16)
        painter.drawLine(QPointF(10, 11), QPointF(13.5, 7.5))
        painter.drawLine(QPointF(6, 15), QPointF(14, 15))
    elif kind == "light":
        painter.drawEllipse(QRectF(6.5, 6.5, 7, 7))
        for x, y, end_x, end_y in ((10, 2, 10, 4), (10, 16, 10, 18), (2, 10, 4, 10),
                                    (16, 10, 18, 10), (4, 4, 5.4, 5.4),
                                    (14.6, 14.6, 16, 16), (4, 16, 5.4, 14.6),
                                    (14.6, 5.4, 16, 4)):
            painter.drawLine(QPointF(x, y), QPointF(end_x, end_y))
    elif kind == "more":
        for x in (4, 10, 16):
            painter.drawPoint(QPointF(x, 10))
    elif kind == "chevron":
        draw_chevron(painter, 10, 10)
    elif kind == "mark":
        shape = QPainterPath(QPointF(2.5, 15.5))
        shape.lineTo(6.5, 4.5)
        shape.lineTo(10, 11)
        shape.lineTo(13.5, 4.5)
        shape.lineTo(17.5, 15.5)
        painter.drawPath(shape)
    painter.end()
    return QIcon(pixmap)

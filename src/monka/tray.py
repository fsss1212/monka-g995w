"""Battery status in the Linux desktop tray."""
from PyQt6.QtCore import QRectF, Qt, QTime
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def battery_icon(percent=None):
    icon = QIcon()
    for size in (16, 22, 32, 48):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 24, size / 24)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#222925"))
        painter.drawRoundedRect(QRectF(0.5, 1, 23, 22), 5, 5)
        painter.setPen(QColor("#f0f4ed" if percent is not None else "#a6afa5"))
        font = QFont("sans-serif")
        font.setBold(True)
        font.setPixelSize(11 if percent == 100 else 14)
        painter.setFont(font)
        painter.drawText(QRectF(1, 1, 22, 17), Qt.AlignmentFlag.AlignCenter,
                         str(percent) if percent is not None else "–")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#58625a"))
        painter.drawRoundedRect(QRectF(4, 18, 16, 2), 1, 1)
        if percent:
            painter.setBrush(QColor("#ffb46c" if percent <= 20 else "#d7fa79"))
            painter.drawRoundedRect(QRectF(4, 18, 16 * percent / 100, 2), 1, 1)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class BatteryTray(QSystemTrayIcon):
    def __init__(self, window):
        super().__init__(window)
        menu = QMenu(window)
        self.summary = menu.addAction("")
        self.summary.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Открыть MONKA G995W", window.reveal)
        menu.addAction("Выйти", window.quit_from_tray)
        self.setContextMenu(menu)
        self.activated.connect(self.on_activated)
        self.update_status("Поиск мыши…")
        self.show()

    def update_status(self, status, percent=None):
        if percent != getattr(self, "percent", None) or self.icon().isNull():
            self.setIcon(battery_icon(percent))
        self.percent = percent
        self.summary.setText(status)
        self.setToolTip(f"MONKA G995W\n{status}")

    def set_battery(self, percent):
        received = QTime.currentTime().toString("HH:mm")
        self.update_status(f"Заряд ≈ {percent}% · отчёт в {received}", percent)

    def on_activated(self, reason):
        if reason == self.ActivationReason.Trigger:
            self.parent().reveal()

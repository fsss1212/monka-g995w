"""Native Qt interface for sensor, lighting, buttons and local profiles."""
from copy import deepcopy
import json
from pathlib import Path
import time

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QColorDialog, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGraphicsOpacityEffect, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QSystemTrayIcon, QVBoxLayout, QWidget,
)

from . import protocol as p, state
from .mouse_map import ACCENT, MouseMap
from .theme import ComboBox, STYLE, SpinBox, Toggle, icon
from .tray import BatteryTray
from .worker import Worker

GROUP_LABELS = {"sensor": "DPI", "polling": "Частота", "lighting": "Подсветка",
                "buttons": "Кнопки и макросы"}
PAGES = (
    ("mouse", "Кнопки", "Назначения кнопок"),
    ("sensor", "Сенсор", "Сенсор"),
    ("light", "Подсветка", "Подсветка"),
)
PAGE_GROUPS = ("buttons", "sensor", "lighting")
BUTTON_NAMES = ("Левая кнопка", "Правая кнопка", "Колесо", "Кнопка DPI",
                "Боковая · вперёд", "Боковая · назад")


def button(label, callback):
    widget = QPushButton(label)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


def help_text(text):
    label = label_for(text, "notice")
    label.setWordWrap(True)
    return label


def label_for(text, name):
    label = QLabel(text)
    label.setObjectName(name)
    return label


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(21, 20, 21, 20)
    layout.setSpacing(13)
    return frame, layout


def field(layout, title, control):
    label = label_for(title, "label")
    label.setBuddy(control)
    layout.addWidget(label)
    layout.addWidget(control)


def scroll_page(content):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.viewport().setObjectName("viewport")
    content.setObjectName("content")
    scroll.setWidget(content)
    return scroll


def spin(minimum, maximum, step=1):
    widget = SpinBox()
    widget.setRange(minimum, maximum)
    widget.setSingleStep(step)
    return widget


def combo(items):
    widget = ComboBox()
    widget.addItems(list(items))
    return widget


class ColorButton(QPushButton):
    color_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.set_color("ffffff")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(14, 14))
        self.clicked.connect(self.pick)

    def set_color(self, value):
        self.value = value
        self.setText("#" + value.upper())
        pixmap = QPixmap(28, 28)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#91a18d"))
        painter.setBrush(QColor("#" + value))
        painter.drawRoundedRect(1, 1, 12, 12, 4, 4)
        painter.end()
        self.setIcon(QIcon(pixmap))
        self.color_changed.emit()

    def pick(self):
        color = QColorDialog.getColor(QColor("#" + self.value), self, "Выберите цвет")
        if color.isValid():
            self.set_color(color.name()[1:])
        return color.isValid()


class MacroEditor(QDialog):
    def __init__(self, parent, macros):
        super().__init__(parent)
        self.setWindowTitle("Макросы профиля")
        self.resize(550, 430)
        self.macros = deepcopy(macros)
        self.recording = False
        self.held = set()
        layout = QVBoxLayout(self)
        message = help_text("Одна строка на событие: клавиша down/up задержка_мс. "
                            "Например: a down 10, затем a up 40 на следующей строке.")
        layout.addWidget(message)
        top = QHBoxLayout()
        self.select = combo(self.macros)
        top.addWidget(self.select, 1)
        top.addWidget(button("Загрузить", self.load))
        top.addWidget(button("Удалить", self.delete))
        layout.addLayout(top)
        fields = QFormLayout()
        self.name = QLineEdit()
        self.mode = combo(("Указанное число раз", "Любая кнопка останавливает",
                           "Пока кнопка удерживается"))
        self.repeat = spin(1, 255)
        self.events = QPlainTextEdit()
        self.events.setPlaceholderText("a down 10\na up 40")
        self.events.installEventFilter(self)
        self.events.viewport().installEventFilter(self)
        fields.addRow("Имя", self.name)
        fields.addRow("Режим", self.mode)
        fields.addRow("Повторы", self.repeat)
        fields.addRow("События", self.events)
        layout.addLayout(fields)
        capture = QHBoxLayout()
        self.record = button("Начать запись", self.toggle_recording)
        self.timing = combo(("Записывать интервалы", "Минимальная задержка", "Фиксированная задержка"))
        self.delay = spin(1, 51199)
        self.delay.setValue(30)
        self.delay.setSuffix(" мс")
        self.delay.setEnabled(False)
        self.timing.currentIndexChanged.connect(lambda index: self.delay.setEnabled(index == 2))
        for control in (self.record, self.timing, self.delay):
            capture.addWidget(control)
        layout.addLayout(capture)
        layout.addWidget(button("Сохранить макрос в список", self.save))
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                    QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def toggle_recording(self):
        self.recording = not self.recording
        if self.recording:
            self.held.clear()
            self.when = None
            self.record.setText("Остановить запись")
            self.events.setFocus()
        else:
            for name in sorted(self.held):
                self.append_event(name, "up")
            self.held.clear()
            self.record.setText("Начать запись")

    def append_event(self, name, action):
        now = time.monotonic()
        mode = self.timing.currentIndex()
        elapsed = 10 if self.when is None else round((now - self.when) * 1000)
        delay = self.delay.value() if mode == 2 else 10 if mode == 1 else max(1, min(51199, elapsed))
        self.when = now
        self.events.appendPlainText(f"{name} {action} {delay}")

    def eventFilter(self, watched, event):
        if not self.recording:
            return super().eventFilter(watched, event)
        kind = event.type()
        mouse_buttons = {
            Qt.MouseButton.LeftButton: "mouse_left", Qt.MouseButton.RightButton: "mouse_right",
            Qt.MouseButton.MiddleButton: "mouse_middle", Qt.MouseButton.BackButton: "mouse_back",
            Qt.MouseButton.ForwardButton: "mouse_forward",
        }
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            name = mouse_buttons.get(event.button())
            down = kind == QEvent.Type.MouseButtonPress
        elif kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if event.isAutoRepeat():
                return True
            if event.key() == Qt.Key.Key_Escape:
                if kind == QEvent.Type.KeyPress:
                    self.toggle_recording()
                return True
            name = self.key_name(event.key())
            down = kind == QEvent.Type.KeyPress
        else:
            return super().eventFilter(watched, event)
        if name is not None and down != (name in self.held):
            self.held.symmetric_difference_update({name})
            self.append_event(name, "down" if down else "up")
        return True

    @staticmethod
    def key_name(key):
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F12:
            return f"f{key - Qt.Key.Key_F1 + 1}"
        if 32 <= key <= 126:
            name = chr(key).lower() if key != 32 else "space"
            return name if name in p.KEYS else None
        return {
            Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Return: "enter", Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Delete: "delete", Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home", Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "pageup", Qt.Key.Key_PageDown: "pagedown",
            Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
            Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
            Qt.Key.Key_Control: "lctrl", Qt.Key.Key_Shift: "lshift",
            Qt.Key.Key_Alt: "lalt", Qt.Key.Key_Meta: "lmeta",
        }.get(key)

    def load(self):
        name = self.select.currentText()
        if name:
            macro = self.macros[name]
            self.name.setText(name)
            self.mode.setCurrentIndex(macro["mode"])
            self.repeat.setValue(macro["repeat"])
            self.events.setPlainText("\n".join(f"{key} {action} {delay}"
                                               for key, action, delay in macro["events"]))

    def delete(self):
        if self.select.currentText():
            del self.macros[self.select.currentText()]
            self.select.removeItem(self.select.currentIndex())

    def save(self):
        if self.recording:
            self.toggle_recording()
        try:
            name = self.name.text().strip()
            if not 1 <= len(name) <= 60:
                raise ValueError("Введите имя длиной от 1 до 60 символов.")
            events = []
            for line in self.events.toPlainText().splitlines():
                if line.strip():
                    key, action, delay = line.lower().split()
                    events.append([key, action, int(delay)])
            macro = {"mode": self.mode.currentIndex(), "repeat": self.repeat.value(),
                     "events": events}
            p.macro_reports(1, macro)
        except ValueError as exc:
            QMessageBox.warning(self, "Проверьте макрос", str(exc))
            return
        if name not in self.macros:
            self.select.addItem(name)
        self.macros[name] = macro
        self.select.setCurrentText(name)


class Window(QMainWindow):
    def __init__(self, file_state):
        super().__init__()
        self.file_state = file_state
        self.online = self.busy = self.quitting = False
        self.live = {}
        self.setWindowTitle("MONKA G995W")
        self.setMinimumSize(840, 560)
        self.resize(1090, 700)
        self.setStyleSheet(STYLE)
        main = QWidget()
        self.setCentralWidget(main)
        shell = QHBoxLayout(main)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self.sidebar())
        workspace = QWidget()
        shell.addWidget(workspace, 1)
        body = QVBoxLayout(workspace)
        body.setContentsMargins(24, 21, 24, 20)
        body.setSpacing(15)

        header = QHBoxLayout()
        self.title = label_for("", "title")
        header.addWidget(self.title, 1)
        header.addLayout(self.profile_controls())
        body.addLayout(header)

        main_row = QHBoxLayout()
        main_row.setSpacing(15)
        visual, visual_layout = card()
        self.visual_title = label_for("Карта мыши", "section")
        visual_layout.addWidget(self.visual_title)
        self.mouse = MouseMap()
        self.mouse.selected.connect(self.select_button)
        visual_layout.addWidget(self.mouse, 1)
        self.preview_caption = help_text("")
        self.preview_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        visual_layout.addWidget(self.preview_caption)
        main_row.addWidget(visual, 5)

        editor, editor_layout = card()
        editor_layout.setContentsMargins(19, 17, 19, 17)
        self.pages = QStackedWidget()
        for page in (self.buttons_tab(), self.sensor_tab(), self.light_tab()):
            self.pages.addWidget(scroll_page(page))
        editor_layout.addWidget(self.pages)
        main_row.addWidget(editor, 6)
        body.addLayout(main_row, 1)

        self.fade = QGraphicsOpacityEffect(self.pages)
        self.fade.setOpacity(1)
        self.pages.setGraphicsEffect(self.fade)
        self.page_animation = QPropertyAnimation(self.fade, b"opacity", self)
        self.page_animation.setDuration(190)
        self.page_animation.setStartValue(0.52)
        self.page_animation.setEndValue(1.0)
        self.page_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        body.addWidget(self.footer())
        self.show_profile(self.file_state["current"])
        self.select_button(0)
        self.navigate(0, animate=False)
        self.tray = BatteryTray(self)
        self.worker = Worker()
        self.worker.connection.connect(self.on_connection)
        self.worker.event.connect(self.on_event)
        self.worker.dispatched.connect(self.on_dispatched)
        self.worker.done.connect(self.on_done)
        self.worker.start()

    def sidebar(self):
        panel = QFrame()
        panel.setObjectName("sidebar")
        panel.setFixedWidth(168)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 27, 16, 20)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        mark = QLabel()
        mark.setPixmap(icon("mark", ACCENT).pixmap(20, 20))
        brand.addWidget(mark)
        brand.addWidget(label_for("MONKA", "brand"), 1)
        layout.addLayout(brand)
        layout.addWidget(label_for("GURU G995W", "model"))
        layout.addSpacing(31)
        self.nav = QButtonGroup(self)
        for index, (glyph, name, _) in enumerate(PAGES):
            entry = button(name, lambda checked, i=index: self.navigate(i))
            entry.setCheckable(True)
            entry.setProperty("nav", True)
            entry.setIcon(icon(glyph))
            entry.setIconSize(QSize(20, 20))
            self.nav.addButton(entry, index)
            layout.addWidget(entry)
        layout.addStretch()
        presence = QHBoxLayout()
        self.connection_dot = label_for("●", "connectionDot")
        self.connection = label_for("Поиск устройства", "connection")
        self.connection.setWordWrap(True)
        presence.addWidget(self.connection_dot, 0, Qt.AlignmentFlag.AlignTop)
        presence.addWidget(self.connection, 1)
        layout.addLayout(presence)
        self.telemetry = help_text("")
        self.telemetry.hide()
        layout.addWidget(self.telemetry)
        return panel

    def profile_controls(self):
        row = QHBoxLayout()
        row.addWidget(label_for("Профиль", "label"))
        self.profiles = combo(self.file_state["profiles"])
        self.profiles.setAccessibleName("Локальный профиль")
        self.profiles.setMinimumWidth(118)
        self.profiles.setMaximumWidth(165)
        self.profiles.setCurrentText(self.file_state["current"])
        self.profiles.currentTextChanged.connect(self.switch_profile)
        row.addWidget(self.profiles)
        more = self.menu_button("Управление профилями", "more")
        for label, action in (("Сохранить профиль", self.persist_profile),
                              ("Новый профиль…", self.add_profile), ("Переименовать…", self.rename_profile),
                              ("Удалить…", self.delete_profile), ("Импорт…", self.import_profile),
                              ("Экспорт…", self.export_profile), ("Сбросить локальный профиль…", self.reset_profile)):
            more.menu().addAction(label, action)
        more.menu().addSeparator()
        self.last_button = more.menu().addAction("Последние отправленные значения", self.show_last_sent)
        row.addWidget(more)
        return row

    def menu_button(self, label, glyph):
        control = QPushButton()
        control.setIcon(icon(glyph))
        control.setIconSize(QSize(20, 20))
        control.setCursor(Qt.CursorShape.PointingHandCursor)
        control.setFixedWidth(34)
        control.setToolTip(label)
        control.setAccessibleName(label)
        control.setMenu(QMenu(control))
        return control

    def footer(self):
        frame = QFrame()
        frame.setObjectName("footer")
        row = QHBoxLayout(frame)
        row.setContentsMargins(13, 8, 8, 8)
        messages = QVBoxLayout()
        messages.setSpacing(2)
        self.source = help_text("")
        self.status = help_text("")
        self.status.setObjectName("status")
        self.status.hide()
        messages.addWidget(self.source)
        messages.addWidget(self.status)
        row.addLayout(messages, 1)
        self.apply_button = button("", lambda: self.apply_groups((PAGE_GROUPS[self.pages.currentIndex()],)))
        self.apply_button.setObjectName("apply")
        self.apply_button.setEnabled(False)
        row.addWidget(self.apply_button)
        self.apply_menu = self.menu_button("Выбрать настройки для отправки", "chevron")
        self.apply_menu.setEnabled(False)
        menu = self.apply_menu.menu()
        menu.addAction("Применить все настройки…", lambda: self.apply_groups(p.GROUPS))
        menu.addSeparator()
        for group, name in GROUP_LABELS.items():
            menu.addAction(name, lambda checked=False, g=group: self.apply_groups((g,)))
        row.addWidget(self.apply_menu)
        return frame

    def navigate(self, index, animate=True):
        self.nav.button(index).setChecked(True)
        self.title.setText(PAGES[index][2])
        self.pages.setCurrentIndex(index)
        self.mouse.set_interactive(index == 0)
        self.visual_title.setText(("Карта мыши", "Активная ступень DPI", "Предпросмотр")[index])
        self.apply_button.setText(("Применить назначения", "Применить DPI", "Применить подсветку")[index])
        self.update_preview()
        if animate:
            self.page_animation.stop()
            self.page_animation.start()

    def sensor_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 0, 6, 0)
        layout.setSpacing(11)
        layout.addWidget(label_for("Чувствительность", "section"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for col, label in enumerate(("Ступень", "Вкл.", "DPI", "Индикатор")):
            grid.addWidget(label_for(label, "label"), 0, col)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        self.stages = []
        for i in range(1, 7):
            enabled = Toggle(f"Включить ступень {i}")
            dpi, color = spin(50, 26000, 50), ColorButton()
            dpi.setAccessibleName(f"Значение DPI ступени {i}")
            color.setAccessibleName(f"Цвет ступени {i}")
            for col, control in enumerate((label_for(str(i), "metric"), enabled, dpi, color)):
                grid.addWidget(control, i, col)
            dpi.valueChanged.connect(self.update_preview)
            color.color_changed.connect(self.update_preview)
            self.stages.append((enabled, dpi, color))
        layout.addLayout(grid)
        self.active = spin(1, 6)
        self.active.valueChanged.connect(self.update_preview)
        self.rate = combo(str(rate) for rate in p.RATES)
        self.rate.currentTextChanged.connect(self.update_preview)
        form = QFormLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Активная ступень", self.active)
        rate_row = QHBoxLayout()
        rate_row.addWidget(self.rate, 1)
        self.apply_rate_button = button("Применить частоту", lambda: self.apply_groups(("polling",)))
        rate_row.addWidget(self.apply_rate_button)
        self.apply_rate_button.setEnabled(False)
        form.addRow("Частота опроса, Гц", rate_row)
        layout.addLayout(form)
        layout.addStretch()
        return page

    def light_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 0, 6, 0)
        layout.setSpacing(10)
        layout.addWidget(label_for("Эффект", "section"))
        self.mode = combo(p.MODES)
        self.mode.setAccessibleName("Эффект подсветки")
        self.brightness = spin(1, 8)
        self.speed = spin(4, 8)
        self.light_color = ColorButton()
        self.minutes = spin(1, 20)
        self.minutes.setSuffix(" мин")
        self.choose_static = button("Выбрать свой цвет…", self.choose_static_color)
        self.choose_static.setObjectName("quiet")
        self.light_hint = help_text("")
        self.mode.currentIndexChanged.connect(self.update_light_controls)
        self.brightness.valueChanged.connect(self.update_preview)
        self.light_color.color_changed.connect(self.update_preview)
        layout.addWidget(self.mode)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(9)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Яркость", self.brightness)
        form.addRow("Скорость", self.speed)
        form.addRow("Цвет", self.light_color)
        form.addRow("Таймер", self.minutes)
        layout.addLayout(form)
        layout.addWidget(self.choose_static, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.light_hint)
        layout.addStretch()
        layout.addWidget(help_text("Во время зарядки мышь показывает пульсирующий красный."))
        return page

    def update_light_controls(self, mode):
        self.speed.setEnabled(mode in (1, 5))
        self.light_color.setEnabled(mode == 1)
        self.choose_static.setVisible(mode != 1)
        if mode in (5, 6):
            self.light_hint.setText("Цвет берётся из активной ступени в разделе «Сенсор».")
        elif mode == 0:
            self.light_hint.setText("Подсветка выключена.")
        elif mode != 1:
            self.light_hint.setText("Цвет задаёт эффект. Свой цвет можно выбрать в режиме «Постоянный».")
        self.light_hint.setVisible(mode != 1)
        self.update_preview()

    def choose_static_color(self):
        if self.light_color.pick():
            self.mode.setCurrentIndex(1)

    def lighting_settings(self):
        return {"mode": self.mode.currentIndex(), "brightness": self.brightness.value(),
                "speed": self.speed.value(), "color": self.light_color.value,
                "minutes": self.minutes.value()}

    def buttons_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 0, 6, 0)
        layout.setSpacing(12)
        self.button_title = label_for("", "section")
        layout.addWidget(self.button_title)
        self.assignment_pages = QStackedWidget()
        self.assignment_pages.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.buttons = []
        for _ in p.BUTTONS:
            editor = QWidget()
            editor.setObjectName("content")
            fields = QVBoxLayout(editor)
            fields.setContentsMargins(0, 0, 0, 0)
            fields.setSpacing(8)
            action = combo((*p.ACTIONS, "Сочетание клавиш", "Макрос"))
            arg = QLineEdit()
            arg.setAccessibleName("Параметр действия")
            action.currentTextChanged.connect(lambda choice, field=arg: self.button_argument(choice, field))
            field(fields, "Действие", action)
            fields.addWidget(arg)
            fields.addStretch()
            self.buttons.append((action, arg))
            self.assignment_pages.addWidget(editor)
        layout.addWidget(self.assignment_pages)
        layout.addSpacing(6)
        layout.addWidget(label_for("Все назначения", "section"))
        bindings = QVBoxLayout()
        bindings.setSpacing(5)
        self.button_selectors = QButtonGroup(self)
        for index, (name, (action, _)) in enumerate(zip(BUTTON_NAMES, self.buttons)):
            entry = button("", lambda checked, i=index: self.select_button(i))
            entry.setAccessibleName(name)
            entry.setProperty("selector", True)
            entry.setCheckable(True)
            row = QHBoxLayout(entry)
            row.setContentsMargins(10, 0, 10, 0)
            label = label_for(name, "assignmentName")
            value = label_for(action.currentText(), "assignmentValue")
            value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            for child in (label, value):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            action.currentTextChanged.connect(value.setText)
            action.currentTextChanged.connect(entry.setToolTip)
            row.addWidget(label)
            row.addWidget(value, 1)
            self.button_selectors.addButton(entry, index)
            bindings.addWidget(entry)
        layout.addLayout(bindings)
        layout.addStretch()
        macros = button("Редактор макросов", self.edit_macros)
        macros.setObjectName("quiet")
        layout.addWidget(macros, alignment=Qt.AlignmentFlag.AlignLeft)
        return page

    def select_button(self, index):
        self.mouse.set_selection(index)
        self.button_selectors.button(index).setChecked(True)
        self.assignment_pages.setCurrentIndex(index)
        self.button_title.setText(BUTTON_NAMES[index])

    def update_preview(self, *_):
        page = self.pages.currentIndex()
        if page == 0:
            self.preview_caption.setText("Выберите кнопку, чтобы изменить её действие.")
            self.mouse.set_light(0, "ffffff", 8)
            return
        active = self.active.value()
        _, dpi, stage_color = self.stages[active - 1]
        if page == 1:
            self.mouse.set_light(1, stage_color.value, 8)
            self.preview_caption.setText(f"Ступень {active}  ·  {dpi.value():,} DPI  ·  {self.rate.currentText()} Гц".replace(",", " "))
            return
        settings = self.lighting_settings()
        mode = settings["mode"]
        color = stage_color.value if mode in (5, 6) else settings["color"]
        self.mouse.set_light(mode, color, settings["brightness"])
        self.preview_caption.setText(p.MODES[mode])

    @staticmethod
    def button_argument(choice, field):
        needs_argument = choice in ("Макрос", "Сочетание клавиш")
        field.setVisible(needs_argument)
        field.setEnabled(needs_argument)
        field.setPlaceholderText("Имя макроса" if choice == "Макрос" else
                                 "ctrl+shift+a" if choice == "Сочетание клавиш" else "")

    def show_profile(self, name):
        profile = self.file_state["profiles"][name]
        for i, (enabled, dpi, color) in enumerate(self.stages):
            enabled.setChecked(profile["sensor"]["enabled"][i])
            dpi.setValue(profile["sensor"]["dpi"][i])
            color.set_color(profile["sensor"]["colors"][i])
        self.active.setValue(profile["sensor"]["stage"])
        self.rate.setCurrentText(str(profile["polling"]))
        light = profile["lighting"]
        self.mode.setCurrentIndex(light["mode"])
        self.update_light_controls(light["mode"])
        self.brightness.setValue(light["brightness"])
        self.speed.setValue(light["speed"])
        self.light_color.set_color(light["color"])
        self.minutes.setValue(light["minutes"])
        for (action, arg), assignment in zip(self.buttons, profile["buttons"]):
            action.setCurrentText(assignment["action"])
            arg.setText(assignment["arg"])
            self.button_argument(action.currentText(), arg)
        self.macros = deepcopy(profile["macros"])
        self.update_source()
        self.update_preview()

    def draft(self):
        return {
            "sensor": {"enabled": [x.isChecked() for x, _, _ in self.stages],
                       "dpi": [x.value() for _, x, _ in self.stages],
                       "colors": [x.value for _, _, x in self.stages],
                       "stage": self.active.value()},
            "polling": int(self.rate.currentText()),
            "lighting": self.lighting_settings(),
            "buttons": [{"action": x.currentText(), "arg": y.text().strip() if y.isEnabled() else ""}
                        for x, y in self.buttons],
            "macros": self.macros,
        }

    def snapshot(self):
        return p.validate(self.draft())

    def edit_macros(self):
        editor = MacroEditor(self, self.macros)
        if editor.exec():
            self.macros = editor.macros

    def error(self, exc):
        QMessageBox.warning(self, "MONKA G995W", str(exc))

    def save_file(self):
        try:
            state.write(self.file_state)
        except OSError as exc:
            self.error(exc)

    def persist_profile(self):
        try:
            self.file_state["profiles"][self.profiles.currentText()] = self.snapshot()
            state.write(self.file_state)
            self.set_status("Профиль сохранён на компьютере.")
        except (ValueError, OSError) as exc:
            self.error(exc)

    def switch_profile(self, name):
        if name:
            self.file_state["current"] = name
            self.show_profile(name)
            self.save_file()

    def new_name(self, initial=""):
        name, ok = QInputDialog.getText(self, "Профиль", "Имя профиля", text=initial)
        name = name.strip()
        if ok and name and name not in self.file_state["profiles"]:
            return name
        if ok:
            self.error("Введите уникальное имя профиля.")
        return None

    def add_profile(self):
        if name := self.new_name():
            self.file_state["profiles"][name] = p.defaults()
            self.profiles.addItem(name)
            self.profiles.setCurrentText(name)

    def rename_profile(self):
        old = self.profiles.currentText()
        if name := self.new_name(old):
            self.file_state["profiles"][name] = self.file_state["profiles"].pop(old)
            self.profiles.setItemText(self.profiles.currentIndex(), name)
            self.file_state["current"] = name
            self.save_file()

    def delete_profile(self):
        if self.profiles.count() == 1:
            return self.error("Оставьте хотя бы один профиль.")
        name = self.profiles.currentText()
        if QMessageBox.question(self, "Удалить профиль", f"Удалить профиль «{name}»?") == QMessageBox.StandardButton.Yes:
            del self.file_state["profiles"][name]
            self.profiles.removeItem(self.profiles.currentIndex())
            self.save_file()

    def reset_profile(self):
        name = self.profiles.currentText()
        if QMessageBox.question(self, "Сброс профиля", "Восстановить значения Marvo в локальном профиле?") == QMessageBox.StandardButton.Yes:
            self.file_state["profiles"][name] = p.defaults()
            self.show_profile(name)
            self.save_file()

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, "Импорт профиля", "", "Профили JSON (*.json)")
        if path:
            try:
                profile = p.validate(json.loads(Path(path).read_text()))
                if name := self.new_name(Path(path).stem):
                    self.file_state["profiles"][name] = profile
                    self.profiles.addItem(name)
                    self.profiles.setCurrentText(name)
            except (AttributeError, OSError, ValueError, TypeError, KeyError) as exc:
                self.error(exc)

    def export_profile(self):
        try:
            profile = self.snapshot()
            path, _ = QFileDialog.getSaveFileName(self, "Экспорт профиля", "", "Профили JSON (*.json)")
            if path:
                state.atomic_write(Path(path), profile)
        except (OSError, ValueError) as exc:
            self.error(exc)

    def update_source(self):
        sent = self.file_state["sent"]
        self.last_button.setEnabled(bool(sent))
        self.source.setText("Локальный профиль · Примените, чтобы отправить изменения")
        self.source.setToolTip("Текущая конфигурация в памяти мыши может отличаться. "
                               "История отправки доступна в меню профиля.")

    def show_last_sent(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Последние отправленные значения")
        dialog.resize(630, 440)
        layout = QVBoxLayout(dialog)
        layout.addWidget(help_text("История отправки с этого компьютера. "
                                   "Текущие значения в памяти мыши могут отличаться."))
        saved = QPlainTextEdit()
        saved.setReadOnly(True)
        sections = {}
        for group, record in self.file_state["sent"].items():
            content = {"Подтверждение мыши": record["acknowledged"],
                       "Значения": record["value"]}
            if "transport" in record:
                content["Подключение"] = record["transport"]
            if "macros" in record:
                content["Макросы"] = record["macros"]
            sections[GROUP_LABELS[group]] = content
        saved.setPlainText(json.dumps(sections, indent=2, ensure_ascii=False))
        layout.addWidget(saved)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def on_connection(self, message, online):
        if online:
            self.connection.setText(message.partition(" · ")[0])
        else:
            self.connection.setText("Мышь отключена" if message.startswith("Ожидание") else "Нет подключения")
        self.connection.setToolTip(message)
        tray_status = "Ожидание данных о заряде" if online else self.connection.text()
        self.tray.update_status(tray_status)
        self.connection_dot.setProperty("online", online)
        self.connection_dot.style().unpolish(self.connection_dot)
        self.connection_dot.style().polish(self.connection_dot)
        self.online = online
        self.live.clear()
        self.telemetry.clear()
        self.telemetry.hide()
        self.update_apply_buttons()

    def update_apply_buttons(self):
        enabled = self.online and not self.busy
        for control in (self.apply_button, self.apply_menu, self.apply_rate_button):
            control.setEnabled(enabled)

    def set_status(self, message, failed=False):
        self.status.setProperty("failed", failed)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def on_event(self, kind, value):
        if kind == "ack" or not self.online:
            return
        if kind == "battery":
            self.tray.set_battery(value[0])
        self.live[kind] = value
        labels = []
        if "battery" in self.live:
            battery, _ = self.live["battery"]
            labels.append(f"Батарея ≈ {battery}%")
        if "stage" in self.live:
            labels.append(f"Ступень DPI {self.live['stage']}")
        if "light" in self.live and self.live["light"] < len(p.MODES):
            labels.append(p.MODES[self.live["light"]])
        self.telemetry.setText("\n".join(labels))
        self.telemetry.setVisible(bool(labels))

    def apply_groups(self, groups):
        if self.busy or not self.online:
            return
        try:
            profile = self.snapshot() if groups == p.GROUPS else self.draft()
            list(p.packets(profile, groups))
        except (KeyError, ValueError) as exc:
            return self.error(exc)
        if "buttons" in groups or "sensor" in groups:
            question = ("Настройки из локального профиля заменят текущие значения в памяти мыши. "
                        "Применить изменения?")
            if QMessageBox.question(self, "Применить", question) != QMessageBox.StandardButton.Yes:
                return
        self.queue_apply(profile, groups)

    def queue_apply(self, profile, groups):
        self.busy = True
        self.update_apply_buttons()
        self.set_status("Передача настроек…")
        self.worker.apply(profile, groups)

    def on_dispatched(self, group, profile, acknowledged, transport):
        try:
            state.remember(self.file_state, profile, group, acknowledged, transport)
        except OSError as exc:
            self.error(exc)
        self.update_source()

    def on_done(self, message):
        self.busy = False
        self.set_status(message, message.startswith("Ошибка"))
        self.update_apply_buttons()

    def reveal(self):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        if self.busy:
            self.reveal()
            self.set_status("Дождитесь завершения передачи.")
            return
        self.quitting = True
        self.close()
        QApplication.quit()

    def stop_worker(self):
        self.worker.requestInterruption()
        self.worker.wait()

    def closeEvent(self, event):
        if not self.quitting and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
            return
        if self.busy:
            self.set_status("Дождитесь завершения передачи.")
            event.ignore()
            return
        self.tray.hide()
        self.stop_worker()
        event.accept()

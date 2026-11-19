"""Feature reports reconstructed from Marvo Mouse.exe 1.0.0.0."""
from copy import deepcopy

RATES = {125: 8, 250: 4, 500: 2, 1000: 1}
MODES = ("Выкл.", "Постоянный", "Дыхание", "Неон", "Цветное дыхание",
         "Цвет DPI", "Дыхание цветом DPI")
BUTTONS = {0: "Левая", 1: "Правая", 2: "Колесо", 3: "Кнопка DPI",
           6: "Вперёд", 7: "Назад"}
# Stable names and values of the button functions exposed by this configurator.
ACTIONS = {
    "Выкл.": (1, 0, 0), "Левый клик": (2, 0, 0), "Правый клик": (3, 0, 0),
    "Средний клик": (4, 0, 0), "Вперёд": (6, 0, 0), "Назад": (5, 0, 0),
    "Следующая ступень DPI": (13, 0, 0), "DPI +": (14, 0, 0), "DPI −": (15, 0, 0),
    "Двойной клик": (7, 0, 0), "Автоогонь": (8, 0, 0),
    "Временное прицеливание": (16, 0, 3), "Прокрутка вверх": (9, 0, 0),
    "Прокрутка вниз": (10, 0, 0), "Прокрутка влево": (12, 0, 0),
    "Прокрутка вправо": (11, 0, 0), "Проигрыватель": (21, 0, 0),
    "Предыдущая дорожка": (22, 0, 0), "Следующая дорожка": (23, 0, 0),
    "Воспроизведение / пауза": (24, 0, 0), "Остановить": (25, 0, 0),
    "Без звука": (26, 0, 0), "Громче": (27, 0, 0), "Тише": (28, 0, 0),
    "Калькулятор": (29, 0, 0), "Почта": (30, 0, 0),
    "Домой в браузере": (37, 0, 0), "Избранное в браузере": (17, 3, 18),
    "Вперёд в браузере": (32, 0, 0), "Назад в браузере": (33, 0, 0),
    "Прервать загрузку": (34, 0, 0), "Этот компьютер": (35, 0, 0),
    "Обновить страницу": (36, 0, 0), "Поиск в браузере": (38, 0, 0),
    "Вырезать": (17, 1, 27), "Копировать": (17, 1, 6), "Вставить": (17, 1, 25),
    "Открыть": (17, 1, 18), "Отменить": (17, 1, 29), "Повторить": (17, 1, 28),
    "Сохранить": (17, 1, 22), "Печать": (17, 1, 19), "Найти": (17, 1, 9),
    "Выделить всё": (17, 1, 4), "Закрыть окно": (17, 4, 61),
    "Переключить окно": (17, 4, 43), "Показать рабочий стол": (17, 8, 7),
    "Открыть команду": (17, 8, 21), "Заблокировать": (17, 8, 15),
    "Снимок экрана": (17, 10, 22),
}
DEFAULT_ASSIGNMENTS = ["Левый клик", "Правый клик", "Средний клик",
                       "Следующая ступень DPI", "Вперёд", "Назад"]
DEFAULT_SLOTS = (2, 3, 4, 13, 60, 15, 6, 5, 1, 1, 1, 1, 1, 1, 1, 1, 10, 9)
KEYS = {key: i for i, key in enumerate("abcdefghijklmnopqrstuvwxyz", 4)}
KEYS.update({key: i for i, key in enumerate("1234567890", 30)})
KEYS.update({f"f{i}": 57 + i for i in range(1, 13)})
KEYS.update({"enter": 40, "esc": 41, "backspace": 42, "tab": 43, "space": 44,
             "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49, ";": 51, "'": 52,
             "`": 53, ",": 54, ".": 55, "/": 56, "capslock": 57,
             "printscreen": 70, "scrolllock": 71, "pause": 72, "insert": 73,
             "home": 74, "pageup": 75, "delete": 76, "end": 77, "pagedown": 78,
             "right": 79, "left": 80, "down": 81, "up": 82,
             "lctrl": 224, "lshift": 225, "lalt": 226, "lmeta": 227,
             "rctrl": 228, "rshift": 229, "ralt": 230, "rmeta": 231,
             "mouse_left": 241, "mouse_right": 242, "mouse_middle": 243,
             "mouse_back": 244, "mouse_forward": 245})
MODIFIERS = {"ctrl": 1, "shift": 2, "alt": 4, "meta": 8}
INIT = bytes.fromhex("0c 0a 01 fe 01 fe 00 00 00 00")
GROUPS = ("sensor", "lighting", "polling", "buttons")


def defaults():
    return {
        "sensor": {"dpi": [800, 1600, 3200, 4800, 8000, 26000],
                   "enabled": [True] * 6, "stage": 2,
                   "colors": ["ff0000", "00ff00", "0000ff", "ffff00", "00ffff", "ff00ff"]},
        "lighting": {"mode": 5, "brightness": 6, "speed": 8, "color": "0000ff",
                     "minutes": 1},
        "polling": 1000,
        "buttons": [{"action": action, "arg": ""} for action in DEFAULT_ASSIGNMENTS],
        "macros": {},
    }


def integer(value, lo, hi, field):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f"{field} — допустимо от {lo} до {hi}")
    return value


def rgb(value):
    if not isinstance(value, str) or len(value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in value):
        raise ValueError("Цвет должен быть в формате RRGGBB")
    return bytes.fromhex(value)


def checked(payload, length):
    return payload + sum(payload[3:]).to_bytes(2, "big") + bytes(length - len(payload) - 2)


def sensor_report(sensor):
    dpi, enabled, colors = (sensor[key] for key in ("dpi", "enabled", "colors"))
    if not len(dpi) == len(enabled) == len(colors) == 6 or any(type(x) is not bool for x in enabled):
        raise ValueError("Ожидаются шесть ступеней DPI")
    active = integer(sensor["stage"], 1, 6, "Активная ступень")
    if not enabled[active - 1]:
        raise ValueError("Активная ступень DPI должна быть включена")
    codes = [integer(value, 50, 26000, "DPI") // 50 - 1 for value in dpi]
    if any(value % 50 for value in dpi):
        raise ValueError("Шаг DPI составляет 50")
    mask = sum(1 << i for i, on in enumerate(enabled) if on)
    body = bytes((4, 56, 1, 0, 0, mask, 0, 0))
    body += bytes(code & 255 for code in codes) + b"\0\0"
    body += bytes(code >> 8 for code in codes) + b"\0\0"
    body += bytes((active,)) + b"".join(map(rgb, colors))
    body += bytes.fromhex("ff4000 ffffff 01")
    return checked(body, 56)


def lighting_report(lighting):
    mode = integer(lighting["mode"], 0, len(MODES) - 1, "Режим света")
    brightness = integer(lighting["brightness"], 1, 8, "Яркость")
    speed = integer(lighting["speed"], 4, 8, "Скорость")
    minutes = integer(lighting["minutes"], 1, 20, "Таймер")
    body = bytes((5, 15, 1, mode << 4, 9 - brightness, speed if mode in (1, 5) else 8))
    body += rgb(lighting["color"]) + bytes((minutes, 0))
    return checked(body, 15)


def polling_report(rate):
    if type(rate) is not int or rate not in RATES:
        raise ValueError("Допустимые частоты — 125, 250, 500 и 1000 Гц")
    divisor = RATES[rate]
    return bytes((6, 9, 1, divisor, divisor ^ 255, 0, 0, 0, 0))


def shortcut(arg):
    mods, _, key = arg.strip().lower().rpartition("+")
    names = mods.split("+") if mods else []
    if key not in KEYS or KEYS[key] >= 224 or any(name not in MODIFIERS for name in names):
        raise ValueError("Введите сочетание в формате ctrl+shift+a")
    return 17, sum(MODIFIERS[name] for name in set(names)), KEYS[key]


def macro_reports(slot, macro, *, wired=False):
    mode = integer(macro["mode"], 0, 2, "Повтор макроса")
    repeat = integer(macro["repeat"], 1, 255, "Количество повторов")
    events = bytearray()
    pressed = set()
    extended = 0
    for name, kind, delay in macro["events"]:
        if name not in KEYS or kind not in ("down", "up"):
            raise ValueError("Ожидаются имя клавиши и тип down/up")
        if (kind == "down") == (name in pressed):
            raise ValueError(f"Нарушен порядок нажатия и отпускания {name}")
        pressed.symmetric_difference_update({name})
        integer(delay, 1, 51199, "Задержка макроса")
        count, remainder = divmod(delay, 200) if delay > 1270 else (0, delay)
        flag = 1 if kind == "down" else 129
        events.extend((((max(1, remainder) + 5) // 10) | flag, KEYS[name]))
        if count:
            events.extend((count, 3))
            extended += 1
    if pressed or not 0 < len(events) <= 100 or extended > 10:
        raise ValueError("Макрос должен отпускать все клавиши и содержать от 1 до 50 событий с задержками")
    master = bytes((9, 131, slot, mode, 0, 0, 0, repeat)) + bytes(20)
    master += bytes((len(events) // 2,)) + events + bytes(100 - len(events))
    # The third fragment on the receiver advertises 12 bytes including its header.
    # Windows copies 128 bytes after the prefix, then zero pads the fragments.
    payload = checked(master, 131)[3:].ljust(180, b"\0")
    return [bytes((9, 12 if i == 2 and not wired else 64, slot, i)) + payload[i * 60:(i + 1) * 60]
            for i in range(3)]


def button_reports(assignments, macros, *, wired=False):
    if len(assignments) != len(BUTTONS):
        raise ValueError("Ожидаются шесть назначений")
    values = [(code, 0, 0) for code in DEFAULT_SLOTS]
    reports = []
    for index, assignment in zip(BUTTONS, assignments):
        action, arg = assignment["action"], assignment["arg"]
        if action == "Сочетание клавиш":
            value = shortcut(arg)
        elif action == "Макрос":
            if arg not in macros:
                raise ValueError(f"Макрос {arg!r} отсутствует в профиле")
            slot = 1 + len(reports) // 3
            reports.extend(macro_reports(slot, macros[arg], wired=wired))
            value = (18, 0, slot)
        elif action in ACTIONS:
            value = ACTIONS[action]
        else:
            raise ValueError(f"Неизвестное назначение: {action}")
        values[index] = value
    if (2, 0, 0) not in (values[index] for index in BUTTONS):
        raise ValueError("Сохраните левый клик хотя бы на одной кнопке")
    reports.append(checked(bytes((8, 59, 1)) + b"".join(map(bytes, values)), 59))
    return reports


def packets(profile, groups=GROUPS, *, wired=False):
    for group in groups:
        if group == "sensor":
            yield group, [sensor_report(profile[group])]
        elif group == "lighting":
            yield group, [lighting_report(profile[group])]
        elif group == "polling":
            yield group, [polling_report(profile[group])]
        elif group == "buttons":
            yield group, button_reports(profile[group], profile["macros"], wired=wired)


def validate(profile):
    if not isinstance(profile, dict) or set(profile) != set(defaults()):
        raise ValueError("Неверный формат профиля")
    list(packets(profile))
    macros = profile["macros"]
    if not isinstance(macros, dict):
        raise ValueError("Неверный формат макросов")
    for name, macro in macros.items():
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError("Введите имя макроса длиной до 60 символов")
        macro_reports(1, macro)
    return deepcopy(profile)

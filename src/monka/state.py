"""Host-side profiles and a record of successfully dispatched settings."""
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile

from .protocol import defaults, validate

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "monka-g995w"


class AlreadyRunningError(OSError):
    pass


@contextmanager
def exclusive():
    CONFIG.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (CONFIG / "lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AlreadyRunningError("Приложение уже запущено") from exc
        yield


def read():
    try:
        saved = json.loads((CONFIG / "profiles.json").read_text())
    except FileNotFoundError:
        return {"current": "Основной", "profiles": {"Основной": defaults()}, "sent": {}}
    for profile in saved["profiles"].values():
        validate(profile)
    if saved["current"] not in saved["profiles"] or not isinstance(saved["sent"], dict):
        raise ValueError("Повреждён файл профилей")
    return saved


def atomic_write(path, value):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write(state):
    atomic_write(CONFIG / "profiles.json", state)


def remember(state, snapshot, group, acknowledged, transport):
    state["sent"][group] = {
        "value": deepcopy(snapshot[group]),
        "acknowledged": acknowledged,
        "transport": transport,
    }
    if group == "buttons":
        state["sent"][group]["macros"] = deepcopy(snapshot["macros"])
    write(state)

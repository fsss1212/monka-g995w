"""Linux transport using the system HIDAPI hidraw backend."""
import ctypes as c
from dataclasses import dataclass
import hashlib
from pathlib import Path
import time

@dataclass(frozen=True)
class Variant:
    pid: str
    revision: str
    product: str
    descriptor: str
    label: str
    wired: bool


VARIANTS = {
    ("fa60", "0105", "G995W MOUSE"): Variant(
        "fa60", "0105", "G995W MOUSE",
        "cdb1e588d6f03e063c7c8886d74fc693ce27b869b24743db13448e75aafd437b",
        "Приёмник 2,4 ГГц", False,
    ),
    ("fa61", "0104", "USB Gaming Mouse"): Variant(
        "fa61", "0104", "USB Gaming Mouse",
        "f8744b49ea4883417d755f964cafb51277fb74b3401cfdbc067b5ea2b8150d7f",
        "Кабель USB", True,
    ),
}


@dataclass(frozen=True)
class Endpoint:
    path: Path
    sysfs: Path
    variant: Variant

    def info(self):
        return (f"{self.variant.label} · 1d57:{self.variant.pid} · "
                f"{self.variant.revision} · {self.path}")


def discover():
    """Match the observed revision and its complete interface-02 descriptor."""
    paths = []
    for node in Path("/sys/class/hidraw").glob("hidraw*"):
        try:
            hid = (node / "device").resolve(strict=True)
            interface = hid.parent
            usb = interface.parent
            if (interface / "bInterfaceNumber").read_text().strip() != "02":
                continue
            vid, pid, version, name, manufacturer = [
                (usb / key).read_text().strip()
                for key in ("idVendor", "idProduct", "bcdDevice", "product", "manufacturer")
            ]
            variant = VARIANTS.get((pid, version, name))
            if vid != "1d57" or manufacturer != "Beken" or variant is None:
                continue
            digest = hashlib.sha256((hid / "report_descriptor").read_bytes()).hexdigest()
            if digest == variant.descriptor:
                paths.append(Endpoint(Path("/dev") / node.name, hid, variant))
        except OSError:
            continue
    return sorted(paths, key=lambda endpoint: endpoint.path)


def decode(report):
    if len(report) != 5 or report[0] != 3:
        return None
    prefix, event, value, extra = report[1:]
    if prefix == 16:
        if event == 0x50:
            return "ack", (value, extra)
        if event == 0x40 and value in (0, 1) and 1 <= extra <= 10:
            return "battery", (min(extra + (6 <= extra < 10), 10) * 10, bool(value))
    if prefix == 0:
        if event == 0x10 and 1 <= value <= 8 and extra == 0:
            return "stage", value
        if event == 0x70 and 0 <= value <= 7 and extra == 0:
            return "light", value
    return None


class Device:
    def __init__(self, node):
        self.node = node
        self.variant = node.variant
        self.lib = c.CDLL("libhidapi-hidraw.so.0")
        signature = {
            "hid_init": (c.c_int, []),
            "hid_open_path": (c.c_void_p, [c.c_char_p]),
            "hid_send_feature_report": (c.c_int, [c.c_void_p, c.c_void_p, c.c_size_t]),
            "hid_read_timeout": (c.c_int, [c.c_void_p, c.c_void_p, c.c_size_t, c.c_int]),
            "hid_error": (c.c_wchar_p, [c.c_void_p]),
            "hid_get_report_descriptor": (c.c_int, [c.c_void_p, c.c_void_p, c.c_size_t]),
            "hid_close": (None, [c.c_void_p]),
        }
        for name, (result, args) in signature.items():
            function = getattr(self.lib, name)
            function.restype = result
            function.argtypes = args

        if self.lib.hid_init() != 0:
            raise OSError(self.lib.hid_error(None))
        self.handle = self.lib.hid_open_path(bytes(node.path))
        if not self.handle:
            raise OSError(self.lib.hid_error(None))
        descriptor = c.create_string_buffer(4096)
        size = self.lib.hid_get_report_descriptor(self.handle, descriptor, len(descriptor))
        if size < 0 or hashlib.sha256(descriptor.raw[:size]).hexdigest() != self.variant.descriptor:
            self.close()
            raise OSError("Дескриптор открытого устройства изменился")

    def close(self):
        self.lib.hid_close(self.handle)

    def receive(self, timeout):
        buffer = c.create_string_buffer(64)
        size = self.lib.hid_read_timeout(self.handle, buffer, len(buffer), timeout)
        if size < 0:
            raise OSError(self.lib.hid_error(self.handle))
        return buffer.raw[:size]

    def send(self, packet):
        buffer = c.create_string_buffer(packet, len(packet))
        size = self.lib.hid_send_feature_report(self.handle, buffer, len(packet))
        if size != len(packet):
            raise OSError(f"Report {packet[0]:02x}: {self.lib.hid_error(self.handle) if size < 0 else size}")

    def await_ack(self, report_id, on_event, *, expected=0.7):
        deadline = time.monotonic() + expected
        while (remaining := deadline - time.monotonic()) > 0:
            event = decode(self.receive(max(1, int(remaining * 1000))))
            if event is None:
                continue
            if event[0] == "ack":
                if event[1][1] != report_id:
                    continue
                if event[1][0] != 0:
                    raise OSError(f"Мышь отклонила команду, код {event[1][0]}")
                return True
            on_event(*event)
        return False

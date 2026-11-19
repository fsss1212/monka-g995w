"""Serialize HID operations outside the Qt event loop."""
import queue
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .device import Device, decode, discover
from .protocol import INIT, packets


class Worker(QThread):
    connection = pyqtSignal(str, bool)
    event = pyqtSignal(str, object)
    dispatched = pyqtSignal(str, object, bool, str)
    done = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.requests = queue.Queue(maxsize=1)

    def apply(self, snapshot, groups):
        self.requests.put_nowait((snapshot, groups))

    def dispatch(self, dev, snapshot, groups):
        # The Windows utility sends this marker first. Receiver 0105 can stall
        # it while asleep. The status of the actual setting is decisive.
        try:
            dev.send(INIT)
            dev.await_ack(INIT[0], self.event.emit, expected=0.2 if dev.variant.wired else 0.7)
        except OSError:
            pass

        pending = []
        for group, reports in packets(snapshot, groups, wired=dev.variant.wired):
            confirmed = False
            for offset in range(0, len(reports) - 1, 3):
                fragments = reports[offset:offset + 3]
                if dev.variant.wired:
                    for part in fragments:
                        dev.send(part)
                        time.sleep(0.2)
                    continue
                for _ in range(3):
                    for part in fragments[:2]:
                        dev.send(part)
                        time.sleep(0.5)
                    dev.send(fragments[2])
                    if dev.await_ack(9, self.event.emit):
                        break
                else:
                    raise OSError("Приёмник не подтвердил загрузку макроса. Назначения кнопок не отправлены.")
            report = reports[-1]
            # Matches the receiver's retry interval. Use bounded retries for a
            # missed acknowledgement while retaining the successful USB send.
            for _ in range(1 if dev.variant.wired else 3):
                dev.send(report)
                if dev.await_ack(report[0], self.event.emit, expected=0.2 if dev.variant.wired else 0.7):
                    confirmed = True
                    break
            self.dispatched.emit(group, snapshot, confirmed, dev.variant.label)
            if not confirmed:
                pending.append(group)
        if pending:
            return "USB принял отчёты. Для части настроек подтверждение мыши не пришло."
        return "Мышь подтвердила применение."

    def run(self):
        dev = None
        next_scan = 0
        status = None
        try:
            while not self.isInterruptionRequested():
                if time.monotonic() >= next_scan:
                    next_scan = time.monotonic() + 0.8
                    matches = discover()
                    if dev and matches != [dev.node]:
                        dev.close()
                        dev = None
                    if len(matches) > 1:
                        new_status = ("Оставьте подключённым один интерфейс G995W.", False)
                    elif not matches:
                        new_status = ("Ожидание G995W по кабелю или через приёмник", False)
                    else:
                        node = matches[0]
                        try:
                            if dev is None:
                                dev = Device(node)
                            new_status = (node.info(), True)
                        except OSError as exc:
                            new_status = (f"Интерфейс {node.path} недоступен · {exc}", False)
                    if new_status != status:
                        status = new_status
                        self.connection.emit(*status)

                try:
                    snapshot, groups = self.requests.get_nowait()
                except queue.Empty:
                    pass
                else:
                    try:
                        if dev is None or discover() != [dev.node]:
                            raise OSError("Устройство отключено")
                        message = self.dispatch(dev, snapshot, groups)
                    except (OSError, ValueError) as exc:
                        message = f"Ошибка применения · {exc}. Ранее переданные группы могли сохраниться."
                    self.done.emit(message)

                if dev is None:
                    self.msleep(100)
                    continue
                try:
                    event = decode(dev.receive(100))
                    if event is not None:
                        self.event.emit(*event)
                except OSError:
                    dev.close()
                    dev = None
                    status = ("Связь с мышью прервалась", False)
                    self.connection.emit(*status)
        finally:
            if dev:
                dev.close()

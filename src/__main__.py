import argparse
import hashlib
import json
import sys

from monka import state
from monka.device import Device, decode, discover


def main():
    parser = argparse.ArgumentParser(description="Настройка MONKA G995W")
    parser.add_argument("--probe", action="store_true", help="проверить HID без записи")
    parser.add_argument("--tray", action="store_true", help="запуститься сразу в системном трее")
    args = parser.parse_args()
    if args.probe:
        devices = discover()
        if len(devices) != 1:
            print(f"Ожидается один интерфейс G995W, найдено: {len(devices)}", file=sys.stderr)
            return 1
        try:
            device = Device(devices[0])
            try:
                print(f"{devices[0].info()} · интерфейс 02", flush=True)
                for _ in range(7):
                    report = device.receive(1000)
                    if report:
                        print(report.hex(" "), json.dumps(decode(report), ensure_ascii=False),
                              flush=True)
            finally:
                device.close()
        except OSError as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0

    from PyQt6.QtCore import Qt
    from PyQt6.QtNetwork import QLocalServer, QLocalSocket
    from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
    from monka.gui import Window

    application = QApplication([sys.argv[0]])
    application.setApplicationName("MONKA G995W")
    application.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    key = hashlib.sha256(str(state.CONFIG.resolve()).encode()).hexdigest()[:20]
    socket_name = f"monka-g995w-{key}"
    try:
        with state.exclusive():
            window = Window(state.read())
            application.aboutToQuit.connect(window.stop_worker)
            server = QLocalServer(application)
            server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
            QLocalServer.removeServer(socket_name)
            if server.listen(socket_name):
                def reveal_window():
                    while server.hasPendingConnections():
                        connection = server.nextPendingConnection()
                        connection.disconnectFromServer()
                        connection.deleteLater()
                    window.reveal()

                server.newConnection.connect(reveal_window)
            if not args.tray or not QSystemTrayIcon.isSystemTrayAvailable():
                window.show()
            return application.exec()
    except state.AlreadyRunningError as exc:
        if args.tray:
            return 0
        client = QLocalSocket()
        client.connectToServer(socket_name)
        if client.waitForConnected(800):
            return 0
        QMessageBox.critical(None, "MONKA G995W", str(exc))
        return 1
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        QMessageBox.critical(None, "MONKA G995W", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())

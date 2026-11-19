PYTHON ?= /usr/bin/python
PREFIX ?= $(HOME)/.local
DATA_DIR ?= $(PREFIX)/share
BIN_DIR ?= $(PREFIX)/bin
UDEV_DIR ?= /etc/udev/rules.d
APP = build/monka-g995w
SOURCES := $(wildcard src/*.py src/monka/*.py)

.PHONY: all test install uninstall install-udev uninstall-udev

all: $(APP)

$(APP): $(SOURCES)
	install -d build/staging/monka
	install -m644 src/__main__.py build/staging/
	install -m644 src/monka/*.py build/staging/monka/
	$(PYTHON) -m zipapp build/staging -p /usr/bin/python -c -o $@

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

install: $(APP)
	install -Dm755 $(APP) "$(DESTDIR)$(BIN_DIR)/monka-g995w"
	sed 's|^Exec=.*|Exec="$(BIN_DIR)/monka-g995w"|' monka-g995w.desktop > build/monka-g995w.desktop
	install -Dm644 build/monka-g995w.desktop "$(DESTDIR)$(DATA_DIR)/applications/monka-g995w.desktop"

uninstall:
	rm -f "$(DESTDIR)$(BIN_DIR)/monka-g995w" "$(DESTDIR)$(DATA_DIR)/applications/monka-g995w.desktop"

install-udev:
	install -Dm644 70-monka-g995w.rules "$(DESTDIR)$(UDEV_DIR)/70-monka-g995w.rules"
	udevadm control --reload-rules

uninstall-udev:
	rm -f "$(DESTDIR)$(UDEV_DIR)/70-monka-g995w.rules"
	udevadm control --reload-rules

.DEFAULT_GOAL := test

PYTHON ?= python3

.PHONY: test lint icewm uninstall clean
test:
	$(PYTHON) -m unittest discover -s tests
	bash -n scripts/build-icewm.sh
	$(PYTHON) -m py_compile bin/kilix-icewm src/kilix_icewm/*.py

lint:
	-command -v shellcheck >/dev/null && shellcheck -S warning scripts/build-icewm.sh

icewm:
	./scripts/build-icewm.sh

# Removes only what the install recorded; anything else is reported and kept.
uninstall:
	$(PYTHON) bin/kilix-icewm --uninstall

clean:
	rm -rf src/kilix_icewm/__pycache__ tests/__pycache__

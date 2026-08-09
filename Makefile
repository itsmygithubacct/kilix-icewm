.DEFAULT_GOAL := test

PYTHON ?= python3

.PHONY: test lint icewm clean
test:
	$(PYTHON) -m unittest discover -s tests
	bash -n scripts/build-icewm.sh
	$(PYTHON) -m py_compile bin/kilix-icewm src/kilix_icewm/*.py

lint:
	-command -v shellcheck >/dev/null && shellcheck -S warning scripts/build-icewm.sh

icewm:
	./scripts/build-icewm.sh

clean:
	rm -rf src/kilix_icewm/__pycache__ tests/__pycache__

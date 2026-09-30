.PHONY: test bootstrap help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3.14)

test:
	$(PYTHON) -m pytest tests/ -q

bootstrap:
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -e '.[dev]'

help:
	@echo "Targets:"
	@echo "  test       Run pytest unit tests"
	@echo "  bootstrap  Create .venv and install ensemble[dev]"

.PHONY: test bootstrap help

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3.14)

# Run unit tests (no live LLM or Docker required).
test:
	$(PYTHON) -m pytest tests/ -q

# Create .venv and install editable package with dev extras.
bootstrap:
	./scripts/bootstrap_dev.sh

help:
	@echo "Targets:"
	@echo "  test       Run pytest unit tests"
	@echo "  bootstrap  Create .venv and install ensemble[dev]"

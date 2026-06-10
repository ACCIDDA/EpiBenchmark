PYTHON ?= python3.13
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

.PHONY: venv install test-cli

venv:
	$(PYTHON) -m venv $(VENV_DIR)

install: venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e .

test-cli:
	$(VENV_DIR)/bin/epibench
	$(VENV_DIR)/bin/epibench --help
	$(VENV_DIR)/bin/epibench setup --help
	-$(VENV_DIR)/bin/epibench score --help
	-$(VENV_DIR)/bin/epibench plot --help

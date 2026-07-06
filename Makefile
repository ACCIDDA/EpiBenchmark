# Python interpreter used to create the virtual environment.
# Override on the command line if desired:
# make install-pip PYTHON=python3.11
PYTHON ?= python

VENV_DIR ?= .venv

VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
VENV_EPIBENCH := $(VENV_DIR)/bin/epibench

.PHONY: \
	venv \
	install \
	install-pip \
	install-uv \
	sync \
	lock \
	test-cli \
	clean

# Create a virtual environment using Python's built-in venv.
venv:
	$(PYTHON) -m venv $(VENV_DIR)

# Install using pip (editable mode).
install: install-pip

install-pip: venv
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e .


# Install using uv.
# Requires uv to be installed on the system.
install-uv:
	uv sync --locked

# Synchronize the environment with the project.
sync:
	uv sync

# Regenerate uv.lock after dependency changes.
lock:
	uv lock


# Basic CLI smoke tests.
test-cli:
	$(VENV_EPIBENCH)
	$(VENV_EPIBENCH) --help
	$(VENV_EPIBENCH) setup --help
	-$(VENV_EPIBENCH) score --help
	-$(VENV_EPIBENCH) plot --help


# Remove the virtual environment.
clean:
	rm -rf $(VENV_DIR)

# EpiBench

EpiBench is a work-in-progress benchmarking tool for disease forecasts. The package is still in development.

## Virtual Environment Setup

Use a project-local virtual environment so that `pip`, `python`, and `epibench`
all come from the same interpreter.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If `.venv` already exists and was created with a different Python version,
remove it and recreate it before installing:

```bash
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

After virtual environment setup, you can deactivate and reactivate it with:
```bash
deactivate
```

```bash
source .venv/bin/activate
```

## Installing EpiBench

Install EpiBench from the repository root with:

```bash
python -m pip install -e .
```
This makes the `epibench` CLI availabile inside the active virtual environment.

Typical install flow:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Makefile Shortcuts

You can also use the included `Makefile` to avoid typing the full setup and
testing commands each time.

Available commands:

- `make venv`
  Creates the project virtual environment.
- `make install`
  Creates the virtual environment if needed, upgrades `pip`, and installs
  EpiBench in editable mode.
- `make test-cli`
  Runs a small CLI smoke test for:
  - `epibench`
  - `epibench --help`
  - `epibench setup --help`
  - `epibench score --help`
  - `epibench plot --help`

If your Python 3.13 executable has a different name, you can override it:

```bash
make install PYTHON=python3.13
```

After installation, test the CLI with:

```bash
epibench
epibench --help
epibench setup --help
epibench score --help
epibench plot --help
```


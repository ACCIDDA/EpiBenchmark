# EpiBench

EpiBench is a work-in-progress benchmarking tool for disease forecasts. The package is still in development.

## Installation

We recommend using a project-local virtual environment so that `pip`, `python`,
and `epibench` all come from the same interpreter.

To begin installing EpiBench, clone the repository locally and run the following commands from the repository
root.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
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

Install EpiBench from the repository root with:

```bash
python -m pip install -e .
```
This makes the `epibench` CLI available inside the active virtual environment.

Full install flow:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

After setup, you can leave and re-enter the environment with:

```bash
deactivate
source .venv/bin/activate
```

## Scoring Requirements

The Python virtual environment only manages EpiBench's Python dependencies.
The `epibench score` command also calls `Rscript`, so scoring has two external
requirements:

- `Rscript` must be available on your `PATH`
- the CRAN package `scoringutils` must be installed in the R library used by
  that `Rscript`

This is compatible with the `venv` workflow above: you run `epibench` from the
activated Python environment, and that Python process invokes the `Rscript`
available on your machine.

You can check that `Rscript` is available with:

```bash
Rscript --version
```

Install `scoringutils` with:

```bash
Rscript -e 'install.packages("scoringutils")'
```

Verify that the package is available with:

```bash
Rscript -e 'library(scoringutils)'
```

If `epibench score` reports that `Rscript` or `scoringutils` is missing, make
sure they are installed in the same R environment used by your `Rscript`
command.

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

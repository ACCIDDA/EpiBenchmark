# EpiBenchmark

EpiBench is a work-in-progress benchmarking tool for evaluating performance of infectious disease forecasting models. The package is still in development.

## Requirements
- Python 3.10 or later
- Git
- R and the `scoringutils` package for the `epibench score` command

## Quick Start
```bash
git clone https://github.com/ACCIDDA/EpiBenchmark.git
cd EpiBenchmark
uv sync --locked
uv run epibench --help
```

## Installation

Clone the repository:

```bash
git clone https://github.com/ACCIDDA/EpiBenchmark.git

cd EpiBenchmark
```

EpiBenchmark supports installation using either **uv** (recommended) or **pip**.

## Option 1: Install with uv

This is the fastet installation method.

If the repository includes a `uv.lock` file, install using:

```bash
uv sync
```

### Activate the virtual environment

### Windows

```bash
.venv\Scripts\activate
```

### macOS/Linux

```bash
source .venv/bin/activate
```

Alternatively, users can run commands without activating the environment:

```bash
uv run epibench --help
```

## Option 2: Install with pip

Create a virtual environment.

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### macOS/Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install EpiBenchmark in editable mode:

```bash
python -m pip install -e .
```

## Verify the Installation

After installation, verify that the command-line interface is available:

```bash
epibench --help
```
Users can also verify the available subcommands:

```bash
epibench setup --help
epibench score --help
epibench plot --help
```

## Scoring Requirements

The Python virtual environment only manages EpiBenchmark's Python dependencies.
The `epibench score` command also calls `Rscript`, so scoring has two external
requirements:

- `Rscript` must be available on users' `PATH`
- the CRAN package `scoringutils` must be installed in the R library used by
  that `Rscript`

Check that `R` is available with:

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
sure they are installed in the same R environment used by `Rscript`
command.

## Makefile Shortcuts

The repository includes a `Makefile` with several convenience commands for common development tasks. These shortcuts are primarily intended for macOS and Linux users. Windows users can run the equivalent commands directly from the command line.

### Create a virtual environment

- `make venv`
  Creates a project-local virtual environment in `.venv`.

### Install with pip
- `make install` or `make install-pip`
  Creates the virtual environment if needed, upgrades `pip`, and installs
  EpiBenchmark in editable mode using `pip`.

### Install with uv
- `make install-uv`
  Installs EpiBenchmark using the recommended `uv` workflow: `uv sync --locked`
  This installs the project and its dependencies according to the committed `uv.lock` file.

### Synchronize the environment
- `make sync` runs `uv sync`
  This command is intended primarily for developers after project dependencies have changed.

### Regenerate the lock file
- `make lock` runs `uv lock`
  Regnerates the `uv.lock` file fafter updating project dependencies.

### Test the command-line interface
- `make test-cli`
  Runs a basci CLI smoke test for:
  - `epibench`
  - `epibench --help`
  - `epibench setup --help`
  - `epibench score --help`
  - `epibench plot --help`

### Remove the virtual environment
- `make clean`
  Deletes the local `.venv` directory, allowing users to create a fresh environment.

### Using a different Python interpreter
By default, the Makefile uses the system python3 executable. Users can override it when creating the virtual environment:

```bash
make install-pip PYTHON=python3.11
```

or

```bash
make venv PYTHON=/path/to/python
```

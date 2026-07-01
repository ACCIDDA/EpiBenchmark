# EpiBenchmark

EpiBench is a work-in-progress benchmarking tool for evaluating performance of infectious disease forecasting models. The package is still in development.

## Requirements
- Python 3.10 or later
- Git
- R and the `scoringutils` package for the `epibench score` command

## Installation

Clone the repository:

git clone https://github.com/ACCIDDA/EpiBenchmark.git

cd EpiBenchmark

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

Alternatively, you can run commands without activating the environment:

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
You can also verify the available subcommands:

```bash
epibench setup --help
epibench score --help
epibench plot --help
```

## Scoring Requirements

The Python virtual environment only manages EpiBenchmark's Python dependencies.
The `epibench score` command also calls `Rscript`, so scoring has two external
requirements:

- `Rscript` must be available on your `PATH`
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
sure they are installed in the same R environment used by your `Rscript`
command.

## Makefile Shortcuts

The repository includes a `Makefile` with several convenience commands.

Available commands:

- `make venv`
  Creates the project virtual environment.
- `make install`
  Creates the virtual environment if needed, upgrades `pip`, and installs
  EpiBenchmark in editable mode.
- `make test-cli`
  Runs a small CLI smoke test for:
  - `epibench`
  - `epibench --help`
  - `epibench setup --help`
  - `epibench score --help`
  - `epibench plot --help`

If your Python executable has a different name, you can override it:

```bash
make install PYTHON=python3
```

or for a specific version:

```bash
make install PYTHON=python3.11
```

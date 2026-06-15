# Installation

EpiBench uses a standard Python installation flow with one extra runtime
requirement for scoring: `epibench score` calls `Rscript` and needs the CRAN
package `scoringutils`.

## Python Environment

We recommend using a project-local virtual environment so that `python`, `pip`,
and `epibench` all come from the same interpreter.

Clone the repository locally and run the following commands from the repository
root.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

If `.venv` already exists but was created with a different Python version,
recreate it before installing:

```bash
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## Installing EpiBench

From the repository root, install EpiBench with:

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

## R Requirements For Scoring

The Python virtual environment does not install or manage R. To use
`epibench score`, make sure:

- `Rscript` is available on your `PATH`
- `scoringutils` is installed for that `Rscript`

Check that `Rscript` is available:

```bash
Rscript --version
```

Install `scoringutils`:

```bash
Rscript -e 'install.packages("scoringutils")'
```

Verify that it loads correctly:

```bash
Rscript -e 'library(scoringutils)'
```

If `epibench score` reports that `Rscript` or `scoringutils` is missing, make
sure they are installed in the same R environment used by your `Rscript`
command.

## Verifying The Installation

After installing EpiBench, you can verify that the CLI is available inside the
activated virtual environment:

```bash
epibench
epibench --help
epibench setup --help
epibench score --help
epibench plot --help
```

## Makefile Shortcuts

You can also use the included `Makefile` to simplify setup and CLI checks:

- `make venv` creates the project virtual environment
- `make install` creates the virtual environment if needed, upgrades `pip`, and installs EpiBench in editable mode
- `make test-cli` runs a small CLI smoke test

If your Python 3.13 executable has a different name, you can override it:

```bash
make install PYTHON=python3.13
```

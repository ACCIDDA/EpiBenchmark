# Installation

EpiBench uses a standard Python installation flow with one extra runtime
requirement for scoring: `epibench score` calls `Rscript` and needs the CRAN
package `scoringutils`.

## Python Environment

We recommend using a local virtual environment so that `python`, `pip`, and
`epibench` come from the same interpreter.

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If `.venv` already exists but was created with a different Python version,
recreate it before installing.

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

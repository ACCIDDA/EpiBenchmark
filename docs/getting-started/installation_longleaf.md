# Installing EpiBenchmark on the UNC Longleaf Cluster

This guide describes how to install and use EpiBenchmark on the UNC Longleaf HPC cluster.

## Prerequisites

Before installing EpiBenchmark, load a compatible Python module.

List the available Python versions:

```bash
module avail python
```

Load a supported version (Python 3.10 or newer). For example:

```bash
module load python/3.11
```

> **Note**
>
> The exact module name may change over time. Use `module avail python` to see the versions currently available on Longleaf.

Clone the repository:

```bash
git clone https://github.com/ACCIDDA/EpiBenchmark.git
cd EpiBenchmark
```

---

# Option 1: Install with uv (Recommended)

First, verify whether `uv` is available:

```bash
uv --version
```

If `uv` is installed, create the environment:

```bash
uv sync --locked
```

Activate the environment:

```bash
source .venv/bin/activate
```

Verify the installation:

```bash
epibench --help
```

---

# If uv is not installed

Install `uv` into your user account:

```bash
python -m pip install --user uv
```

Make sure your user-level executable directory is on your `PATH`.

Then run:

```bash
uv sync --locked
```

---

# Option 2: Install with pip

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install EpiBenchmark:

```bash
python -m pip install -e .
```

Verify the installation:

```bash
epibench --help
```

---

# R Requirements for Scoring

The `epibench score` command requires:

* R
* `Rscript`
* the CRAN package `scoringutils`

Check that R is available:

```bash
module spider r
```

Load the default R

```bash
module load r
```

Install `scoringutils`:

```bash
Rscript -e 'install.packages("scoringutils")'
```

Verify the installation:

```bash
Rscript -e 'library(scoringutils)'
```

---

# Running EpiBenchmark

Activate the virtual environment whenever you begin a new session:

```bash
source .venv/bin/activate
```

Example commands:

```bash
epibench --help
epibench setup --help
epibench score --help
epibench plot --help
```

Deactivate the environment when finished:

```bash
deactivate
```

---

# Troubleshooting

### Python version

Verify the Python version:

```bash
python --version
```

EpiBenchmark requires Python **3.10 or newer**.

### Missing `uv`

If `uv` is unavailable, install it with:

```bash
python -m pip install --user uv
```

or use the pip installation method instead.

### Missing `Rscript`

Verify that R is available:

```bash
Rscript --version

or 

module spider r
```

If this command fails, load the appropriate R module or contact the Longleaf administrators.

### Missing `scoringutils`

Install the package into the same R environment used by `Rscript`:

```bash
Rscript -e 'install.packages("scoringutils")'
```

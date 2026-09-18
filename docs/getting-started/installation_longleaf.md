# Installing EpiBenchmark on the UNC Longleaf Cluster

This guide describes how to install and use EpiBenchmark on the UNC Longleaf HPC cluster. **If you only want to use EpiBenchmark on your machine, you need not do anything beyond the standard [installation instructions](installation.md)**.

## Prerequisites

Before installing EpiBenchmark, verify or load a compatible Python module.

Verify the Python version:

```bash
python --version
```

List the available Python versions:

```bash
module avail python
```

Load a supported version (Python 3.10 or newer). For example:

```bash
module load python/3.11
```

> **Note**
> The exact module name may change over time. Use `module avail python` to see the versions currently available on Longleaf.

Clone the repository:

```bash
git clone https://github.com/ACCIDDA/EpiBenchmark.git
cd EpiBenchmark
```

---

# Option 1: Install with uv

First, verify whether `uv` is available:

```bash
uv --version
```

If `uv` is installed, create the virtual environment and install `EpiBenchmark` package:

```bash
uv sync
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

## If uv is not installed

Install `uv` into your user account:

```bash
python -m pip install --user uv
```

Make sure your user-level executable directory is on your `PATH`. Users can run `echo $PATH` to check user-level directory. If you see `/nas/longleaf/home/<onyen_ID>/.local/bin` in the output list, then your PATH is already configured correctly.

Then run:

```bash
uv sync
```

Verify the installation:

```bash
epibench --help
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

Install `EpiBenchmark` package:

```bash
python -m pip install -e .
```

Verify the installation:

```bash
epibench --help
```

---

# Running EpiBenchmark

Activate the virtual environment whenever you begin a new session:

```bash
source .venv/bin/activate
```

Example commands:

```bash
epibench
epibench --help
epibench create --help
epibench score --help
epibench plot --help
```

Deactivate the environment when finished:

```bash
deactivate
```

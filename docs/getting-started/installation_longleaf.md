# Installing EpiBenchmark on the UNC Longleaf Cluster

This guide describes how to install and use EpiBenchmark on the UNC Longleaf HPC cluster.

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

# R Requirements for Scoring

To run `epibench score` command, users need:

* R
* `Rscript`
* the CRAN package `scoringutils`


Verify the R version:

```bash
Rscript --version
```

If R is not installed, check that R is available:

```bash
module spider r
```

Load the default R

```bash
module load r
```

## R library setup
Before installing `scoringutils`, check whether R already has a personal library configured:

```bash
Rscript -e '.libPaths()'
```

This is because R will try to install packages into the system library if no users' personal library configured. That system directory is owned by the Longleaf administrators, ordinary users cannot write to it.

If there isn't a user library, create one.

```bash
mkdir -p ~/R/x86_64-pc-linux-gnu-library/<R_version_installed_in_longleaf>
e.g. mkdir -p ~/R/x86_64-pc-linux-gnu-library/4.4
```

**Note**: 4.4 will be used in the following command examples.

Add the created user library to `libPaths` and verify:

```bash
Rscript -e '.libPaths(c("~/R/x86_64-pc-linux-gnu-library/4.4", .libPaths())); print(.libPaths())'
```

Users should see the following:
```
[1] "/home/<onyen_ID>/R/x86_64-pc-linux-gnu-library/4.4"
[2] "/nas/longleaf/rhel9/apps/r/4.4.0/lib64/R/library"
```

## Install package `scoringutils`
Once the user-level library exists, run:

```bash
Rscript -e '.libPaths(c("~/R/x86_64-pc-linux-gnu-library/4.4", .libPaths())); install.packages("scoringutils", repos="https://cloud.r-project.org")'
```

Verify the installation:

```bash
Rscript -e '.libPaths(c("~/R/x86_64-pc-linux-gnu-library/4.4", .libPaths())); library(scoringutils)'
```
if no error appears, the `scoringutils` is installed correctly.

## Make R configuration permanent

Create a profile file:
```bash
nano ~/.Rprofile
```

Put the following line inside and save the file:
```
.libPaths(c("~/R/x86_64-pc-linux-gnu-library/4.4", .libPaths()))
```
Now users can simply load the R module and run EpiBenchmark without repeating the library configuration in Longleaf.

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
epibench setup --help
epibench score --help
epibench plot --help
```

Deactivate the environment when finished:

```bash
deactivate
```
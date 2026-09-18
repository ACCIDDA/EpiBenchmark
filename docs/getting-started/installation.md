# Installation

EpiBenchmark uses a standard Python installation flow. All functionality,
including forecast scoring, runs within the installed Python environment.

## Requirements
- Python 3.10 or later
- Git

## Quick Start
```bash
git clone https://github.com/ACCIDDA/EpiBenchmark.git
cd EpiBenchmark
uv sync
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

Alternatively, users can run commands without activating the virtual environment when using `uv`:

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
epibench
epibench --help
```
Users can also verify the available subcommands:

```bash
epibench create --help
epibench score --help
epibench plot --help
```

## Remove the virtual environment
Deletes the local `.venv` directory, allowing users to create a fresh virtual environment.

### Windows
If Command Prompt:
```bash
rmdir /s /q .venv 
```

If PowerShell:
```bash
Remove-Item -Recurse -Force .venv (PowerShell)
```

### macOS/Linux
```bash
rm -rf .venv
```

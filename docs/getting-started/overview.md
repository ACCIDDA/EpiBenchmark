# EpiBenchmark Overview

Once completing the installation instructions, you will have all EpiBenchmark commands available to you (see: `epibench --help`). The commands fall into two groups: those that **build a challenge** and those that **use a challenge**.

## Building a challenge

- `epibench setup`: A command that fetches and organizes ground truth data (of a specificed vintage) from a forecasting hub. In running this command with your specifications, you will have the un-backfilled ground truth data necessary to execute model runs from any date of reference. [Use it now!](../workflows/epibench-setup.md)

## Using a challenge

- `epibench list`: Lists the challenges available in the bundled **challenge library**. [Learn more](challenge-library.md) and browse the [challenge catalog](../challenges.md).
- `epibench fetch`: Downloads a challenge's data files from Zenodo. [Learn more](challenge-library.md).
- `epibench score`: A command that scores model forecast data with a weighted interval score (WIS) and compiles all information into a CSV output file. [Use it now!](../workflows/epibench-score.md)
- `epibench plot`: A command that, when given an `epibench score` CSV output file, will generate a set of plots for the visual analysis of model performance. [Use it now!](../workflows/epibench-plot.md)

While they are written to build off one another, all of the EpiBenchmark workflows can be run independently (i.e., `epibench setup` is not a pre-requesite for `epibench score`, etc.).

The `setup`, `score`, and `plot` commands each take a single required `--config-path` flag — the absolute path to a YAML configuration file you create. The configuration file for each command is slightly different; visit the [Configuration templates](configuration-templates.md) page to get copy/pasteable templates, or visit 'Workflows' for thorough explanation of configuration keys.

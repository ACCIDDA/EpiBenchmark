# EpiBench Overview

Once completing the installation instructions, you will have all EpiBench commands available to you (see: `epibench --help`). The EpiBench package has 3 primary functionalities, each with its own `epibench` sub-command:

- `epibench setup`: A command that fetches and organizes ground truth data (of a specificed vintage) from a forecasting hub. In running this command with your specifications, you will have the un-backfilled ground truth data necessary to execute model runs from any date of reference. [Use it now!](../workflows/epibench-setup.md)
- `epibench score`: A command that scores model forecast data with a weighted interval score (WIS) and compiles all information into a CSV output file. [Use it now!](../workflows/epibench-score.md)
- `epibench plot`: A command that, when given an `epibench score` CSV output file, will generate a set of plots for the visual analysis of model performance. [Use it now!](../workflows/epibench-plot.md)

While they are written to build off one another, all of the EpiBench workflows can be run independently (i.e., `epibench setup` is not a pre-requesite for `epibench score`, etc.). 

Each command (`epibench setup`, `epibench score`, `epibench plot`) has only one flag – `--config-path`; which is a required flag. That is, when you run any of the commands, you will have to pass the absolute path to a configuration file you have created in order to execute the logic. The configuration file (YAML) for each command is slightly different. Visit the [Configuration templates](configuration-templates.md) page to get copy/pasteable templates for each command, or visit 'Workflows' for thorough explanation of configuration keys. 

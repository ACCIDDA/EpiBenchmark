# EpiBenchmark Overview

Once completing the installation instructions, you will have all EpiBenchmark commands available to you (see: `epibench --help`). EpiBenchmark allows users to interact with its benchmarking framework in two distinct ways: either through a challenge defined in our library, or through a challenge that they have defined themselves. The challenges in our [challenge library](../challenge-information/challenges.md) are comprised of a set combination of pathogen, dates, locations, horizons, and quantiles. In order to score your model data against a library challenge, your model data must have forecasts for all of the facets defined in the challenge. Alternatively, and more flexibly, you may define challenges/fetch ground truth for personal use, or score + plot model data unrelated to a challenge.

## Using a library challenge

- `epibench list`: Lists the challenges available in the bundled **challenge library**. [Learn more and browse the challenge catalog](../challenge-information/challenges.md).
- `epibench fetch <challenge-id> --output-path`: Downloads a bundled challenge to a local directory
    - A challenge's data files include all the data you need to run your model for a challenge, including instruction files for an agent
- `epibench score <challenge-id> --model-data-path --model-name --output-path`: A command that scores model forecast data with a weighted interval score (WIS) and compiles all information into two CSVs:
    - `EpiBenchmark_scorecard.csv`: a scorecard, with one value for each metric defined in the challenge metrics
    - `EpiBenchmark_scores.csv`: a scores file, with all scores for all unique forecast units included in your model data
    - Note that your model data must contain every forecast unit combination defined in a challenge in order to be scored against it
- `epibench plot <challenge-id> --score-file-path --output-path`: Using your `EpiBenchmark_scores.csv` output produced from a library challenge scoring run, generate a set of plots for the visual analysis of your model performance in a library challenge. Invoking the `<challenge-id>` in your command will include the scores for all of the hub-submitted models that have full coverage of the challenge definition to allow for easy comparison. If you wish to visualize your scores alone, simply run without the `<challenge-id>` (i.e., `epibench plot --score-file-path --output-path`).

When scoring model data for a library challenge, you may only submit one model's data at a time

## Building your own challenge

- `epibench create --config-path`: A command that reads a user-configured ground truth file from a forecasting hub, applies the requested vintaging method, and writes standardized ground truth for model runs at the requested reference dates. The challenges you create with `epibench create` differ from our library challenges, which are static and represent fixed forecasting requirements.
-  `epibench score --config-path` to score any model output
- `epibench plot --score-file-path --ouptut-path` to visualize your scores. The baseline model for the corresponding hub will alwasy be included in scoring and plotting output.


When using `epibench create` or `epibench score` outside of a library challenge, pass a single required `--config-path` flag – the path to a YAML configuration file with the parameters of each run. The configuration file for each command is slightly different; visit the [Configuration templates](configuration-templates.md) page to get copy/pasteable templates, or visit 'Workflows' for thorough explanation of configuration keys.


While each command is written to build off the others, all of the EpiBenchmark workflows can be run independently (i.e., `epibench create` is not a pre-requesite for `epibench score`, etc.).

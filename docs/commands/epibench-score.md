# `epibench score`

The command `epibench score` evaluates model output against ground truth data using the R package `scoringutils`, producing scoring metrics for every unique forecast unit (a forecast unit is a unique combination of model, reference_date, target_end_date, location, and horizon). In order to score forecasts with EpiBenchmark, your model data must be in the [Hubverse format]().

As is delineated in the [EpiBenchmark Overview](../getting-started/overview.md), there are two ways to use `epibench score`: The first is to score model data against a library challenge (one model at a time), and the second is to define your own scoring config to set the parameters of your scoring run and then score your model(s) against this (any amount of models at a time). When doin the former, EpiBenchmark enforces strict checks that all forecast units written in the challenge defnition are present in your model data. That is, if you are missing a single location, quantile, horizon, etc. for any forecast, `epibench score` will fail. This is done to maintain the validity of the scoring output. 

## Extra dependencies

The EpiBenchmark scoring workflow uses CRAN packages `scoringutils`, and `purrr`. Before running `epibench score`, make sure:

- EpiBench is installed in an activated Python virtual environment
- `Rscript` is available on your `PATH`
- the CRAN packages `scoringutils` and `purrr` are installed for that `Rscript`

Install the required R packages if needed:

```bash
Rscript -e 'install.packages(c("scoringutils", "purrr"))'
```

Verify that they load:

```bash
Rscript -e 'library(scoringutils); library(purrr)'
```

If scoring fails because `Rscript` is missing, install R and make sure the
`Rscript` executable is on your `PATH`.

If scoring fails because `scoringutils` or `purrr` is missing, install them in
the same R environment used by the `Rscript` command above.

## Config file

When using `epibench score` via a configuration file, you will have to set the following keys:

* `hub_path`: a path to a local hub repo clone, or to a hub GitHub repo URL 
* `evaluation_start_date`: at which date you would like to start evaluating the model data (inclusive,  expressed as `YYYY-MM-DD`)
* `evaluation_end_date`: at which date you would like to stop evaluating the model data (inclusive, expressed as `YYYY-MM-DD`)
* `target`: which data target you would like to score. `epibench score` presently only scores one target at a time, and the target provided in your config must be an exact match for values found in your model data.
* `models`: a dictionary where keys are the name you would like to use to refer to the model, and values are the paths to the model data. The paths may point to a single CSV file, or to a directory of CSV file(s); during processing, all data will be concatenated so it does not matter if CSVs are stored separately.
* `baseline_model`: the name (exact character match) of the baseline model for your hub. The baseline model is necessary in the calculation of relative WIS.
* `include_models` (optional): as a list, optionaly pass the names of submitting models in your hub to be included in scoring (**hint, including an ensemble model can be useful for visualization later). You do not need to specify the baseline model in the `include_models` key; it will be included regardless.
* `output_path`: the path where you would like output to be saved

See our [configuration templates](../getting-started/configuration-templates.md) for a copy-pasteable template of the `epibench score` config.

## Output

The output of an `epibench score` run depends on whether the run was associated with a library challenge or not. If you ran `epibench score` for a library challenge, you can expect two CSVs and one Markdown file of output:

* `EpiBenchmark_scores.csv`: A CSV file with score data for every forecast unit for every model included in the scoring run
* `EpiBenchmark_scorecard.csv`: A CSV file with a column for every scoring metric defined in that library challenge, and a single row of values
* `summary.md`: A human-readable markdown file describing the data used for scoring, what was filtered out, etc.

For config-based scoring, the required baseline and any models named in
`include_models` are restricted to the union of facets found across all models
in `models`.
A facet is one forecast unit at one specific quantile level, so matching uses
reference date, target end date, location, horizon, and quantile level. The
summary reports how many facets were retained and removed for each included hub
model, and warns when an included model is missing any facet from that union
set. After this paring, every retained baseline or included model is subjected
to the same quantile validation as the submitted models. Quantile-validation
failure in any submitted, baseline, or included model stops the scoring run.

If you ran `epibench score --config-path`, only the `EpiBenchmark_scores.csv` and `summary.md` files will be produced. EpiBenchmark will not overwrite pre-existing files, and will therefore exit with error if the `output_path` already contains scoring output.

`Epibenchmark_scores.csv` will have a set of columns that serve as a composite key, and therefore make up a forecast unit: `model`, `reference_date`, `target_end_date`, `location`, and `horizon`. It will also have nine score columns:

| Column name | Description |
|---|---|
| `wis` | Weighted Interval Score for a single forecast unit. Lower is better. |
| `overprediction` | WIS penalty for forecasts that are too high. Lower is better. |
| `underprediction` | WIS penalty for forecasts that are too low. Lower is better. |
| `dispersion` | WIS component reflecting forecast spread or interval width. Lower values indicate sharper forecasts. |
| `bias` | Directional tendency of the forecast. Negative values indicate underprediction, positive values indicate overprediction. |
| `interval_coverage_50` | Whether the observed value falls within the 50% prediction interval (`True`/`False`). |
| `interval_coverage_95` | Whether the observed value falls within the 95% prediction interval (`True`/`False`). |
| `ae_median` | Absolute error of the median prediction. Lower is better. |
| `rwis` | Relative WIS compared with the baseline model for the same forecast unit. Values below `1` are better than baseline. |

These scores can be interpreted separaely by the user, and/or visualized with `epibench plot`.

## example usages

When scoring your model against a library challenge:
```bash
epibench score epb_flu_inchosp_2024-2025_dev --model-data-path "my/model/data/" --model-name "my-model" --output-path "/Users/user/Desktop"
```

When scoring model forecast data that does not belong to a library challege:
```bash
epibench score --config-path
```
where `--config-path` is the path to your YAML configuration file.

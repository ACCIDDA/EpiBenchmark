# `epibench score`

The command `epibench score` evaluates model output against ground truth data using EpiBenchmark's in-process Python scoring implementation. It produces scoring metrics for every unique forecast unit (a forecast unit is a unique combination of model, reference date, target end date, location, and horizon). To score forecasts with EpiBenchmark, model data must use the [Hubverse format](https://hubverse.io/).

As described in the [EpiBenchmark Overview](../getting-started/overview.md), there are two ways to use `epibench score`: score one model against a library challenge, or define a scoring configuration and evaluate one or more models. For library challenges, EpiBenchmark enforces strict checks that every forecast unit in the challenge definition is present in the model data. A missing location, quantile, horizon, or other required facet causes the challenge scoring run to fail. This maintains the validity of the scorecard.

Scoring runs entirely within the Python environment created during EpiBenchmark installation, but logic mimics the [scoringutils R package](https://epiforecasts.io/scoringutils/articles/scoringutils.html).

## Config file

When using `epibench score` via a configuration file, you will have to set the following keys:

* `hub_path`: a path to a local hub repo clone, or to a hub GitHub repo URL 
* `evaluation_start_date`: at which date you would like to start evaluating the model data (inclusive,  expressed as `YYYY-MM-DD`)
* `evaluation_end_date`: at which date you would like to stop evaluating the model data (inclusive, expressed as `YYYY-MM-DD`)
* `target`: which data target you would like to score. `epibench score` presently only scores one target at a time, and the target provided in your config must be an exact match for values found in your model data.
* `models`: a dictionary where keys are the name you would like to use to refer to the model, and values are the paths to the model data. The paths may point to a single CSV file, or to a directory of CSV file(s); during processing, all data will be concatenated so it does not matter if CSVs are stored separately.
* `baseline_model`: the name (exact character match) of the baseline model for your hub. The baseline model is necessary in the calculation of relative WIS.
* `include_models` (optional): as a list, optionally pass the names of submitting models in your hub to include in scoring. Including an ensemble model can be useful for later visualization. You do not need to specify the baseline model in `include_models`; it is included automatically.
* `output_path`: the path where you would like output to be saved

See our [configuration templates](../getting-started/configuration-templates.md) for a copy-pasteable template of the `epibench score` config.

## Scoring behavior

The scorer validates that forecast data contain the required forecast-unit,
observation, prediction, and quantile columns. Quantiles must be numeric,
unique within each forecast unit, and between `0` and `1`. Invalid forecast
structure stops the scoring run with an error.

Each metric is evaluated independently once the forecast structure is valid.
If a quantile grid cannot support a particular metric, EpiBenchmark emits a
warning, records that metric as missing, and continues calculating the other
metrics. For example:

* WIS and its components require symmetric lower and upper quantiles.
* 50% interval coverage requires the `0.25` and `0.75` quantiles.
* 95% interval coverage requires the `0.025` and `0.975` quantiles.
* Median absolute error requires the `0.5` quantile.
* Bias requires quantiles on both sides of `0.5` and nondecreasing predictions.

Forecast units with different valid quantile grids are scored in separate
batches. The score output always retains the complete column schema, with
missing values for metrics that could not be calculated.

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

These scores can be interpreted separately or visualized with `epibench plot`.

## example usages

When scoring your model against a library challenge:
```bash
epibench score epb_flu_inchosp_2024-2025_dev --model-data-path "my/model/data/" --model-name "my-model" --output-path "/Users/user/Desktop"
```

When scoring model forecast data that does not belong to a library challenge:
```bash
epibench score --config-path
```
where `--config-path` is the path to your YAML configuration file.

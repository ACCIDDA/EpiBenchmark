# Python API reference

Install `EpiBenchmark` as described in the [installation guide](getting-started/installation.md), then `import epibench`.

## Challenge library

### `list_challenges() -> list[dict[str, ChallengeInfo]]`

Return a ditionary of library challenges in ID order. Each list item maps one challenge name to information about the contents of that challenge: `{"hub": str, "target": str, "dates": list[str]}`. Dates refer to `reference_dates` required for that challenge. 

```python
import epibench

for entry in epibench.list_challenges():
    challenge_id, info = next(iter(entry.items()))
    print(challenge_id, info["target"], info["dates"])
```

### `fetch_challenge(challenge_name: str) -> Challenge`

Load a library challenge into memory. Pass a name from `list_challenges()` as the parameter. The result includes the bundled instructions, notes regarding the challenge, and vintaged ground truth data files in the `.tasks` attribute. An unknown challenge name will raise a `click.ClickException`.

```python
challenge = epibench.fetch_challenge("epb_flu_inchosp_2024-2025_dev")
print(challenge.instructions, challenge.notes)
for task in challenge.tasks:
    print(task.name, task.gt_df.shape)
```

### `Challenge` and `Task`

`Challenge` is a mutable dataclass with `instructions: str | None`, `tasks: list[Task]`, and `notes: str | None`. Instructions and notes exist for library challenges, and are `None` for results of user `create()` function calls. `Task` is a mutable dataclass with `name: str` (a `YYYY-MM-DD` reference date) and `gt_df: pandas.DataFrame` (ground truth data vintaged for that date).

#### `Challenge.save(output_path: str | Path | None = None) -> None`

Write each task to `gt/<reference-date>/<YYYYMMDD>_gt.csv` beneath `output_path`, or the current working directory when `output_path` is omitted. The output directory is created if needed. A pre-existing `gt` directory found at the output path will cause a `FileExistsError`. 

## Create a challenge

### `create(*, hub_path, target, dates, ground_truth_file, observed_column_name, location_column_name, date_column_name, vintaging, vintaging_method=None, vintaging_offset=None) -> Challenge`

Build ground-truth tasks from a hub and return them in memory. Using this functionality, users may specify their own retrievals of vintaged ground truth data. `create()` parameters are all keyword arguments.

| Argument | Type | Meaning |
| --- | --- | --- |
| `hub_path` | `str \| Path` | Path to a local hub directory or link to a GitHub hub repository URL; the hub must contain `target-data/`. |
| `target` | `str` | Data target to extract. |
| `dates` | `list[str] \| dict[str, str]` | a list of `YYYY-MM-DD` reference dates, or a dict containing keys: `start_date`, `end_date`, and frequencey (`freq`). `freq` must be referenced as `"<num> week"` or `"<num> weeks"`.|
| `ground_truth_file` | `str` | Path to the ground truth data file you would like ground truth data to be pulled from. Must be relative to the root directory of the specified hub. |
| `observed_column_name` | `str` | Name of the column in the specified ground truth data file that contains the observed values. |
| `location_column_name` | `str` | Name of the column in the specified ground truth data file that contains the location values. |
| `date_column_name` | `str` | Name of the column in the specified ground truth data file that contains the date values. |
| `vintaging` | `bool` | Whether or not to vintage ground truth to each reference date provided. Setting to `False` will retrieve most updated ground truth data to cover your date span. |
| `vintaging_method` | `"as_of" \| "checkout" \| None` | Required when `vintaging=True`. |
| `vintaging_offset` | `int \| None` | For each reference date, how many days before/after should ground truth retrieval be cut off. Pass `0` for no offset, `-3` for 3 days before the reference date, etc. |

Dates must be readable into `YYYY-MM-DD` format, no later than the current date, and be valid reference dates for your hub and season. List dates are deduplicated and sorted. A create run must stay within one July 1–June 30 season. For known hubs, the bundled date library also restricts reference dates to the hub's recorded weekly submission window. Each task contains only ground truth with `target_end_date` from that season's July 1 through its reference date, inclusive. Call `Challenge.save()` to save the resulting ground truth data files to your machine.

```python
challenge = epibench.create(
    hub_path="/path/to/hub",
    target="wk inc flu hosp",
    dates=["2024-11-23", "2024-11-30"],
    ground_truth_file="target-data/time-series.csv",
    observed_column_name="value",
    location_column_name="location",
    date_column_name="target_end_date",
    vintaging=True,
    vintaging_method="as_of",
    vintaging_offset=-3
)
challenge.save("results/ground-truth")
```

Be sure to use a ground-truth path and column names that match your hub. If using `vintaging_method="checkout"`, be certain that your ground truth data file exists across your entire span of dates.

## Score forecasts

Much like the command line scoring interface, there are two ways to score quantile model data with EpiBenchmark: against a library challenge (strict validation) or in user-defined parameters (non-strict validation). Both scoring functions return an in-memory `ScoreResult`. Forecast inputs must use the [Hubverse format](https://hubverse.io/); for more information on validation, visit the [scoring guide](commands/epibench-score.md). Call `ScoreResult.save()` to write files locally.

### `read_forecasts(path: str | Path) -> pandas.DataFrame`

Read a forecast CSV or Parquet file for either scoring function. `horizon`, `location`, and `output_type_id` become strings, preserving identifiers such as `01`. Other columns retain their inferred CSV types or stored Parquet types. Scoring validates and normalizes dates and numeric values later.

```python
forecast_df = epibench.read_forecasts("/path/to/forecasts.csv")
```

### `score(*, hub_path, evaluation_start_date, evaluation_end_date, target, models, baseline_model, include_models=None) -> ScoreResult`

Run scoring with no relationship to a library challenge. Model data will not required to have the same forecast units (i.e., all data across all provided models will be scored together, regardless if all models forecast across the same locations, horizons, quantiles, etc.) All arguments except `include_models` are required keyword arguments.

| Argument | Type | Meaning |
| --- | --- | --- |
| `hub_path` | `str \| Path` | Path to a local hub directory or link to a GitHub hub repository URL. |
| `evaluation_start_date`, `evaluation_end_date` | `str \| date \| datetime` | Inclusive evaluation window; strings use `YYYY-MM-DD`. The end must be at least seven days after the start. Evaluation windows should span the `target_end_dates` of your model forecasts, not the reference dates. |
| `target` | `str` | Data target to score. |
| `models` | `Mapping[str, pandas.DataFrame]` | Submitted model name mapped to an in-memory DataFrame of Hubverse forecast data. |
| `baseline_model` | `str` | Name of the baseline model for your hub (used to calculate relative WIS). |
| `include_models` | `Sequence[str] \| None` | Names of other models from your hub you would like included in your scoring output. |

```python
forecast_df = epibench.read_forecasts("/path/to/forecasts.csv")
result = epibench.score(
    hub_path="/path/to/hub",
    evaluation_start_date="2024-11-23",
    evaluation_end_date="2024-12-21",
    target="wk inc flu hosp",
    models={"my-model": forecast_df},
    baseline_model="FluSight-baseline",
)
print(result.summary)
print(result.scores.head())
result.save("results/scoring")
```

Standard scoring sets `mode` to `"standard"` and `scorecard` to `None`.

### `score_challenge(challenge_name: str, model_data: pandas.DataFrame, model_name: str) -> ScoreResult`

Run scoring for a model against a library challenge. `challenge_name` is a valid EpiBenchmark challenge name, `model_data` is an in-memory DataFrame of Hubverse forecast data, and `model_name` is the name that you would like to use to identify the submitted model. The challenge supplies the target, dates, required forecast facets, quantiles, and baseline. This route validates complete challenge coverage and computes a one-row scorecard. 

```python
forecast_df = epibench.read_forecasts("/path/to/forecasts.csv")
result = epibench.score_challenge(
    "epb_flu_inchosp_2024-2025_dev",
    forecast_df,
    "name-of-my-model",
)
print(result.summary)
print(result.scorecard)
result.save("results/challenge-scoring")
```

### `ScoreResult`

`ScoreResult` is a mutable dataclass:

| Field | Type | Meaning |
| --- | --- | --- |
| `mode` | `"standard" \| "challenge"` | Scoring route used. |
| `scores` | `pandas.DataFrame` | Per-forecast-unit scores, including the baseline. |
| `scorecard` | `pandas.DataFrame \| None` | One-row challenge scorecard; `None` for non-library challenge scoring. |
| `summary` | `str` | Markdown-formatted summary of filtering and exclusions. |
| `excluded_files` | `frozenset[str]` | Forecast data sources excluded during loading or validation. |
| `output_dir`, `scores_path`, `scorecard_path`, `summary_path` | `Path \| None` | Locations populated by `save()`; initially `None`. `scorecard_path` stays `None` for standard scoring. |

#### `ScoreResult.save(output_path: str | Path | None = None) -> None`

Write `EpiBenchmark_scores.csv` and `summary.md` to `output_path`, or the current working directory. Challenge results also write `EpiBenchmark_scorecard.csv`. The directory is created if needed; an existing output file raises `FileExistsError`. Path fields (`output_dir`, `scores_path`, `scorecard_path`, `summary_path`) are populated after a successful save.

## Plot scores

Plotting takes an in-memory DataFrame (such as `ScoreResult.scores`) and writes `EpiBenchmark_plots.pdf`. Required score data columns are `model`, `reference_date`, `target_end_date`, `location`, `horizon`, `wis`, `overprediction`, `underprediction`, `dispersion`, and `rwis`. See the [plotting guide](commands/epibench-plot.md) for more.

### `plot(score_file: pandas.DataFrame, output_path: str | Path | None = None) -> Path`

Validate scores, produce summary figures, and return the PDF path. `output_path` defaults to the current working directory. An existing PDF raises `FileExistsError`.

```python
pdf_path = epibench.plot(result.scores, "results/plots")
```

### `plot_challenge(challenge_name: str, score_file: pandas.DataFrame, output_path: str | Path | None = None) -> Path`

Plot scores from a library challenge scoring run; automatically includes scores for hub-submitting models that complete (w.r.t the challenge definition). `score_file` must contain the challenge baseline and at least one non-baseline model. User-provided models receive a `-USER-PROVIDED` suffix in the combined plot data. The function returns the PDF path and does not overwrite an existing PDF.

```python
pdf_path = epibench.plot_challenge(
    "epb_flu_inchosp_2024-2025_dev",
    result.scores,
    "results/challenge-plots",
)
```

To plot saved scores, load the CSV into a DataFrame while preserving location codes as strings:

```python
import pandas as pd

scores = pd.read_csv("results/scoring/EpiBenchmark_scores.csv", dtype={"location": str})
epibench.plot(scores, "results/plots")
```

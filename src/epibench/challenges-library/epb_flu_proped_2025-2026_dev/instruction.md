# EpiBenchmark challenge: `epb_flu_proped_2025-2026_dev`

This challenge is designed for [EpiBenchmark](https://accidda.github.io/EpiBenchmark/). Before preparing forecasts or scoring them, install the EpiBench command-line interface as described in the EpiBenchmark documentation.

> **Development challenge — not finalized.** This is a `dev` release for testing. Its definition, ground truth, and scoring may change before a stable versioned release, and it is not yet a citable benchmark.

The challenge is derived from the 2025–2026 [FluSight Forecast Hub](https://github.com/cdcepi/FluSight-forecast-hub). It evaluates forecasts of the weekly proportion of emergency department (ED) visits due to influenza, using the target name `wk inc flu prop ed visits`. The numerator is visits with an influenza discharge diagnosis; the denominator is total ED visits. The hub supplies this target as decimal proportions between 0 and 1 (for example, `0.01` means 1% of ED visits).

## Challenge details

| Field | Value |
| --- | --- |
| Challenge name | `epb_flu_proped_2025-2026_dev` |
| Source hub | [FluSight Forecast Hub](https://github.com/cdcepi/FluSight-forecast-hub), 2025–2026 season |
| Pathogen | Influenza |
| Target | `wk inc flu prop ed visits` |
| Frequency | Weekly |
| Reference-date span | 2025-11-22 to 2026-05-30 (28 continuous weekly dates) |
| Target-end-date span for forecasts | 2025-11-22 to 2026-06-20 |
| Locations | 51 jurisdictions, including `US` |
| Horizons | 0, 1, 2, and 3 |
| Required forecast tasks | 5,712 (28 reference dates × 51 locations × 4 horizons) |
| Required quantile rows | 28,560 (5 quantiles per forecast task) |
| Provided ground truth | 47,787 observations across 28 vintages; one row per vintage/date/location/target key |
| Source truth file | `target-data/target-ed-visits-prop.csv` |
| Scoring truth | Latest-revised values reported by the source hub |

The required locations are 49 U.S. states, Washington D.C., and the U.S. as a whole. Missouri (`29`) and Puerto Rico (`72`) are excluded. Use the exact location list in the challenge JSON, preserving leading zeroes in two-digit FIPS codes and using `US` for the national forecast.

## Ground truth and forecast tasks

Fetch the challenge from the bundled library:

```bash
epibench fetch epb_flu_proped_2025-2026_dev --output-path challenges
```

The library stores all vintages in `gt.parquet`, with columns `target_end_date`, `location`, `target`, `observed`, and `reference_date`. The `reference_date` column identifies the vintage. The fetch command expands these into the per-date Parquet files listed in `task_list.csv`, beneath `gt/<reference_date>/`. Each expanded file contains the four observation columns without `reference_date`.

**Ground-truth revision selection.** Each vintage uses the repository checkout three days before its reference date. Where the source includes `as_of`, only the latest revision on or before that cutoff is retained for each observation. Identical repeated values are collapsed; conflicting values that cannot be resolved by `as_of` cause generation to fail.

For each forecast reference date, use the corresponding ground-truth vintage and information available by that date. Later vintages may contain revisions or observations unavailable at earlier dates. Historical observations are restricted to the season beginning July 1, 2025, through the reference date; reporting lags can make the latest observed week earlier than the reference date.

Provide forecasts for every reference date in `task_list.csv`, every required location, and every horizon. Horizon 0 is the reference week; horizons 1, 2, and 3 are the following three weeks. The target end date is the Saturday ending the corresponding US CDC/MMWR epiweek:

```text
target_end_date = reference_date + horizon * 7 days
```

Submit one CSV file with exactly these columns:

```text
reference_date,target,horizon,target_end_date,location,output_type,output_type_id,value
```

Each row represents one quantile forecast. Use `quantile` for `output_type`, and set `output_type_id` to one of `0.025`, `0.25`, `0.5`, `0.75`, or `0.975`. Every reference-date/location/horizon combination must have all five quantiles. Values must be decimal proportions between 0 and 1, and quantile values must not decrease as the quantile level increases.

Use `wk inc flu prop ed visits` for `target`. Each row should follow this pattern:

```text
2025-11-22,wk inc flu prop ed visits,0,2025-11-22,01,quantile,0.025,0.001
```

## Model name and metadata

Use `--model-name` to identify the model in the score output. For reproducibility, use the model name in the filename, for example `<model_name>.csv` or `<model_name>.parquet`, and keep a separate `<model_name>.metadata.json` file beside it with the model name, model description, model version, forecast-generation date, and the software or data versions used. Do not add metadata as extra CSV columns.

## Scoring

After producing the forecast CSV, run the following command from the repository root. Replace `<model_name>` with your model name.

```bash
epibench score epb_flu_proped_2025-2026_dev \
  --model-data-path "challenges/epb_flu_proped_2025-2026_dev/model-output/<model_name>.csv" \
  --model-name "<model_name>" \
  --output-path "results/epb_flu_proped_2025-2026_dev/<model_name>"
```

Forecasts are scored with the Weighted Interval Score (WIS) together with 50% and 95% prediction-interval coverage, and are compared against the hub baseline model (`FluSight-baseline`). The scoring truth is retrieved separately from the source hub; the bundled vintages provide historical inputs for forecasting.

The command writes `EpiBenchmark_scores.csv`, `EpiBenchmark_scorecard.csv`, and `summary.md` to the output directory. It will not overwrite existing score files.

**Report your scorecard.** The deliverable for this challenge is the `EpiBenchmark_scorecard.csv` produced by `epibench score epb_flu_proped_2025-2026_dev` — it is the official record of your model's performance and is what should be submitted or reported.

## Source documentation

- [FluSight Forecast Hub](https://github.com/cdcepi/FluSight-forecast-hub)
- [FluSight README — ED target definition and proportion scale](https://github.com/cdcepi/FluSight-forecast-hub/blob/main/README.md#prediction-targets)
- [FluSight ED proportion target data](https://github.com/cdcepi/FluSight-forecast-hub/blob/main/target-data/target-ed-visits-prop.csv)
- [FluSight model-output directory](https://github.com/cdcepi/FluSight-forecast-hub/tree/main/model-output)
- [Hubverse](https://hubverse.io/)

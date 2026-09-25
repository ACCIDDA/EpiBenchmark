# EpiBenchmark challenge: `epb_rsv_inchosp_2025-2026_dev`

This challenge is designed for [EpiBenchmark](https://accidda.github.io/EpiBenchmark/). Before preparing forecasts or scoring them, install the EpiBench command-line interface as described in the EpiBenchmark documentation.

> **Development challenge — not finalized.** This is a `dev` release for testing. Its definition, ground truth, and scoring may change before a stable versioned release, and it is not yet a citable benchmark.

The challenge is derived from the 2025–2026 [RSV Forecast Hub](https://github.com/cdcgov/rsv-forecast-hub). It evaluates forecasts of weekly incident RSV hospital admissions, using the target name `wk inc rsv hosp`.

## Challenge details

| Field | Value |
| --- | --- |
| Challenge name | `epb_rsv_inchosp_2025-2026_dev` |
| Source hub | [RSV Forecast Hub](https://github.com/cdcgov/rsv-forecast-hub), 2025–2026 season |
| Pathogen | Respiratory syncytial virus (RSV) |
| Target | `wk inc rsv hosp` |
| Frequency | Weekly |
| Reference-date span | 2025-11-22 to 2026-05-30 |
| Forecast-date span | 2025-11-22 to 2026-06-20 |
| Locations | 52 jurisdictions, including `US` |
| Horizons | 0, 1, 2, and 3 |
| Required forecast tasks | 5,824 (28 reference dates × 52 locations × 4 horizons) |
| Provided ground truth | Vintaged (`as_of` each reference date); see `gt/` and `task_list.csv` |
| Scoring truth | Final (latest-revised) values reported by the source hub |

Provide forecasts for every reference date in `task_list.csv`, every required location, and every horizon. Horizon 0 is the reference week; horizons 1, 2, and 3 are the following three weeks. The target end date is the Saturday ending the corresponding US CDC/MMWR epiweek:

```text
target_end_date = reference_date + horizon * 7 days
```

Submit one CSV file with exactly these columns:

```text
reference_date,target,horizon,target_end_date,location,output_type,output_type_id,value
```

Each row represents one quantile forecast. Use `quantile` for `output_type`, and set `output_type_id` to one of `0.05`, `0.25`, `0.5`, `0.75`, or `0.95`. Every reference-date/location/horizon combination must have all five quantiles. Values are non-negative admission counts, and quantile values must not decrease as the quantile level increases.

Use `wk inc rsv hosp` for `target`. Locations must use the two-digit FIPS codes defined by the challenge, preserving leading zeroes, or `US` for the national forecast.

Each row should follow this pattern:

```text
2025-11-22,wk inc rsv hosp,0,2025-11-22,01,quantile,0.05,10
```

## Model name and metadata

Use `--model-name` to identify the model in the score output. For reproducibility, use the model name in the filename, for example `<model_name>.csv` or `<model_name>.parquet`, and keep a separate `<model_name>.metadata.json` file beside it with the model name, model description, model version, forecast-generation date, and the software or data versions used. Do not add metadata as extra CSV columns.

## Scoring

After producing the forecast CSV, run the following command from the repository root. Replace `<model_name>` with your model name.

```bash
epibench score epb_rsv_inchosp_2025-2026_dev \
  --model-data-path "challenges/epb_rsv_inchosp_2025-2026_dev/model-output/<model_name>.csv" \
  --model-name "<model_name>" \
  --output-path "results/epb_rsv_inchosp_2025-2026_dev/<model_name>"
```

Forecasts are scored with the Weighted Interval Score (WIS) together with 50% and 90% prediction-interval coverage, and are compared against the hub baseline model (`RSVHub-baseline`).

The command writes `EpiBenchmark_scores.csv`, `EpiBenchmark_scorecard.csv`, and `summary.md` to the output directory. It will not overwrite existing score files. It requires `Rscript`, the R package `scoringutils`, and network access to clone or update the source hub.

**Report your scorecard.** The deliverable for this challenge is the `EpiBenchmark_scorecard.csv` produced by `epibench score epb_rsv_inchosp_2025-2026_dev` — it is the official record of your model's performance and is what should be submitted or reported.

## Source documentation

- [RSV Forecast Hub](https://github.com/cdcgov/rsv-forecast-hub)
- [RSV README](https://github.com/cdcgov/rsv-forecast-hub/blob/main/README.md)
- [RSV model-output directory](https://github.com/cdcgov/rsv-forecast-hub/tree/main/model-output)
- [Hubverse](https://hubverse.io/)

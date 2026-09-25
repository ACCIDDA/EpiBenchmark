# `epibench create`

Running `epibench create --config-path "../.."` creates model-input ground truth from a file you specify in a forecasting hub. It filters and vintages that file for each requested reference date, then writes one standardized ground truth CSV per date.

## Config file 

The configuration file for an `epibench create` run takes in the following keys:

* `hub_path`: a path to a local hub repository clone, or a hub GitHub repository URL
* `challenge_name`: whatever name you would like to give the "challenge" you are defining
* `target`: the single target for this create run. If the source file contains `target`, it must exactly match this value.
* `ground_truth_file`: a relative, hub-root path to the CSV or Parquet ground truth file. Absolute paths and paths outside the hub are rejected.
* `observed_column_name`: the source column containing observed values.
* `location_column_name`: the source column containing locations.
* `date_column_name`: the source column containing target end dates.
* `dates`: which dates of reference you want to fetch ground truth data for (`YYYY-MM-DD`)
    * this can be passes as a list of individually-specified dates, 
    * or as a dictionary with three keys: `start_date`, `end_date`, `freq`
        * `freq` format must be `"<n> weeks"` or `"<n> week"`
    * **important: your dates must match the submission cadence of the hub you have provided for a given season.** If your `epibench create` run spans more than a season, the process will exit and ask that you limit to one season at a time. The boundary between seasons is set at June 30 (end of season) and July 1 (start of new season).
* `vintaging`: `TRUE` or `FALSE`. Set `TRUE` to prepare a distinct ground truth vintage for every reference date.
* `vintaging_method`: when vintaging, choose `"as_of"` or `"checkout"`.
    * `"as_of"` reads the configured current file. It requires an `as_of` column and uses the latest revision at or before each cutoff date.
    * `"checkout"` checks out the hub at each cutoff date, then reads the configured file from that historical repository state. The file must exist at every requested checkout. If it has an `as_of` column, the same latest-eligible-revision rule is applied.
* `vintaging_offset`: if vintaging, elect an integer vintaging offset
    * many hubs take forecasting submission a few days before the reported reference date (e.g., forecasts are made on Wednesday, but the reference date is the following Saturday, creating an offset of `-3` days). For maximum realism, you can inform `epibench create` of this and it will ensure you do not get any ground truth data that would have been filled in (e.g.) between the Wednesday and the Saturday.
    * if you would like no offset, pass `0`
    * when possible, `epibench create` will match you `vintaging_offset` value with the submisison cadence of the hub and give warning if your value does not match the hub

See our [configuration templates](../getting-started/configuration-templates.md) for a copy-pasteable template of the `epibench create` config.

## Source-file Requirements

Every source file read during the run must contain the configured observed, location, and date columns. The `as_of` method also requires an `as_of` column.

The source `target` column is optional. If it is present, EpiBench filters the file to the configured target and preserves that column. If it is absent from every file, EpiBench adds a `target` column with the configured target value and logs a warning that it could not verify the target. A run fails if some vintages have a `target` column and others do not.

When multiple revisions share a date and location, EpiBench retains the latest `as_of` version available at the cutoff. If `target` is present, it is also part of this revision key. When no `as_of` column exists, duplicate revision keys are rejected because there is no reliable way to select a vintage.

## Output

Upon a successful `epibench create` run, you can expect a single folder to appear at your `--output-path`. The folder will be named by whatever string you set as `challenge_name` in the configuration file, followed by a ten-character hash that is both unique to your specifications and reproducible. Within the folder, you would find the following nested structure: 

```
output_path/
└── my-covid-challenge_b7bb9fbf7c/
    ├── task_list.csv
    └── gt/ 
        ├── 2026-01-01/
        │   └── 20260101_gt.csv
        ├── 2026-01-08/
        │   └── 20260108_gt.csv
        ├── 2026-01-15/
        │   └── 20260115_gt.csv
        ├── 2026-01-22/
        │   └── 20260122_gt.csv
        └── 2026-01-29/
            └── 20260129_gt.csv
```

Where each requested date of reference has its own folder and file within the `gt/` directory, and the `task_list.csv` file give relative paths to ground truth data files for each date of reference.

Each generated ground truth file uses exactly these standardized columns: `target_end_date`, `location`, `target`, and `observed`. The configured source date, location, and observed columns are renamed during output preparation.
For each task, only observations with `target_end_date` from July 1 of its season through that task's reference date are returned. 

## example usage

An example config could look like this:
```bash
epibench create --config-path "path/to/create-config.yml"
```
where `--config-path` is the path to your YAML configuration file.

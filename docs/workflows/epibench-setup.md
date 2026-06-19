# `epibench setup`

`epibench setup` is a command that, when given a configuration file with a specified hub and dates, can fetch + organize vintaged ground truth data from a forecasting hub. That is, if you wanted to run your model on the ground truth influenza data that was available on date YYYY-MM-DD, `epibench setup` will visit the correct hub, check out the ground truth file from that day in the past, and return it to you in an organized hierarchy on your machine.

## Config file 

To run `epibench setup`, you will have to create a YAML configuration file with 4 keys: `hub`, `dates`, `vintaging`, and `output_path`. 

### hub

A key denoting which forecasting hub you would like your ground truth data fetched from. It must be, exactly, one of these options: [`flusight`, `rsv`, `covid19`, `flu metrocast`].

- `flusight` | pulls from the [FluSight Forecasting Hub repository](https://github.com/cdcepi/FluSight-forecast-hub)
- `rsv` | pulls from the [RSV Forecasting Hub repository](https://github.com/cdcgov/rsv-forecast-hub)
- `covid19` | pulls from the [COVID-19 Forecasting Hub repository](https://github.com/CDCgov/covid19-forecast-hub)
- `flu metrocast` | pulls from the [Flu Metrocast Hub repository](https://github.com/reichlab/flu-metrocast)

### dates

The dates key of the config takes the form of a dictionary with 3 required keys: `start_date`, `end_date`, and `freq`. This is where you can specify which date(s) you want ground truth fetched for. With values for start, end, and frequency, `epibench setup` will create a list of unique dates of reference to pull for. Notes on values:

- `start_date` and `end_date` should be expressed as `YYYY-MM-DD`
- `end_date` should come AFTER `start_date`, and both dates must be in the past/present
- `start_date` and `end_date` are inclusive on both ends
- The `freq` string must be specified as `n week` or `n weeks` where `n` is a positive, non-zero integer

e.g.:
```yaml
dates: {
    start_date: 2026-01-01, 
    end_date: 2026-01-30,
    freq: "1 week" 
} 
```

Passing a `start_date` of `2026-01-01` and an `end_date` of `2026-01-30` with a `freq` of `"1 week"` will result in 5 dates of reference 1 week apart: `2026-01-01`, `2026-01-08`, `2026-01-15`, `2026-01-22`, `2026-01-29`. 

Alternatively, if you wish to pass a list of explicit dates instead of a dictionary with key/values, you may do so as follows:
```yaml
dates: [2026-01-01, 2026-01-08, 2026-01-15, 2026-01-22, 2026-01-29]
```

### vintaging

A boolean indicating whether or not you would like your ground truth data to be vintaged. If `TRUE`, a separate ground truth file will be fetched for each date of reference reflecting only what was available on that date. If `FALSE`, only one ground truth data file will be fetched (whatever the most recent available data is that encompasses all of your dates of reference).

### output_path

The absolute path you would like output to be generated at.

## Example

An example config could look like this:
```yaml
---

hub: "flusight" 

dates: {
    start_date: 2026-01-01, 
    end_date: 2026-01-30,
    freq: "1 week" 
} 

vintaging: TRUE

output_path: "/Users/name/Desktop"
```

If your config file existed at absolute path `/absolute/path/to/config.yml`, you could run:
```bash
epibench setup --config-path "/absolute/path/to/config.yml"
```
which would result in an output folder created at `/Users/name/Desktop`, with the structure:
```
Desktop/
└── HASH-GOES-HERE/
    ├── challenges.csv 
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

where:

- `challenges.csv` is a table with two columns – `date` and `absolute_path_to_gt` – that has a row for each date of reference in the specified date range (2026-01-01, 2026-01-08, 2026-01-15, 2026-01-22, 2026-01-29), and absolute paths to the ground truth data pulled from the FluSight Forecast Hub **vintaged** to that date.
- `gt/` is a folder that contains sub-folders for each date of reference (sub-folders then contain the single ground truth CSVs)


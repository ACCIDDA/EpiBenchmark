# `epibench score`

COMING SOON 

`epibench score` evaluates model output against ground truth data using the R package `scoringutils`. You can use this feature to score multiple models' data at once, returning metrics related to WIS in one table.

## Requirements

Before running this command, make sure:

- EpiBench is installed in an activated Python virtual environment
- `Rscript` is available on your `PATH`
- the CRAN package `scoringutils` is installed for that `Rscript`

Install `scoringutils` if needed:

```bash
Rscript -e 'install.packages("scoringutils")'
```

Verify that it loads:

```bash
Rscript -e 'library(scoringutils)'
```

## Troubleshooting

If scoring fails because `Rscript` is missing, install R and make sure the
`Rscript` executable is on your `PATH`.

If scoring fails because `scoringutils` is missing, install it in the same R
environment used by the `Rscript` command above.

## Config file

To run `epibench score`, you will have to create a YAML configuration file with 6 keys: `hub`, `evaluation_start_date`, `evaluation_end_date`, `target`, `models`, and `output_path`. 

### hub

TODO

### evaluation_start_date

### evaluation_end_date

### target

### models

### output_path 

## Example 

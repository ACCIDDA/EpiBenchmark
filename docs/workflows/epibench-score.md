# `epibench score`

`epibench score` evaluates forecast output against ground truth data and uses
the R package `scoringutils` under the hood.

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

## How It Works

When you run `epibench score`, the Python package prepares the data to be
scored and then launches `Rscript` in a subprocess. That R process loads
`scoringutils`, computes the scores, and writes the results back for EpiBench
to save.

Because of this design, the Python virtual environment and the R installation
are separate:

- the virtual environment manages Python packages like EpiBench, pandas, and
  click
- your system or external R environment provides `Rscript` and
  `scoringutils`

## Troubleshooting

If scoring fails because `Rscript` is missing, install R and make sure the
`Rscript` executable is on your `PATH`.

If scoring fails because `scoringutils` is missing, install it in the same R
environment used by the `Rscript` command above.

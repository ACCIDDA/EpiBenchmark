# `epibench plot`

Running `epibench plot` will generate a set of graphics to help visualize your model(s) scores (i.e., an `EpiBenchmark_scores.csv` file). The graphics will be saved in PDF format. There are two ways to engage with `epibench plot`:

1. If the `EpiBenchmark_scores.csv` file you wish to plot was scored against one of the library challenges, you may invoke a challenge ID in your command to view other models from the hub on your plots. Only models with full coverage of the challenge defnition will be included.
2. If the `EpiBenchmark_scores.csv` file you with to plot does **NOT** belong to a challenge, or if you wish to visualize your scores alone, you may simply run the command with the required flags `--score-file-path` and `--output-path`.

Note that baseline model output will be included in your plotting output, as it is necessary in calculating the relative WIS metric.

## Output 

Currently, `epibench plot` produces 3 plots for visualizing the output of `epibench score`:

* plot 1: **Total WIS components by model**
    * a horizontal stacked bar chart that sums each model's WIS across all scored forecast units and decomposes it into underprediction, dispersion, and overprediction.
* plot 2: **Mean relative WIS by model and horizon**
    * a heatmap of relative WIS for each model-horizon pair; demonstrating how each model performs relative to the baseline at each forecast horizone (rWIS < 1 is better than th baseline, rWIS > 1 is worse).
* plot 3: **Mean WIS by reference date**
    * a time-series line plot of each model's mean WIS over date of reference; useful for understanding model performance over time. 

#### Hint: when scoring from a config, it can be useful to list relevant submitting models via the `include_models` key. Doing so will allow you to compare the performance of your model data to other models in the hub.

The PDF output will be named `EpiBenchmark_plots.pdf`.

## example usage:

```bash
epibench plot --score-file-path "./EpiBenchmark_scores.csv" --output-path "/Users/user/Desktop"
```
or
```bash
epibench plot epb_flu_inchosp_2024-2025_dev --score-file-path "./EpiBenchmark_scores.csv" --output-path
```
where `--score-file-path` is a path to a valid `EpiBenchmark_scores.csv` file.

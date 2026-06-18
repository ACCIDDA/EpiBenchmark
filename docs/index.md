# EpiBenchmark

**Authors**: Joseph Lemaitre, Emily Przykucki, Yue Liu, Justin Lessler and ???

**EpiBenchmark is a benchmark for infectious disease forecasting models, built to make evaluation more consistent, reproducible, and comparable across teams and targets.** Epidemiologic model evaluation is often difficult to compare in practice because targets vary, metrics vary, and data revisions can change results after the fact. EpiBench addresses that problem by standardizing vintaged truth data, evaluation workflows, and probabilistic scoring so that benchmark results are easier to interpret and compare. Using the three EpiBench workflows, you can:

- facillitate your model runs with vintaged ground truth data that is fetched and organized by the tool (`epibench setup`)
- score model forecasts with a WIS (includes over prediction, under prediction, coverage, etc.) (`epibench score`)
- create an array of plots to visualize model performance (`epibench plot`)

## Funding

This project was made possible by the Insight Net cooperative agreement `CDC-RFA-FT-23-0069` from the CDC's Center for Forecasting and Outbreak Analytics. Its contents are solely the responsibility of the authors and do not necessarily represent the official views of the Centers for Disease Control and Prevention.

EpiBench is being developed at UNC Chapel Hill through [ACCIDDA](https://www.accidda.org/), the  Atlantic Coast Center for Infectious Disease Dynamics and Analytics.

## Get started!

- [Installation](getting-started/installation.md) – install the EpiBench package
- [Overview](getting-started/overview.md) – understand the scope and usage of EpiBench

## Attribution

EpiBench relies on the [Hubverse](https://hubverse.io/) structure as a standard for data. Without the Hubverse and its associated tools, EpiBench would not be possible. The scoring component of EpiBench utilizes [scoringutils](https://epiforecasts.io/scoringutils/articles/scoringutils.html), a [CRAN](https://cran.r-project.org/web/packages/scoringutils/index.html) package that facillitates the evaluation of forecasts and is highly-compatible with the Hubverse structure. 

## Contact

Have a question, comment, or suggestion? Get in touch with the developers by [raising an issue](https://github.com/ACCIDDA/EpiBench/issues/new) on the EpiBench repository.

# EpiBench

**Authors**: Joseph Lemaitre, Emily Przykucki, Yue Liu, Justin Lessler

**Affiliation**: The University of North Carolina at Chapel Hill 

EpiBench is a python package that allows you to benchmark your infectious disease forecasting model(s). Using the three EpiBench workflows, you can:

- facillitate your model runs with vintaged data that is fetched and organized by the tool (`epibench setup`)
- score model forecasts with a WIS (includes over prediction, under prediction, coverage, etc.) (`epibench score`)
- create an array of plots to visualize model performance (`epibench plot`)


## Get started!

- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quick-start.md)

## Attribution

EpiBench relies on the [Hubverse](https://hubverse.io/) structure as a standard for data. Without the Hubverse and its associated tools, EpiBench would not be possible. The scoring component of EpiBench utilizes [scoringutils](https://epiforecasts.io/scoringutils/articles/scoringutils.html), a [CRAN](https://cran.r-project.org/web/packages/scoringutils/index.html) package that facillitates the evaluation of forecasts and is highly-compatible with the Hubverse structure. 

## Contact

Have a question, comment, or suggestion? Get in touch with the developers by [raising an issue](https://github.com/ACCIDDA/EpiBench/issues/new) on the EpiBench repository.

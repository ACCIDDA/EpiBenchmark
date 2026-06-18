# EpiBenchmark

**Authors**: [Author names placeholder]

## What is EpiBenchmark?

EpiBenchmark is a benchmark framework for infectious disease forecasting. It defines common forecasting tasks, fixed versions of truth data, standard evaluation rules, and shared scorecards so that models can be assessed under the same conditions. In practice, it is meant to provide a reproducible way to compare epidemiologic forecasting methods across diseases, targets, and teams.

## Why EpiBenchmark?
Evaluation of epidemiologic forecasting models is difficult for a basic reason: the field is fragmented. Different groups evaluate forecasts on different targets, different versions of observed data, different geographic units, and different scoring rules. As a result, reported performance is often hard to compare directly across papers.

This problem is amplified by the fact that surveillance data are often revised after initial release. A model evaluated against the latest revised data may not be directly comparable to a model evaluated against an earlier data version, even if both were forecasting the same target. For probabilistic forecasts, performance also depends on the exact scoring rule and evaluation procedure used.

The motivation is similar to [WeatherBench](https://arxiv.org/abs/2002.00469) and [WeatherBench 2](https://arxiv.org/abs/2308.15560): progress is easier to measure when a field has shared tasks, standardized data, baseline methods, and common scorecards. Epidemiologic forecasting needs the same structure, but adapted to revised surveillance data, local reporting differences, target definitions, forecast horizons, and probabilistic evaluation. Earlier work also argued for a common evaluation protocol in epidemic forecasting ([Srivastava et al. 2021](https://arxiv.org/abs/2102.02842)).

### Real-time hubs
Real-time collaborative hubs are and remain the gold standard for operational epidemiologic forecasting. They have shown the value of common forecast formats, shared targets, coordinated submissions, and centralized evaluation. Examples include [FluSight](https://github.com/cdcepi/FluSight-forecast-hub), [RSV Forecast Hub](https://github.com/CDCgov/rsv-forecast-hub), [COVID-19 Forecast Hub](https://github.com/CDCgov/covid19-forecast-hub), and [Flu MetroCast](https://github.com/reichlab/flu-metrocast).

But real-time hub evaluation is tied to ongoing submission cycles, changing data, and operational timelines. That makes comparison slower, harder to rerun, and less reproducible across studies. EpiBenchmark is intended to provide a faster benchmarking layer around these hubs, while staying compatible with their forecasting setup.

### Hubverse

EpiBenchmark is a thin layer on top of [Hubverse](https://hubverse.io/). Hubverse defines the data format and shared infrastructure. EpiBenchmark defines the benchmark tasks, frozen truth snapshots, scoring procedures, and scorecards. The goal is not to replace Hubverse, but to add a benchmark layer that makes evaluation faster to run, easier to reproduce, and easier to compare across models.

## EpiBenchmark in practice

EpiBench exposes three workflows:

- facilitate model runs with vintaged ground truth data fetched and organized by the tool (`epibench setup`)
- score model forecasts with a WIS (includes over prediction, under prediction, coverage, etc.) (`epibench score`)
- create an array of plots to visualize model performance (`epibench plot`)

## Funding

This project was made possible by the Insight Net cooperative agreement `CDC-RFA-FT-23-0069` from the CDC's Center for Forecasting and Outbreak Analytics. Its contents are solely the responsibility of the authors and do not necessarily represent the official views of the Centers for Disease Control and Prevention.

EpiBench is being developed at UNC Chapel Hill through [ACCIDDA](https://www.accidda.org/), the Atlantic Coast Center for Infectious Disease Dynamics and Analytics.

## Get started!

- [Installation](getting-started/installation.md) – install the EpiBench package
- [Overview](getting-started/overview.md) – understand the scope and usage of EpiBench

## Attribution

EpiBench relies on the [Hubverse](https://hubverse.io/) structure as a standard for data. Without the Hubverse and its associated tools, EpiBench would not be possible. The scoring component of EpiBench utilizes [scoringutils](https://epiforecasts.io/scoringutils/articles/scoringutils.html), a [CRAN](https://cran.r-project.org/web/packages/scoringutils/index.html) package that facillitates the evaluation of forecasts and is highly-compatible with the Hubverse structure. 

## Contact

Have a question, comment, or suggestion? Get in touch with the developers by [raising an issue](https://github.com/ACCIDDA/EpiBench/issues/new) on the EpiBench repository.

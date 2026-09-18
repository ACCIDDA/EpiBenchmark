# EpiBenchmark

**Authors**: Joseph Lemaitre, Emily Przykucki, Yue Liu, and Justin Lessler

## What is EpiBenchmark?

EpiBenchmark is a **benchmarking framework** and **challenge library** for infectious disease forecasting. Our challenges define common forecasting tasks associated with fixed versions of ground truth data and evaluation rules to facillitate easy and fair forecasting evaluation. That is, models receive scorecards with a variety of metrics and can be compared under the same conditions. EpiBenchmark provides a reproducible way to compare epidemiologic forecasting methods across diseases, targets, and teams.

## Why EpiBenchmark?
Evaluation of epidemiologic forecasting models is difficult, and the field is fragmented. Different groups evaluate forecasts on different targets, different versions of observed data, different geographic units, and different scoring rules. As a result, reported performance is often hard to compare directly across papers.

This problem is amplified by the fact that surveillance data are often revised after initial release (backfilling). A model evaluated against the latest revised data may not be directly comparable to a model evaluated against an earlier data version, even if both were forecasting the same target. For probabilistic forecasts, performance also depends on the exact scoring rule and evaluation procedure used. 

The progress in a scientific field is easier to measure when there exists a common protocol for evaluation. EpiBenchmark mirrors similar effort in other fields such as [WeatherBench](https://arxiv.org/abs/2002.00469) and [WeatherBench 2](https://arxiv.org/abs/2308.15560), but is adapted to the specific challenges associated with epidemiologic forecasting (such as backfilled surveillance data) and its conventions (probabilistic evaluation, [hubverse](https://hubverse.io/) format). Note that earlier work also argued for a common evaluation protocol in epidemic forecasting ([Srivastava et al. 2021](https://arxiv.org/abs/2102.02842)).

### EpiBenchMark vs Real-time hubs
Real-time collaborative hubs are and remain the gold standard for operational epidemiologic forecasting. Examples include [FluSight](https://github.com/cdcepi/FluSight-forecast-hub), [RSV Forecast Hub](https://github.com/CDCgov/rsv-forecast-hub), [COVID-19 Forecast Hub](https://github.com/CDCgov/covid19-forecast-hub), and [Flu MetroCast](https://github.com/reichlab/flu-metrocast).

But real-time hub evaluation is tied to ongoing submission cycles, changing data, and operational timelines. That makes comparison slower and models harder to re-run, resulting in less reproducibility across studies. EpiBenchmark is intended to provide a faster benchmarking layer around these hubs, while staying compatible with their forecasting setup.

### EpiBenchmark vs Hubverse

EpiBenchmark is a thin layer on top of [Hubverse](https://hubverse.io/). Hubverse defines the data format and shared infrastructure. EpiBenchmark defines the benchmark tasks, frozen ground truth snapshots, scoring procedures, scorecards, and plots. The goal is to add a benchmarking layer to the hubverse that makes evaluation faster to run, easier to reproduce, and easier to compare across models.

## EpiBenchmark in practice

EpiBenchmark exposes three workflows:

- `epibench create`: facilitate model runs for any reference date with vintaged ground truth data fetched and organized by the tool
- `epibench score`: score model forecasts with a WIS (includes over prediction, under prediction, coverage, etc.) 
- `epibench plot`: create an array of plots to visualize model performance (`epibench plot`)

## Funding

This project was made possible by the Insight Net cooperative agreement `CDC-RFA-FT-23-0069` from the CDC's Center for Forecasting and Outbreak Analytics. Its contents are solely the responsibility of the authors and do not necessarily represent the official views of the Centers for Disease Control and Prevention.

EpiBenchmark is being developed at UNC Chapel Hill through [ACCIDDA](https://www.accidda.org/), the Atlantic Coast Center for Infectious Disease Dynamics and Analytics.

## Get started!
### Overview
- [Overview](getting-started/overview.md) – understand the scope and usage of EpiBenchmark

### Installation Guide
- [Installation](getting-started/installation.md) – install the EpiBenchmark package

### Installation_Longleaf Guide
- [Installation_Longleaf](getting-started/installation_longleaf.md) - install the EpiBenchmark package on UNC Longleaf Cluster

## Attribution

EpiBenchmark relies on the [Hubverse](https://hubverse.io/) structure as a standard for forecast and target data. Its in-process scoring implementation evaluates Hubverse quantile forecasts and produces the metrics used by EpiBenchmark scorecards and plots.

## Contact

Have a question, comment, or suggestion? Get in touch with the developers by [raising an issue](https://github.com/ACCIDDA/EpiBenchmark/issues/new) on the EpiBenchmark repository.

# Challenge library

The challenges bundled with EpiBenchmark. List them at the command line with `epibench list`, and download a challenge's data files from Zenodo with `epibench fetch <challenge_id>` — see [Challenge library commands](getting-started/challenge-library.md).

Click a challenge to expand its full definition.

??? note "epb_flu_inchosp_2023-2024_v1"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2023-10-14 → 2024-05-04 (30 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 52 |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 90_coverage |
    | Zenodo | *not yet published to Zenodo* |

??? note "epb_flu_inchosp_2024-2025_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2024-11-23 → 2025-05-31 (27 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 52 |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 90_coverage |
    | Zenodo | [10.5281/zenodo.21413630](https://doi.org/10.5281/zenodo.21413630) |

??? note "epb_flu_inchosp_2025-2026_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2025-11-22 → 2026-05-30 (28 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 52 |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 90_coverage |
    | Zenodo | [10.5281/zenodo.21413852](https://doi.org/10.5281/zenodo.21413852) |

??? note "epb_rsv_inchosp_2025-2026_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `rsv-forecast-hub` |
    | Target | `wk inc rsv hosp` |
    | Reference dates | 2025-11-22 → 2026-05-30 (28 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 52 |
    | Baseline model | `RSVHub-baseline` |
    | Scorecard | total wis, 50_coverage, 90_coverage |
    | Zenodo | [10.5281/zenodo.21413793](https://doi.org/10.5281/zenodo.21413793) |

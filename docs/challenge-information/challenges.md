# Challenge library

EpiBenchmark ships with a library of predefined **challenges** (challenges have fixed hub, target, dates, horizons, quantiles, locations, and scoring settings). Each location uses 52 locations: the 50 U.S. states, Washington D.C., and the U.S. as a whole. Puerto Rico is excluded. Explore each challenge in our library below. You can list them locally via the command line with `epibench list`, and fully download a challenge from Zenodo with `epibench fetch <challenge-id>`.

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
    | Scorecard | total wis, 50_coverage, 95_coverage |
    | Zenodo | *not yet published to Zenodo* |

    !!! warning "Ground-truth exclusions"
        Ground-truth observations are unavailable for the following location and target-end-date combinations:

        | Location | Target end date |
        | --- | --- |
        | `25` | `2024-05-18` |
        | `25` | `2024-05-25` |
        | `27` | `2024-05-18` |
        | `27` | `2024-05-25` |

        Forecast units corresponding to these combinations are excluded from scoring. They must still be present in model output to satisfy the challenge's complete-coverage validation.

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
    | Scorecard | total wis, 50_coverage, 95_coverage |
    | Zenodo | [10.5281/zenodo.21413630](https://doi.org/10.5281/zenodo.21413630) |

    * **Note**: `epb_flu_inchosp_2025-2025_dev` has a 1-week date discontinuity at `2025-01-25` due to a US government shutdown.

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
    | Scorecard | total wis, 50_coverage, 95_coverage |
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
    | Scorecard | total wis, 50_coverage, 95_coverage |
    | Zenodo | [10.5281/zenodo.21413793](https://doi.org/10.5281/zenodo.21413793) |

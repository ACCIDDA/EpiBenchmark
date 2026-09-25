# Challenge library

EpiBenchmark ships with a library of predefined **challenges** (challenges have fixed hub, target, dates, horizons, quantiles, locations, and scoring requirements).  Explore each challenge in our library below. You can list them locally via the command line with `epibench list`, and fully download a bundled challenge with `epibench fetch <challenge-id>`.

Click a challenge to expand its full definition.

??? note "epb_flu_inchosp_2023-2024_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2023-10-14 → 2024-05-04 (30 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 50 U.S. states + Washington D.C. + U.S. (52 total) |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 95_coverage |

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
    | Locations | 50 U.S. states + Washington D.C. + U.S. (52 total) |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 95_coverage |

    * **Note**: `epb_flu_inchosp_2025-2025_dev` has a 1-week date discontinuity at `2025-01-25` due to a US government shutdown.

??? note "epb_flu_inchosp_2024-2026_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2024-11-23 → 2025-05-31; 2025-11-22 → 2026-05-30 (55 dates total) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.025, 0.25, 0.5, 0.75, 0.975 |
    | Locations | 50 U.S. states + Washington D.C. + U.S. (52 total) |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 95_coverage |

    * **Note**: This challenge combines `epb_flu_inchosp_2024-2025_dev` and `epb_flu_inchosp_2025-2026_dev`. There is a 1-week discontinuity at `2025-01-25` and a break between the two flu seasons.

??? note "epb_flu_inchosp_2025-2026_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `flusight-forecast-hub` |
    | Target | `wk inc flu hosp` |
    | Reference dates | 2025-11-22 → 2026-05-30 (28 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 50 U.S. states + Washington D.C. + U.S. (52 total) |
    | Baseline model | `FluSight-baseline` |
    | Scorecard | total wis, 50_coverage, 95_coverage |

??? note "epb_rsv_inchosp_2025-2026_dev"
    | Field | Value |
    | --- | --- |
    | Hub | `rsv-forecast-hub` |
    | Target | `wk inc rsv hosp` |
    | Reference dates | 2025-11-22 → 2026-05-30 (28 dates) |
    | Horizons | 0, 1, 2, 3 |
    | Quantiles | 0.05, 0.25, 0.5, 0.75, 0.95 |
    | Locations | 50 U.S. states + Washington D.C. + U.S. (52 total) |
    | Baseline model | `RSVHub-baseline` |
    | Scorecard | total wis, 50_coverage, 95_coverage |

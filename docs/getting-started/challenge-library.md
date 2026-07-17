# Challenge library commands

EpiBenchmark ships with a library of predefined **challenges** (fixed hub, target, dates, and scoring settings). Two commands work with it. Browse the catalog on the [Challenge library](../challenges.md) page.

## `epibench list`

List every challenge in the library, with its target, date range, and whether its data is published to Zenodo.

```bash
epibench list
```

## `epibench fetch`

Download a challenge's data files from Zenodo into a folder named after the challenge.

```bash
epibench fetch <challenge_id> [--output-path DIR]
```

- `<challenge_id>` — a challenge id from `epibench list` (e.g. `epb_rsv_inchosp_2025-2026_dev`).
- `--output-path` — directory to download into; defaults to the current directory.

The archive is unzipped in place, leaving `<output-path>/<challenge_id>/` with the ground-truth data (`gt/<date>/…`), the `task_list.csv`, and a copy of the challenge definition. Fetching a challenge that has not been published to Zenodo yet raises an error.

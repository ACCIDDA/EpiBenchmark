# EpiBenchmark — strategy for a first "good" release (v1.0)

*Internal design/strategy note. Excluded from the published site (see `exclude_docs`
in `mkdocs.yml`). This document defines a realistic, non-over-scoped target for
EpiBenchmark v1.0: what the product should be, what we deliberately leave out, the
references we cite to justify the design, and the one documentation page that still
needs to be written.*

---

## 1. The one-sentence product

EpiBenchmark is a thin, reproducible **benchmark layer on top of the Hubverse**: it
freezes a forecasting task — a fixed target, a fixed set of locations and dates, a
**frozen (unrevised) ground-truth snapshot**, a fixed scoring rule, and a designated
baseline — into a named **challenge**, so that any model's forecasts can be scored and
turned into a comparable **scorecard** under identical conditions, weeks or years after
the fact.

The design analogy is deliberate and load-bearing: EpiBenchmark is to epidemic
forecasting what **WeatherBench** is to data-driven weather forecasting — a common,
frozen evaluation harness that makes results comparable across papers and teams
(Rasp et al. 2020; Rasp et al. 2023). The novelty relative to WeatherBench is that
epidemic surveillance data are *revised after the fact*, so "freeze the truth" is not a
convenience — it is the core scientific problem the benchmark exists to solve.

## 2. Why scope discipline matters here

The project already has the three-command spine working (`setup`, `score`, `plot`) and a
challenge-library mechanism (`challenges.json` → scorecard). The risk to the project is
not lack of features; it is **over-reach** — trying to become a live leaderboard, a model
submission portal, or a multi-disease auto-ingestion platform before the atomic unit (one
fully reproducible challenge) actually works end to end. v1.0 should make *one thing*
undeniably solid: **a challenge that anyone can re-run and get the same scorecard.**

## 3. What v1.0 IS (in scope)

The bar for v1.0 is *reproducible comparability of one challenge*, documented well enough
that an external forecaster can use it unaided.

1. **The challenge is the atomic, frozen unit.** Lock down the `challenges.json` schema as
   the contract. Every challenge must carry: `hub`, `target`, `locations`,
   `target_end_dates`, `baseline_model`, `scorecard_function`, a schema `version`, and a
   **real, resolvable ground-truth pointer** (see #2 below). Add a short JSON-schema file
   and a validator so a malformed challenge fails loudly at load time.

2. **Frozen truth is real, not `"TBD"`.** Today `challenges.json` has
   `"zenodo_doi": "TBD"`, and `score_from_challenge_library` clones the *live* hub. That
   means a challenge's result can silently drift when the hub revises data — which defeats
   the benchmark's entire purpose. v1.0 must resolve a challenge against an **archived,
   content-addressed snapshot** (a Zenodo DOI, or a pinned hub commit SHA as an interim
   step) rather than `HEAD`. This is the single most important correctness item in the
   release; the `setup` pipeline already knows how to vintage truth, so this is about
   *pinning and recording* the vintage, not new science.

3. **One flagship challenge, fully worked, doubling as the integration test.** Take the
   existing `epb_rsv_inchosp_2025-2026_v1` challenge, give it a real frozen snapshot, and
   wire it up as the end-to-end integration test the team already wants
   (issue #28). "The example *is* the test" keeps the demo honest and prevents regressions.

4. **A small, defensible scorecard.** Keep the metric set intentionally minimal and
   justified rather than exhaustive:
   - **WIS** (weighted interval score) — the primary accuracy metric for quantile
     forecasts (Bracher et al. 2021), already computed via `scoringutils`.
   - **Relative WIS vs. the challenge baseline** — the *comparability* metric. A raw WIS is
     not interpretable across targets or seasons; WIS relative to a fixed baseline is. This
     is the number a scorecard should lead with, and it is why every challenge names a
     `baseline_model`. (Add this to `scorecard_functions.py`; `scoringutils` exposes it.)
   - **Interval coverage at 50% and 90%** — calibration, already implemented.
   - Report **per-horizon** as well as aggregate, since accuracy decays with horizon.

5. **Reproducibility guarantees.** Pin the R `scoringutils` version (or record it in the
   scorecard), stamp each scorecard with the challenge id + schema version + snapshot
   pointer + tool versions, and keep the "no silent overwrite" behavior already in
   `_write_output_csv`. A scorecard should be self-describing enough to trace back to
   exactly what produced it.

6. **Documentation completed to "an outsider can run it" level** — specifically the concept
   page described in §6, plus finishing the two workflow pages that currently say
   "COMING SOON" / "coming soon" (`epibench score`, `epibench plot`).

## 4. What v1.0 is NOT (deliberately deferred)

Naming these out loud is half the point of the strategy — each is a plausible feature that
would blow the timeline:

- **No hosted leaderboard / public comparison website.** Scorecards are local CSVs in v1.0.
  A leaderboard is a v2 concern and pulls in hosting, moderation, and identity.
- **No model-submission portal or CI-gated submissions.** Users bring their own forecast
  CSVs and score locally.
- **No multi-disease breadth push.** One flagship challenge (RSV) done properly beats ten
  half-specified ones. Add COVID/flu challenges only *after* the schema and snapshot flow
  are proven.
- **No ensembling / model-building tools.** EpiBenchmark evaluates; it does not forecast.
- **`plot`-inside-`score` (issue #23) is optional, not blocking.** Nice ergonomics, but it
  is a convenience flag, not part of the reproducibility story. Ship if cheap, cut if not.
- **No API-reference site section yet.** The `api/` nav is already commented out in
  `mkdocs.yml`; leave it until the module boundaries settle.

## 5. Sequenced plan (dependency order)

1. **Freeze the schema.** Write `challenges-library/challenge.schema.json`; add a loader
   that validates `challenges.json` against it. *(unblocks everything else)*
2. **Pin the truth.** Replace `"zenodo_doi": "TBD"` with a real snapshot pointer and make
   `score_from_challenge_library` resolve against the pinned snapshot (Zenodo DOI, or a
   pinned commit SHA as the interim). Record the pointer in the scorecard.
3. **Add relative-WIS** to `scorecard_functions.py` and make it the headline scorecard
   metric; add per-horizon breakdown.
4. **Land the flagship challenge as an integration test** (issue #28) that runs the full
   `score` → scorecard path against the frozen snapshot in CI.
5. **Write the docs**: the new "Challenges & benchmark design" concept page (§6) and finish
   the `score` / `plot` workflow pages.
6. *(optional)* plot-in-score flag (issue #23).

## 6. The documentation page to be written

The single most important missing piece of user-facing documentation is a **concept page
that explains what a "challenge" is and why the truth is frozen.** Everything else in the
docs is mechanical ("here are the config keys"); nothing yet explains the *idea* that makes
EpiBenchmark worth using. Recommended:

- **Title / path:** `docs/concepts/challenges.md` (add a new top-level "Concepts" section in
  `mkdocs.yml`, before "Workflows").
- **Audience:** an epidemiologic forecaster who has never heard of EpiBenchmark and is
  deciding whether to invest an afternoon in it.
- **It must answer, in order:**
  1. *What is a challenge?* — the atomic unit: target + locations + dates + frozen truth +
     scoring rule + baseline, identified by a stable name and schema version. Show the
     `epb_rsv_inchosp_2025-2026_v1` entry as the worked example.
  2. *Why is the ground truth frozen?* — surveillance data are revised after release, so a
     model scored against "today's" data is not comparable to one scored last month. Frozen
     snapshots (Zenodo DOI / pinned vintage) are what make results reproducible. This is the
     paragraph that carries the whole value proposition.
  3. *What is on a scorecard, and how do I read it?* — WIS, **relative WIS vs. baseline**
     (lead with this and explain "1.0 = as good as baseline, <1.0 = better"), 50%/90%
     coverage, per-horizon. Explain why relative-to-baseline is the comparable number.
  4. *How does this relate to real-time hubs and to Hubverse?* — reuse the framing already
     in `index.md`: a faster, rerunnable benchmark layer *around* hubs, built *on* Hubverse
     format, not a competitor to either.
  5. *How do I run the flagship challenge myself?* — a copy-pasteable
     `epibench score <challenge> --model-data-path … --model-name … --output-path …` block,
     linking onward to the `score` workflow page.

Secondary docs debt (finish these, don't design them): `docs/workflows/epibench-score.md`
(remove "COMING SOON", document the challenge-library route + the six config keys) and
`docs/workflows/epibench-plot.md` (currently a stub).

## 7. References

Grouped by the design claim each one supports. Links/DOIs given where known; a few are
flagged **[verify]** and should be double-checked against the canonical citation before
they go into published prose.

### Benchmark philosophy (why a frozen common harness)
- **Rasp et al. 2020**, *WeatherBench: A benchmark data set for data-driven weather
  forecasting.* arXiv:2002.00469 — the frozen-benchmark model EpiBenchmark imitates.
  (already cited in `index.md`)
- **Rasp et al. 2023**, *WeatherBench 2.* arXiv:2308.15560 — the "keep the harness, grow the
  scope" follow-up; a useful template for how EpiBenchmark should grow *after* v1.0.
  (already cited in `index.md`)
- **Srivastava et al. 2021**, arXiv:2102.02842 — prior argument for a common evaluation
  protocol in epidemic forecasting; establishes that this need is recognized in the field.
  (already cited in `index.md`)

### Scoring rules and forecast evaluation (why WIS + coverage)
- **Bracher, Ray, Gneiting & Reich 2021**, *Evaluating epidemic forecasts in an interval
  format.* PLOS Computational Biology 17(2):e1008618 — the definition and justification of
  the **weighted interval score (WIS)**, EpiBenchmark's primary metric. **[core citation]**
- **Gneiting & Raftery 2007**, *Strictly proper scoring rules, prediction, and estimation.*
  JASA 102(477):359–378 — foundational theory of proper scoring rules; grounds *why* WIS is
  a defensible choice and why coverage alone is not enough. **[verify page/vol]**
- **Bosse et al. 2022**, *Evaluating forecasts with scoringutils in R.* arXiv:2205.07090 —
  the R package EpiBenchmark shells out to for scoring; cite for the exact metric
  implementations and the relative-skill computation. **[verify arXiv id]**

### Collaborative hubs and the Hubverse (what EpiBenchmark layers onto)
- **Hubverse** — https://hubverse.io/ — the data format and infrastructure EpiBenchmark is a
  thin layer over. (already cited)
- **Cramer et al. 2022**, *Evaluation of individual and ensemble probabilistic forecasts of
  COVID-19 mortality in the United States.* PNAS 119(15):e2113561119 — the canonical
  large-scale hub evaluation; motivates comparable, baseline-relative scoring. **[verify]**
- **Reich et al. 2019**, *Accuracy of real-time multi-model ensemble forecasts for seasonal
  influenza in the U.S.* PLOS Comp Bio — precedent for standardized multi-model flu
  evaluation. **[verify]**
- Operational hubs referenced as the "gold standard" EpiBenchmark complements
  (already linked in `index.md`): FluSight (`cdcepi/FluSight-forecast-hub`), RSV Forecast
  Hub (`CDCgov/rsv-forecast-hub`), COVID-19 Forecast Hub (`CDCgov/covid19-forecast-hub`),
  Flu MetroCast (`reichlab/flu-metrocast`).

### Reproducibility / frozen snapshots (why Zenodo, not `HEAD`)
- **Zenodo** — https://zenodo.org/ — DOI-minting archive used to freeze and cite the
  ground-truth snapshot behind each challenge (the intended target of the `zenodo_doi`
  field, currently `"TBD"`).
- **scoringutils on CRAN** — https://cran.r-project.org/package=scoringutils — pin/record
  the version so scores are reproducible across machines. (already cited)

*(Data-revision / backfill in surveillance is the empirical premise for freezing truth; if
a citation is wanted for published prose, add one on nowcasting/backfill — e.g. work on
reporting delays in surveillance systems — but it is not required for the design itself.)*

## 8. Definition of done for v1.0

- [ ] `challenges.json` validates against a committed JSON schema; bad entries fail at load.
- [ ] The flagship RSV challenge resolves against a **frozen** snapshot (no `"TBD"`, no live
      `HEAD`), and the snapshot pointer + tool versions appear on the scorecard.
- [ ] Scorecard reports WIS, **relative WIS vs. baseline**, 50%/90% coverage, per horizon.
- [ ] `epibench score <flagship>` runs green in CI as the integration test (issue #28).
- [ ] The Concepts → Challenges page exists; `score` and `plot` workflow pages no longer say
      "coming soon".

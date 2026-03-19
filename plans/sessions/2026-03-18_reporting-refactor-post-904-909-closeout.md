# Reporting Refactor Post-#904/#909 Closeout
**Date:** 2026-03-18
**Goal:** Finish aligning the shipped `arc_d_v2` reporting suite with the governing refactor plan after PRs `#904` and `#909`. This plan separates what still needs code changes from what is genuinely blocked on missing experiment artifacts.

## Current State

### Confirmed improvements
- Governing-plan status was moved away from a false `COMPLETE` state.
- `outcome_summary.csv` was removed from committed `quick/full` bundles.
- `04_rung_decision.md` is now deprecated in `full` bundles rather than silently acting as a parallel decision surface.
- QUICK `02_decision.md` is no longer universally `PENDING`; `r0/r1` show `ADVANCE`, `r2/r3` show `PRELIMINARY`.
- `extract_comparator_cis.py` now emits `bidders_by_contract`, which is the right upstream hook for real contract-faceted behavior outputs on future regenerations.
- Bundle hygiene tests exist and pass.

### Verified remaining gaps
- Produced `quick` bundles still ship synthetic `outcome_distributions.csv`.
- Produced `quick` bundles still ship pooled-only `behavior_by_contract.csv`.
- Produced `quick` bundles still lack Charts `10`, `16`, `17`, `18`, `21`, and `22`.
- The governing plan still has stale “current truth” bullets that describe pre-`#877` bundle state rather than current branch state.
- Chart-data ownership is still not fully disciplined:
  - `decision_comparison.csv` / `disagreement_outcomes.csv` still have both a dormant parquet path and a productive interpretability path.
  - `selection_paths.csv` is still dual-written from feature-importance rows.
  - `cross_rung_progression.csv` still exists as a target contract item without canonical bundle generation.

### Real blockers
- This checkout only has `data/fixtures/`; it does not have the `data/artifacts/arc_d_v2/` and run outputs needed to regenerate the missing model-eval and seat-balance evidence.
- Per-contract behavior output in shipped bundles depends on rerunning extraction against real comparator JSONL logs after `#909`.

## Plan

- Step 1: Correct the governing plan so it is a trustworthy handoff document again.
  - Update `plans/arc_d_v2/reporting_refactor_full_plan.md` §2.2 so it matches current branch truth.
  - Remove stale bullets claiming QUICK decisions are still `Rung ?` / `PENDING`.
  - Remove stale bullets claiming FULL manifests are still uniformly `Mode: QUICK` / `Seeds: []`.
  - Keep only the real remaining gaps: synthetic distributions, pooled-only shipped behavior faceting, missing shipped chart family, deprecated extra decision file, and ownership drift.

- Step 2: Close the remaining code-side ownership and contract gaps that are **not** blocked on source data.
  - Make one canonical producer for `decision_comparison.csv` and `disagreement_outcomes.csv`.
    - Preferred owner: `scripts/internal/generate_interpretability.py`
    - Non-canonical parquet extractor path in `src/bid_euchre/arc_d_v2/tables.py` should be clearly fallback-only or removed from normal regeneration.
  - Decide the disposition of `cross_rung_progression.csv`.
    - If canonical: wire it into normal generation and manifest/report expectations.
    - If not canonical: remove it from the target contract and acceptance checks.
  - Decide the disposition of `selection_paths.csv`.
    - If it remains canonical, define real selection-path semantics distinct from feature importance.
    - Otherwise demote it to a compatibility alias and stop treating Chart 19 as distinct evidence.

- Step 3: Merge the upstream comparator-faceting fix and prepare regeneration prerequisites.
  - Merge PR `#909`.
  - Record that shipped bundle faceting is still incomplete until regeneration runs against real comparator logs.
  - Confirm which artifact directories and JSONL sources are required for:
    - `behavior_by_contract.csv`
    - `seat_balance.csv`
    - `predictions.csv`
    - `residuals.csv`
    - `calibration_bins.csv`
    - `decision_comparison.csv`
    - `disagreement_outcomes.csv`

- Step 4: Regenerate canonical bundles when source artifacts are available.
  - Regenerate `docs/04_reports/arc_d_v2/r0-r3/quick/`.
  - Regenerate `docs/04_reports/arc_d_v2/r0-r3/full/` for rungs with the necessary parquet/model artifacts.
  - Do not regenerate `canonical/`.

- Step 5: Re-audit the regenerated bundles against the governing plan.
  - Verify `behavior_by_contract.csv` contains `suit`, `high`, and `low` rows.
  - Verify `outcome_distributions.csv` is parquet-backed where row-level data exists; otherwise ensure degraded state is explicit.
  - Verify Charts `10`, `16`, `17`, `18`, `21`, and `22` render whenever their source CSVs exist.
  - Verify `01_results.md` no longer shows placeholder sections where the source data is present.
  - Verify `02_decision.md` remains the sole maintained decision artifact.

- Step 6: Only then declare the remaining gaps as data-blocked.
  - If code-side ownership cleanup is complete and regeneration still cannot fill specific charts, record those as true source-artifact blockers.
  - Do not describe the refactor as “pipeline code now correct” until both:
    - code-side contract cleanup is complete
    - bundle-level regeneration proves the intended outputs are actually emitted

## Workstreams

### Workstream A — Plan Truth Correction
- File: `plans/arc_d_v2/reporting_refactor_full_plan.md`
- Deliverable:
  - accurate §2.2 current-state bullets
  - accurate acceptance / remaining-work text
- Success condition:
  - no internal contradictions between plan status and branch state

### Workstream B — Chart-Data Ownership Cleanup
- Files:
  - `src/bid_euchre/arc_d_v2/tables.py`
  - `scripts/internal/generate_interpretability.py`
  - `src/bid_euchre/arc_d_v2/chart_registry.py`
- Deliverable:
  - one canonical writer per chart-data artifact
  - explicit disposition for `cross_rung_progression.csv`
  - explicit disposition for `selection_paths.csv`
- Success condition:
  - no target artifact is simultaneously “canonical” in two different generation paths

### Workstream C — Regeneration Readiness
- Files:
  - `scripts/internal/extract_comparator_cis.py`
  - regeneration commands / working notes
- Deliverable:
  - merged `#909`
  - documented artifact prerequisites for regeneration
- Success condition:
  - next agent can regenerate without rediscovering missing inputs

### Workstream D — Bundle Regeneration and Audit
- Files:
  - `docs/04_reports/arc_d_v2/r*/quick/**`
  - `docs/04_reports/arc_d_v2/r*/full/**`
  - `tests/unit/test_bundle_hygiene.py`
  - reporting bundle tests as needed
- Deliverable:
  - regenerated bundles reflecting the current pipeline
  - follow-up audit documenting what is now fixed vs still degraded
- Success condition:
  - shipped bundles, not just infrastructure, align materially better with the governing plan

## Implementation Sequence

- PR 1: Governing-plan truth correction
  - fix stale §2.2 bullets
  - sync acceptance/remaining-work text with actual branch state

- PR 2: Chart-data ownership cleanup
  - canonicalize `decision_comparison.csv` / `disagreement_outcomes.csv`
  - decide `cross_rung_progression.csv`
  - decide `selection_paths.csv`

- PR 3: Merge `#909`
  - land comparator per-contract extraction
  - document regeneration prerequisites

- PR 4: Regeneration
  - rerun bundle generation with real logs/artifacts
  - do not touch `canonical/`

- PR 5: Bundle audit / closeout
  - verify shipped outputs against plan
  - record any remaining true data-blocked items

## Acceptance Criteria
- The governing plan accurately describes the current repo state.
- `quick` bundles no longer rely on stale status text to describe fixed issues.
- `behavior_by_contract.csv` is contract-faceted in regenerated bundles when comparator logs are available.
- Missing charts are treated as source-data gaps only after regeneration has been attempted with the required inputs.
- `decision_comparison.csv` and `disagreement_outcomes.csv` have a single canonical producer in normal regeneration.
- `cross_rung_progression.csv` is either canonically generated or explicitly removed from the target contract.
- `selection_paths.csv` is either semantically distinct from feature importance or explicitly demoted from canonical evidence.
- A post-regeneration audit exists that distinguishes:
  - fixed in code
  - fixed in shipped bundles
  - still blocked on missing artifacts

## Validation
- `PYTHONPATH=. uv run python -m pytest -q tests/unit/test_bundle_hygiene.py`
- `rg -n "Rung \\?|PENDING|Mode: QUICK|Seeds: \\[\\]" plans/arc_d_v2/reporting_refactor_full_plan.md docs/04_reports/arc_d_v2/*/{quick,full}`
- `rg -n "selection_paths.csv|decision_comparison|disagreement_outcomes|cross_rung_progression" src/bid_euchre/arc_d_v2/tables.py scripts/internal/generate_interpretability.py src/bid_euchre/arc_d_v2/chart_registry.py`
- `rg -n "contract,net_eppd" docs/04_reports/arc_d_v2/*/quick/tables/behavior_by_contract.csv`

## Outcome (Partial — 2026-03-18, author-d session)

### Completed
- **Step 1 (Workstream A):** §2.2 stale bullets corrected — 8 items marked fixed with strikethrough, "Still outstanding" section reflects real gaps. §13 acceptance criteria corrected (✅→❌/⚠️). §16 added with 5 verified gaps.
- **Step 2 partial (Workstream B):** `selection_paths.csv` dual-write removed from `tables.py` — now exclusively produced by `generate_interpretability.py`. `cross_rung_progression.csv` decided as optional (§16.5). `decision_comparison.csv`/`disagreement_outcomes.csv` ownership documented in §16.5 but dormant code paths not guarded.
- **Step 4 partial (Workstream D):** R3/full chart_data regenerated — 4 new CSVs (predictions, residuals, calibration_bins, seat_balance) + 2 upgraded (outcome_distributions synthetic→parquet, bid_levels aggregate→per-level). R3/full now has 10 chart_data CSVs matching R0-R2/full.

### PRs
- [#904](https://github.com/Questuart/Bid-Euchre/pull/904): governing plan correction, outcome_summary removal, deprecation, 34 tests
- [#909](https://github.com/Questuart/Bid-Euchre/pull/909): per-contract extraction, fixture enrichment, R3/full chart_data, ownership cleanup, §2.2 fix (stacked on #904)

### Remaining gaps → see Handoff section below

## Handoff

### Context for next agent

Two PRs (#904, #909) are open and under review. Once merged, the following
gaps remain from this closeout plan. The next agent should address them in
a single session.

**Source artifacts ARE available** in the main checkout at
`/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/`:
- `data/artifacts/arc_d_v2/r{0,1,2,3}/` — H2H batteries, comparator CIs, training artifacts, joblib models
- `data/runs/arc_d_v2/` — parquet datasets (r3_datasets/quick/seed_1001/)
- R0/R1 have FULL H2H batteries (3 seeds); R2/R3 only have QUICK

### Directive

> **Draft a plan, have a reviewer review the plan, create a task list to
> support execution, assess for parallelism, then execute the plan end to
> end autonomously.**

### Gap 1: Guard dormant extractors (code, no data dependency)

`_extract_decision_comparison()` and `_extract_disagreement_outcomes()` in
`src/bid_euchre/arc_d_v2/tables.py` (lines ~1072-1086) are dormant parquet
extractors that will silently activate if the parquet schema ever gains
`bid_decision` + `model` columns — potentially shadowing the canonical
producer (`generate_interpretability.py`). Add an explicit guard or remove
from the normal `generate_chart_data` call path so only the interpretability
pipeline produces these CSVs.

**Files:** `src/bid_euchre/arc_d_v2/tables.py`
**Test impact:** `tests/unit/test_rung_tables.py` (existing graceful-skip tests should still pass)

### Gap 2: Write regeneration prerequisites doc (doc, no data dependency)

Document which artifact paths are required for each chart_data CSV so the
next agent doing regeneration doesn't have to rediscover inputs. Include:

| CSV | Required Artifact | Path Pattern |
|-----|------------------|--------------|
| `behavior_by_contract.csv` | comparator_cis with `bidders_by_contract` | Re-extract from JSONL via `extract_comparator_cis.py` |
| `seat_balance.csv` | action_value.parquet | `data/runs/arc_d_v2/*/datasets/` |
| `predictions.csv` | training_artifact_*.json + parquet | `data/artifacts/arc_d_v2/<rung>/` |
| `residuals.csv` | training_artifact_*.json + parquet | same |
| `calibration_bins.csv` | training_artifact_*.json + parquet | same |
| `decision_comparison.csv` | trained models (joblib) + parquet | `generate_interpretability.py` |
| `disagreement_outcomes.csv` | trained models (joblib) + parquet | same |

**File:** New doc or section in the governing plan

### Gap 3: Regenerate QUICK bundles (data-dependent)

QUICK bundles still have:
- Synthetic `outcome_distributions.csv` (no QUICK parquet → acceptable)
- Pooled-only `behavior_by_contract.csv` (comparator CIs lack `bidders_by_contract` → need re-extraction from JSONL)

To fix `behavior_by_contract.csv` in QUICK bundles: re-run
`extract_comparator_cis.py` against JSONL game logs in `data/runs/` for each
rung, then regenerate tables. Check if JSONL logs exist:
```bash
find /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/data/runs -name "*.jsonl" -path "*comparator*" | head -5
```

If JSONL logs don't exist, this is a true data blocker — document it and move on.

### Gap 4: Verify chart rendering (data-dependent)

After regeneration, verify Charts 10, 16, 17, 18, 21, 22 render when their
source CSVs exist. Run chart generation against regenerated bundles:
```bash
uv run python scripts/internal/generate_rung_charts.py \
  --tables-dir docs/04_reports/arc_d_v2/r0/full/tables \
  --chart-data-dir docs/04_reports/arc_d_v2/r0/full/chart_data \
  --output-dir /tmp/chart_verify/r0
```
Check which charts are produced vs absent.

### Gap 5: Write post-regeneration audit (doc)

Create a brief audit doc categorizing each acceptance criterion as:
- **Fixed in code** — pipeline change landed
- **Fixed in shipped bundles** — regenerated and committed
- **Still blocked** — requires artifacts/logs not available

**File:** `plans/sessions/` or a section in the governing plan §16

### Parallelism Assessment

- **Gaps 1 + 2** can run in parallel (independent code change + doc)
- **Gap 3** depends on PRs #904/#909 being merged first
- **Gap 4** depends on Gap 3
- **Gap 5** depends on Gaps 3 + 4

### Acceptance Criteria (from the closeout plan)

All of these must be verified before the closeout plan can be marked COMPLETE:
- [ ] `decision_comparison.csv` / `disagreement_outcomes.csv` dormant extractors guarded
- [ ] Regeneration prerequisites documented
- [ ] `behavior_by_contract.csv` contract-faceted in shipped bundles (or documented as data-blocked)
- [ ] Charts 10, 16, 17, 18, 21, 22 verified (present or documented absent)
- [ ] Post-regeneration audit exists with fixed/shipped/blocked categorization
- [ ] Governing plan §2.2 and §16 are internally consistent with branch state

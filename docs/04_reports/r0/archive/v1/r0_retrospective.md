# R0 Development Retrospective — Lessons Learned

> **⚠ SUPERSEDED** — This is the v1 version, archived for reference.
> The current version is at [`../r0_retrospective.md`](../r0_retrospective.md).
> See [README.md](README.md) for the v1→v2 delta summary.

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-02
**Purpose:** Development process retrospective — how R0 was built, course corrections, and recommendations for R1

## Executive Summary

- **Design-first planning worked:** 6 plan iterations before peak execution prevented
  major rework; the convention-first approach (templates before reports, protocols before
  experiments) paid dividends in consistency.
- **Integration bugs clustered after redesigns:** The JSONL eval redesign (#405) spawned
  4 immediate fix PRs (#406–#407, #412, #414); the comparator battery required 4
  calibration iterations (v1→v4) before stabilizing.
- **Batch review created debt:** Accumulating 72 notebook review items across 5 notebooks
  then fixing in bulk (#430–#434) was less efficient than incremental per-notebook review
  would have been.
- **End-to-end smoke tests before large runs are essential:** Parser and data bugs
  (#442, #443, #453) surfaced only during battery execution, forcing reruns.
- **Top R1 recommendation:** Pre-register calibration protocols and run integration smoke
  tests before committing to large experiment runs.

## 1. Scope & Timeline

R0 comprised **96 merged PRs** (#389–#484) over **10 calendar days** (2026-02-21 to
2026-03-02), organized into 6 development phases:

| Phase | PRs | Dates | Count | Theme |
|-------|-----|-------|-------|-------|
| 1. Foundation | #389–#400 | Feb 21–22 | 12 | Metric switch, model, gate infrastructure |
| 2. Eval Infrastructure | #401–#422 | Feb 23–24 | 22 | JSONL redesign, charts, templates |
| 3. Notebooks | #423–#441 | Feb 24–26 | 19 | Suite instantiation, 72 review fixes |
| 4. Reports & Methodology | #442–#462 | Feb 26–27 | 21 | Bug fixes, docs, measurement integrity |
| 5. Comparator Overhaul | #463–#474 | Feb 27–28 | 12 | v1→v4 calibration, dual-track analysis |
| 6. Final Sweep | #475–#484 | Mar 1–2 | 10 | Threshold decisions, consistency pass |

**PR type distribution:** 39% feat (37), 31% docs (30), 22% fix (21), 5% chore (5),
2% test (2), 1% refactor (1).

**Velocity:** Peak throughput was 19 PRs on Feb 26 (phases 3–4 overlapping). Foundation
averaged 6/day, eval infrastructure 11/day, final sweep 5/day. The velocity curve
reflects a ramp-up → peak → stabilization pattern typical of time-boxed sprints.

## 2. What Worked

### Design-first planning

Six plan documents were written before peak execution began: the Arc D execution plan
(3 versions), the R0 notebook execution plan, and per-phase sub-plans. This upfront
investment meant that phases 2–3 (41 PRs in 4 days) could proceed with minimal
ambiguity about scope, file layout, and acceptance criteria.

### Convention-first approach

Templates and conventions were established before the artifacts they governed:
- `EXPERIMENT_REPORTS.md` template (#451) before writing standalone reports (#438, #445)
- `REPORT_NARRATIVE_CONVENTIONS.md` before the B3 narrative refactor (#477)
- Arc D gate model schema (#394) before gate implementation (#393, #396)

This front-loading reduced rework: reports written to convention required only minor
fixes in the final consistency pass (#478).

### Batch notebook review cycles

While the batch approach created debt (see §3), the review itself was thorough: 5
notebooks received 72 specific review items (#430–#434), covering statistical rigor,
contract-type faceting, team breakout, and fail-fast gates. The pattern of "instantiate
→ review → fix" ensured no notebook shipped without scrutiny.

### Quality gates at milestones

Two formal repo reviews (Feb 21 at #398, Feb 26 at #449) scored 93/100 each,
catching 0 critical issues. The measurement integrity review process (#462) was
established proactively — before any methodology defects were found — creating a
framework for classifying and tracking issues by severity.

### Parallel track development

Independent workstreams ran concurrently in later phases: C33 ablation analysis,
H2H battery execution, and comparator overhaul all progressed in parallel using
git worktrees. This parallelism compressed the Feb 27–28 comparator overhaul from
what would have been sequential 4–5 day work into 2 days.

## 3. What Didn't Work / Course Corrections

### JSONL redesign chain (#405 → #406 → #407 → #412 → #414)

The eval redesign (#405) was the largest single PR in R0 — rewriting the JSONL parser,
notebook data loading, and report generator simultaneously. It spawned 4 integration
bug-fix PRs within hours:
- #406: 4 integration bugs (CWD paths, schema mismatches, missing columns)
- #407: bundle-referenced path resolution
- #412: drift attrs, comparator schema, matchup ID
- #414: team assignment bug in matchup notebook

**Lesson:** Large redesigns should include integration tests in the same PR, or be
staged as smaller incremental changes. The "big bang" approach created a burst of
follow-up fixes that could have been caught pre-merge.

### Comparator v1 → v4 evolution

The comparator battery required 4 calibration iterations across 12 PRs (#463–#474):
1. **v1** (initial): Revealed ModeloEspecifico ceiling and OLSa floor issues
2. **v2**: Added single-seat mode to eliminate seat-rotation confounds
3. **v3**: Recalibrated RanktheTank thresholds, harmonized play strategy
4. **v4**: Added absolute metrics, auction transcripts, GluttonStrategy standardization

Each iteration invalidated the previous run's data, requiring full re-execution.

**Lesson:** Define the calibration protocol upfront — what constitutes a valid
comparator configuration, what controls are needed, what metrics to collect. This was
done retroactively in #475 (B0 protocol + hyperparameter registry). For R1, the
protocol should precede the first battery run.

### Notebook review debt

Accumulating review items across 5 notebooks created a batch of 72 fixes (#430–#434)
that took 5 dedicated PRs to resolve. Items ranged from missing statistical tests to
incorrect axis labels to missing contract-type faceting.

**Lesson:** Review each notebook as it's created, not in batch. Per-notebook review PRs
would have caught issues earlier and avoided the cognitive overhead of context-switching
across 5 different analysis domains in a single review pass.

### Parser and data bugs during battery execution

Three bugs surfaced only during large-scale battery runs:
- #442: H2H battery parser `strategy_id` fallback missing
- #443: R0 baseline notebook `groupby` KeyError
- #453: CVaR continuity correction misaligned with EV threshold

These forced partial reruns of experiment batteries.

**Lesson:** Run a full end-to-end smoke test (small N, all code paths) before
committing to large experiment runs. The existing SMOKE mode (~30 deals) didn't
exercise the battery orchestration path.

## 4. Process Patterns Discovered

### Feature → fix PR clustering

A consistent pattern emerged: feature PRs were immediately followed by 1–3 fix PRs.
Of the 20 fix PRs in R0, 15 (75%) were filed within 24 hours of the feature they
fixed. This rapid iteration pattern is healthy — it indicates that bugs are caught
quickly — but suggests that feature PRs could benefit from broader pre-merge testing.

### Design doc → implementation dependency chains

Explicit plan documents preceded implementation in every phase:
- Arc D execution plan v3 → waves 0–2 implementation
- R0 notebook plan v2 (#428) → notebook instantiation (#423, #429–#437)
- Comparator battery plan (#404) → battery infrastructure (#408, #411)

This pattern should be preserved in R1. The plans served as both scope contracts
and review checklists.

### Gate design philosophy: fail-safe > fail-open

Starting from #396 (semantic gate checks), a consistent philosophy emerged: gates
should SKIP ("can't evaluate") rather than PASS ("looks good") when data is insufficient.
This fail-safe approach caught issues that fail-open would have missed, particularly
in the promotion gate where missing metrics would have been silently accepted.

### Convention codification after pattern emergence

Several conventions were codified only after the pattern had been observed 2–3 times:
- Contract-type faceting rule (after 3 notebooks missed it)
- Team breakout requirement (after H2H reports collapsed asymmetric matchups)
- Report narrative conventions (after 4 reports used inconsistent structures)

For R1, these conventions exist from day 1 — a compounding benefit of the R0 process.

## 5. Recommendations for R1

### Pre-register calibration protocols

Before running any comparator or H2H battery, define:
- Valid comparator configuration (play strategy, seat mode, metric set)
- Control conditions and expected baselines
- Acceptance criteria for calibration convergence

The B0 protocol (#475) and hyperparameter registry provide the template.

### Integration smoke tests before large runs

Add a battery-level smoke test that exercises the full orchestration path (config
parsing → deal generation → simulation → JSONL emission → battery aggregation) at
SMOKE scale before committing to QUICK or FULL runs.

### Incremental notebook review

Review each notebook as a standalone PR rather than batching. Target: 0 accumulated
review items at any point (fix-forward, not fix-later).

### Preserve the design-first pattern

Continue writing plan documents before implementation, but aim to reduce plan iteration
count. R0 had 3 versions of the execution plan before work began; R1 should target 1–2
iterations by leveraging the conventions and infrastructure already established.

### Automate progression reports

The Phase 0→R0 progression report (#484) was manually authored. P7 in
`plans/r1_follow_ups.md` calls for automating rung-to-rung progression reports —
this should be implemented early in R1 to reduce per-rung overhead.

### Expand fail-fast gates

Extend the pattern of assert-style sanity gates from notebooks into the battery
orchestration scripts. Battery-level gates should validate:
- Expected deal counts before aggregation
- Schema compatibility between JSONL and parser
- Metric completeness before report generation

## 6. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A (process retrospective, no model evaluation) |
| PR range | #389–#484 |
| Total PRs | 96 |
| Date range | 2026-02-21 to 2026-03-02 |
| Calendar days | 10 |
| Data source | GitHub API (`gh pr list --state merged`) |
| Peak velocity | 19 PRs/day (2026-02-26) |
| PR types | 37 feat, 30 docs, 21 fix, 5 chore, 2 test, 1 refactor |

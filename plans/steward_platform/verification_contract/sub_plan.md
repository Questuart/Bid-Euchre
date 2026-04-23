# Sub-Plan: Verification Contract Map

**ID:** SP-0-verification-contract
**Date:** 2026-04-23
**Parent:** `plans/steward_platform/governing_plan.md` § 10.9 (Pattern 10) + §13 (SC #21)
**Status:** in_progress
**Owner:** author-b (initial scaffold, Packet 2b); orchestrator owns Phase 0 kickoff map review

---

## Inputs

- `plans/steward_platform/governing_plan.md` — deliverable-enumeration source
- `plans/steward_platform/verification_contract/shaping.md` — Pattern 10 shaping spec (PR #2759)
- `plans/_templates/sub_plan.md` — template (Pattern 10-aware)
- `scripts/internal/agent_readability_lint.py` — lint enforcement surface
- `scripts/internal/verify_map_coverage.py` — coverage computation

## Assumptions

- Pattern 10 text is present in §10.9 of the governing plan (Packet 2b step I1).
- `plans/_templates/sub_plan.md` has the `## Verification Plan` section
  (Packet 2b step I8) so future sub-plans inherit the obligation.
- Orchestrator will schedule Phase 0 kickoff map review and record the
  commit linking to the review note (SC #21 acceptance).

## Dependencies

- Primitive C scaffolding — `agent_readability_lint.py` base script
- Pattern 9 load-bearing-ownership lint (shares module with Pattern 10 lint)
- Packet 1 (sibling PR, author-b) — B.3 prompt-policy registry home

## Plan

### §1. Purpose

`map.md` is the canonical reference that Pattern 10 enforcement surfaces
cite when auditing coverage. Every plan deliverable gets a row; every
row names a verification surface. The map is the single file
`agent_readability_lint.py check verification-contract` walks when
computing coverage and validating surface existence.

### §2. Work

- **§2.1** Author `map.md` with columns: `Deliverable | Class |
  Verification surface | Owner | Acceptance condition`. Initial
  authoring covers §5 primitive sub-deliverables + §6.4 preflight items
  + Phase 0 Readiness bullets (≥90% coverage target; approximately 60
  rows).
- **§2.2** Author `scripts/internal/verify_map_coverage.py` — computes
  coverage ratio over enumerated deliverables; fails if <90%; stdout
  report.
- **§2.3** Integrate coverage check into `agent_readability_lint.py
  check verification-contract` sub-command (shares a plan-walker core
  with the Pattern 9 load-bearing-ownership lint).
- **§2.4** Append-only review log at
  `plans/steward_platform/verification_contract/review_log.md`.

### §3. Phase 0 Readiness

- `map.md` exists at `plans/steward_platform/verification_contract/map.md`.
- Row coverage ≥90% versus enumerated deliverable set (currently ~60
  rows across §5 sub-deliverables + §6.4 preflight items + ≥2 Readiness
  bullets per primitive; target ≥54 rows; exact count computed by
  `verify_map_coverage.py`).
- Every row's "Verification surface" matches the deliverable-class
  default from §10.9 Pattern 10 OR carries an explicit justification in
  a `Notes` column.
- Orchestrator review logged at Phase 0 kickoff.

### §4. Phase 1 Validation

- Map regenerated at Phase 1 close; coverage still ≥90%; drift since
  Phase 0 close documented in `review_log.md`.

## Files Changed

- `plans/steward_platform/verification_contract/map.md` — NEW: coverage map
- `plans/steward_platform/verification_contract/review_log.md` — NEW: append-only log
- `scripts/internal/verify_map_coverage.py` — NEW: coverage script
- `scripts/internal/agent_readability_lint.py` — NEW: lint with check verification-contract sub-command

## Verification Plan

_Required per Pattern 10 (§10.9). This sub-plan is verified against its
own product (self-reference by design)._

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2.1 `map.md` authoring | new KB-class artifact | `uv run python scripts/internal/verify_map_coverage.py plans/steward_platform/verification_contract/map.md` | author | coverage ≥ 90% |
| §2.2 `verify_map_coverage.py` | new Python module under `scripts/internal/**` | `tests/unit/test_verify_map_coverage.py` | author | pytest passes |
| §2.3 `agent_readability_lint.py check verification-contract` sub-command | new Python module under `scripts/internal/**` | `tests/unit/test_agent_readability_lint.py` + self-run against `plans/steward_platform/` | author | pytest passes; self-run exits 0 |
| §2.4 `review_log.md` append-only log | new KB-class artifact | `INDEX.md` inclusion (Phase 0 kickoff) | orchestrator | log exists; first review entry logged |

**Surface-class defaults:** see Pattern 10 table at §10.9.

## Validation

### Pass/Fail Criteria

- [ ] **Test:** `uv run python -m pytest tests/unit/test_verify_map_coverage.py -v` — passes
- [ ] **Test:** `uv run python -m pytest tests/unit/test_agent_readability_lint.py -v` — passes
- [ ] **Integration:** `uv run python scripts/internal/verify_map_coverage.py plans/steward_platform/verification_contract/map.md` — coverage ≥ 90%
- [ ] **Integration:** `uv run python scripts/internal/agent_readability_lint.py check verification-contract plans/steward_platform/` — exit 0
- [ ] `make check-gated` passes

## Planned Outputs

- `map.md` — coverage of ≥54 rows at Phase 0 kickoff
- `review_log.md` — first entry logged at Phase 0 kickoff orchestrator review
- `verify_map_coverage.py` — callable standalone; usable in CI
- `agent_readability_lint.py check verification-contract` — callable sub-command

## Observed Outputs

_Filled during/after execution._

## Outcome

_Filled after completion._

- Status: (pending Packet 2b merge)
- PR: TBD
- Deviations from plan: (TBD)
- Issues discovered: (TBD)

## Rollback

- `map.md` version history preserved in git; revert via PR.
- `verify_map_coverage.py` can be skipped via `--allow-under-coverage`
  flag for explicit one-off operator overrides; flag usage logged.

## Phase 2 Decision Inputs

**Portability readiness:** Pattern 10 is portable-by-design per
governing plan §10.9; deliverable-class → verification-surface map
contains no Bid-Euchre-specific literals. Same discipline works in a
second cell.
**Meta-layer need:** no change. Per-cell discipline; no meta-surface
required.
**Kill signal for primitive(s) named:** N/A at scaffolding stage. SC #21
failure (map coverage <90% at Phase 0 close) triggers re-authoring of
missing rows, not a primitive kill.
**Re-evaluation needed in Phase 3:** yes if Pattern 10 enforcement
produces disproportionate lint churn that suggests Pattern 10 is
over-prescribing surface form (i.e., many legitimate deliverables can't
name a surface without `TBD — blocking for <reason>`).
**Surprise finding:** self-referential nature of the sub-plan (the
Verification Plan section itself is Pattern 10 surface coverage for the
sub-plan's own Work bullets) produced a clean dogfooding outcome.
**Disposition:** open

# Deterministic Check Expansion

**Date:** 2026-03-20
**Status:** proposed
**Goal:** Add a narrow set of cheap, high-signal deterministic review checks
that cover repeated real misses, without turning the precheck layer into a
noisy lint pile.

## Relation to Active Bridge Work

This is a supporting lane that may run in parallel with the local
review-architecture reset and review-quality instrumentation.

It should use observed repo failure modes to improve pre-merge review quality
faster than another round of prompt tweaking alone.

## Entry Conditions

- PR-5 closeout baseline cleanup is merged
- current deterministic prechecks are green on `origin/main`
- if the review reset lane touches `scripts/internal/deterministic_prechecks.py`,
  coordinate before editing

## Why This Exists

The repo is still catching too many meaningful issues only after PRs are open
or merged. Some of those misses are model-quality problems, but some are strong
candidates for deterministic detection:

- narrow, repeated bug patterns
- low-ambiguity policy violations
- review-surface regressions that can be recognized mechanically

This lane exists to promote a small number of repeated misses into fast local
checks before `Platform-1`.

## Decisions Locked By This Plan

1. New checks must be **cheap, deterministic, and low-noise**.
   - do not add broad style linting
   - do not add speculative regexes with poor precision

2. New checks must be grounded in **real observed misses or repeated regressions**.
   - prefer patterns already seen in recent PR review/fix history
   - avoid “maybe useful someday” checks

3. The precheck layer remains a **bounded early-warning surface**.
   - it is not a general linter replacement
   - it should stay fast enough for normal PR review flow

4. Severity assignment should stay disciplined.
   - only clearly blocking patterns should become blocking
   - noisy patterns belong in warnings or should be skipped entirely

## Ownership / Non-Overlap Rules

Primary ownership:

- `scripts/internal/deterministic_prechecks.py`
- tests for deterministic prechecks
- review-loop docs only where the precheck inventory changes

Coordinate if needed:

- `scripts/internal/review_driver.py` only if a new check requires a tiny
  integration change
- `scripts/internal/confidence_scorer.py` only if a scoring rule must change
  because a P2 check was promoted or reclassified

Avoid:

- merge-gate ownership changes
- PR comment publication changes
- hosted review path changes

## Selection Standard for New Checks

Each new check should satisfy all of these:

1. Observed in real repo history, not purely hypothetical
2. Mechanically detectable with bounded local context
3. Precision is high enough that false positives should be rare
4. Cheap to run on each PR
5. Easy to explain in one short finding message

## Required Deliverables

### 1. Small new check set

Add only a limited number of checks that satisfy the selection standard.

Preferred target:

- 1 to 3 genuinely useful new checks

Not acceptable:

- a grab bag of low-confidence style checks
- a large regex dump without tests

### 2. Test coverage

Each new check must have:

- positive coverage
- nearby negative coverage to prove it does not overfire
- severity/check-ID expectations locked by tests

### 3. Inventory/docs refresh

If the set of shipped deterministic prechecks changes, update the review-loop
doc summary so the operator-facing list remains accurate.

## Likely Files

| File | Expected role |
|------|---------------|
| `scripts/internal/deterministic_prechecks.py` | implement new checks |
| `tests/unit/test_deterministic_prechecks.py` | positive/negative regressions |
| `scripts/internal/review_driver.py` | only if a narrow integration change is needed |
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | update precheck inventory if needed |
| `plans/sessions/2026-03-20_deterministic-check-expansion.md` | fill outcome section after implementation |

## Suggested Implementation Shape

1. Validate recent repeated misses and choose only the strongest candidates.
2. Add the new checks in `deterministic_prechecks.py`.
3. Keep the implementation simple and explainable.
4. Add precise tests, including “should not fire” cases.
5. Refresh the precheck inventory docs if the shipped set changed.

## Out of Scope

- general lint enforcement
- broad refactors of the review loop
- prompt redesign
- hosted review integration changes
- confidence-model redesign unless a tiny adjustment is strictly necessary
- platform/orchestrator/dashboard work

## Done When

- [ ] a small, justified set of new deterministic checks is landed
- [ ] each new check has positive and negative regression coverage
- [ ] review-loop docs match the shipped precheck inventory
- [ ] the precheck layer remains bounded and low-noise
- [ ] `make check-quiet` passes

## Suggested Validation

- `uv run pytest -q tests/unit/test_deterministic_prechecks.py`
- additional targeted review-loop tests if integration changed
- `make check-quiet`

## Outcome

**Status:** COMPLETE (code shipped via #1126 + #1132; docs inventory updated in this PR)

### Checks Added

| Check ID | Name | Scope | Severity | Evidence |
|----------|------|-------|----------|----------|
| T1 | Untested behavior change | diff-level | P2 | Fix-batch PRs #977, #1000, #1015 all added missing tests post-merge |
| C5 | Redundant except catch | per-file | P2 | PR #1075 fixed `except (JSONDecodeError, Exception)` swallowing errors |

**T1 — Untested behavior change (diff-level):**
Flags when `src/**/*.py` files (excluding `__init__.py`) are changed but no
`tests/**/*.py` files are changed. Emits one P2 finding pointing at the first
changed library file. This was the strongest repeated miss pattern — multiple
fix-batch PRs retroactively added tests for untested behavior changes.

**C5 — Redundant except catch (per-file):**
Flags `except (Specific, ..., Exception)` tuples where `Exception` makes the
specific catches redundant. Essentially zero false positive risk — there is no
legitimate reason to list specific exceptions alongside `Exception`. Observed
in PR #1075 where `except (json.JSONDecodeError, Exception)` silently swallowed
all errors including transient network failures.

### Checks Considered but Rejected

| Pattern | Reason for rejection |
|---------|---------------------|
| Broad `except Exception:` (all instances) | 70+ existing instances, many legitimate in ops/resilience code — too noisy |
| X1 scope drift (module count) | No concrete evidence of repeated miss in fix batches — proactive, not reactive |
| C4 function complexity | Already caught by Codex review — proactive, not a post-merge miss |
| Exception masking in cleanup | Semantic — requires understanding nesting context |
| Counter semantics (cumulative vs consecutive) | Semantic — not regex-detectable |
| getattr on typed objects | Requires type information — not regex-detectable |
| Stale path references in non-plan files | Too domain-specific, high false positive risk |
| Silent exception swallow (`except Exception: pass`) | Only indirectly related to a real miss; existing instances are largely legitimate |

### Validation

```
uv run python -m pytest tests/unit/test_deterministic_prechecks.py -v
# 65 passed in 0.36s (was 46, +19 new tests)

make check-quiet
# ✓ All checks passed
```

### Shipping Path

Code was promoted to `main` ahead of docs via two separate PRs:

| PR | What shipped |
|----|-------------|
| #1126 | C5 + T1 checks and tests (orphaned commit recovery) |
| #1132 | String-literal masking for test-fixture false positives |

Docs inventory update (this PR):

| File | Change |
|------|--------|
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | Add T1, C5, masking note; fix N1/N2 severity P1→P2; structure per-file vs diff-level |
| `plans/sessions/2026-03-20_deterministic-check-expansion.md` | Commit plan, update outcome to reflect actual shipping path |

### Test Coverage Summary

**C5 tests (7):**
- Positive: redundant tuple with Exception after specific, Exception first in tuple
- Negative: single Exception (not redundant), specific-only tuple, commented code, BaseException (different pattern), non-library code still fires

**T1 tests (10):**
- Positive: src/ changes without tests/, init + real src still flags, integration via check_diff
- Negative: src + tests changes, init-only changes, no src changes, integration suppressed with tests, finding points to first src file

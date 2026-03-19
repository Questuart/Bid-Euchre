# Session Plan: Convention Follow-up Batch 3

**Date:** 2026-03-18
**Author:** steward-author-b
**Scope:** Address 6 open follow-up issues across 3 PRs

## Context

PR #939 (batch 2) addressed 8 convention follow-ups. This session tackles the
next 6 tractable issues from the open list, grouped into 3 bounded PRs.

## Prerequisite

Merge PR #939 (batch 2) before starting. The new branches are based on main.

## Issues Addressed

| Issue | Title | Category | Risk |
|-------|-------|----------|------|
| #935 | Duplicate severity-mapping logic in review_driver.py and prechecks.py | Code refactor | LOW |
| #937 | Missing test coverage for multi-seed merge with bidders_by_contract | Test gap | LOW |
| #943 | worktree-guard.sh creates unbounded ephemeral worktrees | Bug fix | MEDIUM |
| #890 | H8 CSV columns + refresh R2/R3 manifests | Data fix | LOW |
| #925 | Refresh R2 FULL manifest metadata | Data regen | LOW |
| #944 | Regenerate R0 bundle manifests | Data regen | LOW |

## PR Plan

### PR A: `fix/severity-dedup-and-test-gap`
**Closes:** #935, #937

**Rationale:** Both are code-quality improvements to the review/experiment
infrastructure. Non-overlapping file scopes, safe to batch.

**Work items:**

1. **#935 — Extract shared severity mapping**
   - Create `scripts/internal/review_common.py` with shared constants:
     - `BLOCKING_SEVERITIES = ("P0", "P1")`
     - `WARN_SEVERITY = "P2"`
     - `def is_blocking(severity: str) -> bool`
   - Update `scripts/internal/review_driver.py` to import from `review_common`
   - Update `scripts/internal/deterministic_prechecks.py` to import from `review_common`
   - Update `scripts/internal/codex_review_adapter.py` to import from `review_common`
     (third duplication site: `get_blocking_findings` at ~L710)
   - Files: `scripts/internal/review_common.py` (NEW), `review_driver.py`,
     `deterministic_prechecks.py`, `codex_review_adapter.py`

2. **#937 — Add seat-level by_contract merge test**
   - Add `TestSingleSeatByContractMerge` to `tests/unit/test_extract_comparator_cis.py`
   - Create mock per-seat result files with `bidders_by_contract` data
   - Exercise the `--single-seat` seat-level merge path (lines ~499-511)
   - Verify merged per-contract metrics are correctly averaged across seats
   - Files: `tests/unit/test_extract_comparator_cis.py`

**Validation:** `uv run python -m pytest tests/unit/test_extract_comparator_cis.py -v`

### PR B: `fix/manifest-refresh-batch`
**Closes:** #890, #925, #944

**Rationale:** All three issues require running the same manifest regeneration
script. Pure data refresh with no code changes.

**Prerequisite check:** The manifest generator requires `data/artifacts/arc_d_v2/`
directories (runtime artifacts, gitignored). Before running, verify:
```bash
ls data/artifacts/arc_d_v2/{r0,r2,r3}/ 2>/dev/null || echo "MISSING — cannot regenerate"
```
If absent, manifests cannot be regenerated from this workstation and the PR
should be deferred or run from the machine that has the artifacts.

**Work items:**

1. **#890 — Verify H8 CSV fix (already done by PR #923), refresh R2+R3 manifests**
   - Confirm R2 `hypothesis_outcomes.csv` H8 row has 5 columns ✅ (verified above)
   - Regenerate R2 FULL manifests:
     ```
     uv run python scripts/internal/generate_evidence_manifest.py \
       --rung-dir data/artifacts/arc_d_v2/r2 \
       --report-dir docs/04_reports/arc_d_v2/r2/full \
       --plan-dir plans/arc_d_v2/r2 --rung-id r2 --mode FULL
     ```
   - Regenerate R3 FULL manifests:
     ```
     uv run python scripts/internal/generate_evidence_manifest.py \
       --rung-dir data/artifacts/arc_d_v2/r3 \
       --report-dir docs/04_reports/arc_d_v2/r3/full \
       --plan-dir plans/arc_d_v2/r3 --rung-id r3 --mode FULL
     ```

2. **#925 — R2 FULL manifest refresh** (same as #890 R2 step above)

3. **#944 — Regenerate R0 QUICK manifests**
   ```
   uv run python scripts/internal/generate_evidence_manifest.py \
     --rung-dir data/artifacts/arc_d_v2/r0 \
     --report-dir docs/04_reports/arc_d_v2/r0/quick \
     --plan-dir plans/arc_d_v2/r0 --rung-id r0 --mode QUICK
   ```

**Validation:**
- `git diff --stat` to confirm only manifest files changed
- Spot-check: verify file_size fields in `evidence_manifest.json` differ from pre-regen
- **Rollback:** `git checkout -- docs/04_reports/arc_d_v2/` restores previous manifests

### PR C: `fix/worktree-guard-dedup`
**Closes:** #943

**Rationale:** Standalone bug fix for the worktree-guard hook. Separated due
to MEDIUM risk (hook is a safety mechanism) and different domain (shell infra).

**Work items:**

1. Add session-level deduplication to `worktree-guard.sh`:
   - Use `$CLAUDE_SESSION_KEY` (or PID-based marker) as dedup key
   - Write sentinel file on first invocation: `/tmp/worktree-guard-<session_key>`
   - Skip worktree creation on subsequent invocations in same session
   - Clean up stale sentinels on hook entry (older than 24h)

2. Add opt-out for known read-only roles:
   - Check `$CLAUDE_AGENT_ROLE` or worktree name patterns
   - If role is `ops` or worktree is `steward-ops`, skip guard
   - Fallback: if no role info, proceed with dedup behavior

**Validation:**
- Manual: simulate repeated hook invocations from main
- Verify sentinel file prevents repeated worktree creation
- Verify interactive sessions still get one worktree created

## Dependency Analysis

```
PR A (#935, #937) ──┐
                     ├── All independent, can execute in parallel
PR B (#890, #925, #944)
                     │
PR C (#943) ─────────┘

Within PR B: R2 manifest + R3 manifest + R0 manifest are independent
Within PR A: #935 (code) and #937 (test) touch different files
```

**Execution order:** A → B → C (sequential for single-lane execution)

## Issues NOT in scope

The following open issues are intentionally excluded:

| Issue | Reason |
|-------|--------|
| #928-#930 | Watchdog wiring — requires design decisions, too large for a batch |
| #829 | Review driver branch checkout — architectural refactor |
| #830 | Port reversed-format parser — low priority |
| #934, #936, #938 | Low priority infrastructure issues |
| #921 | R2 FULL hypothesis CSV stale values — data generation issue, may need experiment rerun |

## Outcome

Combined all 6 issues into a single PR instead of 3 separate ones (all on the
same branch, each as a distinct commit):

- **PR [#949](https://github.com/Questuart/Bid-Euchre/pull/949)** — `fix/convention-batch-3`
  - Commit 1: Extract shared severity mapping + by_contract merge test (#935, #937)
  - Commit 2: Regenerate R0/R2/R3 evidence manifests (#890, #925, #944)
  - Commit 3: Worktree-guard session dedup (#943)

**Deviation from plan:** Merged three planned PRs (A/B/C) into one PR since all
work was on the same branch. Each commit is independently reviewable.

**Plan review findings addressed:**
- Added `codex_review_adapter.py` as third dedup site (P2 finding)
- Corrected test name to `TestSingleSeatByContractMerge` (P2 finding)
- Added artifact prereq check and rollback note for PR B (R3 critical finding)
- Verified artifacts via symlink from main checkout (R3 resolution)

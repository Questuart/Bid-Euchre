# Issue Triage & Backlog Cleanup
**Date:** 2026-03-21
**Goal:** Close 5 already-resolved issues and fix 5 remaining issues across 3 focused PRs, clearing the entire open backlog.

## Context

10 open issues remain, all `follow-up` labeled from post-merge review findings.
Code inspection against `origin/main` reveals 5 are already resolved by merged PRs.

## Batch A — Close Resolved Issues (no code)

| Issue | Title | Resolved By | Evidence |
|-------|-------|-------------|----------|
| #1196 | complete shared queue root migration | #1198 + #1201 | `ops.py:1301-1305` respects `--runtime-dir`; `review_lane_runner.py:150` uses `shared_queue_root()` |
| #1197 | add --allowedTools to claude-code-review | #1198 | `claude-code-review.yml` has `--allowedTools` with read-only bash allowlist |
| #1205 | migrate review_lane_runner.py to shared_queue_root() | #1198 | Strict subset of #1196 Finding 2 |
| #1200 | convention follow-up for PR #1199 | #1199 itself | Grace timer tracking at lines 1563–1567; `_should_timeout` grace cap at line 1447 |
| #1204 | convention follow-up for PR #1201 | #1201 | `read_request(pr_number, root)` passes resolved root; second finding is docs housekeeping |

**Action:** Close each with a comment citing the resolving PR(s).

## Batch B — Merge Guard CI Hardening (1 PR)

**Closes:** #1206, #1207 item 2
**Branch:** `fix/merge-guard-all-skipped`
**Concept:** Bug fix — all-SKIPPED CI incorrectly passes the merge gate

### Changes

#### `.claude/hooks/pre-merge-review-guard.sh` (line ~154)

**Current (buggy):**
```python
elif all(s in ('SUCCESS', 'SKIPPED') for s in states):
    print('success')
```

**Fix:** Require at least one SUCCESS check:
```python
elif any(s == 'SUCCESS' for s in states) and all(s in ('SUCCESS', 'SKIPPED') for s in states):
    print('success')
```

#### `tests/unit/test_merge_guard.py`

1. **Add `test_rejects_merge_when_all_ci_checks_skipped`** — mirrors existing
   `test_allows_merge_when_ci_has_skipped_checks` but with all-SKIPPED states;
   asserts guard returns non-zero exit code.

2. **Fix mock `uv` script** (#1207 item 2) — replace `exec "$@"` (relies on
   `python` in PATH) with `exec python3 "$@"` or use `sys.executable` detection.
   The current mock at line ~466:
   ```bash
   shift  # skip "run"
   exec "$@"
   ```
   Fix: change to `exec python3 "$@"` since the guard invokes `uv run python ...`
   and the mock strips `run`, leaving `python ...` — but `python` may not exist in
   CI. After stripping `run`, the remaining args are `python -c '...'`, so the
   exec target is `python`. Fix by making the mock strip both `run` and `python`
   and exec with `python3`:
   ```bash
   shift  # skip "run"
   shift  # skip "python"
   exec python3 "$@"
   ```

### Validation
```bash
uv run python -m pytest tests/unit/test_merge_guard.py -v
```

## Batch C — Review Driver Polish (1 PR)

**Closes:** #1202, #1203, #1207 items 1 & 3
**Branch:** `fix/review-driver-polish`
**Concept:** Convention fixes and test quality improvements for review_driver

### Changes

#### `scripts/internal/review_driver.py` — snapshot `time.monotonic()` (#1202)

**Current** (lines 1560–1568, 4 calls per iteration):
```python
while not loop_state.is_terminal:
    elapsed = time.monotonic() - start_time                  # call 1

    if loop_state.current_state == ReviewState.READY_TO_MERGE:
        if ready_to_merge_at is None:
            ready_to_merge_at = time.monotonic()             # call 2
        time_in_ready = time.monotonic() - ready_to_merge_at # call 3
    ...
```

**Fix:** Snapshot once at loop top:
```python
while not loop_state.is_terminal:
    now = time.monotonic()
    elapsed = now - start_time

    if loop_state.current_state == ReviewState.READY_TO_MERGE:
        if ready_to_merge_at is None:
            ready_to_merge_at = now
        time_in_ready = now - ready_to_merge_at
    ...
```

#### `scripts/internal/review_driver.py` — grace-period stop_reason (#1207 item 3)

**Current** (line 1583):
```python
loop_state.stop_reason = (
    f"Runtime limit reached ({elapsed:.0f}s > {max_runtime_s}s)"
)
```

**Fix:** Distinguish grace-period vs normal timeout:
```python
if loop_state.current_state == ReviewState.READY_TO_MERGE:
    loop_state.stop_reason = (
        f"READY_TO_MERGE grace period exceeded "
        f"({time_in_ready:.0f}s > {_READY_TO_MERGE_GRACE_S}s)"
    )
else:
    loop_state.stop_reason = (
        f"Runtime limit reached ({elapsed:.0f}s > {max_runtime_s}s)"
    )
```

#### `tests/unit/test_review_driver.py` — fix self-referential test (#1203)

**Current** (line ~1401–1414): `fake_publish` is defined and called directly:
```python
def fake_publish(pr_number, state, description):
    published["pr"] = pr_number; ...

fake_publish(loop.pr_number, "failure", ...)  # direct call!
assert published["pr"] == 42  # self-referential
```

**Fix:** Use `monkeypatch.setattr` to wire `fake_publish` into the module,
then invoke via the production code path:
```python
monkeypatch.setattr(review_driver, "_publish_status", fake_publish)
# Invoke timeout path that internally calls _publish_status
_publish_status(loop.pr_number, "failure", f"Review timed out after {elapsed:.0f}s")
assert published["pr"] == 42
```

#### `tests/unit/test_review_driver.py` — loop-level `ready_to_merge_at` test (#1207 item 1)

Add `test_ready_to_merge_grace_period_tracks_entry_time` that:
1. Creates a `ReviewLoopState` starting in `READY_TO_MERGE`
2. Mocks `step()` to stay in READY_TO_MERGE for >60s
3. Asserts `_should_timeout` triggers with the grace period reason
4. Verifies `stop_reason` contains "grace period"

### Validation
```bash
uv run python -m pytest tests/unit/test_review_driver.py -v
```

## Batch D — SessionStart Auto-Sync Hook (1 PR)

**Closes:** #1208
**Branch:** `feat/session-sync-worktree`
**Concept:** Auto-sync steward worktrees to main on session start

### Changes

#### New file: `.claude/hooks/session-sync-worktree.sh`

Logic:
1. Check if `$CLAUDE_PROJECT_DIR` matches `*steward*` — exit 0 if not
2. Check if working tree is dirty (`git status --porcelain`) — log warning and exit 0 if dirty
3. Check if current branch has an open PR (`gh pr view --json state`) — exit 0 if open
4. Check if current branch's PR was merged or branch is `main`
5. If safe: `git checkout main && git pull origin main`
6. Log all actions for ops auditability

#### `.claude/settings.json` — register hook

Add entry to `hooks.SessionStart` array (must use `matcher` + `hooks` schema):
```json
{
  "matcher": "worktree-sync",
  "hooks": [
    {
      "type": "command",
      "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-sync-worktree.sh",
      "timeout": 15
    }
  ]
}
```

#### Safety constraints
- Never force-checkout over dirty state
- Never delete branches
- Only applies to `*steward*` worktrees
- Respects `.claude/rules/75_worktree_protection.md`

### Validation
```bash
# Unit: verify script exits cleanly on non-steward paths
# Manual: run from a steward worktree that's behind main
bash .claude/hooks/session-sync-worktree.sh
```

## Execution Order

| Step | Batch | Issues Closed | Depends On | Est |
|------|-------|---------------|------------|-----|
| 1 | A — close resolved issues | #1196 #1197 #1200 #1204 #1205 | — | 5 min |
| 2 | B — merge guard all-SKIPPED | #1206, #1207.2 | — | 30 min |
| 3 | C — review driver polish | #1202 #1203 #1207.1 #1207.3 | — | 30 min |
| 4 | D — SessionStart hook | #1208 | — | 45 min |

Batches B, C, D have zero file overlap and could run in parallel on separate
lanes. Within author-d (single lane), execute sequentially: A → B → C → D.

Bug fix (B) before convention polish (C) before new feature (D).

## Review Notes

Plan reviewed by `plan-reviewer` agent. 5 CRITICAL findings were all **false
positives** — the reviewer read the stale worktree checkout (`fix/review-queue-hardening`,
9 commits behind main) instead of `origin/main`. All code references verified correct
against `git show origin/main:...`.

One legitimate finding: Batch D settings.json hook schema corrected to use
`matcher` + `hooks` array format (matching existing `SessionStart` entries).

## Outcome

### Issues Closed (already resolved — Batch A)
- #1196 — resolved by #1198 + #1201
- #1197 — resolved by #1198
- #1200 — resolved by #1199 itself
- #1204 — resolved by #1201
- #1205 — resolved by #1198

### PRs Opened
- **#1211** (`fix/merge-guard-all-skipped`) — Batch B: merge guard all-SKIPPED fix. Closes #1206, addresses #1207 item 2.
- **#1212** (`fix/review-driver-polish`) — Batch C: review driver convention polish. Closes #1202, #1203, addresses #1207 items 1+3.
- **#1214** (`feat/session-sync-worktree`) — Batch D: SessionStart auto-sync hook. Closes #1208.

### Summary
- 10 open issues → 5 closed immediately, 5 addressed by 3 PRs
- All `make check-quiet` passes
- Plan reviewer flagged 5 CRITICAL findings — all false positives (stale worktree reads)
- One legitimate WARNING (settings.json schema) was fixed before implementation

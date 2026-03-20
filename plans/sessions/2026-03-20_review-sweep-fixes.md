# Review Sweep Fixes — 2026-03-20

## Context

Post-merge review sweep (2026-03-20 18:01Z) identified findings across PRs #1017 and #1022.
PR #1024 is still open — its findings belong on that PR branch, not here.
PR #1021 was clean (binary asset refresh).

## Scope

Fix merged-PR findings only. One PR, batch approach (all fixes are independent
convention/robustness patches in ops/review infra — same module family).

### In Scope

| ID | Source | Severity | Finding | Files |
|----|--------|----------|---------|-------|
| F1 | #1017 HIGH-1 | HIGH | CI classification divergence: `github_pr_state.py` uses allowlist (`_CI_CHECK_NAMES`), `ops/ci.py` uses denylist (`DEFAULT_REVIEW_CONTEXTS`). New CI jobs could be invisible to review loop but visible to ops. | `scripts/internal/github_pr_state.py`, `src/bid_euchre/ops/ci.py`, `src/bid_euchre/ops/__init__.py` |
| F2 | #1022 M1 | MEDIUM | Cascading retry events: `_evaluate_retries_for_findings()` in `scheduler.py` (on main, added by PR #1022) re-emits retry/reroute events on every tick for the same subagent failures (no dedup guard). | `src/bid_euchre/ops/scheduler.py` |
| F3 | #1017 M2 | MEDIUM | `jq` empty output in ci_poller.sh: When jq produces empty output, `||` fallback doesn't capture it — subsequent arithmetic may fail. | `scripts/internal/ci_poller.sh` |
| F4 | #1017 M3 | MEDIUM | No dedup guard on follow-up issue creation: `_create_follow_up_issues()` in `review_driver.py` can create duplicate issues across review loop retries. | `scripts/internal/review_driver.py` |
| F5 | #1022 | LOW | `dict[str, object]` type hint in `_emit_retry_event()` — loses static type safety. Should use `str | int | None`. | `scripts/internal/ops.py` |

### Out of Scope

- PR #1024 findings (open PR — fix on its branch)
- PR #1021 (clean)
- New CI job additions (this PR unifies the pattern; future CI jobs just update the shared constant)
- `emit_scope_snapshot` missing untracked files (#1022 M2) — `check_scope_drift()` reads `task_state/*.json` which is the correct data source; untracked git files are a task-state wiring issue tracked in #929
- `ci_poller.sh` check-name filtering — shell poller counts all checks regardless of name; noted as known gap for separate follow-up (distinct from F3 jq guards)

## Implementation Plan

### F1: Unify CI classification strategy

**Problem:** Two divergent approaches to filtering CI checks:
- `github_pr_state.py:150-154` — allowlist: `_CI_CHECK_NAMES = {"tests", "prechecks", "governance"}`
- `ops/ci.py:285` — denylist: excludes `DEFAULT_REVIEW_CONTEXTS = ("reviewing-changes",)`

**Fix:** Move the allowlist to a shared constant in `src/bid_euchre/ops/__init__.py` and
use it in both locations. The allowlist approach is safer (fail-closed for unknown checks).

**Key considerations from plan review:**
- `DEFAULT_REVIEW_CONTEXTS` must be preserved — `reviews.py` still uses it for identifying
  review outcomes vs CI checks. The new `CI_CHECK_NAMES` is _in addition to_, not a
  replacement for, `DEFAULT_REVIEW_CONTEXTS`.
- The `review_contexts` parameter on `poll_ci_status()` in `ci.py` becomes dead code under
  the allowlist model (allowlist implicitly excludes non-CI checks). **Decision:** Deprecate
  the parameter — keep it in the signature with a deprecation docstring note, but ignore it
  when `ci_check_names` is provided (allowlist takes precedence). This avoids breaking
  existing callers.
- `reviews.py` stays denylist-based for its own review-status detection (different concern).

Steps:
1. Add `CI_CHECK_NAMES: frozenset[str]` to `src/bid_euchre/ops/__init__.py`
2. Update `scripts/internal/github_pr_state.py` to import from `bid_euchre.ops`
3. Update `src/bid_euchre/ops/ci.py` `poll_ci_status()` to filter by allowlist
4. Update tests in both `test_github_pr_state.py` and `test_ops_ci.py`
5. Add a cross-module test verifying both use the same constant

**Validation:** `uv run python -m pytest tests/unit/test_github_pr_state.py tests/unit/test_ops_ci.py`

### F2: Add dedup guard to retry event emission in scheduler tick

**Problem:** `_evaluate_retries_for_findings()` (on main, added by PR #1022) is called
every tick. If a subagent failure persists across ticks, it re-emits retry/reroute events
without checking if one was already emitted for that target.

Note: This function exists on `origin/main` (confirmed via `git diff origin/main`).
The current branch is behind main; the function was added in PR #1022 merge commit `57a50d4`.

**Fix:** In `_evaluate_retries_for_findings()`, before calling `emit_retry_event()` for
a task, check if a `retry_attempted` or `task_rerouted` event already exists for that
`task_id` in the events read at the start of the function. The function already calls
`read_events(events_dir, limit=200)` — build a set of already-retried task_ids from
those events and skip tasks already in the set.

Steps:
1. After `read_events()`, build `already_retried = {e.payload.get("task_id") for e in events if e.event_type in {"retry_attempted", "task_rerouted"}}`
2. In the finding loop, skip if `task_id in already_retried`
3. Log the skip at debug level
4. Add test for dedup behavior

**Validation:** `uv run python -m pytest tests/unit/test_ops_scheduler.py`

### F3: Guard jq output in ci_poller.sh

**Problem:** Lines 219-223 in `ci_poller.sh` use `jq ... 2>/dev/null || echo "0"`,
but jq can succeed with empty output (empty string), leaving variables empty
and breaking subsequent `[ "$FAILED" -gt 0 ]` comparisons.

Note: The `CHECK_OUTPUT` empty/`[]` check at line 213 provides a first defense, and
`set -euo pipefail` is NOT enabled in ci_poller.sh, making the fallback pattern important.

**Fix:** Add explicit empty-string guards after each jq invocation:
```bash
FAILED=$(echo "$CHECK_OUTPUT" | jq '...' 2>/dev/null || echo "0")
FAILED=${FAILED:-0}
```

Steps:
1. Add `${VAR:-default}` guards for FAILED, NOT_COMPLETE, SUCCEEDED, TOTAL, FAILED_NAMES
2. Guard REPO in `set_review_status.sh` with `${REPO:?...}` (fail-fast, no sensible default)

**Validation:** Manual — shell scripts not covered by pytest.

### F4: Add dedup guard to follow-up issue creation

**Problem:** `_create_follow_up_issues()` in `review_driver.py` doesn't check
for existing issues before creating. If the review loop retries, duplicates result.

**Fix:** Before creating, search for existing issue with same label + PR number
in title. Use label filtering to narrow search and reduce false-positive risk.

```python
# Check for existing issue
result = subprocess.run(
    ["gh", "issue", "list", "--label", f"{label},follow-up",
     "--search", f"follow-up for PR #{pr_number} in:title",
     "--state", "all", "--limit", "1", "--json", "url"],
    capture_output=True, text=True,
)
existing = json.loads(result.stdout or "[]")
if existing:
    logger.info("Skipping duplicate issue for %s on PR #%d: %s", label, pr_number, existing[0]["url"])
    continue
```

Steps:
1. Add dedup check before `gh issue create` in the label loop
2. Log skip when duplicate found
3. Add test mocking `subprocess.run` to verify dedup behavior

**Validation:** `uv run python -m pytest tests/unit/test_review_driver.py`

### F5: Tighten type hint in _emit_retry_event

**Problem:** `dict[str, object]` at line 549 of `scripts/internal/ops.py` is overly
broad. The actual values are str, int, or None.

**Fix:** Change to `dict[str, str | int]` (no values are actually `None` in the current code).

**Validation:** `make lint`

## Execution Order

F5 (trivial) → F3 (shell, independent) → F1 (shared constant) → F4 (dedup) → F2 (dedup)

All fixes are independent — can be parallelized.

## Outcome

<!-- Filled after implementation -->

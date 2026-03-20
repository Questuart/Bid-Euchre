# Issue Triage Swarm — 2026-03-20

## Goal

Close 7 open issues across 4 parallel PRs, each authored by an independent
agent in its own worktree. Every agent plans, gets reviewed, then executes
autonomously through PR creation.

## Batches

### Batch A — Workflow jq guards (#1039)

**Branch:** `fix/jq-empty-output-guards`
**Lane:** author-b
**Issues closed:** #1039
**Risk:** LOW (2-line shell fix, no Python)

**File:** `.github/workflows/claude-code-review.yml` lines 56-57

**Fix:**
After the jq extraction of `SUBTYPE` and `DENIALS`, add:
```bash
SUBTYPE=${SUBTYPE:-unknown}
DENIALS=${DENIALS:-0}
```
Also add handling for missing `$EXECUTION_FILE`:
```bash
if [ ! -f "$EXECUTION_FILE" ]; then
  SUBTYPE="missing_execution_file"
fi
```

**Validation:** Syntax check (bash -n not applicable for YAML, but visual inspection). `make check` is not required since no Python changes.

---

### Batch B — Scheduler dedup fixes (#1042 + #1045)

**Branch:** `fix/scheduler-dedup-gaps`
**Lane:** author-c
**Issues closed:** #1042, #1045
**Risk:** LOW (small changes, existing test coverage)

**Files:**
- `src/bid_euchre/ops/scheduler.py` (lines 155-165)
- `tests/unit/test_ops_scheduler.py` (add tests)

**Fix 1 — Dead else branch (#1042):**
Remove the `else` branch (lines 159-161) since `read_events()` always returns
`list[dict[str, Any]]`. Replace with dict access directly + a type assertion:
```python
for evt in events:
    etype = evt.get("event_type", "")
    payload = evt.get("payload", {})
    if etype in ("retry_attempted", "task_rerouted", "escalation"):
        tid = payload.get("task_id") if isinstance(payload, dict) else None
        if tid:
            already_retried.add(tid)
```

**Fix 2 — Escalation in dedup set (#1045):**
Add `"escalation"` to the dedup set on line 162:
```python
if etype in ("retry_attempted", "task_rerouted", "escalation"):
```

**Tests:**
- Add `test_dedup_skips_already_escalated_tasks` — pre-populate event log with
  an `escalation` event and verify the task is skipped
- Add `test_dedup_dict_only_no_else_branch` — verify dict-only event processing

**Validation:** `uv run python -m pytest tests/unit/test_ops_scheduler.py -v`

---

### Batch C — Review driver dedup hardening (#1043)

**Branch:** `fix/review-driver-dedup-hardening`
**Lane:** author-d
**Issues closed:** #1043
**Risk:** LOW (exception narrowing, logging level change)

**Files:**
- `scripts/internal/review_driver.py` (lines 177-190)
- `tests/unit/test_review_driver.py` (add tests)

**Fix 1 — Narrow exception catch:**
```python
# Before:
except (json.JSONDecodeError, Exception) as e:
    logger.debug("Dedup check failed, proceeding with creation: %s", e)

# After:
except (json.JSONDecodeError, subprocess.CalledProcessError) as e:
    logger.warning("Dedup check failed, proceeding with creation: %s", e)
```

**Fix 2 — Promote logging level:** `logger.debug` → `logger.warning`

**Tests:**
- Add test verifying that dedup exception is narrowed (mock gh to raise
  CalledProcessError, verify it's caught; mock to raise ValueError, verify
  it propagates)

**Validation:** `uv run python -m pytest tests/unit/test_review_driver.py -v`

---

### Batch D — CI classifier unification (#1036 + #1041)

**Branch:** `fix/unify-ci-classifiers`
**Lane:** author-a (this lane, after coordination)
**Issues closed:** #1036, #1041
**Risk:** MEDIUM (changes CI polling logic used by review loop)

**Files:**
- `scripts/internal/github_pr_state.py` (lines 146-192)
- `src/bid_euchre/ops/__init__.py` (line 67 — CI_CHECK_NAMES)
- `tests/unit/test_github_pr_state.py`
- `tests/unit/test_check_classifier.py`

**Fix:**
Replace the fail-closed `CI_CHECK_NAMES` allowlist in `github_pr_state.py`
with `classify_check()` from `bid_euchre.ops`:

```python
# Before (fail-closed allowlist):
from bid_euchre.ops import CI_CHECK_NAMES as _CI_CHECK_NAMES
ci_checks = [c for c in checks if c.get("name") in _CI_CHECK_NAMES]

# After (fail-open denylist, single source of truth):
from bid_euchre.ops import classify_check
ci_checks = [c for c in checks if classify_check(c.get("name", "")) == "ci"]
```

Keep `CI_CHECK_NAMES` in `__init__.py` but add a deprecation comment.
Update the fallback in `github_pr_state.py` to use inline classify_check.

**Tests:**
- Update `test_check_classifier.py` consistency test
- Add `test_github_pr_state.py` test verifying classify_check integration
- Add drift-detection test asserting CI_CHECK_NAMES ⊂ classify_check("ci")

**Validation:** `uv run python -m pytest tests/unit/test_check_classifier.py tests/unit/test_github_pr_state.py -v`

---

## Execution Model

```
Master (author-a)
  ├── spawn Batch A agent (author-b worktree) ──→ plan → review → execute → PR
  ├── spawn Batch B agent (author-c worktree) ──→ plan → review → execute → PR
  ├── spawn Batch C agent (author-d worktree) ──→ plan → review → execute → PR
  └── Batch D: execute locally after A/B/C launch
```

Each agent:
1. Writes a concrete execution plan
2. Spawns an independent reviewer agent for that plan
3. Creates a TUI task list for implementation + validation
4. Implements the fix
5. Runs targeted tests (Tier 1)
6. Runs `make check-quiet` (Tier 2) — except Batch A (no Python)
7. Commits and opens PR with exact repro commands
8. Closes referenced issues

## Outcome

<!-- Filled after implementation -->

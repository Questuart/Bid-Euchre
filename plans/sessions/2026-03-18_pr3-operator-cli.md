# PR-3: Operator CLI — Implementation Plan

**Date:** 2026-03-18
**Author lane:** author-c
**Governing plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` § PR-3
**Depends on:** PR-1 (#835, #839, #841 — merged), PR-2 (#858, #866 — #866 pending merge)

## Goal

Implement a repo-owned operator layer so `ops` becomes the scheduler/monitoring
brain: status inspection, worktree lifecycle, durable events, scheduler tick,
review/CI aggregation, watchdog detection, and bounded recovery guidance.

## Design Constraints

1. **Online-first review:** PR review outcomes come from GitHub. Local
   `review_loops/**` and `plan_reviews/**` are transitional — do not build new
   dependencies on them.
2. **Persistent lanes own durable work.** Sub-agents are bounded helpers.
3. **Important work checkpointed to repo-local state.** No reliance on chat
   history or session-only cron.
4. **`ops` monitors adherence, progress, drift, and repeated sub-agent failure.**
5. **All cleanup flows through repo-owned lifecycle tooling**, not raw
   `git worktree remove/prune`.
6. **`lane_id` is canonical machine identity.** tmux/cmux fields are
   transport/presentation metadata only.
7. **`src/bid_euchre/ops/` is internal tooling.** Not re-exported to the public
   engine API surface.
8. **Loose coupling to Arc D.** Parse state files directly; do not import
   orchestration or schema internals just for status queries.

## Existing Code to Reuse (Not Duplicate)

| Existing | What to reuse | How |
|----------|--------------|-----|
| `scripts/internal/github_pr_state.py` | `get_ci_status()`, `get_pr_metadata()`, `PRMetadata` | Import directly in `ops/reviews.py` and `ops/ci.py` |
| `scripts/internal/review_state.py` | `ReviewLoopState`, `load_state()` | Import for transitional review status display only |
| `scripts/internal/rung_state.py` | Backward-compat re-export | Ignore; read rung state files directly |
| `scripts/internal/clean_worktrees.sh` | Reference for `[gone]` branch detection logic | Port pattern to `ops/worktrees.py`, keep shell script as-is |
| `scripts/internal/deterministic_prechecks.py` | `run_all_checks()` | Reference for CI workflow; do not import into ops |

## Schema Contracts (from PR-1)

All runtime state schemas are defined in:
- `.claude/runtime/worktree_registry/README.md` — v2 schema
- `.claude/runtime/session_metadata/README.md` — v2 schema
- `.claude/runtime/task_state/README.md` — v2 schema

New directories introduced by this PR:
- `.claude/runtime/events/` — JSONL event log + README
- `.claude/runtime/scheduler/` — scheduler tick state + README

## Phase 3A: Core Operator Surfaces

### Files Created

| File | Purpose |
|------|---------|
| `src/bid_euchre/ops/__init__.py` | Package root (minimal exports) |
| `src/bid_euchre/ops/status.py` | Status aggregation across lanes, sessions, tasks |
| `src/bid_euchre/ops/worktrees.py` | Worktree registry reading, classification, health |
| `src/bid_euchre/ops/events.py` | Durable event append/drain/query |
| `src/bid_euchre/ops/scheduler.py` | Tick loop, due-check, scheduler state persistence |
| `src/bid_euchre/ops/watchdogs.py` | Watchdog rules: stale heartbeats, stuck tasks, drift |
| `scripts/internal/ops.py` | CLI entrypoint (argparse subcommands) |
| `.claude/runtime/events/README.md` | Event log schema |
| `.claude/runtime/scheduler/README.md` | Scheduler state schema |
| `tests/unit/test_ops_status.py` | Status aggregation tests |
| `tests/unit/test_ops_worktrees.py` | Worktree parsing/classification tests |
| `tests/unit/test_ops_events.py` | Event append/drain tests |
| `tests/unit/test_ops_scheduler.py` | Scheduler tick/due-check tests |
| `tests/unit/test_ops_watchdogs.py` | Watchdog rule tests |

### CLI Commands (Phase 3A)

```
ops.py status          # Lane/session/task health summary
ops.py worktrees       # Worktree registry + git worktree list reconciliation
ops.py events          # Recent events (tail of event log)
ops.py events drain    # Mark events as processed
ops.py tick            # Run one scheduler cycle
ops.py health          # Aggregated health check
ops.py watchdogs       # Watchdog status report
```

All commands support `--json` for machine-readable output.

### Module Design

#### `ops/status.py`

```python
# Key functions (signatures grounded in actual schemas):
def load_lane_registry(runtime_dir: Path) -> list[dict]
    # Reads .claude/runtime/worktree_registry/*.json
    # Returns list of v2 worktree registry entries
    # Handles v1→v2 field inference per README

def load_sessions(runtime_dir: Path) -> list[dict]
    # Reads .claude/runtime/session_metadata/*.json
    # Returns list of v2 session entries

def load_tasks(runtime_dir: Path) -> list[dict]
    # Reads .claude/runtime/task_state/*.json
    # Returns list of v2 task entries

def aggregate_status(runtime_dir: Path) -> StatusReport
    # Combines lanes, sessions, tasks into unified summary
    # Identifies: active lanes, blocked tasks, stale sessions

@dataclass
class StatusReport:
    lanes: list[LaneStatus]
    active_sessions: list[dict]
    active_tasks: list[dict]
    blocked_tasks: list[dict]
    warnings: list[str]
```

#### `ops/worktrees.py`

```python
def list_worktrees_git() -> list[GitWorktree]
    # Parses `git worktree list --porcelain`
    # Returns structured list

def list_worktrees_registry(runtime_dir: Path) -> list[dict]
    # Reads worktree_registry/*.json

def reconcile(git_worktrees, registry_entries) -> ReconciliationReport
    # Cross-references git worktrees with registry
    # Identifies: unregistered, missing, stale, orphaned

def classify_cleanup_candidates(reconciled) -> list[CleanupCandidate]
    # Applies lifecycle policy:
    # - persistent: never auto-prune
    # - ephemeral + stale TTL + clean: ready_to_remove
    # - ephemeral + dirty: quarantine candidate
    # - unregistered: unknown (needs manual review)

@dataclass
class GitWorktree:
    path: str
    branch: str
    head: str
    bare: bool

@dataclass
class CleanupCandidate:
    path: str
    branch: str
    lifecycle_class: str   # persistent | ephemeral
    cleanup_state: str     # active | idle | stale | quarantined | ready_to_remove
    reason: str
    is_dirty: bool
    is_protected: bool     # matches steward worktree protection list
```

#### `ops/events.py`

```python
# Event log: .claude/runtime/events/events.jsonl (append-only)
# Each line is a JSON object with:
#   timestamp, event_type, source, lane_id, payload

VALID_EVENT_TYPES = {
    "task_completed", "task_failed", "task_blocked",
    "ci_failure", "ci_success",
    "heartbeat_stale", "heartbeat_ok",
    "review_outcome", "plan_review_outcome",
    "worktree_created", "worktree_removed",
    "escalation", "recovery_action",
    "session_started", "session_ended",
}

def append_event(event_type: str, source: str, lane_id: str,
                 payload: dict, events_dir: Path) -> None
    # Appends one JSON line to events.jsonl

def read_events(events_dir: Path, *, since: datetime | None,
                event_type: str | None, limit: int = 50) -> list[dict]
    # Reads and filters events from the log

def drain_events(events_dir: Path, *, up_to: datetime) -> int
    # Archives processed events to events.archive.jsonl
    # Returns count of drained events
```

#### `ops/scheduler.py`

```python
# Scheduler state: .claude/runtime/scheduler/state.json
# Fields: last_tick, last_health_pass, due_checks, tick_count

@dataclass
class SchedulerState:
    last_tick: str | None          # ISO 8601
    last_health_pass: str | None   # ISO 8601
    tick_count: int
    due_checks: list[str]          # check names due to run
    last_error: str | None

def load_scheduler_state(scheduler_dir: Path) -> SchedulerState
def save_scheduler_state(state: SchedulerState, scheduler_dir: Path) -> None

def tick(runtime_dir: Path) -> TickResult
    # Runs one scheduler cycle:
    # 1. Load scheduler state
    # 2. Run due health checks (watchdogs, event drain, session liveness)
    # 3. Emit events for findings
    # 4. Update scheduler state
    # 5. Return summary

@dataclass
class TickResult:
    checks_run: list[str]
    findings: list[str]
    events_emitted: int
    next_due: str | None  # ISO 8601
```

#### `ops/watchdogs.py`

```python
@dataclass
class WatchdogFinding:
    watchdog_name: str
    severity: str          # "critical", "warning", "info"
    target: str            # what was checked (lane, process, worktree)
    message: str
    threshold: str         # what threshold fired
    recommended_action: str

def check_heartbeats(runtime_dir: Path, *,
                     staleness_minutes: int = 5) -> list[WatchdogFinding]
    # Checks plans/**/heartbeat files for staleness

def check_task_progress(runtime_dir: Path, *,
                        staleness_minutes: int = 30) -> list[WatchdogFinding]
    # Checks task_state/*.json progress.last_forward_progress_at

def check_worktree_health(runtime_dir: Path) -> list[WatchdogFinding]
    # Checks for stale/orphaned/unregistered worktrees

def run_all_watchdogs(runtime_dir: Path) -> list[WatchdogFinding]
    # Runs all watchdog checks and returns combined findings
```

### Event Log Schema (`.claude/runtime/events/README.md`)

```json
{
  "timestamp": "2026-03-18T10:00:00Z",
  "event_type": "ci_failure",
  "source": "ops.tick",
  "lane_id": "author-a",
  "payload": {
    "pr_number": 866,
    "failure_class": "lint",
    "details": "ruff check found 2 issues"
  }
}
```

### Scheduler State Schema (`.claude/runtime/scheduler/README.md`)

```json
{
  "last_tick": "2026-03-18T10:00:00Z",
  "last_health_pass": "2026-03-18T09:55:00Z",
  "tick_count": 42,
  "due_checks": ["heartbeats", "task_progress", "worktree_health"],
  "last_error": null
}
```

### Implementation Order (Phase 3A)

1. Create `src/bid_euchre/ops/__init__.py` (empty package)
2. Implement `ops/events.py` + `test_ops_events.py` — foundational; other
   modules emit events
3. Implement `ops/worktrees.py` + `test_ops_worktrees.py` — parse registry,
   reconcile with `git worktree list`, classify
4. Implement `ops/status.py` + `test_ops_status.py` — aggregate lanes,
   sessions, tasks
5. Implement `ops/watchdogs.py` + `test_ops_watchdogs.py` — heartbeat,
   progress, worktree health checks
6. Implement `ops/scheduler.py` + `test_ops_scheduler.py` — tick loop,
   state persistence
7. Implement `scripts/internal/ops.py` — CLI wiring (argparse subcommands)
8. Write `.claude/runtime/events/README.md` and
   `.claude/runtime/scheduler/README.md`
9. Run targeted tests: `uv run python -m pytest tests/unit/test_ops_*.py`
10. Run `make check-quiet`

## Phase 3B: Safe Cleanup + Hooks

### Files Created/Modified

| File | Purpose |
|------|---------|
| `src/bid_euchre/ops/recovery.py` | Failure classification + recovery templates |
| `.claude/hooks/post-task-event.sh` | Hook: append durable events on task completion |
| `.claude/hooks/pre-worktree-cleanup.sh` | Hook: intercept `rm -rf` on worktree dirs |
| `tests/unit/test_ops_recovery.py` | Recovery template tests |

### New CLI Commands

```
ops.py worktrees prune       # Remove clean stale ephemeral worktrees (dry-run default)
ops.py worktrees quarantine   # Mark dirty stale worktrees for manual review
ops.py worktrees archive      # Archive metadata, remove directory
ops.py recover                # Show recovery guidance for current failures
```

### Prune Policy

```python
def prune_worktrees(runtime_dir: Path, *, dry_run: bool = True,
                    force: bool = False) -> list[PruneResult]
    # 1. Reconcile git worktrees with registry
    # 2. For each candidate:
    #    - Skip if protected (steward worktrees)
    #    - Skip if persistent class
    #    - Skip if dirty (unless force → quarantine first)
    #    - Skip if active session
    #    - Remove if: ephemeral + stale TTL + clean + no active session
    # 3. Update registry entries
    # 4. Emit events for each action
    # Always dry-run by default; require --execute for real removal

def quarantine_worktree(worktree_path: str, reason: str,
                        runtime_dir: Path) -> None
    # 1. Save diff to .claude/runtime/worktree_quarantine/<slug>.diff
    # 2. Update registry entry: cleanup_state = "quarantined"
    # 3. Emit quarantine event

def archive_worktree(worktree_path: str, runtime_dir: Path) -> None
    # 1. Verify clean or quarantined
    # 2. Save metadata snapshot
    # 3. git worktree remove
    # 4. Update registry entry: cleanup_state = "archived"
    # 5. Emit archive event
```

### Hook Design

**`post-task-event.sh`**: PostToolUse hook triggered after specific tool
completions. Appends structured events to the event log.

**`pre-worktree-cleanup.sh`**: PreToolUse hook that intercepts `Bash` commands
matching `rm -rf ../Bid-Euchre*` or `git worktree remove`. Returns a
"block + suggest" response redirecting to `ops.py worktrees prune`.

### Implementation Order (Phase 3B)

1. Implement `ops/recovery.py` + `test_ops_recovery.py`
2. Add `prune_worktrees()`, `quarantine_worktree()`, `archive_worktree()` to
   `ops/worktrees.py`
3. Add `test_ops_worktrees.py` tests for prune/quarantine/archive
4. Wire new subcommands to `scripts/internal/ops.py`
5. Create `.claude/hooks/post-task-event.sh`
6. Create `.claude/hooks/pre-worktree-cleanup.sh`
7. Run targeted tests
8. Test hooks manually (dry-run, verify interception)

## Phase 3C: Review/CI Migration Surfaces

### Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/bid_euchre/ops/reviews.py` | Create | Provider-neutral review outcome aggregation |
| `src/bid_euchre/ops/ci.py` | Create | CI status polling, failure classification |
| `.github/workflows/deterministic-prechecks.yml` | Create | GitHub-hosted deterministic prechecks |
| `tests/unit/test_ops_reviews.py` | Create | Review aggregation tests |
| `tests/unit/test_ops_ci.py` | Create | CI classification tests |
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | Update | Mark local loop transitional |
| `docs/02_agent/CODEX_GITHUB_REVIEW.md` | Update | Document online review path |

### Module Design

#### `ops/reviews.py`

```python
# Imports from existing code:
from scripts.internal.github_pr_state import get_pr_metadata, get_ci_status

@dataclass
class ReviewOutcome:
    pr_number: int
    title: str
    ci_status: str       # "success", "failure", "pending", "unknown"
    review_status: str   # from reviewing-changes commit status
    has_precheck_ci: bool
    url: str

def get_open_pr_reviews() -> list[ReviewOutcome]
    # Lists open PRs via `gh pr list --json`
    # For each: gets CI status, reviewing-changes status
    # Returns provider-neutral summary

def get_pr_review_detail(pr_number: int) -> ReviewOutcome
    # Detailed review status for a single PR
```

#### `ops/ci.py`

```python
CI_FAILURE_CLASSES = {
    "lint_format": {"auto_remediable": True, "max_retries": 3},
    "deterministic_test": {"auto_remediable": True, "max_retries": 3},
    "missing_config": {"auto_remediable": True, "max_retries": 2},
    "flaky_external": {"auto_remediable": False, "max_retries": 1},
    "infra_auth": {"auto_remediable": False, "max_retries": 0},
    "risky_destructive": {"auto_remediable": False, "max_retries": 0},
}

@dataclass
class CIFailureClassification:
    pr_number: int
    failure_class: str
    auto_remediable: bool
    details: str
    remediation_hint: str
    retry_count: int
    max_retries: int

def classify_ci_failure(pr_number: int, check_output: str) -> CIFailureClassification
    # Parses CI failure output
    # Classifies into failure categories
    # Returns classification with remediation hint

def poll_ci_status(pr_number: int) -> dict
    # Wraps github_pr_state.get_ci_status with additional metadata
    # Returns structured status with per-check breakdown
```

### Implementation Order (Phase 3C)

1. Implement `ops/reviews.py` + `test_ops_reviews.py` — mock `gh` calls in tests
2. Implement `ops/ci.py` + `test_ops_ci.py` — classification logic is pure
   Python, testable without GitHub
3. Wire `ops.py reviews` and `ops.py ci` subcommands
4. Create `.github/workflows/deterministic-prechecks.yml`
5. Update `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` with transitional markers
6. Update `docs/02_agent/CODEX_GITHUB_REVIEW.md`
7. Run targeted tests

## Phase 3D: Watchdogs + Retry/Reroute Policy

### Extensions to Existing Modules

| Module | Addition |
|--------|---------|
| `ops/watchdogs.py` | `check_ci_stuck()`, `check_subagent_failures()`, `check_scope_drift()` |
| `ops/scheduler.py` | `daemon()` mode — repeating tick with configurable interval |
| `ops/recovery.py` | Retry/reroute policy engine |
| `test_ops_watchdogs.py` | Additional watchdog tests |

### Watchdog Extensions

```python
def check_ci_stuck(runtime_dir: Path, *,
                   stuck_minutes: int = 30) -> list[WatchdogFinding]
    # Checks for PRs with CI pending/failing beyond threshold

def check_subagent_failures(runtime_dir: Path, *,
                            max_failures: int = 3) -> list[WatchdogFinding]
    # Checks event log for repeated task_failed events from same lane/task
    # Recommends reroute to persistent lane after threshold

def check_scope_drift(runtime_dir: Path) -> list[WatchdogFinding]
    # Compares task_state in_scope with actual file changes
    # Flags when changed files don't match declared scope
```

### Retry/Reroute Policy

```python
@dataclass
class RetryPolicy:
    task_id: str
    retry_count: int
    max_retries: int
    last_failure: str
    action: str  # "retry", "reroute", "escalate"
    reroute_to: str | None  # lane_id for reroute

def evaluate_retry_policy(task_id: str, events: list[dict]) -> RetryPolicy
    # Counts failures for this task
    # Returns: retry if under cap, reroute if repeated, escalate if exhausted
```

### Implementation Order (Phase 3D)

1. Add watchdog extensions to `ops/watchdogs.py`
2. Add retry/reroute policy to `ops/recovery.py`
3. Add `daemon()` mode to `ops/scheduler.py`
4. Add tests for all new functionality
5. Wire `ops.py daemon` subcommand

## Overall Implementation Sequence

| Step | Phase | What | Est. Files |
|------|-------|------|-----------|
| 1 | 3A | `ops/__init__.py` + `ops/events.py` + tests | 3 |
| 2 | 3A | `ops/worktrees.py` + tests | 2 |
| 3 | 3A | `ops/status.py` + tests | 2 |
| 4 | 3A | `ops/watchdogs.py` + tests | 2 |
| 5 | 3A | `ops/scheduler.py` + tests + schema READMEs | 4 |
| 6 | 3A | `scripts/internal/ops.py` CLI | 1 |
| 7 | 3A | Targeted test run + lint | 0 |
| 8 | 3B | `ops/recovery.py` + tests | 2 |
| 9 | 3B | Prune/quarantine/archive in worktrees + tests | 1 |
| 10 | 3B | Hooks: post-task-event, pre-worktree-cleanup | 2 |
| 11 | 3C | `ops/reviews.py` + `ops/ci.py` + tests | 4 |
| 12 | 3C | GitHub workflow + doc updates | 3+ |
| 13 | 3D | Watchdog extensions + retry policy + daemon | 2 |
| 14 | All | `make check-quiet`, final validation | 0 |

**Total new files:** ~26 (12 source, 8 test, 3 schema/hook, 3 docs/workflow)

## Commit Strategy

One commit per logical slice. Suggested commit sequence:

1. `feat: add ops package skeleton with events module`
2. `feat: add worktree registry parsing and reconciliation`
3. `feat: add status aggregation across lanes/sessions/tasks`
4. `feat: add watchdog rules for heartbeat and progress checks`
5. `feat: add scheduler tick loop and state persistence`
6. `feat: add ops.py CLI entrypoint with core subcommands`
7. `feat: add prune/quarantine/archive cleanup policy`
8. `feat: add recovery templates and failure classification`
9. `feat: add hooks for task events and worktree protection`
10. `feat: add review/CI aggregation and failure classification`
11. `feat: add GitHub deterministic-prechecks workflow`
12. `feat: add watchdog extensions and retry/reroute policy`
13. `docs: update review architecture docs for online-first migration`

## Validation Plan

Operational validation for this PR must follow the governing plan's
infrastructure gate:

- Include a `Validation Performed` section in the PR body before merge.
- Record automated tests run, dry-run checks, manual steward-environment smoke
  checks, at least one failure-injection check, rollback/disable path, and
  known gaps.
- Prefer observe-only/report-only rollout before enabling mutation or
  enforcement for new automation surfaces.

### During Implementation (Tier 1)
```bash
uv run python -m pytest tests/unit/test_ops_events.py -v
uv run python -m pytest tests/unit/test_ops_worktrees.py -v
uv run python -m pytest tests/unit/test_ops_status.py -v
# etc. for each module
```

### Before PR (Tier 2)
```bash
git fetch origin main && git rebase origin/main
make check-quiet
```

- Prepare the PR-body `Validation Performed` section with:
  - exact test commands run
  - dry-run commands and observed results
  - manual smoke checks completed
  - at least one unhappy-path or failure-injection exercise
  - rollback/disable instructions
  - known gaps

### Failure Injection
- Create at least one intentionally bad or stale runtime state and verify the
  new operator surface classifies it correctly instead of only proving the
  happy path.
- For destructive or enforcement-adjacent features, prove detect/report mode
  before enabling mutation.

### Manual Verification
- `uv run python scripts/internal/ops.py status` from main checkout
- `uv run python scripts/internal/ops.py worktrees` reconciliation output
- `uv run python scripts/internal/ops.py worktrees prune --dry-run` output
- Hook interception verification (manual `rm -rf` test)

### Post-Merge Soak
- Treat the PR as landed but not yet trusted until it has survived a short soak
  period in normal steward use.
- Do not remove older manual fallback paths immediately after merge.

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Large PR (26 files) | Phased commits with validation at each phase boundary |
| `gh` CLI dependency in tests | Mock all subprocess calls; tests are pure Python |
| Hook registration complexity | Use existing `.claude/settings.json` patterns from PR-2 |
| Schema drift from PR-1 | Ground all parsing in committed README schemas |
| Import boundary violation | `src/bid_euchre/ops/` imports only from stdlib + `scripts/internal/` utilities |

## Out of Scope (Deferred to PR-4/PR-5)

- Curated memory system
- Audit index (SQLite/FTS)
- Session compaction/archive
- Context safety scanning
- Skill promotion workflow
- Shadow snapshots
- Permission migration (removing deny rules) — deferred until hooks are
  validated in production

## Outcome

_To be filled after implementation._

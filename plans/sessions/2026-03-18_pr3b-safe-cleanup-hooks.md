# PR-3B: Safe Cleanup + Hooks — Implementation Plan

**Date:** 2026-03-18
**Author lane:** author-c (`codex/steward-author-c`)
**Parent plan:** `plans/sessions/2026-03-18_pr3-operator-cli.md` § Phase 3B
**Depends on:** Phase 3A (merged: #878, #884, #888)

## Goal

Add safe worktree lifecycle operations (prune, quarantine, archive) and
failure recovery guidance to the ops package. Wire hooks that emit durable
events on task completion and intercept dangerous worktree removal commands.

## Scope

### In Scope

| # | Deliverable | Files |
|---|------------|-------|
| 1 | Recovery module — failure classification + templates | `src/bid_euchre/ops/recovery.py` |
| 2 | Recovery tests | `tests/unit/test_ops_recovery.py` |
| 3 | Prune/quarantine/archive functions | `src/bid_euchre/ops/worktrees.py` (extend) |
| 4 | Prune/quarantine/archive tests | `tests/unit/test_ops_worktrees.py` (extend) |
| 5 | CLI wiring for new subcommands | `scripts/internal/ops.py` (extend) |
| 6 | CLI tests for new subcommands | `tests/unit/test_ops_cli.py` (extend) |
| 7 | Post-task event hook | `.claude/hooks/post-task-event.sh` |
| 8 | Pre-worktree-cleanup hook | `.claude/hooks/pre-worktree-cleanup.sh` |
| 9 | Hook registration in settings | `.claude/settings.json` (extend) |

### Out of Scope

- Review/CI migration surfaces (Phase 3C)
- Watchdog extensions and retry/reroute policy (Phase 3D)
- Curated memory system (PR-4)

## Design

### 1. Recovery Module (`ops/recovery.py`)

Failure classification maps event types to severity + recovery templates.
Recovery templates are human-readable multi-step guidance, not auto-remediation.

```python
@dataclass
class RecoveryTemplate:
    name: str
    description: str
    steps: list[str]
    auto_remediable: bool

@dataclass
class FailureClassification:
    failure_type: str       # matches event_type or category
    severity: str           # "critical" | "warning" | "info"
    target: str             # what failed (lane_id, PR number, worktree path)
    details: str            # human-readable description
    template: RecoveryTemplate | None

RECOVERY_TEMPLATES: dict[str, RecoveryTemplate]  # keyed by failure_type

def classify_failure(event: dict) -> FailureClassification
def get_active_failures(events_dir: Path) -> list[FailureClassification]
    # Reads recent events, classifies those needing attention
def format_recovery_text(failures: list[FailureClassification]) -> str
def format_recovery_json(failures: list[FailureClassification]) -> list[dict]
```

**Recovery template catalog:**

| Failure Type | Template Name | Steps | Auto? |
|-------------|--------------|-------|-------|
| `ci_failure` | CI Failure | ruff fix → ruff format → commit → push | Yes |
| `task_failed` | Task Failure | check logs → retry or reroute → escalate | No |
| `task_blocked` | Task Blocked | check blocker → resolve or skip → update state | No |
| `heartbeat_stale` | Stale Heartbeat | check agent alive → respawn if dead → update state | No |
| `worktree_quarantined` | Quarantined Worktree | review diff → commit or discard → archive | No |
| `escalation` | Escalation | read details → human decision needed | No |

### 2. Worktree Lifecycle Operations (`ops/worktrees.py` extensions)

```python
@dataclass
class PruneResult:
    path: str
    branch: str
    action: str            # "removed" | "skipped" | "quarantined"
    reason: str
    dry_run: bool

def prune_worktrees(
    runtime_dir: Path,
    *, dry_run: bool = True,
    events_dir: Path | None = None,
) -> list[PruneResult]:
    # 1. list_worktrees_git() + list_worktrees_registry()
    # 2. classify_cleanup_candidates(check_dirty=True)
    # 3. For each candidate:
    #    - Skip if protected or persistent
    #    - Skip if active session
    #    - Quarantine if dirty + stale
    #    - Remove if stale + clean (only when dry_run=False)
    # 4. Emit events for each action
    # Returns list of PruneResult

def quarantine_worktree(
    worktree_path: str,
    reason: str,
    runtime_dir: Path,
    *, events_dir: Path | None = None,
) -> None:
    # 1. Save diff to .claude/runtime/worktree_quarantine/<slug>.diff
    # 2. Emit worktree_quarantined event

def archive_worktree(
    worktree_path: str,
    runtime_dir: Path,
    *, events_dir: Path | None = None,
    force: bool = False,
) -> None:
    # 0. SAFETY: Verify target is not cwd or a protected worktree
    # 1. Verify clean or already quarantined (unless force)
    # 2. Run `git worktree remove <path>`
    # 3. Emit worktree_archived event
    # HIGH RISK: `git worktree remove` is irreversible.
    # Guard: reject if path == cwd, reject if protected.
```

**Policy constraints:**
- `prune_worktrees()` defaults to `dry_run=True` — requires `--execute` CLI flag
- Protected worktrees (from `PROTECTED_WORKTREE_NAMES`) always skipped
- Persistent lifecycle class always skipped
- Dirty worktrees → quarantine (save diff first), never auto-remove
- Active session → skip entirely

### 3. CLI Wiring (`scripts/internal/ops.py`)

New subcommands under `worktrees`:
```
ops.py worktrees prune [--execute] [--json]     # Dry-run by default
ops.py worktrees quarantine <path> [--reason R]  # Manual quarantine
ops.py worktrees archive <path> [--force]        # Archive a worktree
ops.py recover [--json]                          # Show recovery guidance
```

### 4. Hooks

**`post-task-event.sh`** — PostToolUse hook on `Bash`:
- Matches tool output containing `gh pr merge`, `task completed`, etc.
- Resolves `lane_id` from the worktree directory name (e.g., `Bid-Euchre-steward-author-c` → `author-c`),
  falling back to `"unknown"` if the name doesn't match a known pattern
- Calls `uv run python -c "from bid_euchre.ops.events import append_event; ..."`
- Emits `task_completed` or relevant event type
- Timeout: 5s (must be fast)

**`pre-worktree-cleanup.sh`** — PreToolUse hook on `Bash`:
- Matches tool input containing `rm -rf ../Bid-Euchre` or `git worktree remove`
- Prints warning + suggests `uv run python scripts/internal/ops.py worktrees prune`
- Does NOT block (advisory only — blocking requires `exitCode` non-zero)
- Timeout: 5s

## Implementation Order

| Step | Task | Depends On | Files |
|------|------|-----------|-------|
| 1 | Implement `recovery.py` | — | `src/bid_euchre/ops/recovery.py` |
| 2 | Test `recovery.py` | Step 1 | `tests/unit/test_ops_recovery.py` |
| 3 | Add prune/quarantine/archive to `worktrees.py` | — | `src/bid_euchre/ops/worktrees.py` |
| 4 | Test prune/quarantine/archive | Step 3 | `tests/unit/test_ops_worktrees.py` |
| 5 | Wire CLI subcommands | Steps 1, 3 | `scripts/internal/ops.py` |
| 6 | Test CLI subcommands | Step 5 | `tests/unit/test_ops_cli.py` |
| 7 | Create hooks | — | `.claude/hooks/post-task-event.sh`, `.claude/hooks/pre-worktree-cleanup.sh` |
| 8 | Register hooks in settings.json | Step 7 | `.claude/settings.json` |

**Rollback (hooks):** If new hooks cause problems, revert the added entries in
`.claude/settings.json` and delete the hook scripts. No other state changes needed.
| 9 | Run all ops tests | Steps 2, 4, 6 | — |
| 10 | Run `make check-quiet` | Step 9 | — |

**Parallelism:** Steps 1-2 and 3-4 are independent and can run in parallel.
Steps 7-8 are independent of steps 1-6. Step 5 depends on both 1 and 3.

## Validation

### Tier 1 (during implementation)
```bash
uv run python -m pytest tests/unit/test_ops_recovery.py -v
uv run python -m pytest tests/unit/test_ops_worktrees.py -v
uv run python -m pytest tests/unit/test_ops_cli.py -v
```

### Tier 2 (before PR)
```bash
make check-quiet
```

## Commit Strategy

Single logical commit for Phase 3B:
```
feat: add safe cleanup, recovery templates, and ops hooks (Phase 3B)
```

## Outcome

_To be filled after implementation._

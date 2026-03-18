# PR-2: Persistent Session Manager and VS Code Audit Surface

**Date:** 2026-03-18
**Lane:** author-c (`codex/steward-author-c`)
**Parent plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md`
**Depends on:** PR-1 ✅ (merged as #835, #839, #841)

## Goal

Close the remaining PR-2 deliverables from the autonomous agent ops workflow plan.
PR-1 already delivered the steward tmux launcher, layout config, VS Code workspace
(legacy naming), and tasks.json. This PR updates the workspace to use steward lane
names, adds missing VS Code tasks, creates a macOS launchd recovery template, and
updates the workflow doc to cover host-level recovery.

## Delta Analysis

### Already Complete (from PR-1)

| Deliverable | File | Status |
|-------------|------|--------|
| Canonical steward launcher | `.claude/tmux/steward-session.sh` | ✅ Done |
| tmux layout config | `.claude/tmux/agent-ops-layout.conf` | ✅ Done |
| VS Code tasks (14 tasks) | `.vscode/tasks.json` | ✅ Partial |
| Workflow documentation | `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | ✅ Partial |
| VS Code workspace | `Bid-Euchre-agent-audit.code-workspace` | ✅ Outdated |

### Remaining Work

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | Update workspace to steward lane names + add all lanes | New |
| 2 | Add missing VS Code tasks (GH PR checks, prechecks, plan reviews) | New |
| 3 | Create `ensure-steward-session.plist` launchd template | New |
| 4 | Create `install-launchd.sh` helper script | New |
| 5 | Update AUTONOMOUS_OPERATOR_WORKFLOW.md with recovery section | New |

## Implementation Plan

### Step 1: Update VS Code Workspace

**File:** `Bid-Euchre-agent-audit.code-workspace`

Current workspace uses legacy 3-role names (`author`, `review`, `ops` at
`../Bid-Euchre-author`, etc.). Update to match the deployed steward lanes:

```json
{
  "folders": [
    {"name": "main", "path": "."},
    {"name": "author-a", "path": "../Bid-Euchre-steward-author"},
    {"name": "author-b", "path": "../Bid-Euchre-steward-author-b"},
    {"name": "author-c", "path": "../Bid-Euchre-steward-author-c"},
    {"name": "author-d", "path": "../Bid-Euchre-steward-author-d"},
    {"name": "review", "path": "../Bid-Euchre-steward-review"},
    {"name": "scratch", "path": "../Bid-Euchre-steward-author-scratch"}
  ]
}
```

Notes:
- `ops` is removed as a folder since it runs from main checkout (same as "main")
- `scratch` included for visibility into exploratory work
- All paths use the actual steward worktree naming convention
- Settings, extensions, and exclusions carry forward from current workspace

### Step 2: Add Missing VS Code Tasks

**File:** `.vscode/tasks.json`

Add tasks required by PR-2 acceptance criteria that are not yet present:

| Task | Command | Notes |
|------|---------|-------|
| **GitHub PR checks** | `gh pr checks` | Shows CI status for current branch |
| **GitHub PR checks (specific)** | `gh pr checks <N>` | Pick-string for PR number |
| **Deterministic prechecks** | `uv run python scripts/internal/deterministic_prechecks.py` | Local prechecks run |
| **Plan review artifacts** | List `.claude/runtime/plan_reviews/` contents | Inspection only |

Existing 14 tasks are retained unchanged.

### Step 3: Create launchd Recovery Template

**File:** `.claude/launchd/ensure-steward-session.plist`

A macOS `launchd` plist template that:
- Runs on user login (`RunAtLoad`)
- Watches for tmux session absence and re-creates it
- Calls `.claude/tmux/steward-session.sh` (which is idempotent)
- Includes `StandardOutPath` / `StandardErrorPath` for debugging
- Uses `KeepAlive` with `SuccessfulExit: false` so it relaunches only if the script exits non-zero (tmux died)

This is a **template** — it contains placeholder paths (`__REPO_PATH__`) that
must be customized per installation.

### Step 4: Create install-launchd.sh Helper

**File:** `.claude/launchd/install-launchd.sh`

A helper script that:
1. Substitutes `__REPO_PATH__` with the actual repo path
2. Copies the plist to `~/Library/LaunchAgents/`
3. Loads the agent with `launchctl load`
4. Provides uninstall instructions

### Step 5: Update Workflow Documentation

**File:** `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`

Add a new section "## Host-Level Recovery (macOS)" covering:
- What the launchd agent does
- How to install/uninstall it
- How to verify it works
- Troubleshooting tips
- Cross-reference to the template and installer

## Files Changed

| File | Action |
|------|--------|
| `Bid-Euchre-agent-audit.code-workspace` | Edit (update folders to steward lanes) |
| `.vscode/tasks.json` | Edit (add 4 new tasks) |
| `.claude/launchd/ensure-steward-session.plist` | Create |
| `.claude/launchd/install-launchd.sh` | Create |
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Edit (add recovery section) |

## Validation

- [ ] Workspace file is valid JSON and opens correctly in VS Code
- [ ] All new tasks appear in VS Code task list and execute without error
- [ ] launchd plist is valid XML (`plutil -lint`)
- [ ] install-launchd.sh runs without error in dry-run mode
- [ ] `make check-quiet` passes (docs-only + config files, should be fast)
- [ ] No `src/` or `tests/` changes (pure tooling/config/docs PR)

## Acceptance Criteria (from governing plan)

1. ✅ One repo-owned command starts the tmux session — already done
2. ⬜ On macOS, one repo-owned launchd template re-establishes the session
3. ⬜ One repo-owned workspace file opens the audit layout — needs update
4. ⬜ User can inspect all active role worktrees and runtime artifacts — needs tasks

## Out of Scope

- `ops.py` CLI (PR-3)
- Permission migration (PR-3)
- SQLite audit index (PR-4)
- Context safety scanning (PR-5)
- Any `src/` or `tests/` code changes

## Outcome

_To be filled after implementation._

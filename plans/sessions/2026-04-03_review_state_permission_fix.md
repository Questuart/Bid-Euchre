# Research: review_state Permission Stall — Move Out of .claude/ or Find Bypass

> **Issue:** [#2238](https://github.com/Questuart/Bid-Euchre/issues/2238)
> **Related:** [#2249](https://github.com/Questuart/Bid-Euchre/issues/2249) (auto-accept audit, analyst-a, COMPLETE)
> **Date:** 2026-04-03
> **Lane:** analyst-b
> **Task:** 4d10129902b0
> **Status:** COMPLETE

---

## Executive Summary

The review lane stalls because **Claude Code v2.1.78+ hard-protects all
`.claude/` directory writes** at the platform level. This protection
**overrides `permissions.allow` patterns** in settings.json — our existing
`Edit/Write(.claude/runtime/**)` rules are silently ignored by the runtime.

**Root cause:** Platform-level security constraint, not a configuration gap.

**Recommended fix:** **Option A — Relocate `.claude/runtime/` to `.ops_runtime/`**
at the repo root. This is the only reliable fix that works today without
depending on upstream changes or unsafe bypass flags.

---

## Part 1: Root Cause Confirmation

### 1.1 The Platform Protection

Claude Code v2.1.78 (late February 2026) introduced hardcoded "protected
directory" logic that prompts for confirmation on **any** write to:

- `.git/`
- `.claude/`
- `.vscode/`
- `.idea/`
- `.husky/`

This protection fires **regardless of**:
- `permissions.allow` patterns in settings.json
- `bypassPermissions` mode
- `--dangerously-skip-permissions` CLI flag
- `auto` mode classifier decisions

### 1.2 Documented Exceptions (Unreliable)

The official docs claim three `.claude/` subdirectories are exempt:
- `.claude/commands/`
- `.claude/agents/`
- `.claude/skills/`

However, multiple upstream issues report these exemptions are **not reliably
honored** in practice:
- [anthropics/claude-code#37157](https://github.com/anthropics/claude-code/issues/37157) — `.claude/skills/` not exempt despite docs
- [anthropics/claude-code#38806](https://github.com/anthropics/claude-code/issues/38806) — Feature request for opt-in override
- [anthropics/claude-code#37765](https://github.com/anthropics/claude-code/issues/37765) — `--dangerously-skip-permissions` doesn't bypass
- [anthropics/claude-code#36168](https://github.com/anthropics/claude-code/issues/36168) — Bypass broken in all versions > v2.1.77
- [anthropics/claude-code#29639](https://github.com/anthropics/claude-code/issues/29639) — Configured permissions not respected for `.claude/` paths

### 1.3 Why Our Allowlist Doesn't Work

Our current `permissions.allow` includes:
```json
"Edit(.claude/runtime/**)",
"Write(.claude/runtime/**)",
"Edit(.claude/runtime/review_state/**)",
"Write(.claude/runtime/review_state/**)"
```

These rules are **correctly formatted** but the platform's protected-directory
check runs **before** the allowlist is evaluated. The allowlist never gets a
chance to match.

### 1.4 What Triggers the Stall

The review lane writes to `.claude/runtime/` in multiple ways:

| Subsystem | Path | Writer | Trigger |
|-----------|------|--------|---------|
| Review loops | `.claude/runtime/review_loops/pr_N/state.json` | `review_driver.py` | PR review cycle |
| Review queue | `.claude/runtime/review_queue/pr_N/verdict.json` | `review_queue.py` | Verdict write |
| Review state | `.claude/runtime/review_state/last_merged_pr.txt` | `steward-review` agent | Post-merge sweep |
| Events | `.claude/runtime/events/*.jsonl` | `events.py` | Any ops event |
| Task queue | `.claude/runtime/task_queue/*.json` | `task_queue.py` | Task dispatch |

All of these trigger the protection prompt because they write under `.claude/`.

---

## Part 2: Fix Options Evaluated

### Option A: Relocate `.claude/runtime/` → `.ops_runtime/` ⭐ RECOMMENDED

**Approach:** Move all runtime state out of `.claude/` to a new directory
at the repo root (e.g., `.ops_runtime/`). This entirely avoids the platform
protection.

**Why `.ops_runtime/`:**
- Dot-prefixed (hidden) — doesn't clutter repo root
- Descriptive — clearly ops infrastructure, not user content
- No platform protection — writes are governed only by `permissions.allow`
- Already gitignored pattern possible (`.ops_runtime/*`)

**Implementation complexity:** Medium — the codebase is well-parameterized.

**Codebase pattern:** Almost every ops module uses the same parameter pattern:
```python
def some_function(runtime_dir: Path | None = None):
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
```

This means we need to:
1. Change the default constant in each module
2. Or (better) create a single canonical `RUNTIME_ROOT` constant and import it

**File impact analysis:**

| Category | Files | Pattern |
|----------|-------|---------|
| Python source (`src/bid_euchre/ops/`) | ~25 files | `Path(".claude/runtime")` default |
| Scripts (`scripts/internal/`) | ~6 files | Hardcoded paths |
| Shell hooks (`.claude/hooks/`) | ~8 files | Hardcoded paths in bash |
| Tests | ~8 files | Hardcoded paths or test overrides |
| Documentation/plans | ~60 files | References in docs (non-breaking) |

**Special case — `review_queue.py`:** Uses `shared_queue_root()` which
resolves to `<main_repo>/.claude/runtime/review_queue` via `git rev-parse
--git-common-dir`. This cross-worktree path must also be relocated.

**Migration strategy:**
1. Create `src/bid_euchre/ops/paths.py` with a single `RUNTIME_ROOT` constant
2. Update all `Path(".claude/runtime")` defaults to use `RUNTIME_ROOT`
3. Update `shared_queue_root()` in `review_queue.py`
4. Update shell hooks to use the new path
5. Update `.gitignore` (add `.ops_runtime/*`, keep `.claude/runtime/*` for transition)
6. Physically move existing data: `mv .claude/runtime/* .ops_runtime/`
7. Update documentation references (non-blocking, can be batched)

**Estimated PR count:** 2-3 PRs
- PR 1: Create `paths.py` constant, update Python source + tests
- PR 2: Update shell hooks + .gitignore + migration script
- PR 3 (optional): Documentation reference updates

**Risk:** Low. All tests already use `runtime_dir` parameter overrides via
`tmp_path` fixtures, so they won't break. The only risk is missing a hardcoded
path in a shell script.

**Validation:**
```bash
# After migration, verify no remaining .claude/runtime references in hot paths
grep -r '\.claude/runtime' src/ scripts/ .claude/hooks/ --include='*.py' --include='*.sh' | grep -v '# legacy'
# Run full test suite
make check
# Smoke test: review driver writes to new location
ls .ops_runtime/review_loops/
```

### Option B: `auto` Mode (Classifier-Based Bypass)

**Approach:** Use Claude Code's `auto` mode which uses an AI classifier to
evaluate each action and auto-approve routine operations.

**Requirements:**
- Team or Enterprise plan (not available on Pro/Max individual subscriptions)
- v2.1.38+

**Problems:**
1. **Plan requirement:** We may not have Team/Enterprise plan
2. **Headless abort:** In headless mode (`claude -p`), classifier denials
   abort the session — no fallback
3. **Non-deterministic:** The classifier may randomly deny `.claude/` writes
   that are routine for us
4. **Still prompts for `.claude/`:** The protected-directory check may still
   fire before the classifier evaluates — unclear from docs

**Verdict:** Not viable as primary fix. Could be a useful complement to
Option A for other edge cases.

### Option C: `--dangerously-skip-permissions`

**Approach:** Launch review lane with `--dangerously-skip-permissions`.

**Problems:**
1. **Broken for `.claude/`:** Issues #36168 and #37765 confirm this flag
   does NOT bypass the `.claude/` protected directory check in v2.1.78+
2. **Security risk:** Removes ALL permission gates, not just `.claude/`
3. **Not fleet-appropriate:** Our fleet documentation explicitly prohibits this

**Verdict:** Not viable. Confirmed broken for this specific use case.

### Option D: `defaultMode: "acceptEdits"` in settings.json

**Approach:** Set `"defaultMode": "acceptEdits"` to auto-approve file edits.

**How it works:** Auto-accepts all `Edit`/`Write` tool calls without prompting.
Does NOT auto-accept Bash commands or MCP tools.

**Problems:**
1. **May not override protected directory check:** The protected-directory
   logic likely fires before mode evaluation (same as `permissions.allow`)
2. **Untested for `.claude/` paths:** No upstream confirmation this works

**Verdict:** Worth testing as a quick experiment, but unlikely to work based
on the protection architecture. Recommended by #2249 audit for other stall
prevention — should be adopted regardless.

### Option E: Orchestrator tmux Auto-Approve

**Approach:** Detect permission prompts via tmux pane capture and auto-send
`2` (Always Allow) via `tmux send-keys`.

**Current state:** This is already documented in MEMORY.md as the manual
workaround:
```bash
tmux send-keys -t steward:<window>.<pane> '2'
```

**Problems:**
1. **Fragile:** Depends on prompt text detection, tmux timing
2. **Race conditions:** Multiple prompts can stack
3. **Not durable:** Must be reconfigured after session restart
4. **Treats symptoms:** Doesn't fix the root cause

**Verdict:** Keep as emergency manual workaround. Not a production fix.

### Option F: Wait for Upstream Fix

**Approach:** Wait for Anthropic to fix issues #38806/#36168.

**Problems:**
1. **Timeline unknown:** No ETA from Anthropic
2. **Review pipeline blocked now:** Every fleet run accumulates stalls
3. **May never be fixed:** Anthropic views the protection as a security feature

**Verdict:** Not viable as primary strategy. File upstream request, but
don't wait.

---

## Part 3: What Else Lives in `.claude/runtime/`

Everything in `.claude/runtime/` has the same problem — not just review_state.

| Directory | Purpose | Write Frequency |
|-----------|---------|-----------------|
| `events/` | JSONL event log | Every ops event (high) |
| `review_loops/` | Per-PR review state | Every PR review (medium) |
| `review_queue/` | Cross-worktree verdict store | Every PR (medium) |
| `scheduler/` | Watchdog schedule state | Every monitor cycle (high) |
| `session_metadata/` | Lane session tracking | Session start (low) |
| `task_queue/` | Task dispatch packets | Every dispatch (medium) |
| `task_state/` | Task execution state | Every task update (medium) |
| `worktree_registry/` | Lane registration | Session start (low) |

**All 8 subdirectories** are affected by the platform protection. Relocating
only `review_state/` would leave 7 other stall sources in place. This is
why Option A relocates the entire `runtime/` tree.

---

## Part 4: Implementation Plan (Option A)

### PR 1: Create canonical RUNTIME_ROOT and update Python source

**Scope:** `src/bid_euchre/ops/`, `scripts/internal/`, `tests/`

**Steps:**
1. Create `src/bid_euchre/ops/paths.py`:
   ```python
   """Canonical paths for ops runtime state."""
   from pathlib import Path
   import os

   # Environment override for testing / alternative deployments
   RUNTIME_ROOT = Path(
       os.environ.get("BID_EUCHRE_RUNTIME_DIR", ".ops_runtime")
   )
   ```
2. Update all `Path(".claude/runtime")` defaults in `src/bid_euchre/ops/*.py`
   to import and use `RUNTIME_ROOT`
3. Update `shared_queue_root()` in `review_queue.py` to use `.ops_runtime`
   instead of `.claude/runtime/review_queue`
4. Update test fixtures if any hardcode the old path
5. Run Tier 1 tests: `uv run python -m pytest tests/unit/test_review_queue.py tests/unit/test_review_driver.py tests/unit/test_ops_cli.py`

**Files touched:** ~30 Python files (but most are 1-line default changes)

### PR 2: Update shell hooks + gitignore + migration

**Scope:** `.claude/hooks/`, `.gitignore`, migration script

**Steps:**
1. Update all shell hooks that reference `.claude/runtime/`:
   - `post-pr-review-loop.sh` (LOGDIR)
   - `pre-merge-review-guard.sh` (QUEUE_ROOT fallback)
   - `ci_poller.sh` (poll state dir)
   - `alert-inject.sh` / `alert-inject.py` (fleet_status.json)
   - `post-tool-daemon-notify.sh` (daemon state)
   - `post-push-ci-check.sh` (CI poll state)
   - Others as found by grep
2. Update `.gitignore`:
   ```
   # New runtime location
   .ops_runtime/*
   !.ops_runtime/README.md
   # ... (mirror existing .claude/runtime/ exceptions)
   ```
3. Create `scripts/internal/migrate_runtime.sh`:
   ```bash
   #!/bin/bash
   # One-time migration: .claude/runtime/ → .ops_runtime/
   if [ -d ".claude/runtime" ] && [ ! -d ".ops_runtime" ]; then
     cp -r .claude/runtime .ops_runtime
     echo "Migrated .claude/runtime/ → .ops_runtime/"
     echo "Old data preserved at .claude/runtime/ (safe to remove later)"
   fi
   ```
4. Update `permissions.allow` in `.claude/settings.json`:
   - Remove `Edit/Write(.claude/runtime/**)` entries
   - Add `Edit/Write(.ops_runtime/**)` entries (optional — these paths
     won't trigger platform protection anyway)

**Files touched:** ~12 shell/config files

### PR 3 (Optional): Documentation updates

**Scope:** `docs/`, `plans/`, `.claude/agents/`, `.claude/skills/`, `.claude/rules/`

Non-blocking — references in docs are informational. Can be batched as a
follow-up or done incrementally.

**Files touched:** ~60 markdown files (cosmetic path references only)

---

## Part 5: Acceptance Criteria

1. **Review lane completes a full review cycle without permission prompts**
   - Review driver writes state to `.ops_runtime/review_loops/`
   - Verdict written to `.ops_runtime/review_queue/`
   - No "Do you want to make this edit?" prompts observed
2. **All tests pass:** `make check` green
3. **Cross-worktree queue works:** `shared_queue_root()` resolves to
   `<main_repo>/.ops_runtime/review_queue`
4. **No remaining hot-path references:** `grep -r '\.claude/runtime' src/ scripts/ .claude/hooks/` returns zero matches (excluding comments/docs)
5. **Migration script works:** Running on a fresh worktree with old data
   moves it to the new location

---

## Part 6: Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Missed hardcoded path in shell hook | Medium | Grep sweep + integration test |
| Cross-worktree queue resolution breaks | High | Test `shared_queue_root()` from multiple worktrees |
| Existing review loop state lost during migration | Low | Migration copies (not moves), old data preserved |
| `permissions.allow` patterns for `.ops_runtime/` not needed but nice-to-have | Low | Add patterns anyway for documentation value |
| Hooks reference `.claude/runtime/` before migration runs | Low | Migration script runs at session start or manually once |
| Environment variable `BID_EUCHRE_RUNTIME_DIR` conflicts with test fixtures | Low | Tests already use `tmp_path` via `runtime_dir` parameter |

---

## Part 7: Immediate Quick Win (While PRs Are In Flight)

Add `"defaultMode": "acceptEdits"` to `.claude/settings.json` as recommended
by the #2249 audit. This **may** not fix the `.claude/` protection issue, but
it will prevent other file-edit permission stalls. Low risk, high value.

Also continue using the manual tmux workaround documented in MEMORY.md for
the review lane until the migration lands:
```bash
tmux send-keys -t steward:review.0 '2'
```

---

## Outcome

Analysis complete. Recommending Option A (relocate `.claude/runtime/` to
`.ops_runtime/`) as a 2-3 PR implementation. Ready for orchestrator dispatch
to an author lane.

### Sources

- [Configure permissions — Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [anthropics/claude-code#38806 — Feature request for .claude/ bypass override](https://github.com/anthropics/claude-code/issues/38806)
- [anthropics/claude-code#37157 — .claude/skills/ not exempt despite docs](https://github.com/anthropics/claude-code/issues/37157)
- [anthropics/claude-code#37765 — --dangerously-skip-permissions doesn't bypass .claude/ writes](https://github.com/anthropics/claude-code/issues/37765)
- [anthropics/claude-code#36168 — Bypass broken in versions > v2.1.77](https://github.com/anthropics/claude-code/issues/36168)
- [anthropics/claude-code#29639 — Configured permissions not respected for .claude/ paths](https://github.com/anthropics/claude-code/issues/29639)
- [Claude Code auto mode — Anthropic Engineering](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [Claude Code Changelog 2026](https://claudefa.st/blog/guide/changelog)

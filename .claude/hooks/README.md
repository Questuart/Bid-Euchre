# Auto-Worktree Hook System

This directory contains hooks to enforce and streamline the worktree-only workflow.

## Hooks

### `worktree-guard.sh` (UserPromptSubmit)

**Trigger:** Before every prompt submission

**Purpose:** Blocks work from main checkout on main branch, auto-creates worktree

**Behavior:**
1. Checks if you're in `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre` on `main` branch
2. If yes:
   - Generates timestamped branch name (e.g., `work-20260202-153045`)
   - Creates the branch and worktree automatically
   - Prints the `cd` command to copy-paste
   - Blocks the prompt submission (exit 1)
3. If no: allows prompt submission (exit 0)

**Example output:**
```
🔧 Auto-creating worktree for you...

✅ Worktree created successfully!
   Branch: work-20260202-153045
   Location: ../Bid-Euchre-work-20260202-153045

⛔ Cannot work from main checkout. Please run:

   cd ../Bid-Euchre-work-20260202-153045

Then restart your Claude session in that directory.
```

### `worktree-reminder.sh` (SessionStart)

**Trigger:** When a Claude session starts

**Purpose:** Provides early warning about main checkout

**Behavior:**
1. Checks if you're in main checkout on main branch
2. If yes: prints informational warning (doesn't block)
3. Suggests creating a worktree manually or letting the UserPromptSubmit hook do it
4. Always exits 0 (never blocks session start)

**Example output:**
```
⚠️  SESSION NOTICE: You're in main checkout on main branch.

   All code changes will be blocked by the UserPromptSubmit hook.
   If you want to make changes, you'll need to switch to a worktree.

   The hook will auto-create a worktree when blocked, or you can
   create one manually now:

     git worktree add ../Bid-Euchre-<branch-name> <branch-name>
     cd ../Bid-Euchre-<branch-name>
```

### `post-pr-review.sh` (PostToolUse)

**Trigger:** After any Bash tool call

**Purpose:** Enqueues a durable review request after successful `gh pr create`

**Behavior:**
1. Checks if the Bash command contained `gh pr create` and exit code was 0
2. If yes: writes a `ReviewRequest` to the shared review queue
   (`bid_euchre.ops.review_queue`) with the PR number, HEAD SHA, and branch
3. Emits an informational `additionalContext` message telling the agent that
   a review has been enqueued (no manual `/reviewing-changes` needed)
4. A dedupe sentinel prevents double-trigger when registered in both
   `settings.json` and `settings.local.json`

**Note:** This hook formerly triggered the `/reviewing-changes` skill.  Under
the queue-backed model, it enqueues a request instead.  The review driver
(launched by `post-pr-review-loop.sh`) runs the review loop independently
and writes a verdict that the merge guard checks before allowing merge.

### `pre-merge-review-guard.sh` (PreToolUse)

**Trigger:** Before any Bash tool call containing `gh pr merge`

**Purpose:** Hard local merge guard — blocks merge unless review is complete

**Behavior:**
1. Extracts the PR number from the `gh pr merge` command
2. Resolves the shared review queue root (canonical across worktrees)
3. Checks four conditions (all must pass):
   - A verdict file exists for the PR
   - The verdict's `reviewed_sha` matches the PR's current HEAD
   - The verdict status is `passed`
   - CI checks are green
4. If any check fails: blocks the command (exit 2) with an explanatory message
5. If all pass: allows the merge (exit 0)

**Timeout:** 10s (needs `gh` API calls for SHA and CI status)

### `post-plan-review.sh` (DEPRECATED)

**Status:** Deprecated -- no longer triggers automatically.

**Replacement:** Use `/review-plan [path]` for manual plan review with
independent Codex CLI + Claude agent reviewers.

**History:** Previously auto-invoked the now-retired `/reviewing-plans` skill
after plan file creation. Replaced by `/review-plan` which provides independent
review via Codex CLI + Claude failsafe (PR-4 of the plan review agent chain).

## Helper Script

### `../scripts/claude-worktree.sh`

**Location:** `.claude/scripts/claude-worktree.sh`

**Purpose:** One-command worktree creation + Claude session start

**Usage:**
```bash
# From main checkout
./.claude/scripts/claude-worktree.sh [branch-name]

# Or add to ~/.zshrc:
alias claude-work='/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/.claude/scripts/claude-worktree.sh'

# Then use:
claude-work my-feature-branch
claude-work  # Uses auto-generated timestamp branch
```

**Behavior:**
1. Verifies you're in main checkout
2. Creates branch (or uses existing)
3. Creates worktree at `../Bid-Euchre-<branch-name>`
4. Changes to worktree directory
5. Starts `claude` session in worktree

### `pre-bash-dispatch.sh` (PreToolUse — Bash)

**Trigger:** Before any Bash tool call

**Purpose:** Consolidated dispatcher that runs all PreToolUse Bash hooks in a
single invocation to minimize "Async hook completed" TUI messages (issue #1255).

**Dispatches to (in order):**
1. `pre-worktree-cleanup.sh` — blocks dangerous rm/worktree commands
2. `pre-merge-review-guard.sh` — blocks merge without review verdict
3. `rule-loader.sh` — progressive rule disclosure (context injection)

Guards run first: if either blocks (exit 2), the block propagates immediately
and rule-loader is skipped.

### `post-bash-dispatch.sh` (PostToolUse — Bash)

**Trigger:** After any Bash tool call

**Purpose:** Consolidated dispatcher that runs all PostToolUse Bash hooks in a
single invocation to minimize "Async hook completed" TUI messages (issue #1255).

**Dispatches to (in order):**
1. `post-pr-review.sh` — enqueues review request after `gh pr create`
2. `post-pr-review-loop.sh` — launches review driver after `gh pr create`
3. `post-push-ci-check.sh` — launches CI poller after `git push`
4. `post-merge-ci-check.sh` — checks main CI after `gh pr merge`
5. `post-merge-review.sh` — triggers post-merge review after `gh pr merge`
6. `post-tool-daemon-notify.sh` — checks for background daemon failures
7. `post-task-event.sh` — emits task events on relevant commands
8. `post-merge-notify.sh` — auto-completes task lifecycle on merge

For typical Bash commands, all sub-hooks exit immediately (<100ms each).
Only specific commands (`gh pr create`, `git push`, `gh pr merge`) trigger
meaningful work.

## Configuration

Hooks are registered across two files:

**`.claude/settings.json`** (committed, shared):
- `SessionStart` (compact) → `compact-context.sh`
- `SessionStart` (all) → `session-sync-worktree.sh` (no matcher — fires on init, clear, compact)
- `PreToolUse` (Edit|Write) → `rule-loader.sh`
- `PreToolUse` (Bash) → `pre-bash-dispatch.sh` (consolidated dispatcher)
- `PostToolUse` (Write|Edit) → `post-write-check.sh`
- `PostToolUse` (Bash) → `post-bash-dispatch.sh` (consolidated dispatcher)

**`.claude/settings.local.json`** (gitignored, per-machine):
- `SessionStart` → `worktree-reminder.sh`
- `UserPromptSubmit` → `worktree-guard.sh`

## Limitations

**What hooks CAN do:**
- Create worktrees automatically
- Print helpful messages
- Block operations (exit 1)

**What hooks CANNOT do:**
- Change the session's working directory
- Auto-switch you to the worktree (you must `cd` manually)
- Run after plan mode exits (no post-plan hook event exists)

**Workaround:** The guard hook creates the worktree and provides the exact `cd` command. You just copy-paste and restart Claude.

## Troubleshooting

**Hook doesn't run:**
- Check permissions: `chmod +x .claude/hooks/*.sh`
- Verify hook registration in `.claude/settings.local.json`

**Worktree creation fails:**
- Branch may already exist: `git branch -d <branch-name>` and retry
- Worktree path conflict: remove old worktree with `git worktree remove`

**False positives:**
- Hook only blocks when BOTH conditions are true:
  - Directory = `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre`
  - Branch = `main`
- Working in a worktree or on a different branch is always allowed

## Unattended State Contract

Scripts that run in the background, poll external systems, or continue after
user interaction ends must expose minimal machine-readable state for debugging.

### Required outputs

| Output | Format | Purpose |
|--------|--------|---------|
| `status.json` | JSON object | Current state snapshot: status, summary, timestamp, identifiers |
| Append-only log | Plain text or JSONL | Execution progress and failure details |

### `status.json` minimal schema

```json
{
  "status": "running | success | failure | timeout",
  "summary": "Human-readable one-liner",
  "updated_at": "ISO-8601 timestamp",
  "pr_number": 123
}
```

Additional fields are script-specific but the four above are the baseline.

### Conforming scripts

| Script | State dir | status.json | Log |
|--------|-----------|-------------|-----|
| `scripts/internal/ci_poller.sh` | `.claude/runtime/ci_polls/pr_<N>/` | `status.json` | `poller.log` |
| `scripts/internal/review_driver.py` | `.claude/runtime/review_loops/pr_<N>/` | `state.json` | Per-round artifacts |
| `scripts/internal/plan_review_driver.py` | `.claude/runtime/plan_reviews/<key>/` | `state.json` | Per-round artifacts |

### Synchronous hooks (no state file needed)

| Script | Type | Latency |
|--------|------|---------|
| `.claude/hooks/pre-merge-review-guard.sh` | PreToolUse (blocking) | ~5-10s (gh API calls) |

### Non-conforming scripts (audit)

The following hooks run in the background but do not yet write `status.json`:

| Script | Runs in background? | Gap |
|--------|---------------------|-----|
| `.claude/hooks/post-push-ci-check.sh` | Yes (launches ci_poller) | Delegates to ci_poller — no gap |
| `.claude/hooks/post-pr-review-loop.sh` | Yes (launches review_driver) | Delegates to review_driver — no gap |
| `.claude/hooks/post-merge-review.sh` | Yes (spawns agent) | Agent-spawned — no status.json feasible |
| `.claude/hooks/post-tool-daemon-notify.sh` | Yes (checks daemons) | Lightweight checker — no long-running state |

No actionable gaps were found. All long-running unattended scripts already
conform via their downstream drivers.

## Design Notes

This is a **three-layered solution** to work around hook limitations:

1. **SessionStart hook** - Early warning, non-blocking
2. **UserPromptSubmit hook** - Auto-creates worktree, blocks work, provides `cd` command
3. **Shell helper script** - One-command workflow from terminal (optional)

Since hooks can't change directories, the workflow is:
1. Hook creates worktree automatically
2. Hook prints `cd` command
3. User copies and pastes
4. User restarts Claude in new location

This reduces friction from "manual branch creation + worktree creation + cd" to just "cd + restart".

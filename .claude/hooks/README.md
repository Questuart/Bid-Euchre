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

**Purpose:** Auto-invokes `/reviewing-changes` skill after successful `gh pr create`

**Behavior:**
1. Checks if the Bash command contained `gh pr create` and exit code was 0
2. If yes: emits structured JSON with `additionalContext` directive
3. Claude reads the injected context and auto-invokes the `/reviewing-changes` skill
4. The skill reviews code quality, convention compliance, and generates a handoff summary

**How it works:**
- PostToolUse hooks can return JSON with a `hookSpecificOutput.additionalContext` field
- This text is injected into Claude's conversation context on the next turn
- The directive instructs Claude to invoke the skill without waiting for user input

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

## Configuration

Hooks are registered across two files:

**`.claude/settings.json`** (committed, shared):
- `SessionStart` → `compact-context.sh`
- `PostToolUse` (Write) → `post-write-check.sh`

**`.claude/settings.local.json`** (gitignored, per-machine):
- `SessionStart` → `worktree-reminder.sh`
- `UserPromptSubmit` → `worktree-guard.sh`
- `PostToolUse` (Bash) → `post-pr-review.sh`

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

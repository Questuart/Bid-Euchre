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

### `post-plan-review.sh` (PostToolUse)

**Trigger:** After any Write tool call

**Purpose:** Auto-invokes `/reviewing-plans` skill after plan file creation

**Behavior:**
1. Extracts `tool_input.file_path` from the Write tool's JSON input
2. Checks if the path matches `*/plans/*.md` (excludes `TEMPLATE.md`)
3. If yes: emits `additionalContext` directive triggering `/reviewing-plans`
4. The skill reviews the plan against repo conventions and flags implementation risks

**Configuration:** Registered in `.claude/settings.json` under `PostToolUse` with matcher `"Write"`.

**Review checks:** 10 convention checks (P1-P10) covering code-first planning, determinism, scope,
testing strategy, and template completeness. 5 risk flags (R1-R5) for circular imports, stale data,
missing exports, scope creep, and gate semantics. See `.claude/skills/reviewing-plans/SKILL.md`.

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
- `PostToolUse` (Write) → `post-plan-review.sh`

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

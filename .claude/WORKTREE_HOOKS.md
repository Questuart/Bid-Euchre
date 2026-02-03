# Auto-Worktree Hook System - User Guide

## What This Does

Automatically creates worktrees when you're blocked from working in the main checkout, reducing the workflow to just copy-paste `cd` and restart Claude.

## Quick Start

### The Problem (Before)

```
You: "Let's add a feature"
Claude: ⛔ ERROR: Cannot work from main checkout.
        Create a worktree first:
          git worktree add ../Bid-Euchre-my-branch my-branch
          cd ../Bid-Euchre-my-branch

You: [manually create branch]
You: [manually create worktree]
You: [manually cd]
You: [restart Claude]
```

### The Solution (After)

```
You: "Let's add a feature"
Claude: 🔧 Auto-creating worktree for you...
        ✅ Worktree created successfully!
           Branch: work-20260202-153045
           Location: ../Bid-Euchre-work-20260202-153045

        ⛔ Cannot work from main checkout. Please run:

           cd ../Bid-Euchre-work-20260202-153045

You: [copy-paste cd command]
You: [restart Claude]
```

**Saved steps:** branch creation, worktree creation, path construction

## How It Works

### 1. SessionStart Hook (Early Warning)

When you start a Claude session in the main checkout on `main` branch, you'll see:

```
⚠️  SESSION NOTICE: You're in main checkout on main branch.

   All code changes will be blocked by the UserPromptSubmit hook.
   If you want to make changes, you'll need to switch to a worktree.
```

**Non-blocking** - you can still ask questions, explore code, etc.

### 2. UserPromptSubmit Hook (Auto-Create Worktree)

When you try to make changes, the hook:
1. ✅ **Creates the branch** automatically (timestamped name)
2. ✅ **Creates the worktree** automatically
3. ✅ **Prints the exact `cd` command** to copy-paste
4. ❌ **Blocks the operation** (you're still in main checkout)

After copy-pasting `cd`, restart Claude in the new worktree and you're ready to work.

### 3. Shell Helper (Optional Power User Tool)

Add to `~/.zshrc` or `~/.bashrc`:

```bash
alias claude-work='/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre/.claude/scripts/claude-worktree.sh'
```

Then from the main checkout:

```bash
# Auto-generated branch name
claude-work

# Custom branch name
claude-work my-feature-branch
```

This creates the worktree, changes to it, and starts Claude in one command.

## Examples

### Example 1: Plan Mode Workflow

```bash
# Start in main checkout
pwd
# /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre

# Start Claude, enter plan mode
claude

# You: "I want to add feature X"
# Claude enters plan mode, explores, creates plan
# Claude: "Ready to exit plan mode and implement?"
# You: "Yes"

# Hook triggers:
# 🔧 Auto-creating worktree for you...
# ✅ Worktree created: ../Bid-Euchre-work-20260202-153045
# ⛔ Cannot work from main checkout. Please run:
#    cd ../Bid-Euchre-work-20260202-153045

# Copy-paste the cd command
cd ../Bid-Euchre-work-20260202-153045

# Restart Claude
claude

# Now you can implement the plan
```

### Example 2: Using Shell Helper

```bash
# From main checkout
claude-work add-bidding-feature

# Worktree created, you're now in ../Bid-Euchre-add-bidding-feature
# Claude session starts automatically
# You can start working immediately
```

### Example 3: Already in Worktree

```bash
# You're in a worktree already
pwd
# /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-my-feature

# Hooks don't trigger - you can work normally
claude
# No warnings, no blocks, just normal operation
```

## What Changed

### Files Created

```
.claude/hooks/worktree-guard.sh       # UserPromptSubmit hook (auto-create)
.claude/hooks/worktree-reminder.sh    # SessionStart hook (early warning)
.claude/hooks/README.md               # Technical documentation
.claude/scripts/claude-worktree.sh    # Shell helper script
.claude/WORKTREE_HOOKS.md            # This file (user guide)
```

### Files Modified

```
.claude/settings.local.json           # Added SessionStart hook, enhanced UserPromptSubmit
```

### Old vs New UserPromptSubmit Hook

**Before:**
- Prints error message
- Tells you to create worktree
- Blocks operation

**After:**
- **Creates worktree automatically**
- Prints ready-to-copy `cd` command
- Blocks operation

**Key improvement:** Removes manual branch + worktree creation steps.

## Limitations

**Hooks cannot:**
- Change your session's working directory
- Auto-switch you to the worktree
- Run after plan mode exits (no such hook event exists)

**Workaround:** The hook creates everything for you, you just `cd` and restart.

## Troubleshooting

**Q: Hook isn't running**
- Check permissions: `ls -la .claude/hooks/` should show `-rwxr-xr-x`
- If not: `chmod +x .claude/hooks/*.sh .claude/scripts/*.sh`

**Q: Worktree creation fails**
- Branch may exist: `git branch -D work-<timestamp>` and try again
- Worktree path conflict: `git worktree remove ../Bid-Euchre-work-<timestamp>`

**Q: I'm getting blocked even though I'm in a worktree**
- Verify location: `git rev-parse --show-toplevel`
- Should NOT be `/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre`
- Verify branch: `git branch --show-current`
- Should NOT be `main`

**Q: Can I use custom branch names instead of timestamps?**
- Yes, use the shell helper: `claude-work my-custom-branch-name`
- Or create worktree manually before starting Claude

**Q: Can I disable this?**
- Remove the hooks from `.claude/settings.local.json`
- But you'll lose the worktree enforcement (not recommended)

## Advanced: Customizing Branch Names

By default, branches are named `work-YYYYMMDD-HHMMSS` (e.g., `work-20260202-153045`).

To customize the naming pattern, edit `.claude/hooks/worktree-guard.sh`:

```bash
# Current (line ~12):
BRANCH_NAME="work-$(date +%Y%m%d-%H%M%S)"

# Example: Include username
BRANCH_NAME="$USER-work-$(date +%Y%m%d-%H%M%S)"

# Example: Use git config user name
BRANCH_NAME="$(git config user.name | tr ' ' '-')-work-$(date +%Y%m%d-%H%M%S)"

# Example: Sequential numbers
BRANCH_NAME="work-$(git branch | grep -c 'work-' | awk '{print $1+1}')"
```

## Testing the Setup

### Test 1: SessionStart Hook

```bash
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre
git checkout main
claude
# Should see warning message at session start
```

### Test 2: UserPromptSubmit Hook

```bash
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre
git checkout main
claude
# In Claude: "Let's add a feature"
# Should see worktree auto-created with cd command
```

### Test 3: Shell Helper

```bash
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre
./.claude/scripts/claude-worktree.sh test-branch
# Should create worktree and start Claude
```

### Test 4: No False Positives

```bash
# From a worktree
cd /Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-my-feature
claude
# Should NOT see any warnings or blocks
```

## See Also

- `.claude/hooks/README.md` - Technical documentation for hook implementation
- `docs/02_agent/AGENTS.md` - Full worktree workflow documentation
- `.claude/CLAUDE.md` - Project memory and quick reference

## Feedback

If you encounter issues or have suggestions for improving the auto-worktree system, please file an issue in the repository.

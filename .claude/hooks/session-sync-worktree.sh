#!/usr/bin/env bash
# Auto-sync steward worktrees to main on session start.
# Only acts on *steward* worktrees. Safe: never force-checkouts over dirty
# state, never deletes branches, never touches non-steward worktrees.
# See: .claude/rules/75_worktree_protection.md, GitHub issue #1208.
#
# Triggered by SessionStart hook with "worktree-sync" matcher.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
LOG_PREFIX="[session-sync]"

# --------------------------------------------------------------------------
# Guard: only act on steward worktrees
# --------------------------------------------------------------------------
if [[ "$PROJECT_DIR" != *steward* ]]; then
  exit 0
fi

# --------------------------------------------------------------------------
# Guard: skip if working tree is dirty
# --------------------------------------------------------------------------
if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain 2>/dev/null)" ]]; then
  echo "${LOG_PREFIX} WARNING: Dirty working tree — skipping auto-sync. Clean or stash changes manually."
  exit 0
fi

# --------------------------------------------------------------------------
# Guard: skip if current branch has an open PR
# --------------------------------------------------------------------------
CURRENT_BRANCH="$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "")"

if [[ -z "$CURRENT_BRANCH" ]]; then
  echo "${LOG_PREFIX} WARNING: Detached HEAD — skipping auto-sync."
  exit 0
fi

# Already on main — just pull
if [[ "$CURRENT_BRANCH" == "main" ]]; then
  echo "${LOG_PREFIX} Already on main — pulling latest."
  git -C "$PROJECT_DIR" pull origin main --ff-only 2>/dev/null || true
  exit 0
fi

# Check if current branch has an open PR (skip if so — active work)
PR_STATE="$(gh pr view "$CURRENT_BRANCH" --repo Questuart/Bid-Euchre --json state --jq '.state' 2>/dev/null || echo "NONE")"

if [[ "$PR_STATE" == "OPEN" ]]; then
  echo "${LOG_PREFIX} Branch '$CURRENT_BRANCH' has an open PR — skipping auto-sync."
  exit 0
fi

# --------------------------------------------------------------------------
# Safe to sync: branch has no open PR (merged, closed, or never had one)
# --------------------------------------------------------------------------
echo "${LOG_PREFIX} Syncing '$CURRENT_BRANCH' → main (PR state: ${PR_STATE})"

# Fetch latest main
git -C "$PROJECT_DIR" fetch origin main --quiet 2>/dev/null || true

# Switch to tracking origin/main. We can't checkout 'main' directly because
# it's used by the primary worktree — instead reset the current branch to
# origin/main, giving us the same effect.
git -C "$PROJECT_DIR" reset --hard origin/main 2>/dev/null || {
  echo "${LOG_PREFIX} WARNING: Failed to reset to origin/main — skipping."
  exit 0
}

echo "${LOG_PREFIX} Synced to $(git -C "$PROJECT_DIR" log --oneline -1)"

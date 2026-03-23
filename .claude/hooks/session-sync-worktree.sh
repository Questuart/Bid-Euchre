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
  echo >&2 "${LOG_PREFIX} WARNING: Dirty working tree — skipping auto-sync. Clean or stash changes manually."
  exit 0
fi

# --------------------------------------------------------------------------
# Guard: skip if current branch has an open PR
# --------------------------------------------------------------------------
CURRENT_BRANCH="$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || echo "")"

if [[ -z "$CURRENT_BRANCH" ]]; then
  echo >&2 "${LOG_PREFIX} WARNING: Detached HEAD — skipping auto-sync."
  exit 0
fi

# Already on main — just pull
if [[ "$CURRENT_BRANCH" == "main" ]]; then
  echo >&2 "${LOG_PREFIX} Already on main — pulling latest."
  git -C "$PROJECT_DIR" pull origin main --ff-only 2>/dev/null || true
  exit 0
fi

# Check if current branch has an open PR (skip if so — active work).
# Fail closed: if gh is unavailable or auth fails, skip sync rather than
# risk resetting a branch that has an open PR we can't see.
PR_STATE="$(gh pr view "$CURRENT_BRANCH" --repo Questuart/Bid-Euchre --json state --jq '.state' 2>/dev/null)" || {
  echo >&2 "${LOG_PREFIX} WARNING: Could not query PR state (gh unavailable or auth error) — skipping auto-sync."
  exit 0
}

# Treat empty output (no PR found) as "NONE"
PR_STATE="${PR_STATE:-NONE}"

if [[ "$PR_STATE" == "OPEN" ]]; then
  echo >&2 "${LOG_PREFIX} Branch '$CURRENT_BRANCH' has an open PR — skipping auto-sync."
  exit 0
fi

# --------------------------------------------------------------------------
# Guard: skip if branch has unpushed commits
# --------------------------------------------------------------------------
# Fetch first so origin/main is current for the comparison.
git -C "$PROJECT_DIR" fetch origin main --quiet 2>/dev/null || true

AHEAD="$(git -C "$PROJECT_DIR" rev-list origin/main..HEAD --count 2>/dev/null || echo "unknown")"
if [[ "$AHEAD" != "0" ]]; then
  echo >&2 "${LOG_PREFIX} WARNING: Branch '$CURRENT_BRANCH' is ${AHEAD} commit(s) ahead of origin/main — skipping auto-sync to avoid losing unpushed work."
  exit 0
fi

# --------------------------------------------------------------------------
# Safe to sync: no open PR, no unpushed commits, clean working tree
# --------------------------------------------------------------------------
echo >&2 "${LOG_PREFIX} Syncing '$CURRENT_BRANCH' → main (PR state: ${PR_STATE})"

# Switch to tracking origin/main. We can't checkout 'main' directly because
# it's used by the primary worktree — instead reset the current branch to
# origin/main, giving us the same effect.
git -C "$PROJECT_DIR" reset --hard origin/main 2>/dev/null || {
  echo >&2 "${LOG_PREFIX} WARNING: Failed to reset to origin/main — skipping."
  exit 0
}

echo >&2 "${LOG_PREFIX} Synced to $(git -C "$PROJECT_DIR" log --oneline -1)"

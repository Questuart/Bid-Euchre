#!/usr/bin/env bash
# Auto-sync steward worktrees to main on session start.
# Only acts on *steward* worktrees. Safe: never force-checkouts over dirty
# state, never deletes branches, never touches non-steward worktrees.
# See: .claude/rules/75_worktree_protection.md, GitHub issue #1208.
#
# Triggered by SessionStart hook (fires on all session starts: init, clear,
# compact).  Must NEVER exit non-zero — a failing SessionStart hook leaves
# the session at a blank prompt with 0 tokens and no context.

# Safety: guarantee exit 0 on ANY error.  SessionStart hooks that exit
# non-zero break the session (blank prompt, 0 tokens, no /start-task pickup).
trap 'exit 0' ERR

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
  git -C "$PROJECT_DIR" pull origin main --ff-only 2>/dev/null || true
  exit 0
fi

# Check if current branch has an open PR (skip if so — active work).
# Fail closed: if gh is unavailable or auth fails, skip sync rather than
# risk resetting a branch that has an open PR we can't see.
#
# Use `timeout 5` to cap the network call — without it, a slow GitHub API
# response can exhaust the hook's 15s timeout and kill the whole hook,
# bypassing all || guards and leaving the session broken.
PR_STATE="$(timeout 5 gh pr view "$CURRENT_BRANCH" --repo Questuart/Bid-Euchre --json state --jq '.state' 2>/dev/null)" || {
  echo >&2 "${LOG_PREFIX} WARNING: Could not query PR state (gh unavailable, auth error, or timeout) — skipping auto-sync."
  exit 0
}

# Treat empty output (no PR found) as "NONE"
PR_STATE="${PR_STATE:-NONE}"

if [[ "$PR_STATE" == "OPEN" ]]; then
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
# Switch to tracking origin/main. We can't checkout 'main' directly because
# it's used by the primary worktree — instead reset the current branch to
# origin/main, giving us the same effect.
git -C "$PROJECT_DIR" reset --hard origin/main >/dev/null 2>&1 || {
  echo >&2 "${LOG_PREFIX} WARNING: Failed to reset to origin/main — skipping."
  exit 0
}

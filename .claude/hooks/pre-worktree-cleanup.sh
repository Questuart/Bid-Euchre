#!/usr/bin/env bash
# PreToolUse hook: Advisory warning when dangerous worktree removal is attempted.
#
# Matches Bash tool input containing patterns like:
#   rm -rf ../Bid-Euchre*
#   git worktree remove
#   git worktree prune
#
# Prints a warning suggesting the safe ops.py worktrees prune flow instead.
# Advisory only — does NOT block the command (exit 0).
#
# Timeout: 5s

set -euo pipefail

# PreToolUse receives tool_input via environment
TOOL_INPUT="${TOOL_INPUT:-}"
if [ -z "$TOOL_INPUT" ]; then
    exit 0
fi

# Check for dangerous worktree operations
MATCHED=""

if echo "$TOOL_INPUT" | grep -qE "rm\s+(-rf?|--recursive)\s+.*Bid-Euchre"; then
    MATCHED="rm -rf on Bid-Euchre directory"
elif echo "$TOOL_INPUT" | grep -q "git worktree remove"; then
    MATCHED="git worktree remove"
elif echo "$TOOL_INPUT" | grep -q "git worktree prune"; then
    MATCHED="git worktree prune"
fi

if [ -z "$MATCHED" ]; then
    exit 0
fi

# Print advisory warning (shows up in tool output)
cat <<EOF

⚠ WARNING: Detected potentially dangerous worktree operation: $MATCHED

Use the safe cleanup flow instead:
  uv run python scripts/internal/ops.py worktrees prune           # dry-run first
  uv run python scripts/internal/ops.py worktrees prune --execute  # then execute

This ensures:
  - Protected steward worktrees are never removed
  - Dirty worktrees are quarantined (diff saved) first
  - Events are emitted for audit trail

EOF

# Advisory only — allow the command to proceed (exit 0)
exit 0

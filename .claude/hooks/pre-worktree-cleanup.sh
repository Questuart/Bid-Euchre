#!/usr/bin/env bash
# PreToolUse hook: Block dangerous worktree removal and redirect to safe ops flow.
#
# Matches Bash tool input containing patterns like:
#   rm -rf ../Bid-Euchre*
#   git worktree remove
#   git worktree prune
#
# Blocks the command and suggests ops.py worktrees prune instead.
# Per governing plan: "Direct rm -rf on worktree directories is intercepted
# by PreToolUse hook and redirected to ops.py worktrees prune."
#
# Timeout: 5s

set -euo pipefail

# PreToolUse receives JSON on stdin
INPUT=$(cat)

# Extract the command being attempted
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
    exit 0
fi

# Check for dangerous worktree operations
MATCHED=""

if echo "$COMMAND" | grep -qE "rm\s+(-rf?|--recursive)\s+.*Bid-Euchre"; then
    MATCHED="rm -rf on Bid-Euchre directory"
elif echo "$COMMAND" | grep -q "git worktree remove"; then
    MATCHED="git worktree remove"
elif echo "$COMMAND" | grep -q "git worktree prune"; then
    MATCHED="git worktree prune"
fi

if [ -z "$MATCHED" ]; then
    exit 0
fi

# Block the command and redirect to safe flow
cat <<EOF
BLOCKED: Detected dangerous worktree operation: $MATCHED

Use the safe cleanup flow instead:
  uv run python scripts/internal/ops.py worktrees prune           # dry-run first
  uv run python scripts/internal/ops.py worktrees prune --execute  # then execute
  uv run python scripts/internal/ops.py worktrees archive <path>   # archive one worktree

This ensures:
  - Protected steward worktrees are never removed
  - Dirty worktrees are quarantined (diff saved) first
  - Events are emitted for audit trail
EOF

# Non-zero exit blocks the command from executing
exit 2

#!/usr/bin/env bash
# PostToolUse hook: Emit durable events on task-relevant tool completions.
#
# Reads PostToolUse JSON from stdin (matching existing hook patterns like
# post-pr-review.sh and post-merge-ci-check.sh). Matches successful
# gh pr merge commands and emits task_completed events.
#
# Timeout: 5s (must be fast — runs on every Bash tool completion)

set -euo pipefail

# Read PostToolUse JSON payload from stdin
INPUT=$(cat)

# Extract the bash command and exit code
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0' 2>/dev/null || echo "0")

# Only process successful commands
if [ "$EXIT_CODE" != "0" ]; then
    exit 0
fi

# Resolve lane_id from worktree directory name
# e.g., Bid-Euchre-steward-author-c → author-c
LANE_ID="unknown"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR")
    case "$DIR_NAME" in
        *steward-author-scratch) LANE_ID="author-scratch" ;;
        *steward-author-b)       LANE_ID="author-b" ;;
        *steward-author-c)       LANE_ID="author-c" ;;
        *steward-author-d)       LANE_ID="author-d" ;;
        *steward-author)         LANE_ID="author-a" ;;
        *steward-review)         LANE_ID="review" ;;
        *steward-ops)            LANE_ID="ops" ;;
    esac
fi

# Check for task-relevant patterns in the command
EVENT_TYPE=""
DETAILS=""

if [[ "$COMMAND" == *"gh pr merge"* ]]; then
    EVENT_TYPE="task_completed"
    # Try to extract PR number from command
    PR_NUM=$(echo "$COMMAND" | grep -oE '[0-9]+' | head -1 || true)
    DETAILS="PR #${PR_NUM:-unknown} merged"
fi

# Only emit if we matched a relevant pattern
if [ -z "$EVENT_TYPE" ]; then
    exit 0
fi

# Emit the event (fire-and-forget, don't block on failure)
# Use environment variables instead of string interpolation to avoid
# injection from shell metacharacters in DETAILS or other values.
EVENT_TYPE="$EVENT_TYPE" LANE_ID="$LANE_ID" DETAILS="$DETAILS" \
uv run python -c "
import os
from bid_euchre.ops.events import append_event
append_event(
    os.environ['EVENT_TYPE'],
    'hook.post-task',
    os.environ['LANE_ID'],
    {'details': os.environ['DETAILS']},
)
" 2>/dev/null || true

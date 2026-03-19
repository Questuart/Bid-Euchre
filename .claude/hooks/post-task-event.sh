#!/usr/bin/env bash
# PostToolUse hook: Emit durable events on task-relevant tool completions.
#
# Matches Bash tool output containing patterns like "gh pr merge" and emits
# structured events to the ops event log.
#
# Timeout: 5s (must be fast — runs on every Bash tool completion)

set -euo pipefail

# Read tool output from stdin (PostToolUse receives tool_input and tool_output)
TOOL_OUTPUT="${TOOL_OUTPUT:-}"
if [ -z "$TOOL_OUTPUT" ]; then
    # Try reading from the environment or bail
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

# Check for task-relevant patterns in tool output
EVENT_TYPE=""
DETAILS=""

if echo "$TOOL_OUTPUT" | grep -q "gh pr merge"; then
    EVENT_TYPE="task_completed"
    DETAILS="PR merged"
elif echo "$TOOL_OUTPUT" | grep -q "Successfully rebased"; then
    # Not a failure event, just informational — skip
    exit 0
fi

# Only emit if we matched a relevant pattern
if [ -z "$EVENT_TYPE" ]; then
    exit 0
fi

# Emit the event (fire-and-forget, don't block on failure)
uv run python -c "
from bid_euchre.ops.events import append_event
append_event('$EVENT_TYPE', 'hook.post-task', '$LANE_ID', {'details': '$DETAILS'})
" 2>/dev/null || true

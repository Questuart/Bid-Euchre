#!/usr/bin/env bash
# PostToolUse hook: Auto-complete task lifecycle on successful PR merge.
#
# When an author lane merges a PR via `gh pr merge`:
#   1. Finds the active dispatched task packet owned by this lane
#   2. Transitions it to "completed" status
#   3. Sends a completion message to the orchestrator via message bus
#
# Guards:
#   - Only fires on successful `gh pr merge` (same as post-merge-review.sh)
#   - Deduplicates via sentinel file (one notification per PR)
#   - Best-effort: failures are logged but don't block the merge
#
# Lane identity:
#   - Uses CLAUDE_AGENT_NAME env var (e.g., "steward-author-c" → "author-c")
#   - Falls back to CLAUDE_PROJECT_DIR directory name parsing
#
# Resolves BD-005: No auto-completion callback from agent to task queue.
#
# Timeout: 10s (needs to call Python for bus + task_queue operations)

set -euo pipefail

# Read PostToolUse JSON payload from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0' 2>/dev/null || echo "0")

# Guard: only fire on successful `gh pr merge`
if [[ "$COMMAND" != *"gh pr merge"* ]] || [[ "$EXIT_CODE" != "0" ]]; then
    exit 0
fi

# Extract PR number for deduplication and messaging
PR_NUM=$(echo "$COMMAND" | grep -oE '[0-9]+' | head -1 || true)

# Dedupe guard — one notification per PR merge
if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-post-merge-notify-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
        exit 0
    fi
    touch "$SENTINEL"
fi

# Resolve lane_id
LANE_ID=""

# Try CLAUDE_AGENT_NAME first (e.g., "steward-author-c" → "author-c")
if [ -n "${CLAUDE_AGENT_NAME:-}" ]; then
    LANE_ID=$(echo "$CLAUDE_AGENT_NAME" | sed 's/^steward-//')
fi

# Fall back to CLAUDE_PROJECT_DIR directory name parsing
if [ -z "$LANE_ID" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR")
    case "$DIR_NAME" in
        *steward-author-scratch) LANE_ID="author-scratch" ;;
        *steward-author-b)       LANE_ID="author-b" ;;
        *steward-author-c)       LANE_ID="author-c" ;;
        *steward-author-d)       LANE_ID="author-d" ;;
        *steward-author)         LANE_ID="author-a" ;;
        *steward-brws-author-a)  LANE_ID="brws-author-a" ;;
        *steward-brws-author-b)  LANE_ID="brws-author-b" ;;
        *steward-brws-author-c)  LANE_ID="brws-author-c" ;;
        *steward-brws-author-d)  LANE_ID="brws-author-d" ;;
        *steward-flex-a)         LANE_ID="flex-a" ;;
        *steward-flex-b)         LANE_ID="flex-b" ;;
        *steward-flex-c)         LANE_ID="flex-c" ;;
        *steward-review)         LANE_ID="review" ;;
        *steward-ops)            LANE_ID="ops" ;;
    esac
fi

if [ -z "$LANE_ID" ]; then
    # Cannot identify lane — skip silently
    exit 0
fi

# Run the completion logic in Python (fire-and-forget, don't block on failure)
LANE_ID="$LANE_ID" PR_NUM="${PR_NUM:-unknown}" \
uv run python -c "
import os, sys

lane_id = os.environ['LANE_ID']
pr_num = os.environ['PR_NUM']

# 1. Find and complete the active dispatched task packet for this lane
packet_id = None
try:
    from bid_euchre.ops.task_queue import list_packets, transition_status
    dispatched = list_packets(status_filter='dispatched', owner_filter=lane_id)
    if dispatched:
        pkt = dispatched[0]
        packet_id = pkt.packet_id
        transition_status(packet_id, 'completed')
except Exception as exc:
    print(f'post-merge-notify: task transition failed: {exc}', file=sys.stderr)

# 2. Send completion message to orchestrator via message bus
try:
    from bid_euchre.ops.message_bus import create_message, send_message
    msg = create_message(
        from_lane=lane_id,
        to_lane='orchestrator',
        message_type='completion',
        summary=f'PR #{pr_num} merged — task complete',
        task_id=packet_id,
        payload={'pr_number': pr_num, 'packet_id': packet_id},
    )
    send_message(msg)
except Exception as exc:
    print(f'post-merge-notify: message send failed: {exc}', file=sys.stderr)
" 2>/dev/null || true

exit 0

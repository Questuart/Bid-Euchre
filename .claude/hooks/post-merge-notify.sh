#!/usr/bin/env bash
# PostToolUse hook: Auto-complete task lifecycle on successful PR merge.
#
# When an author lane merges a PR via `gh pr merge`:
#   1. Finds the active dispatched task packet by PR number (Gap B)
#   2. Transitions it to "completed" status
#   3. Sends a completion message to the orchestrator via message bus
#
# Guards:
#   - Only fires on successful `gh pr merge` (same as post-merge-review.sh)
#   - Deduplicates via sentinel file (one notification per PR)
#   - Sentinel created AFTER successful execution (Gap C fix)
#   - Best-effort: failures are logged but don't block the merge
#
# Packet lookup (Gap B):
#   - Primary: match PR number against dispatched packets' metadata.pr_number
#   - Fallback: resolve lane identity and find dispatched packet for that lane
#   - Lane identity via CLAUDE_AGENT_NAME or CLAUDE_PROJECT_DIR parsing
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
    # Gap C: sentinel is created AFTER successful execution (see below)
fi

# Resolve lane_id (fallback for Gap B)
LANE_ID=""

# Try CLAUDE_AGENT_NAME first (e.g., "steward-author-c" -> "author-c")
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

# Run the completion logic in Python (fire-and-forget, don't block on failure)
# Gap B: primary lookup by PR number, fallback to lane identity
LANE_ID="${LANE_ID:-}" PR_NUM="${PR_NUM:-unknown}" \
uv run python -c "
import os, sys

lane_id = os.environ.get('LANE_ID', '')
pr_num = os.environ['PR_NUM']

# 1. Find and complete the active dispatched task packet
#    Primary (Gap B): look up by PR number in metadata
#    Fallback: look up by lane owner
packet_id = None
try:
    from bid_euchre.ops.task_queue import list_packets, transition_status
    dispatched = list_packets(status_filter='dispatched')

    # Primary: match by PR number in metadata
    if pr_num and pr_num != 'unknown':
        for pkt in dispatched:
            pkt_pr = (pkt.metadata or {}).get('pr_number')
            if pkt_pr is not None and str(pkt_pr) == str(pr_num):
                packet_id = pkt.packet_id
                lane_id = lane_id or pkt.owner or ''
                break

    # Fallback: match by lane owner
    if packet_id is None and lane_id:
        for pkt in dispatched:
            if pkt.owner == lane_id:
                packet_id = pkt.packet_id
                break

    if packet_id:
        transition_status(packet_id, 'completed')
except Exception as exc:
    print(f'post-merge-notify: task transition failed: {exc}', file=sys.stderr)

# 2. Send completion message to orchestrator via message bus
from_lane = lane_id or 'unknown'
try:
    from bid_euchre.ops.message_bus import create_message, send_message
    msg = create_message(
        from_lane=from_lane,
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

# Gap C: sentinel created AFTER successful execution so failures can retry
if [ -n "${PR_NUM:-}" ]; then
    touch "/tmp/.claude-post-merge-notify-${PR_NUM}"
fi

exit 0

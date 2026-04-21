#!/usr/bin/env bash
# PostToolUse hook: Auto-complete task lifecycle on successful PR merge.
#
# When an author lane merges a PR via `gh pr merge`:
#   1. Finds the active dispatched task packet by PR number (Gap B)
#   2. Transitions it to "completed" status
#   3. Sends a completion message to the orchestrator via message bus
#   4. Best-effort tmux nudge ("/inbox-poll") to wake the orchestrator
#      immediately so it processes the completion without waiting for
#      the next /fleet-check cron tick (PR-MSG-1).
#
# Handles two merge modes:
#   - Direct merge (`gh pr merge <N> --squash`): completes immediately
#   - Auto-merge (`gh pr merge <N> --auto --squash`): launches a background
#     watcher that polls for actual merge, then completes (issue #1461)
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

# Extract PR number for deduplication and messaging.
# The first positional arg after "gh pr merge" can be a bare number (PR ID),
# a branch name (e.g., "fix/issue-1234"), or a URL.  Try bare digits first,
# then /pull/<N> URL pattern, then fall back to stdout parsing.
MERGE_ARG=$(echo "$COMMAND" | sed -n 's/.*gh pr merge[[:space:]]\{1,\}\([^[:space:]]\{1,\}\).*/\1/p')
PR_NUM=""
if [[ "$MERGE_ARG" =~ ^[0-9]+$ ]]; then
    PR_NUM="$MERGE_ARG"
elif [[ "$MERGE_ARG" =~ /pull/([0-9]+) ]]; then
    PR_NUM="${BASH_REMATCH[1]}"
fi

# Fallback: extract PR number from command stdout (e.g., "Merged pull request #1453")
if [ -z "$PR_NUM" ]; then
    PR_NUM=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' 2>/dev/null \
        | grep -oE '#[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
fi

# Dedupe guard — one notification per PR merge
if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-post-merge-notify-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
        exit 0
    fi
    # Gap C: sentinel is created AFTER successful execution (see below)
fi

# Resolve lane_id (fallback for Gap B). Sourced helper centralizes the
# 19-case fleet table — see .claude/hooks/lib/resolve-lane-id.sh (#2690).
LANE_ID=""
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && \
   [ -r "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh" ]; then
    # shellcheck disable=SC1091
    . "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh"
    LANE_ID=$(resolve_lane_id)
fi

# ---------------------------------------------------------------------------
# Completion logic (reusable function)
# ---------------------------------------------------------------------------
run_completion() {
    local lane="$1"
    local pr="$2"
    local project_dir="${3:-${CLAUDE_PROJECT_DIR:-.}}"
    local auto_merge="${4:-false}"

    # Run in the correct directory so uv finds pyproject.toml.
    # Returns the Python exit code so callers can gate on success
    # (e.g., skip sentinel creation on failure to allow retries).
    (
        cd "$project_dir" 2>/dev/null || true

        LANE_ID="$lane" PR_NUM="$pr" AUTO_MERGE="$auto_merge" \
        uv run python -c "
import os, sys

lane_id = os.environ.get('LANE_ID', '')
pr_num = os.environ['PR_NUM']
auto_merge = os.environ.get('AUTO_MERGE', 'false') == 'true'

# Track whether the critical operation (task transition) failed.
# Message send is advisory — its failure should not prevent sentinel
# creation or block retries.
_transition_failed = False

# 1. Find and complete the active dispatched task packet
#    Primary (Gap B): look up by PR number in metadata
#    Fallback: look up by lane owner
#    Uses ServiceProvider for task_queue operations (SP-5-01 PR4).
packet_id = None
try:
    from bid_euchre.ops.core.provider import ServiceProvider
    _provider = ServiceProvider.default()
    dispatched = _provider.task_queue.list_packets(status='dispatched')

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
        _provider.task_queue.transition_status(packet_id, 'completed')
except Exception as exc:
    print(f'post-merge-notify: task transition failed: {exc}', file=sys.stderr)
    _transition_failed = True

# 2. Clean up orphaned build/test processes from this lane's worktree.
#    Prevents pytest/make/uv accumulation across fleet task cycles (#1951).
if lane_id:
    try:
        from bid_euchre.ops.worker_pool import cleanup_lane_processes
        killed = cleanup_lane_processes(lane_id)
        if killed:
            print(f'post-merge-notify: cleaned up {len(killed)} orphaned process(es)', file=sys.stderr)
    except Exception as exc:
        print(f'post-merge-notify: process cleanup failed: {exc}', file=sys.stderr)

# 3. Send completion message to orchestrator via message bus (advisory)
from_lane = lane_id or 'unknown'
suffix = ' (auto-merge)' if auto_merge else ''
payload = {'pr_number': pr_num, 'packet_id': packet_id}
if auto_merge:
    payload['auto_merge'] = True
_send_succeeded = False
try:
    from bid_euchre.ops.message_bus import create_message, send_message
    msg = create_message(
        from_lane=from_lane,
        to_lane='orchestrator',
        message_type='completion',
        summary=f'PR #{pr_num} merged{suffix} — task complete',
        task_id=packet_id,
        payload=payload,
    )
    send_message(msg)
    _send_succeeded = True
except Exception as exc:
    print(f'post-merge-notify: message send failed: {exc}', file=sys.stderr)

# 4. Best-effort nudge: wake the orchestrator so it processes the
#    completion message immediately instead of waiting for the next
#    /fleet-check cron tick.  This is the PR-MSG-1 attention fast path.
#
#    Delivery-policy boundary (see
#    plans/sessions/2026-04-20_messaging-revamp-execution-plan.md):
#    the durable send happens via message_bus.send_message(); the
#    tmux-layer nudge lives in worker_pool.nudge_inbox().  Only nudge
#    after a successful send — nudging on failure would surface stale
#    inbox state without the new message.
if _send_succeeded:
    try:
        from bid_euchre.ops.worker_pool import nudge_inbox
        nudge_inbox('orchestrator')
    except Exception as exc:
        print(f'post-merge-notify: nudge failed: {exc}', file=sys.stderr)

# Exit non-zero only when the task transition itself failed — this
# prevents sentinel creation so the next hook invocation can retry.
# Message send and nudge failures are logged but do not block the
# sentinel.
if _transition_failed:
    sys.exit(1)
" 2>/dev/null
    )
}

# ---------------------------------------------------------------------------
# Auto-merge detection: if --auto flag is present, the PR isn't merged yet.
# Launch a background watcher that polls for actual merge completion.
# (Issue #1461: auto-merged PRs bypass the PostToolUse hook)
# ---------------------------------------------------------------------------
if [[ "$COMMAND" == *"--auto"* ]]; then
    if [ -n "$PR_NUM" ]; then
        # Capture values for the background subshell
        _LANE_ID="$LANE_ID"
        _PR_NUM="$PR_NUM"
        _PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

        (
            # Background watcher: poll for actual merge, then send completion.
            # Polls every 30s for up to 30 minutes (60 iterations).
            # Self-terminates on MERGED, CLOSED, or timeout.
            for _attempt in $(seq 1 60); do
                sleep 30
                STATE=$(gh pr view "$_PR_NUM" --json state --jq '.state' 2>/dev/null || echo "unknown")

                if [ "$STATE" = "MERGED" ]; then
                    # PR is actually merged — reuse shared completion logic.
                    # Only create sentinel on success so failures can retry.
                    if run_completion "$_LANE_ID" "$_PR_NUM" "$_PROJECT_DIR" "true"; then
                        touch "/tmp/.claude-post-merge-notify-${_PR_NUM}"
                        exit 0
                    fi
                    # Completion failed — continue polling to retry
                    continue
                elif [ "$STATE" = "CLOSED" ]; then
                    # PR closed without merging — nothing to do
                    exit 0
                fi
            done
            # Timeout after 30 minutes — give up silently
        ) </dev/null >/dev/null 2>&1 &
    fi
    exit 0
fi

# ---------------------------------------------------------------------------
# Direct merge: complete immediately (existing behavior)
# ---------------------------------------------------------------------------
# Gap C: sentinel created AFTER successful execution so failures can retry.
# run_completion now returns non-zero on Python failure, so the sentinel is
# only created when both task transition and message send succeed.
if run_completion "$LANE_ID" "${PR_NUM:-unknown}" "${CLAUDE_PROJECT_DIR:-.}"; then
    if [ -n "${PR_NUM:-}" ]; then
        touch "/tmp/.claude-post-merge-notify-${PR_NUM}"
    fi
fi

exit 0

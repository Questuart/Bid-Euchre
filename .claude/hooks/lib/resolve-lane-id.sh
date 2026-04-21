#!/usr/bin/env bash
# resolve-lane-id.sh — canonical lane-id resolver for steward hooks.
#
# This library centralizes the 19-case lane-id resolution logic that had
# been duplicated — and had drifted — across seven hook scripts. Before
# this file, analyst-*, flex-d, brws-author-d, and ops/review lanes were
# intermittently resolved as "unknown" depending on which hook fired,
# producing live attribution gaps in the event stream, orchestrator
# task-completion messages, scope-drift enforcement, and the #2701
# dispatched-packet PR write-back.
#
# Usage (from any hook):
#     # shellcheck disable=SC1091
#     . "${CLAUDE_PROJECT_DIR:?}/.claude/hooks/lib/resolve-lane-id.sh"
#     LANE_ID=$(resolve_lane_id)
#     [ -z "$LANE_ID" ] && LANE_ID="<caller-specific fallback if any>"
#
# Contract:
#   - Reads $CLAUDE_AGENT_NAME and $CLAUDE_PROJECT_DIR (both optional).
#   - Prints canonical lane_id to stdout; empty string if the context
#     cannot be classified.
#   - No side effects. Safe under `set -euo pipefail`.
#   - Does NOT apply caller-specific fallbacks (hostname, Bid-Euchre → main,
#     wildcard sed). Each caller owns its own fallback policy — see
#     permission-denied-log.sh and permission_denied_alert.sh for the
#     two known fallback patterns.
#
# Performance note:
#   Pure bash with a sourced function — no `uv run` cold start. This is
#   deliberate: the lane-heartbeat hook holds a 2s wall-clock budget
#   (.claude/hooks/lane-heartbeat-post-tool.sh:12-14) that a Python
#   spawn per tool call would blow.
#
# Ordering note:
#   `*steward-author-scratch)` MUST precede `*steward-author)` because
#   `*steward-author` glob would otherwise match the scratch suffix.
#   tests/unit/test_resolve_lane_id.py locks this invariant.
#
# Ref: issue #2690

resolve_lane_id() {
    local lane=""
    if [ -n "${CLAUDE_AGENT_NAME:-}" ]; then
        lane=$(printf '%s' "$CLAUDE_AGENT_NAME" | sed 's/^steward-//')
    fi
    if [ -z "$lane" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
        local dir_name
        dir_name=$(basename "$CLAUDE_PROJECT_DIR" 2>/dev/null || true)
        case "$dir_name" in
            *steward-author-scratch) lane="author-scratch" ;;
            *steward-author-b)       lane="author-b" ;;
            *steward-author-c)       lane="author-c" ;;
            *steward-author-d)       lane="author-d" ;;
            *steward-author)         lane="author-a" ;;
            *steward-brws-author-a)  lane="brws-author-a" ;;
            *steward-brws-author-b)  lane="brws-author-b" ;;
            *steward-brws-author-c)  lane="brws-author-c" ;;
            *steward-brws-author-d)  lane="brws-author-d" ;;
            *steward-analyst-b)      lane="analyst-b" ;;
            *steward-analyst-c)      lane="analyst-c" ;;
            *steward-analyst-d)      lane="analyst-d" ;;
            *steward-analyst)        lane="analyst-a" ;;
            *steward-flex-a)         lane="flex-a" ;;
            *steward-flex-b)         lane="flex-b" ;;
            *steward-flex-c)         lane="flex-c" ;;
            *steward-flex-d)         lane="flex-d" ;;
            *steward-review)         lane="review" ;;
            *steward-ops)            lane="ops" ;;
        esac
    fi
    printf '%s' "$lane"
}

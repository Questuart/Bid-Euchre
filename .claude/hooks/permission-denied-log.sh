#!/usr/bin/env bash
# permission-denied-log.sh — PermissionDenied hook: log auto-mode denials for observability.
#
# Fires when the auto-mode classifier denies a tool call (Claude Code v2.1.89+).
# Appends a JSONL record to .claude/runtime/permission_denials.jsonl.
#
# Limitations:
#   - Only fires in auto mode (Team/Enterprise plan). Does NOT fire for:
#     - Manual user denial of permission dialogs
#     - PreToolUse hook blocks (exit 2)
#     - dontAsk mode allowlist misses
#     - permissions.deny rule matches
#   - Useful as forward-looking observability for when the fleet adopts auto mode.
#
# Design:
#   - Never crashes — all operations wrapped in defensive guards
#   - Never blocks — always exits 0, returns retry: false
#   - Lightweight — uses only bash builtins + jq (no Python, no uv)
#
# Closes #2256.
set -euo pipefail

# Read PermissionDenied JSON payload from stdin
INPUT=$(cat)

# Extract fields (defensive: default to empty string on parse failure)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
REASON=$(echo "$INPUT" | jq -r '.reason // "no reason provided"' 2>/dev/null || echo "no reason provided")
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null || echo '{}')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown")

# Derive lane name — prefer CLAUDE_AGENT_NAME, fall back to project dir parsing.
# Use canonical lane IDs (e.g. "author-a" not "author") matching post-merge-notify.sh.
LANE="unknown"
if [ -n "${CLAUDE_AGENT_NAME:-}" ]; then
    LANE=$(echo "$CLAUDE_AGENT_NAME" | sed 's/^steward-//')
elif [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR")
    case "$DIR_NAME" in
        *steward-author-scratch) LANE="author-scratch" ;;
        *steward-author-b)       LANE="author-b" ;;
        *steward-author-c)       LANE="author-c" ;;
        *steward-author-d)       LANE="author-d" ;;
        *steward-author)         LANE="author-a" ;;
        *steward-brws-author-a)  LANE="brws-author-a" ;;
        *steward-brws-author-b)  LANE="brws-author-b" ;;
        *steward-brws-author-c)  LANE="brws-author-c" ;;
        *steward-brws-author-d)  LANE="brws-author-d" ;;
        *steward-analyst-b)      LANE="analyst-b" ;;
        *steward-analyst-c)      LANE="analyst-c" ;;
        *steward-analyst-d)      LANE="analyst-d" ;;
        *steward-analyst)        LANE="analyst-a" ;;
        *steward-flex-a)         LANE="flex-a" ;;
        *steward-flex-b)         LANE="flex-b" ;;
        *steward-flex-c)         LANE="flex-c" ;;
        *steward-flex-d)         LANE="flex-d" ;;
        *steward-review)         LANE="review" ;;
        *steward-ops)            LANE="ops" ;;
        Bid-Euchre)              LANE="main" ;;
        *)                       LANE=$(echo "$DIR_NAME" | sed 's/^Bid-Euchre-steward-//' | sed 's/^Bid-Euchre/main/') ;;
    esac
fi

# Ensure runtime directory exists
RUNTIME_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/runtime"
mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

# Construct JSONL record
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "unknown")
RECORD=$(jq -nc \
    --arg ts "$TIMESTAMP" \
    --arg lane "$LANE" \
    --arg tool "$TOOL_NAME" \
    --arg reason "$REASON" \
    --arg session "$SESSION_ID" \
    --argjson tool_input "$TOOL_INPUT" \
    '{timestamp: $ts, lane: $lane, tool_name: $tool, reason: $reason, session_id: $session, tool_input: $tool_input}' \
    2>/dev/null || echo "{\"timestamp\":\"$TIMESTAMP\",\"lane\":\"$LANE\",\"tool_name\":\"$TOOL_NAME\",\"reason\":\"$REASON\"}")

# Append to JSONL log (best-effort)
echo "$RECORD" >> "$RUNTIME_DIR/permission_denials.jsonl" 2>/dev/null || true

# Return hook response: do not retry (let denial stand for safety)
echo '{"hookSpecificOutput": {"hookEventName": "PermissionDenied", "retry": false}}'

exit 0

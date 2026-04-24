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

# Derive lane name via the canonical helper (#2690), then apply the
# hook-specific "Bid-Euchre → main" / wildcard fallback. The unknown
# default preserves the old behavior when the project dir is missing.
LANE="unknown"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && \
   [ -r "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh" ]; then
    # shellcheck disable=SC1091
    . "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh"
    RESOLVED=$(resolve_lane_id)
    if [ -n "$RESOLVED" ]; then
        LANE="$RESOLVED"
    elif [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
        DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR")
        case "$DIR_NAME" in
            Bid-Euchre) LANE="main" ;;
            *)          LANE=$(echo "$DIR_NAME" | sed 's/^Bid-Euchre-steward-//' | sed 's/^Bid-Euchre/main/') ;;
        esac
    fi
fi

# Ensure runtime directory exists
RUNTIME_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/runtime"
mkdir -p "$RUNTIME_DIR" 2>/dev/null || true

# B.6 enrichment — look up approval classes from the tool risk registry.
# The registry is a dual-envelope classification table at
# .claude/rules/tool_risk_registry.md (per Primitive B.6; shaping §5.4).
# Enrichment fields: approval_class_auto_mode, approval_class_bypass,
# registry_row_id. All three default to null when no row matches, which
# drives the check-tool-risk TR4 triage item in §5.2 item 4.
REGISTRY_PATH="${CLAUDE_PROJECT_DIR:-.}/.claude/rules/tool_risk_registry.md"
APPROVAL_AUTO="null"
APPROVAL_BYPASS="null"
REGISTRY_ROW_ID="null"
if [ -r "$REGISTRY_PATH" ]; then
    # Grep the first table row whose `Tool` column contains the tool_name
    # as a substring (backticked-form matches the rows the registry uses).
    # awk splits on `|` and strips surrounding whitespace; we trust the
    # first whitespace-delimited token of each envelope cell as the class.
    MATCH=$(awk -F'|' -v tool="$TOOL_NAME" '
        /^\|/ && !seen && index($2, tool) {
            gsub(/^[ \t]+|[ \t]+$/, "", $3)
            gsub(/^[ \t]+|[ \t]+$/, "", $4)
            auto_cls = tolower($3); sub(/[^a-z].*$/, "", auto_cls)
            bypass_cls = tolower($4); sub(/[^a-z].*$/, "", bypass_cls)
            if (auto_cls == "direct" || auto_cls == "approve" || auto_cls == "edit" || auto_cls == "reject") {
                print NR "|" auto_cls "|" bypass_cls
                seen = 1
            }
        }' "$REGISTRY_PATH" 2>/dev/null || echo "")
    if [ -n "$MATCH" ]; then
        ROW_LINE="${MATCH%%|*}"
        REST="${MATCH#*|}"
        APPROVAL_AUTO="\"${REST%%|*}\""
        APPROVAL_BYPASS="\"${REST##*|}\""
        REGISTRY_ROW_ID="\".claude/rules/tool_risk_registry.md:${ROW_LINE}\""
    fi
fi

# Construct JSONL record
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo "unknown")
RECORD=$(jq -nc \
    --arg ts "$TIMESTAMP" \
    --arg lane "$LANE" \
    --arg tool "$TOOL_NAME" \
    --arg reason "$REASON" \
    --arg session "$SESSION_ID" \
    --argjson tool_input "$TOOL_INPUT" \
    --argjson approval_auto "$APPROVAL_AUTO" \
    --argjson approval_bypass "$APPROVAL_BYPASS" \
    --argjson registry_row_id "$REGISTRY_ROW_ID" \
    '{timestamp: $ts, lane: $lane, tool_name: $tool, reason: $reason, session_id: $session, tool_input: $tool_input, approval_class_auto_mode: $approval_auto, approval_class_bypass: $approval_bypass, registry_row_id: $registry_row_id}' \
    2>/dev/null || echo "{\"timestamp\":\"$TIMESTAMP\",\"lane\":\"$LANE\",\"tool_name\":\"$TOOL_NAME\",\"reason\":\"$REASON\"}")

# Append to JSONL log (best-effort)
echo "$RECORD" >> "$RUNTIME_DIR/permission_denials.jsonl" 2>/dev/null || true

# Return hook response: do not retry (let denial stand for safety)
echo '{"hookSpecificOutput": {"hookEventName": "PermissionDenied", "retry": false}}'

exit 0

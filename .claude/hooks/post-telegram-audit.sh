#!/usr/bin/env bash
# post-telegram-audit.sh — PostToolUse hook: audit outbound Telegram MCP tool calls.
#
# Wires audit_mcp_outbound() into the live PostToolUse path for Telegram tools.
# When any Telegram MCP tool (reply, react, edit_message) is invoked, this hook
# appends an audit record to .claude/runtime/audit_trail/remote_exchanges.jsonl.
#
# Design:
#   - Best-effort: audit failure never blocks the tool response
#   - Lightweight guard: exits immediately for non-Telegram tools
#   - Uses env vars (not shell args) to avoid injection from tool args
#   - Same uv-run-python pattern as post-pr-review.sh
#
# Closes #1685 (runtime wiring for Platform-8b audit trail)
set -euo pipefail

# Read PostToolUse JSON payload from stdin
INPUT=$(cat)

# Lane guard: only the orchestrator should audit Telegram tool calls.
# Other lanes should not call Telegram tools, but if they do (due to
# competing plugin instances — #1824), skip auditing.
if [ "${STEWARD_TELEGRAM_RECEIVER:-}" = "0" ]; then
    exit 0
fi
if [ "${STEWARD_TELEGRAM_RECEIVER:-}" != "1" ]; then
    _BASENAME=$(basename "${CLAUDE_PROJECT_DIR:-}")
    if [ "$_BASENAME" != "Bid-Euchre" ]; then
        exit 0
    fi
fi

# Extract tool name
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")

# Guard: only audit known Telegram outbound tools
case "$TOOL_NAME" in
    mcp__plugin_telegram_telegram__reply|\
    mcp__plugin_telegram_telegram__react|\
    mcp__plugin_telegram_telegram__edit_message|\
    mcp__plugin_telegram_telegram__download_attachment)
        ;;
    *)
        exit 0
        ;;
esac

# Extract tool arguments as JSON string
TOOL_ARGS=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null || echo '{}')

# Best-effort audit: call audit_mcp_outbound() via Python.
# Failures are silently swallowed — auditing must not block the agent.
AUDIT_TOOL_NAME="$TOOL_NAME" AUDIT_TOOL_ARGS="$TOOL_ARGS" \
  uv run python -c "
import os, json, sys
from bid_euchre.ops.audit_trail import audit_mcp_outbound
tool_name = os.environ['AUDIT_TOOL_NAME']
tool_args = json.loads(os.environ['AUDIT_TOOL_ARGS'])
record = audit_mcp_outbound(tool_name, tool_args)
if record:
    print(f'audit: {record.exchange_type} -> {record.exchange_id}', file=sys.stderr)
" 2>/dev/null || true

# Suppress TUI notification — audit is silent background work
echo '{"suppressOutput": true}'

exit 0

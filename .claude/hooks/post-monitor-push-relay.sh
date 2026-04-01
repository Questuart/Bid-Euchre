#!/usr/bin/env bash
# PostToolUse sub-hook: Detect push relay output from ops.py monitor and
# inject additionalContext so the orchestrator delivers alerts to Telegram.
#
# Called by post-bash-dispatch.sh (the consolidated PostToolUse dispatcher).
# Reads PostToolUse JSON from stdin. If the Bash command's stdout contains
# a PUSH_RELAY: marker line, extracts the chat_id and message, then emits
# hookSpecificOutput with additionalContext containing delivery instructions.
#
# When no PUSH_RELAY: marker is present, exits silently (no output).
#
# Timeout: 5s (must be fast — runs on every Bash tool completion)

set -euo pipefail

# Read PostToolUse JSON payload from stdin
INPUT=$(cat)

# Fast guard: only process successful ops.py monitor commands
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0' 2>/dev/null || echo "0")

# Monitor exits non-zero when HIGH findings exist — that's normal.
# But we still need stdout to contain push relay data, so don't filter on exit code.

# Fast path: skip commands that can't be monitor
case "$COMMAND" in
    *ops.py*monitor*|*ops*monitor*) ;;
    *) exit 0 ;;
esac

# Extract stdout and look for PUSH_RELAY: marker
STDOUT=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' 2>/dev/null || echo "")

# Find the PUSH_RELAY: line
RELAY_LINE=$(echo "$STDOUT" | grep -m1 '^PUSH_RELAY:' || true)

if [ -z "$RELAY_LINE" ]; then
    # No push relay payload — exit silently
    exit 0
fi

# Strip the PUSH_RELAY: prefix to get raw JSON
RELAY_JSON="${RELAY_LINE#PUSH_RELAY:}"

# Parse chat_id and message from the JSON payload
CHAT_ID=$(echo "$RELAY_JSON" | jq -r '.chat_id // empty' 2>/dev/null || true)
MESSAGE=$(echo "$RELAY_JSON" | jq -r '.message // empty' 2>/dev/null || true)

if [ -z "$CHAT_ID" ] || [ -z "$MESSAGE" ]; then
    # Malformed relay payload — exit silently rather than injecting bad context
    exit 0
fi

# Build the additionalContext delivery instruction.
# Use a prominent format that the orchestrator can't miss in conversation context.
# Truncate message to Telegram's 4096-char limit to avoid oversized context injection.
TRUNCATED_MESSAGE="${MESSAGE:0:4096}"

CONTEXT="TELEGRAM ALERT PUSH (chat_id=${CHAT_ID}):
${TRUNCATED_MESSAGE}
→ DELIVER NOW: Call mcp__plugin_telegram_telegram__reply(chat_id=\"${CHAT_ID}\", text=\"<the above message>\")
→ If you already delivered this alert based on stdout, skip this instruction."

# Emit hookSpecificOutput with additionalContext
echo "$CONTEXT" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: .}}'

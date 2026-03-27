#!/usr/bin/env bash
# inbound-channel-audit.sh — UserPromptSubmit hook: audit inbound <channel> tags.
#
# Wires audit_channel_tag() into the live UserPromptSubmit path for inbound
# Telegram messages.  When a prompt contains a <channel source="telegram" ...>
# tag (injected by the Telegram plugin), this hook appends an inbound audit
# record to .claude/runtime/audit_trail/remote_exchanges.jsonl.
#
# Design:
#   - Best-effort: audit failure never blocks prompt submission
#   - Fast guard: exits immediately (~0ms) when no <channel tag in prompt
#   - Delegates to inbound-channel-audit.py for tag parsing + audit_channel_tag()
#
# Closes #1752.
set -euo pipefail

# Read UserPromptSubmit JSON from stdin
INPUT=$(cat)

# Fast guard: skip entirely if no <channel tag present in the prompt.
# This is the common case — most prompts have no Telegram messages.
echo "$INPUT" | grep -q '<channel' || exit 0

# Lane guard: only the orchestrator should process inbound Telegram messages.
# Other lanes may receive messages due to competing plugin instances (#1824).
# Check the explicit env var first (fastest), then fall back to dir detection.
if [ "${STEWARD_TELEGRAM_RECEIVER:-}" = "0" ]; then
    exit 0
fi
if [ "${STEWARD_TELEGRAM_RECEIVER:-}" != "1" ]; then
    # No explicit env var — check project dir basename.
    _BASENAME=$(basename "${CLAUDE_PROJECT_DIR:-}")
    if [ "$_BASENAME" != "Bid-Euchre" ]; then
        exit 0
    fi
fi

# Audit inbound channel tags.  Best-effort: failures are silently swallowed.
echo "$INPUT" | uv run python "$CLAUDE_PROJECT_DIR/.claude/hooks/inbound-channel-audit.py" 2>/dev/null || true

exit 0

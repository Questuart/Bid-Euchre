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

# Audit inbound channel tags.  Best-effort: failures are silently swallowed.
echo "$INPUT" | uv run python "$CLAUDE_PROJECT_DIR/.claude/hooks/inbound-channel-audit.py" 2>/dev/null || true

exit 0

#!/usr/bin/env bash
# inbox-completion-inject.sh — UserPromptSubmit hook: surface unacked
# completion messages from the orchestrator inbox.
#
# When author/analyst lanes complete tasks, they send completion messages
# to the orchestrator's inbox.  This hook checks for unacked completions
# and injects them as additionalContext so the orchestrator sees them
# immediately — no polling needed.
#
# Design:
#   - Best-effort: failures never block prompt submission
#   - Fast guard: exits immediately (~0ms) when no inbox file or no completions
#   - Delegates to inbox-completion-inject.py for inbox reading + ack
#   - Only fires on the orchestrator lane (lane guard)
#
# Closes #1986.
set -euo pipefail

# Lane guard: only the orchestrator needs completion injection.
# Check the explicit env var first (fastest), then fall back to dir detection.
_LANE="${CLAUDE_AGENT_NAME:-}"
if [ -z "$_LANE" ]; then
    _LANE=$(basename "${CLAUDE_PROJECT_DIR:-}")
fi

# The orchestrator lane lives in the "Bid-Euchre" directory (the main checkout).
case "$_LANE" in
    orchestrator|Bid-Euchre) ;;
    *) exit 0 ;;
esac

# Fast guard: check if the orchestrator inbox file exists and contains any
# "completion" messages in a deliverable state.  This avoids Python startup
# (~200ms) on every prompt when no completions are pending.
_BUS_ROOT="${BID_EUCHRE_BUS_DIR:-}"
if [ -z "$_BUS_ROOT" ]; then
    _BUS_ROOT=$(git -C "${CLAUDE_PROJECT_DIR:-.}" rev-parse --git-common-dir 2>/dev/null)/message_bus
fi

_INBOX_FILE="$_BUS_ROOT/inboxes/orchestrator.jsonl"
if [ ! -f "$_INBOX_FILE" ]; then
    exit 0
fi

# Quick grep: does the inbox contain any completion messages that aren't resolved/expired?
# This is a heuristic — the Python script does the accurate filtering.
grep -q '"completion"' "$_INBOX_FILE" || exit 0

# Delegate to Python for accurate inbox reading, formatting, and auto-ack.
# Best-effort: failures are silently swallowed.
uv run python "$CLAUDE_PROJECT_DIR/.claude/hooks/inbox-completion-inject.py" 2>/dev/null || true

exit 0

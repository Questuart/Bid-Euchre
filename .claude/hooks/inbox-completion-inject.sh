#!/usr/bin/env bash
# inbox-completion-inject.sh — UserPromptSubmit hook: surface unacked
# high-priority inbox messages from the orchestrator inbox.
#
# When author/analyst lanes signal orchestrator-actionable state, they send
# messages (completion, blocker, escalation, high/urgent supervisor_alert)
# to the orchestrator's inbox.  This hook checks for unacked instances of
# those types and injects them as additionalContext so the orchestrator
# sees them on every prompt boundary — no polling needed.
#
# Only `completion` messages are auto-acked after surfacing.  Blockers,
# escalations, and high/urgent alerts are surfaced ONLY and remain in the
# inbox until explicitly handled — auto-acking them would silently drop
# real action items.  See inbox-completion-inject.py for the full policy.
#
# Design:
#   - Best-effort: failures never block prompt submission
#   - Fast guard: exits immediately (~0ms) when no inbox file or no matching
#     message types are present
#   - Delegates to inbox-completion-inject.py for accurate filtering,
#     priority checks, and conditional ack
#   - Only fires on the orchestrator lane (lane guard)
#
# Closes #1986.  Broadened by PR-MSG-3 (messaging revamp execution plan).
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

# Quick grep: does the inbox contain any message type we care about?
# This is a heuristic — the Python script does the accurate filtering
# (including the priority check for supervisor_alert).
grep -qE '"(completion|blocker|escalation|supervisor_alert)"' "$_INBOX_FILE" || exit 0

# Delegate to Python for accurate inbox reading, formatting, and auto-ack.
# Best-effort: failures are silently swallowed.
uv run python "$CLAUDE_PROJECT_DIR/.claude/hooks/inbox-completion-inject.py" 2>/dev/null || true

exit 0

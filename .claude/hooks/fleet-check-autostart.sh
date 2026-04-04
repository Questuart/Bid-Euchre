#!/usr/bin/env bash
# SessionStart hook: auto-start fleet-check cron on orchestrator boot.
#
# Fires on all session starts (init, clear, compact).  When the current lane
# is the orchestrator, outputs a directive that the agent processes to create
# (or verify) the fleet-check durable cron.
#
# Must NEVER exit non-zero — a failing SessionStart hook leaves the session
# at a blank prompt with 0 tokens and no context.
#
# Refs #2333.

trap 'exit 0' ERR

# --------------------------------------------------------------------------
# Guard: only act on the orchestrator lane
# --------------------------------------------------------------------------
# CLAUDE_AGENT_NAME is set by the --name flag (e.g., "orchestrator").
# We require an explicit agent name — do not fall back to directory-based
# detection, because ad-hoc sessions in the main checkout are not the
# orchestrator.  Refs #2375.
AGENT_NAME="${CLAUDE_AGENT_NAME:-}"

# Only the orchestrator needs fleet-check
if [[ "$AGENT_NAME" != "orchestrator" ]]; then
    exit 0
fi

# --------------------------------------------------------------------------
# Guard: skip autostart after an intentional park
# --------------------------------------------------------------------------
# The /park skill (or park_worker()) can drop this marker to suppress
# fleet-check autostart on the next session start.  Remove the marker
# manually or via /fleet-check to re-enable autostart.  Refs #2375.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
INHIBIT_FILE="$PROJECT_DIR/.claude/runtime/fleet-check-inhibit"

if [[ -f "$INHIBIT_FILE" ]]; then
    exit 0
fi

# --------------------------------------------------------------------------
# Emit directive for the orchestrator agent (JSON additionalContext format)
# --------------------------------------------------------------------------
# The Claude Code hook framework requires JSON output with an additionalContext
# field.  Plain text is logged as "OK" and never reaches the agent.  Refs #2333.
python3 -c "
import json, sys
msg = (
    'FLEET-CHECK AUTO-START: The orchestrator fleet-check cron must be running.\n'
    '\n'
    'Action required:\n'
    '1. Run CronList to check for an existing fleet-check cron\n'
    '2. If a fleet-check cron already exists, no action needed\n'
    '3. If no fleet-check cron exists, run: /loop 8m /fleet-check\n'
    '\n'
    'This ensures periodic inbox polling, CPU checks, task completion detection,\n'
    'and lane health monitoring continue after /clear or session restart.'
)
json.dump({'additionalContext': msg}, sys.stdout)
"

exit 0

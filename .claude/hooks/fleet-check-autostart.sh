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
AGENT_NAME="${CLAUDE_AGENT_NAME:-}"

if [[ -z "$AGENT_NAME" ]]; then
    # Fallback: detect from project directory name
    PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
    DIR_NAME="$(basename "$PROJECT_DIR")"
    # The main checkout (Bid-Euchre) is where the orchestrator runs
    if [[ "$DIR_NAME" == "Bid-Euchre" ]]; then
        AGENT_NAME="orchestrator"
    fi
fi

# Only the orchestrator needs fleet-check
if [[ "$AGENT_NAME" != "orchestrator" ]]; then
    exit 0
fi

# --------------------------------------------------------------------------
# Emit directive for the orchestrator agent
# --------------------------------------------------------------------------
cat <<'DIRECTIVE'
FLEET-CHECK AUTO-START: The orchestrator fleet-check cron must be running.

Action required:
1. Run CronList to check for an existing fleet-check cron
2. If a fleet-check cron already exists, no action needed
3. If no fleet-check cron exists, run: /loop 8m /fleet-check

This ensures periodic inbox polling, CPU checks, task completion detection,
and lane health monitoring continue after /clear or session restart.
DIRECTIVE

exit 0

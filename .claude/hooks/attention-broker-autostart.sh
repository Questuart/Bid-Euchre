#!/usr/bin/env bash
# SessionStart hook: launch the attention-broker daemon (PR-MSG-4).
#
# The broker tails .claude/runtime/events/events.jsonl and nudges
# message recipients only when their pane looks safe to poke.  It is
# pidfile-guarded, so repeated session starts across lanes spawn at
# most one live broker per repo.
#
# Fires on all session starts (init, clear, compact).  Must NEVER exit
# non-zero — a failing SessionStart hook leaves the session at a blank
# prompt with 0 tokens and no context.
#
# Behavior:
#   - If another live broker is already running, exit 0 silently.
#   - If no broker is alive, spawn one in the background via nohup.
#   - Never block the session start on daemon output; all logs go to
#     .claude/runtime/attention_broker/daemon.log.
#
# Refs PR-MSG-4 plan: plans/sessions/2026-04-20_messaging-revamp-execution-plan.md

trap 'exit 0' ERR

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if [[ -z "$PROJECT_DIR" || ! -d "$PROJECT_DIR" ]]; then
    exit 0
fi

RUNTIME_DIR="$PROJECT_DIR/.claude/runtime"
BROKER_DIR="$RUNTIME_DIR/attention_broker"
PIDFILE="$BROKER_DIR/pid"
LOG_FILE="$BROKER_DIR/daemon.log"

# --------------------------------------------------------------------------
# Opt-out guard: presence of the inhibit marker suppresses autostart.
# --------------------------------------------------------------------------
INHIBIT_FILE="$BROKER_DIR/disabled"
if [[ -f "$INHIBIT_FILE" ]]; then
    exit 0
fi

# --------------------------------------------------------------------------
# Single-instance check.  The broker itself enforces this via pidfile,
# but we short-circuit here to avoid a brief window of overlapping
# processes and to keep session starts fast.
# --------------------------------------------------------------------------
if [[ -f "$PIDFILE" ]]; then
    EXISTING_PID="$(cat "$PIDFILE" 2>/dev/null | tr -d '[:space:]')"
    if [[ -n "$EXISTING_PID" ]] && kill -0 "$EXISTING_PID" 2>/dev/null; then
        # Live broker already running; nothing to do.
        exit 0
    fi
fi

# --------------------------------------------------------------------------
# Locate `uv` and launch the broker in the background.
# --------------------------------------------------------------------------
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "$UV_BIN" ]]; then
    # No uv on PATH — best-effort only; leave a hint and exit cleanly.
    mkdir -p "$BROKER_DIR" 2>/dev/null || true
    echo "attention-broker autostart skipped: uv not on PATH ($(date -u))" \
        >> "$LOG_FILE" 2>/dev/null || true
    exit 0
fi

mkdir -p "$BROKER_DIR" 2>/dev/null || true

# Launch detached.  The broker writes its own pidfile on startup; if
# another instance wins the race (e.g. two sessions booted at once),
# the loser will see acquire_pidfile() return False and exit 0.
(
    cd "$PROJECT_DIR" || exit 0
    nohup "$UV_BIN" run python scripts/internal/ops.py attention run \
        --interval 3 \
        >> "$LOG_FILE" 2>&1 &
) &

exit 0

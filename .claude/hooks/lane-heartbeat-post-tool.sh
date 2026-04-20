#!/usr/bin/env bash
# PostToolUse hook: emit a lane-heartbeat snapshot after every tool call.
#
# Part of issue #2415 / PR 1 of 3 (writer-only).  The heartbeat file at
# .claude/runtime/lane_status/<lane_id>.json records when this lane last
# completed a tool call; future PRs will use it to fix the F1 dashboard
# failure mode where actively running lanes are mislabeled as [stale!].
#
# Invariants:
#   1. ALWAYS exits 0.  A failed heartbeat must never block a tool call
#      or cause the hook to be unregistered.
#   2. Bounded wall-clock time.  The heartbeat write runs under a 2s
#      `timeout` so a pathologically slow Python start never stalls the
#      tool-call pipeline.
#   3. No consumer is wired up yet — this file is strictly additive.
#
# Lane resolution matches post-merge-notify.sh so the writer emits the
# same lane_id that the rest of the steward fleet uses.
#
# The tool_name is read from the PostToolUse JSON payload on stdin (the
# standard mechanism; there is no CLAUDE_TOOL_NAME env var).

# Strict mode inside the hook body; we override the exit behavior at the
# end so a mid-script failure still yields exit 0 to the harness.
set -uo pipefail

# Read the PostToolUse payload once.  jq is available in the fleet
# toolchain; if it is somehow missing we fall back to an empty tool name
# rather than failing.
INPUT=$(cat 2>/dev/null || true)
TOOL_NAME=""
if command -v jq >/dev/null 2>&1; then
    TOOL_NAME=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
fi

# Resolve lane_id (mirrors post-merge-notify.sh).
LANE_ID=""
if [ -n "${CLAUDE_AGENT_NAME:-}" ]; then
    LANE_ID=$(printf '%s' "$CLAUDE_AGENT_NAME" | sed 's/^steward-//')
fi
if [ -z "$LANE_ID" ] && [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
    DIR_NAME=$(basename "$CLAUDE_PROJECT_DIR")
    case "$DIR_NAME" in
        *steward-author-scratch) LANE_ID="author-scratch" ;;
        *steward-author-b)       LANE_ID="author-b" ;;
        *steward-author-c)       LANE_ID="author-c" ;;
        *steward-author-d)       LANE_ID="author-d" ;;
        *steward-author)         LANE_ID="author-a" ;;
        *steward-brws-author-a)  LANE_ID="brws-author-a" ;;
        *steward-brws-author-b)  LANE_ID="brws-author-b" ;;
        *steward-brws-author-c)  LANE_ID="brws-author-c" ;;
        *steward-brws-author-d)  LANE_ID="brws-author-d" ;;
        *steward-analyst-b)      LANE_ID="analyst-b" ;;
        *steward-analyst-c)      LANE_ID="analyst-c" ;;
        *steward-analyst-d)      LANE_ID="analyst-d" ;;
        *steward-analyst)        LANE_ID="analyst-a" ;;
        *steward-flex-a)         LANE_ID="flex-a" ;;
        *steward-flex-b)         LANE_ID="flex-b" ;;
        *steward-flex-c)         LANE_ID="flex-c" ;;
        *steward-flex-d)         LANE_ID="flex-d" ;;
        *steward-review)         LANE_ID="review" ;;
        *steward-ops)            LANE_ID="ops" ;;
    esac
fi

# Without a lane_id there is no meaningful heartbeat to write.  Exit 0 so
# non-lane sessions (dev laptops, ad-hoc CLI) never fail the hook.
if [ -z "$LANE_ID" ]; then
    exit 0
fi

# Run the writer under a bounded timeout so a slow `uv run` cold start
# cannot stall the tool-call pipeline.  Failure for any reason — missing
# uv, import error, OSError on the runtime dir — is swallowed.
#
# Timeout strategy: prefer GNU ``timeout`` (Linux fleet hosts) and fall
# back to ``gtimeout`` (macOS with coreutils).  On hosts with neither we
# run unwrapped and rely on the in-Python ``signal.alarm(2)`` self-kill
# as the bound on wall-clock time.  This keeps the hook portable across
# Linux and macOS dev laptops without drifting from the 2s budget.
#
# The writer gets the tool name via an env var rather than shell
# interpolation to avoid quoting hazards if a tool name ever contains
# special characters.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if command -v timeout >/dev/null 2>&1; then
    TIMEOUT_CMD="timeout 2"
elif command -v gtimeout >/dev/null 2>&1; then
    TIMEOUT_CMD="gtimeout 2"
else
    TIMEOUT_CMD=""
fi

(
    cd "$PROJECT_DIR" 2>/dev/null || true
    LANE_ID="$LANE_ID" LAST_TOOL="$TOOL_NAME" \
        $TIMEOUT_CMD uv run --quiet python -c '
import os
import signal

# In-Python timeout as portable fallback when coreutils `timeout` is
# missing.  SIGALRM self-terminates the process so uv cold start can
# never stall the tool-call pipeline past the 2-second budget.
try:
    signal.alarm(2)
except (AttributeError, ValueError):
    # Windows or unusual runtime — skip the alarm; the outer timeout
    # wrapper is the primary defense in those environments.
    pass

from bid_euchre.ops.lane_heartbeat import write_heartbeat

tool = os.environ.get("LAST_TOOL") or None
write_heartbeat(os.environ["LANE_ID"], tool_name=tool)
' >/dev/null 2>&1 || true
) || true

exit 0

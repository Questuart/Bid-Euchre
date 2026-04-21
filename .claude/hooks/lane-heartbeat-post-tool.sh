#!/usr/bin/env bash
# PostToolUse hook: emit a lane-heartbeat snapshot after every tool call.
#
# Part of issue #2415 / PR 1 of 3 (writer-only).  The heartbeat file at
# .claude/runtime/lane_status/<lane_id>.json records when this lane last
# completed a tool call; later PRs wire it into the dashboard classifier
# so actively running lanes are not mislabeled as [stale!].
#
# PURE SHELL IMPLEMENTATION (issue #2689, PR <TBD>)
# -------------------------------------------------
# This hook was previously a ~60ms `uv run python` spawn per tool call.
# Measurement:  19 lanes × hundreds of tool calls/session × fleet-long
# operation made that startup cost a real steady-state tax.  The payload
# is a 7-field flat JSON dict, so interpreter startup was the dominant
# cost — not the ~1ms of actual work.  This rewrite emits the same JSON
# via `printf` + atomic `mv`, dropping steady-state cost to < 10ms.
#
# The canonical schema + reader lives in
# ``src/bid_euchre/ops/lane_heartbeat.py``; the Python writer there is
# retained as a test fixture generator and fallback for any non-hook
# caller that might appear.  Contract parity between this shell writer
# and the Python writer is locked by
# ``tests/unit/test_lane_heartbeat_hook.py``.
#
# Invariants (unchanged from PR 1):
#   1. ALWAYS exits 0.  A failed heartbeat must never block a tool call
#      or cause the hook to be unregistered.
#   2. Bounded wall-clock time.  The steady-state work is < 10ms; the
#      outer `timeout: 10` in .claude/settings.json bounds any pathological
#      case (e.g. a hung `jq`).
#   3. No consumer needs to change — the on-disk JSON shape matches what
#      `write_heartbeat` in lane_heartbeat.py produces.
#
# Lane resolution matches post-merge-notify.sh so the writer emits the
# same lane_id that the rest of the steward fleet uses.
#
# The tool_name is read from the PostToolUse JSON payload on stdin (the
# standard mechanism; there is no CLAUDE_TOOL_NAME env var).
#
# Runtime dir override:
#   The heartbeat directory can be overridden via
#   ``CLAUDE_HEARTBEAT_RUNTIME_DIR`` for tests.  Production hook
#   invocations never set this; they use the default
#   ``$CLAUDE_PROJECT_DIR/.claude/runtime/lane_status``.

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

# Resolve the runtime dir.  Explicit override via env wins (used by
# contract tests); otherwise default to
# $CLAUDE_PROJECT_DIR/.claude/runtime/lane_status — matching the default
# used by write_heartbeat() in lane_heartbeat.py when called from CWD =
# project root.
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
RUNTIME_DIR="${CLAUDE_HEARTBEAT_RUNTIME_DIR:-$PROJECT_DIR/.claude/runtime/lane_status}"

# Create the runtime dir.  If this fails (e.g. parent is a regular file,
# or an unwritable mount) we exit 0 — heartbeats are advisory, never
# blocking.
mkdir -p "$RUNTIME_DIR" 2>/dev/null || exit 0

# Build the JSON payload.  All numeric and schema-controlled fields are
# interpolated directly; the two free-text fields (tool name, session id)
# go through `jq -Rcn 'inputs'` so embedded quotes, backslashes, tabs,
# and unicode are encoded to valid JSON.  Fallback to `null` if jq is
# unavailable or the encoding fails — `null` is schema-compatible with
# Heartbeat.from_json which maps None to the Optional[str] fields.
SESSION_ID="${CLAUDE_SESSION_ID:-}"
if command -v jq >/dev/null 2>&1; then
    if [ -n "$TOOL_NAME" ]; then
        LAST_TOOL_JSON=$(printf '%s' "$TOOL_NAME" | jq -Rsc '.' 2>/dev/null || echo 'null')
    else
        LAST_TOOL_JSON='null'
    fi
    if [ -n "$SESSION_ID" ]; then
        SESSION_JSON=$(printf '%s' "$SESSION_ID" | jq -Rsc '.' 2>/dev/null || echo 'null')
    else
        SESSION_JSON='null'
    fi
else
    LAST_TOOL_JSON='null'
    SESSION_JSON='null'
fi

# Timestamp in ISO-8601 with Z suffix (matches _iso() in lane_heartbeat.py).
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
PID=$$

TARGET="$RUNTIME_DIR/$LANE_ID.json"
TMP="$RUNTIME_DIR/$LANE_ID.json.tmp"

# Keys sorted alphabetically to match the Python writer's
# json.dumps(..., sort_keys=True) output byte-for-byte on the shared
# fields.  If Python ever changes sort order, the schema-parity test
# will catch it.
printf '{"extras": {}, "last_tool": %s, "lane_id": "%s", "phase": null, "pid": %d, "schema_version": 1, "session_id": %s, "updated_at": "%s"}\n' \
    "$LAST_TOOL_JSON" \
    "$LANE_ID" \
    "$PID" \
    "$SESSION_JSON" \
    "$TS" \
    > "$TMP" 2>/dev/null || exit 0

# Atomic rename.  `mv -f` within a single directory is atomic on POSIX,
# matching the `os.replace` invariant in the Python writer.
mv -f "$TMP" "$TARGET" 2>/dev/null || {
    # Cleanup a stray tempfile if the rename itself failed.  We still
    # exit 0 — heartbeat writes are best-effort.
    rm -f "$TMP" 2>/dev/null
    exit 0
}

exit 0

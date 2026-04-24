#!/usr/bin/env bash
# Primitive A v1.0 — native lifecycle hook absorber.
#
# Forwards a native Claude Code lifecycle event through the
# ``bid_euchre.ops.events.emit`` dispatcher, which writes to the
# v1.0 JSONL pipeline under ``data/events/events-YYYY-MM-DD-NNN.jsonl``.
#
# Invocation:
#   event_emit.sh <event_type>
#
# Where <event_type> matches a registered v1.0 event type:
#   pre_tool_use | post_tool_use | post_tool_use_failure |
#   permission_request | permission_denied | notification |
#   user_prompt_submit | stop | stop_failure |
#   subagent_start | subagent_stop |
#   pre_compact | session_start | session_end | teammate_idle
#
# Stdin: the native hook JSON payload.
# Stderr: absorbed (never-raises contract; nothing must block the caller).
# Exit code: always 0 (hook must never fail the hosting tool call).
#
# Design notes:
#
# - This hook is fire-and-forget. If ``uv run`` is slow to warm up,
#   the cost is absorbed here once per hook fire. ``emit()`` itself is
#   non-blocking in-process (O(ms) JSONL append + lock).
# - Event payloads with enormous ``tool_response`` strings still flow
#   through; summary-tier truncation is the dispatcher's job, not this
#   script's.
# - Resolves lane_id via the canonical helper when available so events
#   carry the right lane even on hook-only dispatch paths.

set -u  # Treat unset vars as error (do NOT set -e; we swallow failures)

# Exit silently on any unhandled failure — never block the tool call.
trap 'exit 0' ERR

EVENT_TYPE="${1:-}"
if [ -z "$EVENT_TYPE" ]; then
    exit 0
fi

# Read the native hook JSON payload from stdin (may be empty for some
# hook types like SessionStart).
INPUT="$(cat || true)"

# Resolve lane_id via the canonical helper (shared with other hooks).
LANE_ID="${CLAUDE_AGENT_NAME:-unknown}"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && \
   [ -r "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh" ]; then
    # shellcheck disable=SC1091
    . "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh"
    RESOLVED="$(resolve_lane_id 2>/dev/null || true)"
    [ -n "$RESOLVED" ] && LANE_ID="$RESOLVED"
fi

# Fire the emission as a detached process so even a slow interpreter
# warmup never stalls the tool call. All output discarded; exit 0
# regardless.
INPUT="$INPUT" EVENT_TYPE="$EVENT_TYPE" LANE_ID="$LANE_ID" \
uv run --no-sync python -c "
import json
import os
import sys

try:
    from bid_euchre.ops.events import emit
except Exception:  # pragma: no cover — import guard
    sys.exit(0)

event_type = os.environ.get('EVENT_TYPE', '')
raw = os.environ.get('INPUT', '') or '{}'
try:
    payload = json.loads(raw)
except Exception:
    payload = {}

# The native Claude Code payload schema keys are mostly compatible with
# the v1.0 registry. Pass them through verbatim; dispatcher partitions
# registered slots vs. extra_fields automatically.
kwargs = {}
if isinstance(payload, dict):
    kwargs.update({k: v for k, v in payload.items() if k not in (
        'event_type',
    )})

lane_id = os.environ.get('LANE_ID')
if lane_id and 'lane_id' not in kwargs:
    kwargs['lane_id'] = lane_id

try:
    emit(event_type, **kwargs)
except Exception:
    # emit() is never-raises; this is a defensive redundancy.
    pass
" >/dev/null 2>&1 &

# Detach and exit immediately
disown 2>/dev/null || true
exit 0

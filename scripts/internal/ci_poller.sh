#!/bin/bash
# ci_poller.sh — Background CI poller with optional auto-merge.
#
# Monitors GitHub PR checks and optionally merges when all pass.
# Designed to be launched by post-push-ci-check.sh hook.
#
# Usage:
#   ci_poller.sh --pr <N> [--repo-root <path>] [--auto-merge] [--timeout <seconds>] [--interval <seconds>]
#
# State:
#   .claude/runtime/ci_polls/pr_<N>/status.json — current polling state
#   .claude/runtime/ci_polls/pr_<N>/poller.pid  — PID file for deduplication
#   .claude/runtime/ci_polls/pr_<N>/poller.log  — execution log
#
# Exit codes:
#   0 — CI passed (and merged if --auto-merge)
#   1 — CI failed or merge failed
#   2 — timeout
#   3 — setup error (no PR, can't acquire lock)
set -euo pipefail

# Defaults
PR_NUM=""
REPO_ROOT=""
AUTO_MERGE=false
TIMEOUT=900   # 15 minutes
INTERVAL=30   # 30 seconds
STARTUP_DELAY=15  # seconds to wait before first poll (allows review loop to claim PR)

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --pr) PR_NUM="$2"; shift 2 ;;
        --repo-root) REPO_ROOT="$2"; shift 2 ;;
        --auto-merge) AUTO_MERGE=true; shift ;;
        --timeout) TIMEOUT="$2"; shift 2 ;;
        --interval) INTERVAL="$2"; shift 2 ;;
        --no-delay) STARTUP_DELAY=0; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 3 ;;
    esac
done

if [ -z "$PR_NUM" ]; then
    echo "Error: --pr <N> required" >&2
    exit 3
fi

# Locate repo root
if [ -n "$REPO_ROOT" ]; then
    REPO_ROOT=$(cd "$REPO_ROOT" 2>/dev/null && pwd || echo "")
else
    REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$REPO_ROOT" ]; then
    echo "Error: not in a git repo" >&2
    exit 3
fi

cd "$REPO_ROOT"

# State directory
STATE_DIR="${REPO_ROOT}/.claude/runtime/ci_polls/pr_${PR_NUM}"
mkdir -p "$STATE_DIR"
PID_FILE="${STATE_DIR}/poller.pid"
STATUS_FILE="${STATE_DIR}/status.json"
LOG_FILE="${STATE_DIR}/poller.log"

# Redirect all output to log
exec >> "$LOG_FILE" 2>&1

# --- Helper functions ---

write_status() {
    local state="$1"
    local detail="${2:-}"
    cat > "$STATUS_FILE" <<SEOF
{
  "pr": $PR_NUM,
  "state": "$state",
  "detail": "$detail",
  "auto_merge": $AUTO_MERGE,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "pid": $$
}
SEOF
}

emit_ci_event() {
    # Emit a durable CI event to the ops event log (fire-and-forget).
    # Args: $1=event_type (ci_failure|ci_success), $2=failure_class (optional)
    local event_type="$1"
    local failure_class="${2:-}"
    local lane_id="unknown"

    # Infer lane_id from worktree directory name
    local dir_name
    dir_name=$(basename "$REPO_ROOT")
    case "$dir_name" in
        *steward-author-scratch) lane_id="author-scratch" ;;
        *steward-author-b)       lane_id="author-b" ;;
        *steward-author-c)       lane_id="author-c" ;;
        *steward-author-d)       lane_id="author-d" ;;
        *steward-author)         lane_id="author-a" ;;
        *steward-review)         lane_id="review" ;;
        *steward-ops)            lane_id="ops" ;;
    esac

    EVENT_TYPE="$event_type" LANE_ID="$lane_id" PR_NUM_ENV="$PR_NUM" \
    FAILURE_CLASS="$failure_class" \
    uv run python -c "
import os, json
from bid_euchre.ops.events import append_event
payload = {'pr_number': int(os.environ['PR_NUM_ENV'])}
fc = os.environ.get('FAILURE_CLASS', '')
if fc:
    payload['failure_class'] = fc
append_event(
    os.environ['EVENT_TYPE'],
    'ci_poller',
    os.environ['LANE_ID'],
    payload,
)
" 2>/dev/null || true
}

cleanup() {
    rm -f "$PID_FILE"
}
trap cleanup EXIT

review_loop_active() {
    local review_state_file="${REPO_ROOT}/.claude/runtime/review_loops/pr_${PR_NUM}/state.json"
    if [ -f "$review_state_file" ]; then
        local loop_state
        loop_state=$(jq -r '.state // "unknown"' "$review_state_file" 2>/dev/null || echo "unknown")
        # Active states from review_state.py ReviewState enum (lowercase snake_case)
        case "$loop_state" in
            initialized|authoring|pr_open|waiting_for_ci|waiting_for_codex|scoring_findings|applying_fixes|retesting|ready_to_merge)
                return 0  # active
                ;;
        esac
    fi
    return 1  # not active
}

# --- PID file lock ---

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "[$(date -u +%H:%M:%S)] Another poller (PID $OLD_PID) already running for PR #${PR_NUM}. Exiting."
        exit 0
    fi
    echo "[$(date -u +%H:%M:%S)] Stale PID file (PID $OLD_PID). Taking over."
    rm -f "$PID_FILE"
fi

echo "$$" > "$PID_FILE"

# --- Startup delay: let review loop claim PR if it's also starting ---

if [ "$STARTUP_DELAY" -gt 0 ]; then
    echo "[$(date -u +%H:%M:%S)] Waiting ${STARTUP_DELAY}s for review loop to claim PR..."
    sleep "$STARTUP_DELAY"

    if review_loop_active; then
        echo "[$(date -u +%H:%M:%S)] Review loop is active. Deferring to review loop."
        write_status "deferred" "Review loop is actively managing this PR"
        exit 0
    fi
fi

echo "[$(date -u +%H:%M:%S)] Starting CI poll for PR #${PR_NUM} (timeout=${TIMEOUT}s, interval=${INTERVAL}s, auto_merge=${AUTO_MERGE})"
write_status "polling" "CI checks in progress"

# --- Polling loop ---

START_TIME=$(date +%s)
POLL_COUNT=0

while true; do
    ELAPSED=$(( $(date +%s) - START_TIME ))
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "[$(date -u +%H:%M:%S)] Timeout after ${ELAPSED}s."
        write_status "timeout" "CI still pending after ${TIMEOUT}s"
        emit_ci_event "ci_timeout" "timeout"
        echo "CI_TIMEOUT: CI still pending after ${TIMEOUT}s" > "$STATE_DIR/FAILED"
        exit 2
    fi

    # Re-check for review loop and PR state every 5 polls (rate-limited
    # to avoid doubling API calls on every iteration).
    POLL_COUNT=$((POLL_COUNT + 1))
    if [ $((POLL_COUNT % 5)) -eq 0 ]; then
        # Check if PR has been merged or closed — stop polling if so (#862)
        PR_STATE=$(gh pr view "$PR_NUM" --json state --jq '.state' 2>/dev/null || echo "")
        if [ "$PR_STATE" = "MERGED" ] || [ "$PR_STATE" = "CLOSED" ]; then
            echo "[$(date -u +%H:%M:%S)] PR #${PR_NUM} is ${PR_STATE}. Exiting."
            write_status "completed" "PR ${PR_STATE} — polling no longer needed"
            exit 0
        fi
    fi

    if [ $((POLL_COUNT % 5)) -eq 0 ] && review_loop_active; then
        echo "[$(date -u +%H:%M:%S)] Review loop became active. Deferring."
        write_status "deferred" "Review loop took over"
        exit 0
    fi

    # Get check states
    CHECK_OUTPUT=$(gh pr checks "$PR_NUM" --json name,state 2>/dev/null || echo "")

    if [ -z "$CHECK_OUTPUT" ] || [ "$CHECK_OUTPUT" = "[]" ]; then
        echo "[$(date -u +%H:%M:%S)] No checks found yet. Waiting..."
        sleep "$INTERVAL"
        continue
    fi

    FAILED=$(echo "$CHECK_OUTPUT" | jq '[.[] | select(.state == "FAILURE")] | length' 2>/dev/null || echo "0")
    # Count both PENDING and IN_PROGRESS as "not yet complete" (matches github_pr_state.py)
    NOT_COMPLETE=$(echo "$CHECK_OUTPUT" | jq '[.[] | select(.state == "PENDING" or .state == "IN_PROGRESS")] | length' 2>/dev/null || echo "0")
    SUCCEEDED=$(echo "$CHECK_OUTPUT" | jq '[.[] | select(.state == "SUCCESS")] | length' 2>/dev/null || echo "0")
    TOTAL=$(echo "$CHECK_OUTPUT" | jq 'length' 2>/dev/null || echo "0")

    echo "[$(date -u +%H:%M:%S)] [${ELAPSED}s] Checks: ${SUCCEEDED}/${TOTAL} succeeded, ${NOT_COMPLETE} in progress, ${FAILED} failed"

    # --- CI FAILED ---
    if [ "$FAILED" -gt 0 ]; then
        FAILED_NAMES=$(echo "$CHECK_OUTPUT" | jq -r '[.[] | select(.state == "FAILURE") | .name] | join(", ")' 2>/dev/null || echo "unknown")
        echo "[$(date -u +%H:%M:%S)] CI FAILED: $FAILED_NAMES"
        write_status "failed" "Failed checks: $FAILED_NAMES"
        emit_ci_event "ci_failure" "$FAILED_NAMES"
        echo "CI_FAILED: Failed checks: $FAILED_NAMES" > "$STATE_DIR/FAILED"
        exit 1
    fi

    # --- ALL PASSED (matches github_pr_state.py: all(s == "SUCCESS")) ---
    if [ "$SUCCEEDED" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
        echo "[$(date -u +%H:%M:%S)] All ${TOTAL} checks passed!"
        emit_ci_event "ci_success"

        if [ "$AUTO_MERGE" = true ]; then
            echo "[$(date -u +%H:%M:%S)] Attempting squash merge..."

            MERGE_OUTPUT=$(gh pr merge "$PR_NUM" --squash 2>&1) && MERGE_RC=0 || MERGE_RC=$?

            if [ "$MERGE_RC" -eq 0 ]; then
                echo "[$(date -u +%H:%M:%S)] PR #${PR_NUM} merged successfully."
                write_status "merged" "All checks passed, PR merged via squash"
                exit 0
            fi

            echo "[$(date -u +%H:%M:%S)] Direct merge failed (rc=$MERGE_RC): $MERGE_OUTPUT"
            echo "[$(date -u +%H:%M:%S)] Trying auto-merge (queued)..."

            AUTO_OUTPUT=$(gh pr merge "$PR_NUM" --auto --squash 2>&1) && AUTO_RC=0 || AUTO_RC=$?

            if [ "$AUTO_RC" -eq 0 ]; then
                echo "[$(date -u +%H:%M:%S)] Auto-merge queued for PR #${PR_NUM}."
                write_status "auto_merge_queued" "All checks passed, auto-merge queued"
                exit 0
            fi

            echo "[$(date -u +%H:%M:%S)] Auto-merge also failed (rc=$AUTO_RC): $AUTO_OUTPUT"
            write_status "merge_failed" "All checks passed but merge failed — manual merge required"
            echo "MERGE_FAILED: All checks passed but merge failed — manual merge required" > "$STATE_DIR/FAILED"
            exit 1
        else
            write_status "passed" "All checks passed"
            exit 0
        fi
    fi

    sleep "$INTERVAL"
done

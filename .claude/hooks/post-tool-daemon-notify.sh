#!/bin/bash
# PostToolUse hook — notifies agents of background daemon failures.
#
# Checks .claude/runtime/{ci_polls,review_loops}/pr_*/FAILED sentinel files.
# When found, injects failure context into the agent's tool response and
# renames the sentinel to NOTIFIED to prevent repeated alerts.
#
# Lightweight: only reads local files, no network calls.
set -euo pipefail

# Locate repo root via CLAUDE_PROJECT_DIR or git
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_DIR" ]; then
    exit 0
fi

RUNTIME_DIR="${PROJECT_DIR}/.claude/runtime"

if [ ! -d "$RUNTIME_DIR" ]; then
    exit 0
fi

# Collect all FAILED sentinels
MESSAGES=""

for sentinel in "$RUNTIME_DIR"/ci_polls/pr_*/FAILED "$RUNTIME_DIR"/review_loops/pr_*/FAILED; do
    # Skip unmatched globs
    [ -f "$sentinel" ] || continue

    # Extract daemon type and PR number from path
    # e.g., .claude/runtime/ci_polls/pr_123/FAILED
    daemon_dir=$(dirname "$sentinel")
    pr_dir=$(basename "$daemon_dir")
    pr_num="${pr_dir#pr_}"
    parent_dir=$(basename "$(dirname "$daemon_dir")")

    case "$parent_dir" in
        ci_polls)       daemon_label="CI poller" ;;
        review_loops)   daemon_label="Review loop" ;;
        *)              daemon_label="Background daemon" ;;
    esac

    # Read summary (first line only, cap at 200 chars)
    summary=$(head -1 "$sentinel" 2>/dev/null | cut -c1-200 || echo "unknown failure")

    # Build message (use printf for real newlines, not literal \n)
    log_file=$([ "$parent_dir" = "ci_polls" ] && echo "poller.log" || echo "driver.log")
    MESSAGES="${MESSAGES}${daemon_label} for PR #${pr_num} FAILED: ${summary}. Log: ${daemon_dir}/${log_file}
"

    # Rename to NOTIFIED so we only alert once
    mv "$sentinel" "${daemon_dir}/NOTIFIED" 2>/dev/null || true
done

# Attention-broker sentinel (PR-MSG-4): one top-level FAILED file, not
# a per-PR directory.  Surface it once per failure then rename.
ATTENTION_SENTINEL="$RUNTIME_DIR/attention_broker/FAILED"
if [ -f "$ATTENTION_SENTINEL" ]; then
    summary=$(head -1 "$ATTENTION_SENTINEL" 2>/dev/null | cut -c1-200 || echo "unknown failure")
    log_file="$RUNTIME_DIR/attention_broker/daemon.log"
    MESSAGES="${MESSAGES}Attention broker FAILED: ${summary}. Log: ${log_file}
"
    mv "$ATTENTION_SENTINEL" "$RUNTIME_DIR/attention_broker/NOTIFIED" 2>/dev/null || true
fi

# If we found any failures, emit them as additionalContext
if [ -n "$MESSAGES" ]; then
    FULL_MSG="WARNING — Background daemon failure(s) detected:
${MESSAGES}Check the log files for details. You may need to re-push or manually investigate."

    # Use jq for robust JSON encoding (handles all special chars correctly).
    # Falls back to sed-based escaping if jq is unavailable.
    if command -v jq >/dev/null 2>&1; then
        jq -n --arg ctx "$FULL_MSG" \
            '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
    else
        # Fallback: escape \, ", tab, then collapse newlines to spaces
        JSON_MSG=$(printf '%s' "$FULL_MSG" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' ')
        cat <<ENDJSON
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "${JSON_MSG}"
  }
}
ENDJSON
    fi
fi

exit 0

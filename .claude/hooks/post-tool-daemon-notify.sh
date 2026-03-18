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

    # Build message
    MESSAGES="${MESSAGES}${daemon_label} for PR #${pr_num} FAILED: ${summary}. Log: ${daemon_dir}/$([ "$parent_dir" = "ci_polls" ] && echo "poller.log" || echo "driver.log")\n"

    # Rename to NOTIFIED so we only alert once
    mv "$sentinel" "${daemon_dir}/NOTIFIED" 2>/dev/null || true
done

# If we found any failures, emit them as additionalContext
if [ -n "$MESSAGES" ]; then
    # Escape for JSON
    JSON_MSG=$(printf '%s' "$MESSAGES" | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/\\t/g' | tr '\n' ' ')

    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "WARNING — Background daemon failure(s) detected:\n${JSON_MSG}\nCheck the log files for details. You may need to re-push or manually investigate."
  }
}
EOF
fi

exit 0

#!/bin/bash
# PostToolUse hook — checks main branch CI after a PR merge
# Alerts Claude if post-merge CI is failing so broken main is caught immediately.
set -euo pipefail

INPUT=$(cat)

# Only trigger for gh pr merge commands that succeeded
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr merge"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
  # Extract PR number from command for context
  PR_NUM=$(echo "$COMMAND" | grep -oE '[0-9]+' | head -1 || true)

  # Dedupe: don't check twice for the same merge in the same session
  if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-merge-ci-check-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
      exit 0
    fi
    touch "$SENTINEL"
  fi

  # Wait a moment for the push-to-main CI to trigger
  sleep 10

  # Check the latest CI run on main
  # Use gh run list to find the most recent run on main branch
  LATEST_STATUS=$(gh run list --branch main --limit 1 --json status,conclusion --jq '.[0] | "\(.status) \(.conclusion // "pending")"' 2>/dev/null || echo "unknown unknown")

  STATUS=$(echo "$LATEST_STATUS" | awk '{print $1}')
  CONCLUSION=$(echo "$LATEST_STATUS" | awk '{print $2}')

  if [[ "$CONCLUSION" == "failure" ]]; then
    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "WARNING: The latest CI run on main branch has FAILED after merging PR #${PR_NUM}. Post-merge CI failure detected. You should investigate: run 'gh run list --branch main --limit 3' and 'gh run view <id> --log-failed' to identify the failure. This may indicate that the merged PR conflicts with other recent merges."
  }
}
EOF
  elif [[ "$STATUS" == "in_progress" ]] || [[ "$CONCLUSION" == "pending" ]]; then
    # CI is still running — that's normal, no alert needed
    # But we could optionally note it
    :
  fi
fi

exit 0

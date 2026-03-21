#!/bin/bash
# PostToolUse hook — enqueues a durable review request after gh pr create.
#
# Under the queue-backed review model, this hook writes a ReviewRequest
# to the review queue substrate (bid_euchre.ops.review_queue) instead of
# triggering the /reviewing-changes skill.  The review driver (launched
# by post-pr-review-loop.sh) processes the request and writes a verdict
# that the merge guard (pre-merge-review-guard.sh) checks before merge.
#
# Guard: Sentinel file prevents double-trigger when registered in both
# settings.json and settings.local.json.
set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract the bash command (if this was a Bash tool call)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only trigger for gh pr create commands that succeeded
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr create"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
  # Dedupe guard: extract PR number from command output and use as sentinel.
  PR_NUM=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-pr-review-hook-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
      exit 0
    fi
    touch "$SENTINEL"
  fi

  # Enqueue a durable review request via the queue substrate
  SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  uv run python -c "
from bid_euchre.ops.review_queue import ReviewRequest, write_request
req = ReviewRequest(
    pr_number=${PR_NUM},
    head_sha='${SHA}',
    branch='${BRANCH}',
    requester='post-pr-review-hook',
)
write_request(req)
" 2>/dev/null || true

  # Inform the agent that a review was enqueued (informational only —
  # no longer triggers /reviewing-changes).
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "A PR was just created successfully. A review request has been enqueued and the review driver will process it asynchronously. The merge guard will verify the review verdict before allowing merge. You do NOT need to invoke /reviewing-changes — the queue-backed review system handles this automatically."
  }
}
EOF
fi

exit 0

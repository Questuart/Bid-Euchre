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

  # Enqueue a durable review request via the queue substrate.
  # Pass values via environment variables to avoid shell injection
  # from branch names containing quotes or special characters.
  SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  PR_REVIEW_NUM="$PR_NUM" PR_REVIEW_SHA="$SHA" PR_REVIEW_BRANCH="$BRANCH" \
    uv run python -c "
import os
from bid_euchre.ops.review_queue import ReviewRequest, write_request
req = ReviewRequest(
    pr_number=int(os.environ['PR_REVIEW_NUM']),
    head_sha=os.environ['PR_REVIEW_SHA'],
    branch=os.environ['PR_REVIEW_BRANCH'],
    requester='post-pr-review-hook',
)
write_request(req, emit_event=True)
" 2>/dev/null || true

  # --- #2701 — write PR number back onto the active dispatched packet ---
  # This feeds the orchestrator-side reconcile_dispatched_packets() pass in
  # monitor.py.  Without this, the reconciler has no way to map a packet
  # to a PR state on the auto-merge.yml path (which bypasses the local
  # post-merge-notify.sh hook entirely).
  #
  # Resolve the calling lane the same way post-merge-notify.sh does so
  # the two hooks agree on ownership. Best-effort — a failure here never
  # blocks PR creation.
  # Canonical resolver — previously missing analyst-* which broke the
  # #2701 PR write-back for analyst-lane PRs on the auto-merge path.
  LANE_ID=""
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && \
     [ -r "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh" ]; then
    # shellcheck disable=SC1091
    . "${CLAUDE_PROJECT_DIR}/.claude/hooks/lib/resolve-lane-id.sh"
    LANE_ID=$(resolve_lane_id)
  fi

  if [ -n "$LANE_ID" ]; then
    # packet_id='-' triggers lane-based resolution in the CLI.
    # Exit 0 is expected on "no dispatched packet" — the hook also
    # fires for ops-lane manual PRs that have no packet at all.
    uv run python scripts/internal/ops.py task update-metadata "-" \
      --lane "$LANE_ID" --pr-number "$PR_NUM" >/dev/null 2>&1 || true
  fi

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

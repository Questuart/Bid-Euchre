#!/bin/bash
# PostToolUse hook — triggers the autonomous review loop driver after PR creation.
#
# This hook complements post-pr-review.sh (which triggers /reviewing-changes).
# The review loop driver runs asynchronously in the background and manages
# the full Codex CLI review → fix → retest cycle.
set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract the bash command (if this was a Bash tool call)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only trigger for gh pr create commands that succeeded
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr create"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
  # Extract PR number from command output
  PR_NUM=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  BRANCH=$(git branch --show-current 2>/dev/null || true)

  if [ -n "$PR_NUM" ] && [ -n "$BRANCH" ]; then
    # Dedupe guard
    SENTINEL="/tmp/.claude-review-loop-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
      exit 0
    fi
    touch "$SENTINEL"

    # Launch driver in background (loops until terminal, 15min max)
    LOGDIR=".claude/runtime/review_loops/pr_${PR_NUM}"
    mkdir -p "$LOGDIR"
    PYTHONPATH=scripts/internal python scripts/internal/review_driver.py \
      --pr "$PR_NUM" \
      --branch "$BRANCH" \
      --trigger pr_created \
      > "$LOGDIR/driver.log" 2>&1 &
  fi
fi

exit 0

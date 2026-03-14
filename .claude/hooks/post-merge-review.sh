#!/bin/bash
# PostToolUse hook — triggers comprehensive post-merge review
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr merge"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
  # Extract PR number
  PR_NUM=$(echo "$COMMAND" | grep -oE '[0-9]+' | head -1 || true)

  # Dedupe guard
  if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-post-merge-review-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
      exit 0
    fi
    touch "$SENTINEL"
  fi

  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "PR #${PR_NUM} was just merged. You SHOULD spawn a background Explore agent to perform a comprehensive post-merge review of the merged code on main. The agent should review all changed files for: correctness (C1/C2 checks, logic bugs, edge cases), contract compliance with the governing plan, architectural boundary violations (src/ vs scripts/), test coverage gaps, and integration risks with other recently merged PRs. Report findings as a severity table (CRITICAL/WARNING/NIT). If CRITICAL findings are found, create a follow-up fix PR immediately."
  }
}
EOF
fi

exit 0

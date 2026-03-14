#!/bin/bash
# PostToolUse hook — triggers parallel multi-lens post-merge review
# Instead of one monolithic Explore agent, launches 3 specialized agents
# (correctness, architecture, coverage) with smaller scope and shorter timeouts.
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
    "additionalContext": "PR #${PR_NUM} was just merged. Launch a parallel multi-lens post-merge review using 3 specialized agents. Run all 3 in parallel using the Agent tool:\n\n1. **correctness-reviewer** (agent: .claude/agents/correctness-reviewer.md) — Logic bugs, contract violations, data policy, determinism. Prompt: 'Review the merge commit for PR #${PR_NUM}. Run git diff main~1...main to see what changed. Check for logic bugs, contract violations (core/scoring/logging changes without doc updates), data policy violations, and determinism issues. Return JSON findings list.'\n\n2. **architecture-reviewer** (agent: .claude/agents/architecture-reviewer.md) — Import boundaries, module coupling, API surface, circular imports. Prompt: 'Review the merge commit for PR #${PR_NUM}. Run git diff main~1...main to see what changed. Check for import boundary violations (src/ importing from experiments/ or tests/), new cross-module coupling, API surface changes without caller updates, and circular import risks. Return JSON findings list.'\n\n3. **coverage-reviewer** (agent: .claude/agents/coverage-reviewer.md) — Untested changes, missing edge cases, regression risk. Prompt: 'Review the merge commit for PR #${PR_NUM}. Run git diff main~1...main to see what changed. Check for untested behavior changes, missing edge case tests, and regression risk. Return JSON findings list.'\n\nAfter all 3 agents complete, consolidate their findings into a single severity table. If ANY agent reports CRITICAL findings, create an immediate follow-up fix PR. If there are WARNING or INFO findings, post a summary comment on PR #${PR_NUM} using: gh pr comment ${PR_NUM} --body '<summary>'"
  }
}
EOF
fi

exit 0

#!/bin/bash
# PostToolUse hook — triggers parallel multi-lens post-merge review
# Instead of one monolithic Explore agent, launches 3 specialized agents
# (correctness, architecture, coverage) with smaller scope and shorter timeouts.
#
# Scope guards:
#   - Only fires on successful `gh pr merge`
#   - Skips if no src/ or tests/ or scripts/ files changed (docs/plans-only PRs)
#   - Passes explicit file list to agents to prevent scope creep
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

  # Compute changed files from the merge commit
  CHANGED_FILES=$(git diff main~1...main --name-only 2>/dev/null || echo "")

  # Skip review if no code files changed (docs/plans/reports-only PRs)
  CODE_FILES=$(echo "$CHANGED_FILES" | grep -E '^(src/|tests/|scripts/|experiments/)' || true)
  if [ -z "$CODE_FILES" ]; then
    # No code files — skip review entirely
    exit 0
  fi

  # Build file list string for agent prompts (newline-separated, indented)
  FILE_LIST=$(echo "$CODE_FILES" | sed 's/^/  - /' | tr '\n' '|' | sed 's/|/\\n/g')

  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "PR #${PR_NUM} was just merged. Launch a parallel multi-lens post-merge review using 3 specialized agents. Run all 3 in parallel using the Agent tool:\n\nIMPORTANT SCOPE CONSTRAINT: The following files were changed in this PR. Agents must ONLY review these files. Do NOT read or analyze files outside this list. Do NOT perform gap analysis against plan documents. The goal is to find regressions INTRODUCED by this PR, not pre-existing issues.\n\nChanged files:\n${FILE_LIST}\n\n1. **correctness-reviewer** (subagent_type: correctness-reviewer) — Logic bugs, contract violations, data policy, determinism. Prompt: 'Review ONLY the changes in PR #${PR_NUM}. Run git diff main~1...main to see the diff. SCOPE: Only review code that was actually changed — do NOT review adjacent files, do NOT read plan documents, do NOT perform gap analysis against plans. Your goal is finding regressions INTRODUCED by this specific PR. Changed files:\\n${FILE_LIST}\\nCheck for: logic bugs, contract violations, data policy violations, determinism issues. If no src/ files were changed or no issues found in the changed code, return [].'\n\n2. **architecture-reviewer** (subagent_type: architecture-reviewer) — Import boundaries, module coupling, API surface, circular imports. Prompt: 'Review ONLY the changes in PR #${PR_NUM}. Run git diff main~1...main to see the diff. SCOPE: Only review code that was actually changed — do NOT review adjacent files, do NOT follow references to other modules for gap analysis. Your goal is finding architectural regressions INTRODUCED by this specific PR. Changed files:\\n${FILE_LIST}\\nCheck for: import boundary violations, new cross-module coupling, API surface changes without caller updates, circular import risks. If no issues found in the changed code, return [].'\n\n3. **coverage-reviewer** (subagent_type: coverage-reviewer) — Untested changes, missing edge cases, regression risk. Prompt: 'Review ONLY the changes in PR #${PR_NUM}. Run git diff main~1...main to see the diff. SCOPE: Only review code that was actually changed — do NOT review the entire module for pre-existing coverage gaps. Your goal is finding untested behavior changes INTRODUCED by this specific PR. Changed files:\\n${FILE_LIST}\\nCheck for: untested behavior changes, missing edge case tests, regression risk. If no issues found in the changed code, return [].'\n\nAfter all 3 agents complete, consolidate their findings into a single severity table. DISCARD any finding about code that was NOT changed in this PR. If ANY agent reports CRITICAL findings about code changed in this PR, create an immediate follow-up fix PR. If there are WARNING or INFO findings, post a summary comment on PR #${PR_NUM} using: gh pr comment ${PR_NUM} --body '<summary>'"
  }
}
EOF
fi

exit 0

#!/bin/bash
# PostToolUse hook — triggers /reviewing-changes after gh pr create
#
# Guard: This hook may be registered in both settings.json (shared) and
# settings.local.json (legacy). The sentinel file prevents double-trigger
# within the same Claude session when both copies fire.
set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract the bash command (if this was a Bash tool call)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only trigger for gh pr create commands that succeeded
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr create"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
  # Dedupe guard: extract PR number from command output and use as sentinel.
  # If both settings.json and settings.local.json register this hook,
  # the second invocation finds the sentinel and exits silently.
  PR_NUM=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' | head -1 || true)
  if [ -n "$PR_NUM" ]; then
    SENTINEL="/tmp/.claude-pr-review-hook-${PR_NUM}"
    if [ -f "$SENTINEL" ]; then
      exit 0
    fi
    touch "$SENTINEL"
  fi
  # Emit structured JSON so additionalContext is injected into Claude's
  # conversation context, making it auto-invoke /reviewing-changes.
  cat <<'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "A PR was just created successfully. You MUST now invoke the /reviewing-changes skill immediately — do not wait for the user to ask. This skill reviews the PR for quality issues, convention compliance, and generates a handoff summary."
  }
}
EOF
fi

exit 0

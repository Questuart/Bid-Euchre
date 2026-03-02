#!/bin/bash
# PostToolUse hook — triggers /reviewing-changes after gh pr create
set -euo pipefail

# Read JSON input from stdin
INPUT=$(cat)

# Extract the bash command (if this was a Bash tool call)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only trigger for gh pr create commands that succeeded
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

if [[ "$COMMAND" == *"gh pr create"* ]] && [[ "$EXIT_CODE" == "0" ]]; then
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

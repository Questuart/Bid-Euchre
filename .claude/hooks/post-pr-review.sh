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
  echo ""
  echo "PR created successfully."
  echo "Now run /reviewing-changes to review the code and generate a handoff summary."
  echo "This will check for quality issues, convention compliance, and produce a copyable context block."
fi

exit 0

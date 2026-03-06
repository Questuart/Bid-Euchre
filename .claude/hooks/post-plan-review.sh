#!/bin/bash
# PostToolUse hook — triggers /reviewing-plans after plan file creation
set -euo pipefail

INPUT=$(cat)

# Extract the file path from Write tool input
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Only trigger for plan files under the repo's plans/ directory
# Exclude TEMPLATE.md to avoid triggering on template creation/edits
if [[ "$FILE_PATH" == */plans/*.md ]] && \
   [[ "$FILE_PATH" != *TEMPLATE.md ]]; then

  PLAN_NAME=$(basename "$FILE_PATH" .md)

  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "A plan file '${PLAN_NAME}' was just created at ${FILE_PATH}. You MUST now invoke the /reviewing-plans skill immediately -- do not wait for the user to ask. Pass the plan file path to the reviewer."
  }
}
EOF
fi

exit 0

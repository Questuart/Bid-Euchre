#!/bin/bash
# PostToolUse hook — polls CI status after git push to a PR branch.
# Warns Claude if CI fails so the failure is caught before proceeding.
set -euo pipefail

INPUT=$(cat)

# Only trigger for git push commands that succeeded
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

# Match 'git push' but not 'git push --delete' or 'git push origin :branch'
if [[ "$COMMAND" == *"git push"* ]] && [[ "$EXIT_CODE" == "0" ]] \
   && [[ "$COMMAND" != *"--delete"* ]] && [[ "$COMMAND" != *" :"* ]]; then

  # Determine current branch
  BRANCH=$(git branch --show-current 2>/dev/null || true)
  if [ -z "$BRANCH" ] || [ "$BRANCH" = "main" ]; then
    exit 0
  fi

  # Dedupe: don't check twice for the same push in the same session
  HEAD_SHA=$(git rev-parse --short HEAD 2>/dev/null || true)
  SENTINEL="/tmp/.claude-push-ci-check-${BRANCH}-${HEAD_SHA}"
  if [ -f "$SENTINEL" ]; then
    exit 0
  fi
  touch "$SENTINEL"

  # Wait for CI to start
  sleep 15

  # Poll CI status (up to 3 minutes, every 15 seconds)
  MAX_POLLS=12
  for i in $(seq 1 "$MAX_POLLS"); do
    # Get check status for the branch
    CHECK_OUTPUT=$(gh pr checks --json name,state 2>/dev/null || echo "")

    if [ -z "$CHECK_OUTPUT" ]; then
      # No PR exists yet or gh pr checks failed — skip
      exit 0
    fi

    # Check if any check has failed
    FAILED=$(echo "$CHECK_OUTPUT" | jq -r '[.[] | select(.state == "FAILURE")] | length' 2>/dev/null || echo "0")
    PENDING=$(echo "$CHECK_OUTPUT" | jq -r '[.[] | select(.state == "PENDING")] | length' 2>/dev/null || echo "0")

    if [ "$FAILED" -gt 0 ]; then
      FAILED_NAMES=$(echo "$CHECK_OUTPUT" | jq -r '[.[] | select(.state == "FAILURE") | .name] | join(", ")' 2>/dev/null || echo "unknown")
      cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "WARNING: CI FAILED on branch '${BRANCH}' after push. Failed checks: ${FAILED_NAMES}. Run 'gh pr checks' and 'gh run view <id> --log-failed' to diagnose. Fix the issue and push again."
  }
}
EOF
      exit 0
    fi

    if [ "$PENDING" -eq 0 ]; then
      # All checks passed — no alert needed
      exit 0
    fi

    # Still pending — wait and retry
    sleep 15
  done

  # Timed out waiting for CI — note it but don't block
  cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "NOTE: CI still running on branch '${BRANCH}' after 3 minutes. Check status with 'gh pr checks' before proceeding."
  }
}
EOF
fi

exit 0

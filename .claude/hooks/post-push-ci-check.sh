#!/bin/bash
# PostToolUse hook — launches background CI poller after git push to a PR branch.
#
# Replaces the previous synchronous 3-minute polling approach. Now exits in <2s
# and launches scripts/internal/ci_poller.sh in the background to handle CI
# monitoring and optional auto-merge.
set -euo pipefail

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

git_in_project() {
    git -C "$PROJECT_DIR" "$@"
}

gh_in_project() {
    (
        cd "$PROJECT_DIR"
        gh "$@"
    )
}

sanitize_token() {
    printf '%s' "$1" | sed 's#[^A-Za-z0-9._-]#_#g'
}

# Only trigger for git push commands that succeeded
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0')

# Match 'git push' but not 'git push --delete' or 'git push origin :branch'
if [[ "$COMMAND" == *"git push"* ]] && [[ "$EXIT_CODE" == "0" ]] \
   && [[ "$COMMAND" != *"--delete"* ]] && [[ "$COMMAND" != *" :"* ]]; then

    # Determine current branch
    BRANCH=$(git_in_project branch --show-current 2>/dev/null || true)
    if [ -z "$BRANCH" ] || [ "$BRANCH" = "main" ]; then
        exit 0
    fi

    # Dedupe: don't trigger twice for the same push
    HEAD_SHA=$(git_in_project rev-parse --short HEAD 2>/dev/null || true)
    SAFE_BRANCH=$(sanitize_token "$BRANCH")
    SENTINEL="/tmp/.claude-push-ci-check-${SAFE_BRANCH}-${HEAD_SHA}"
    if [ -f "$SENTINEL" ]; then
        exit 0
    fi
    touch "$SENTINEL"

    # Check if a PR exists for this branch
    PR_NUM=$(gh_in_project pr view --json number --jq '.number' 2>/dev/null || echo "")
    if [ -z "$PR_NUM" ]; then
        # No PR yet — nothing to monitor
        exit 0
    fi

    # Locate the CI poller script
    REPO_ROOT=$(git_in_project rev-parse --show-toplevel 2>/dev/null || echo "")
    POLLER="${REPO_ROOT}/scripts/internal/ci_poller.sh"

    if [ ! -f "$POLLER" ]; then
        exit 0
    fi

    # Launch CI poller in background with auto-merge enabled
    (
        cd "$REPO_ROOT"
        bash "$POLLER" --pr "$PR_NUM" --repo-root "$REPO_ROOT" --auto-merge
    ) &

    cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "CI has been triggered on branch '${BRANCH}' (PR #${PR_NUM}). A background CI poller is monitoring checks and will auto-merge (squash) when all pass. Status file: .claude/runtime/ci_polls/pr_${PR_NUM}/status.json — Log: .claude/runtime/ci_polls/pr_${PR_NUM}/poller.log — No action needed unless you want to check progress."
  }
}
EOF
fi

exit 0

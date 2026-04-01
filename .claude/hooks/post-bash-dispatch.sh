#!/usr/bin/env bash
# post-bash-dispatch.sh — Consolidated PostToolUse dispatcher for Bash tool calls.
#
# Runs all PostToolUse hooks for Bash in a single invocation to minimize
# "Async hook completed" TUI messages (issue #1255). Dispatches to each
# sub-hook sequentially, collecting any additionalContext output.
#
# Sub-hooks (order matters for merge/push flows):
#   1. post-pr-review.sh — enqueues review request after gh pr create
#   2. post-pr-review-loop.sh — launches review driver after gh pr create
#   3. post-push-ci-check.sh — launches CI poller after git push
#   4. post-merge-ci-check.sh — checks main CI after gh pr merge
#   5. post-merge-review.sh — triggers post-merge review after gh pr merge
#   6. post-tool-daemon-notify.sh — checks for background daemon failures
#   7. post-task-event.sh — emits task events on relevant commands
#   8. post-monitor-push-relay.sh — injects additionalContext for Telegram push
#   9. post-merge-notify.sh — auto-completes task lifecycle on merge
#
# For typical Bash commands (cd, ls, git status, pytest, etc.), all hooks
# exit immediately (<100ms each). Only specific commands (gh pr create,
# git push, gh pr merge) trigger meaningful work.
#
# Timeout: 45s (accommodates post-merge-ci-check's sleep 10 + API calls)
set -euo pipefail

HOOKS_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks"

# Read JSON from stdin once
INPUT=$(cat)

# Collect additionalContext from all hooks that produce output
COMBINED_CONTEXT=""

run_hook() {
    local hook_script="$1"
    local output=""

    if [ ! -x "$hook_script" ]; then
        return 0
    fi

    # Run the hook, piping saved stdin.
    # Sub-hooks that launch background processes must redirect their own
    # stdout/stderr (e.g., > logfile 2>&1 &) so they don't hold this
    # pipe open. See post-push-ci-check.sh fix.
    output=$(echo "$INPUT" | "$hook_script" 2>/dev/null) || true

    if [ -n "$output" ]; then
        # Extract additionalContext from hookSpecificOutput (PostToolUse schema)
        local ctx=""
        ctx=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)
        if [ -n "$ctx" ]; then
            if [ -n "$COMBINED_CONTEXT" ]; then
                COMBINED_CONTEXT="${COMBINED_CONTEXT}
---
${ctx}"
            else
                COMBINED_CONTEXT="$ctx"
            fi
        fi
    fi
}

# Run all sub-hooks sequentially
run_hook "$HOOKS_DIR/post-pr-review.sh"
run_hook "$HOOKS_DIR/post-pr-review-loop.sh"
run_hook "$HOOKS_DIR/post-push-ci-check.sh"
run_hook "$HOOKS_DIR/post-merge-ci-check.sh"
run_hook "$HOOKS_DIR/post-merge-review.sh"
run_hook "$HOOKS_DIR/post-tool-daemon-notify.sh"
run_hook "$HOOKS_DIR/post-task-event.sh"
run_hook "$HOOKS_DIR/post-monitor-push-relay.sh"
run_hook "$HOOKS_DIR/post-merge-notify.sh"

# Return combined output (if any hooks produced context),
# otherwise suppress TUI notification (issue #1360).
if [ -n "$COMBINED_CONTEXT" ]; then
    echo "$COMBINED_CONTEXT" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: .}}'
else
    echo '{"suppressOutput": true}'
fi

exit 0

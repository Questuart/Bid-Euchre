#!/usr/bin/env bash
# pre-bash-dispatch.sh — Consolidated PreToolUse dispatcher for Bash tool calls.
#
# Runs all PreToolUse hooks for Bash in a single invocation to minimize
# "Async hook completed" TUI messages (issue #1255). Dispatches to:
#   1. pre-worktree-cleanup.sh — blocks dangerous rm/worktree commands
#   2. pre-merge-review-guard.sh — blocks merge without review verdict
#   3. rule-loader.sh — progressive rule disclosure (context injection)
#
# Guards run first: if either blocks (exit 2), we propagate immediately.
# Rule-loader runs last since context injection is only useful if the
# command is allowed to proceed.
#
# Exit codes: 0 = allow, 2 = block (propagated from sub-hooks)
# Timeout: 20s (accommodates merge guard's gh API calls)
set -euo pipefail

HOOKS_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/hooks"

# Read JSON from stdin once, reuse for all sub-hooks
INPUT=$(cat)

# --- 1. Worktree cleanup guard (may block with exit 2) ---
if [ -x "$HOOKS_DIR/pre-worktree-cleanup.sh" ]; then
    WT_OUTPUT=""
    WT_EXIT=0
    WT_OUTPUT=$(echo "$INPUT" | "$HOOKS_DIR/pre-worktree-cleanup.sh" 2>/dev/null) || WT_EXIT=$?
    if [ "$WT_EXIT" -ne 0 ]; then
        # Propagate block — output the guard's message and exit
        echo "$WT_OUTPUT"
        exit "$WT_EXIT"
    fi
fi

# --- 2. Merge review guard (may block with exit 2) ---
if [ -x "$HOOKS_DIR/pre-merge-review-guard.sh" ]; then
    MRG_OUTPUT=""
    MRG_EXIT=0
    MRG_OUTPUT=$(echo "$INPUT" | "$HOOKS_DIR/pre-merge-review-guard.sh" 2>/dev/null) || MRG_EXIT=$?
    if [ "$MRG_EXIT" -ne 0 ]; then
        echo "$MRG_OUTPUT"
        exit "$MRG_EXIT"
    fi
fi

# --- 3. Rule loader (never blocks, may return additionalContext) ---
if [ -x "$HOOKS_DIR/rule-loader.sh" ]; then
    RULE_OUTPUT=""
    RULE_OUTPUT=$(echo "$INPUT" | "$HOOKS_DIR/rule-loader.sh" 2>/dev/null) || true

    # Check if rule-loader returned additionalContext
    if [ -n "$RULE_OUTPUT" ]; then
        AC=$(echo "$RULE_OUTPUT" | jq -r '.additionalContext // empty' 2>/dev/null || true)
        if [ -n "$AC" ]; then
            # Pass through rule-loader's full output (includes additionalContext + suppressOutput)
            echo "$RULE_OUTPUT"
            exit 0
        fi
    fi
fi

# All guards passed, no context to inject
echo '{"suppressOutput": true}'
exit 0

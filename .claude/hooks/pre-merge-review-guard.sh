#!/usr/bin/env bash
# PreToolUse hook — blocks gh pr merge unless review verdict is clean.
#
# This is the hard local merge guard for the queue-backed review model.
# It checks:
#   1. A review verdict exists for the PR
#   2. The verdict SHA matches the current PR HEAD
#   3. The verdict status is "passed"
#   4. CI checks are green
#
# If any check fails, the command is blocked with an explanatory message.
# Exit code 2 blocks the tool execution (Claude Code convention).
#
# Timeout: 10s (needs gh API calls for SHA and CI)
set -euo pipefail

# PreToolUse receives JSON on stdin
INPUT=$(cat)

# Extract the command being attempted
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Only guard gh pr merge commands
if [[ "$COMMAND" != *"gh pr merge"* ]]; then
  exit 0
fi

# Extract PR number from the command. Supports:
#   gh pr merge 123 --squash
#   gh pr merge https://github.com/.../pull/123 --squash
#   gh pr merge feature-branch --squash  (falls back to gh pr view)
#   gh pr merge --squash  (falls back to gh pr view for current branch)
PR_NUM=$(echo "$COMMAND" | grep -oE 'gh pr merge[[:space:]]+[0-9]+' | grep -oE '[0-9]+' || true)

# Try URL pattern: /pull/<N>
if [ -z "$PR_NUM" ]; then
  PR_NUM=$(echo "$COMMAND" | grep -oE '/pull/[0-9]+' | grep -oE '[0-9]+' || true)
fi

# Fallback: use gh pr view for current branch or branch argument
if [ -z "$PR_NUM" ]; then
  PR_NUM=$(gh pr view --json number --jq .number 2>/dev/null || true)
fi

if [ -z "$PR_NUM" ]; then
  cat <<BLOCK
BLOCKED: Cannot determine PR number for merge command.

Specify the PR number explicitly: gh pr merge <number> --squash
BLOCK
  exit 2
fi

# --- Check 1: Verdict exists ---
VERDICT_FILE="${CLAUDE_PROJECT_DIR:-.}/.claude/runtime/review_queue/pr_${PR_NUM}/verdict.json"
if [ ! -f "$VERDICT_FILE" ]; then
  cat <<BLOCK
BLOCKED: No review verdict found for PR #${PR_NUM}.

The review driver must complete and write a verdict before merge is allowed.
Check review status:
  uv run python scripts/internal/ops.py reviews queue

Or manually trigger a review:
  uv run python scripts/internal/review_driver.py --pr ${PR_NUM} --trigger manual
BLOCK
  exit 2
fi

# --- Check 2: Verdict SHA matches current HEAD ---
VERDICT_SHA=$(jq -r '.reviewed_sha // ""' "$VERDICT_FILE" 2>/dev/null || echo "")
CURRENT_SHA=$(gh pr view "$PR_NUM" --json headRefOid --jq .headRefOid 2>/dev/null || echo "")

if [ -z "$CURRENT_SHA" ]; then
  cat <<BLOCK
BLOCKED: Cannot determine current HEAD SHA for PR #${PR_NUM}.

Ensure the PR exists and is open, then retry.
BLOCK
  exit 2
fi

if [ "$VERDICT_SHA" != "$CURRENT_SHA" ]; then
  cat <<BLOCK
BLOCKED: Stale review verdict for PR #${PR_NUM}.

Verdict covers SHA ${VERDICT_SHA:0:8} but current HEAD is ${CURRENT_SHA:0:8}.
A new review is needed after the latest push.

Trigger a new review:
  uv run python scripts/internal/review_driver.py --pr ${PR_NUM} --trigger manual
BLOCK
  exit 2
fi

# --- Check 3: Verdict status is "passed" ---
VERDICT_STATUS=$(jq -r '.status // ""' "$VERDICT_FILE" 2>/dev/null || echo "")

if [ "$VERDICT_STATUS" != "passed" ]; then
  VERDICT_REASON=$(jq -r '.reason // "(no reason)"' "$VERDICT_FILE" 2>/dev/null || echo "unknown")
  cat <<BLOCK
BLOCKED: Review verdict for PR #${PR_NUM} is "${VERDICT_STATUS}", not "passed".

Reason: ${VERDICT_REASON}

Address the review findings, push fixes, and re-run the review.
BLOCK
  exit 2
fi

# --- Check 4: CI is green ---
CI_STATUS=$(uv run python -c "
import json, subprocess, sys
try:
    from bid_euchre.ops import classify_check
except ImportError:
    NON_CI = {'reviewing-changes', 'claude-review', 'enable-auto-merge'}
    def classify_check(name):
        return 'non_ci' if name in NON_CI else 'ci'

result = subprocess.run(
    ['gh', 'pr', 'checks', '${PR_NUM}', '--json', 'name,state'],
    capture_output=True, text=True, timeout=15,
)
if result.returncode != 0:
    print('unknown'); sys.exit()
checks = json.loads(result.stdout)
ci = [c for c in checks if classify_check(c.get('name', '')) == 'ci']
if not ci:
    print('pending'); sys.exit()
states = [c.get('state', 'PENDING') for c in ci]
if any(s == 'FAILURE' for s in states):
    print('failure')
elif any(s in ('PENDING', 'IN_PROGRESS') for s in states):
    print('pending')
elif all(s in ('SUCCESS', 'SKIPPED') for s in states):
    print('success')
else:
    print('unknown')
" 2>/dev/null || echo "unknown")

if [ "$CI_STATUS" != "success" ]; then
  cat <<BLOCK
BLOCKED: CI status for PR #${PR_NUM} is "${CI_STATUS}", not "success".

Wait for CI to pass before merging.
  gh pr checks ${PR_NUM}
BLOCK
  exit 2
fi

# All checks passed — allow the merge
exit 0

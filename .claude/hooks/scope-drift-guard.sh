#!/usr/bin/env bash
# PreToolUse hook — warns or blocks git commit when staged files exceed
# the active task packet's declared scope.
#
# Only activates when:
#   1. The Bash command starts with "git commit"
#   2. A dispatched task packet exists for the current lane
#   3. The packet has declared scope patterns
#
# Exit codes: 0 = allow, 2 = block (Claude Code convention)
# Timeout: 10s
set -euo pipefail

# PreToolUse receives JSON on stdin
INPUT=$(cat)

# Extract the command being attempted
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Only guard on direct "git commit" commands (not quoted inside tmux etc.)
TRIMMED="${COMMAND#"${COMMAND%%[![:space:]]*}"}"
if [[ "$TRIMMED" != "git commit"* ]]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Determine lane identity
LANE_ID="${CLAUDE_AGENT_NAME:-}"
if [ -z "$LANE_ID" ]; then
  # Fallback: parse from project directory name
  PROJ_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
  DIR_NAME=$(basename "$PROJ_DIR")
  case "$DIR_NAME" in
    *steward-author)    LANE_ID="author-a" ;;
    *steward-author-b)  LANE_ID="author-b" ;;
    *steward-author-c)  LANE_ID="author-c" ;;
    *steward-author-d)  LANE_ID="author-d" ;;
    *steward-author-scratch) LANE_ID="author-scratch" ;;
    *brws-author-a)     LANE_ID="brws-author-a" ;;
    *brws-author-b)     LANE_ID="brws-author-b" ;;
    *brws-author-c)     LANE_ID="brws-author-c" ;;
    *brws-author-d)     LANE_ID="brws-author-d" ;;
    *steward-flex-a)    LANE_ID="flex-a" ;;
    *steward-flex-b)    LANE_ID="flex-b" ;;
    *steward-flex-c)    LANE_ID="flex-c" ;;
    *)                  LANE_ID="" ;;
  esac
fi

if [ -z "$LANE_ID" ]; then
  # Cannot determine lane — skip enforcement silently
  echo '{"suppressOutput": true}'
  exit 0
fi

# Run enforcement via Python — pass LANE_ID as sys.argv[1] to avoid
# unsafe shell interpolation into Python source (issue #1379).
RESULT=$(uv run python -c "
import json, subprocess, sys

from bid_euchre.ops.scope import enforce_scope_drift, get_active_task_scope

lane_id = sys.argv[1]

# Find active task for this lane
task_id, patterns = get_active_task_scope(lane_id)
if task_id is None or not patterns:
    print(json.dumps({'action': 'skip', 'reason': 'No active task or no scope patterns.'}))
    sys.exit(0)

# Get staged files from git
result = subprocess.run(
    ['git', 'diff', '--cached', '--name-only'],
    capture_output=True, text=True, timeout=5,
)
if result.returncode != 0:
    print(json.dumps({'action': 'skip', 'reason': 'Cannot read staged files.'}))
    sys.exit(0)

staged = [f for f in result.stdout.strip().split('\n') if f]
if not staged:
    print(json.dumps({'action': 'skip', 'reason': 'No staged files.'}))
    sys.exit(0)

verdict = enforce_scope_drift(staged, patterns, task_id=task_id)
print(json.dumps(verdict.to_dict()))
" "$LANE_ID" 2>/dev/null)

if [ -z "$RESULT" ]; then
  # Python invocation failed — don't block work
  echo '{"suppressOutput": true}'
  exit 0
fi

ACTION=$(echo "$RESULT" | jq -r '.action // "skip"' 2>/dev/null || echo "skip")
REASON=$(echo "$RESULT" | jq -r '.reason // ""' 2>/dev/null || echo "")
TASK_ID=$(echo "$RESULT" | jq -r '.task_id // ""' 2>/dev/null || echo "")
OOS_FILES=$(echo "$RESULT" | jq -r '.out_of_scope[]? // empty' 2>/dev/null || echo "")

case "$ACTION" in
  block)
    cat <<BLOCK
SCOPE DRIFT BLOCKED: Commit blocked by scope enforcement.

Task: ${TASK_ID}
${REASON}

Out-of-scope files:
$(echo "$OOS_FILES" | sed 's/^/  ! /')

To proceed, either:
  1. Unstage out-of-scope files: git reset HEAD <file>
  2. Update the task packet scope if the files are legitimately needed
BLOCK
    exit 2
    ;;
  warn)
    # Warn but allow — inject context so Claude sees the warning
    WARNING="SCOPE DRIFT WARNING (task ${TASK_ID}): ${REASON}"
    if [ -n "$OOS_FILES" ]; then
      WARNING="${WARNING}\nOut-of-scope: $(echo "$OOS_FILES" | tr '\n' ', ' | sed 's/,$//')"
    fi
    echo "{\"additionalContext\": \"${WARNING}\"}"
    exit 0
    ;;
  *)
    # skip or allow
    echo '{"suppressOutput": true}'
    exit 0
    ;;
esac

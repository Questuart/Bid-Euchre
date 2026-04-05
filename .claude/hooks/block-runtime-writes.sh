#!/usr/bin/env bash
# PreToolUse hook — blocks Edit/Write to .claude/runtime/ paths.
#
# Claude Code has a platform-level protection on .claude/ paths that
# prompts for confirmation.  This check fires BEFORE permissions.allow
# is evaluated, so allow-list entries for .claude/runtime/** are
# ineffective (see issue #2238, upstream issues #38806, #37765, #36168).
#
# In autonomous fleet operation no human watches the prompt, causing the
# lane to stall indefinitely.  This hook intercepts the tool call BEFORE
# the platform check fires, returning a clear error with CLI alternatives.
#
# Alternatives for writing .claude/runtime/ state:
#   Review HWM:   uv run python scripts/internal/ops.py review-hwm set <N>
#   General file: uv run python -c "from pathlib import Path; ..."
#   Shell hook:   echo '...' > .claude/runtime/<file>  (Bash tool, not Edit/Write)
#
# Refs: #2238, #2249, analyst plan 2026-04-03_review_state_permission_fix.md
set -uo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")

# No file path — not our concern (shouldn't happen for Edit/Write, but be safe)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Check if the path targets .claude/runtime/
# Handle both absolute and relative paths
#
# README.md exemption: only the 6 git-tracked schema docs are exempt.
# An arbitrary new README.md under .claude/runtime/ is NOT exempt — the
# allowlist must be updated when a new tracked README is added.
# Tracked README.md files (as of PR #2425):
#   .claude/runtime/README.md
#   .claude/runtime/events/README.md
#   .claude/runtime/scheduler/README.md
#   .claude/runtime/session_metadata/README.md
#   .claude/runtime/task_state/README.md
#   .claude/runtime/worktree_registry/README.md
_TRACKED_DIRS="events scheduler session_metadata task_state worktree_registry"
case "$FILE_PATH" in
  */.claude/runtime/README.md|.claude/runtime/README.md)
    # Top-level runtime README.md — tracked schema doc
    exit 0
    ;;
esac
for _dir in $_TRACKED_DIRS; do
  case "$FILE_PATH" in
    */.claude/runtime/"$_dir"/README.md|.claude/runtime/"$_dir"/README.md)
      exit 0
      ;;
  esac
done
case "$FILE_PATH" in
  */.claude/runtime/*|.claude/runtime/*)
    cat <<BLOCK
BLOCKED: Edit/Write to .claude/runtime/ is not allowed.

Claude Code's platform-level protection on .claude/ paths causes permission
stalls in autonomous fleet operation.  Use subprocess-based alternatives:

  Review HWM:     uv run python scripts/internal/ops.py review-hwm set <N>
  Arbitrary file:  uv run python -c "from pathlib import Path; p=Path('.claude/runtime/...'); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('...')"
  Shell redirect:  echo '...' > .claude/runtime/<path>

See issue #2238 for details.
BLOCK
    exit 2
    ;;
esac

# Path is not in .claude/runtime/ — allow
exit 0

#!/bin/bash
# UserPromptSubmit hook: inject high/urgent fleet alerts as additionalContext.
#
# Reads .claude/runtime/fleet_status.json (written by the controller/reconciler)
# and injects open HIGH or URGENT items so the orchestrator cannot miss them.
#
# Speed: ~100ms (stdlib-only Python, no project imports, no uv overhead).
# Closes #1608.

set -euo pipefail

exec python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/alert-inject.py"

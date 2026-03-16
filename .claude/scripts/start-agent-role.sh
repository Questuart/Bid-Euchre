#!/bin/bash
# Start Claude Code in a specific role worktree.
# Usage: start-agent-role.sh <role>
#
# Verifies the role worktree exists, sets CLAUDE_ROLE for hooks,
# and execs claude in the worktree directory.

set -euo pipefail

MAIN_DIR="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel)"
PARENT_DIR="$(dirname "$MAIN_DIR")"
REPO_NAME="$(basename "$MAIN_DIR")"
VALID_ROLES="author review ops"

# --- helpers ----------------------------------------------------------------

usage() {
    echo "Usage: $0 <role>"
    echo ""
    echo "Roles: author, review, ops"
    echo ""
    echo "Starts Claude Code in the role worktree with role-appropriate context."
    echo "The worktree must already exist. Create it with:"
    echo "  .claude/scripts/start-role-worktree.sh <role>"
}

is_valid_role() {
    local role="$1"
    for r in $VALID_ROLES; do
        if [ "$r" = "$role" ]; then
            return 0
        fi
    done
    return 1
}

# --- main -------------------------------------------------------------------

if [ $# -ne 1 ] || [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    usage
    exit 1
fi

ROLE="$1"

if ! is_valid_role "$ROLE"; then
    echo "Error: Invalid role '${ROLE}'. Must be one of: ${VALID_ROLES}"
    exit 1
fi

WT_PATH="${PARENT_DIR}/${REPO_NAME}-${ROLE}"

if [ ! -d "$WT_PATH" ]; then
    echo "Error: Role worktree not found at ${WT_PATH}"
    echo ""
    echo "Create it first:"
    echo "  .claude/scripts/start-role-worktree.sh ${ROLE}"
    exit 1
fi

echo "Starting Claude in ${ROLE} role..."
echo "  Worktree: ${WT_PATH}"
echo "  Branch:   role/${ROLE}"
echo ""

export CLAUDE_ROLE="$ROLE"
cd "$WT_PATH"
exec claude

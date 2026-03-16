#!/bin/bash
# Role-aware worktree bootstrap.
# Usage: start-role-worktree.sh [author|review|ops]
#        No arguments creates all three role worktrees.
#
# Idempotent: if the worktree already exists, updates it to latest main.
# Writes registry metadata to .claude/runtime/worktree_registry/<role>.json.

set -euo pipefail

MAIN_DIR="$(cd "$(dirname "$0")/../.." && git rev-parse --show-toplevel)"
PARENT_DIR="$(dirname "$MAIN_DIR")"
REPO_NAME="$(basename "$MAIN_DIR")"
REGISTRY_DIR="$MAIN_DIR/.claude/runtime/worktree_registry"
VALID_ROLES="author review ops"

# --- helpers ----------------------------------------------------------------

usage() {
    echo "Usage: $0 [author|review|ops]"
    echo "       No arguments creates all three role worktrees."
    echo ""
    echo "Creates persistent role worktrees at sibling directories:"
    echo "  ${PARENT_DIR}/${REPO_NAME}-author"
    echo "  ${PARENT_DIR}/${REPO_NAME}-review"
    echo "  ${PARENT_DIR}/${REPO_NAME}-ops"
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

now_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

write_registry() {
    local role="$1"
    local wt_path="$2"
    local branch="$3"
    local created="$4"

    mkdir -p "$REGISTRY_DIR"

    cat > "$REGISTRY_DIR/${role}.json" <<EOJSON
{
  "schema_version": 1,
  "role": "${role}",
  "worktree_path": "${wt_path}",
  "branch": "${branch}",
  "class": "persistent",
  "created_at": "${created}",
  "last_active": "$(now_iso)",
  "session_id": null,
  "ttl_hours": null
}
EOJSON
}

# --- bootstrap one role -----------------------------------------------------

bootstrap_role() {
    local role="$1"
    local branch="role/${role}"
    local wt_path="${PARENT_DIR}/${REPO_NAME}-${role}"

    echo "--- ${role} ---"

    # Ensure we are on latest main
    git -C "$MAIN_DIR" fetch origin main --quiet 2>/dev/null || true

    if git -C "$MAIN_DIR" worktree list --porcelain | grep -q "worktree ${wt_path}$"; then
        # Worktree exists — update to latest main
        echo "  Worktree exists at ${wt_path}, updating..."
        git -C "$wt_path" fetch origin main --quiet 2>/dev/null || true
        git -C "$wt_path" rebase origin/main --quiet 2>/dev/null || true
        local created
        created="$(now_iso)"
        if [ -f "$REGISTRY_DIR/${role}.json" ]; then
            # Preserve original created_at from existing registry
            created="$(python3 -c "
import json, sys
try:
    d = json.load(open('${REGISTRY_DIR}/${role}.json'))
    print(d.get('created_at', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")"
            if [ -z "$created" ]; then
                created="$(now_iso)"
            fi
        fi
        write_registry "$role" "$wt_path" "$branch" "$created"
        echo "  Updated and registered."
    else
        # Create branch if needed
        if ! git -C "$MAIN_DIR" rev-parse --verify "$branch" >/dev/null 2>&1; then
            git -C "$MAIN_DIR" branch "$branch" origin/main 2>/dev/null \
                || git -C "$MAIN_DIR" branch "$branch"
        fi

        # Create worktree
        echo "  Creating worktree at ${wt_path}..."
        git -C "$MAIN_DIR" worktree add "$wt_path" "$branch"

        local created
        created="$(now_iso)"
        write_registry "$role" "$wt_path" "$branch" "$created"
        echo "  Created and registered."
    fi

    echo ""
    echo "  Path:   ${wt_path}"
    echo "  Branch: ${branch}"
    echo "  Start:  .claude/scripts/start-agent-role.sh ${role}"
    echo ""
}

# --- main -------------------------------------------------------------------

# Must run from main checkout
CURRENT_TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [ "$CURRENT_TOPLEVEL" != "$MAIN_DIR" ]; then
    echo "Error: Must run from the main checkout at ${MAIN_DIR}"
    echo "Current location: ${CURRENT_TOPLEVEL:-unknown}"
    exit 1
fi

if [ $# -eq 0 ]; then
    echo "Bootstrapping all role worktrees..."
    echo ""
    for role in $VALID_ROLES; do
        bootstrap_role "$role"
    done
    echo "All role worktrees ready."
    echo "Start a role session with: .claude/scripts/start-agent-role.sh <role>"
elif [ $# -eq 1 ]; then
    if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
        usage
        exit 0
    fi
    if ! is_valid_role "$1"; then
        echo "Error: Invalid role '$1'. Must be one of: ${VALID_ROLES}"
        exit 1
    fi
    bootstrap_role "$1"
else
    usage
    exit 1
fi

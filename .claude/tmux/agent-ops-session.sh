#!/bin/bash
# Bootstrap a persistent tmux session with role-based windows.
# Usage: agent-ops-session.sh [session-name]
#
# Creates (or attaches to) a tmux session with four windows:
#   1. author  — ../Bid-Euchre-author worktree
#   2. review  — ../Bid-Euchre-review worktree
#   3. ops     — ../Bid-Euchre-ops worktree
#   4. scratch — main checkout
#
# Idempotent: if the session already exists, attaches to it.

set -euo pipefail

# --- configuration ---------------------------------------------------------

SESSION="${1:-bid-euchre-ops}"

# Locate the main checkout (works from any worktree or the main checkout itself)
MAIN_DIR="$(git worktree list 2>/dev/null | head -1 | awk '{print $1}')"
if [ -z "$MAIN_DIR" ]; then
    echo "Error: Could not determine the main checkout directory."
    echo "Run this script from within the Bid-Euchre repository."
    exit 1
fi

PARENT_DIR="$(dirname "$MAIN_DIR")"
REPO_NAME="$(basename "$MAIN_DIR")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAYOUT_CONF="${SCRIPT_DIR}/agent-ops-layout.conf"

# --- helpers ----------------------------------------------------------------

role_path() {
    local role="$1"
    echo "${PARENT_DIR}/${REPO_NAME}-${role}"
}

window_dir() {
    local role="$1"
    local wt_path
    wt_path="$(role_path "$role")"
    if [ -d "$wt_path" ]; then
        echo "$wt_path"
    else
        echo ""
    fi
}

banner_cmd() {
    local role="$1"
    local upper
    upper="$(echo "$role" | tr '[:lower:]' '[:upper:]')"
    echo "printf '\\n  === %s ROLE ===\\n  Branch: %s\\n  Path:   %s\\n\\n' '${upper}' \"\$(git branch --show-current 2>/dev/null || echo 'N/A')\" \"\$(pwd)\""
}

missing_msg() {
    local role="$1"
    echo "echo ''; echo '  Worktree not found for role: ${role}'; echo '  Create it with:'; echo '    .claude/scripts/start-role-worktree.sh ${role}'; echo ''"
}

# --- preflight --------------------------------------------------------------

if ! command -v tmux >/dev/null 2>&1; then
    echo "Error: tmux is not installed."
    echo "Install with: brew install tmux (macOS) or apt install tmux (Linux)"
    exit 1
fi

# --- idempotent attach ------------------------------------------------------

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '${SESSION}' already exists. Attaching..."
    exec tmux attach-session -t "$SESSION"
fi

# --- create session ---------------------------------------------------------

echo "Creating tmux session: ${SESSION}"

# Source layout configuration if it exists
TMUX_EXTRA_CONF=""
if [ -f "$LAYOUT_CONF" ]; then
    TMUX_EXTRA_CONF="-f ${LAYOUT_CONF}"
fi

# Window 1: author
AUTHOR_DIR="$(window_dir author)"
if [ -n "$AUTHOR_DIR" ]; then
    tmux new-session -d -s "$SESSION" -n "author" -c "$AUTHOR_DIR"
    tmux send-keys -t "${SESSION}:author" "$(banner_cmd author)" Enter
else
    tmux new-session -d -s "$SESSION" -n "author" -c "$MAIN_DIR"
    tmux send-keys -t "${SESSION}:author" "$(missing_msg author)" Enter
fi

# Window 2: review
REVIEW_DIR="$(window_dir review)"
if [ -n "$REVIEW_DIR" ]; then
    tmux new-window -t "$SESSION" -n "review" -c "$REVIEW_DIR"
    tmux send-keys -t "${SESSION}:review" "$(banner_cmd review)" Enter
else
    tmux new-window -t "$SESSION" -n "review" -c "$MAIN_DIR"
    tmux send-keys -t "${SESSION}:review" "$(missing_msg review)" Enter
fi

# Window 3: ops
OPS_DIR="$(window_dir ops)"
if [ -n "$OPS_DIR" ]; then
    tmux new-window -t "$SESSION" -n "ops" -c "$OPS_DIR"
    tmux send-keys -t "${SESSION}:ops" "$(banner_cmd ops)" Enter
else
    tmux new-window -t "$SESSION" -n "ops" -c "$MAIN_DIR"
    tmux send-keys -t "${SESSION}:ops" "$(missing_msg ops)" Enter
fi

# Window 4: scratch (always main checkout)
tmux new-window -t "$SESSION" -n "scratch" -c "$MAIN_DIR"
tmux send-keys -t "${SESSION}:scratch" "$(banner_cmd scratch)" Enter

# Apply layout configuration
if [ -f "$LAYOUT_CONF" ]; then
    tmux source-file "$LAYOUT_CONF"
fi

# Select the first window
tmux select-window -t "${SESSION}:author"

echo "Session '${SESSION}' created with windows: author, review, ops, scratch"
echo "Attaching..."

exec tmux attach-session -t "$SESSION"

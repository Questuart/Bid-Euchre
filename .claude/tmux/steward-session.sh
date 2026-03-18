#!/bin/bash
# Bootstrap a persistent tmux session for the steward dashboard layout.
# Usage: steward-session.sh [session-name]
#
# Creates (or attaches to) a tmux session with:
#   1. dashboard       — 4-pane mission-control view
#      pane 1: author-a
#      pane 2: author-b
#      pane 3: review
#      pane 4: ops
#   2. author-c        — overflow author lane
#   3. author-d        — overflow author lane
#   4. author-scratch  — exploratory Claude lane

set -euo pipefail

SESSION="${1:-steward}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if ! git -C "$MAIN_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: Could not determine the Bid Euchre repository root."
    exit 1
fi

PARENT_DIR="$(dirname "$MAIN_DIR")"
REPO_NAME="$(basename "$MAIN_DIR")"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude || true)}"

if [ -z "$CLAUDE_BIN" ]; then
    echo "Error: Could not find 'claude' in PATH."
    exit 1
fi

AUTHOR_A="${PARENT_DIR}/${REPO_NAME}-steward-author"
AUTHOR_B="${PARENT_DIR}/${REPO_NAME}-steward-author-b"
AUTHOR_C="${PARENT_DIR}/${REPO_NAME}-steward-author-c"
AUTHOR_D="${PARENT_DIR}/${REPO_NAME}-steward-author-d"
AUTHOR_SCRATCH="${PARENT_DIR}/${REPO_NAME}-steward-author-scratch"
REVIEW="${PARENT_DIR}/${REPO_NAME}-steward-review"
MAIN_DIR="$(git -C "$MAIN_DIR" worktree list 2>/dev/null | head -1 | awk '{print $1}')"

ensure_worktree() {
    local path="$1"
    local branch="$2"
    if [ -d "$path" ]; then
        return
    fi
    git -C "$MAIN_DIR" worktree add -b "$branch" "$path" main
}

ensure_review_worktree() {
    if [ -d "$REVIEW" ]; then
        return
    fi
    git -C "$MAIN_DIR" worktree add --detach "$REVIEW" main
}

if ! command -v tmux >/dev/null 2>&1; then
    echo "Error: tmux is not installed."
    echo "Install with: brew install tmux"
    exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    exec caffeinate -dims tmux attach-session -t "$SESSION"
fi

ensure_worktree "$AUTHOR_A" "codex/steward-author"
ensure_worktree "$AUTHOR_B" "codex/steward-author-b"
ensure_worktree "$AUTHOR_C" "codex/steward-author-c"
ensure_worktree "$AUTHOR_D" "codex/steward-author-d"
ensure_worktree "$AUTHOR_SCRATCH" "codex/steward-author-scratch"
ensure_review_worktree

tmux new-session -d -s "$SESSION" -n dashboard -c "$AUTHOR_A" \
    "$CLAUDE_BIN" --name author-a --agent steward-author-a

tmux split-window -h -t "${SESSION}:dashboard" -c "$AUTHOR_B" \
    "$CLAUDE_BIN" --name author-b --agent steward-author-b

tmux split-window -v -t "${SESSION}:dashboard.1" -c "$REVIEW" \
    "$CLAUDE_BIN" --name review --agent steward-review

tmux split-window -v -t "${SESSION}:dashboard.2" -c "$MAIN_DIR" \
    "$CLAUDE_BIN" --name ops --agent steward-ops

tmux select-layout -t "${SESSION}:dashboard" tiled
tmux swap-pane -s "${SESSION}:dashboard.2" -t "${SESSION}:dashboard.4"
tmux swap-pane -s "${SESSION}:dashboard.3" -t "${SESSION}:dashboard.4"
tmux select-pane -t "${SESSION}:dashboard.1" -T author-a
tmux select-pane -t "${SESSION}:dashboard.2" -T author-b
tmux select-pane -t "${SESSION}:dashboard.3" -T review
tmux select-pane -t "${SESSION}:dashboard.4" -T ops

tmux new-window -t "$SESSION" -n author-c -c "$AUTHOR_C" \
    "$CLAUDE_BIN" --name author-c --agent steward-author-c

tmux new-window -t "$SESSION" -n author-d -c "$AUTHOR_D" \
    "$CLAUDE_BIN" --name author-d --agent steward-author-d

tmux new-window -t "$SESSION" -n author-scratch -c "$AUTHOR_SCRATCH" \
    "$CLAUDE_BIN" --name author-scratch --agent steward-author-scratch

tmux select-window -t "${SESSION}:dashboard"

exec caffeinate -dims tmux attach-session -t "$SESSION"

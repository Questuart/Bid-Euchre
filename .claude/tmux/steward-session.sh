#!/bin/bash
# Canonical steward session bootstrap.
# Usage: steward-session.sh [session-name]
#
# Creates (or attaches to) a tmux session with:
#   1. dashboard       -- 4-pane mission-control view
#      pane 1: author-a
#      pane 2: author-b
#      pane 3: review
#      pane 4: ops
#   2. author-c        -- overflow author lane
#   3. author-d        -- overflow author lane
#   4. author-scratch  -- exploratory Claude lane
#
# Writes v2 worktree registry metadata for each launched lane.
# See docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md for the full model.

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

update_last_active() {
    # Update last_active timestamp in all steward registry files.
    local registry_dir="$MAIN_DIR/.claude/runtime/worktree_registry"
    [ -d "$registry_dir" ] || return 0
    local now
    now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    for f in "$registry_dir"/*.json; do
        [ -f "$f" ] || continue
        python3 -c "
import json, sys
try:
    with open('$f') as fh:
        d = json.load(fh)
    d['last_active'] = '$now'
    with open('$f', 'w') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\n')
except Exception:
    pass
" 2>/dev/null || true
    done
}

# --- lane metadata ----------------------------------------------------------

REGISTRY_DIR="$MAIN_DIR/.claude/runtime/worktree_registry"

now_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Write a v2 worktree registry entry for a steward lane.
# Args: lane_id lane_class worktree_path branch tmux_window [tmux_pane]
write_lane_metadata() {
    local lane_id="$1"
    local lane_class="$2"
    local wt_path="$3"
    local branch="$4"
    local tmux_window="$5"
    local tmux_pane="${6:-null}"
    local now
    now="$(now_iso)"

    mkdir -p "$REGISTRY_DIR"

    # Preserve created_at from existing entry if present
    local created="$now"
    if [ -f "$REGISTRY_DIR/${lane_id}.json" ]; then
        local prev
        prev="$(python3 -c "
import json
try:
    d = json.load(open('${REGISTRY_DIR}/${lane_id}.json'))
    print(d.get('created_at', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")"
        if [ -n "$prev" ]; then
            created="$prev"
        fi
    fi

    # Quote tmux_pane if it's not null
    local pane_val="null"
    if [ "$tmux_pane" != "null" ]; then
        pane_val="\"${tmux_pane}\""
    fi

    cat > "$REGISTRY_DIR/${lane_id}.json" <<EOJSON
{
  "schema_version": 2,
  "lane_id": "${lane_id}",
  "lane_class": "${lane_class}",
  "worktree_path": "${wt_path}",
  "branch": "${branch}",
  "class": "persistent",
  "created_at": "${created}",
  "last_active": "${now}",
  "session_id": null,
  "ttl_hours": null,
  "display_name": null,
  "tmux_session": "${SESSION}",
  "tmux_window": "${tmux_window}",
  "tmux_pane": ${pane_val},
  "cmux_workspace_ref": null,
  "cmux_surface_ref": null,
  "legacy_role": null
}
EOJSON
}

if ! command -v tmux >/dev/null 2>&1; then
    echo "Error: tmux is not installed."
    echo "Install with: brew install tmux"
    exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    update_last_active
    if [ "${STEWARD_DETACHED:-}" = "1" ]; then
        echo "Session '${SESSION}' already exists (detached mode, not attaching)."
        exit 0
    fi
    exec caffeinate -dims tmux attach-session -t "$SESSION"
fi

ensure_worktree "$AUTHOR_A" "codex/steward-author"
ensure_worktree "$AUTHOR_B" "codex/steward-author-b"
ensure_worktree "$AUTHOR_C" "codex/steward-author-c"
ensure_worktree "$AUTHOR_D" "codex/steward-author-d"
ensure_worktree "$AUTHOR_SCRATCH" "codex/steward-author-scratch"
ensure_review_worktree

# Write v2 registry metadata for each lane
write_lane_metadata "author-a"       "author"  "$AUTHOR_A"       "codex/steward-author"         "dashboard" "1"
write_lane_metadata "author-b"       "author"  "$AUTHOR_B"       "codex/steward-author-b"       "dashboard" "2"
write_lane_metadata "review"         "review"  "$REVIEW"         "detached"                     "dashboard" "3"
write_lane_metadata "ops"            "ops"     "$MAIN_DIR"       "--"                           "dashboard" "4"
write_lane_metadata "author-c"       "author"  "$AUTHOR_C"       "codex/steward-author-c"       "author-c"
write_lane_metadata "author-d"       "author"  "$AUTHOR_D"       "codex/steward-author-d"       "author-d"
write_lane_metadata "author-scratch" "scratch" "$AUTHOR_SCRATCH" "codex/steward-author-scratch"  "author-scratch"

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

update_last_active

if [ "${STEWARD_DETACHED:-}" = "1" ]; then
    echo "Session '${SESSION}' created (detached mode, not attaching)."
    exit 0
fi

exec caffeinate -dims tmux attach-session -t "$SESSION"

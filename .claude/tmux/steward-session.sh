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
#   2. orchestrator    -- single intake point for delegating work
#   3. author-c        -- overflow author lane
#   4. author-d        -- overflow author lane
#   5. author-scratch  -- exploratory Claude lane
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

# ---------------------------------------------------------------------------
# Filesystem boundary validation
# ---------------------------------------------------------------------------
# Worktree paths must be within PARENT_DIR (the parent of the main checkout).
# This is a repo-level guard — it does not claim OS-level sandboxing.

validate_worktree_path() {
    local path="$1"
    local resolved
    # Resolve the path (create parent dirs first if needed for realpath)
    if [ -e "$path" ]; then
        resolved="$(cd "$path" && pwd -P)"
    else
        # Path doesn't exist yet — resolve the parent
        local parent
        parent="$(dirname "$path")"
        if [ ! -d "$parent" ]; then
            echo "Error: parent directory does not exist: $parent" >&2
            return 1
        fi
        resolved="$(cd "$parent" && pwd -P)/$(basename "$path")"
    fi

    local parent_resolved
    parent_resolved="$(cd "$PARENT_DIR" && pwd -P)"

    case "$resolved" in
        "${parent_resolved}"/*)
            return 0
            ;;
        *)
            echo "Error: worktree path is outside the repo boundary: $resolved" >&2
            echo "  Expected path under: $parent_resolved" >&2
            return 1
            ;;
    esac
}

ensure_worktree() {
    local path="$1"
    local branch="$2"
    validate_worktree_path "$path" || exit 1
    if [ -d "$path" ]; then
        return
    fi
    git -C "$MAIN_DIR" worktree add -b "$branch" "$path" main
}

ensure_review_worktree() {
    validate_worktree_path "$REVIEW" || exit 1
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
fpath, timestamp = sys.argv[1], sys.argv[2]
try:
    with open(fpath) as fh:
        d = json.load(fh)
    d['last_active'] = timestamp
    with open(fpath, 'w') as fh:
        json.dump(d, fh, indent=2)
        fh.write('\n')
except Exception:
    pass
" "$f" "$now" 2>/dev/null || true
    done
}

# --- lane metadata ----------------------------------------------------------

REGISTRY_DIR="$MAIN_DIR/.claude/runtime/worktree_registry"

now_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Write a v2 worktree registry entry for a steward lane.
# Args: lane_id lane_class worktree_path branch tmux_window [tmux_pane] [visibility] [display_name]
write_lane_metadata() {
    local lane_id="$1"
    local lane_class="$2"
    local wt_path="$3"
    local branch="$4"
    local tmux_window="$5"
    local tmux_pane="${6:-null}"
    local visibility="${7:-null}"
    local display_name="${8:-null}"
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

    # Quote visibility if it's not null
    local vis_val="null"
    if [ "$visibility" != "null" ]; then
        vis_val="\"${visibility}\""
    fi

    # Quote display_name if it's not null
    local dn_val="null"
    if [ "$display_name" != "null" ]; then
        dn_val="\"${display_name}\""
    fi

    # Derive session_handle from lane_id
    local session_handle="\"steward:${lane_id}\""

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
  "display_name": ${dn_val},
  "tmux_session": "${SESSION}",
  "tmux_window": "${tmux_window}",
  "tmux_pane": ${pane_val},
  "cmux_workspace_ref": null,
  "cmux_surface_ref": null,
  "legacy_role": null,
  "session_handle": ${session_handle},
  "visibility": ${vis_val}
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
# Dashboard panes: visibility=foreground; off-dashboard windows: visibility=background
write_lane_metadata "author-a"       "author"  "$AUTHOR_A"       "codex/steward-author"         "dashboard" "1"    "foreground" "Author A"
write_lane_metadata "author-b"       "author"  "$AUTHOR_B"       "codex/steward-author-b"       "dashboard" "2"    "foreground" "Author B"
write_lane_metadata "review"         "review"  "$REVIEW"         "detached"                     "dashboard" "3"    "foreground" "Review"
write_lane_metadata "ops"            "ops"     "$MAIN_DIR"       "--"                           "dashboard" "4"    "foreground" "Ops"
write_lane_metadata "orchestrator"   "orchestrator" "$MAIN_DIR" "--"                           "orchestrator" "null" "foreground" "Orchestrator"
write_lane_metadata "author-c"       "author"  "$AUTHOR_C"       "codex/steward-author-c"       "author-c"  "null" "background" "Author C"
write_lane_metadata "author-d"       "author"  "$AUTHOR_D"       "codex/steward-author-d"       "author-d"  "null" "background" "Author D"
write_lane_metadata "author-scratch" "scratch" "$AUTHOR_SCRATCH" "codex/steward-author-scratch"  "author-scratch" "null" "background" "Scratch"

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

tmux new-window -t "$SESSION" -n orchestrator -c "$MAIN_DIR" \
    "$CLAUDE_BIN" --name orchestrator --agent steward-orchestrator

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

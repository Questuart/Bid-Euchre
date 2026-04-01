#!/bin/bash
# Canonical steward session bootstrap — 5-window layout.
# Usage: steward-session.sh [session-name]
#
# Creates (or attaches to) a tmux session with 5 windows:
#
#   Window 1 — central-ops (3 panes, main-vertical layout)
#     .1  orchestrator      -- single intake point (large left pane)
#     .2  ops               -- operator monitoring lane
#     .3  review            -- independent review lane
#
#   Window 2 — analyst (4 panes, tiled)
#     .1  analyst-a        -- primary analyst lane (shaping, triage)
#     .2  analyst-b        -- secondary analyst lane
#     .3  analyst-c        -- overflow analyst lane
#     .4  analyst-d        -- overflow analyst lane
#
#   Window 3 — platform (4 panes, tiled)
#     .1  author-a        -- primary platform author lane
#     .2  author-b        -- secondary platform author lane
#     .3  author-c        -- overflow platform author lane
#     .4  author-d        -- overflow platform author lane
#
#   Window 4 — browser (4 panes, tiled)
#     .1  brws-author-a   -- primary browser-game author lane
#     .2  brws-author-b   -- secondary browser-game author lane
#     .3  brws-author-c   -- overflow browser-game author lane
#     .4  brws-author-d   -- overflow browser-game author lane
#
#   Window 5 — flex (4 panes, tiled)
#     .1  flex-a          -- domain-agnostic overflow lane
#     .2  flex-b          -- domain-agnostic overflow lane
#     .3  flex-c          -- domain-agnostic overflow lane
#     .4  flex-d          -- domain-agnostic overflow lane
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

# Telegram channel configuration (Platform-8a).
# Auto-detect: if the Telegram plugin is installed and enabled, default to on.
# Override: set STEWARD_TELEGRAM_ENABLED=0 to explicitly disable, or =1 to force enable.
# Only the orchestrator lane gets the channel flag — author lanes remain
# tmux-only per SP-4-01 key decisions.
if [ -z "${STEWARD_TELEGRAM_ENABLED+x}" ]; then
    _plugins="$("$CLAUDE_BIN" plugins list 2>/dev/null || true)"
    if printf '%s\n' "$_plugins" | grep -q 'telegram' && \
       ! printf '%s\n' "$_plugins" | grep -A4 'telegram' | grep -q 'disabled'; then
        STEWARD_TELEGRAM_ENABLED="1"
    else
        STEWARD_TELEGRAM_ENABLED="0"
    fi
    unset _plugins
fi

# Platform pool worktrees
AUTHOR_A="${PARENT_DIR}/${REPO_NAME}-steward-author"
AUTHOR_B="${PARENT_DIR}/${REPO_NAME}-steward-author-b"
AUTHOR_C="${PARENT_DIR}/${REPO_NAME}-steward-author-c"
AUTHOR_D="${PARENT_DIR}/${REPO_NAME}-steward-author-d"

# Browser-game pool worktrees
BRWS_A="${PARENT_DIR}/${REPO_NAME}-steward-brws-author-a"
BRWS_B="${PARENT_DIR}/${REPO_NAME}-steward-brws-author-b"
BRWS_C="${PARENT_DIR}/${REPO_NAME}-steward-brws-author-c"
BRWS_D="${PARENT_DIR}/${REPO_NAME}-steward-brws-author-d"

# Analyst pool worktrees (analyst-a reuses existing steward-analyst)
ANALYST_A="${PARENT_DIR}/${REPO_NAME}-steward-analyst"
ANALYST_B="${PARENT_DIR}/${REPO_NAME}-steward-analyst-b"
ANALYST_C="${PARENT_DIR}/${REPO_NAME}-steward-analyst-c"
ANALYST_D="${PARENT_DIR}/${REPO_NAME}-steward-analyst-d"

# Flex pool worktrees
FLEX_A="${PARENT_DIR}/${REPO_NAME}-steward-flex-a"
FLEX_B="${PARENT_DIR}/${REPO_NAME}-steward-flex-b"
FLEX_C="${PARENT_DIR}/${REPO_NAME}-steward-flex-c"
FLEX_D="${PARENT_DIR}/${REPO_NAME}-steward-flex-d"

# Control plane
REVIEW="${PARENT_DIR}/${REPO_NAME}-steward-review"
OPS="${PARENT_DIR}/${REPO_NAME}-steward-ops"
MAIN_DIR="$(git -C "$MAIN_DIR" worktree list 2>/dev/null | head -1 | awk '{print $1}')"

# ---------------------------------------------------------------------------
# Filesystem boundary validation
# ---------------------------------------------------------------------------
# Worktree paths must be within PARENT_DIR (the parent of the main checkout).
# This is a repo-level guard — it does not claim OS-level sandboxing.

# Merge a JSON fragment into a settings.local.json file using jq.
# If the file does not exist, create it.  If it does, deep-merge so that
# existing keys (e.g. user overrides) are preserved.
# Args: file_path json_fragment
merge_settings_local() {
    local file_path="$1"
    local fragment="$2"
    local dir
    dir="$(dirname "$file_path")"
    mkdir -p "$dir"
    if [ -f "$file_path" ]; then
        local merged
        merged="$(jq --argjson frag "$fragment" '. * $frag' "$file_path")" || {
            echo "merge_settings_local: jq merge failed for $file_path" >&2
            return 1
        }
        printf '%s\n' "$merged" > "$file_path"
    else
        printf '%s\n' "$fragment" | jq '.' > "$file_path" || {
            echo "merge_settings_local: jq format failed for $file_path" >&2
            return 1
        }
    fi
}

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

ensure_detached_worktree() {
    local path="$1"
    validate_worktree_path "$path" || exit 1
    if [ -d "$path" ]; then
        return
    fi
    git -C "$MAIN_DIR" worktree add --detach "$path" main
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

# Platform pool
ensure_worktree "$AUTHOR_A" "codex/steward-author"
ensure_worktree "$AUTHOR_B" "codex/steward-author-b"
ensure_worktree "$AUTHOR_C" "codex/steward-author-c"
ensure_worktree "$AUTHOR_D" "codex/steward-author-d"

# Browser-game pool
ensure_worktree "$BRWS_A" "codex/steward-brws-author-a"
ensure_worktree "$BRWS_B" "codex/steward-brws-author-b"
ensure_worktree "$BRWS_C" "codex/steward-brws-author-c"
ensure_worktree "$BRWS_D" "codex/steward-brws-author-d"

# Analyst pool (detached — shaping lanes, not code-authoring)
ensure_detached_worktree "$ANALYST_A"
ensure_detached_worktree "$ANALYST_B"
ensure_detached_worktree "$ANALYST_C"
ensure_detached_worktree "$ANALYST_D"

# Flex pool
ensure_worktree "$FLEX_A" "codex/steward-flex-a"
ensure_worktree "$FLEX_B" "codex/steward-flex-b"
ensure_worktree "$FLEX_C" "codex/steward-flex-c"
ensure_worktree "$FLEX_D" "codex/steward-flex-d"

# Control plane
ensure_detached_worktree "$REVIEW"
ensure_detached_worktree "$OPS"

# Write v2 registry metadata for each lane.
# tmux_window = group name, tmux_pane = 1-based pane index within the window.
# Pane target format: ${SESSION}:${tmux_window}.${tmux_pane}
# Indices are 1-based to match tmux pane-base-index=1.

# Central ops  (window: central-ops, panes 1-3, main-vertical layout)
# Note: pane indices are 1-based to match tmux pane-base-index=1.
write_lane_metadata "orchestrator"   "orchestrator" "$MAIN_DIR"       "--"                              "central-ops" "1" "foreground" "Orchestrator"
write_lane_metadata "ops"            "ops"          "$OPS"            "detached"                        "central-ops" "2" "foreground" "Ops"
write_lane_metadata "review"         "review"       "$REVIEW"         "detached"                        "central-ops" "3" "foreground" "Review"

# Analyst pool  (window: analyst, panes 1-4, tiled)
write_lane_metadata "analyst-a"      "analyst"      "$ANALYST_A"      "detached"                        "analyst" "1" "background" "Analyst A"
write_lane_metadata "analyst-b"      "analyst"      "$ANALYST_B"      "detached"                        "analyst" "2" "background" "Analyst B"
write_lane_metadata "analyst-c"      "analyst"      "$ANALYST_C"      "detached"                        "analyst" "3" "background" "Analyst C"
write_lane_metadata "analyst-d"      "analyst"      "$ANALYST_D"      "detached"                        "analyst" "4" "background" "Analyst D"

# Platform workers  (window: platform, panes 1-4)
write_lane_metadata "author-a"       "author"       "$AUTHOR_A"       "codex/steward-author"            "platform" "1" "background" "Author A"
write_lane_metadata "author-b"       "author"       "$AUTHOR_B"       "codex/steward-author-b"          "platform" "2" "background" "Author B"
write_lane_metadata "author-c"       "author"       "$AUTHOR_C"       "codex/steward-author-c"          "platform" "3" "background" "Author C"
write_lane_metadata "author-d"       "author"       "$AUTHOR_D"       "codex/steward-author-d"          "platform" "4" "background" "Author D"

# Browser-game workers  (window: browser, panes 1-4)
write_lane_metadata "brws-author-a"  "author"       "$BRWS_A"         "codex/steward-brws-author-a"     "browser" "1" "background" "Brws Author A"
write_lane_metadata "brws-author-b"  "author"       "$BRWS_B"         "codex/steward-brws-author-b"     "browser" "2" "background" "Brws Author B"
write_lane_metadata "brws-author-c"  "author"       "$BRWS_C"         "codex/steward-brws-author-c"     "browser" "3" "background" "Brws Author C"
write_lane_metadata "brws-author-d"  "author"       "$BRWS_D"         "codex/steward-brws-author-d"     "browser" "4" "background" "Brws Author D"

# Flex pool  (window: flex, panes 1-3, tiled)
write_lane_metadata "flex-a"         "flex"          "$FLEX_A"          "codex/steward-flex-a"           "flex" "1" "background" "Flex A"
write_lane_metadata "flex-b"         "flex"          "$FLEX_B"          "codex/steward-flex-b"           "flex" "2" "background" "Flex B"
write_lane_metadata "flex-c"         "flex"          "$FLEX_C"          "codex/steward-flex-c"           "flex" "3" "background" "Flex C"
write_lane_metadata "flex-d"         "flex"          "$FLEX_D"          "codex/steward-flex-d"           "flex" "4" "background" "Flex D"

# ---------------------------------------------------------------------------
# Orchestrator channel flags (Platform-8a)
# ---------------------------------------------------------------------------
# When STEWARD_TELEGRAM_ENABLED=1 the orchestrator pane gets
# --channels so the Telegram plugin connects on boot.
# All other panes launch without --channels (tmux-only).
# STEWARD_CHANNELS is propagated via tmux set-environment (not shell export)
# so that panes spawned by the tmux server can read it.
#
# Single-receiver enforcement (#1824):
# The Telegram plugin is NOT enabled in the committed .claude/settings.json
# (that would cause every lane to spawn its own polling instance).  Instead,
# this script writes a per-worktree .claude/settings.local.json that enables
# the plugin ONLY in the orchestrator's worktree.  Other lanes never get the
# plugin, so the orchestrator is the sole inbound message receiver.
ORCH_CHANNEL_FLAGS=""
STEWARD_CHANNELS=""
if [ "$STEWARD_TELEGRAM_ENABLED" = "1" ]; then
    ORCH_CHANNEL_FLAGS="--channels plugin:telegram@claude-plugins-official"
    STEWARD_CHANNELS="telegram"

    # Provision settings.local.json in the orchestrator worktree so the
    # Telegram plugin is enabled only there.  The file is gitignored.
    # Uses jq merge so that re-runs update enabledPlugins even when the
    # file already exists (Bug 1 — idempotency guard blocked updates).
    merge_settings_local "${MAIN_DIR}/.claude/settings.local.json" \
        '{"enabledPlugins":{"telegram@claude-plugins-official":true}}'

    # Negative enforcement (Bug 2): explicitly disable plugins on every
    # non-orchestrator worktree.  Without this override the globally-installed
    # plugin auto-enables for every lane, causing competing poll instances.
    for _wt in "$AUTHOR_A" "$AUTHOR_B" "$AUTHOR_C" "$AUTHOR_D" \
               "$BRWS_A" "$BRWS_B" "$BRWS_C" "$BRWS_D" \
               "$ANALYST_A" "$ANALYST_B" "$ANALYST_C" "$ANALYST_D" \
               "$FLEX_A" "$FLEX_B" "$FLEX_C" "$FLEX_D" \
               "$REVIEW" "$OPS"; do
        if [ -d "$_wt" ]; then
            merge_settings_local "$_wt/.claude/settings.local.json" \
                '{"enabledPlugins":{"telegram@claude-plugins-official":false}}'
        fi
    done
    unset _wt
fi

# ---------------------------------------------------------------------------
# Window + pane creation — 5 windows
#   central-ops: 3 panes main-vertical
#   analyst: 4 panes tiled
#   platform: 4 panes tiled
#   browser: 4 panes tiled
#   flex: 4 panes tiled
# ---------------------------------------------------------------------------

# --- Window 1: central-ops (3 panes, main-vertical) ---
tmux new-session -d -s "$SESSION" -n central-ops -c "$MAIN_DIR" \
    "$CLAUDE_BIN" --name orchestrator --agent steward-orchestrator $ORCH_CHANNEL_FLAGS

# Propagate channel config into the tmux session environment so all panes
# can read it.  Shell `export` only affects the launcher process; tmux panes
# are spawned by the tmux server and need `set-environment` instead.
if [ -n "$STEWARD_CHANNELS" ]; then
    tmux set-environment -t "$SESSION" STEWARD_CHANNELS "$STEWARD_CHANNELS"
fi
tmux set-environment -t "$SESSION" STEWARD_TELEGRAM_ENABLED "$STEWARD_TELEGRAM_ENABLED"
# Bug 3: Set STEWARD_TELEGRAM_RECEIVER so the orchestrator pane's
# telegram_filter.is_telegram_receiver() returns True.  Non-orchestrator
# panes do not receive this env var (tmux set-environment is session-global,
# but only the orchestrator's process reads it via the filter module).
if [ "$STEWARD_TELEGRAM_ENABLED" = "1" ]; then
    tmux set-environment -t "$SESSION" STEWARD_TELEGRAM_RECEIVER "1"
fi

tmux split-window -t "${SESSION}:central-ops" -c "$OPS" \
    "$CLAUDE_BIN" --name ops --agent steward-ops
tmux split-window -t "${SESSION}:central-ops" -c "$REVIEW" \
    "$CLAUDE_BIN" --name review --agent steward-review
tmux select-layout -t "${SESSION}:central-ops" main-vertical

# --- Window 2: analyst (4 panes, tiled) ---
tmux new-window -t "$SESSION" -n analyst -c "$ANALYST_A" \
    "$CLAUDE_BIN" --name analyst-a --agent steward-analyst
tmux split-window -t "${SESSION}:analyst" -c "$ANALYST_B" \
    "$CLAUDE_BIN" --name analyst-b --agent steward-analyst
tmux split-window -t "${SESSION}:analyst" -c "$ANALYST_C" \
    "$CLAUDE_BIN" --name analyst-c --agent steward-analyst
tmux split-window -t "${SESSION}:analyst" -c "$ANALYST_D" \
    "$CLAUDE_BIN" --name analyst-d --agent steward-analyst
tmux select-layout -t "${SESSION}:analyst" tiled

# --- Window 3: platform ---
tmux new-window -t "$SESSION" -n platform -c "$AUTHOR_A" \
    "$CLAUDE_BIN" --name author-a --agent steward-author-a
tmux split-window -t "${SESSION}:platform" -c "$AUTHOR_B" \
    "$CLAUDE_BIN" --name author-b --agent steward-author-b
tmux split-window -t "${SESSION}:platform" -c "$AUTHOR_C" \
    "$CLAUDE_BIN" --name author-c --agent steward-author-c
tmux split-window -t "${SESSION}:platform" -c "$AUTHOR_D" \
    "$CLAUDE_BIN" --name author-d --agent steward-author-d
tmux select-layout -t "${SESSION}:platform" tiled

# --- Window 4: browser ---
tmux new-window -t "$SESSION" -n browser -c "$BRWS_A" \
    "$CLAUDE_BIN" --name brws-author-a --agent steward-brws-author-a
tmux split-window -t "${SESSION}:browser" -c "$BRWS_B" \
    "$CLAUDE_BIN" --name brws-author-b --agent steward-brws-author-b
tmux split-window -t "${SESSION}:browser" -c "$BRWS_C" \
    "$CLAUDE_BIN" --name brws-author-c --agent steward-brws-author-c
tmux split-window -t "${SESSION}:browser" -c "$BRWS_D" \
    "$CLAUDE_BIN" --name brws-author-d --agent steward-brws-author-d
tmux select-layout -t "${SESSION}:browser" tiled

# --- Window 5: flex (4 panes, tiled) ---
tmux new-window -t "$SESSION" -n flex -c "$FLEX_A" \
    "$CLAUDE_BIN" --name flex-a --agent steward-flex-a
tmux split-window -t "${SESSION}:flex" -c "$FLEX_B" \
    "$CLAUDE_BIN" --name flex-b --agent steward-flex-b
tmux split-window -t "${SESSION}:flex" -c "$FLEX_C" \
    "$CLAUDE_BIN" --name flex-c --agent steward-flex-c
tmux split-window -t "${SESSION}:flex" -c "$FLEX_D" \
    "$CLAUDE_BIN" --name flex-d --agent steward-flex-d
tmux select-layout -t "${SESSION}:flex" tiled

# Auto-launch ops monitoring loop (SP-3-08).
# Wait briefly for the claude process to initialize, then send the /loop
# command.  Best-effort — if it fails the ops agent can start it manually.
# Target: central-ops window, pane 2 (ops lane).
# Note: pane-base-index=1, so orchestrator=.1, ops=.2, review=.3.
(
    sleep 10
    tmux send-keys -t "${SESSION}:central-ops.2" \
        "/loop 3m uv run python scripts/internal/ops.py monitor" Enter
) &

# Auto-launch merged-PR review loop on the review pane.
# Triggers the review agent's startup behavior: discover recent merges,
# review diffs, triage findings, then poll every 15 minutes.
# Best-effort — if it fails the review agent can start it manually.
# Target: central-ops window, pane 3 (review lane).
(
    sleep 15
    tmux send-keys -t "${SESSION}:central-ops.3" \
        "Review recently merged PRs and triage findings. Set up a 15m recurring poll." Enter
) &

tmux select-window -t "${SESSION}:central-ops"

update_last_active

if [ "${STEWARD_DETACHED:-}" = "1" ]; then
    echo "Session '${SESSION}' created (detached mode, not attaching)."
    exit 0
fi

exec caffeinate -dims tmux attach-session -t "$SESSION"

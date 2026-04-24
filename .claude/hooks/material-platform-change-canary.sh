#!/usr/bin/env bash
# PostToolUse hook: trigger a `/run-canary --trigger=material-change` run
# when a PR merge touches one of the "material platform change"
# trigger paths declared in canary_scenarios/dogfood.md §8.
#
# Spec: plans/steward_platform/8_primitive_H/shaping.md §5.5 + §13.2 risk #4.
#
# Trigger-path list (dogfood.md §8):
#   - .claude/skills/**
#   - .claude/hooks/**
#   - src/bid_euchre/ops/core/**
#   - scripts/internal/review_driver.py
#   - src/bid_euchre/ops/dashboard.py
#   - .claude/rules/prompt_policy/**
#
# Self-exclusion (shape §13.2 risk #4):
#   - If the merged PR carries the label `canary-rollback-pr`, do not fire.
#     That label is attached to any revert-PR opened by the canary runner,
#     preventing recursive canary triggers on the canary's own rollback.
#
# Idempotency (checklist row #10):
#   - Hook logs its before/after state at .claude/runtime/canary_state/hook_log.jsonl.
#   - Each PR is processed at-most-once via a sentinel file at
#     .claude/runtime/canary_state/hook_seen/<PR#>.
#   - Second invocation for the same PR is observable as a "already-fired" log
#     entry rather than a duplicate canary dispatch.
#
# Best-effort: failures here do not block the merge.

set -euo pipefail

# Read PostToolUse JSON payload from stdin
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_response.exit_code // 0' 2>/dev/null || echo "0")

# Guard: only fire on successful `gh pr merge`
if [[ "$COMMAND" != *"gh pr merge"* ]] || [[ "$EXIT_CODE" != "0" ]]; then
    exit 0
fi

STATE_DIR=".claude/runtime/canary_state"
SEEN_DIR="$STATE_DIR/hook_seen"
LOG_FILE="$STATE_DIR/hook_log.jsonl"
mkdir -p "$SEEN_DIR"

_log() {
    # $1 status, $2 reason (JSON-safe), $3 pr_num, $4 changed_paths (CSV)
    local ts
    ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    printf '{"ts":"%s","hook":"material-platform-change-canary","status":"%s","reason":"%s","pr":"%s","paths":"%s"}\n' \
        "$ts" "$1" "$2" "$3" "$4" >> "$LOG_FILE" || true
}

# Extract PR number
MERGE_ARG=$(echo "$COMMAND" | sed -n 's/.*gh pr merge[[:space:]]\{1,\}\([^[:space:]]\{1,\}\).*/\1/p')
PR_NUM=""
if [[ "$MERGE_ARG" =~ ^[0-9]+$ ]]; then
    PR_NUM="$MERGE_ARG"
elif [[ "$MERGE_ARG" =~ /pull/([0-9]+) ]]; then
    PR_NUM="${BASH_REMATCH[1]}"
fi
if [ -z "$PR_NUM" ]; then
    PR_NUM=$(echo "$INPUT" | jq -r '.tool_response.stdout // ""' 2>/dev/null \
        | grep -oE '#[0-9]+' | grep -oE '[0-9]+' | head -1 || echo "")
fi

if [ -z "$PR_NUM" ]; then
    _log "skipped" "no_pr_number_parsed" "" ""
    exit 0
fi

# Idempotency: at-most-once per PR (row #10).
SEEN_FILE="$SEEN_DIR/$PR_NUM"
if [ -f "$SEEN_FILE" ]; then
    _log "already_fired" "sentinel_exists" "$PR_NUM" ""
    exit 0
fi

# Self-exclusion: skip canary rollback PRs.
if command -v gh >/dev/null 2>&1; then
    LABELS_JSON=$(gh pr view "$PR_NUM" --json labels 2>/dev/null || echo "")
    if [[ -n "$LABELS_JSON" ]] && echo "$LABELS_JSON" \
        | grep -q '"name"[[:space:]]*:[[:space:]]*"canary-rollback-pr"' ; then
        touch "$SEEN_FILE"
        _log "skipped" "canary_rollback_pr_label" "$PR_NUM" ""
        exit 0
    fi
fi

# Compute changed paths for this PR.
CHANGED_PATHS=""
if command -v gh >/dev/null 2>&1; then
    CHANGED_PATHS=$(gh pr view "$PR_NUM" --json files --jq '.files[].path' 2>/dev/null \
        | tr '\n' ',' | sed 's/,$//' || echo "")
fi

# Evaluate trigger-path list (dogfood.md §8).
MATCHED_PATHS=""
if [ -n "$CHANGED_PATHS" ]; then
    IFS=',' read -ra PATHS <<< "$CHANGED_PATHS"
    for p in "${PATHS[@]}"; do
        case "$p" in
            .claude/skills/*) MATCHED_PATHS+="$p,";;
            .claude/hooks/*) MATCHED_PATHS+="$p,";;
            src/bid_euchre/ops/core/*) MATCHED_PATHS+="$p,";;
            scripts/internal/review_driver.py) MATCHED_PATHS+="$p,";;
            src/bid_euchre/ops/dashboard.py) MATCHED_PATHS+="$p,";;
            .claude/rules/prompt_policy/*) MATCHED_PATHS+="$p,";;
        esac
    done
    MATCHED_PATHS="${MATCHED_PATHS%,}"
fi

if [ -z "$MATCHED_PATHS" ]; then
    touch "$SEEN_FILE"
    _log "skipped" "no_material_paths" "$PR_NUM" "$CHANGED_PATHS"
    exit 0
fi

# Dispatch the canary run (best-effort; hook must not block merge).
# Pass --changed-paths so the canary_packet records the trigger reason.
if uv run python tests/reliability/canaries/dogfood_v1.py \
    --trigger material-change \
    --changed-paths "$MATCHED_PATHS" >/dev/null 2>&1 & disown ; then
    touch "$SEEN_FILE"
    _log "fired" "material_change_paths_matched" "$PR_NUM" "$MATCHED_PATHS"
else
    _log "dispatch_failed" "canary_runner_nonzero" "$PR_NUM" "$MATCHED_PATHS"
fi

exit 0

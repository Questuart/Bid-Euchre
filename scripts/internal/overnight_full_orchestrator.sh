#!/bin/bash
# Overnight FULL Orchestrator (Sequential — safe for 16GB M3)
#
# Runs all 3 pre-R3 rungs SEQUENTIALLY. Each run_rung.py handles:
#   - Step 1: dataset generation (holistic, iterates dataset seeds internally)
#   - Steps 2-5: per-seed training/eval (iterates run seeds [42,123,456])
#   - Steps 6-9: holistic reporting + advance check
#
# Usage: nohup bash scripts/internal/overnight_full_orchestrator.sh > /tmp/overnight_orchestrator.log 2>&1 &
#
# Estimated time: ~6-9 hours total (sequential)
# (run_rung.py is idempotent — safe to restart if interrupted)

set -uo pipefail  # no -e: we want to continue on individual failures

WORKTREE="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"
LOG="/tmp/overnight_orchestrator.log"
HEARTBEAT="/tmp/overnight_orchestrator_heartbeat"
RUNGS=(r0 r1 r2)

cd "$WORKTREE"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ORCH] $*" | tee -a "$LOG"
}

heartbeat() {
    date '+%Y-%m-%d %H:%M:%S' > "$HEARTBEAT"
}

run_rung() {
    local rung=$1
    local run_log="/tmp/full_${rung}.log"

    log "--- Starting $rung (all seeds via MODE_SEEDS) ---"
    heartbeat

    # run_rung.py handles multi-seed dispatch internally.
    # Step 1 uses MODE_DATASET_SEEDS; Steps 2-5 use MODE_SEEDS.
    uv run python scripts/internal/run_rung.py \
        --rung "$rung" --mode full \
        > "$run_log" 2>&1
    local rc=$?

    if [ $rc -eq 0 ]; then
        log "  $rung: SUCCESS (exit code 0)"
    else
        log "  $rung: FAILED (exit code $rc) — see $run_log"
    fi

    heartbeat
    return $rc
}

run_advance_checks() {
    log "Running advance checks for all rungs..."

    for rung in "${RUNGS[@]}"; do
        log "  Advance check: $rung"
        uv run python scripts/internal/generate_advance_check.py \
            --rung "$rung" --mode full \
            --hypotheses "plans/arc_d_v2/${rung}/hypotheses.json" \
            --tables-dir "docs/04_reports/arc_d_v2/${rung}/full/tables" \
            --output "plans/arc_d_v2/${rung}/advance_check_full.json" \
            >> "$LOG" 2>&1 || log "WARNING: advance check failed for $rung"
    done
}

# ============================================================
# Main execution — one rung at a time, multi-seed handled internally
# ============================================================

log "========================================="
log "Overnight FULL Orchestrator (sequential)"
log "Working directory: $WORKTREE"
log "Rungs: ${RUNGS[*]}"
log "Dataset seeds: 1001-1010 (10 shards × 5000 = 50000 deals)"
log "Run seeds: 42, 123, 456 (3 train/val/test splits)"
log "========================================="

failed=0
completed=0
total=${#RUNGS[@]}

for rung in "${RUNGS[@]}"; do
    if run_rung "$rung"; then
        completed=$((completed + 1))
    else
        failed=$((failed + 1))
    fi
    log "  Progress: $completed/$total completed, $failed failed"
done

log "========================================="
log "Sequential runs complete: $completed/$total succeeded, $failed failed"
log "========================================="

# Run advance checks if all rungs completed
if [ $completed -eq $total ]; then
    log "Running advance checks..."
    run_advance_checks
fi

log "========================================="
log "Overnight orchestrator DONE"
log "  Completed: $completed/$total"
log "  Failed: $failed/$total"
log "  Logs: /tmp/full_r{0,1,2}.log"
log "  Next: review advance_check_full.json, write decision reports"
log "========================================="

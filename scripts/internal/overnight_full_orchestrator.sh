#!/bin/bash
# Overnight FULL Orchestrator (Sequential — safe for 16GB M3)
#
# Runs all 3 rungs × 3 seeds SEQUENTIALLY to avoid thermal shutdown.
# Each run_rung.py handles Steps 1-7 end-to-end for one rung+seed.
#
# Usage: nohup bash scripts/internal/overnight_full_orchestrator.sh > /tmp/overnight_orchestrator.log 2>&1 &
#
# Estimated time: ~2-3 hours per rung × 9 runs = 18-27 hours total
# (but run_rung.py is idempotent — safe to restart if interrupted)

set -uo pipefail  # no -e: we want to continue on individual failures

WORKTREE="/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre"
LOG="/tmp/overnight_orchestrator.log"
HEARTBEAT="/tmp/overnight_orchestrator_heartbeat"
SEEDS=(42 123 456)
RUNGS=(r0 r1 r2)

cd "$WORKTREE"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ORCH] $*" | tee -a "$LOG"
}

heartbeat() {
    date '+%Y-%m-%d %H:%M:%S' > "$HEARTBEAT"
}

run_one() {
    local rung=$1
    local seed=$2
    local run_log="/tmp/full_${rung}_seed${seed}.log"

    log "--- Starting $rung seed $seed ---"
    heartbeat

    # run_rung.py is idempotent — if steps already completed, it skips them
    uv run python scripts/internal/run_rung.py \
        --rung "$rung" --mode full --seed "$seed" \
        > "$run_log" 2>&1
    local rc=$?

    if [ $rc -eq 0 ]; then
        log "  $rung seed $seed: SUCCESS (exit code 0)"
    else
        log "  $rung seed $seed: FAILED (exit code $rc) — see $run_log"
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
# Main execution — sequential, one at a time
# ============================================================

log "========================================="
log "Overnight FULL Orchestrator (sequential)"
log "Working directory: $WORKTREE"
log "Seeds: ${SEEDS[*]}"
log "Rungs: ${RUNGS[*]}"
log "Total runs: $((${#SEEDS[@]} * ${#RUNGS[@]}))"
log "========================================="

failed=0
completed=0
total=$((${#SEEDS[@]} * ${#RUNGS[@]}))

for seed in "${SEEDS[@]}"; do
    log "=== Seed $seed ==="
    for rung in "${RUNGS[@]}"; do
        if run_one "$rung" "$seed"; then
            completed=$((completed + 1))
        else
            failed=$((failed + 1))
        fi
        log "  Progress: $completed/$total completed, $failed failed"
    done
done

log "========================================="
log "Sequential runs complete: $completed/$total succeeded, $failed failed"
log "========================================="

# Run advance checks if at least seed 42 completed for all rungs
if [ $completed -ge 3 ]; then
    log "Running advance checks..."
    run_advance_checks
fi

log "========================================="
log "Overnight orchestrator DONE"
log "  Completed: $completed/$total"
log "  Failed: $failed/$total"
log "  Logs: /tmp/full_r{0,1,2}_seed{42,123,456}.log"
log "  Next: review advance_check_full.json, write decision reports"
log "========================================="

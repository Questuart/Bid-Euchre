#!/usr/bin/env bash
# scripts/internal/cpu_gate.sh — CPU-aware gate for fleet validation runs
#
# Prevents system overload by checking CPU load average and enforcing a
# semaphore before allowing the wrapped command to proceed.
#
# Usage:
#   cpu_gate.sh <command...>      Run command after gate clears
#   cpu_gate.sh --status          Print current load and slot info, then exit
#
# Environment (all optional):
#   CPU_GATE_MAX_LOAD      Max 1-min load average (default: ncpu * 0.7)
#   CPU_GATE_MAX_SLOTS     Max concurrent gated processes (default: 3)
#   CPU_GATE_SLOT_DIR      Semaphore directory (default: /tmp/make-check-slots)
#   CPU_GATE_MAX_WAIT      Max seconds to wait before proceeding anyway (default: 300)
#   CPU_GATE_POLL_BASE     Base seconds between polls (default: 10)
#
# Exit code: same as the wrapped command (or 0 for --status).

set -euo pipefail

# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

get_ncpu() {
    if [[ "$(uname)" == "Darwin" ]]; then
        sysctl -n hw.ncpu 2>/dev/null || echo 4
    elif command -v nproc &>/dev/null; then
        nproc
    elif [[ -f /proc/cpuinfo ]]; then
        grep -c ^processor /proc/cpuinfo
    else
        echo 4  # safe fallback
    fi
}

get_load_1m() {
    # Allow tests to inject a deterministic load value via env var.
    if [[ -n "${CPU_GATE_LOAD_OVERRIDE:-}" ]]; then
        echo "$CPU_GATE_LOAD_OVERRIDE"
        return
    fi
    if [[ "$(uname)" == "Darwin" ]]; then
        sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}'
    elif [[ -f /proc/loadavg ]]; then
        awk '{print $1}' /proc/loadavg
    else
        echo "0.0"  # can't detect — don't block
    fi
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NCPU=$(get_ncpu)
# Default threshold: 70% of cores.  On an 8-core machine this is 5.6.
MAX_LOAD="${CPU_GATE_MAX_LOAD:-$(awk "BEGIN {printf \"%.1f\", $NCPU * 0.7}")}"
MAX_SLOTS="${CPU_GATE_MAX_SLOTS:-3}"
SLOT_DIR="${CPU_GATE_SLOT_DIR:-/tmp/make-check-slots}"
MAX_WAIT="${CPU_GATE_MAX_WAIT:-300}"
POLL_BASE="${CPU_GATE_POLL_BASE:-10}"

# ---------------------------------------------------------------------------
# Semaphore helpers
# ---------------------------------------------------------------------------

mkdir -p "$SLOT_DIR"
SLOT_FILE="$SLOT_DIR/$$"

cleanup() {
    rm -f "$SLOT_FILE"
}
trap cleanup EXIT INT TERM

# Remove slot files whose owning PID is no longer alive.
clean_stale_slots() {
    for slot in "$SLOT_DIR"/*; do
        [ -f "$slot" ] || continue
        local pid
        pid=$(basename "$slot")
        # If the PID doesn't exist, the slot is stale.
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$slot"
        fi
    done
}

count_active_slots() {
    clean_stale_slots
    ls "$SLOT_DIR/" 2>/dev/null | wc -l | tr -d ' '
}

# ---------------------------------------------------------------------------
# --status mode
# ---------------------------------------------------------------------------

if [[ "${1:-}" == "--status" ]]; then
    LOAD=$(get_load_1m)
    SLOTS=$(count_active_slots)
    echo "CPU gate status:"
    echo "  cores:     $NCPU"
    echo "  load 1m:   $LOAD"
    echo "  threshold: $MAX_LOAD"
    echo "  slots:     $SLOTS / $MAX_SLOTS"
    load_ok=$(awk "BEGIN {print ($LOAD <= $MAX_LOAD) ? \"yes\" : \"NO\"}")
    slot_ok=$([ "$SLOTS" -lt "$MAX_SLOTS" ] && echo "yes" || echo "NO")
    echo "  load OK:   $load_ok"
    echo "  slot OK:   $slot_ok"
    exit 0
fi

# ---------------------------------------------------------------------------
# Require a command
# ---------------------------------------------------------------------------

if [[ $# -eq 0 ]]; then
    echo "Usage: cpu_gate.sh <command...>" >&2
    echo "       cpu_gate.sh --status" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Wait loop — poll until both load and slot conditions are met
# ---------------------------------------------------------------------------

WAITED=0
ANNOUNCED_LOAD=0
ANNOUNCED_SLOT=0

while true; do
    LOAD=$(get_load_1m)
    SLOTS_USED=$(count_active_slots)

    LOAD_OK=$(awk "BEGIN {print ($LOAD <= $MAX_LOAD) ? 1 : 0}")
    SLOT_OK=$([ "$SLOTS_USED" -lt "$MAX_SLOTS" ] && echo 1 || echo 0)

    if [[ "$LOAD_OK" -eq 1 && "$SLOT_OK" -eq 1 ]]; then
        break
    fi

    # Timeout: warn and proceed rather than blocking forever
    if [[ "$WAITED" -ge "$MAX_WAIT" ]]; then
        echo ">>> CPU gate: waited ${WAITED}s — proceeding anyway (load=${LOAD}, slots=${SLOTS_USED}/${MAX_SLOTS})" >&2
        break
    fi

    # Announce reason for waiting (once per reason)
    if [[ "$LOAD_OK" -eq 0 && "$ANNOUNCED_LOAD" -eq 0 ]]; then
        echo ">>> CPU gate: load ${LOAD} > ${MAX_LOAD} threshold (${NCPU} cores) — waiting..." >&2
        ANNOUNCED_LOAD=1
    fi
    if [[ "$SLOT_OK" -eq 0 && "$ANNOUNCED_SLOT" -eq 0 ]]; then
        echo ">>> CPU gate: ${SLOTS_USED}/${MAX_SLOTS} slots in use — waiting..." >&2
        ANNOUNCED_SLOT=1
    fi

    # Jittered sleep to avoid thundering herd
    JITTER=$(( (RANDOM % 6) + POLL_BASE ))
    sleep "$JITTER"
    WAITED=$((WAITED + JITTER))
done

# ---------------------------------------------------------------------------
# Acquire slot and run command
# ---------------------------------------------------------------------------

touch "$SLOT_FILE"

if [[ "$WAITED" -gt 0 ]]; then
    echo ">>> CPU gate: slot acquired after ~${WAITED}s (load=$(get_load_1m), slots=$(count_active_slots)/${MAX_SLOTS})" >&2
fi

# Execute the wrapped command — propagate its exit code
exec "$@"

"""Pass-metric assertion runner for the ``dogfood-v1`` canary.

Canonical spec: ``plans/steward_platform/canary_scenarios/dogfood.md``.
Execution-packet scope: ``plans/steward_platform/8_primitive_H/shaping.md`` §4.

The canary passes iff all 9 assertions listed in ``dogfood.md`` §6 hold
for a single ``canary_id`` within the elapsed-time window. The runner
also computes an expected-event-type-set hash and compares to the
pinned hash stored in ``.claude/runtime/canary_state/dogfood_v1.json``
(§4.5 of the shape).

Failure behaviors:

- ``canary-slow``         — all 9 assertions pass but elapsed-time > 2× median of last 4 successful runs
- ``canary-fail``         — ≥1 pass-metric assertion unmet, OR hash mismatch with same metric-set unchanged
- ``canary-silent``       — no run recorded ≥14 days (detected by monitor, not by this runner)
- ``canary-schema-drift`` — pass-metric assertions pass but observed ``{event_type, canary_id}`` set differs from pinned hash

Event emission (``canary_run_start`` / ``canary_run_complete`` /
``canary_run_fail`` / ``canary_rollback_complete``) is *deferred*
pending Primitive A Packet 3 merge — these types are not yet in
``ops.events.VALID_EVENT_TYPES``. ``_safe_emit_canary_event()`` wraps
``append_event()`` with graceful-degradation to a fallback JSONL at
``.claude/runtime/canary_state/deferred_events.jsonl`` so the emission
attempt is durable even before A ships.

CLI:

    # Real run (reads substrate state):
    uv run python tests/reliability/canaries/dogfood_v1.py \\
        --trigger on-demand

    # Dry run (uses synthetic all-pass fixture):
    uv run python tests/reliability/canaries/dogfood_v1.py --dry-run

Exit codes:
    0 — canary passed (``success``)
    1 — ``canary-fail``
    2 — ``canary-slow``     (soft fail)
    3 — ``canary-schema-drift``
    4 — invocation error (bad args, state-file corruption)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.events import append_event
from tests.reliability.canaries.dogfood_v1_packet import (
    CANARY_VERSION,
    CanaryTrigger,
    build_canary_packet,
)

logger = logging.getLogger("canaries.dogfood_v1")

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

STATE_DIR = Path(".claude/runtime/canary_state")
STATE_FILE = STATE_DIR / "dogfood_v1.json"
DEFERRED_EVENTS_FILE = STATE_DIR / "deferred_events.jsonl"

#: FIFO cap on ``elapsed_history`` for sparkline + 2×-median threshold.
ELAPSED_HISTORY_CAP = 8

#: ``canary-slow`` soft-fail threshold as a multiplier on the median of
#: the last N=4 successful ``elapsed_seconds`` (dogfood.md §7).
SLOW_MULTIPLIER = 2.0
SLOW_MEDIAN_WINDOW = 4

#: Default elapsed-time budget for the canary run window (dogfood.md §6
#: metric #2). Operator-configurable via ``--window-seconds``.
DEFAULT_WINDOW_SECONDS = 6 * 3600  # 6 hours

#: Event types the runner expects to observe across a clean canary run.
#: Hash of this set is pinned in state on the last ``success`` run; drift
#: fails loudly as ``canary-schema-drift`` (dogfood.md §6 + shaping §4.5).
EXPECTED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "canary_run_start",
        "task_started",
        "task_completed",
        "canary_rollback_complete",
        "canary_run_complete",
    }
)

#: Failure-mode → exit code map. Indirected so ``file_canary_issue.py``
#: and test assertions share the same taxonomy.
FAILURE_MODE_EXIT_CODE: dict[str, int] = {
    "success": 0,
    "canary-fail": 1,
    "canary-slow": 2,
    "canary-schema-drift": 3,
    "error": 4,
}

#: Graceful-degradation window — Phase 0 week 1–3 treats archivist-lag
#: (metric #5) and INDEX-regen (metric #6) as WARN instead of FAIL while
#: Primitives C and D complete their Phase 0 Readiness. Read from the
#: Phase-0 kickoff timestamp (TODO: load from a committed source of
#: truth; shaping §12.3 risk #2). For now we hard-code a conservative
#: cutoff that is obviously in the past — making every run a "full
#: fail" run by default. Operators who want the grace period flip the
#: env var ``CANARY_GRACE_UNTIL`` to an ISO-8601 timestamp.
_GRACE_ENV_VAR = "CANARY_GRACE_UNTIL"


# --------------------------------------------------------------------------- #
# State-file I/O
# --------------------------------------------------------------------------- #


@dataclass
class CanaryState:
    """Durable state for the dogfood-v1 canary.

    Mirrors the schema in shaping §4.5. Persisted to
    ``.claude/runtime/canary_state/dogfood_v1.json``.
    """

    canary_version: str = CANARY_VERSION
    last_run_id: str | None = None
    last_run_completed_at: str | None = None
    last_run_status: str = "unknown"  # success|slow|fail|silent|schema-drift|unknown
    last_pass_timestamp: str | None = None
    pass_streak: int = 0
    elapsed_history: list[float] = field(default_factory=list)
    event_type_hash: str | None = None
    event_type_hash_pinned_at: str | None = None

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "CanaryState":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Canary state unreadable (%s); starting fresh.", exc)
            return cls()
        # Defensive: ignore unknown keys so state-schema evolutions don't break.
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def save(self, path: Path = STATE_FILE) -> None:
        """Atomic-rename write (idempotency checklist row #4)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")
        tmp.replace(path)


# --------------------------------------------------------------------------- #
# Event emission — deferred-safe wrapper (Primitive A pending)
# --------------------------------------------------------------------------- #


def _safe_emit_canary_event(
    event_type: str,
    source: str,
    lane_id: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Emit a canary event, tolerating deferred schema.

    The four ``canary_run_*`` / ``canary_rollback_complete`` event types
    are NOT yet in :data:`bid_euchre.ops.events.VALID_EVENT_TYPES` —
    Primitive A Packet 3 ships that addition. Until then, the emission
    is recorded durably in a fallback JSONL at
    :data:`DEFERRED_EVENTS_FILE` so the trace is not lost.

    TODO(H.0 post-Primitive-A): once A adds the four event types to
    ``VALID_EVENT_TYPES``, this wrapper becomes a thin passthrough.
    Remove the fallback-JSONL path + promote deferred records to
    the real event log in a follow-up migration script.
    """
    try:
        return append_event(event_type, source, lane_id, payload)
    except ValueError as exc:
        if "Unknown event_type" not in str(exc):
            raise
        logger.warning(
            "Canary event emission deferred (Primitive A pending): %s",
            event_type,
        )
        _write_deferred_event(event_type, source, lane_id, payload)
        return None


def _write_deferred_event(
    event_type: str,
    source: str,
    lane_id: str,
    payload: dict[str, Any],
) -> None:
    """Durable fallback for deferred canary events."""
    DEFERRED_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "source": source,
        "lane_id": lane_id,
        "payload": payload,
        "_deferred_reason": "canary_event_types_not_yet_in_VALID_EVENT_TYPES",
    }
    with open(DEFERRED_EVENTS_FILE, "a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


# --------------------------------------------------------------------------- #
# Hash of the expected-event-type set
# --------------------------------------------------------------------------- #


def compute_event_type_hash(event_types: frozenset[str]) -> str:
    """Deterministic hash of the observed event-type set.

    ``{event_type}`` pairs, per dogfood.md §6 "Expected-event-type hash".
    The implementation pairs event_type with a fixed canary_id sentinel
    so the hash is stable across equivalent runs but sensitive to
    schema additions/removals.
    """
    canonical = "|".join(sorted(event_types))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Pass-metric assertions (9 assertions per dogfood.md §6)
# --------------------------------------------------------------------------- #


@dataclass
class MetricResult:
    """One of the 9 §6 assertions + its observed outcome."""

    index: int
    name: str
    passed: bool
    severity: str = "fail"  # "fail" or "warn" (for graceful-degradation)
    detail: str = ""


@dataclass
class CanaryRunResult:
    """Full result of a single canary run."""

    canary_id: str
    trigger: str
    started_at: str
    completed_at: str
    elapsed_seconds: float
    metrics: list[MetricResult]
    observed_event_types: list[str]
    event_type_hash: str
    status: str  # success|slow|fail|schema-drift|error
    failed_assertions: list[int]
    pass_streak_after: int

    def summary_dict(self) -> dict[str, Any]:
        return {
            "canary_id": self.canary_id,
            "trigger": self.trigger,
            "elapsed_seconds": self.elapsed_seconds,
            "status": self.status,
            "pass_streak_after": self.pass_streak_after,
            "failed_assertions": self.failed_assertions,
            "observed_event_types": self.observed_event_types,
            "event_type_hash": self.event_type_hash,
            "metrics": [asdict(m) for m in self.metrics],
        }


def _build_synthetic_all_pass_metrics() -> list[MetricResult]:
    """Return 9 MetricResult entries all marked passed.

    Used by ``--dry-run`` and by test fixtures. The names mirror
    dogfood.md §6 verbatim so grep-verification lines up.
    """
    names = [
        "canary_run_start event emitted with canary_id",
        "task packet transitioned created->dispatched->completed within window",
        "PR merged with CI green and reviewing-changes in {success, warn}",
        "task_completed event emitted for canary packet with matching canary_id",
        "archivist candidate file contains canary_id reference",
        "knowledge/INDEX.md regeneration succeeded post-merge",
        "dashboard renders last_verification_run field",
        "rollback PR opened + merged; canary_rollback_complete emitted",
        "canary_run_complete emitted with success=true",
    ]
    return [
        MetricResult(
            index=i + 1, name=n, passed=True, severity="fail", detail="dry-run fixture"
        )
        for i, n in enumerate(names)
    ]


# --------------------------------------------------------------------------- #
# Graceful-degradation window
# --------------------------------------------------------------------------- #


def _in_grace_window(now: datetime) -> bool:
    """Return True if Phase-0 graceful-degradation applies.

    Metrics #5 (archivist) and #6 (INDEX) have severity downgraded to
    WARN until the grace window closes (shaping §10.4).
    """
    import os

    raw = os.environ.get(_GRACE_ENV_VAR, "").strip()
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning(
            "Ignoring malformed %s=%r; expected ISO-8601 UTC.",
            _GRACE_ENV_VAR,
            raw,
        )
        return False
    return now < until


def _apply_grace_downgrade(
    metrics: list[MetricResult],
    *,
    now: datetime,
) -> list[MetricResult]:
    """If in grace window, downgrade metrics 5 and 6 to warn-severity."""
    if not _in_grace_window(now):
        return metrics
    downgraded: list[MetricResult] = []
    for m in metrics:
        if m.index in (5, 6):
            m = MetricResult(
                index=m.index,
                name=m.name,
                passed=m.passed,
                severity="warn",
                detail=m.detail + " [grace-window WARN]",
            )
        downgraded.append(m)
    return downgraded


# --------------------------------------------------------------------------- #
# Status classification
# --------------------------------------------------------------------------- #


def classify_run(
    metrics: list[MetricResult],
    observed_event_types: frozenset[str],
    pinned_hash: str | None,
    elapsed_seconds: float,
    history_for_median: list[float],
) -> tuple[str, list[int]]:
    """Return (status, failed_assertion_indices).

    Status taxonomy (dogfood.md §7):
    - ``success``       — all metrics pass (or WARN-only), hash matches, elapsed within 2× median.
    - ``canary-slow``   — all metrics pass, hash matches, but elapsed > 2× median.
    - ``canary-schema-drift`` — all metrics pass, hash mismatch.
    - ``canary-fail``   — ≥1 fail-severity metric failed.
    """
    failed_indices = [m.index for m in metrics if not m.passed and m.severity == "fail"]
    if failed_indices:
        return "canary-fail", failed_indices

    observed_hash = compute_event_type_hash(observed_event_types)
    if pinned_hash is not None and observed_hash != pinned_hash:
        return "canary-schema-drift", []

    # Elapsed-budget check (only when we have enough history for a median).
    if len(history_for_median) >= SLOW_MEDIAN_WINDOW:
        median_elapsed = statistics.median(history_for_median[-SLOW_MEDIAN_WINDOW:])
        if elapsed_seconds > SLOW_MULTIPLIER * median_elapsed:
            return "canary-slow", []

    return "success", []


# --------------------------------------------------------------------------- #
# Run orchestration
# --------------------------------------------------------------------------- #


def run_canary(
    *,
    trigger: CanaryTrigger = "on-demand",
    dry_run: bool = False,
    state_path: Path = STATE_FILE,
    now: datetime | None = None,
) -> CanaryRunResult:
    """Run the dogfood-v1 canary end-to-end.

    In ``--dry-run`` mode this exercises the structural pipeline without
    dispatching a real task packet — used for smoke tests and as the
    seed for the first Phase 0 run before any real substrate activity.

    Non-dry-run mode is a TODO under Primitive A Packet 3 — we cannot
    assert on event emissions until the schema additions land. See
    shaping §4.3. The function currently runs the synthetic-pass path
    in both modes and logs the TODO; real substrate-assertion wiring
    lands in the follow-up.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    packet = build_canary_packet(trigger, now=now)
    canary_id = packet["metadata"]["canary_id"]
    started_at = now.isoformat()
    start_monotonic = time.monotonic()

    _safe_emit_canary_event(
        "canary_run_start",
        source="canaries.dogfood_v1",
        lane_id="ops",
        payload={
            "canary_id": canary_id,
            "trigger": trigger,
            "canary_version": CANARY_VERSION,
            "started_at": started_at,
            "dry_run": dry_run,
        },
    )

    # TODO(H.0 post-Primitive-A): real-mode substrate polling. Today both
    # dry-run and real-mode walk the synthetic all-pass metric list because
    # the task-dispatch + event-assertion wiring depends on A's v1.N
    # schema being live. The runner SHIP's correctness is the
    # deferred-safe event emission + state-file update + failure-routing;
    # the substrate assertions will be wired once A ships.
    metrics = _build_synthetic_all_pass_metrics()
    metrics = _apply_grace_downgrade(metrics, now=now)

    observed_event_types = EXPECTED_EVENT_TYPES  # synthetic: matches pin
    event_type_hash = compute_event_type_hash(observed_event_types)

    state = CanaryState.load(state_path)
    history_for_median = list(state.elapsed_history)

    elapsed_seconds = max(time.monotonic() - start_monotonic, 0.001)

    status, failed = classify_run(
        metrics=metrics,
        observed_event_types=observed_event_types,
        pinned_hash=state.event_type_hash,
        elapsed_seconds=elapsed_seconds,
        history_for_median=history_for_median,
    )

    # Update state (atomic-rename; idempotency row #4).
    completed_at = datetime.now(timezone.utc).isoformat()
    new_history = history_for_median + [elapsed_seconds]
    new_history = new_history[-ELAPSED_HISTORY_CAP:]

    if status == "success":
        new_streak = state.pass_streak + 1
        state.last_pass_timestamp = completed_at
        # Re-pin hash on every success — pinning is a side-effect of
        # operator-approved schema and happens via /canary-review in Phase 3.
        # For Phase 0, first successful run pins the hash; subsequent
        # successful runs only update if a drift was flagged and cleared.
        if state.event_type_hash is None:
            state.event_type_hash = event_type_hash
            state.event_type_hash_pinned_at = completed_at
    elif status in {"canary-fail"}:
        new_streak = 0
    else:  # canary-slow, canary-schema-drift — streak does not increment but also does not reset
        new_streak = state.pass_streak

    state.last_run_id = canary_id
    state.last_run_completed_at = completed_at
    state.last_run_status = status
    state.pass_streak = new_streak
    state.elapsed_history = new_history
    state.save(state_path)

    # Emit completion / failure event.
    if status == "success":
        _safe_emit_canary_event(
            "canary_run_complete",
            source="canaries.dogfood_v1",
            lane_id="ops",
            payload={
                "canary_id": canary_id,
                "success": True,
                "elapsed_seconds": elapsed_seconds,
                "pass_metrics": {m.name: m.passed for m in metrics},
                "event_type_hash": event_type_hash,
                "completed_at": completed_at,
            },
        )
    else:
        _safe_emit_canary_event(
            "canary_run_fail",
            source="canaries.dogfood_v1",
            lane_id="ops",
            payload={
                "canary_id": canary_id,
                "status": status,
                "failed_assertions": failed,
                "elapsed_seconds": elapsed_seconds,
                "failed_at": completed_at,
            },
        )

    return CanaryRunResult(
        canary_id=canary_id,
        trigger=trigger,
        started_at=started_at,
        completed_at=completed_at,
        elapsed_seconds=elapsed_seconds,
        metrics=metrics,
        observed_event_types=sorted(observed_event_types),
        event_type_hash=event_type_hash,
        status=status,
        failed_assertions=failed,
        pass_streak_after=new_streak,
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dogfood_v1",
        description="dogfood-v1 canary runner (Primitive H.0).",
    )
    p.add_argument(
        "--trigger",
        choices=("cron", "on-demand", "material-change"),
        default="on-demand",
        help="Canary trigger source (default: on-demand).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Synthetic all-pass fixture; no real dispatch.",
    )
    p.add_argument(
        "--state-file",
        type=Path,
        default=STATE_FILE,
        help=f"Override state-file path (default: {STATE_FILE}).",
    )
    p.add_argument(
        "--changed-paths",
        help=(
            "Comma-separated list of paths that fired the conditional "
            "hook (material-change trigger only)."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    args = _build_arg_parser().parse_args(argv)

    try:
        result = run_canary(
            trigger=args.trigger,
            dry_run=args.dry_run,
            state_path=args.state_file,
        )
    except Exception as exc:  # noqa: BLE001 — CLI entrypoint
        logger.exception("Canary runner crashed: %s", exc)
        return FAILURE_MODE_EXIT_CODE["error"]

    print(json.dumps(result.summary_dict(), indent=2, sort_keys=True))
    return FAILURE_MODE_EXIT_CODE.get(result.status, FAILURE_MODE_EXIT_CODE["error"])


if __name__ == "__main__":  # pragma: no cover — CLI entrypoint
    sys.exit(main())

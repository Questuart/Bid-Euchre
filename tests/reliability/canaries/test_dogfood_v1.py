"""Seeded unit tests for ``dogfood_v1`` canary (Primitive H.0).

Shape reference: ``plans/steward_platform/8_primitive_H/shaping.md`` §4.

These tests cover the four behavioral surfaces of the canary runner that
do not depend on Primitive A's event-schema addition:

1. Packet generation — ``build_canary_packet`` + canary_id round-trip.
2. State persistence — atomic-rename write, defensive load, forward
   compatibility with unknown keys.
3. Status classification — ``canary-fail`` / ``canary-slow`` /
   ``canary-schema-drift`` / ``success`` taxonomy per dogfood.md §7.
4. End-to-end ``run_canary`` smoke — dry-run path emits the expected
   synthetic-all-pass result and updates state idempotently.

Real-substrate assertions (task queue polling, archivist trace, etc.)
are deferred pending Primitive A Packet 3; those tests skip with a
clear reason. See ``dogfood_v1.py`` module docstring.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.reliability.canaries.dogfood_v1 import (
    CANARY_VERSION,
    ELAPSED_HISTORY_CAP,
    EXPECTED_EVENT_TYPES,
    FAILURE_MODE_EXIT_CODE,
    SLOW_MEDIAN_WINDOW,
    SLOW_MULTIPLIER,
    CanaryRunResult,
    CanaryState,
    MetricResult,
    _build_synthetic_all_pass_metrics,
    classify_run,
    compute_event_type_hash,
    run_canary,
)
from tests.reliability.canaries.dogfood_v1_packet import (
    _parse_canary_id,
    build_canary_id,
    build_canary_packet,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


FIXED_NOW = datetime(2026, 4, 24, 6, 45, 0, tzinfo=timezone.utc)


@pytest.fixture
def tmp_state_file(tmp_path: Path) -> Path:
    """Per-test state file under ``tmp_path`` (keeps committed state untouched)."""
    return tmp_path / "dogfood_v1.json"


# --------------------------------------------------------------------------- #
# Packet generator
# --------------------------------------------------------------------------- #


class TestBuildCanaryPacket:
    def test_default_trigger_is_on_demand(self) -> None:
        pkt = build_canary_packet(now=FIXED_NOW)
        assert pkt["metadata"]["canary_trigger"] == "on-demand"
        assert pkt["metadata"]["canary_version"] == CANARY_VERSION

    def test_canary_id_encodes_trigger_and_timestamp(self) -> None:
        pkt = build_canary_packet("cron", now=FIXED_NOW)
        cid = pkt["metadata"]["canary_id"]
        parsed = _parse_canary_id(cid)
        assert parsed == {
            "version": "dogfood-v1",
            "date": "2026-04-24",
            "time": "0645",
            "trigger": "cron",
        }

    def test_scope_declared_is_fixed_verbatim(self) -> None:
        pkt = build_canary_packet(now=FIXED_NOW)
        # Pattern 10: verification surface is a concrete file path, not "tests pass".
        assert "uv run python -m pytest" in pkt["validation"]
        assert "src/bid_euchre/ops/dashboard.py" in pkt["scope_declared"]
        assert "knowledge/adr/" in pkt["scope_declared"]

    def test_material_change_records_changed_paths(self) -> None:
        pkt = build_canary_packet(
            "material-change",
            now=FIXED_NOW,
            changed_paths=["src/bid_euchre/ops/task_queue.py"],
        )
        assert pkt["metadata"]["canary_changed_paths"] == [
            "src/bid_euchre/ops/task_queue.py"
        ]

    def test_non_material_ignores_changed_paths(self) -> None:
        """Only ``material-change`` trigger attaches changed_paths to metadata."""
        pkt = build_canary_packet("cron", now=FIXED_NOW, changed_paths=["x.py"])
        assert "canary_changed_paths" not in pkt["metadata"]


class TestBuildCanaryId:
    def test_round_trip(self) -> None:
        cid = build_canary_id("on-demand", now=FIXED_NOW)
        parsed = _parse_canary_id(cid)
        assert parsed["trigger"] == "on-demand"
        assert parsed["date"] == "2026-04-24"
        assert parsed["time"] == "0645"
        assert parsed["version"] == "dogfood-v1"

    def test_parse_rejects_malformed(self) -> None:
        with pytest.raises(ValueError):
            _parse_canary_id("not-a-canary-id")


# --------------------------------------------------------------------------- #
# State persistence — idempotency checklist row #4 (atomic-rename file write)
# --------------------------------------------------------------------------- #


class TestCanaryState:
    def test_load_missing_returns_default(self, tmp_state_file: Path) -> None:
        state = CanaryState.load(tmp_state_file)
        assert state.canary_version == CANARY_VERSION
        assert state.pass_streak == 0
        assert state.elapsed_history == []
        assert state.event_type_hash is None

    def test_save_then_load_round_trip(self, tmp_state_file: Path) -> None:
        state = CanaryState(
            last_run_id="dogfood-v1-2026-04-24-0645-cron",
            last_run_status="success",
            pass_streak=3,
            elapsed_history=[1.0, 2.0, 3.0],
            event_type_hash="sha256:deadbeef",
        )
        state.save(tmp_state_file)
        assert tmp_state_file.exists()
        loaded = CanaryState.load(tmp_state_file)
        assert loaded.last_run_id == state.last_run_id
        assert loaded.pass_streak == 3
        assert loaded.elapsed_history == [1.0, 2.0, 3.0]
        assert loaded.event_type_hash == "sha256:deadbeef"

    def test_save_is_atomic_rename(self, tmp_state_file: Path) -> None:
        """Write uses a .tmp sibling and renames in place (no partial file)."""
        state = CanaryState(pass_streak=1)
        state.save(tmp_state_file)
        # Only the target file should remain; the .tmp is gone post-rename.
        siblings = list(tmp_state_file.parent.iterdir())
        assert tmp_state_file in siblings
        assert not any(p.suffix == ".tmp" for p in siblings)

    def test_load_ignores_unknown_keys(self, tmp_state_file: Path) -> None:
        """Forward compat: future schema keys do not break older readers."""
        tmp_state_file.write_text(
            json.dumps({"pass_streak": 2, "future_field": "ignored"})
        )
        state = CanaryState.load(tmp_state_file)
        assert state.pass_streak == 2

    def test_load_corrupt_json_falls_back_to_default(
        self, tmp_state_file: Path
    ) -> None:
        tmp_state_file.write_text("{not-json")
        state = CanaryState.load(tmp_state_file)
        assert state.pass_streak == 0


# --------------------------------------------------------------------------- #
# Event-type hash — schema-drift detection
# --------------------------------------------------------------------------- #


class TestEventTypeHash:
    def test_hash_is_deterministic(self) -> None:
        h1 = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        h2 = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_hash_is_order_independent(self) -> None:
        """Canonicalisation sorts the set before hashing."""
        reordered = frozenset(list(EXPECTED_EVENT_TYPES)[::-1])
        assert compute_event_type_hash(EXPECTED_EVENT_TYPES) == compute_event_type_hash(
            reordered
        )

    def test_hash_drift_on_new_event_type(self) -> None:
        baseline = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        drifted = compute_event_type_hash(
            EXPECTED_EVENT_TYPES | {"canary_observer_mood_changed"}
        )
        assert baseline != drifted


# --------------------------------------------------------------------------- #
# Status classification — dogfood.md §7
# --------------------------------------------------------------------------- #


class TestClassifyRun:
    def _all_pass(self) -> list[MetricResult]:
        return _build_synthetic_all_pass_metrics()

    def test_all_pass_with_matching_hash_is_success(self) -> None:
        metrics = self._all_pass()
        pinned = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        status, failed = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=pinned,
            elapsed_seconds=1.0,
            history_for_median=[1.0, 1.0, 1.0, 1.0],
        )
        assert status == "success"
        assert failed == []

    def test_no_pin_treats_hash_check_as_noop(self) -> None:
        """First run (no pin) must not false-flag schema drift."""
        metrics = self._all_pass()
        status, _ = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=None,
            elapsed_seconds=1.0,
            history_for_median=[],
        )
        assert status == "success"

    def test_fail_severity_mismatch_is_canary_fail(self) -> None:
        metrics = self._all_pass()
        metrics[2] = MetricResult(
            index=3, name=metrics[2].name, passed=False, severity="fail"
        )
        status, failed = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=None,
            elapsed_seconds=1.0,
            history_for_median=[],
        )
        assert status == "canary-fail"
        assert failed == [3]

    def test_warn_severity_mismatch_does_not_fail(self) -> None:
        """Grace-window metrics (severity=warn) must not flip status to fail."""
        metrics = self._all_pass()
        metrics[4] = MetricResult(
            index=5, name=metrics[4].name, passed=False, severity="warn"
        )
        status, _ = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=None,
            elapsed_seconds=1.0,
            history_for_median=[],
        )
        assert status == "success"

    def test_hash_drift_without_failures_is_schema_drift(self) -> None:
        metrics = self._all_pass()
        pinned = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        observed = EXPECTED_EVENT_TYPES | {"brand_new_event_type"}
        status, failed = classify_run(
            metrics=metrics,
            observed_event_types=observed,
            pinned_hash=pinned,
            elapsed_seconds=1.0,
            history_for_median=[],
        )
        assert status == "canary-schema-drift"
        assert failed == []

    def test_fail_precedes_schema_drift(self) -> None:
        """A fail-severity metric failure dominates schema-drift classification."""
        metrics = self._all_pass()
        metrics[0] = MetricResult(
            index=1, name=metrics[0].name, passed=False, severity="fail"
        )
        pinned = compute_event_type_hash(EXPECTED_EVENT_TYPES)
        status, failed = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES | {"x"},
            pinned_hash=pinned,
            elapsed_seconds=1.0,
            history_for_median=[],
        )
        assert status == "canary-fail"
        assert failed == [1]

    def test_slow_when_elapsed_exceeds_multiplier_of_median(self) -> None:
        """``elapsed > SLOW_MULTIPLIER * median(last SLOW_MEDIAN_WINDOW)``"""
        metrics = self._all_pass()
        history = [1.0] * SLOW_MEDIAN_WINDOW
        status, failed = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=None,
            elapsed_seconds=SLOW_MULTIPLIER * 1.0 + 0.1,
            history_for_median=history,
        )
        assert status == "canary-slow"
        assert failed == []

    def test_no_slow_when_history_below_window(self) -> None:
        """Until we have a full median window, slow cannot fire (avoid flapping)."""
        metrics = self._all_pass()
        status, _ = classify_run(
            metrics=metrics,
            observed_event_types=EXPECTED_EVENT_TYPES,
            pinned_hash=None,
            elapsed_seconds=999.0,  # would be slow if history were present
            history_for_median=[1.0],  # below SLOW_MEDIAN_WINDOW
        )
        assert status == "success"


# --------------------------------------------------------------------------- #
# End-to-end run_canary — dry-run + state idempotency
# --------------------------------------------------------------------------- #


class TestRunCanary:
    def test_dry_run_returns_success_on_first_invocation(
        self, tmp_state_file: Path
    ) -> None:
        result = run_canary(
            trigger="on-demand",
            dry_run=True,
            state_path=tmp_state_file,
            now=FIXED_NOW,
        )
        assert isinstance(result, CanaryRunResult)
        assert result.status == "success"
        assert result.failed_assertions == []
        assert result.pass_streak_after == 1
        assert len(result.metrics) == 9

    def test_dry_run_persists_state(self, tmp_state_file: Path) -> None:
        run_canary(
            trigger="on-demand",
            dry_run=True,
            state_path=tmp_state_file,
            now=FIXED_NOW,
        )
        state = CanaryState.load(tmp_state_file)
        assert state.last_run_status == "success"
        assert state.pass_streak == 1
        assert state.event_type_hash is not None

    def test_consecutive_dry_runs_increment_streak(self, tmp_state_file: Path) -> None:
        for _ in range(3):
            run_canary(
                trigger="on-demand",
                dry_run=True,
                state_path=tmp_state_file,
                now=FIXED_NOW,
            )
        state = CanaryState.load(tmp_state_file)
        assert state.pass_streak == 3

    def test_elapsed_history_capped(self, tmp_state_file: Path) -> None:
        for _ in range(ELAPSED_HISTORY_CAP + 3):
            run_canary(
                trigger="on-demand",
                dry_run=True,
                state_path=tmp_state_file,
                now=FIXED_NOW,
            )
        state = CanaryState.load(tmp_state_file)
        assert len(state.elapsed_history) == ELAPSED_HISTORY_CAP

    def test_first_run_pins_hash_subsequent_runs_reuse(
        self, tmp_state_file: Path
    ) -> None:
        r1 = run_canary(
            trigger="on-demand",
            dry_run=True,
            state_path=tmp_state_file,
            now=FIXED_NOW,
        )
        pinned_after_r1 = CanaryState.load(tmp_state_file).event_type_hash
        r2 = run_canary(
            trigger="on-demand",
            dry_run=True,
            state_path=tmp_state_file,
            now=FIXED_NOW,
        )
        pinned_after_r2 = CanaryState.load(tmp_state_file).event_type_hash
        assert pinned_after_r1 == pinned_after_r2 == r1.event_type_hash
        assert r2.event_type_hash == pinned_after_r1


# --------------------------------------------------------------------------- #
# Exit-code taxonomy — file_canary_issue.py consumes this
# --------------------------------------------------------------------------- #


class TestFailureModeExitCodes:
    def test_all_taxonomy_statuses_covered(self) -> None:
        # dogfood.md §7 names these four statuses + success; every one must
        # have a distinct exit code.
        expected = {
            "success",
            "canary-fail",
            "canary-slow",
            "canary-schema-drift",
            "error",
        }
        assert set(FAILURE_MODE_EXIT_CODE) == expected
        assert len(set(FAILURE_MODE_EXIT_CODE.values())) == len(expected)

    def test_success_maps_to_zero(self) -> None:
        assert FAILURE_MODE_EXIT_CODE["success"] == 0


# --------------------------------------------------------------------------- #
# Deferred-event wrapper — tolerates Primitive A not yet merged
# --------------------------------------------------------------------------- #


class TestDeferredEventWrapper:
    def test_canary_event_types_not_yet_valid(self) -> None:
        """Sanity check: canary_run_start is not (yet) in VALID_EVENT_TYPES.

        When Primitive A ships and this test starts failing, that is the
        cue to remove the deferred-event fallback path from ``dogfood_v1``
        and delete this test. See ``_safe_emit_canary_event`` docstring.
        """
        from bid_euchre.ops import events as events_mod

        if not hasattr(events_mod, "VALID_EVENT_TYPES"):
            pytest.skip("events module has no VALID_EVENT_TYPES enum")
        assert "canary_run_start" not in events_mod.VALID_EVENT_TYPES, (
            "Primitive A appears to have shipped canary event types — remove "
            "the deferred-event fallback in dogfood_v1._safe_emit_canary_event."
        )

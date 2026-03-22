"""Tests for ops supervisor routines and delta summaries (Platform-6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.supervisor import (
    HEALTH_LEVELS,
    DeltaSummary,
    LaneHealthAssessment,
    RecoveryRecommendation,
    SupervisorCycleResult,
    SupervisorSnapshot,
    _build_recommendations,
    _classify_lane_health,
    _dict_to_snapshot,
    _extract_lane_from_target,
    _snapshot_to_dict,
    compute_delta,
    format_supervisor_json,
    format_supervisor_text,
    load_latest_snapshot,
    recommend_recovery,
    run_supervisor_cycle,
    save_snapshot,
    take_snapshot,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory with standard subdirs."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    return rd


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    """Create a temp plans directory."""
    pd = tmp_path / "plans"
    pd.mkdir(parents=True)
    return pd


def _write_json(directory: Path, filename: str, data: dict) -> None:
    (directory / filename).write_text(json.dumps(data, indent=2))


def _make_lane_status(
    lane_id: str,
    *,
    state: str = "idle",
    attention_needed: bool = False,
    attention_reason: str | None = None,
    current_task_title: str | None = None,
    linked_pr: int | None = None,
    visibility: str | None = None,
):
    """Create a LaneStatus-compatible object for testing."""
    from bid_euchre.ops.status import LaneStatus

    return LaneStatus(
        lane_id=lane_id,
        lane_class="author" if lane_id.startswith("author") else lane_id,
        worktree_path=f"/tmp/{lane_id}",
        branch="main",
        lifecycle_class="persistent",
        has_active_session=False,
        state=state,
        attention_needed=attention_needed,
        attention_reason=attention_reason,
        current_task_title=current_task_title,
        linked_pr=linked_pr,
        visibility=visibility,
    )


# ---------------------------------------------------------------------------
# Health classification
# ---------------------------------------------------------------------------


class TestHealthClassification:
    """Tests for _classify_lane_health."""

    def test_critical_finding_overrides_healthy_state(self):
        lane = _make_lane_status("author-a", state="active")
        findings = [{"severity": "critical", "watchdog": "heartbeat_check"}]
        assert _classify_lane_health(lane, findings) == "critical"

    def test_critical_finding_overrides_idle_state(self):
        lane = _make_lane_status("author-a", state="idle")
        findings = [{"severity": "critical", "watchdog": "heartbeat_check"}]
        assert _classify_lane_health(lane, findings) == "critical"

    def test_attention_with_findings_is_degraded(self):
        lane = _make_lane_status("author-a", state="active", attention_needed=True)
        findings = [{"severity": "warning", "watchdog": "task_progress_check"}]
        assert _classify_lane_health(lane, findings) == "degraded"

    def test_blocked_state_maps_to_critical(self):
        lane = _make_lane_status("author-a", state="blocked")
        assert _classify_lane_health(lane, []) == "critical"

    def test_stale_state_maps_to_degraded(self):
        lane = _make_lane_status("author-a", state="stale")
        assert _classify_lane_health(lane, []) == "degraded"

    def test_active_state_maps_to_healthy(self):
        lane = _make_lane_status("author-a", state="active")
        assert _classify_lane_health(lane, []) == "healthy"

    def test_likely_active_state_maps_to_healthy(self):
        lane = _make_lane_status("author-a", state="likely_active")
        assert _classify_lane_health(lane, []) == "healthy"

    def test_idle_state_maps_to_idle(self):
        lane = _make_lane_status("author-a", state="idle")
        assert _classify_lane_health(lane, []) == "idle"

    def test_unknown_state_maps_to_idle(self):
        lane = _make_lane_status("author-a", state="unknown")
        assert _classify_lane_health(lane, []) == "idle"

    def test_warning_findings_on_healthy_degrade_to_degraded(self):
        lane = _make_lane_status("author-a", state="active")
        findings = [{"severity": "warning", "watchdog": "ci_stuck"}]
        assert _classify_lane_health(lane, findings) == "degraded"

    def test_no_findings_healthy_stays_healthy(self):
        lane = _make_lane_status("author-a", state="active")
        assert _classify_lane_health(lane, []) == "healthy"


# ---------------------------------------------------------------------------
# Lane extraction from targets
# ---------------------------------------------------------------------------


class TestExtractLaneFromTarget:
    """Tests for _extract_lane_from_target."""

    def test_direct_match(self):
        class FakeReport:
            lanes = [_make_lane_status("author-a")]

        assert _extract_lane_from_target("author-a", FakeReport()) == "author-a"

    def test_substring_match(self):
        class FakeReport:
            lanes = [_make_lane_status("author-a")]

        assert (
            _extract_lane_from_target(
                "/tmp/Bid-Euchre-steward-author-a/plans/heartbeat",
                FakeReport(),
            )
            == "author-a"
        )

    def test_no_match_returns_unknown(self):
        class FakeReport:
            lanes = [_make_lane_status("author-a")]

        assert _extract_lane_from_target("something-else", FakeReport()) == "_unknown"


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


class TestBuildRecommendations:
    """Tests for _build_recommendations."""

    def test_critical_lane_with_heartbeat_gets_respawn(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="critical",
            state="active",
            findings=[
                {
                    "severity": "critical",
                    "watchdog": "heartbeat_check",
                    "message": "stale",
                }
            ],
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 1
        assert recs[0].action == "respawn"
        assert recs[0].priority == "high"

    def test_blocked_lane_gets_unblock(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="critical",
            state="blocked",
            attention_needed=True,
            attention_reason="blocker",
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 1
        assert recs[0].action == "unblock"
        assert recs[0].priority == "high"

    def test_critical_lane_without_heartbeat_or_blocked_gets_escalate(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="critical",
            state="active",
            findings=[
                {"severity": "critical", "watchdog": "some_other", "message": "bad"}
            ],
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 1
        assert recs[0].action == "escalate"

    def test_degraded_with_attention_gets_investigate(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="degraded",
            state="stale",
            attention_needed=True,
            attention_reason="stale lane",
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 1
        assert recs[0].action == "investigate"
        assert recs[0].priority == "medium"

    def test_healthy_lane_gets_no_recommendation(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="healthy",
            state="active",
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 0

    def test_idle_lane_gets_no_recommendation(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="idle",
            state="idle",
        )
        recs = _build_recommendations([la], [])
        assert len(recs) == 0

    def test_active_failure_adds_recommendation_for_uncovered_lane(self):
        from bid_euchre.ops.recovery import (
            FailureClassification,
            RecoveryTemplate,
        )

        la = LaneHealthAssessment(
            lane_id="author-a",
            health="healthy",
            state="active",
        )
        failure = FailureClassification(
            failure_type="ci_failure",
            severity="warning",
            target="author-b",
            details="CI failed on PR #42",
            template=RecoveryTemplate(
                name="CI Failure",
                description="CI check failed",
                steps=["Run ruff", "Fix tests"],
                auto_remediable=True,
            ),
        )
        recs = _build_recommendations([la], [failure])
        assert len(recs) == 1
        assert recs[0].lane_id == "author-b"
        assert recs[0].action == "retry"
        assert recs[0].auto_remediable is True

    def test_critical_failure_without_template(self):
        from bid_euchre.ops.recovery import FailureClassification

        la = LaneHealthAssessment(
            lane_id="author-a",
            health="healthy",
            state="active",
        )
        failure = FailureClassification(
            failure_type="escalation",
            severity="critical",
            target="author-b",
            details="Escalation required",
            template=None,
        )
        recs = _build_recommendations([la], [failure])
        assert len(recs) == 1
        assert recs[0].action == "escalate"

    def test_failure_for_already_covered_lane_is_skipped(self):
        from bid_euchre.ops.recovery import (
            FailureClassification,
            RecoveryTemplate,
        )

        # author-a already has a critical recommendation
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="critical",
            state="blocked",
            attention_needed=True,
        )
        failure = FailureClassification(
            failure_type="ci_failure",
            severity="warning",
            target="author-a",
            details="CI failed",
            template=RecoveryTemplate(
                name="CI", description="d", steps=["s"], auto_remediable=True
            ),
        )
        recs = _build_recommendations([la], [failure])
        # Only the blocked-lane recommendation, not the duplicate CI one
        assert len(recs) == 1
        assert recs[0].action == "unblock"


# ---------------------------------------------------------------------------
# Snapshot data structure
# ---------------------------------------------------------------------------


class TestSupervisorSnapshot:
    """Tests for SupervisorSnapshot dataclass behavior."""

    def test_empty_snapshot(self):
        snap = SupervisorSnapshot(timestamp="2026-03-22T00:00:00+00:00")
        assert snap.lane_assessments == []
        assert snap.watchdog_finding_count == 0
        assert snap.active_failure_count == 0
        assert snap.recommendations == []
        assert snap.summary == {}

    def test_snapshot_with_assessments(self):
        la = LaneHealthAssessment(
            lane_id="ops",
            health="healthy",
            state="active",
        )
        rec = RecoveryRecommendation(
            lane_id="author-a",
            action="respawn",
            reason="stale",
        )
        snap = SupervisorSnapshot(
            timestamp="2026-03-22T00:00:00+00:00",
            lane_assessments=[la],
            watchdog_finding_count=1,
            recommendations=[rec],
            summary={"total_lanes": 1},
        )
        assert len(snap.lane_assessments) == 1
        assert snap.lane_assessments[0].lane_id == "ops"
        assert len(snap.recommendations) == 1


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSnapshotSerialization:
    """Tests for snapshot serialization and deserialization."""

    def test_round_trip(self):
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="degraded",
            state="stale",
            findings=[
                {
                    "severity": "warning",
                    "watchdog": "test",
                    "message": "m",
                    "target": "t",
                }
            ],
            attention_needed=True,
            attention_reason="stale lane",
            current_task="fix bug",
            linked_pr=42,
        )
        rec = RecoveryRecommendation(
            lane_id="author-a",
            action="investigate",
            reason="degraded",
            priority="medium",
            auto_remediable=False,
            recovery_steps=["step 1", "step 2"],
        )
        original = SupervisorSnapshot(
            timestamp="2026-03-22T10:00:00+00:00",
            lane_assessments=[la],
            watchdog_finding_count=1,
            active_failure_count=0,
            recommendations=[rec],
            summary={"total_lanes": 1, "degraded": 1},
        )

        data = _snapshot_to_dict(original)
        restored = _dict_to_snapshot(data)

        assert restored.timestamp == original.timestamp
        assert len(restored.lane_assessments) == 1
        assert restored.lane_assessments[0].lane_id == "author-a"
        assert restored.lane_assessments[0].health == "degraded"
        assert len(restored.lane_assessments[0].findings) == 1
        assert len(restored.recommendations) == 1
        assert restored.recommendations[0].action == "investigate"
        assert restored.summary == original.summary

    def test_json_round_trip(self):
        """Verify JSON serialization is valid."""
        snap = SupervisorSnapshot(
            timestamp="2026-03-22T10:00:00+00:00",
            lane_assessments=[
                LaneHealthAssessment(lane_id="ops", health="healthy", state="active")
            ],
            summary={"total_lanes": 1},
        )
        data = _snapshot_to_dict(snap)
        json_str = json.dumps(data, indent=2)
        restored_data = json.loads(json_str)
        restored = _dict_to_snapshot(restored_data)
        assert restored.timestamp == snap.timestamp


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------


class TestComputeDelta:
    """Tests for compute_delta."""

    def test_no_changes_produces_empty_delta(self):
        la = LaneHealthAssessment(lane_id="author-a", health="healthy", state="active")
        prev = SupervisorSnapshot(
            timestamp="2026-03-22T09:00:00+00:00",
            lane_assessments=[la],
            summary={"total_lanes": 1, "healthy": 1},
        )
        curr = SupervisorSnapshot(
            timestamp="2026-03-22T10:00:00+00:00",
            lane_assessments=[la],
            summary={"total_lanes": 1, "healthy": 1},
        )
        delta = compute_delta(prev, curr)
        assert delta.from_timestamp == prev.timestamp
        assert delta.to_timestamp == curr.timestamp
        assert delta.health_changes == []
        assert delta.new_findings == []
        assert delta.resolved_findings == []
        assert delta.new_recommendations == []
        assert delta.resolved_recommendations == []
        assert delta.summary_deltas == {}

    def test_health_change_detected(self):
        prev = SupervisorSnapshot(
            timestamp="t1",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="author-a", health="healthy", state="active"
                )
            ],
            summary={"healthy": 1, "degraded": 0},
        )
        curr = SupervisorSnapshot(
            timestamp="t2",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="author-a", health="degraded", state="stale"
                )
            ],
            summary={"healthy": 0, "degraded": 1},
        )
        delta = compute_delta(prev, curr)
        assert len(delta.health_changes) == 1
        assert delta.health_changes[0]["lane_id"] == "author-a"
        assert delta.health_changes[0]["from"] == "healthy"
        assert delta.health_changes[0]["to"] == "degraded"
        assert delta.summary_deltas["healthy"] == -1
        assert delta.summary_deltas["degraded"] == 1

    def test_new_lane_in_delta(self):
        prev = SupervisorSnapshot(timestamp="t1", lane_assessments=[])
        curr = SupervisorSnapshot(
            timestamp="t2",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="author-a", health="healthy", state="active"
                )
            ],
        )
        delta = compute_delta(prev, curr)
        assert len(delta.health_changes) == 1
        assert delta.health_changes[0]["from"] == "(absent)"
        assert delta.health_changes[0]["to"] == "healthy"

    def test_removed_lane_in_delta(self):
        prev = SupervisorSnapshot(
            timestamp="t1",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="author-a", health="healthy", state="active"
                )
            ],
        )
        curr = SupervisorSnapshot(timestamp="t2", lane_assessments=[])
        delta = compute_delta(prev, curr)
        assert len(delta.health_changes) == 1
        assert delta.health_changes[0]["from"] == "healthy"
        assert delta.health_changes[0]["to"] == "(absent)"

    def test_new_finding_detected(self):
        prev = SupervisorSnapshot(
            timestamp="t1",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="a", health="healthy", state="active", findings=[]
                )
            ],
        )
        curr = SupervisorSnapshot(
            timestamp="t2",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="a",
                    health="degraded",
                    state="active",
                    findings=[
                        {
                            "watchdog": "ci_stuck",
                            "severity": "warning",
                            "message": "CI stuck",
                            "target": "PR #1",
                        }
                    ],
                )
            ],
        )
        delta = compute_delta(prev, curr)
        assert len(delta.new_findings) == 1
        assert delta.new_findings[0]["watchdog"] == "ci_stuck"
        assert delta.resolved_findings == []

    def test_resolved_finding_detected(self):
        finding = {
            "watchdog": "ci_stuck",
            "severity": "warning",
            "message": "CI stuck",
            "target": "PR #1",
        }
        prev = SupervisorSnapshot(
            timestamp="t1",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="a",
                    health="degraded",
                    state="active",
                    findings=[finding],
                )
            ],
        )
        curr = SupervisorSnapshot(
            timestamp="t2",
            lane_assessments=[
                LaneHealthAssessment(
                    lane_id="a", health="healthy", state="active", findings=[]
                )
            ],
        )
        delta = compute_delta(prev, curr)
        assert len(delta.resolved_findings) == 1
        assert delta.new_findings == []

    def test_new_recommendation_detected(self):
        prev = SupervisorSnapshot(timestamp="t1", recommendations=[])
        rec = RecoveryRecommendation(lane_id="a", action="respawn", reason="stale")
        curr = SupervisorSnapshot(timestamp="t2", recommendations=[rec])
        delta = compute_delta(prev, curr)
        assert len(delta.new_recommendations) == 1
        assert delta.new_recommendations[0]["action"] == "respawn"

    def test_resolved_recommendation_detected(self):
        rec = RecoveryRecommendation(lane_id="a", action="respawn", reason="stale")
        prev = SupervisorSnapshot(timestamp="t1", recommendations=[rec])
        curr = SupervisorSnapshot(timestamp="t2", recommendations=[])
        delta = compute_delta(prev, curr)
        assert len(delta.resolved_recommendations) == 1


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestSnapshotPersistence:
    """Tests for save_snapshot / load_latest_snapshot."""

    def test_save_and_load(self, runtime_dir: Path):
        snap = SupervisorSnapshot(
            timestamp="2026-03-22T10:00:00+00:00",
            lane_assessments=[
                LaneHealthAssessment(lane_id="ops", health="healthy", state="active")
            ],
            summary={"total_lanes": 1},
        )
        path = save_snapshot(snap, runtime_dir)
        assert path.exists()
        assert path.suffix == ".json"

        loaded = load_latest_snapshot(runtime_dir)
        assert loaded is not None
        assert loaded.timestamp == snap.timestamp
        assert len(loaded.lane_assessments) == 1

    def test_load_latest_returns_newest(self, runtime_dir: Path):
        snap1 = SupervisorSnapshot(timestamp="2026-03-22T09:00:00+00:00")
        snap2 = SupervisorSnapshot(timestamp="2026-03-22T10:00:00+00:00")
        save_snapshot(snap1, runtime_dir)
        save_snapshot(snap2, runtime_dir)

        loaded = load_latest_snapshot(runtime_dir)
        assert loaded is not None
        assert loaded.timestamp == "2026-03-22T10:00:00+00:00"

    def test_load_returns_none_when_no_snapshots(self, runtime_dir: Path):
        assert load_latest_snapshot(runtime_dir) is None

    def test_pruning_enforces_limit(self, runtime_dir: Path):
        from bid_euchre.ops.supervisor import MAX_PERSISTED_SNAPSHOTS

        for i in range(MAX_PERSISTED_SNAPSHOTS + 5):
            snap = SupervisorSnapshot(timestamp=f"2026-03-22T{i:02d}:00:00+00:00")
            save_snapshot(snap, runtime_dir)

        snap_dir = runtime_dir / "supervisor_snapshots"
        files = list(snap_dir.glob("snapshot_*.json"))
        assert len(files) <= MAX_PERSISTED_SNAPSHOTS


# ---------------------------------------------------------------------------
# Full cycle
# ---------------------------------------------------------------------------


class TestRunSupervisorCycle:
    """Tests for run_supervisor_cycle."""

    def test_first_cycle_no_delta(self, runtime_dir: Path, plans_dir: Path):
        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = run_supervisor_cycle(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now,
        )
        assert isinstance(result, SupervisorCycleResult)
        assert result.snapshot is not None
        assert result.delta is None
        assert result.has_changes is False

    def test_cycle_with_previous_snapshot(self, runtime_dir: Path, plans_dir: Path):
        now1 = datetime(2026, 3, 22, 9, 0, 0, tzinfo=timezone.utc)
        now2 = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)

        prev = take_snapshot(runtime_dir, plans_dir, now=now1)
        result = run_supervisor_cycle(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now2,
            prev_snapshot=prev,
        )
        assert result.delta is not None
        assert result.delta.from_timestamp == prev.timestamp
        assert result.delta.to_timestamp == result.snapshot.timestamp

    def test_cycle_with_save_persists(self, runtime_dir: Path, plans_dir: Path):
        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = run_supervisor_cycle(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now,
            save=True,
        )
        assert result.snapshot is not None

        loaded = load_latest_snapshot(runtime_dir)
        assert loaded is not None
        assert loaded.timestamp == result.snapshot.timestamp

    def test_cycle_with_save_loads_prev_automatically(
        self, runtime_dir: Path, plans_dir: Path
    ):
        now1 = datetime(2026, 3, 22, 9, 0, 0, tzinfo=timezone.utc)
        now2 = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)

        # First cycle — saves a snapshot
        run_supervisor_cycle(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now1,
            save=True,
        )

        # Second cycle — should auto-load previous
        result = run_supervisor_cycle(
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now2,
            save=True,
        )
        assert result.delta is not None


# ---------------------------------------------------------------------------
# take_snapshot integration
# ---------------------------------------------------------------------------


class TestTakeSnapshot:
    """Tests for take_snapshot with real (empty) runtime dirs."""

    def test_empty_runtime_dir(self, runtime_dir: Path, plans_dir: Path):
        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        snap = take_snapshot(runtime_dir, plans_dir, now=now)
        assert snap.timestamp == now.isoformat()
        assert snap.lane_assessments == []
        # watchdog_finding_count may be >= 0 — watchdogs scan real
        # worktree state even with empty runtime/plans dirs
        assert snap.watchdog_finding_count >= 0
        assert snap.summary["total_lanes"] == 0

    def test_with_registered_lane(self, runtime_dir: Path, plans_dir: Path):
        # Register a lane
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/author-a",
                "branch": "main",
                "lifecycle_class": "persistent",
                "visibility": "background",
            },
        )

        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        snap = take_snapshot(runtime_dir, plans_dir, now=now)
        assert len(snap.lane_assessments) >= 1

        author_a = None
        for la in snap.lane_assessments:
            if la.lane_id == "author-a":
                author_a = la
                break
        assert author_a is not None
        assert author_a.health in HEALTH_LEVELS


# ---------------------------------------------------------------------------
# recommend_recovery
# ---------------------------------------------------------------------------


class TestRecommendRecovery:
    """Tests for recommend_recovery (convenience accessor)."""

    def test_returns_copy_of_recommendations(self):
        rec = RecoveryRecommendation(lane_id="a", action="retry", reason="r")
        snap = SupervisorSnapshot(
            timestamp="t",
            recommendations=[rec],
        )
        result = recommend_recovery(snap)
        assert len(result) == 1
        assert result[0].lane_id == "a"
        # Verify it's a copy, not the same list
        result.clear()
        assert len(snap.recommendations) == 1


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    """Tests for format_supervisor_text and format_supervisor_json."""

    def _make_result(
        self,
        *,
        with_delta: bool = False,
        has_changes: bool = False,
    ) -> SupervisorCycleResult:
        la = LaneHealthAssessment(
            lane_id="author-a",
            health="degraded",
            state="stale",
            findings=[
                {
                    "severity": "warning",
                    "watchdog": "task_progress",
                    "message": "stalled 35min",
                    "target": "author-a",
                }
            ],
            attention_needed=True,
            attention_reason="stale lane",
            current_task="fix bug",
            linked_pr=42,
        )
        rec = RecoveryRecommendation(
            lane_id="author-a",
            action="investigate",
            reason="stale lane",
            priority="medium",
            recovery_steps=["check findings", "verify progress"],
        )
        snap = SupervisorSnapshot(
            timestamp="2026-03-22T10:00:00+00:00",
            lane_assessments=[la],
            watchdog_finding_count=1,
            active_failure_count=0,
            recommendations=[rec],
            summary={
                "total_lanes": 1,
                "degraded": 1,
                "healthy": 0,
                "critical": 0,
                "idle": 0,
                "watchdog_findings": 1,
                "active_failures": 0,
                "attention_needed": 1,
            },
        )

        delta = None
        if with_delta:
            delta = DeltaSummary(
                from_timestamp="2026-03-22T09:00:00+00:00",
                to_timestamp="2026-03-22T10:00:00+00:00",
                health_changes=[
                    {"lane_id": "author-a", "from": "healthy", "to": "degraded"}
                ],
                new_findings=[
                    {
                        "severity": "warning",
                        "watchdog": "task_progress",
                        "message": "stalled 35min",
                        "target": "author-a",
                    }
                ],
                summary_deltas={"healthy": -1, "degraded": 1},
            )

        return SupervisorCycleResult(
            snapshot=snap,
            delta=delta,
            has_changes=has_changes,
        )

    def test_text_format_basic(self):
        result = self._make_result()
        text = format_supervisor_text(result)
        assert "=== Supervisor Report ===" in text
        assert "author-a" in text
        assert "[DEGRADED]" in text
        assert "investigate" in text
        assert "stale lane" in text

    def test_text_format_with_delta(self):
        result = self._make_result(with_delta=True, has_changes=True)
        text = format_supervisor_text(result)
        assert "--- Delta ---" in text
        assert "Health changes:" in text
        assert "healthy -> degraded" in text
        assert "New findings:" in text

    def test_text_format_no_changes_delta(self):
        result = self._make_result(with_delta=True, has_changes=False)
        # Override delta to have no changes
        result.delta = DeltaSummary(from_timestamp="t1", to_timestamp="t2")
        text = format_supervisor_text(result)
        assert "--- Delta: no changes ---" in text

    def test_json_format_structure(self):
        result = self._make_result()
        data = format_supervisor_json(result)
        assert "timestamp" in data
        assert "summary" in data
        assert "lane_assessments" in data
        assert "recommendations" in data
        assert data["has_changes"] is False

    def test_json_format_with_delta(self):
        result = self._make_result(with_delta=True, has_changes=True)
        data = format_supervisor_json(result)
        assert "delta" in data
        assert data["has_changes"] is True
        assert len(data["delta"]["health_changes"]) == 1

    def test_json_is_serializable(self):
        result = self._make_result(with_delta=True, has_changes=True)
        data = format_supervisor_json(result)
        # Must not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    def test_text_format_with_task_and_pr(self):
        result = self._make_result()
        text = format_supervisor_text(result)
        assert "fix bug" in text
        assert "PR #42" in text


# ---------------------------------------------------------------------------
# Health levels constant
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify module constants are well-formed."""

    def test_health_levels_are_ordered(self):
        assert HEALTH_LEVELS == ("critical", "degraded", "healthy", "idle")

    def test_health_levels_tuple(self):
        assert isinstance(HEALTH_LEVELS, tuple)
        assert len(HEALTH_LEVELS) == 4


# ---------------------------------------------------------------------------
# assess_lane_health convenience
# ---------------------------------------------------------------------------


class TestAssessLaneHealth:
    """Tests for the assess_lane_health convenience function."""

    def test_returns_none_for_unknown_lane(self, runtime_dir: Path, plans_dir: Path):
        from bid_euchre.ops.supervisor import assess_lane_health

        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = assess_lane_health(
            "nonexistent-lane",
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now,
        )
        assert result is None

    def test_returns_assessment_for_registered_lane(
        self, runtime_dir: Path, plans_dir: Path
    ):
        from bid_euchre.ops.supervisor import assess_lane_health

        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/author-a",
                "branch": "main",
                "lifecycle_class": "persistent",
            },
        )

        now = datetime(2026, 3, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = assess_lane_health(
            "author-a",
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            now=now,
        )
        assert result is not None
        assert result.lane_id == "author-a"
        assert result.health in HEALTH_LEVELS

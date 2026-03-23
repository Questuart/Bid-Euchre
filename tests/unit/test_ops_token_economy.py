"""Tests for the token economy usage data importer and attribution.

Validates:
- Idempotent import (re-run produces same count)
- Schema validation rejects malformed input
- Imported session count matches source count
- Facet data is merged when available
- Rollup aggregation is correct
- Lane inference from project_path
- Attribution quality enum
- Session-to-packet correlation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.token_economy import (
    AntiPattern,
    AttributionQuality,
    AttributionResult,
    ImportResult,
    SchemaValidationError,
    SessionAttribution,
    SessionRecord,
    ThroughputMetrics,
    UsageSummary,
    _is_session_complete,
    attribute_sessions,
    dashboard_token_economy,
    detect_anti_patterns,
    import_usage_data,
    infer_lane_from_path,
    join_to_packets,
    lane_summary,
    throughput_summary,
    usage_summary,
    validate_facet,
    validate_session_meta,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_session_meta(
    session_id: str = "test-session-001",
    *,
    input_tokens: int = 100,
    output_tokens: int = 500,
    duration_minutes: int = 10,
    lines_added: int = 20,
    lines_removed: int = 5,
    git_commits: int = 1,
    git_pushes: int = 1,
    files_modified: int = 3,
    project_path: str = "/tmp/test-project",
    user_message_count: int = 2,
    assistant_message_count: int = 8,
    tool_errors: int = 0,
) -> dict:
    return {
        "session_id": session_id,
        "project_path": project_path,
        "start_time": "2026-03-20T10:00:00Z",
        "duration_minutes": duration_minutes,
        "user_message_count": user_message_count,
        "assistant_message_count": assistant_message_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_modified": files_modified,
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "tool_counts": {"Bash": 5, "Read": 3},
        "tool_errors": tool_errors,
        "tool_error_categories": {},
        "languages": {"Python": 2},
        "user_interruptions": 0,
        "uses_task_agent": False,
        "uses_mcp": False,
        "uses_web_search": False,
        "uses_web_fetch": False,
        "first_prompt": "Test prompt",
    }


def _make_facet(
    session_id: str = "test-session-001",
    *,
    outcome: str = "fully_achieved",
    brief_summary: str = "Test session",
) -> dict:
    return {
        "session_id": session_id,
        "underlying_goal": "Test goal",
        "outcome": outcome,
        "session_type": "iterative_refinement",
        "claude_helpfulness": "essential",
        "brief_summary": brief_summary,
        "goal_categories": {"infrastructure_automation": 1},
        "friction_counts": {},
        "friction_detail": "",
        "primary_success": "multi_file_changes",
        "user_satisfaction_counts": {"satisfied": 1},
    }


@pytest.fixture()
def usage_dir(tmp_path: Path) -> Path:
    """Create a mock usage-data directory with session-meta and facets."""
    meta_dir = tmp_path / "usage-data" / "session-meta"
    meta_dir.mkdir(parents=True)
    facets_dir = tmp_path / "usage-data" / "facets"
    facets_dir.mkdir(parents=True)
    return tmp_path / "usage-data"


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    """Create an output directory for the importer."""
    out = tmp_path / "token_economy"
    out.mkdir(parents=True)
    return out


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestValidateSessionMeta:
    def test_valid_session_meta(self, tmp_path: Path) -> None:
        data = _make_session_meta()
        validate_session_meta(data, tmp_path / "test.json")  # no raise

    def test_missing_session_id(self, tmp_path: Path) -> None:
        data = {"project_path": "/tmp/test"}
        with pytest.raises(SchemaValidationError, match="Missing required"):
            validate_session_meta(data, tmp_path / "test.json")

    def test_empty_session_id(self, tmp_path: Path) -> None:
        data = {"session_id": ""}
        with pytest.raises(SchemaValidationError, match="non-empty string"):
            validate_session_meta(data, tmp_path / "test.json")

    def test_non_dict_input(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaValidationError, match="Expected dict"):
            validate_session_meta([], tmp_path / "test.json")  # type: ignore[arg-type]

    def test_numeric_session_id(self, tmp_path: Path) -> None:
        data = {"session_id": 123}
        with pytest.raises(SchemaValidationError, match="non-empty string"):
            validate_session_meta(data, tmp_path / "test.json")  # type: ignore[arg-type]


class TestValidateFacet:
    def test_valid_facet(self, tmp_path: Path) -> None:
        data = _make_facet()
        validate_facet(data, tmp_path / "test.json")  # no raise

    def test_non_dict_input(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaValidationError, match="Expected dict"):
            validate_facet("not a dict", tmp_path / "test.json")  # type: ignore[arg-type]

    def test_empty_session_id_in_facet(self, tmp_path: Path) -> None:
        data = {"session_id": "  "}
        with pytest.raises(SchemaValidationError, match="non-empty string"):
            validate_facet(data, tmp_path / "test.json")

    def test_facet_without_session_id_is_valid(self, tmp_path: Path) -> None:
        """Facets may not have session_id (they join by filename)."""
        data = {"outcome": "fully_achieved"}
        validate_facet(data, tmp_path / "test.json")  # no raise


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


class TestImportUsageData:
    def test_import_basic(self, usage_dir: Path, output_dir: Path) -> None:
        """Import 3 sessions, verify counts match."""
        meta_dir = usage_dir / "session-meta"
        facets_dir = usage_dir / "facets"

        for i in range(3):
            sid = f"session-{i:03d}"
            fname = f"{sid}.json"
            (meta_dir / fname).write_text(
                json.dumps(_make_session_meta(sid)), encoding="utf-8"
            )
            (facets_dir / fname).write_text(
                json.dumps(_make_facet(sid)), encoding="utf-8"
            )

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)

        assert isinstance(result, ImportResult)
        assert result.sessions_imported == 3
        assert result.sessions_skipped == 0
        assert result.sessions_failed == 0
        assert result.total_sessions == 3

        # Verify JSONL file has exactly 3 lines
        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        lines = [l for l in jsonl.strip().splitlines() if l.strip()]
        assert len(lines) == 3

        # Verify rollups
        rollups = json.loads(
            (output_dir / "session_rollups.json").read_text(encoding="utf-8")
        )
        assert rollups["session_count"] == 3
        assert rollups["totals"]["input_tokens"] == 300  # 100 * 3
        assert rollups["totals"]["output_tokens"] == 1500  # 500 * 3

    def test_idempotent_import(self, usage_dir: Path, output_dir: Path) -> None:
        """Re-running import does not duplicate sessions."""
        meta_dir = usage_dir / "session-meta"

        for i in range(2):
            sid = f"session-{i:03d}"
            (meta_dir / f"{sid}.json").write_text(
                json.dumps(_make_session_meta(sid)), encoding="utf-8"
            )

        # First import
        r1 = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert r1.sessions_imported == 2
        assert r1.sessions_skipped == 0

        # Second import (same data)
        r2 = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert r2.sessions_imported == 0
        assert r2.sessions_skipped == 2

        # Verify still only 2 lines in JSONL
        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        lines = [l for l in jsonl.strip().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_incremental_import(self, usage_dir: Path, output_dir: Path) -> None:
        """New sessions are added, existing ones are skipped."""
        meta_dir = usage_dir / "session-meta"

        # First batch
        (meta_dir / "session-001.json").write_text(
            json.dumps(_make_session_meta("session-001")), encoding="utf-8"
        )
        r1 = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert r1.sessions_imported == 1

        # Add another session
        (meta_dir / "session-002.json").write_text(
            json.dumps(_make_session_meta("session-002")), encoding="utf-8"
        )
        r2 = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert r2.sessions_imported == 1
        assert r2.sessions_skipped == 1

        # Total should be 2 lines
        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        lines = [l for l in jsonl.strip().splitlines() if l.strip()]
        assert len(lines) == 2

    def test_malformed_json_rejected(self, usage_dir: Path, output_dir: Path) -> None:
        """Malformed JSON files are counted as failed, not crash."""
        meta_dir = usage_dir / "session-meta"

        # Valid session
        (meta_dir / "good.json").write_text(
            json.dumps(_make_session_meta("good-session")), encoding="utf-8"
        )
        # Malformed JSON
        (meta_dir / "bad.json").write_text("{ this is not valid json", encoding="utf-8")

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_imported == 1
        assert result.sessions_failed == 1
        assert result.total_sessions == 2

    def test_missing_required_field_rejected(
        self, usage_dir: Path, output_dir: Path
    ) -> None:
        """Files missing session_id are rejected."""
        meta_dir = usage_dir / "session-meta"

        (meta_dir / "no-id.json").write_text(
            json.dumps({"project_path": "/tmp/test"}), encoding="utf-8"
        )

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_imported == 0
        assert result.sessions_failed == 1

    def test_facet_data_merged(self, usage_dir: Path, output_dir: Path) -> None:
        """Facet data is merged into the session record when available."""
        meta_dir = usage_dir / "session-meta"
        facets_dir = usage_dir / "facets"

        sid = "test-facet-merge"
        fname = f"{sid}.json"
        (meta_dir / fname).write_text(
            json.dumps(_make_session_meta(sid)), encoding="utf-8"
        )
        (facets_dir / fname).write_text(
            json.dumps(
                _make_facet(sid, outcome="partially_achieved", brief_summary="Merged!")
            ),
            encoding="utf-8",
        )

        import_usage_data(usage_dir=usage_dir, output_dir=output_dir)

        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        rec = json.loads(jsonl.strip())
        assert rec["outcome"] == "partially_achieved"
        assert rec["brief_summary"] == "Merged!"
        assert rec["underlying_goal"] == "Test goal"

    def test_session_without_facet(self, usage_dir: Path, output_dir: Path) -> None:
        """Sessions without facet files are imported successfully."""
        meta_dir = usage_dir / "session-meta"

        sid = "no-facet-session"
        (meta_dir / f"{sid}.json").write_text(
            json.dumps(_make_session_meta(sid)), encoding="utf-8"
        )
        # No corresponding facet file

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_imported == 1

        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        rec = json.loads(jsonl.strip())
        assert rec["outcome"] is None
        assert rec["brief_summary"] is None

    def test_empty_usage_dir(self, tmp_path: Path) -> None:
        """Empty/missing session-meta dir returns zero counts."""
        empty_dir = tmp_path / "empty-usage"
        empty_dir.mkdir()
        out = tmp_path / "token_economy"

        result = import_usage_data(usage_dir=empty_dir, output_dir=out)
        assert result.sessions_imported == 0
        assert result.total_sessions == 0

    def test_rollup_aggregation(self, usage_dir: Path, output_dir: Path) -> None:
        """Rollups aggregate token counts correctly."""
        meta_dir = usage_dir / "session-meta"

        (meta_dir / "s1.json").write_text(
            json.dumps(
                _make_session_meta(
                    "s1",
                    input_tokens=200,
                    output_tokens=1000,
                    lines_added=50,
                    lines_removed=10,
                    git_commits=3,
                    tool_errors=2,
                )
            ),
            encoding="utf-8",
        )
        (meta_dir / "s2.json").write_text(
            json.dumps(
                _make_session_meta(
                    "s2",
                    input_tokens=300,
                    output_tokens=2000,
                    lines_added=100,
                    lines_removed=20,
                    git_commits=1,
                    tool_errors=1,
                )
            ),
            encoding="utf-8",
        )

        import_usage_data(usage_dir=usage_dir, output_dir=output_dir)

        rollups = json.loads(
            (output_dir / "session_rollups.json").read_text(encoding="utf-8")
        )
        assert rollups["session_count"] == 2
        totals = rollups["totals"]
        assert totals["input_tokens"] == 500
        assert totals["output_tokens"] == 3000
        assert totals["total_tokens"] == 3500
        assert totals["lines_added"] == 150
        assert totals["lines_removed"] == 30
        assert totals["net_lines"] == 120
        assert totals["git_commits"] == 4
        assert totals["tool_errors"] == 3

    def test_source_tracking_in_record(self, usage_dir: Path, output_dir: Path) -> None:
        """Records include source path and hash for traceability."""
        meta_dir = usage_dir / "session-meta"

        sid = "tracked-session"
        fname = f"{sid}.json"
        (meta_dir / fname).write_text(
            json.dumps(_make_session_meta(sid)), encoding="utf-8"
        )

        import_usage_data(usage_dir=usage_dir, output_dir=output_dir)

        jsonl = (output_dir / "session_usage.jsonl").read_text(encoding="utf-8")
        rec = json.loads(jsonl.strip())
        assert rec["source_path"].endswith(fname)
        assert len(rec["source_hash"]) == 64  # SHA-256 hex digest
        assert rec["import_timestamp"]  # non-empty
        assert rec["schema_version"] == 1

    def test_non_dict_json_rejected(self, usage_dir: Path, output_dir: Path) -> None:
        """JSON files containing arrays instead of dicts are rejected."""
        meta_dir = usage_dir / "session-meta"

        (meta_dir / "array.json").write_text("[1, 2, 3]", encoding="utf-8")

        result = import_usage_data(usage_dir=usage_dir, output_dir=output_dir)
        assert result.sessions_failed == 1
        assert result.sessions_imported == 0


# ---------------------------------------------------------------------------
# SessionRecord tests
# ---------------------------------------------------------------------------


class TestSessionRecord:
    def test_defaults(self) -> None:
        rec = SessionRecord(session_id="test")
        assert rec.session_id == "test"
        assert rec.input_tokens is None
        assert rec.tool_counts == {}
        assert rec.outcome is None

    def test_schema_version(self) -> None:
        rec = SessionRecord(session_id="test")
        assert rec.schema_version == 1


# ---------------------------------------------------------------------------
# Lane inference tests
# ---------------------------------------------------------------------------


class TestInferLaneFromPath:
    """Test lane ID inference from session project_path."""

    def test_platform_author_a(self) -> None:
        path = "/Users/claude_runner/Projects/Bid-Euchre-meta/Bid-Euchre-steward-author"
        lane, wt = infer_lane_from_path(path)
        assert lane == "author-a"
        assert wt == "Bid-Euchre-steward-author"

    def test_platform_author_b(self) -> None:
        path = "/Users/foo/Bid-Euchre-meta/Bid-Euchre-steward-author-b"
        lane, wt = infer_lane_from_path(path)
        assert lane == "author-b"
        assert wt == "Bid-Euchre-steward-author-b"

    def test_platform_author_scratch(self) -> None:
        path = "/Users/foo/Bid-Euchre-meta/Bid-Euchre-steward-author-scratch"
        lane, wt = infer_lane_from_path(path)
        assert lane == "author-scratch"

    def test_browser_game_pool(self) -> None:
        path = "/Users/foo/meta/Bid-Euchre-steward-brws-author-a"
        lane, wt = infer_lane_from_path(path)
        assert lane == "brws-author-a"
        assert wt == "Bid-Euchre-steward-brws-author-a"

    def test_flex_pool(self) -> None:
        path = "/Users/foo/meta/Bid-Euchre-steward-flex-b"
        lane, wt = infer_lane_from_path(path)
        assert lane == "flex-b"

    def test_control_ops(self) -> None:
        path = "/Users/foo/meta/Bid-Euchre-steward-ops"
        lane, wt = infer_lane_from_path(path)
        assert lane == "ops"

    def test_control_review(self) -> None:
        path = "/Users/foo/meta/Bid-Euchre-steward-review"
        lane, wt = infer_lane_from_path(path)
        assert lane == "review"

    def test_main_checkout(self) -> None:
        path = "/Users/foo/Projects/Bid-Euchre-meta/Bid-Euchre"
        lane, wt = infer_lane_from_path(path)
        assert lane == "main-checkout"
        assert wt == "Bid-Euchre"

    def test_unknown_project(self) -> None:
        path = "/Users/foo/some-other-project"
        lane, wt = infer_lane_from_path(path)
        assert lane is None
        assert wt is None

    def test_none_path(self) -> None:
        lane, wt = infer_lane_from_path(None)
        assert lane is None
        assert wt is None

    def test_empty_path(self) -> None:
        lane, wt = infer_lane_from_path("")
        assert lane is None
        assert wt is None

    def test_subdirectory_of_worktree(self) -> None:
        """Sessions may run from subdirectories of the worktree."""
        path = "/Users/foo/meta/Bid-Euchre-steward-author/src/bid_euchre"
        lane, wt = infer_lane_from_path(path)
        assert lane == "author-a"
        assert wt == "Bid-Euchre-steward-author"

    def test_all_known_lanes_covered(self) -> None:
        """Every known author lane maps from at least one worktree path."""
        from bid_euchre.ops.token_economy import _WORKTREE_TO_LANE

        expected_lanes = {
            "author-a",
            "author-b",
            "author-c",
            "author-d",
            "author-scratch",
            "brws-author-a",
            "brws-author-b",
            "brws-author-c",
            "brws-author-d",
            "flex-a",
            "flex-b",
            "flex-c",
            "review",
            "ops",
        }
        assert set(_WORKTREE_TO_LANE.values()) == expected_lanes


# ---------------------------------------------------------------------------
# Attribution quality tests
# ---------------------------------------------------------------------------


class TestAttributionQuality:
    def test_enum_values(self) -> None:
        assert AttributionQuality.ATTRIBUTED.value == "attributed"
        assert AttributionQuality.PARTIALLY_ATTRIBUTED.value == "partially_attributed"
        assert AttributionQuality.UNATTRIBUTED.value == "unattributed"

    def test_string_enum(self) -> None:
        """AttributionQuality is a str enum for JSON serialization."""
        assert isinstance(AttributionQuality.ATTRIBUTED, str)


# ---------------------------------------------------------------------------
# Attribution integration tests
# ---------------------------------------------------------------------------


def _populate_store(output_dir: Path, sessions: list[dict]) -> None:
    """Write session records to session_usage.jsonl for attribution tests."""
    usage_file = output_dir / "session_usage.jsonl"
    with usage_file.open("w", encoding="utf-8") as f:
        for s in sessions:
            f.write(json.dumps(s) + "\n")


class TestAttributeSessions:
    def test_attribute_steward_sessions(self, output_dir: Path) -> None:
        """Sessions from steward worktrees get lane attribution."""
        sessions = [
            {
                "session_id": "s1",
                "project_path": "/Users/foo/meta/Bid-Euchre-steward-author",
                "start_time": "2026-03-20T10:00:00Z",
                "duration_minutes": 30,
                "input_tokens": 100,
                "output_tokens": 500,
                "lines_added": 20,
                "lines_removed": 5,
                "git_commits": 1,
            },
            {
                "session_id": "s2",
                "project_path": "/Users/foo/meta/Bid-Euchre-steward-flex-a",
                "start_time": "2026-03-20T11:00:00Z",
                "duration_minutes": 15,
                "input_tokens": 50,
                "output_tokens": 200,
                "lines_added": 10,
                "lines_removed": 2,
                "git_commits": 0,
            },
        ]
        _populate_store(output_dir, sessions)

        # Use an empty task queue so packet join is skipped
        tq_dir = output_dir / "empty_tq"
        tq_dir.mkdir()

        result = attribute_sessions(output_dir=output_dir, task_queue_root=tq_dir)

        assert isinstance(result, AttributionResult)
        assert result.total_sessions == 2
        assert result.partially_attributed == 2  # lane found, no packet match
        assert result.unattributed == 0
        assert "author-a" in result.lanes_found
        assert "flex-a" in result.lanes_found

        # Verify attributions file
        attr_file = output_dir / "session_attributions.jsonl"
        assert attr_file.exists()
        lines = [json.loads(l) for l in attr_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert lines[0]["lane_id"] == "author-a"
        assert lines[0]["worktree_class"] == "platform"
        assert lines[1]["lane_id"] == "flex-a"
        assert lines[1]["worktree_class"] == "flex"

    def test_attribute_unrecognized_project(self, output_dir: Path) -> None:
        """Sessions from unknown projects are marked unattributed."""
        sessions = [
            {
                "session_id": "s1",
                "project_path": "/Users/foo/other-project",
                "start_time": "2026-03-20T10:00:00Z",
                "duration_minutes": 10,
                "input_tokens": 100,
                "output_tokens": 500,
            },
        ]
        _populate_store(output_dir, sessions)

        tq_dir = output_dir / "empty_tq"
        tq_dir.mkdir()

        result = attribute_sessions(output_dir=output_dir, task_queue_root=tq_dir)

        assert result.unattributed == 1
        assert result.partially_attributed == 0

    def test_attribute_empty_store(self, output_dir: Path) -> None:
        """Empty session store returns zero counts."""
        result = attribute_sessions(output_dir=output_dir)
        assert result.total_sessions == 0
        assert result.lanes_found == []

    def test_attribute_main_checkout(self, output_dir: Path) -> None:
        """Main checkout sessions are partially attributed."""
        sessions = [
            {
                "session_id": "s1",
                "project_path": "/Users/foo/meta/Bid-Euchre",
                "start_time": "2026-03-20T10:00:00Z",
                "duration_minutes": 10,
                "input_tokens": 100,
                "output_tokens": 500,
            },
        ]
        _populate_store(output_dir, sessions)

        tq_dir = output_dir / "empty_tq"
        tq_dir.mkdir()

        result = attribute_sessions(output_dir=output_dir, task_queue_root=tq_dir)

        assert result.partially_attributed == 1
        assert "main-checkout" in result.lanes_found


# ---------------------------------------------------------------------------
# Packet join tests
# ---------------------------------------------------------------------------


class TestJoinToPackets:
    def test_join_by_lane_and_time(self, tmp_path: Path) -> None:
        """Sessions are joined to packets by matching lane + time overlap."""
        # Create a task queue with one packet
        tq_dir = tmp_path / "task_queue"
        tq_dir.mkdir()
        pkt = {
            "packet_id": "pkt-001",
            "title": "Test task",
            "description": "Test",
            "owner": "author-a",
            "created_by": "orchestrator",
            "created_at": "2026-03-20T09:30:00Z",
            "status": "completed",
            "metadata": {"completed_at": "2026-03-20T11:00:00Z"},
        }
        (tq_dir / "pkt-001.json").write_text(json.dumps(pkt), encoding="utf-8")

        # Create attribution with overlapping time
        attr = SessionAttribution(
            session_id="s1",
            lane_id="author-a",
            quality=AttributionQuality.PARTIALLY_ATTRIBUTED.value,
            attribution_timestamp="2026-03-20T10:00:00Z",
            duration_minutes=30,
        )

        result = join_to_packets([attr], task_queue_root=tq_dir)

        assert len(result) == 1
        assert "pkt-001" in result[0].matched_packets
        assert result[0].quality == AttributionQuality.ATTRIBUTED.value

    def test_no_join_wrong_lane(self, tmp_path: Path) -> None:
        """Sessions don't join to packets on a different lane."""
        tq_dir = tmp_path / "task_queue"
        tq_dir.mkdir()
        pkt = {
            "packet_id": "pkt-001",
            "title": "Test task",
            "description": "Test",
            "owner": "author-b",
            "created_by": "orchestrator",
            "created_at": "2026-03-20T09:30:00Z",
            "status": "completed",
            "metadata": {},
        }
        (tq_dir / "pkt-001.json").write_text(json.dumps(pkt), encoding="utf-8")

        attr = SessionAttribution(
            session_id="s1",
            lane_id="author-a",
            quality=AttributionQuality.PARTIALLY_ATTRIBUTED.value,
            attribution_timestamp="2026-03-20T10:00:00Z",
            duration_minutes=30,
        )

        result = join_to_packets([attr], task_queue_root=tq_dir)

        assert result[0].matched_packets == []
        assert result[0].quality == AttributionQuality.PARTIALLY_ATTRIBUTED.value

    def test_no_join_non_overlapping_time(self, tmp_path: Path) -> None:
        """Sessions don't join if time windows don't overlap."""
        tq_dir = tmp_path / "task_queue"
        tq_dir.mkdir()
        pkt = {
            "packet_id": "pkt-001",
            "title": "Test task",
            "description": "Test",
            "owner": "author-a",
            "created_by": "orchestrator",
            "created_at": "2026-03-20T09:00:00Z",
            "status": "completed",
            "metadata": {"completed_at": "2026-03-20T09:30:00Z"},
        }
        (tq_dir / "pkt-001.json").write_text(json.dumps(pkt), encoding="utf-8")

        attr = SessionAttribution(
            session_id="s1",
            lane_id="author-a",
            quality=AttributionQuality.PARTIALLY_ATTRIBUTED.value,
            attribution_timestamp="2026-03-20T12:00:00Z",
            duration_minutes=30,
        )

        result = join_to_packets([attr], task_queue_root=tq_dir)

        assert result[0].matched_packets == []

    def test_join_with_archived_packets(self, tmp_path: Path) -> None:
        """Archived packets are also checked for joins."""
        tq_dir = tmp_path / "task_queue"
        tq_dir.mkdir()
        archive_dir = tq_dir / "archive"
        archive_dir.mkdir()

        pkt = {
            "packet_id": "pkt-archived",
            "title": "Archived task",
            "description": "Test",
            "owner": "author-a",
            "created_by": "orchestrator",
            "created_at": "2026-03-20T09:30:00Z",
            "status": "completed",
            "metadata": {"completed_at": "2026-03-20T11:00:00Z"},
        }
        (archive_dir / "pkt-archived.json").write_text(
            json.dumps(pkt), encoding="utf-8"
        )

        attr = SessionAttribution(
            session_id="s1",
            lane_id="author-a",
            quality=AttributionQuality.PARTIALLY_ATTRIBUTED.value,
            attribution_timestamp="2026-03-20T10:00:00Z",
            duration_minutes=30,
        )

        result = join_to_packets([attr], task_queue_root=tq_dir)

        assert "pkt-archived" in result[0].matched_packets

    def test_empty_task_queue(self, tmp_path: Path) -> None:
        """Empty task queue leaves attributions unchanged."""
        tq_dir = tmp_path / "task_queue"
        tq_dir.mkdir()

        attr = SessionAttribution(
            session_id="s1",
            lane_id="author-a",
            quality=AttributionQuality.PARTIALLY_ATTRIBUTED.value,
            attribution_timestamp="2026-03-20T10:00:00Z",
            duration_minutes=30,
        )

        result = join_to_packets([attr], task_queue_root=tq_dir)

        assert result[0].matched_packets == []
        assert result[0].quality == AttributionQuality.PARTIALLY_ATTRIBUTED.value


# ---------------------------------------------------------------------------
# Usage summary tests
# ---------------------------------------------------------------------------


def _make_session_record(
    session_id: str,
    *,
    input_tokens: int = 100,
    output_tokens: int = 500,
    duration_minutes: int = 30,
    lines_added: int = 20,
    lines_removed: int = 5,
    git_commits: int = 1,
    git_pushes: int = 1,
    files_modified: int = 3,
    user_message_count: int = 2,
    assistant_message_count: int = 10,
    tool_errors: int = 0,
    start_time: str = "2026-03-20T10:00:00Z",
    project_path: str = "/tmp/test",
) -> dict:
    """Build a session record dict for summary tests."""
    return {
        "session_id": session_id,
        "project_path": project_path,
        "start_time": start_time,
        "duration_minutes": duration_minutes,
        "user_message_count": user_message_count,
        "assistant_message_count": assistant_message_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_modified": files_modified,
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "tool_errors": tool_errors,
    }


def _write_sessions(output_dir: Path, sessions: list[dict]) -> None:
    """Write session records to session_usage.jsonl."""
    usage_file = output_dir / "session_usage.jsonl"
    with usage_file.open("w", encoding="utf-8") as f:
        for s in sessions:
            f.write(json.dumps(s) + "\n")


def _write_attributions(output_dir: Path, attributions: list[dict]) -> None:
    """Write attribution records to session_attributions.jsonl."""
    attr_file = output_dir / "session_attributions.jsonl"
    with attr_file.open("w", encoding="utf-8") as f:
        for a in attributions:
            f.write(json.dumps(a) + "\n")


class TestUsageSummary:
    def test_basic_summary(self, output_dir: Path) -> None:
        """Summary aggregates token counts correctly."""
        sessions = [
            _make_session_record("s1", input_tokens=100, output_tokens=500),
            _make_session_record(
                "s2",
                input_tokens=200,
                output_tokens=1000,
                start_time="2026-03-21T14:00:00Z",
            ),
        ]
        _write_sessions(output_dir, sessions)

        result = usage_summary(output_dir=output_dir)

        assert isinstance(result, UsageSummary)
        assert result.session_count == 2
        assert result.total_input_tokens == 300
        assert result.total_output_tokens == 1500
        assert result.total_tokens == 1800
        assert result.time_range_start == "2026-03-20T10:00:00Z"
        assert result.time_range_end == "2026-03-21T14:00:00Z"

    def test_derived_metrics(self, output_dir: Path) -> None:
        """Output/input ratio and tokens/hour are computed correctly."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=100,
                output_tokens=400,
                duration_minutes=60,
            ),
        ]
        _write_sessions(output_dir, sessions)

        result = usage_summary(output_dir=output_dir)

        assert result.output_input_ratio == pytest.approx(4.0)
        assert result.tokens_per_hour == pytest.approx(500.0)

    def test_empty_store(self, output_dir: Path) -> None:
        """Empty store returns zero summary."""
        result = usage_summary(output_dir=output_dir)
        assert result.session_count == 0
        assert result.total_tokens == 0


# ---------------------------------------------------------------------------
# Lane summary tests
# ---------------------------------------------------------------------------


class TestLaneSummary:
    def test_per_lane_breakdown(self, output_dir: Path) -> None:
        """Lanes are aggregated from attribution data."""
        attributions = [
            {
                "session_id": "s1",
                "lane_id": "author-a",
                "worktree_class": "platform",
                "input_tokens": 100,
                "output_tokens": 500,
                "duration_minutes": 30,
                "lines_added": 20,
                "lines_removed": 5,
                "git_commits": 2,
            },
            {
                "session_id": "s2",
                "lane_id": "author-a",
                "worktree_class": "platform",
                "input_tokens": 200,
                "output_tokens": 1000,
                "duration_minutes": 45,
                "lines_added": 30,
                "lines_removed": 10,
                "git_commits": 1,
            },
            {
                "session_id": "s3",
                "lane_id": "flex-a",
                "worktree_class": "flex",
                "input_tokens": 50,
                "output_tokens": 200,
                "duration_minutes": 10,
                "lines_added": 5,
                "lines_removed": 0,
                "git_commits": 1,
            },
        ]
        _write_attributions(output_dir, attributions)

        result = lane_summary(output_dir=output_dir)

        assert isinstance(result, list)
        assert len(result) == 2

        # Sorted by total_tokens desc — author-a first
        assert result[0].lane_id == "author-a"
        assert result[0].session_count == 2
        assert result[0].total_tokens == 1800
        assert result[0].git_commits == 3
        assert result[0].tokens_per_commit == pytest.approx(600.0)
        assert result[0].pool == "platform"

        assert result[1].lane_id == "flex-a"
        assert result[1].total_tokens == 250
        assert result[1].pool == "flex"

    def test_empty_attributions(self, output_dir: Path) -> None:
        """Empty attributions returns empty list."""
        result = lane_summary(output_dir=output_dir)
        assert result == []

    def test_unattributed_sessions(self, output_dir: Path) -> None:
        """Sessions without lane_id are grouped as unattributed."""
        attributions = [
            {
                "session_id": "s1",
                "lane_id": None,
                "input_tokens": 100,
                "output_tokens": 500,
                "git_commits": 0,
            },
        ]
        _write_attributions(output_dir, attributions)

        result = lane_summary(output_dir=output_dir)
        assert len(result) == 1
        assert result[0].lane_id == "unattributed"


# ---------------------------------------------------------------------------
# Throughput summary tests
# ---------------------------------------------------------------------------


class TestThroughputSummary:
    def test_throughput_metrics(self, output_dir: Path) -> None:
        """Throughput metrics are computed from usage summary."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=100,
                output_tokens=400,
                duration_minutes=60,
                git_commits=2,
                lines_added=50,
                lines_removed=10,
                tool_errors=3,
            ),
        ]
        _write_sessions(output_dir, sessions)

        result = throughput_summary(output_dir=output_dir)

        assert isinstance(result, ThroughputMetrics)
        assert result.total_sessions == 1
        assert result.total_tokens == 500
        assert result.tokens_per_commit == pytest.approx(250.0)
        assert result.tokens_per_net_line == pytest.approx(500 / 40)
        assert result.tokens_per_hour == pytest.approx(500.0)
        assert result.output_input_ratio == pytest.approx(4.0)
        assert result.tool_errors_per_1k_tokens == pytest.approx(6.0)

    def test_empty_store(self, output_dir: Path) -> None:
        """Empty store returns zero metrics."""
        result = throughput_summary(output_dir=output_dir)
        assert result.total_sessions == 0
        assert result.total_tokens == 0


# ---------------------------------------------------------------------------
# Anti-pattern detection tests
# ---------------------------------------------------------------------------


class TestDetectAntiPatterns:
    def test_verbosity_waste(self, output_dir: Path) -> None:
        """High tokens per net line triggers verbosity_waste."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=5000,
                output_tokens=50000,
                lines_added=20,
                lines_removed=10,  # net 10 lines
            ),
        ]
        _write_sessions(output_dir, sessions)

        findings = detect_anti_patterns(output_dir=output_dir)

        verbosity = [f for f in findings if f.pattern_id == "verbosity_waste"]
        assert len(verbosity) == 1
        assert verbosity[0].severity == "high"
        assert isinstance(verbosity[0], AntiPattern)

    def test_retry_churn(self, output_dir: Path) -> None:
        """Many zero-commit sessions triggers retry_churn."""
        sessions = [
            _make_session_record("s1", git_commits=0),
            _make_session_record("s2", git_commits=0),
            _make_session_record("s3", git_commits=1),
        ]
        _write_sessions(output_dir, sessions)

        findings = detect_anti_patterns(output_dir=output_dir)

        churn = [f for f in findings if f.pattern_id == "retry_churn"]
        assert len(churn) == 1
        assert "67" in churn[0].description  # 66.7% rounds to 67%

    def test_no_anti_patterns(self, output_dir: Path) -> None:
        """Clean usage data produces no findings."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=100,
                output_tokens=200,
                lines_added=50,
                lines_removed=5,
                git_commits=3,
                duration_minutes=30,
                tool_errors=0,
                user_message_count=5,
                assistant_message_count=15,
            ),
        ]
        _write_sessions(output_dir, sessions)

        findings = detect_anti_patterns(output_dir=output_dir)
        assert findings == []

    def test_empty_store(self, output_dir: Path) -> None:
        """Empty store produces no findings."""
        findings = detect_anti_patterns(output_dir=output_dir)
        assert findings == []

    def test_severity_ordering(self, output_dir: Path) -> None:
        """Findings are sorted by severity: high first."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=10000,
                output_tokens=100000,
                lines_added=5,
                lines_removed=0,
                git_commits=0,
                duration_minutes=30,
                tool_errors=0,
            ),
            _make_session_record("s2", git_commits=0),
        ]
        _write_sessions(output_dir, sessions)

        findings = detect_anti_patterns(output_dir=output_dir)

        if len(findings) >= 2:
            severity_order = {"high": 0, "medium": 1, "low": 2}
            for i in range(len(findings) - 1):
                assert severity_order.get(
                    findings[i].severity, 99
                ) <= severity_order.get(findings[i + 1].severity, 99)

    def test_fragmentation(self, output_dir: Path) -> None:
        """Many short sessions triggers fragmentation."""
        sessions = [
            _make_session_record(
                f"s{i}",
                duration_minutes=2,
                git_commits=1,
                lines_added=50,
                lines_removed=5,
            )
            for i in range(10)
        ]
        _write_sessions(output_dir, sessions)

        findings = detect_anti_patterns(output_dir=output_dir)

        frag = [f for f in findings if f.pattern_id == "fragmentation"]
        assert len(frag) == 1
        assert frag[0].severity == "low"


# ---------------------------------------------------------------------------
# Dashboard token economy tests
# ---------------------------------------------------------------------------


class TestDashboardTokenEconomy:
    def test_dashboard_with_data(self, output_dir: Path) -> None:
        """Dashboard builds complete sections when data exists."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=100,
                output_tokens=400,
                duration_minutes=30,
                git_commits=2,
                lines_added=50,
                lines_removed=10,
                project_path="/Users/foo/Bid-Euchre-steward-author",
            ),
            _make_session_record(
                "s2",
                input_tokens=200,
                output_tokens=800,
                duration_minutes=45,
                git_commits=1,
                lines_added=30,
                lines_removed=5,
                project_path="/Users/foo/Bid-Euchre-steward-flex-a",
            ),
        ]
        _write_sessions(output_dir, sessions)

        # Write attributions for lane breakdown
        attributions = [
            {
                "session_id": "s1",
                "lane_id": "author-a",
                "worktree_class": "platform",
                "input_tokens": 100,
                "output_tokens": 400,
                "git_commits": 2,
                "lines_added": 50,
                "lines_removed": 10,
                "duration_minutes": 30,
            },
            {
                "session_id": "s2",
                "lane_id": "flex-a",
                "worktree_class": "flex",
                "input_tokens": 200,
                "output_tokens": 800,
                "git_commits": 1,
                "lines_added": 30,
                "lines_removed": 5,
                "duration_minutes": 45,
            },
        ]
        _write_attributions(output_dir, attributions)

        result = dashboard_token_economy(output_dir=output_dir)

        assert isinstance(result, dict)
        assert "overview" in result
        assert "top_lanes" in result
        assert "efficient_lanes" in result
        assert "throughput" in result
        assert "anti_patterns" in result

        # Overview checks
        assert result["overview"]["session_count"] == 2
        assert result["overview"]["total_tokens"] == 1500
        assert result["overview"]["total_git_commits"] == 3

        # Top lanes
        assert len(result["top_lanes"]) == 2
        assert result["top_lanes"][0]["lane_id"] == "flex-a"  # most expensive

        # Efficient lanes (sorted by tokens_per_commit asc)
        assert len(result["efficient_lanes"]) == 2

        # Throughput
        assert result["throughput"]["tokens_per_commit"] > 0

    def test_dashboard_empty_store(self, output_dir: Path) -> None:
        """Dashboard returns empty dict when no data exists."""
        result = dashboard_token_economy(output_dir=output_dir)
        assert result == {}

    def test_dashboard_null_safe(self, output_dir: Path) -> None:
        """Dashboard handles sessions with missing optional fields."""
        sessions = [
            {
                "session_id": "s1",
                "start_time": "2026-03-20T10:00:00Z",
                # Minimal fields — many optional fields missing
            },
        ]
        _write_sessions(output_dir, sessions)

        result = dashboard_token_economy(output_dir=output_dir)

        assert result["overview"]["session_count"] == 1
        assert result["overview"]["total_tokens"] == 0

    def test_dashboard_anti_patterns_included(self, output_dir: Path) -> None:
        """Dashboard includes anti-pattern findings."""
        sessions = [
            _make_session_record(
                "s1",
                input_tokens=5000,
                output_tokens=50000,
                lines_added=20,
                lines_removed=10,  # net 10 → 5500 tok/net line
            ),
        ]
        _write_sessions(output_dir, sessions)

        result = dashboard_token_economy(output_dir=output_dir)

        assert len(result["anti_patterns"]) > 0
        assert result["anti_patterns"][0]["pattern_id"] == "verbosity_waste"


# ---------------------------------------------------------------------------
# Incomplete session exclusion tests
# ---------------------------------------------------------------------------


class TestIsSessionComplete:
    def test_complete_session(self) -> None:
        """Session with duration_minutes is complete."""
        rec = {"session_id": "s1", "duration_minutes": 30}
        assert _is_session_complete(rec) is True

    def test_incomplete_session_none(self) -> None:
        """Session with duration_minutes=None is incomplete."""
        rec = {"session_id": "s1", "duration_minutes": None}
        assert _is_session_complete(rec) is False

    def test_incomplete_session_missing(self) -> None:
        """Session without duration_minutes key is incomplete."""
        rec = {"session_id": "s1"}
        assert _is_session_complete(rec) is False

    def test_zero_duration_is_complete(self) -> None:
        """Session with duration_minutes=0 is still considered complete."""
        rec = {"session_id": "s1", "duration_minutes": 0}
        assert _is_session_complete(rec) is True


class TestIncompleteSessionExclusion:
    """Verify incomplete sessions are excluded from throughput ratios and
    anti-pattern detection (issue #1412)."""

    def test_throughput_excludes_incomplete(self, output_dir: Path) -> None:
        """Throughput metrics ignore sessions without duration_minutes."""
        complete = _make_session_record(
            "s1",
            input_tokens=100,
            output_tokens=400,
            duration_minutes=60,
            git_commits=2,
            lines_added=50,
            lines_removed=10,
        )
        # Incomplete session: has tokens but no duration (still in progress)
        incomplete = {
            "session_id": "s2",
            "input_tokens": 5000,
            "output_tokens": 20000,
            "lines_added": 0,
            "lines_removed": 0,
            "git_commits": 0,
            "git_pushes": 0,
            "start_time": "2026-03-21T10:00:00Z",
            # duration_minutes intentionally omitted — incomplete session
        }
        _write_sessions(output_dir, [complete, incomplete])

        result = throughput_summary(output_dir=output_dir)

        # Should only reflect the complete session
        assert result.total_sessions == 1
        assert result.total_tokens == 500  # 100 + 400 from complete only
        assert result.tokens_per_commit == pytest.approx(250.0)

    def test_usage_summary_exclude_incomplete(self, output_dir: Path) -> None:
        """usage_summary with exclude_incomplete=True filters properly."""
        complete = _make_session_record("s1", duration_minutes=30)
        incomplete = {
            "session_id": "s2",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "start_time": "2026-03-21T10:00:00Z",
            # no duration_minutes
        }
        _write_sessions(output_dir, [complete, incomplete])

        # Default: includes all
        all_result = usage_summary(output_dir=output_dir)
        assert all_result.session_count == 2

        # Excluding incomplete
        filtered = usage_summary(output_dir=output_dir, exclude_incomplete=True)
        assert filtered.session_count == 1

    def test_anti_patterns_exclude_incomplete(self, output_dir: Path) -> None:
        """Anti-pattern detection ignores incomplete sessions."""
        # One complete session with zero commits (would normally be "churn")
        complete_zero = _make_session_record("s1", git_commits=0, duration_minutes=30)
        complete_good = _make_session_record("s2", git_commits=3, duration_minutes=45)
        # Incomplete session with zero commits — should NOT count as churn
        incomplete = {
            "session_id": "s3",
            "input_tokens": 500,
            "output_tokens": 1000,
            "git_commits": 0,
            "git_pushes": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "start_time": "2026-03-21T10:00:00Z",
            # no duration_minutes — still in progress
        }
        _write_sessions(output_dir, [complete_zero, complete_good, incomplete])

        findings = detect_anti_patterns(output_dir=output_dir)

        churn = [f for f in findings if f.pattern_id == "retry_churn"]
        if churn:
            # If churn is detected, the denominator should be 2 (complete only),
            # not 3 (which would include the incomplete session)
            assert churn[0].evidence["total_sessions"] == 2

    def test_all_incomplete_returns_empty(self, output_dir: Path) -> None:
        """When all sessions are incomplete, anti-patterns returns empty."""
        incomplete = {
            "session_id": "s1",
            "input_tokens": 5000,
            "output_tokens": 20000,
            "git_commits": 0,
            "start_time": "2026-03-21T10:00:00Z",
        }
        _write_sessions(output_dir, [incomplete])

        findings = detect_anti_patterns(output_dir=output_dir)
        assert findings == []

        result = throughput_summary(output_dir=output_dir)
        assert result.total_sessions == 0
        assert result.total_tokens == 0

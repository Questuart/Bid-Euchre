"""Tests for the token economy usage data importer.

Validates:
- Idempotent import (re-run produces same count)
- Schema validation rejects malformed input
- Imported session count matches source count
- Facet data is merged when available
- Rollup aggregation is correct
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.token_economy import (
    ImportResult,
    SchemaValidationError,
    SessionRecord,
    import_usage_data,
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

"""Tests for the audit index (ops/index.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.index import (
    BuildResult,
    IndexStats,
    QueryResponse,
    build_index,
    format_query_json,
    format_query_text,
    format_stats_json,
    format_stats_text,
    get_stats,
    init_schema,
    query,
    query_recent,
)


@pytest.fixture()
def index_dir(tmp_path: Path) -> Path:
    """Provide a temporary index directory."""
    d = tmp_path / "audit_index"
    d.mkdir()
    return d


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Provide a temporary runtime directory with sample events."""
    rt = tmp_path / "runtime"
    rt.mkdir()

    # Create events directory with sample events
    events_dir = rt / "events"
    events_dir.mkdir()
    events = [
        {
            "timestamp": "2026-03-18T10:00:00+00:00",
            "event_type": "task_completed",
            "source": "test",
            "lane_id": "author-a",
            "payload": {"task": "implement feature X"},
        },
        {
            "timestamp": "2026-03-18T11:00:00+00:00",
            "event_type": "ci_failure",
            "source": "test",
            "lane_id": "ops",
            "payload": {"pr": 42, "reason": "lint failure"},
        },
        {
            "timestamp": "2026-03-18T12:00:00+00:00",
            "event_type": "review_outcome",
            "source": "test",
            "lane_id": "review",
            "payload": {"pr": 42, "status": "approved"},
        },
    ]
    lines = [json.dumps(e) for e in events]
    (events_dir / "events.jsonl").write_text("\n".join(lines) + "\n")

    return rt


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    """Provide a temporary plans directory with sample checkpoint."""
    pd = tmp_path / "plans"
    pd.mkdir()

    # Create a checkpoint file
    cp_dir = pd / "test_plan"
    cp_dir.mkdir()
    (cp_dir / "checkpoints.md").write_text(
        "# Checkpoints\n\n"
        "- [x] Step 1: Setup infrastructure\n"
        "- [ ] Step 2: Implement feature\n"
        "- [ ] Step 3: Write tests\n"
    )

    # Create a state.json
    state = {
        "rung": "R0",
        "status": "in_progress",
        "current_step": "generate_reports",
        "last_updated": "2026-03-18T10:00:00+00:00",
    }
    (cp_dir / "state.json").write_text(json.dumps(state))

    # Create an execution log
    log_entries = [
        {
            "timestamp": "2026-03-18T09:00:00+00:00",
            "step": "run_experiment",
            "status": "completed",
        },
        {
            "timestamp": "2026-03-18T09:30:00+00:00",
            "step": "generate_reports",
            "status": "started",
        },
    ]
    (cp_dir / "execution_log.jsonl").write_text(
        "\n".join(json.dumps(e) for e in log_entries) + "\n"
    )

    return pd


@pytest.fixture()
def runtime_with_reviews(runtime_dir: Path) -> Path:
    """Extend runtime_dir with review loop and plan review artifacts."""
    # Review loop sidecars
    rl_dir = runtime_dir / "review_loops" / "pr_906"
    rl_dir.mkdir(parents=True)
    (rl_dir / "state.json").write_text(
        json.dumps(
            {
                "pr_number": 906,
                "branch": "codex/steward-author-c",
                "state": "completed",
                "iteration_count": 1,
            }
        )
    )
    round_dir = rl_dir / "round_1"
    round_dir.mkdir()
    (round_dir / "prechecks.json").write_text(json.dumps([]))
    (round_dir / "codex_review.json").write_text(
        json.dumps({"findings": [], "status": "clean"})
    )

    # Plan review artifacts
    pr_dir = runtime_dir / "plan_reviews" / "plan_001"
    pr_dir.mkdir(parents=True)
    (pr_dir / "review.json").write_text(
        json.dumps(
            {
                "plan_path": "plans/sessions/test.md",
                "status": "approved",
                "timestamp": "2026-03-18T14:00:00+00:00",
            }
        )
    )

    # CI poll snapshots (in nested pr_N dirs)
    ci_dir = runtime_dir / "ci_polls" / "pr_906"
    ci_dir.mkdir(parents=True)
    (ci_dir / "status.json").write_text(
        json.dumps(
            {
                "pr_number": 906,
                "overall": "success",
                "checked_at": "2026-03-18T13:00:00+00:00",
            }
        )
    )

    return runtime_dir


class TestInitSchema:
    """Tests for schema initialization."""

    def test_creates_database(self, index_dir: Path) -> None:
        init_schema(index_dir)
        assert (index_dir / "audit.db").exists()

    def test_idempotent(self, index_dir: Path) -> None:
        init_schema(index_dir)
        init_schema(index_dir)
        assert (index_dir / "audit.db").exists()

    def test_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested"
        init_schema(nested)
        assert (nested / "audit.db").exists()


class TestBuildIndex:
    """Tests for build_index()."""

    def test_builds_from_events(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        result = build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        assert result.sources_indexed >= 1
        assert result.entries_indexed >= 3  # 3 events

    def test_builds_from_checkpoints(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        result = build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        # Should include checkpoint steps
        assert result.entries_indexed >= 3  # events + checkpoint steps

    def test_builds_from_state_json(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        result = build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        assert result.sources_indexed >= 1

    def test_builds_from_execution_log(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        result = build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        # 3 events + 3 checkpoint + 1 state + 2 exec log = 9
        assert result.entries_indexed >= 9

    def test_full_rebuild(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        # Build once
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        stats1 = get_stats(index_dir)

        # Rebuild
        build_index(
            index_dir,
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            full_rebuild=True,
        )
        stats2 = get_stats(index_dir)

        assert stats2.total_entries == stats1.total_entries

    def test_idempotent_rebuild(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        stats1 = get_stats(index_dir)

        # Build again (incremental)
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        stats2 = get_stats(index_dir)

        assert stats2.total_entries == stats1.total_entries

    def test_handles_missing_runtime_dir(self, index_dir: Path, tmp_path: Path) -> None:
        result = build_index(
            index_dir,
            runtime_dir=tmp_path / "nonexistent",
            plans_dir=tmp_path / "also_nonexistent",
        )
        assert result.errors == []
        assert result.sources_indexed == 0

    def test_handles_malformed_events(self, index_dir: Path, tmp_path: Path) -> None:
        rt = tmp_path / "runtime"
        events_dir = rt / "events"
        events_dir.mkdir(parents=True)
        (events_dir / "events.jsonl").write_text(
            '{"valid": "json", "event_type": "task_completed", "timestamp": "2026-01-01"}\n'
            "not valid json\n"
            '{"event_type": "ci_failure", "timestamp": "2026-01-02"}\n'
        )

        result = build_index(index_dir, runtime_dir=rt, plans_dir=tmp_path / "plans")
        # Should skip the malformed line but index the rest
        assert result.entries_indexed >= 2

    def test_handles_malformed_state_json(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        pd = tmp_path / "plans" / "test"
        pd.mkdir(parents=True)
        (pd / "state.json").write_text("not valid json")

        result = build_index(
            index_dir,
            runtime_dir=tmp_path / "runtime",
            plans_dir=tmp_path / "plans",
        )
        # Should handle gracefully
        assert isinstance(result, BuildResult)

    def test_indexes_review_loop_sidecars(
        self, index_dir: Path, runtime_with_reviews: Path, plans_dir: Path
    ) -> None:
        result = build_index(
            index_dir, runtime_dir=runtime_with_reviews, plans_dir=plans_dir
        )
        # Should index review loop state + round artifacts
        assert result.entries_indexed >= 9  # base entries + review loop entries

        # Verify review_outcome entries exist
        response = query(index_dir, "review loop")
        assert response.total_matches >= 1

    def test_indexes_plan_review_artifacts(
        self, index_dir: Path, runtime_with_reviews: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_with_reviews, plans_dir=plans_dir)
        response = query(index_dir, "plan review")
        assert response.total_matches >= 1
        # Verify it's a plan_review_outcome entry type
        plan_results = [
            r for r in response.results if r.entry_type == "plan_review_outcome"
        ]
        assert len(plan_results) >= 1

    def test_indexes_ci_poll_snapshots(
        self, index_dir: Path, runtime_with_reviews: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_with_reviews, plans_dir=plans_dir)
        response = query(index_dir, "906")
        assert response.total_matches >= 1

    def test_handles_empty_review_loops(self, index_dir: Path, tmp_path: Path) -> None:
        rt = tmp_path / "runtime"
        rl_dir = rt / "review_loops"
        rl_dir.mkdir(parents=True)
        # Empty review_loops dir
        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=tmp_path / "plans",
        )
        assert isinstance(result, BuildResult)

    def test_full_rebuild_cleans_wal_shm(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        """Verify full_rebuild removes WAL and SHM journal files."""
        # Build once to create the database
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        db_path = index_dir / "audit.db"
        assert db_path.exists()

        # Simulate leftover WAL/SHM files (SQLite journal artifacts)
        wal_path = index_dir / "audit.db-wal"
        shm_path = index_dir / "audit.db-shm"
        wal_path.write_bytes(b"stale WAL data")
        shm_path.write_bytes(b"stale SHM data")

        # Full rebuild should remove them
        build_index(
            index_dir,
            runtime_dir=runtime_dir,
            plans_dir=plans_dir,
            full_rebuild=True,
        )

        assert not wal_path.exists(), "WAL file should be cleaned up"
        assert not shm_path.exists(), "SHM file should be cleaned up"
        # DB should be recreated and functional
        assert db_path.exists()
        stats = get_stats(index_dir)
        assert stats.total_entries > 0

    def test_handles_malformed_review_loop_state(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        rt = tmp_path / "runtime"
        rl_dir = rt / "review_loops" / "pr_999"
        rl_dir.mkdir(parents=True)
        (rl_dir / "state.json").write_text("not valid json")

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=tmp_path / "plans",
        )
        # Should handle gracefully — malformed entries are skipped
        assert isinstance(result, BuildResult)


class TestQuery:
    """Tests for query()."""

    def test_query_absent_index(self, tmp_path: Path) -> None:
        response = query(tmp_path / "nonexistent", "test")
        assert response.index_absent
        assert response.results == []

    def test_query_events(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query(index_dir, "ci_failure")
        assert response.total_matches >= 1
        assert any("ci_failure" in r.content for r in response.results)

    def test_query_with_type_filter(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query(index_dir, "step", entry_type="checkpoint_step")
        assert all(r.entry_type == "checkpoint_step" for r in response.results)

    def test_query_returns_source_file(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query(index_dir, "task_completed")
        assert response.total_matches >= 1
        for r in response.results:
            assert r.source_file  # Must have source reference
            assert r.source_type  # Must have source type

    def test_query_limit(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query(index_dir, "step OR event OR rung", limit=2)
        assert len(response.results) <= 2

    def test_query_empty_results(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query(index_dir, "xyznonexistentterm123")
        assert response.total_matches == 0
        assert response.results == []


class TestQueryRecent:
    """Tests for query_recent()."""

    def test_recent_absent_index(self, tmp_path: Path) -> None:
        response = query_recent(tmp_path / "nonexistent")
        assert response.index_absent

    def test_recent_returns_ordered(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query_recent(index_dir, limit=10)
        assert len(response.results) > 0

        # Verify descending timestamp order
        timestamps = [r.timestamp for r in response.results if r.timestamp]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_recent_type_filter(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        response = query_recent(index_dir, entry_type="event", limit=10)
        assert all(r.entry_type == "event" for r in response.results)


class TestGetStats:
    """Tests for get_stats()."""

    def test_stats_absent_index(self, tmp_path: Path) -> None:
        stats = get_stats(tmp_path / "nonexistent")
        assert stats.total_sources == 0
        assert stats.total_entries == 0

    def test_stats_after_build(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)
        stats = get_stats(index_dir)
        assert stats.total_sources > 0
        assert stats.total_entries > 0
        assert stats.last_built is not None
        assert "event" in stats.source_counts


class TestFormatting:
    """Tests for formatting helpers."""

    def test_format_query_json(self) -> None:
        response = QueryResponse(query="test", results=[], total_matches=0)
        data = format_query_json(response)
        assert data["query"] == "test"
        assert data["total_matches"] == 0

    def test_format_query_text_absent(self) -> None:
        response = QueryResponse(query="test", results=[], index_absent=True)
        text = format_query_text(response)
        assert "not found" in text.lower()

    def test_format_query_text_stale(self) -> None:
        response = QueryResponse(query="test", results=[], index_stale=True)
        text = format_query_text(response)
        assert "stale" in text.lower()

    def test_format_stats_json(self) -> None:
        stats = IndexStats(total_sources=5, total_entries=100)
        data = format_stats_json(stats)
        assert data["total_sources"] == 5
        assert data["total_entries"] == 100

    def test_format_stats_text_empty(self) -> None:
        stats = IndexStats()
        text = format_stats_text(stats)
        assert "not built" in text.lower()

    def test_format_stats_text_populated(self) -> None:
        stats = IndexStats(
            total_sources=3,
            total_entries=50,
            last_built="2026-03-18T10:00:00",
            source_counts={"event": 2, "checkpoint": 1},
        )
        text = format_stats_text(stats)
        assert "50" in text
        assert "event" in text

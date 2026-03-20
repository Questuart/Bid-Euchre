"""Tests for the audit index (ops/index.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.index import (
    BuildResult,
    IndexStats,
    QueryResponse,
    _connect,
    _staleness_cache,
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


# ── Regression tests for #952, #953, #957 ──────────────────────


class TestRepoRootPathResolution:
    """Regression tests for #952: repo-root-aware path derivation."""

    def test_repo_root_ingests_data_runs_manifests(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """build_index(repo_root=...) ingests data/runs manifests without CWD."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        # Create data/runs manifest
        runs_dir = repo / "data" / "runs" / "run_001"
        runs_dir.mkdir(parents=True)
        (runs_dir / "evidence_manifest_R0.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {"name": "model.pkl", "type": "model"},
                        {"name": "metrics.json", "type": "metrics"},
                    ]
                }
            )
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=plans,
            repo_root=repo,
        )
        assert result.errors == []
        assert result.entries_indexed >= 2  # 2 manifest artifacts
        assert result.sources_indexed >= 1

        # Verify searchable
        resp = query(index_dir, "model")
        assert resp.total_matches >= 1

    def test_repo_root_ingests_report_metadata(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """build_index(repo_root=...) ingests docs/04_reports manifests."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        # Create docs/04_reports manifest
        reports_dir = repo / "docs" / "04_reports" / "R0"
        reports_dir.mkdir(parents=True)
        (reports_dir / "manifest_R0.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {"name": "01_results.md", "type": "report"},
                    ]
                }
            )
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=plans,
            repo_root=repo,
        )
        assert result.errors == []
        assert result.entries_indexed >= 1
        assert result.sources_indexed >= 1

    def test_repo_root_absent_dirs_no_errors(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """When data/runs and docs/04_reports don't exist, no errors."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=plans,
            repo_root=repo,
        )
        assert result.errors == []
        assert result.sources_indexed == 0

    def test_repo_root_inferred_from_runtime_dir(self, tmp_path: Path) -> None:
        """Regression: repo_root inferred from runtime_dir when .git exists."""
        repo = tmp_path / "inferred_repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()
        index_dir = rt / "audit_index"

        # Place a .git marker so the inference succeeds
        (repo / ".git").mkdir()

        # Create a manifest in data/runs under the inferred repo root
        runs_dir = repo / "data" / "runs" / "run_infer"
        runs_dir.mkdir(parents=True)
        (runs_dir / "evidence_manifest_R0.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {"name": "metrics.json", "type": "metrics"},
                    ]
                }
            )
        )

        # Create a report manifest in docs/04_reports under the inferred root
        reports_dir = repo / "docs" / "04_reports" / "R0"
        reports_dir.mkdir(parents=True)
        (reports_dir / "manifest_R0.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {"name": "01_results.md", "type": "report"},
                    ]
                }
            )
        )

        # Call WITHOUT explicit repo_root -- should infer from runtime_dir
        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=plans,
        )
        assert result.errors == []
        assert (
            result.sources_indexed >= 2
        ), f"Expected >=2 sources (manifest + report), got {result.sources_indexed}"
        assert result.entries_indexed >= 2


class TestFtsUpdateTrigger:
    """Regression tests for #953: FTS AFTER UPDATE trigger."""

    def test_fts_reflects_updated_content(self, index_dir: Path) -> None:
        """Direct UPDATE on entries.content is reflected in FTS queries."""
        init_schema(index_dir)
        conn = _connect(index_dir)
        try:
            # Insert a source and entry
            conn.execute(
                "INSERT INTO sources (source_type, file_path, indexed_at) "
                "VALUES ('test', '/tmp/test.json', '2026-01-01T00:00:00')"
            )
            source_id = conn.execute(
                "SELECT source_id FROM sources WHERE file_path = '/tmp/test.json'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO entries (source_id, entry_type, content) "
                "VALUES (?, 'test_entry', 'original keyword alpha')",
                (source_id,),
            )
            conn.commit()

            # Verify original content is searchable
            row = conn.execute(
                "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'alpha'"
            ).fetchone()
            assert row[0] == 1

            # Direct UPDATE — this previously broke FTS sync (#953)
            conn.execute(
                "UPDATE entries SET content = 'updated keyword bravo' "
                "WHERE source_id = ?",
                (source_id,),
            )
            conn.commit()

            # Old content should NOT match
            row = conn.execute(
                "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'alpha'"
            ).fetchone()
            assert row[0] == 0, "Stale FTS content found after UPDATE"

            # New content SHOULD match
            row = conn.execute(
                "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'bravo'"
            ).fetchone()
            assert row[0] == 1, "Updated FTS content not found"

        finally:
            conn.close()

    def test_insert_and_delete_triggers_still_work(self, index_dir: Path) -> None:
        """Ensure the existing INSERT and DELETE triggers are not broken."""
        init_schema(index_dir)
        conn = _connect(index_dir)
        try:
            conn.execute(
                "INSERT INTO sources (source_type, file_path, indexed_at) "
                "VALUES ('test', '/tmp/t2.json', '2026-01-01T00:00:00')"
            )
            source_id = conn.execute(
                "SELECT source_id FROM sources WHERE file_path = '/tmp/t2.json'"
            ).fetchone()[0]

            # INSERT trigger
            conn.execute(
                "INSERT INTO entries (source_id, entry_type, content) "
                "VALUES (?, 'test_entry', 'insert trigger test')",
                (source_id,),
            )
            conn.commit()
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'trigger'"
                ).fetchone()[0]
                == 1
            )

            # DELETE trigger
            conn.execute("DELETE FROM entries WHERE source_id = ?", (source_id,))
            conn.commit()
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM entries_fts WHERE entries_fts MATCH 'trigger'"
                ).fetchone()[0]
                == 0
            )
        finally:
            conn.close()


class TestSourcesIndexedAccuracy:
    """Regression tests for #957: accurate sources_indexed for compound ingestors."""

    def test_review_loop_sources_counted_accurately(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """sources_indexed reflects true count for review-loop compound ingestor."""
        rt = tmp_path / "runtime"

        # Create review loop with 1 state.json + 2 round artifacts = 3 sources
        rl_dir = rt / "review_loops" / "pr_100"
        rl_dir.mkdir(parents=True)
        (rl_dir / "state.json").write_text(
            json.dumps({"pr_number": 100, "state": "completed", "branch": "feat/x"})
        )
        round_dir = rl_dir / "round_1"
        round_dir.mkdir()
        (round_dir / "prechecks.json").write_text(json.dumps([]))
        (round_dir / "codex_review.json").write_text(
            json.dumps({"findings": [], "status": "clean"})
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=tmp_path / "empty_plans",
            repo_root=tmp_path,
        )
        # 3 review sources: state.json + prechecks.json + codex_review.json
        assert result.sources_indexed == 3
        assert result.entries_indexed == 3

    def test_plan_review_sources_counted_accurately(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """sources_indexed reflects true count for plan-review compound ingestor."""
        rt = tmp_path / "runtime"

        # Create 2 plan review files = 2 sources
        pr1 = rt / "plan_reviews" / "plan_001"
        pr1.mkdir(parents=True)
        (pr1 / "review.json").write_text(
            json.dumps({"plan_path": "plans/a.md", "status": "approved"})
        )
        pr2 = rt / "plan_reviews" / "plan_002"
        pr2.mkdir(parents=True)
        (pr2 / "review.json").write_text(
            json.dumps({"plan_path": "plans/b.md", "status": "rejected"})
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=tmp_path / "empty_plans",
            repo_root=tmp_path,
        )
        assert result.sources_indexed == 2
        assert result.entries_indexed == 2

    def test_report_metadata_sources_counted_accurately(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """sources_indexed reflects true count for report-metadata compound ingestor."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)

        # Create 2 report manifests with 3 total artifacts
        r0_dir = repo / "docs" / "04_reports" / "R0"
        r0_dir.mkdir(parents=True)
        (r0_dir / "manifest_R0.json").write_text(
            json.dumps({"artifacts": [{"name": "a.md", "type": "report"}]})
        )
        r1_dir = repo / "docs" / "04_reports" / "R1"
        r1_dir.mkdir(parents=True)
        (r1_dir / "manifest_R1.json").write_text(
            json.dumps(
                {
                    "artifacts": [
                        {"name": "b.md", "type": "report"},
                        {"name": "c.csv", "type": "data"},
                    ]
                }
            )
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=tmp_path / "empty_plans",
            repo_root=repo,
        )
        # 2 manifest files = 2 sources, 3 artifact entries
        assert result.sources_indexed == 2
        assert result.entries_indexed == 3

    def test_mixed_compound_ingestors(self, index_dir: Path, tmp_path: Path) -> None:
        """All three compound ingestors count sources accurately together."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        # 1 review-loop source (state.json only, no round artifacts)
        rl_dir = rt / "review_loops" / "pr_200"
        rl_dir.mkdir(parents=True)
        (rl_dir / "state.json").write_text(
            json.dumps({"pr_number": 200, "state": "completed", "branch": "feat/y"})
        )

        # 1 plan-review source
        pr_dir = rt / "plan_reviews" / "plan_003"
        pr_dir.mkdir(parents=True)
        (pr_dir / "review.json").write_text(
            json.dumps({"plan_path": "plans/c.md", "status": "approved"})
        )

        # 1 report metadata source (1 artifact)
        r0_dir = repo / "docs" / "04_reports" / "R0"
        r0_dir.mkdir(parents=True)
        (r0_dir / "manifest_R0.json").write_text(
            json.dumps({"artifacts": [{"name": "x.md", "type": "report"}]})
        )

        result = build_index(
            index_dir,
            runtime_dir=rt,
            plans_dir=plans,
            repo_root=repo,
        )
        # 1 review-loop + 1 plan-review + 1 report-metadata = 3 sources
        assert result.sources_indexed == 3
        # 1 entry + 1 entry + 1 entry = 3 entries
        assert result.entries_indexed == 3


# ── Regression tests for #956 ─────────────────────────────────────


class TestStalenessCache:
    """Regression tests for #956: TTL-cached staleness checks."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self) -> None:
        """Ensure each test starts with a clean cache."""
        _staleness_cache.invalidate_all()

    def test_staleness_detected_after_file_modification(
        self, index_dir: Path, runtime_dir: Path, plans_dir: Path
    ) -> None:
        """After modifying a source file, staleness should be detected."""
        import time as _time

        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        # Index should not be stale immediately after build
        stats = get_stats(index_dir)
        assert stats.stale_sources == 0

        # Modify a source file — ensure mtime advances
        events_file = runtime_dir / "events" / "events.jsonl"
        _time.sleep(0.05)  # ensure mtime resolution
        events_file.write_text(
            events_file.read_text() + '{"event_type":"new","timestamp":"2026-12-31"}\n'
        )

        # Cache should be invalidated for this query (build just ran, but
        # we need to force expiry to see the modification)
        _staleness_cache.invalidate(index_dir)

        stats = get_stats(index_dir)
        assert stats.stale_sources >= 1

    def test_staleness_cache_avoids_repeated_stat_calls(
        self,
        index_dir: Path,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Multiple queries within TTL should not re-scan source files."""
        import bid_euchre.ops.index as idx_mod

        # Set a long TTL so the cache definitely doesn't expire
        monkeypatch.setattr(idx_mod, "_STALENESS_TTL_SECONDS", 3600.0)

        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        # First query — populates cache
        resp1 = query(index_dir, "task_completed")
        assert resp1.total_matches >= 1

        # Patch _count_stale_sources to track calls
        call_count = 0
        original_fn = idx_mod._count_stale_sources

        def counting_wrapper(conn: object) -> int:
            nonlocal call_count
            call_count += 1
            return original_fn(conn)  # type: ignore[arg-type]

        monkeypatch.setattr(idx_mod, "_count_stale_sources", counting_wrapper)

        # Subsequent queries should hit cache — zero calls to _count_stale_sources
        query(index_dir, "ci_failure")
        query(index_dir, "review_outcome")
        query_recent(index_dir)
        get_stats(index_dir)

        assert call_count == 0, f"Expected 0 stale-source scans, got {call_count}"

    def test_staleness_cache_expires_after_ttl(
        self,
        index_dir: Path,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After TTL expires, the next query should re-scan."""
        import bid_euchre.ops.index as idx_mod

        # Set TTL to 0 so cache always expires
        monkeypatch.setattr(idx_mod, "_STALENESS_TTL_SECONDS", 0.0)

        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        # Track calls
        call_count = 0
        original_fn = idx_mod._count_stale_sources

        def counting_wrapper(conn: object) -> int:
            nonlocal call_count
            call_count += 1
            return original_fn(conn)  # type: ignore[arg-type]

        monkeypatch.setattr(idx_mod, "_count_stale_sources", counting_wrapper)

        # Each query should trigger a fresh scan
        query(index_dir, "task_completed")
        query(index_dir, "ci_failure")

        assert call_count == 2, f"Expected 2 scans with TTL=0, got {call_count}"

    def test_staleness_cache_invalidated_after_build(
        self,
        index_dir: Path,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """build_index() invalidates the cache so next query re-scans."""
        import bid_euchre.ops.index as idx_mod

        monkeypatch.setattr(idx_mod, "_STALENESS_TTL_SECONDS", 3600.0)

        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        # Prime the cache
        query(index_dir, "task_completed")

        # Track calls
        call_count = 0
        original_fn = idx_mod._count_stale_sources

        def counting_wrapper(conn: object) -> int:
            nonlocal call_count
            call_count += 1
            return original_fn(conn)  # type: ignore[arg-type]

        monkeypatch.setattr(idx_mod, "_count_stale_sources", counting_wrapper)

        # Rebuild — should invalidate cache
        build_index(index_dir, runtime_dir=runtime_dir, plans_dir=plans_dir)

        # Next query should re-scan despite long TTL
        query(index_dir, "task_completed")

        assert call_count >= 1, "Cache should have been invalidated after build"

    def test_staleness_cache_isolated_across_index_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two different index_dirs should not share cache entries."""
        import bid_euchre.ops.index as idx_mod

        monkeypatch.setattr(idx_mod, "_STALENESS_TTL_SECONDS", 3600.0)

        # Create two independent indexes
        idx1 = tmp_path / "idx1"
        idx1.mkdir()
        idx2 = tmp_path / "idx2"
        idx2.mkdir()

        rt1 = tmp_path / "rt1"
        rt1.mkdir()
        events_dir1 = rt1 / "events"
        events_dir1.mkdir()
        (events_dir1 / "events.jsonl").write_text(
            '{"event_type":"alpha","timestamp":"2026-01-01"}\n'
        )

        rt2 = tmp_path / "rt2"
        rt2.mkdir()
        events_dir2 = rt2 / "events"
        events_dir2.mkdir()
        (events_dir2 / "events.jsonl").write_text(
            '{"event_type":"bravo","timestamp":"2026-01-01"}\n'
        )

        plans = tmp_path / "plans"
        plans.mkdir()

        build_index(idx1, runtime_dir=rt1, plans_dir=plans, repo_root=tmp_path)
        build_index(idx2, runtime_dir=rt2, plans_dir=plans, repo_root=tmp_path)

        # Query each — results should be independent
        resp1 = query(idx1, "alpha")
        resp2 = query(idx2, "bravo")

        assert resp1.total_matches >= 1
        assert resp2.total_matches >= 1

        # Staleness for one should not affect the other
        _staleness_cache.invalidate(idx1)
        # idx2's cache should still be valid
        stats2 = get_stats(idx2)
        assert isinstance(stats2.stale_sources, int)


# ── PR comment ingestion tests ────────────────────────────────────


class TestPRCommentIngestion:
    """Tests for pr_comment JSONL sidecar ingestion."""

    def test_indexes_pr_comment_sidecars(self, index_dir: Path, tmp_path: Path) -> None:
        """build_index ingests pr_comments/*.jsonl sidecars."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        # Create pr_comments sidecar
        pr_comments_dir = rt / "pr_comments"
        pr_comments_dir.mkdir()
        comments = [
            {
                "comment_id": 100,
                "author_login": "octocat",
                "author_type": "human",
                "created_at": "2026-03-20T10:00:00Z",
                "body_excerpt": "LGTM",
                "pr_number": 42,
            },
            {
                "comment_id": 200,
                "author_login": "chatgpt-codex-connector[bot]",
                "author_type": "trusted_bot",
                "created_at": "2026-03-20T11:00:00Z",
                "body_excerpt": "Review findings: no issues",
                "pr_number": 42,
            },
        ]
        lines = [json.dumps(c) for c in comments]
        (pr_comments_dir / "pr_42.jsonl").write_text("\n".join(lines) + "\n")

        result = build_index(index_dir, runtime_dir=rt, plans_dir=plans, repo_root=repo)
        assert result.errors == []
        assert result.sources_indexed >= 1
        assert result.entries_indexed >= 2

        # Verify searchable
        resp = query(index_dir, "codex connector")
        assert resp.total_matches >= 1

    def test_pr_comment_entry_type_in_results(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """Ingested comments have entry_type 'pr_comment'."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        pr_comments_dir = rt / "pr_comments"
        pr_comments_dir.mkdir()
        comment = {
            "comment_id": 300,
            "author_login": "chatgpt-codex-connector[bot]",
            "author_type": "trusted_bot",
            "created_at": "2026-03-20T12:00:00Z",
            "body_excerpt": "Unique searchable token xyzabc",
            "pr_number": 99,
        }
        (pr_comments_dir / "pr_99.jsonl").write_text(json.dumps(comment) + "\n")

        build_index(index_dir, runtime_dir=rt, plans_dir=plans, repo_root=repo)

        resp = query(index_dir, "xyzabc")
        assert resp.total_matches >= 1
        assert any(r.entry_type == "pr_comment" for r in resp.results)

    def test_empty_pr_comments_dir(self, index_dir: Path, tmp_path: Path) -> None:
        """Empty pr_comments directory causes no errors."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        (rt / "pr_comments").mkdir()
        plans = repo / "plans"
        plans.mkdir()

        result = build_index(index_dir, runtime_dir=rt, plans_dir=plans, repo_root=repo)
        assert result.errors == []

    def test_no_pr_comments_dir(self, index_dir: Path, tmp_path: Path) -> None:
        """Missing pr_comments directory causes no errors."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        result = build_index(index_dir, runtime_dir=rt, plans_dir=plans, repo_root=repo)
        assert result.errors == []

    def test_malformed_jsonl_lines_skipped(
        self, index_dir: Path, tmp_path: Path
    ) -> None:
        """Malformed JSONL lines are skipped, valid lines are indexed."""
        repo = tmp_path / "repo"
        rt = repo / ".claude" / "runtime"
        rt.mkdir(parents=True)
        plans = repo / "plans"
        plans.mkdir()

        pr_comments_dir = rt / "pr_comments"
        pr_comments_dir.mkdir()
        content = (
            "not valid json\n"
            + json.dumps(
                {
                    "comment_id": 400,
                    "author_login": "octocat",
                    "author_type": "human",
                    "created_at": "2026-03-20T13:00:00Z",
                    "body_excerpt": "Valid comment",
                    "pr_number": 50,
                }
            )
            + "\n"
        )
        (pr_comments_dir / "pr_50.jsonl").write_text(content)

        result = build_index(index_dir, runtime_dir=rt, plans_dir=plans, repo_root=repo)
        assert result.errors == []
        assert result.entries_indexed >= 1

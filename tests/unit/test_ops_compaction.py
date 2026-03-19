"""Tests for session compaction (ops/compaction.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.compaction import (
    ArtifactRef,
    CompactionResult,
    SessionMetadata,
    compact_session,
    delete_archive,
    format_archives_json,
    format_archives_text,
    format_compaction_json,
    format_compaction_text,
    get_archive,
    get_archive_artifacts,
    get_archive_context,
    list_archives,
)


@pytest.fixture()
def archive_dir(tmp_path: Path) -> Path:
    """Provide a temporary archive directory."""
    d = tmp_path / "session_archive"
    d.mkdir()
    return d


@pytest.fixture()
def sample_artifacts() -> list[ArtifactRef]:
    """Provide sample artifact references."""
    return [
        ArtifactRef(
            path="src/bid_euchre/ops/index.py",
            action="created",
            timestamp="2026-03-18T10:00:00+00:00",
        ),
        ArtifactRef(
            path="tests/unit/test_ops_index.py",
            action="created",
            timestamp="2026-03-18T10:30:00+00:00",
        ),
        ArtifactRef(
            path="scripts/internal/ops.py",
            action="modified",
            timestamp="2026-03-18T11:00:00+00:00",
        ),
    ]


class TestCompactSession:
    """Tests for compact_session()."""

    def test_creates_archive(
        self, archive_dir: Path, sample_artifacts: list[ArtifactRef]
    ) -> None:
        result = compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="Full session context here...",
            artifacts=sample_artifacts,
            summary="Implemented PR-4",
            task_description="Local audit index",
            outcome="completed",
            pr_numbers=[927],
            archive_dir=archive_dir,
        )
        assert result.success
        assert result.artifacts_count == 3
        assert result.context_size_bytes > 0

    def test_creates_metadata_file(
        self, archive_dir: Path, sample_artifacts: list[ArtifactRef]
    ) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=sample_artifacts,
            archive_dir=archive_dir,
        )
        meta_file = archive_dir / "session-001" / "metadata.json"
        assert meta_file.exists()
        data = json.loads(meta_file.read_text())
        assert data["session_id"] == "session-001"
        assert data["lane_id"] == "author-a"

    def test_creates_artifacts_file(
        self, archive_dir: Path, sample_artifacts: list[ArtifactRef]
    ) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=sample_artifacts,
            archive_dir=archive_dir,
        )
        artifacts_file = archive_dir / "session-001" / "artifacts.json"
        assert artifacts_file.exists()
        data = json.loads(artifacts_file.read_text())
        assert len(data) == 3

    def test_preserves_raw_context(self, archive_dir: Path) -> None:
        context = "This is the full session context.\nWith multiple lines.\n"
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text=context,
            artifacts=[],
            archive_dir=archive_dir,
        )
        ctx_file = archive_dir / "session-001" / "context_snapshot.txt"
        assert ctx_file.exists()
        assert ctx_file.read_text() == context

    def test_rejects_duplicate_archive(
        self, archive_dir: Path, sample_artifacts: list[ArtifactRef]
    ) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="first",
            artifacts=sample_artifacts,
            archive_dir=archive_dir,
        )
        result = compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="second attempt",
            artifacts=[],
            archive_dir=archive_dir,
        )
        assert not result.success
        assert "already exists" in result.error

    def test_empty_artifacts(self, archive_dir: Path) -> None:
        result = compact_session(
            session_id="session-empty",
            lane_id="ops",
            context_text="monitoring session",
            artifacts=[],
            archive_dir=archive_dir,
        )
        assert result.success
        assert result.artifacts_count == 0

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "deep" / "nested" / "archive"
        result = compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=[],
            archive_dir=nested,
        )
        assert result.success


class TestRetrieval:
    """Tests for list_archives, get_archive, get_archive_artifacts, get_archive_context."""

    def test_list_empty(self, archive_dir: Path) -> None:
        archives = list_archives(archive_dir)
        assert archives == []

    def test_list_nonexistent_dir(self, tmp_path: Path) -> None:
        archives = list_archives(tmp_path / "nonexistent")
        assert archives == []

    def test_list_archives(self, archive_dir: Path) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="first",
            artifacts=[],
            archive_dir=archive_dir,
        )
        compact_session(
            session_id="session-002",
            lane_id="author-b",
            context_text="second",
            artifacts=[],
            archive_dir=archive_dir,
        )
        archives = list_archives(archive_dir)
        assert len(archives) == 2

    def test_list_skips_malformed(self, archive_dir: Path) -> None:
        # Create a malformed archive
        bad_dir = archive_dir / "bad-session"
        bad_dir.mkdir()
        (bad_dir / "metadata.json").write_text("not valid json")

        # Create a good archive
        compact_session(
            session_id="good-session",
            lane_id="author-a",
            context_text="good",
            artifacts=[],
            archive_dir=archive_dir,
        )

        archives = list_archives(archive_dir)
        assert len(archives) == 1
        assert archives[0].session_id == "good-session"

    def test_get_archive(self, archive_dir: Path) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=[],
            summary="Test session",
            archive_dir=archive_dir,
        )
        archive = get_archive("session-001", archive_dir)
        assert archive is not None
        assert archive.session_id == "session-001"
        assert archive.summary == "Test session"

    def test_get_archive_nonexistent(self, archive_dir: Path) -> None:
        assert get_archive("nonexistent", archive_dir) is None

    def test_get_artifacts(
        self, archive_dir: Path, sample_artifacts: list[ArtifactRef]
    ) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=sample_artifacts,
            archive_dir=archive_dir,
        )
        artifacts = get_archive_artifacts("session-001", archive_dir)
        assert len(artifacts) == 3
        assert artifacts[0].path == "src/bid_euchre/ops/index.py"

    def test_get_artifacts_nonexistent(self, archive_dir: Path) -> None:
        artifacts = get_archive_artifacts("nonexistent", archive_dir)
        assert artifacts == []

    def test_get_context(self, archive_dir: Path) -> None:
        context = "Full session context preserved here."
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text=context,
            artifacts=[],
            archive_dir=archive_dir,
        )
        retrieved = get_archive_context("session-001", archive_dir)
        assert retrieved == context

    def test_get_context_nonexistent(self, archive_dir: Path) -> None:
        assert get_archive_context("nonexistent", archive_dir) is None


class TestDeleteArchive:
    """Tests for delete_archive()."""

    def test_delete_existing(self, archive_dir: Path) -> None:
        compact_session(
            session_id="session-001",
            lane_id="author-a",
            context_text="context",
            artifacts=[],
            archive_dir=archive_dir,
        )
        assert delete_archive("session-001", archive_dir)
        assert not (archive_dir / "session-001").exists()

    def test_delete_nonexistent(self, archive_dir: Path) -> None:
        assert not delete_archive("nonexistent", archive_dir)


class TestFormatting:
    """Tests for formatting helpers."""

    def test_format_archives_json(self) -> None:
        archives = [
            SessionMetadata(
                session_id="s1",
                lane_id="author-a",
                start_time="2026-03-18T10:00:00",
            )
        ]
        data = format_archives_json(archives)
        assert len(data) == 1
        assert data[0]["session_id"] == "s1"

    def test_format_archives_text_empty(self) -> None:
        text = format_archives_text([])
        assert "no archived" in text.lower()

    def test_format_archives_text(self) -> None:
        archives = [
            SessionMetadata(
                session_id="s1",
                lane_id="author-a",
                start_time="2026-03-18T10:00:00",
                summary="Test session",
                outcome="completed",
                context_size_bytes=1024,
            )
        ]
        text = format_archives_text(archives)
        assert "s1" in text
        assert "author-a" in text
        assert "completed" in text

    def test_format_compaction_json_success(self) -> None:
        result = CompactionResult(
            session_id="s1",
            archive_path="/tmp/archive/s1",
            artifacts_count=5,
            context_size_bytes=2048,
            success=True,
        )
        data = format_compaction_json(result)
        assert data["success"]
        assert data["artifacts_count"] == 5

    def test_format_compaction_text_success(self) -> None:
        result = CompactionResult(
            session_id="s1",
            archive_path="/tmp/archive/s1",
            artifacts_count=5,
            context_size_bytes=2048,
            success=True,
        )
        text = format_compaction_text(result)
        assert "successfully" in text
        assert "s1" in text

    def test_format_compaction_text_failure(self) -> None:
        result = CompactionResult(
            session_id="s1",
            archive_path="/tmp/archive/s1",
            artifacts_count=0,
            context_size_bytes=0,
            success=False,
            error="already exists",
        )
        text = format_compaction_text(result)
        assert "failed" in text.lower()
        assert "already exists" in text

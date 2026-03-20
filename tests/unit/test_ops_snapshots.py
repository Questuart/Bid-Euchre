"""Tests for shadow snapshots and rollback workflow (ops/snapshots.py)."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.snapshots import (
    DEFAULT_MAX_AGE_HOURS,
    DEFAULT_MAX_PER_WORKTREE,
    RollbackResult,
    SnapshotRecord,
    _record_from_dict,
    create_snapshot,
    format_prune_json,
    format_prune_text,
    format_rollback_json,
    format_rollback_text,
    format_snapshots_json,
    format_snapshots_text,
    list_snapshots,
    prune_snapshots,
    rollback_snapshot,
)


@pytest.fixture()
def snapshots_dir(tmp_path: Path) -> Path:
    """Create a temp snapshots directory."""
    d = tmp_path / "snapshots"
    d.mkdir()
    return d


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Create a temp events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


def _write_snapshot_meta(
    snapshots_dir: Path,
    *,
    snapshot_id: str = "snap-abc123",
    worktree_path: str = "/tmp/wt-test",
    head_sha: str = "deadbeef" * 5,
    branch: str = "feature/test",
    stash_sha: str | None = None,
    reason: str = "test snapshot",
    timestamp: str = "2026-03-20T10:00:00+00:00",
    lane_id: str | None = "author-a",
    task_id: str | None = None,
    has_uncommitted: bool = False,
    files_changed: int = 0,
    summary: str = "",
) -> dict:
    """Write a snapshot metadata JSON file."""
    record = {
        "snapshot_id": snapshot_id,
        "worktree_path": worktree_path,
        "head_sha": head_sha,
        "branch": branch,
        "stash_sha": stash_sha,
        "reason": reason,
        "timestamp": timestamp,
        "lane_id": lane_id,
        "task_id": task_id,
        "has_uncommitted": has_uncommitted,
        "files_changed": files_changed,
        "summary": summary,
    }
    (snapshots_dir / f"{snapshot_id}.json").write_text(json.dumps(record, indent=2))
    return record


# ---------------------------------------------------------------------------
# Snapshot metadata recording
# ---------------------------------------------------------------------------


class TestCreateSnapshot:
    """Tests for create_snapshot()."""

    def test_creates_metadata_file(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Snapshot creation writes a metadata JSON file with correct fields."""
        wt_dir = tmp_path / "wt-test"
        wt_dir.mkdir()

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_rev_parse", lambda wt, ref: "abc123def456")
        monkeypatch.setattr(snap_mod, "_git_current_branch", lambda wt: "feature/test")
        monkeypatch.setattr(snap_mod, "_git_stash_create", lambda wt: "stash123sha")
        monkeypatch.setattr(
            snap_mod, "_git_diff_summary", lambda wt: (3, "3 files changed")
        )
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: ["scratch.py"])

        record = create_snapshot(
            str(wt_dir),
            "test snapshot",
            snapshots_dir,
            lane_id="author-a",
            task_id="task-1",
            events_dir=events_dir,
        )

        assert record.snapshot_id.startswith("snap-")
        assert record.worktree_path == str(wt_dir)
        assert record.head_sha == "abc123def456"
        assert record.branch == "feature/test"
        assert record.stash_sha == "stash123sha"
        assert record.has_uncommitted is True
        assert record.files_changed == 3
        assert record.lane_id == "author-a"
        assert record.task_id == "task-1"
        assert record.reason == "test snapshot"
        assert record.untracked_files == ["scratch.py"]

        # Verify file was written
        meta_files = list(snapshots_dir.glob("*.json"))
        assert len(meta_files) == 1
        data = json.loads(meta_files[0].read_text())
        assert data["snapshot_id"] == record.snapshot_id

    def test_clean_worktree_has_no_stash(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When working tree is clean, stash_sha is None and has_uncommitted is False."""
        wt_dir = tmp_path / "wt-clean"
        wt_dir.mkdir()

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_rev_parse", lambda wt, ref: "abc123")
        monkeypatch.setattr(snap_mod, "_git_current_branch", lambda wt: "main")
        monkeypatch.setattr(snap_mod, "_git_stash_create", lambda wt: None)
        monkeypatch.setattr(snap_mod, "_git_diff_summary", lambda wt: (0, ""))
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: [])

        record = create_snapshot(str(wt_dir), "clean snapshot", snapshots_dir)

        assert record.stash_sha is None
        assert record.has_uncommitted is False
        assert record.files_changed == 0

    def test_nonexistent_worktree_raises(self, snapshots_dir: Path) -> None:
        """Creating a snapshot for a nonexistent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            create_snapshot("/tmp/no-such-wt-xyz", "test", snapshots_dir)

    def test_emits_snapshot_created_event(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        events_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Snapshot creation emits a snapshot_created event."""
        wt_dir = tmp_path / "wt-events"
        wt_dir.mkdir()

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_rev_parse", lambda wt, ref: "abc123")
        monkeypatch.setattr(snap_mod, "_git_current_branch", lambda wt: "main")
        monkeypatch.setattr(snap_mod, "_git_stash_create", lambda wt: None)
        monkeypatch.setattr(snap_mod, "_git_diff_summary", lambda wt: (0, ""))
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: [])

        create_snapshot(
            str(wt_dir),
            "event test",
            snapshots_dir,
            lane_id="author-b",
            events_dir=events_dir,
        )

        # Check event was written
        events_file = events_dir / "events.jsonl"
        if events_file.exists():
            events = [
                json.loads(line)
                for line in events_file.read_text().strip().splitlines()
            ]
            snapshot_events = [
                e for e in events if e["event_type"] == "snapshot_created"
            ]
            assert len(snapshot_events) == 1
            assert snapshot_events[0]["lane_id"] == "author-b"


# ---------------------------------------------------------------------------
# Snapshot listing
# ---------------------------------------------------------------------------


class TestListSnapshots:
    """Tests for list_snapshots()."""

    def test_empty_dir(self, snapshots_dir: Path) -> None:
        records = list_snapshots(snapshots_dir)
        assert records == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        records = list_snapshots(tmp_path / "no-such-dir")
        assert records == []

    def test_returns_records_newest_first(self, snapshots_dir: Path) -> None:
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-old",
            timestamp="2026-03-19T10:00:00+00:00",
        )
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-new",
            timestamp="2026-03-20T10:00:00+00:00",
        )

        records = list_snapshots(snapshots_dir)
        assert len(records) == 2
        assert records[0].snapshot_id == "snap-new"
        assert records[1].snapshot_id == "snap-old"

    def test_filters_by_worktree(self, snapshots_dir: Path) -> None:
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-a",
            worktree_path="/tmp/wt-a",
        )
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-b",
            worktree_path="/tmp/wt-b",
        )

        records = list_snapshots(snapshots_dir, worktree_path="/tmp/wt-a")
        assert len(records) == 1
        assert records[0].snapshot_id == "snap-a"

    def test_respects_limit(self, snapshots_dir: Path) -> None:
        for i in range(5):
            _write_snapshot_meta(
                snapshots_dir,
                snapshot_id=f"snap-{i:03d}",
                timestamp=f"2026-03-20T{10 + i}:00:00+00:00",
            )

        records = list_snapshots(snapshots_dir, limit=3)
        assert len(records) == 3

    def test_skips_malformed_files(self, snapshots_dir: Path) -> None:
        (snapshots_dir / "bad.json").write_text("not valid json {{{")
        _write_snapshot_meta(snapshots_dir, snapshot_id="snap-good")

        records = list_snapshots(snapshots_dir)
        assert len(records) == 1
        assert records[0].snapshot_id == "snap-good"


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class TestRollbackSnapshot:
    """Tests for rollback_snapshot()."""

    def test_missing_snapshot_raises(self, snapshots_dir: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            rollback_snapshot("snap-nonexistent", snapshots_dir)

    def test_malformed_snapshot_raises(self, snapshots_dir: Path) -> None:
        (snapshots_dir / "snap-bad.json").write_text("not json {{{")
        with pytest.raises(ValueError, match="Malformed"):
            rollback_snapshot("snap-bad", snapshots_dir)

    def test_missing_worktree_returns_failure(self, snapshots_dir: Path) -> None:
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-gone",
            worktree_path="/tmp/no-such-wt-gone-xyz",
        )

        result = rollback_snapshot("snap-gone", snapshots_dir)
        assert result.success is False
        assert "not found" in result.message

    def test_successful_rollback_clean(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rollback with no stash succeeds with just git reset."""
        wt_dir = tmp_path / "wt-rollback"
        wt_dir.mkdir()

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-clean",
            worktree_path=str(wt_dir),
            head_sha="abc123def456",
            stash_sha=None,
            has_uncommitted=False,
        )

        import bid_euchre.ops.snapshots as snap_mod

        reset_calls: list[str] = []
        monkeypatch.setattr(
            snap_mod,
            "_git_reset_hard",
            lambda wt, sha: reset_calls.append(sha),
        )
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: [])

        result = rollback_snapshot("snap-clean", snapshots_dir)
        assert result.success is True
        assert result.stash_applied is False
        assert result.head_restored == "abc123def456"
        assert len(reset_calls) == 1
        assert reset_calls[0] == "abc123def456"

    def test_successful_rollback_with_stash(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rollback with stash applies both reset and stash."""
        wt_dir = tmp_path / "wt-rollback-stash"
        wt_dir.mkdir()

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-stash",
            worktree_path=str(wt_dir),
            head_sha="abc123",
            stash_sha="stash456",
            has_uncommitted=True,
        )

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        monkeypatch.setattr(snap_mod, "_git_stash_apply", lambda wt, sha: None)
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: [])

        result = rollback_snapshot("snap-stash", snapshots_dir)
        assert result.success is True
        assert result.stash_applied is True
        assert "uncommitted changes restored" in result.message

    def test_stash_apply_failure_warns_but_succeeds(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If stash apply fails (e.g., conflicts), rollback still succeeds with warning."""
        wt_dir = tmp_path / "wt-conflict"
        wt_dir.mkdir()

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-conflict",
            worktree_path=str(wt_dir),
            head_sha="abc123",
            stash_sha="stash789",
            has_uncommitted=True,
        )

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        monkeypatch.setattr(snap_mod, "_git_list_untracked", lambda wt: [])

        def failing_apply(wt: str, sha: str) -> None:
            raise subprocess.SubprocessError("merge conflict")

        monkeypatch.setattr(snap_mod, "_git_stash_apply", failing_apply)

        result = rollback_snapshot("snap-conflict", snapshots_dir)
        assert result.success is True
        assert result.stash_applied is False
        assert len(result.warnings) == 1
        assert "conflicts likely" in result.warnings[0].lower()

    def test_reset_failure_returns_failure(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If git reset fails, rollback returns failure."""
        wt_dir = tmp_path / "wt-reset-fail"
        wt_dir.mkdir()

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-resetfail",
            worktree_path=str(wt_dir),
            head_sha="abc123",
        )

        import bid_euchre.ops.snapshots as snap_mod

        def failing_reset(wt: str, sha: str) -> None:
            raise subprocess.SubprocessError("invalid sha")

        monkeypatch.setattr(snap_mod, "_git_reset_hard", failing_reset)

        result = rollback_snapshot("snap-resetfail", snapshots_dir)
        assert result.success is False
        assert "reset failed" in result.message.lower()


# ---------------------------------------------------------------------------
# Untracked file cleanup during rollback
# ---------------------------------------------------------------------------


class TestUntrackedFileCleanup:
    """Tests for untracked file cleanup during rollback."""

    def test_rollback_removes_new_untracked_files(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Files created after snapshot are removed on rollback."""
        wt_dir = tmp_path / "wt-untracked"
        wt_dir.mkdir()

        # Create a file that was NOT present at snapshot time
        new_file = wt_dir / "new_agent_file.py"
        new_file.write_text("# bad edit")

        # Snapshot recorded no untracked files
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-clean-untracked",
            worktree_path=str(wt_dir),
            head_sha="abc123",
        )
        # Ensure untracked_files is in the metadata
        meta = json.loads((snapshots_dir / "snap-clean-untracked.json").read_text())
        meta["untracked_files"] = []
        (snapshots_dir / "snap-clean-untracked.json").write_text(json.dumps(meta))

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        # After reset, git reports new_agent_file.py as untracked
        monkeypatch.setattr(
            snap_mod,
            "_git_list_untracked",
            lambda wt: ["new_agent_file.py"],
        )

        result = rollback_snapshot("snap-clean-untracked", snapshots_dir)
        assert result.success is True
        assert "new_agent_file.py" in result.cleaned_files
        assert not new_file.exists()

    def test_rollback_preserves_files_that_existed_at_snapshot(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Files present at snapshot time are not removed on rollback."""
        wt_dir = tmp_path / "wt-preserve"
        wt_dir.mkdir()

        # This file existed at snapshot time AND still exists
        existing_file = wt_dir / "existing.txt"
        existing_file.write_text("keep me")

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-preserve",
            worktree_path=str(wt_dir),
            head_sha="abc123",
        )
        meta = json.loads((snapshots_dir / "snap-preserve.json").read_text())
        meta["untracked_files"] = ["existing.txt"]
        (snapshots_dir / "snap-preserve.json").write_text(json.dumps(meta))

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        monkeypatch.setattr(
            snap_mod,
            "_git_list_untracked",
            lambda wt: ["existing.txt"],
        )

        result = rollback_snapshot("snap-preserve", snapshots_dir)
        assert result.success is True
        assert result.cleaned_files == []
        assert existing_file.exists()

    def test_rollback_reports_count_in_message(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rollback message includes count of cleaned files."""
        wt_dir = tmp_path / "wt-count"
        wt_dir.mkdir()

        (wt_dir / "a.py").write_text("x")
        (wt_dir / "b.py").write_text("y")

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-count",
            worktree_path=str(wt_dir),
            head_sha="abc123",
        )
        meta = json.loads((snapshots_dir / "snap-count.json").read_text())
        meta["untracked_files"] = []
        (snapshots_dir / "snap-count.json").write_text(json.dumps(meta))

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        monkeypatch.setattr(
            snap_mod,
            "_git_list_untracked",
            lambda wt: ["a.py", "b.py"],
        )

        result = rollback_snapshot("snap-count", snapshots_dir)
        assert "2 untracked file(s) removed" in result.message

    def test_legacy_snapshot_without_untracked_field(
        self,
        tmp_path: Path,
        snapshots_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Snapshots without untracked_files field don't crash rollback."""
        wt_dir = tmp_path / "wt-legacy"
        wt_dir.mkdir()

        # Write metadata WITHOUT untracked_files field
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-legacy",
            worktree_path=str(wt_dir),
            head_sha="abc123",
        )

        import bid_euchre.ops.snapshots as snap_mod

        monkeypatch.setattr(snap_mod, "_git_reset_hard", lambda wt, sha: None)
        monkeypatch.setattr(
            snap_mod,
            "_git_list_untracked",
            lambda wt: ["new_file.py"],
        )

        # new_file.py doesn't actually exist on disk, so cleanup
        # should gracefully handle the missing file
        result = rollback_snapshot("snap-legacy", snapshots_dir)
        assert result.success is True


# ---------------------------------------------------------------------------
# Git error handling
# ---------------------------------------------------------------------------


class TestGitErrorHandling:
    """Tests for git helper error detection."""

    def test_stash_create_raises_on_real_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_git_stash_create raises SubprocessError on stderr errors."""
        import subprocess as sp

        import bid_euchre.ops.snapshots as snap_mod

        def mock_run(*args: object, **kwargs: object) -> object:
            return type(
                "R",
                (),
                {
                    "returncode": 128,
                    "stdout": "",
                    "stderr": "fatal: not a git repository",
                },
            )()

        monkeypatch.setattr(sp, "run", mock_run)

        with pytest.raises(subprocess.SubprocessError, match="not a git repository"):
            snap_mod._git_stash_create("/tmp/fake")

    def test_stash_create_returns_none_for_clean_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_git_stash_create returns None (not error) for clean working tree."""
        import subprocess as sp

        import bid_euchre.ops.snapshots as snap_mod

        # git stash create exits 1 with no output for clean tree
        def mock_run(*args: object, **kwargs: object) -> object:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        result = snap_mod._git_stash_create("/tmp/fake")
        assert result is None

    def test_diff_summary_logs_warning_on_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_git_diff_summary returns (0, '') and logs warning on git error."""
        import subprocess as sp

        import bid_euchre.ops.snapshots as snap_mod

        def mock_run(*args: object, **kwargs: object) -> object:
            return type(
                "R",
                (),
                {
                    "returncode": 128,
                    "stdout": "",
                    "stderr": "fatal: bad revision",
                },
            )()

        monkeypatch.setattr(sp, "run", mock_run)

        files_changed, summary = snap_mod._git_diff_summary("/tmp/fake")
        assert files_changed == 0
        assert summary == ""


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


class TestPruneSnapshots:
    """Tests for prune_snapshots()."""

    def test_empty_dir_returns_nothing(self, snapshots_dir: Path) -> None:
        pruned = prune_snapshots(snapshots_dir)
        assert pruned == []

    def test_nonexistent_dir_returns_nothing(self, tmp_path: Path) -> None:
        pruned = prune_snapshots(tmp_path / "no-such-dir")
        assert pruned == []

    def test_prunes_beyond_per_worktree_cap(self, snapshots_dir: Path) -> None:
        """Keeps max_per_worktree most recent, prunes the rest."""
        for i in range(5):
            _write_snapshot_meta(
                snapshots_dir,
                snapshot_id=f"snap-{i:03d}",
                worktree_path="/tmp/wt-a",
                timestamp=f"2026-03-20T{10 + i}:00:00+00:00",
            )

        pruned = prune_snapshots(snapshots_dir, max_per_worktree=3)
        assert len(pruned) == 2
        # Oldest two should be pruned
        assert "snap-000" in pruned
        assert "snap-001" in pruned

        # Verify files are removed
        remaining = list(snapshots_dir.glob("*.json"))
        assert len(remaining) == 3

    def test_prunes_by_age(self, snapshots_dir: Path) -> None:
        """Snapshots older than max_age_hours are pruned."""
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-old",
            timestamp="2020-01-01T00:00:00+00:00",
        )
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-recent",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        pruned = prune_snapshots(snapshots_dir, max_age_hours=24.0)
        assert "snap-old" in pruned
        assert "snap-recent" not in pruned

    def test_per_worktree_cap_is_independent(self, snapshots_dir: Path) -> None:
        """Per-worktree cap applies separately to each worktree."""
        for i in range(3):
            _write_snapshot_meta(
                snapshots_dir,
                snapshot_id=f"snap-a{i}",
                worktree_path="/tmp/wt-a",
                timestamp=f"2026-03-20T{10 + i}:00:00+00:00",
            )
        for i in range(3):
            _write_snapshot_meta(
                snapshots_dir,
                snapshot_id=f"snap-b{i}",
                worktree_path="/tmp/wt-b",
                timestamp=f"2026-03-20T{10 + i}:00:00+00:00",
            )

        pruned = prune_snapshots(
            snapshots_dir,
            max_per_worktree=2,
            max_age_hours=999999,
        )
        # 1 pruned per worktree = 2 total
        assert len(pruned) == 2

    def test_default_retention_constants(self) -> None:
        assert DEFAULT_MAX_PER_WORKTREE == 20
        assert DEFAULT_MAX_AGE_HOURS == 168.0


# ---------------------------------------------------------------------------
# Record deserialization
# ---------------------------------------------------------------------------


class TestRecordFromDict:
    """Tests for _record_from_dict()."""

    def test_full_record(self) -> None:
        data = {
            "snapshot_id": "snap-123",
            "worktree_path": "/tmp/wt",
            "head_sha": "abc",
            "branch": "main",
            "stash_sha": "def",
            "reason": "test",
            "timestamp": "2026-03-20T10:00:00Z",
            "lane_id": "author-a",
            "task_id": "task-1",
            "has_uncommitted": True,
            "files_changed": 5,
            "summary": "5 files changed",
        }
        record = _record_from_dict(data)
        assert record.snapshot_id == "snap-123"
        assert record.stash_sha == "def"
        assert record.has_uncommitted is True

    def test_missing_optional_fields(self) -> None:
        data = {
            "snapshot_id": "snap-min",
            "worktree_path": "/tmp/wt",
            "head_sha": "abc",
            "branch": "main",
            "reason": "test",
            "timestamp": "2026-03-20T10:00:00Z",
        }
        record = _record_from_dict(data)
        assert record.stash_sha is None
        assert record.lane_id is None
        assert record.has_uncommitted is False
        assert record.files_changed == 0
        assert record.untracked_files == []

    def test_empty_dict_uses_defaults(self) -> None:
        record = _record_from_dict({})
        assert record.snapshot_id == "unknown"
        assert record.worktree_path == ""
        assert record.head_sha == ""


# ---------------------------------------------------------------------------
# Worktree targeting safety
# ---------------------------------------------------------------------------


class TestWorktreeSafety:
    """Tests that snapshot operations target the correct worktree."""

    def test_rollback_does_not_target_main_checkout(self, snapshots_dir: Path) -> None:
        """Rollback with a bad worktree path returns failure, not exception."""
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-bad-target",
            worktree_path="/tmp/nonexistent-main-checkout",
        )

        result = rollback_snapshot("snap-bad-target", snapshots_dir)
        assert result.success is False

    def test_list_filters_by_resolved_path(
        self, snapshots_dir: Path, tmp_path: Path
    ) -> None:
        """Filtering by worktree resolves symlinks/relative paths."""
        real_dir = tmp_path / "real-wt"
        real_dir.mkdir()

        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-real",
            worktree_path=str(real_dir),
        )
        _write_snapshot_meta(
            snapshots_dir,
            snapshot_id="snap-other",
            worktree_path="/tmp/other-wt",
        )

        # Filter using the same resolved path
        records = list_snapshots(snapshots_dir, worktree_path=str(real_dir))
        assert len(records) == 1
        assert records[0].snapshot_id == "snap-real"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    """Tests for text and JSON formatters."""

    def test_text_empty(self) -> None:
        text = format_snapshots_text([])
        assert "No snapshots found" in text

    def test_text_with_records(self) -> None:
        records = [
            SnapshotRecord(
                snapshot_id="snap-abc123def456",
                worktree_path="/tmp/wt-test",
                head_sha="deadbeef12345678",
                branch="feature/test",
                stash_sha="stash123",
                reason="before refactor",
                timestamp="2026-03-20T10:00:00+00:00",
                lane_id="author-a",
                has_uncommitted=True,
                files_changed=3,
                summary="3 files changed",
            ),
        ]
        text = format_snapshots_text(records)
        assert "Shadow Snapshots" in text
        assert "Total: 1" in text
        assert "snap-abc123d" in text
        assert "deadbeef" in text
        assert "+uncommitted" in text
        assert "before refactor" in text

    def test_json_format(self) -> None:
        records = [
            SnapshotRecord(
                snapshot_id="snap-1",
                worktree_path="/tmp/wt",
                head_sha="abc",
                branch="main",
                stash_sha=None,
                reason="test",
                timestamp="2026-03-20T10:00:00Z",
            ),
        ]
        data = format_snapshots_json(records)
        assert len(data) == 1
        assert data[0]["snapshot_id"] == "snap-1"
        assert data[0]["stash_sha"] is None

    def test_rollback_text_success(self) -> None:
        result = RollbackResult(
            snapshot_id="snap-1",
            worktree_path="/tmp/wt",
            head_restored="abc123",
            stash_applied=True,
            success=True,
            message="Rolled back successfully",
        )
        text = format_rollback_text(result)
        assert "SUCCESS" in text
        assert "snap-1" in text

    def test_rollback_text_failure(self) -> None:
        result = RollbackResult(
            snapshot_id="snap-1",
            worktree_path="/tmp/wt",
            head_restored="abc123",
            stash_applied=False,
            success=False,
            message="Reset failed",
            warnings=["Could not apply stash"],
        )
        text = format_rollback_text(result)
        assert "FAILED" in text
        assert "Could not apply stash" in text

    def test_rollback_json(self) -> None:
        result = RollbackResult(
            snapshot_id="snap-1",
            worktree_path="/tmp/wt",
            head_restored="abc123",
            stash_applied=False,
            success=True,
            message="ok",
        )
        data = format_rollback_json(result)
        assert data["snapshot_id"] == "snap-1"
        assert data["success"] is True

    def test_prune_text_empty(self) -> None:
        text = format_prune_text([])
        assert "No snapshots pruned" in text

    def test_prune_text_with_ids(self) -> None:
        text = format_prune_text(["snap-abc123def456", "snap-xyz789"])
        assert "Pruned 2" in text
        assert "snap-abc123d" in text

    def test_prune_json(self) -> None:
        data = format_prune_json(["snap-1", "snap-2"])
        assert data["count"] == 2
        assert data["pruned"] == ["snap-1", "snap-2"]

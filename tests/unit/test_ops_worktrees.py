"""Tests for worktree registry parsing and reconciliation (ops/worktrees.py)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.worktrees import (
    PROTECTED_WORKTREE_NAMES,
    GitWorktree,
    _update_registry_cleanup_state,
    classify_cleanup_candidates,
    is_main_worktree,
    is_protected,
    is_worktree_dirty,
    list_worktrees_registry,
    reconcile,
)


@pytest.fixture()
def registry_dir(tmp_path: Path) -> Path:
    """Create a temp registry dir."""
    d = tmp_path / "worktree_registry"
    d.mkdir()
    return d


def _write_registry_entry(
    registry_dir: Path,
    filename: str,
    *,
    lane_id: str = "author-a",
    lane_class: str = "author",
    worktree_path: str = "/tmp/wt-author",
    branch: str = "codex/steward-author",
    lifecycle_class: str = "persistent",
    last_active: str = "2026-03-18T10:00:00+00:00",
    session_id: str | None = None,
    ttl_hours: float | None = None,
    schema_version: int = 2,
    **extra: object,
) -> dict:
    """Helper to write a registry entry JSON file."""
    entry = {
        "schema_version": schema_version,
        "lane_id": lane_id,
        "lane_class": lane_class,
        "worktree_path": worktree_path,
        "branch": branch,
        "class": lifecycle_class,
        "created_at": "2026-03-18T10:00:00+00:00",
        "last_active": last_active,
        "session_id": session_id,
        "ttl_hours": ttl_hours,
        "display_name": None,
        "tmux_session": None,
        "tmux_window": None,
        "tmux_pane": None,
        "cmux_workspace_ref": None,
        "cmux_surface_ref": None,
        "legacy_role": None,
        **extra,
    }
    (registry_dir / filename).write_text(json.dumps(entry, indent=2))
    return entry


class TestListWorktreesRegistry:
    """Tests for list_worktrees_registry()."""

    def test_empty_dir(self, registry_dir: Path) -> None:
        entries = list_worktrees_registry(registry_dir)
        assert entries == []

    def test_reads_v2_entries(self, registry_dir: Path) -> None:
        _write_registry_entry(registry_dir, "author-a.json", lane_id="author-a")
        _write_registry_entry(registry_dir, "ops.json", lane_id="ops", lane_class="ops")

        entries = list_worktrees_registry(registry_dir)
        assert len(entries) == 2
        lane_ids = {e["lane_id"] for e in entries}
        assert lane_ids == {"author-a", "ops"}

    def test_infers_v1_fields(self, registry_dir: Path) -> None:
        v1_entry = {
            "schema_version": 1,
            "role": "author",
            "worktree_path": "/tmp/wt-author",
            "branch": "role/author",
            "class": "persistent",
            "created_at": "2026-03-16T22:00:00Z",
            "last_active": "2026-03-16T22:00:00Z",
            "session_id": None,
            "ttl_hours": None,
        }
        (registry_dir / "author.json").write_text(json.dumps(v1_entry))

        entries = list_worktrees_registry(registry_dir)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["lane_id"] == "author-a"
        assert entry["lane_class"] == "author"
        assert entry["legacy_role"] == "author"
        assert entry["tmux_session"] is None

    def test_v1_unknown_role_uses_role_as_fallback(self, registry_dir: Path) -> None:
        """v1 entry with unrecognized role should use the role name as fallback lane_id."""
        v1_entry = {
            "schema_version": 1,
            "role": "bogus_role",
            "worktree_path": "/tmp/wt-bogus",
            "branch": "role/bogus",
            "class": "ephemeral",
            "created_at": "2026-03-16T22:00:00Z",
            "last_active": "2026-03-16T22:00:00Z",
            "session_id": None,
            "ttl_hours": None,
        }
        (registry_dir / "bogus.json").write_text(json.dumps(v1_entry))

        entries = list_worktrees_registry(registry_dir)
        assert len(entries) == 1
        assert entries[0]["lane_id"] == "bogus_role"
        assert entries[0]["lane_class"] == "bogus_role"
        assert entries[0]["legacy_role"] == "bogus_role"

    def test_skips_malformed_files(self, registry_dir: Path) -> None:
        (registry_dir / "bad.json").write_text("not json {{{")
        _write_registry_entry(registry_dir, "good.json", lane_id="ops")

        entries = list_worktrees_registry(registry_dir)
        assert len(entries) == 1

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        entries = list_worktrees_registry(tmp_path / "no_such_dir")
        assert entries == []

    def test_ignores_non_json_files(self, registry_dir: Path) -> None:
        (registry_dir / "README.md").write_text("# Doc")
        _write_registry_entry(registry_dir, "ops.json", lane_id="ops")

        entries = list_worktrees_registry(registry_dir)
        assert len(entries) == 1


class TestIsProtected:
    """Tests for is_protected()."""

    def test_protected_names(self) -> None:
        for name in PROTECTED_WORKTREE_NAMES:
            assert is_protected(f"/Users/user/Projects/{name}")

    def test_non_protected(self) -> None:
        assert not is_protected("/tmp/work-feature-xyz")
        assert not is_protected("/tmp/Bid-Euchre")

    def test_ops_worktree_protected(self) -> None:
        """The ops lane worktree must be in the protected list (F3)."""
        assert is_protected("/tmp/Bid-Euchre-steward-ops")

    def test_partial_match_not_protected(self) -> None:
        assert not is_protected("/tmp/Bid-Euchre-steward-author-extra")


class TestIsMainWorktree:
    """Tests for is_main_worktree()."""

    def test_main_checkout_has_git_dir(self, tmp_path: Path) -> None:
        """A directory with a .git/ directory is the main working tree."""
        (tmp_path / ".git").mkdir()
        assert is_main_worktree(str(tmp_path)) is True

    def test_linked_worktree_has_git_file(self, tmp_path: Path) -> None:
        """A directory with a .git file (not directory) is a linked worktree."""
        (tmp_path / ".git").write_text("gitdir: /some/repo/.git/worktrees/foo")
        assert is_main_worktree(str(tmp_path)) is False

    def test_no_git_at_all(self, tmp_path: Path) -> None:
        """A directory without any .git is not the main worktree."""
        assert is_main_worktree(str(tmp_path)) is False

    def test_nonexistent_path(self) -> None:
        """Nonexistent path returns False (no crash)."""
        assert is_main_worktree("/tmp/no-such-dir-xyz") is False


class TestReconcile:
    """Tests for reconcile()."""

    def test_all_matched(self) -> None:
        git_wts = [
            GitWorktree(path="/tmp/wt-a", head="abc123", branch="branch-a"),
        ]
        registry = [{"worktree_path": "/tmp/wt-a", "lane_id": "author-a"}]

        report = reconcile(git_wts, registry)
        assert len(report.matched) == 1
        assert len(report.unregistered) == 0
        assert len(report.missing) == 0

    def test_unregistered_worktree(self) -> None:
        git_wts = [
            GitWorktree(path="/tmp/wt-a", head="abc", branch="branch-a"),
            GitWorktree(path="/tmp/wt-orphan", head="def", branch="branch-b"),
        ]
        registry = [{"worktree_path": "/tmp/wt-a", "lane_id": "author-a"}]

        report = reconcile(git_wts, registry)
        assert len(report.matched) == 1
        assert len(report.unregistered) == 1
        assert report.unregistered[0].path == "/tmp/wt-orphan"

    def test_missing_worktree(self) -> None:
        git_wts = [
            GitWorktree(path="/tmp/wt-a", head="abc", branch="branch-a"),
        ]
        registry = [
            {"worktree_path": "/tmp/wt-a", "lane_id": "author-a"},
            {"worktree_path": "/tmp/wt-gone", "lane_id": "review"},
        ]

        report = reconcile(git_wts, registry)
        assert len(report.matched) == 1
        assert len(report.missing) == 1
        assert report.missing[0]["lane_id"] == "review"
        assert len(report.warnings) == 1

    def test_bare_main_skipped(self) -> None:
        git_wts = [
            GitWorktree(path="/tmp/main", head="abc", branch="main", bare=True),
        ]
        registry: list[dict] = []

        report = reconcile(git_wts, registry)
        assert len(report.unregistered) == 0

    def test_empty_inputs(self) -> None:
        report = reconcile([], [])
        assert len(report.matched) == 0
        assert len(report.unregistered) == 0
        assert len(report.missing) == 0


class TestClassifyCleanupCandidates:
    """Tests for classify_cleanup_candidates()."""

    def test_persistent_not_candidate(self) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-a", head="abc", branch="br-a")]
        registry = [
            {
                "worktree_path": "/tmp/wt-a",
                "lane_id": "author-a",
                "class": "persistent",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": None,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 0

    def test_ephemeral_stale(self) -> None:
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")]
        registry = [
            {
                "worktree_path": "/tmp/wt-task",
                "lane_id": "task-1",
                "class": "ephemeral",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": 24,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].cleanup_state == "stale"
        assert "expired" in candidates[0].reason.lower()

    def test_ephemeral_within_ttl(self) -> None:
        now = datetime(2026, 3, 18, 14, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")]
        registry = [
            {
                "worktree_path": "/tmp/wt-task",
                "lane_id": "task-1",
                "class": "ephemeral",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": 24,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].cleanup_state == "idle"

    def test_ephemeral_active_session(self) -> None:
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")]
        registry = [
            {
                "worktree_path": "/tmp/wt-task",
                "lane_id": "task-1",
                "class": "ephemeral",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": "some-uuid",
                "ttl_hours": 24,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].cleanup_state == "active"

    def test_unregistered_worktree_candidate(self) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/orphan-wt", head="abc", branch="orphan")]
        registry: list[dict] = []

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].lifecycle_class == "unknown"
        assert "not in worktree registry" in candidates[0].reason.lower()

    def test_protected_worktree_not_cleanup_candidate(self) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        # Use a protected worktree name
        path = "/tmp/Bid-Euchre-steward-author"
        git_wts = [GitWorktree(path=path, head="abc", branch="codex/steward-author")]
        registry = [
            {
                "worktree_path": path,
                "lane_id": "author-a",
                "class": "persistent",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": None,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        # Persistent + protected → no candidate
        assert len(candidates) == 0

    def test_protected_unregistered_worktree_skipped(self) -> None:
        """Protected steward worktrees are not cleanup candidates even when unregistered."""
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        path = "/tmp/Bid-Euchre-steward-ops"
        git_wts = [GitWorktree(path=path, head="abc", branch="codex/steward-ops")]
        registry: list[dict] = []  # No registry entry at all

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        # Protected + unregistered → skipped entirely, not a candidate
        assert len(candidates) == 0

    def test_default_ttl_applied(self) -> None:
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")]
        registry = [
            {
                "worktree_path": "/tmp/wt-task",
                "lane_id": "task-1",
                "class": "ephemeral",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": None,  # No explicit TTL
            },
        ]

        # Default TTL is 24h, 48h have passed → stale
        candidates = classify_cleanup_candidates(
            git_wts, registry, ttl_hours_default=24.0, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].cleanup_state == "stale"

    def test_main_checkout_skipped(self, tmp_path: Path) -> None:
        """The main checkout is never a cleanup candidate even when unregistered."""
        # Create a fake main checkout (has .git directory)
        main_dir = tmp_path / "Bid-Euchre"
        main_dir.mkdir()
        (main_dir / ".git").mkdir()

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [
            GitWorktree(path=str(main_dir), head="abc", branch="main"),
        ]
        registry: list[dict] = []

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        # Main checkout should be filtered out
        assert len(candidates) == 0

    def test_linked_worktree_still_candidate(self, tmp_path: Path) -> None:
        """A linked worktree (non-main) that is unregistered remains a candidate."""
        # Create a fake linked worktree (has .git file, not directory)
        linked_dir = tmp_path / "worktree-feature"
        linked_dir.mkdir()
        (linked_dir / ".git").write_text("gitdir: /some/repo/.git/worktrees/feature")

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [
            GitWorktree(path=str(linked_dir), head="abc", branch="feature-x"),
        ]
        registry: list[dict] = []

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=False
        )
        assert len(candidates) == 1
        assert candidates[0].lifecycle_class == "unknown"


class TestIsWorktreeDirty:
    """Tests for is_worktree_dirty()."""

    def test_raises_on_nonexistent_path(self) -> None:
        """Missing path raises FileNotFoundError instead of silently returning True."""
        with pytest.raises(FileNotFoundError, match="does not exist"):
            is_worktree_dirty("/tmp/no-such-worktree-abc123")

    def test_raises_on_file_not_directory(self, tmp_path: Path) -> None:
        """A regular file (not a directory) raises FileNotFoundError."""
        f = tmp_path / "not-a-dir"
        f.write_text("hi")
        with pytest.raises(FileNotFoundError, match="not a directory"):
            is_worktree_dirty(str(f))

    def test_dirty_detection_with_mock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        # Use a real directory so the existence check passes
        wt_dir = tmp_path / "wt"
        wt_dir.mkdir()

        # Clean worktree
        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})(),
        )
        assert wt_mod.is_worktree_dirty(str(wt_dir)) is False

    def test_stale_dirty_becomes_quarantined(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When check_dirty=True and worktree is dirty, stale → quarantined."""
        from bid_euchre.ops import worktrees as wt_mod

        # Mock is_worktree_dirty since the path doesn't exist on disk
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: True)

        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        git_wts = [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")]
        registry = [
            {
                "worktree_path": "/tmp/wt-task",
                "lane_id": "task-1",
                "class": "ephemeral",
                "last_active": "2026-03-18T10:00:00+00:00",
                "session_id": None,
                "ttl_hours": 24,
            },
        ]

        candidates = classify_cleanup_candidates(
            git_wts, registry, now=now, check_dirty=True
        )
        assert len(candidates) == 1
        assert candidates[0].cleanup_state == "quarantined"
        assert candidates[0].is_dirty is True


class TestPruneWorktrees:
    """Tests for prune_worktrees()."""

    @pytest.fixture()
    def runtime_dir(self, tmp_path: Path) -> Path:
        rd = tmp_path / "runtime"
        (rd / "worktree_registry").mkdir(parents=True)
        (rd / "events").mkdir(parents=True)
        return rd

    def test_dry_run_returns_candidates_no_removal(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [GitWorktree(path="/tmp/wt-task", head="abc", branch="task-1")],
        )
        # Mock is_worktree_dirty since /tmp/wt-task doesn't exist on disk
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)

        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "task.json",
            lane_id="task-1",
            lifecycle_class="ephemeral",
            worktree_path="/tmp/wt-task",
            last_active="2020-01-01T00:00:00+00:00",
            ttl_hours=1.0,
        )

        results = wt_mod.prune_worktrees(runtime_dir, dry_run=True)
        assert len(results) >= 1
        # All results should be dry_run=True
        for r in results:
            assert r.dry_run is True

    def test_protected_worktree_skipped(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [
                GitWorktree(
                    path="/tmp/Bid-Euchre-steward-author",
                    head="abc",
                    branch="codex/steward-author",
                )
            ],
        )
        # Mock is_worktree_dirty since /tmp path doesn't exist on disk
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)

        results = wt_mod.prune_worktrees(runtime_dir, dry_run=True)
        # Protected unregistered worktrees get classified but skipped
        for r in results:
            assert r.action == "skipped"

    def test_persistent_worktree_not_candidate(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [GitWorktree(path="/tmp/wt-a", head="abc", branch="br-a")],
        )
        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "author-a.json",
            lane_id="author-a",
            lifecycle_class="persistent",
            worktree_path="/tmp/wt-a",
        )

        results = wt_mod.prune_worktrees(runtime_dir, dry_run=True)
        # Persistent worktrees are not candidates at all
        assert len(results) == 0

    def test_dry_run_dirty_stale_shows_quarantined(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dry-run must check dirtiness and show quarantined, not removed."""
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [GitWorktree(path="/tmp/wt-dirty", head="abc", branch="task-2")],
        )
        # Mock is_worktree_dirty to return True
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: True)

        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "task-dirty.json",
            lane_id="task-2",
            lifecycle_class="ephemeral",
            worktree_path="/tmp/wt-dirty",
            last_active="2020-01-01T00:00:00+00:00",
            ttl_hours=1.0,
        )

        results = wt_mod.prune_worktrees(runtime_dir, dry_run=True)
        assert len(results) == 1
        # Must show quarantined, not removed — dirtiness is checked even in dry-run
        assert results[0].action == "quarantined"
        assert results[0].dry_run is True

    def test_prune_continues_after_quarantine_failure(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If quarantine_worktree fails, prune skips that candidate and continues (F4)."""
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [
                GitWorktree(path="/tmp/wt-fail", head="a", branch="t-fail"),
                GitWorktree(path="/tmp/wt-ok", head="b", branch="t-ok"),
            ],
        )
        # Both dirty and stale
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: True)

        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "fail.json",
            lane_id="fail",
            lifecycle_class="ephemeral",
            worktree_path="/tmp/wt-fail",
            last_active="2020-01-01T00:00:00+00:00",
            ttl_hours=1.0,
        )
        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "ok.json",
            lane_id="ok",
            lifecycle_class="ephemeral",
            worktree_path="/tmp/wt-ok",
            last_active="2020-01-01T00:00:00+00:00",
            ttl_hours=1.0,
        )

        call_count = 0
        original_quarantine = wt_mod.quarantine_worktree

        def failing_quarantine(path: str, *a: object, **kw: object) -> object:
            nonlocal call_count
            call_count += 1
            if "fail" in path:
                raise OSError("Simulated quarantine failure")
            return original_quarantine(path, *a, **kw)

        monkeypatch.setattr(wt_mod, "quarantine_worktree", failing_quarantine)

        results = wt_mod.prune_worktrees(
            runtime_dir, dry_run=False, events_dir=runtime_dir / "events"
        )

        actions = {r.path: r.action for r in results}
        # First candidate fails quarantine → skipped
        assert actions["/tmp/wt-fail"] == "skipped"
        assert "Quarantine failed" in next(
            r.reason for r in results if r.path == "/tmp/wt-fail"
        )
        # Second candidate should still be processed
        assert "/tmp/wt-ok" in actions


class TestQuarantineWorktree:
    """Tests for quarantine_worktree()."""

    @pytest.fixture()
    def runtime_dir(self, tmp_path: Path) -> Path:
        rd = tmp_path / "runtime"
        rd.mkdir(parents=True)
        return rd

    def test_saves_diff_file(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        # Mock git diff to return some content
        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type(
                "R", (), {"returncode": 0, "stdout": "diff --git a/foo\n+bar\n"}
            )(),
        )

        diff_path = wt_mod.quarantine_worktree(
            "/tmp/wt-orphan",
            "stale and dirty",
            runtime_dir,
            events_dir=tmp_path / "events",
        )

        assert diff_path.exists()
        assert "diff --git" in diff_path.read_text()
        assert diff_path.parent.name == "worktree_quarantine"

    def test_quarantine_creates_directory(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})(),
        )

        wt_mod.quarantine_worktree(
            "/tmp/wt-x",
            "test reason",
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

        assert (runtime_dir / "worktree_quarantine").is_dir()

    def test_quarantine_persists_cleanup_state(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quarantine must update cleanup_state in the registry JSON."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": ""})(),
        )

        # Create a registry entry for the worktree
        (runtime_dir / "worktree_registry").mkdir(parents=True, exist_ok=True)
        _write_registry_entry(
            runtime_dir / "worktree_registry",
            "task-q.json",
            lane_id="task-q",
            lifecycle_class="ephemeral",
            worktree_path="/tmp/wt-q",
        )

        wt_mod.quarantine_worktree(
            "/tmp/wt-q",
            "dirty and stale",
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

        # Verify registry entry was updated
        updated = json.loads(
            (runtime_dir / "worktree_registry" / "task-q.json").read_text()
        )
        assert updated["cleanup_state"] == "quarantined"

    def test_quarantine_captures_untracked_files(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quarantine diff file must include untracked file listing (892-M2)."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        call_count = 0

        def mock_run(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            cmd = args[0] if args else kwargs.get("args", [])
            call_count += 1
            if "diff" in cmd:
                return type(
                    "R",
                    (),
                    {"returncode": 0, "stdout": "diff --git a/foo\n+modified\n"},
                )()
            if "ls-files" in cmd:
                return type(
                    "R",
                    (),
                    {"returncode": 0, "stdout": "new_file.py\ndata/scratch.csv\n"},
                )()
            return type("R", (), {"returncode": 0, "stdout": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        diff_path = wt_mod.quarantine_worktree(
            "/tmp/wt-untracked",
            "stale with untracked",
            runtime_dir,
            events_dir=tmp_path / "events",
        )

        content = diff_path.read_text()
        # Must contain the diff
        assert "diff --git" in content
        # Must contain untracked file listing
        assert "# Untracked files" in content
        assert "# - new_file.py" in content
        assert "# - data/scratch.csv" in content

    def test_quarantine_no_untracked_section_when_clean(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When there are no untracked files, no untracked section is added."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        def mock_run(*args: object, **kwargs: object) -> object:
            cmd = args[0] if args else kwargs.get("args", [])
            if "diff" in cmd:
                return type(
                    "R",
                    (),
                    {"returncode": 0, "stdout": "diff --git a/foo\n+bar\n"},
                )()
            # ls-files returns empty (no untracked files)
            return type("R", (), {"returncode": 0, "stdout": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        diff_path = wt_mod.quarantine_worktree(
            "/tmp/wt-clean-untracked",
            "stale but no untracked",
            runtime_dir,
            events_dir=tmp_path / "events",
        )

        content = diff_path.read_text()
        assert "diff --git" in content
        assert "# Untracked files" not in content

    def test_quarantine_diff_filename_has_timestamp(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated quarantines produce different diff files (F2)."""
        import subprocess as sp
        import time

        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "diff1"})(),
        )

        path1 = wt_mod.quarantine_worktree(
            "/tmp/wt-repeat",
            "first quarantine",
            runtime_dir,
            events_dir=tmp_path / "events",
        )

        # Ensure at least 1 second passes for distinct timestamp
        time.sleep(1.1)

        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "diff2"})(),
        )

        path2 = wt_mod.quarantine_worktree(
            "/tmp/wt-repeat",
            "second quarantine",
            runtime_dir,
            events_dir=tmp_path / "events",
        )

        # Must be different files
        assert path1 != path2
        assert path1.exists()
        assert path2.exists()
        # Both should contain the slug
        assert "wt-repeat" in path1.name
        assert "wt-repeat" in path2.name


class TestArchiveWorktree:
    """Tests for archive_worktree()."""

    @pytest.fixture()
    def runtime_dir(self, tmp_path: Path) -> Path:
        rd = tmp_path / "runtime"
        (rd / "worktree_registry").mkdir(parents=True)
        return rd

    def test_rejects_cwd(self, runtime_dir: Path) -> None:
        from bid_euchre.ops.worktrees import archive_worktree

        cwd = str(Path.cwd())
        with pytest.raises(ValueError, match="current working directory"):
            archive_worktree(cwd, runtime_dir)

    def test_rejects_protected(self, runtime_dir: Path, tmp_path: Path) -> None:
        from bid_euchre.ops.worktrees import archive_worktree

        # Create a real directory with a protected name
        protected_dir = tmp_path / "Bid-Euchre-steward-author"
        protected_dir.mkdir()
        with pytest.raises(ValueError, match="protected"):
            archive_worktree(
                str(protected_dir),
                runtime_dir,
            )

    def test_rejects_dirty_without_force(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        # Create a real directory so the existence check passes
        wt_dir = tmp_path / "some-worktree"
        wt_dir.mkdir()

        # Mock is_worktree_dirty to return True
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: True)

        with pytest.raises(RuntimeError, match="uncommitted changes"):
            wt_mod.archive_worktree(str(wt_dir), runtime_dir)

    def test_calls_git_worktree_remove(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        # Create a real directory so the existence check passes
        wt_dir = tmp_path / "some-worktree"
        wt_dir.mkdir()

        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)

        commands_run: list[list[str]] = []

        def mock_run(*args: object, **kwargs: object) -> object:
            cmd = args[0] if args else kwargs.get("args", [])
            commands_run.append(list(cmd))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        wt_mod.archive_worktree(
            str(wt_dir),
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

        assert any(
            "worktree" in str(cmd) and "remove" in str(cmd) for cmd in commands_run
        )

    def test_archive_passes_force_flag(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--force is passed to git worktree remove when force=True (#967)."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        wt_dir = tmp_path / "dirty-worktree"
        wt_dir.mkdir()

        # force=True bypasses the dirty check, so we don't need to mock it as clean
        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: True)

        commands_run: list[list[str]] = []

        def mock_run(*args: object, **kwargs: object) -> object:
            cmd = args[0] if args else kwargs.get("args", [])
            commands_run.append(list(cmd))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        wt_mod.archive_worktree(
            str(wt_dir),
            runtime_dir,
            events_dir=runtime_dir / "events",
            force=True,
        )

        git_cmds = [c for c in commands_run if "worktree" in str(c)]
        assert len(git_cmds) == 1
        assert "--force" in git_cmds[0], f"--force missing from: {git_cmds[0]}"

    def test_archive_no_force_flag_by_default(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--force is NOT in the command when force=False."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        wt_dir = tmp_path / "clean-worktree"
        wt_dir.mkdir()

        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)

        commands_run: list[list[str]] = []

        def mock_run(*args: object, **kwargs: object) -> object:
            cmd = args[0] if args else kwargs.get("args", [])
            commands_run.append(list(cmd))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(sp, "run", mock_run)

        wt_mod.archive_worktree(
            str(wt_dir),
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

        git_cmds = [c for c in commands_run if "worktree" in str(c)]
        assert len(git_cmds) == 1
        assert "--force" not in git_cmds[0], f"Unexpected --force in: {git_cmds[0]}"

    def test_archive_cleans_registry_entry(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After successful removal, the registry JSON file is deleted (892-M4)."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        # Create a real directory so the existence check passes
        wt_dir = tmp_path / "wt-to-archive"
        wt_dir.mkdir()

        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)
        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type(
                "R", (), {"returncode": 0, "stdout": "", "stderr": ""}
            )(),
        )

        # Create a registry entry for the worktree we will archive
        registry_dir = runtime_dir / "worktree_registry"
        _write_registry_entry(
            registry_dir,
            "task-archive.json",
            lane_id="task-archive",
            lifecycle_class="ephemeral",
            worktree_path=str(wt_dir),
        )
        # Also create an unrelated entry that should survive
        _write_registry_entry(
            registry_dir,
            "other.json",
            lane_id="other",
            worktree_path="/tmp/other-wt",
        )

        assert (registry_dir / "task-archive.json").exists()
        assert (registry_dir / "other.json").exists()

        wt_mod.archive_worktree(
            str(wt_dir),
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

        # The archived worktree's registry entry should be removed
        assert not (registry_dir / "task-archive.json").exists()
        # The unrelated entry should remain
        assert (registry_dir / "other.json").exists()

    def test_archive_no_crash_without_registry_entry(
        self, runtime_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Archive succeeds even when no registry entry exists for the worktree."""
        import subprocess as sp

        from bid_euchre.ops import worktrees as wt_mod

        # Create a real directory so the existence check passes
        wt_dir = tmp_path / "unregistered-wt"
        wt_dir.mkdir()

        monkeypatch.setattr(wt_mod, "is_worktree_dirty", lambda p: False)
        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type(
                "R", (), {"returncode": 0, "stdout": "", "stderr": ""}
            )(),
        )

        # No registry entry for this worktree — should not crash
        wt_mod.archive_worktree(
            str(wt_dir),
            runtime_dir,
            events_dir=runtime_dir / "events",
        )

    def test_archive_missing_dir_gives_clear_error(self, runtime_dir: Path) -> None:
        """Archiving a nonexistent path raises FileNotFoundError, not RuntimeError (F8)."""
        from bid_euchre.ops.worktrees import archive_worktree

        with pytest.raises(FileNotFoundError, match="not found"):
            archive_worktree("/tmp/no-such-worktree-xyz", runtime_dir)


class TestUpdateRegistryCleanupState:
    """Tests for _update_registry_cleanup_state()."""

    @pytest.fixture()
    def registry_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "worktree_registry"
        d.mkdir()
        return d

    def test_updates_matching_entry(self, registry_dir: Path) -> None:
        """Updates cleanup_state for a matching worktree path (F7)."""
        _write_registry_entry(
            registry_dir,
            "author-a.json",
            lane_id="author-a",
            worktree_path="/tmp/wt-author",
        )

        result = _update_registry_cleanup_state(
            registry_dir, "/tmp/wt-author", "quarantined"
        )
        assert result is True

        data = json.loads((registry_dir / "author-a.json").read_text())
        assert data["cleanup_state"] == "quarantined"

    def test_returns_false_for_no_match(self, registry_dir: Path) -> None:
        """Returns False when no registry entry matches the path."""
        _write_registry_entry(
            registry_dir,
            "author-a.json",
            lane_id="author-a",
            worktree_path="/tmp/wt-author",
        )

        result = _update_registry_cleanup_state(
            registry_dir, "/tmp/wt-nonexistent", "quarantined"
        )
        assert result is False

    def test_produces_valid_json_after_update(self, registry_dir: Path) -> None:
        """File remains valid JSON after read-modify-write (F7 TOCTOU fix)."""
        _write_registry_entry(
            registry_dir,
            "task.json",
            lane_id="task-1",
            worktree_path="/tmp/wt-task",
        )

        _update_registry_cleanup_state(registry_dir, "/tmp/wt-task", "archived")

        # Must be valid JSON with the updated field
        data = json.loads((registry_dir / "task.json").read_text())
        assert data["cleanup_state"] == "archived"
        # Original fields preserved
        assert data["lane_id"] == "task-1"
        assert data["worktree_path"] == "/tmp/wt-task"

    def test_nonexistent_dir_returns_false(self, tmp_path: Path) -> None:
        result = _update_registry_cleanup_state(
            tmp_path / "no_such_dir", "/tmp/wt", "quarantined"
        )
        assert result is False

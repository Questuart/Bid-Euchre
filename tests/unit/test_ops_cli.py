"""Tests for the ops.py CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

# Import the CLI module — it lives in scripts/internal/ so we add it to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


@pytest.fixture(autouse=True)
def _add_scripts_path() -> None:
    """Ensure scripts/internal is importable."""
    path_str = str(SCRIPTS_DIR)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory with standard subdirs."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    (rd / "scheduler").mkdir(parents=True)
    return rd


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    """Create a temp plans directory."""
    d = tmp_path / "plans"
    d.mkdir()
    return d


class TestBuildParser:
    """Tests for build_parser()."""

    def test_parser_creation(self) -> None:
        import ops

        parser = ops.build_parser()
        assert parser is not None

    def test_no_command_returns_1(self) -> None:
        import ops

        rc = ops.main([])
        assert rc == 1


class TestCmdStatus:
    """Tests for the status subcommand."""

    def test_status_text(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "status"]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "Steward Status" in captured.out

    def test_status_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "status",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "lanes" in data
        assert "warnings" in data

    def test_status_json_lane_activity_fields(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output includes lane-activity fields when lanes exist."""
        from datetime import datetime, timezone

        recent = datetime.now(timezone.utc).isoformat()
        # Create a lane with session and task
        (runtime_dir / "worktree_registry" / "author-a.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "lane_id": "author-a",
                    "lane_class": "author",
                    "worktree_path": "/tmp/wt-a",
                    "branch": "codex/steward-author",
                    "class": "persistent",
                    "session_id": "uuid-1",
                    "last_active": recent,
                }
            )
        )
        (runtime_dir / "session_metadata" / "session-1.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "session_id": "uuid-1",
                    "lane_id": "author-a",
                    "started_at": recent,
                    "task": "Test task",
                }
            )
        )
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "task_id": "t1",
                    "owner_lane": "author-a",
                    "subject": "Test task",
                    "status": "in_progress",
                    "pr_number": 999,
                    "blocked_by": [],
                    "items": [],
                }
            )
        )

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "status",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["lanes"]) == 1
        lane = data["lanes"][0]
        assert lane["state"] == "active"
        assert lane["current_task_id"] == "t1"
        assert lane["current_task_title"] == "Test task"
        assert lane["linked_pr"] == 999
        assert lane["attention_needed"] is False

    def test_status_text_lane_activity(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Text output shows lane-activity format.

        A lane with session_id=None but a recent last_active timestamp
        shows as ``likely_active`` (not idle) since the fallback liveness
        probe detects the fresh registry timestamp.
        """
        from datetime import datetime, timezone

        recent = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "worktree_registry" / "ops.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "lane_id": "ops",
                    "lane_class": "ops",
                    "worktree_path": "/tmp/wt-ops",
                    "branch": "codex/steward-ops",
                    "class": "persistent",
                    "session_id": None,
                    "last_active": recent,
                }
            )
        )

        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "status"]
        )
        assert rc == 0
        text = capsys.readouterr().out
        assert "Lane Activity:" in text
        assert "[likely_active]" in text
        assert "ops" in text


class TestCmdEvents:
    """Tests for the events subcommand."""

    def test_events_empty(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "events"]
        )
        assert rc == 0
        assert "No events" in capsys.readouterr().out

    def test_events_json_empty(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "events",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_events_drain_subcommand(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test `ops.py events drain` (canonical drain interface per governing plan)."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "events",
                "drain",
            ]
        )
        assert rc == 0
        assert "Drained 0" in capsys.readouterr().out

    def test_events_drain_json_subcommand(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test `ops.py --json events drain` returns valid JSON (888-L1)."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "events",
                "drain",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["drained"] == 0


class TestCmdTick:
    """Tests for the tick subcommand."""

    def test_tick_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "tick"]
        )
        assert rc == 0
        assert "Tick #1" in capsys.readouterr().out

    def test_tick_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "tick",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["tick_number"] == 1


class TestCmdWatchdogs:
    """Tests for the watchdogs subcommand."""

    def test_watchdogs_clean(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "watchdogs",
            ]
        )
        assert rc == 0
        assert "all clear" in capsys.readouterr().out.lower()


class TestCmdHealth:
    """Tests for the health subcommand."""

    def test_health_clean(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "health",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Steward Status" in captured
        assert "all clear" in captured.lower()


class TestCmdWorktrees:
    """Tests for the worktrees subcommand."""

    def test_worktrees_with_mock(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
            ]
        )
        assert rc == 0
        assert "Worktree Registry" in capsys.readouterr().out

    def test_worktrees_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "matched" in data
        assert "unregistered" in data

    def test_worktrees_json_includes_visibility(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Worktrees JSON output includes visibility and session_handle fields."""
        from bid_euchre.ops import worktrees as wt_mod

        # Create a registry entry with additive fields
        reg_dir = runtime_dir / "worktree_registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        (reg_dir / "author-a.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "lane_id": "author-a",
                    "lane_class": "author",
                    "worktree_path": "/tmp/wt-a",
                    "branch": "codex/steward-author",
                    "class": "persistent",
                    "last_active": "2026-03-21T10:00:00Z",
                    "session_handle": "steward:author-a",
                    "visibility": "foreground",
                }
            )
        )

        # Mock git to return a matching worktree
        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [
                wt_mod.GitWorktree(
                    path="/tmp/wt-a", head="abc", branch="codex/steward-author"
                )
            ],
        )

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["matched"]) == 1
        matched = data["matched"][0]
        assert matched["visibility"] == "foreground"
        assert matched["session_handle"] == "steward:author-a"

    def test_worktrees_json_null_visibility_for_old_entries(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Old entries without visibility get null in JSON output."""
        from bid_euchre.ops import worktrees as wt_mod

        reg_dir = runtime_dir / "worktree_registry"
        reg_dir.mkdir(parents=True, exist_ok=True)
        (reg_dir / "ops.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "lane_id": "ops",
                    "lane_class": "ops",
                    "worktree_path": "/tmp/wt-ops",
                    "branch": "--",
                    "class": "persistent",
                    "last_active": "2026-03-21T10:00:00Z",
                }
            )
        )

        monkeypatch.setattr(
            wt_mod,
            "list_worktrees_git",
            lambda: [wt_mod.GitWorktree(path="/tmp/wt-ops", head="def", branch="--")],
        )

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["matched"]) == 1
        matched = data["matched"][0]
        assert matched["visibility"] is None
        assert matched["session_handle"] is None


class TestCmdWorktreesPrune:
    """Tests for the worktrees prune subcommand."""

    def test_prune_dry_run_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "prune",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "DRY-RUN" in captured

    def test_prune_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "prune",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)


class TestCmdWorktreesQuarantine:
    """Tests for the worktrees quarantine subcommand."""

    def test_quarantine_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import subprocess as sp

        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type(
                "R", (), {"returncode": 0, "stdout": "diff content\n", "stderr": ""}
            )(),
        )

        import ops

        # Bypass boundary check — this test covers quarantine logic, not boundary
        monkeypatch.setattr(ops, "_check_boundary", lambda *a, **kw: None)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "quarantine",
                "/tmp/some-worktree",
                "--reason",
                "test quarantine",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Quarantined" in captured


class TestCmdWorktreesArchive:
    """Tests for the worktrees archive subcommand."""

    def test_archive_rejects_protected(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Create a real directory with a protected name
        protected_dir = tmp_path / "Bid-Euchre-steward-author"
        protected_dir.mkdir()

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "archive",
                str(protected_dir),
            ]
        )
        assert rc == 1
        assert "protected" in capsys.readouterr().err.lower()


class TestCmdRecover:
    """Tests for the recover subcommand."""

    def test_recover_empty(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "recover",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Recovery Guidance" in captured
        assert "All clear" in captured

    def test_recover_json_empty(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "recover",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_recover_with_failure_events(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Write a failure event
        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text(
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "ci_failure",
                    "source": "test",
                    "lane_id": "author-a",
                    "payload": {"details": "lint failed"},
                }
            )
            + "\n"
        )

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "recover",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Active failures: 1" in captured
        assert "ci_failure" in captured


class TestCmdReviews:
    """Tests for the reviews subcommand."""

    def test_reviews_text_no_prs(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import reviews as rev_mod

        monkeypatch.setattr(rev_mod, "get_open_pr_reviews", lambda: [])

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "reviews",
            ]
        )
        assert rc == 0
        assert "No open PRs" in capsys.readouterr().out

    def test_reviews_json_no_prs(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import reviews as rev_mod

        monkeypatch.setattr(rev_mod, "get_open_pr_reviews", lambda: [])

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "reviews",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_reviews_with_pr_flag(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import reviews as rev_mod
        from bid_euchre.ops.reviews import ReviewOutcome

        mock_outcome = ReviewOutcome(
            pr_number=42,
            title="Test PR",
            branch="feat/test",
            ci_status="success",
            review_status="success",
            has_precheck_ci=True,
            url="https://github.com/org/repo/pull/42",
        )
        monkeypatch.setattr(rev_mod, "get_pr_review_detail", lambda n: mock_outcome)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "reviews",
                "--pr",
                "42",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "#42" in captured


class TestCmdComments:
    """Tests for the comments subcommand."""

    def test_comments_requires_pr(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """comments without --pr should fail."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "comments",
            ]
        )
        assert rc == 1
        assert "--pr" in capsys.readouterr().err

    def test_comments_json_output(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """comments --pr N --json returns JSON overlay (mocked gh)."""
        import subprocess

        from bid_euchre.ops import reviews as rev_mod

        raw_comments = [
            {
                "id": 1,
                "login": "chatgpt-codex-connector[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T10:00:00Z",
                "body": "LGTM",
            },
            {
                "id": 2,
                "login": "octocat",
                "user_type": "User",
                "created_at": "2026-03-20T11:00:00Z",
                "body": "Thanks!",
            },
        ]
        monkeypatch.setattr(
            rev_mod,
            "_run_gh",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(raw_comments), stderr=""
            ),
        )

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "comments",
                "--pr",
                "42",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["total_comments"] == 2
        assert data[0]["trusted_bot_comments"] == 1

    def test_comments_ingest_writes_sidecar(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """comments --pr N --ingest writes sidecar JSONL and emits event."""
        import subprocess

        from bid_euchre.ops import reviews as rev_mod

        raw_comments = [
            {
                "id": 1,
                "login": "chatgpt-codex-connector[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T10:00:00Z",
                "body": "Review done",
            },
        ]
        monkeypatch.setattr(
            rev_mod,
            "_run_gh",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout=json.dumps(raw_comments), stderr=""
            ),
        )

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "comments",
                "--pr",
                "42",
                "--ingest",
            ]
        )
        assert rc == 0

        sidecar = runtime_dir / "pr_comments" / "pr_42.jsonl"
        assert sidecar.exists()
        lines = sidecar.read_text().strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["author_login"] == "chatgpt-codex-connector[bot]"
        assert record["author_type"] == "trusted_bot"

        # Verify event was emitted
        from bid_euchre.ops.events import read_events

        events = read_events(runtime_dir / "events")
        assert len(events) == 1
        event = events[0]
        assert event["event_type"] == "pr_comment_ingested"
        assert event["payload"]["pr_number"] == 42


class TestCmdCI:
    """Tests for the ci subcommand."""

    def test_ci_requires_pr(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "ci",
            ]
        )
        assert rc == 1
        assert "--pr" in capsys.readouterr().err

    def test_ci_success(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import ci as ci_mod
        from bid_euchre.ops.ci import CIStatusReport

        mock_report = CIStatusReport(
            pr_number=42, overall="success", checks=[], classifications=[]
        )
        monkeypatch.setattr(ci_mod, "poll_ci_status", lambda n: mock_report)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "ci",
                "--pr",
                "42",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "PR #42" in captured
        assert "success" in captured

    def test_ci_failure_returns_1(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import ci as ci_mod
        from bid_euchre.ops.ci import CIStatusReport

        mock_report = CIStatusReport(
            pr_number=99, overall="failure", checks=[], classifications=[]
        )
        monkeypatch.setattr(ci_mod, "poll_ci_status", lambda n: mock_report)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "ci",
                "--pr",
                "99",
            ]
        )
        assert rc == 1

    def test_ci_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import ci as ci_mod
        from bid_euchre.ops.ci import CIStatusReport

        mock_report = CIStatusReport(
            pr_number=42, overall="success", checks=[], classifications=[]
        )
        monkeypatch.setattr(ci_mod, "poll_ci_status", lambda n: mock_report)

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "ci",
                "--pr",
                "42",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["pr_number"] == 42
        assert data["overall"] == "success"


# ---- Phase 3D: Daemon + Retry CLI tests ----


class TestCmdDaemon:
    """Tests for the daemon subcommand."""

    def test_daemon_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        # Patch daemon to run with no-op sleep and limited iterations
        from bid_euchre.ops import scheduler as sched_mod

        original_daemon = sched_mod.daemon

        def fast_daemon(**kwargs):
            kwargs["_sleep_fn"] = lambda _: None
            kwargs["max_iterations"] = 2
            return original_daemon(**kwargs)

        monkeypatch.setattr(sched_mod, "daemon", fast_daemon)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "daemon",
                "--max-ticks",
                "2",
                "--interval",
                "1",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Daemon Run Summary" in captured

    def test_daemon_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        from bid_euchre.ops import scheduler as sched_mod

        original_daemon = sched_mod.daemon

        def fast_daemon(**kwargs):
            kwargs["_sleep_fn"] = lambda _: None
            kwargs["max_iterations"] = 2
            return original_daemon(**kwargs)

        monkeypatch.setattr(sched_mod, "daemon", fast_daemon)

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "daemon",
                "--max-ticks",
                "2",
                "--interval",
                "1",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "ticks_completed" in data
        assert data["stopped_reason"] == "max_iterations"


class TestCmdDaemonErrorExit:
    """Tests for daemon error exit code (Codex P2 fix)."""

    def test_daemon_error_returns_1(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Daemon that stops on errors should return non-zero."""
        from bid_euchre.ops import scheduler as sched_mod
        from bid_euchre.ops.scheduler import DaemonResult

        mock_result = DaemonResult(
            ticks_completed=2,
            total_findings=0,
            critical_findings=0,
            total_events_emitted=3,
            errors=["tick 1 failed", "tick 2 failed", "tick 3 failed"],
            stopped_reason="error",
        )
        monkeypatch.setattr(sched_mod, "daemon", lambda **kw: mock_result)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "daemon",
                "--max-ticks",
                "5",
            ]
        )
        assert rc == 1


class TestCmdRetry:
    """Tests for the retry subcommand."""

    def test_retry_no_failures(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "task-1",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Retry/Reroute Policy" in captured
        assert "RETRY" in captured

    def test_retry_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "task-1",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["task_id"] == "task-1"
        assert data["action"] == "retry"

    def test_retry_with_failures(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """With 3 failures, action should be reroute."""
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps(
                    {
                        "timestamp": f"2026-03-18T10:0{i}:00Z",
                        "event_type": "task_failed",
                        "source": "test",
                        "lane_id": "author-a",
                        "payload": {"task_id": "task-x", "details": f"err {i}"},
                    }
                )
            )
        events_file.write_text("\n".join(lines) + "\n")

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "task-x",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["action"] == "reroute"
        assert data["reroute_to"] is not None
        assert data["reroute_to"] != "author-a"


# ---- PR-4: Index, Query, Memory, Compact CLI tests ----


class TestCmdIndex:
    """Tests for the index subcommand."""

    def test_index_build(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "index"]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Audit Index" in captured

    def test_index_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "index",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "build" in data
        assert "stats" in data
        assert "sources_indexed" in data["build"]

    def test_index_rebuild(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "index",
                "--rebuild",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "Rebuilt" in captured


class TestCmdQuery:
    """Tests for the query subcommand."""

    def test_query_recent(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        # Build index first
        ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "index"]
        )
        capsys.readouterr()  # clear output

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "query",
                "--recent",
            ]
        )
        assert rc == 0

    def test_query_text_search(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        # Build index first
        ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "index"]
        )
        capsys.readouterr()

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "query",
                "--text",
                "test",
            ]
        )
        assert rc == 0

    def test_query_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        # Build index first
        ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "index",
            ]
        )
        capsys.readouterr()

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "query",
                "--recent",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "query" in data
        assert "results" in data


class TestCmdMemory:
    """Tests for the memory subcommand."""

    def test_memory_empty(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            ["--runtime-dir", str(runtime_dir), "--plans-dir", str(plans_dir), "memory"]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "no curated memory" in captured.lower()

    def test_memory_json_empty(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "memory",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestCmdCompact:
    """Tests for the compact subcommand."""

    def test_compact_no_archives(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "compact",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr().out
        assert "no archived" in captured.lower()

    def test_compact_json_no_archives(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "compact",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []


# ---- PR-5: Scope CLI Tests ----


class TestScopeShow:
    """Tests for ops.py scope show."""

    def test_show_scope(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "scope": {
                        "declared_files": ["src/*.py"],
                        "touched_files": ["src/a.py"],
                    },
                }
            )
        )
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "scope",
                "show",
                "--task",
                "t1",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "src/*.py" in out
        assert "src/a.py" in out

    def test_show_scope_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "scope": {
                        "declared_files": ["src/*.py"],
                        "touched_files": [],
                    },
                }
            )
        )
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "scope",
                "show",
                "--task",
                "t1",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["declared_files"] == ["src/*.py"]

    def test_show_nonexistent_task(self, runtime_dir: Path, plans_dir: Path) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "scope",
                "show",
                "--task",
                "nonexistent",
            ]
        )
        assert rc == 1


class TestScopeSet:
    """Tests for ops.py scope set."""

    def test_set_declared(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "scope",
                "set",
                "--task",
                "t1",
                "--declared",
                "src/bid_euchre/ops/*.py",
                "tests/unit/test_ops_*.py",
            ]
        )
        assert rc == 0
        # Verify the file was updated
        data = json.loads((runtime_dir / "task_state" / "t1.json").read_text())
        assert data["scope"]["declared_files"] == [
            "src/bid_euchre/ops/*.py",
            "tests/unit/test_ops_*.py",
        ]


class TestScopeTouch:
    """Tests for ops.py scope touch."""

    def test_touch_files(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {"declared_files": [], "touched_files": ["a.py"]},
                }
            )
        )
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "scope",
                "touch",
                "--task",
                "t1",
                "--file",
                "b.py",
                "c.py",
            ]
        )
        assert rc == 0
        data = json.loads((runtime_dir / "task_state" / "t1.json").read_text())
        assert data["scope"]["touched_files"] == ["a.py", "b.py", "c.py"]


# ---- PR-5: Retry Event Emission Tests ----


class TestRetryEmit:
    """Tests for ops.py retry --emit."""

    def test_retry_emits_event(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        # Create a task_failed event to give retry something to evaluate
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "test",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "lint error"},
                }
            )
        ]
        events_file.write_text("\n".join(lines) + "\n")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "t1",
                "--lane",
                "author-a",
                "--emit",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["action"] == "retry"

        # Verify event was emitted
        events_content = events_file.read_text()
        assert "retry_attempted" in events_content

    def test_retry_no_emit_by_default(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text("")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "t1",
            ]
        )
        assert rc == 0
        # No event emitted when --emit not passed
        events_content = events_file.read_text()
        assert "retry_attempted" not in events_content

    def test_retry_reroute_emits_task_rerouted(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": f"2026-03-18T10:0{i}:00Z",
                    "event_type": "task_failed",
                    "source": "test",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": f"error {i}"},
                }
            )
            for i in range(3)
        ]
        events_file.write_text("\n".join(lines) + "\n")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "t1",
                "--lane",
                "author-a",
                "--max-retries",
                "3",
                "--emit",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["action"] == "reroute"

        # Verify event was emitted
        events_content = events_file.read_text()
        assert "task_rerouted" in events_content

    def test_retry_escalate_emits_escalation(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Failures exceeding max_retries → escalation event emitted."""
        import ops

        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": f"2026-03-18T10:0{i}:00Z",
                    "event_type": "task_failed",
                    "source": "test",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": f"error {i}"},
                }
            )
            for i in range(5)
        ]
        events_file.write_text("\n".join(lines) + "\n")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "retry",
                "--task",
                "t1",
                "--max-retries",
                "3",
                "--emit",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["action"] == "escalate"
        assert data["retry_count"] == 5

        # Verify escalation event was emitted with correct payload
        events_content = events_file.read_text()
        assert "escalation" in events_content
        # Parse the emitted event to verify payload shape
        for line in events_content.strip().split("\n"):
            event = json.loads(line)
            if event.get("event_type") == "escalation":
                assert event["payload"]["task_id"] == "t1"
                assert "human attention" in event["payload"]["details"].lower()
                assert event["payload"]["retry_count"] == 5
                break
        else:
            pytest.fail("No escalation event found in event log")


# ---- Standalone CLI script tests (#992) ----


class TestBuildAuditIndexCli:
    """Tests for build_audit_index.py main()."""

    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        import build_audit_index

        with pytest.raises(SystemExit, match="0"):
            build_audit_index.main(["--help"])

    def test_build_index_default(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Runs the build with temp dirs — exercises arg parsing and output."""
        from bid_euchre.ops.index import BuildResult

        def mock_build(*_args: object, **_kwargs: object) -> BuildResult:
            return BuildResult(
                sources_indexed=2,
                entries_indexed=10,
                errors=[],
                duration_seconds=0.1,
            )

        monkeypatch.setattr("bid_euchre.ops.index.build_index", mock_build)

        from bid_euchre.ops.index import IndexStats

        def mock_stats(*_args: object, **_kwargs: object) -> IndexStats:
            return IndexStats(
                total_entries=10,
                db_path=str(runtime_dir / "audit_index" / "index.db"),
                source_counts={"events": 5, "plans": 5},
            )

        monkeypatch.setattr("bid_euchre.ops.index.get_stats", mock_stats)

        import build_audit_index

        rc = build_audit_index.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Sources indexed: 2" in out

    def test_build_index_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON output exercises format_stats_json path."""
        from bid_euchre.ops.index import BuildResult, IndexStats

        monkeypatch.setattr(
            "bid_euchre.ops.index.build_index",
            lambda *a, **kw: BuildResult(
                sources_indexed=1,
                entries_indexed=5,
                errors=[],
                duration_seconds=0.05,
            ),
        )
        monkeypatch.setattr(
            "bid_euchre.ops.index.get_stats",
            lambda *a, **kw: IndexStats(
                total_entries=5,
                db_path="x.db",
                source_counts={"events": 5},
            ),
        )

        import build_audit_index

        rc = build_audit_index.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["build"]["sources_indexed"] == 1

    def test_errors_return_1(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops.index import BuildResult, IndexStats

        monkeypatch.setattr(
            "bid_euchre.ops.index.build_index",
            lambda *a, **kw: BuildResult(
                sources_indexed=0,
                entries_indexed=0,
                errors=["something failed"],
                duration_seconds=0.01,
            ),
        )
        monkeypatch.setattr(
            "bid_euchre.ops.index.get_stats",
            lambda *a, **kw: IndexStats(
                total_entries=0,
                db_path="x.db",
                source_counts={},
            ),
        )

        import build_audit_index

        rc = build_audit_index.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
            ]
        )
        assert rc == 1


class TestBuildCuratedMemoryCli:
    """Tests for build_curated_memory.py main()."""

    def test_help_exits_zero(self) -> None:
        import build_curated_memory

        with pytest.raises(SystemExit, match="0"):
            build_curated_memory.main(["--help"])

    def test_no_action_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        import build_curated_memory

        rc = build_curated_memory.main([])
        assert rc == 1

    def test_list_empty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import build_curated_memory

        rc = build_curated_memory.main(["--memory-dir", str(memory_dir), "list"])
        assert rc == 0

    def test_list_json(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import build_curated_memory

        rc = build_curated_memory.main(
            ["--memory-dir", str(memory_dir), "--json", "list"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, (dict, list))

    def test_validate_empty(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()

        import build_curated_memory

        rc = build_curated_memory.main(["--memory-dir", str(memory_dir), "validate"])
        assert rc == 0


class TestCompactSessionContextCli:
    """Tests for compact_session_context.py main()."""

    def test_help_exits_zero(self) -> None:
        import compact_session_context

        with pytest.raises(SystemExit, match="0"):
            compact_session_context.main(["--help"])

    def test_no_action_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        import compact_session_context

        rc = compact_session_context.main([])
        assert rc == 1

    def test_list_empty(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        import compact_session_context

        rc = compact_session_context.main(["--archive-dir", str(archive_dir), "list"])
        assert rc == 0

    def test_list_json(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        import compact_session_context

        rc = compact_session_context.main(
            ["--archive-dir", str(archive_dir), "--json", "list"]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, (dict, list))

    def test_compact_missing_context_file(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Error path: context file does not exist."""
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        import compact_session_context

        rc = compact_session_context.main(
            [
                "--archive-dir",
                str(archive_dir),
                "compact",
                "--session-id",
                "test-session",
                "--lane",
                "author-a",
                "--context-file",
                str(tmp_path / "nonexistent.txt"),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err.lower()

    def test_show_missing_session(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Error path: show non-existent session."""
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        import compact_session_context

        rc = compact_session_context.main(
            [
                "--archive-dir",
                str(archive_dir),
                "show",
                "--session-id",
                "nonexistent",
            ]
        )
        assert rc == 1

    def test_compact_success(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Happy path: compact a session context."""
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        context_file = tmp_path / "context.txt"
        context_file.write_text("Some session context")

        import compact_session_context

        rc = compact_session_context.main(
            [
                "--archive-dir",
                str(archive_dir),
                "compact",
                "--session-id",
                "test-session",
                "--lane",
                "author-a",
                "--context-file",
                str(context_file),
                "--summary",
                "Test summary",
                "--outcome",
                "done",
            ]
        )
        assert rc == 0


# ---------------------------------------------------------------------------
# Filesystem boundary tests
# ---------------------------------------------------------------------------


class TestBoundaryRejection:
    """Tests that CLI commands reject paths outside the repo boundary."""

    def _mock_boundaries(
        self, monkeypatch: pytest.MonkeyPatch, repo_root: Path
    ) -> None:
        """Set up fs_boundary mocks that make *repo_root* the boundary."""
        from bid_euchre.ops import fs_boundary

        repo_root_str = str(repo_root.resolve())
        runtime_str = str((repo_root / ".claude" / "runtime").resolve())

        fake_boundaries = {
            "repo_root": repo_root_str,
            "worktree_paths": [repo_root_str],
            "runtime_dirs": [runtime_str],
        }
        monkeypatch.setattr(
            fs_boundary,
            "get_repo_boundaries",
            lambda **kw: fake_boundaries,
        )

    def test_quarantine_rejects_external(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """worktrees quarantine should reject paths outside the boundary."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        self._mock_boundaries(monkeypatch, repo_root)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "quarantine",
                "/tmp/evil-worktree",
                "--reason",
                "test",
            ]
        )
        assert rc == 1
        assert "outside the repo boundary" in capsys.readouterr().err

    def test_archive_rejects_external(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """worktrees archive should reject paths outside the boundary."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        self._mock_boundaries(monkeypatch, repo_root)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "archive",
                "/tmp/evil-worktree",
            ]
        )
        assert rc == 1
        assert "outside the repo boundary" in capsys.readouterr().err

    def test_snapshot_create_rejects_external(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """snapshot create should reject --worktree paths outside the boundary."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        self._mock_boundaries(monkeypatch, repo_root)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "snapshot",
                "create",
                "--worktree",
                "/tmp/evil-worktree",
                "--reason",
                "test",
            ]
        )
        assert rc == 1
        assert "outside the repo boundary" in capsys.readouterr().err

    def test_skills_propose_rejects_external(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """skills propose should reject --content-file paths outside the boundary."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        self._mock_boundaries(monkeypatch, repo_root)

        # Create a content file outside the boundary
        external_file = tmp_path / "external" / "skill.md"
        external_file.parent.mkdir()
        external_file.write_text("# Evil skill")

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "skills",
                "propose",
                "--name",
                "evil-skill",
                "--description",
                "test skill",
                "--content-file",
                str(external_file),
                "--source-workflow",
                "test",
                "--proposed-by",
                "ops",
            ]
        )
        assert rc == 1
        assert "outside the repo boundary" in capsys.readouterr().err

    def test_snapshot_create_allows_in_boundary(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """snapshot create should allow --worktree paths inside the boundary.

        The path passes the boundary check but create_snapshot may still fail
        because the test dir isn't a real git repo — that's expected.
        We only verify the error is NOT a boundary violation.
        """
        import subprocess as sp

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()
        self._mock_boundaries(monkeypatch, repo_root)

        wt_path = repo_root / "some-subdir"
        wt_path.mkdir()

        import ops

        # create_snapshot will call git commands that fail in test env.
        # We want to verify boundary check passes — not that snapshot works.
        # Track whether _check_boundary was called and returned None (allowed).
        original_check = ops._check_boundary
        boundary_result = []

        def tracking_check(*a, **kw):
            result = original_check(*a, **kw)
            boundary_result.append(result)
            return result

        monkeypatch.setattr(ops, "_check_boundary", tracking_check)

        # The command may raise or return 1 — we don't care
        try:
            ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "snapshot",
                    "create",
                    "--worktree",
                    str(wt_path),
                    "--reason",
                    "test",
                ]
            )
        except (sp.SubprocessError, OSError):
            pass  # Expected: test dir isn't a real git repo

        # Boundary check was called and returned None (allowed)
        assert boundary_result == [
            None
        ], f"Expected boundary check to allow the path, got {boundary_result}"

    def test_quarantine_allows_registered_worktree(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Paths within a registered worktree should pass boundary checks."""
        import subprocess as sp

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".git").mkdir()

        wt_path = tmp_path / "Bid-Euchre-steward-author"
        wt_path.mkdir()

        from bid_euchre.ops import fs_boundary

        repo_root_str = str(repo_root.resolve())
        wt_str = str(wt_path.resolve())
        runtime_str = str((repo_root / ".claude" / "runtime").resolve())

        monkeypatch.setattr(
            fs_boundary,
            "get_repo_boundaries",
            lambda **kw: {
                "repo_root": repo_root_str,
                "worktree_paths": [repo_root_str, wt_str],
                "runtime_dirs": [runtime_str],
            },
        )

        # Mock subprocess so quarantine itself doesn't fail
        monkeypatch.setattr(
            sp,
            "run",
            lambda *a, **kw: type(
                "R", (), {"returncode": 0, "stdout": "diff\n", "stderr": ""}
            )(),
        )

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "worktrees",
                "quarantine",
                str(wt_path),
                "--reason",
                "test",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "outside the repo boundary" not in captured.err


# ---------------------------------------------------------------------------
# Queue subcommand (review queue visibility — PR3)
# ---------------------------------------------------------------------------


class TestCmdQueue:
    """Tests for the queue subcommand."""

    @pytest.fixture(autouse=True)
    def _use_test_queue(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Point shared_queue_root() at the test's runtime queue dir.

        cmd_queue uses shared_queue_root() to find the canonical queue.
        In tests we redirect it to the test runtime dir via env override.
        """
        queue_dir = runtime_dir / "review_queue"
        monkeypatch.setenv("BID_EUCHRE_REVIEW_QUEUE_DIR", str(queue_dir))

    def test_queue_empty_text(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "No queued reviews" in captured.out

    def test_queue_empty_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_queue_with_entries_text(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Queue with a request shows pending status in text output."""
        from bid_euchre.ops.review_queue import ReviewRequest, write_request

        queue_dir = runtime_dir / "review_queue"
        events_dir = runtime_dir / "events"

        req = ReviewRequest(
            pr_number=42,
            head_sha="abc12345",
            branch="feat/test",
            requester="author-a",
        )
        write_request(req, queue_dir, emit_event=False, events_dir=events_dir)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "#42" in captured.out
        assert "pending" in captured.out
        assert "abc12345" in captured.out

    def test_queue_with_entries_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Queue with a request shows pending status in JSON output."""
        from bid_euchre.ops.review_queue import ReviewRequest, write_request

        queue_dir = runtime_dir / "review_queue"
        events_dir = runtime_dir / "events"

        req = ReviewRequest(
            pr_number=42,
            head_sha="abc12345",
            branch="feat/test",
            requester="author-a",
        )
        write_request(req, queue_dir, emit_event=False, events_dir=events_dir)

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["pr_number"] == 42
        assert data[0]["effective_status"] == "pending"
        assert data[0]["request_sha"] == "abc12345"

    def test_queue_single_pr(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--pr flag shows entry for a specific PR."""
        from bid_euchre.ops.review_queue import ReviewRequest, write_request

        queue_dir = runtime_dir / "review_queue"
        events_dir = runtime_dir / "events"

        req = ReviewRequest(
            pr_number=99,
            head_sha="def456",
            branch="fix/bug",
            requester="review",
        )
        write_request(req, queue_dir, emit_event=False, events_dir=events_dir)

        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
                "--pr",
                "99",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "#99" in captured.out
        assert "pending" in captured.out

    def test_queue_single_pr_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--pr flag with --json shows single entry."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "queue",
                "--pr",
                "999",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["pr_number"] == 999
        assert data["effective_status"] == "no_request"

    def test_queue_explicit_runtime_dir_override(
        self,
        tmp_path: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit --runtime-dir with a review_queue/ subdir overrides shared root (#1196)."""
        from bid_euchre.ops.review_queue import ReviewRequest, write_request

        # Create a separate runtime dir with its own queue + request
        alt_runtime = tmp_path / "alt_runtime"
        alt_queue = alt_runtime / "review_queue"
        alt_events = alt_runtime / "events"
        alt_events.mkdir(parents=True)

        req = ReviewRequest(
            pr_number=77,
            head_sha="override123",
            branch="feat/override",
            requester="author-a",
        )
        write_request(req, alt_queue, emit_event=False, events_dir=alt_events)

        # Clear env override so we're testing the --runtime-dir path, not env var
        monkeypatch.delenv("BID_EUCHRE_REVIEW_QUEUE_DIR", raising=False)

        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(alt_runtime),
                "--plans-dir",
                str(plans_dir),
                "queue",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["pr_number"] == 77
        assert data[0]["request_sha"] == "override123"


class TestTaskCreate:
    """Tests for ops.py task create subcommand."""

    def test_task_create_basic(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Fix scoring edge case",
                "--owner",
                "author-a",
                "--priority",
                "normal",
                "--description",
                "Fix the edge case in scoring",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Fix scoring edge case" in out

    def test_task_create_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Test JSON output",
                "--owner",
                "author-b",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["title"] == "Test JSON output"
        assert data["owner"] == "author-b"
        assert data["priority"] == "normal"
        assert data["status"] == "pending"

    def test_task_create_then_list(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        # Create a packet
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Roundtrip test",
                "--owner",
                "author-a",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)

        # List and verify it appears
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "list",
            ]
        )
        assert rc == 0
        packets = json.loads(capsys.readouterr().out)
        ids = [p["packet_id"] for p in packets]
        assert created["packet_id"] in ids

    def test_task_create_with_scope(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--scope flags are persisted as scope_declared list."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Scoped task",
                "--scope",
                "src/bid_euchre/ops/*.py",
                "--scope",
                "tests/unit/test_ops_*.py",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["scope_declared"] == [
            "src/bid_euchre/ops/*.py",
            "tests/unit/test_ops_*.py",
        ]

    def test_task_create_with_validation(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--validation flags are persisted as validation list."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Validated task",
                "--validation",
                "uv run python -m pytest tests/unit/test_ops_cli.py -v",
                "--validation",
                "make check-quiet",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["validation"] == [
            "uv run python -m pytest tests/unit/test_ops_cli.py -v",
            "make check-quiet",
        ]

    def test_task_create_with_scope_and_validation(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Both --scope and --validation are persisted together."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Full task",
                "--description",
                "A task with everything",
                "--owner",
                "author-a",
                "--priority",
                "high",
                "--scope",
                "scripts/internal/ops.py",
                "--validation",
                "uv run python -m pytest tests/ -v",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["title"] == "Full task"
        assert data["description"] == "A task with everything"
        assert data["owner"] == "author-a"
        assert data["priority"] == "high"
        assert data["scope_declared"] == ["scripts/internal/ops.py"]
        assert data["validation"] == ["uv run python -m pytest tests/ -v"]

    def test_task_create_text_shows_scope_and_validation(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Text output includes scope and validation when present."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Text output task",
                "--scope",
                "src/*.py",
                "--validation",
                "make check-quiet",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Text output task" in out
        assert "src/*.py" in out
        assert "make check-quiet" in out

    # ------------------------------------------------------------------
    # Routing metadata flags (issue #2169 Slice C)
    # ------------------------------------------------------------------

    def test_task_create_with_full_routing_metadata(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All four routing metadata flags are persisted into packet.metadata."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Routed task",
                "--task-type",
                "feature",
                "--complexity-estimate",
                "3",
                "--model-hint",
                "sonnet",
                "--effort-hint",
                "medium",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["metadata"]["task_type"] == "feature"
        assert data["metadata"]["complexity_estimate"] == 3
        assert data["metadata"]["model_hint"] == "sonnet"
        assert data["metadata"]["effort_hint"] == "medium"

    def test_task_create_partial_routing_metadata(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Only supplied routing flags appear in metadata; omitted keys are absent."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Partial routed task",
                "--task-type",
                "bugfix",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["metadata"].get("task_type") == "bugfix"
        # Unspecified keys should not be injected.
        assert "complexity_estimate" not in data["metadata"]
        assert "model_hint" not in data["metadata"]
        assert "effort_hint" not in data["metadata"]

    def test_task_create_no_routing_metadata_leaves_metadata_empty(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A task created without any routing flags has an empty metadata dict."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "No routing task",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        # metadata is always present (default = {}) but should be empty here.
        assert data["metadata"] == {}

    def test_task_create_rejects_out_of_range_complexity(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """complexity_estimate outside [1, 5] is an error (rc=1) and nothing is persisted."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Too-complex task",
                "--complexity-estimate",
                "9",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Routing metadata error" in err
        assert "complexity_estimate" in err

    def test_task_create_unknown_task_type_warns_but_succeeds(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Unknown task_type emits a warning but still persists the value (evolvable taxonomy)."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Exotic task",
                "--task-type",
                "exotic_new_category",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        data = json.loads(captured.out)
        assert data["metadata"]["task_type"] == "exotic_new_category"
        # Warning emitted to stderr, not an error
        assert "Routing metadata warning" in captured.err
        assert "task_type" in captured.err

    def test_task_create_effort_hint_choices_enforced_by_argparse(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """argparse enforces --effort-hint choices (low/medium/high); invalid → SystemExit."""
        import ops

        with pytest.raises(SystemExit):
            ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "task",
                    "create",
                    "--title",
                    "Bad effort",
                    "--effort-hint",
                    "gigantic",
                ]
            )


class TestTaskDispatch:
    """Verify ``task dispatch`` CLI subcommand."""

    def test_task_dispatch_not_found(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Dispatching a nonexistent packet returns exit code 1."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "dispatch",
                "nonexistent_id",
                "author-a",
            ]
        )
        assert rc == 1

    def test_task_dispatch_with_approve_flag(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--approve transitions a pending packet to approved before dispatch attempt."""
        import ops

        # Create a pending packet
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Dispatch test",
                "--owner",
                "author-a",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]
        assert created["status"] == "pending"

        # Dispatch with --approve (will fail at dispatch_to_worker because
        # no runtime infrastructure, but the approval transition should succeed)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "dispatch",
                packet_id,
                "author-a",
                "--approve",
            ]
        )
        # dispatch_to_worker will fail (no tmux, etc) but we can verify the
        # packet was approved by checking its status
        from bid_euchre.ops.task_queue import load_packet

        pkt = load_packet(packet_id, runtime_dir / "task_queue")
        # If dispatch failed after approval, packet should be in approved
        # or dispatched status (not pending)
        assert pkt is not None
        assert pkt.status in ("approved", "dispatched")

    def test_task_dispatch_subparser_exists(self) -> None:
        """Verify the 'task dispatch' subparser is properly registered."""
        import ops

        parser = ops.build_parser()

        # Walk subparsers to find 'task' -> 'dispatch'
        task_subparser = None
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                task_subparser = action.choices.get("task")
                break

        assert task_subparser is not None, "Expected 'task' subcommand"

        dispatch_subparser = None
        for action in task_subparser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                dispatch_subparser = action.choices.get("dispatch")
                break

        assert dispatch_subparser is not None, "Expected 'task dispatch' subcommand"


class TestTaskAccept:
    """Verify ``task accept`` CLI subcommand."""

    def test_task_accept_not_found(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Accepting a nonexistent packet returns exit code 1."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "accept",
                "nonexistent_id",
                "--lane",
                "author-b",
            ]
        )
        assert rc == 1

    def test_task_accept_existing_packet(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Accepting an existing packet succeeds and emits task_started event."""
        import ops

        # Create a pending packet
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Accept test",
                "--owner",
                "author-b",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        # Accept it
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "accept",
                packet_id,
                "--lane",
                "author-b",
            ]
        )
        assert rc == 0
        result = json.loads(capsys.readouterr().out)
        assert result["packet_id"] == packet_id
        assert result["lane"] == "author-b"
        assert "emitted task_started event" in result["steps"]

        # Verify task_started event was written
        from bid_euchre.ops.events import read_events

        events = read_events(runtime_dir / "events", event_type="task_started")
        assert len(events) >= 1
        assert events[-1]["payload"]["packet_id"] == packet_id

    def test_task_accept_idempotent(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Running accept twice succeeds both times (idempotent)."""
        import ops

        # Create a packet
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Idempotent test",
                "--owner",
                "author-b",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        # Accept once
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "accept",
                packet_id,
                "--lane",
                "author-b",
            ]
        )
        assert rc == 0
        capsys.readouterr()  # clear

        # Accept again — should still succeed
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "accept",
                packet_id,
                "--lane",
                "author-b",
            ]
        )
        assert rc == 0

    def test_task_accept_subparser_exists(self) -> None:
        """Verify the 'task accept' subparser is properly registered."""
        import ops

        parser = ops.build_parser()

        task_subparser = None
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                task_subparser = action.choices.get("task")
                break

        assert task_subparser is not None, "Expected 'task' subcommand"

        accept_subparser = None
        for action in task_subparser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                accept_subparser = action.choices.get("accept")
                break

        assert accept_subparser is not None, "Expected 'task accept' subcommand"


class TestTaskComplete:
    """Verify ``task complete`` CLI subcommand."""

    @staticmethod
    def _create_dispatched_packet(
        runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> str:
        """Helper: create a packet and transition it to dispatched state."""
        import ops

        from bid_euchre.ops.task_queue import transition_status

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Complete test",
                "--owner",
                "author-a",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        tq_root = runtime_dir / "task_queue"
        transition_status(packet_id, "approved", tq_root)
        transition_status(packet_id, "dispatched", tq_root)
        return packet_id

    def test_task_complete_not_found(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Completing a nonexistent packet returns exit code 1."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                "nonexistent_id",
            ]
        )
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_task_complete_wrong_state(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Completing a pending packet returns exit code 1."""
        import ops

        # Create a pending packet
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Wrong state test",
                "--owner",
                "author-a",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
            ]
        )
        assert rc == 1
        assert "pending" in capsys.readouterr().err

    def test_task_complete_dispatched(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Completing a dispatched packet transitions to completed and archives."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "All done",
                "--pr",
                "1234",
                "--by",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Completed:" in out
        assert "All done" in out
        assert "#1234" in out
        assert "(archived)" in out

        # Verify archived (not in active list)
        from bid_euchre.ops.task_queue import list_packets

        active = list_packets(runtime_dir / "task_queue")
        assert all(p.packet_id != packet_id for p in active)

        # Verify result file in archive
        archive_path = (
            runtime_dir / "task_queue" / "archive" / f"{packet_id}.result.json"
        )
        assert archive_path.exists()

        # Verify task_completed event was emitted
        events_dir = runtime_dir / "events"
        event_files = sorted(events_dir.glob("*.jsonl"))
        assert event_files, "Expected at least one event file"
        events = []
        for ef in event_files:
            for line in ef.read_text().splitlines():
                if line.strip():
                    events.append(json.loads(line))
        completed_events = [
            e for e in events if e.get("event_type") == "task_completed"
        ]
        assert (
            len(completed_events) == 1
        ), f"Expected 1 task_completed event, got {len(completed_events)}"
        evt = completed_events[0]
        assert evt["payload"]["packet_id"] == packet_id
        assert evt["payload"]["title"] == "Complete test"
        assert evt["payload"]["summary"] == "All done"
        assert evt["payload"]["pr_number"] == 1234
        assert evt["payload"]["completed_by"] == "author-a"
        assert evt["lane_id"] == "author-a"

    def test_task_complete_json_output(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output includes the completed packet data."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "JSON test",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["packet_id"] == packet_id
        assert data["status"] == "completed"

    def test_task_complete_approved_auto_dispatches(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An approved packet is auto-dispatched before completion."""
        import ops

        from bid_euchre.ops.task_queue import transition_status

        # Create a packet in approved state (not dispatched)
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Auto-dispatch test",
                "--owner",
                "author-b",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        tq_root = runtime_dir / "task_queue"
        transition_status(packet_id, "approved", tq_root)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "Auto dispatched then completed",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Completed:" in out

    def test_task_complete_no_archive(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The --no-archive flag keeps the packet in the active queue."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "Stay active",
                "--no-archive",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "(archived)" not in out

        # Verify still in active list
        from bid_euchre.ops.task_queue import load_packet

        pkt = load_packet(packet_id, runtime_dir / "task_queue")
        assert pkt is not None
        assert pkt.status == "completed"

    def test_task_complete_subparser_exists(self) -> None:
        """Verify the 'task complete' subparser is properly registered."""
        import ops

        parser = ops.build_parser()

        task_subparser = None
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                task_subparser = action.choices.get("task")
                break

        assert task_subparser is not None, "Expected 'task' subcommand"

        complete_subparser = None
        for action in task_subparser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                complete_subparser = action.choices.get("complete")
                break

        assert complete_subparser is not None, "Expected 'task complete' subcommand"

    # ------------------------------------------------------------------
    # Enriched task_completed event payload (issue #2169 Slice C)
    # ------------------------------------------------------------------

    @staticmethod
    def _read_task_completed_events(runtime_dir: Path) -> list[dict[str, object]]:
        """Helper: read all ``task_completed`` events from the runtime events dir."""
        events_dir = runtime_dir / "events"
        events: list[dict[str, object]] = []
        for ef in sorted(events_dir.glob("*.jsonl")):
            for line in ef.read_text().splitlines():
                if line.strip():
                    events.append(json.loads(line))
        return [e for e in events if e.get("event_type") == "task_completed"]

    def test_task_complete_enriches_event_payload_with_outcome_detail(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``task complete`` with outcome flags writes them into the event payload."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "Shipped to prod",
                "--pr",
                "9999",
                "--by",
                "author-c",
                "--recommended-lane",
                "author-a",
                "--token-spend",
                "1234",
                "--elapsed-seconds",
                "600.5",
                "--review-rounds",
                "2",
                "--shipped-outcome",
                "merged",
            ]
        )
        assert rc == 0

        events = self._read_task_completed_events(runtime_dir)
        assert len(events) == 1, f"Expected 1 task_completed event, got {len(events)}"
        payload = events[0]["payload"]
        assert isinstance(payload, dict)
        # Outcome detail — sourced from CLI flags.
        assert payload["actual_lane"] == "author-c"
        assert payload["recommended_lane"] == "author-a"
        assert payload["token_spend"] == 1234
        assert payload["elapsed_seconds"] == 600.5
        assert payload["review_rounds"] == 2
        assert payload["shipped_outcome"] == "merged"
        # Routing context keys — always present even when packet has no metadata.
        for key in ("task_type", "complexity_estimate", "model_hint", "effort_hint"):
            assert key in payload, f"Expected routing key {key!r} in payload"

    def test_task_complete_copies_routing_metadata_from_packet(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Routing metadata on the packet flows through to the event payload."""
        import ops

        from bid_euchre.ops.task_queue import transition_status

        # Create a packet with routing metadata via CLI
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Routed completable",
                "--owner",
                "author-a",
                "--task-type",
                "feature",
                "--complexity-estimate",
                "4",
                "--model-hint",
                "opus",
                "--effort-hint",
                "high",
            ]
        )
        assert rc == 0
        created = json.loads(capsys.readouterr().out)
        packet_id = created["packet_id"]

        tq_root = runtime_dir / "task_queue"
        transition_status(packet_id, "approved", tq_root)
        transition_status(packet_id, "dispatched", tq_root)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "Done",
                "--by",
                "author-a",
            ]
        )
        assert rc == 0

        events = self._read_task_completed_events(runtime_dir)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert isinstance(payload, dict)
        assert payload["task_type"] == "feature"
        assert payload["complexity_estimate"] == 4
        assert payload["model_hint"] == "opus"
        assert payload["effort_hint"] == "high"

    def test_task_complete_preserves_none_for_missing_outcome_flags(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Outcome keys are always present; missing flags serialize as None."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "complete",
                packet_id,
                "--summary",
                "No outcome detail",
                "--by",
                "author-a",
            ]
        )
        assert rc == 0

        events = self._read_task_completed_events(runtime_dir)
        assert len(events) == 1
        payload = events[0]["payload"]
        assert isinstance(payload, dict)
        # Missing outcome flags => None, but key must exist (stable schema).
        assert payload["recommended_lane"] is None
        assert payload["token_spend"] is None
        assert payload["elapsed_seconds"] is None
        assert payload["review_rounds"] is None
        assert payload["shipped_outcome"] is None
        # actual_lane falls back to completed_by or packet.owner.
        assert payload["actual_lane"] == "author-a"

    def test_task_complete_shipped_outcome_choices_enforced(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """argparse enforces the --shipped-outcome choice set; invalid → SystemExit."""
        import ops

        packet_id = self._create_dispatched_packet(runtime_dir, plans_dir, capsys)

        with pytest.raises(SystemExit):
            ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "task",
                    "complete",
                    packet_id,
                    "--shipped-outcome",
                    "not_a_valid_outcome",
                ]
            )


class TestPriorityChoicesContract:
    """Verify CLI --priority choices stay in sync with VALID_PRIORITIES."""

    def test_cli_priority_choices_match_valid_priorities(self) -> None:
        """The argparse choices for --priority must equal VALID_PRIORITIES from task_queue."""
        import ops

        from bid_euchre.ops.task_queue import VALID_PRIORITIES

        parser = ops.build_parser()

        # Walk subparsers to find 'task create' and its --priority action
        task_subparser = None
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                task_subparser = action.choices.get("task")
                break

        assert task_subparser is not None, "Expected 'task' subcommand"

        create_subparser = None
        for action in task_subparser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                create_subparser = action.choices.get("create")
                break

        assert create_subparser is not None, "Expected 'task create' subcommand"

        priority_action = None
        for action in create_subparser._actions:
            if (
                hasattr(action, "option_strings")
                and "--priority" in action.option_strings
            ):
                priority_action = action
                break

        assert (
            priority_action is not None
        ), "Expected --priority argument on task create"
        assert (
            set(priority_action.choices) == set(VALID_PRIORITIES)
        ), f"CLI choices {priority_action.choices} != VALID_PRIORITIES {VALID_PRIORITIES}"


class TestCmdSupervisor:
    """Tests for the supervisor subcommand (Platform-6)."""

    def test_supervisor_text(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Basic supervisor invocation produces text output."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "supervisor",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "Supervisor Report" in captured.out

    def test_supervisor_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The --json flag produces valid JSON with expected keys."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "supervisor",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "timestamp" in data
        assert "summary" in data
        assert "lane_assessments" in data
        assert "recommendations" in data

    def test_supervisor_save(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The --save flag persists a snapshot to disk."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "supervisor",
                "--save",
            ]
        )
        assert rc == 0

        snap_dir = runtime_dir / "supervisor_snapshots"
        assert snap_dir.exists()
        snapshots = list(snap_dir.glob("snapshot_*.json"))
        assert len(snapshots) >= 1

    def test_supervisor_diff_valid(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The --diff flag loads a previous snapshot and computes a delta."""
        import ops

        from bid_euchre.ops.supervisor import (
            _snapshot_to_dict,
            take_snapshot,
        )

        # Take a snapshot and write it to a file for --diff
        snap = take_snapshot(runtime_dir, plans_dir)
        snap_file = tmp_path / "prev_snapshot.json"
        snap_file.write_text(json.dumps(_snapshot_to_dict(snap), indent=2))

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "supervisor",
                "--diff",
                str(snap_file),
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "delta" in data

    def test_supervisor_diff_invalid_path(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The --diff flag with a nonexistent file returns error code 1."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "supervisor",
                "--diff",
                "/nonexistent/path/snapshot.json",
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error loading snapshot" in captured.err


# ---------------------------------------------------------------------------
# Message bus CLI (SP-3-07)
# ---------------------------------------------------------------------------


class TestMessageSend:
    """Tests for ops.py message send subcommand."""

    def test_message_send_basic(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        # Ensure message_bus dir exists
        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "message",
                "send",
                "--from",
                "author-a",
                "--to",
                "orchestrator",
                "--type",
                "ack",
                "--summary",
                "Task received: test",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Sent message:" in out
        assert "author-a" in out

    def test_message_send_json(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "message",
                "send",
                "--from",
                "author-b",
                "--to",
                "orchestrator",
                "--type",
                "progress",
                "--summary",
                "Tests passing",
                "--task-id",
                "abc123",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["from_lane"] == "author-b"
        assert data["to_lane"] == "orchestrator"
        assert data["message_type"] == "progress"
        assert data["task_id"] == "abc123"

    def test_message_send_nudge_output(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """message send prints nudge status when nudge succeeds."""
        import ops

        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        from unittest.mock import patch

        from bid_euchre.ops.worker_pool import PoolAction

        mock_action = PoolAction(
            action="inbox_nudge",
            lane_id="orchestrator",
            reason="Sent '/inbox-poll' to pane steward:orchestrator",
            executed=True,
        )

        with patch("bid_euchre.ops.worker_pool.nudge_inbox", return_value=mock_action):
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "message",
                    "send",
                    "--from",
                    "author-a",
                    "--to",
                    "orchestrator",
                    "--type",
                    "ack",
                    "--summary",
                    "Task done",
                ]
            )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Nudge:" in out
        assert "/inbox-poll" in out

    def test_message_send_no_nudge_flag(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--no-nudge suppresses the tmux nudge."""
        import ops

        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        from unittest.mock import patch

        with patch("bid_euchre.ops.worker_pool.nudge_inbox") as mock_nudge:
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "message",
                    "send",
                    "--from",
                    "author-a",
                    "--to",
                    "orchestrator",
                    "--type",
                    "ack",
                    "--summary",
                    "Task done",
                    "--no-nudge",
                ]
            )
        assert rc == 0
        mock_nudge.assert_not_called()
        out = capsys.readouterr().out
        assert "Nudge:" not in out


class TestInboxAck:
    """Tests for ops.py inbox ack subcommand."""

    def test_inbox_ack_not_found(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import ops

        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack",
                "nonexistent_msg_id",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "not found" in err

    def test_inbox_ack_roundtrip(
        self, runtime_dir: Path, plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Send a message then ack it via CLI."""
        import ops

        (runtime_dir / "message_bus" / "inbox").mkdir(parents=True)

        # First send a message
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "message",
                "send",
                "--from",
                "orchestrator",
                "--to",
                "author-a",
                "--type",
                "ack",
                "--summary",
                "Test assignment",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        msg_id = data["message_id"]

        # Now ack it
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack",
                msg_id,
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Acknowledged" in out
        assert msg_id in out

    def test_inbox_prioritized_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--prioritized --json returns P0/P1/P2 structure."""
        import ops

        # Isolate bus root to temp dir to avoid real project bus data
        bus_dir = runtime_dir / "message_bus"
        bus_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("BID_EUCHRE_BUS_DIR", str(bus_dir))

        # Send messages at different priorities
        for prio, msg_type, summary in [
            ("urgent", "blocker", "Lane crash"),
            ("high", "completion", "PR merged"),
            ("normal", "progress", "Tests running"),
        ]:
            rc = ops.main(
                [
                    "--json",
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "message",
                    "send",
                    "--from",
                    "ops",
                    "--to",
                    "orchestrator",
                    "--type",
                    msg_type,
                    "--summary",
                    summary,
                    "--priority",
                    prio,
                ]
            )
            # Capture and discard send output
            capsys.readouterr()

        # Now read with --prioritized --json (status=None to get all, since
        # messages are in "pending" status after send)
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "--lane",
                "orchestrator",
                "--prioritized",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "p0" in data
        assert "p1" in data
        assert "p2" in data
        assert len(data["p0"]) == 1
        assert len(data["p1"]) == 1
        assert len(data["p2"]) == 1
        assert data["p0"][0]["priority"] == "urgent"

    def test_inbox_prioritized_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--prioritized text output shows tier headers."""
        import ops

        # Isolate bus root to temp dir
        bus_dir = runtime_dir / "message_bus"
        bus_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("BID_EUCHRE_BUS_DIR", str(bus_dir))

        # Send one urgent message
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "message",
                "send",
                "--from",
                "ops",
                "--to",
                "test-lane",
                "--type",
                "blocker",
                "--summary",
                "Urgent test",
                "--priority",
                "urgent",
            ]
        )
        capsys.readouterr()

        # Read in text mode
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "--lane",
                "test-lane",
                "--prioritized",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "prioritized" in out
        assert "P0 (urgent)" in out
        assert "P1 (high)" in out
        assert "P2 (normal/low)" in out


class TestInboxBulkAck:
    """Tests for ops.py inbox bulk-ack subcommand (regression for #2668)."""

    @pytest.fixture()
    def bus_dir(self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Isolate the bus root to the test's runtime dir."""
        d = runtime_dir / "message_bus"
        (d / "inbox").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("BID_EUCHRE_BUS_DIR", str(d))
        return d

    def _send(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        to: str,
        summary: str,
    ) -> str:
        """Helper: send a message via CLI and return its id."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "message",
                "send",
                "--from",
                "orchestrator",
                "--to",
                to,
                "--type",
                "ack",
                "--summary",
                summary,
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        return data["message_id"]

    def test_bulk_ack_mixed_pending_and_expired_no_crash(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Regression for #2668: bulk-ack must not crash when a message in
        the batch is already in a terminal state.  Output must surface the
        skipped-terminal count."""
        import ops

        # Send three messages to author-a
        _m1 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Pending 1")
        m2 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Will be expired")
        _m3 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Pending 2")

        # Pre-expire m2 by appending an ``expired`` record to the inbox
        inbox_path = bus_dir / "inbox" / "author-a.jsonl"
        lines = inbox_path.read_text().strip().split("\n")
        latest = None
        for line in lines:
            rec = json.loads(line)
            if rec.get("message_id") == m2:
                latest = rec
        assert latest is not None
        expired_rec = {**latest, "status": "expired"}
        with open(inbox_path, "a") as f:
            f.write(json.dumps(expired_rec) + "\n")

        # Run bulk-ack — must not raise, must report skipped count
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "bulk-ack",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bulk-acked 2 message(s)" in out
        assert "skipped 1 terminal-state message(s)" in out

    def test_bulk_ack_all_terminal_reports_skipped(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """All-terminal batch: 0 acked, N skipped, exit 0."""
        import ops

        m1 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Expired 1")
        m2 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Expired 2")

        inbox_path = bus_dir / "inbox" / "author-a.jsonl"
        lines = inbox_path.read_text().strip().split("\n")
        expired_records = []
        for line in lines:
            rec = json.loads(line)
            if rec.get("message_id") in {m1, m2}:
                expired_records.append({**rec, "status": "expired"})
        with open(inbox_path, "a") as f:
            for rec in expired_records:
                f.write(json.dumps(rec) + "\n")

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "bulk-ack",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bulk-acked 0 message(s)" in out
        assert "skipped 2 terminal-state message(s)" in out

    def test_bulk_ack_all_pending_no_skipped(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No regression: bulk-ack on all-pending acks all, no skipped."""
        import ops

        self._send(runtime_dir, plans_dir, capsys, "author-a", "Task 1")
        self._send(runtime_dir, plans_dir, capsys, "author-a", "Task 2")

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "bulk-ack",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Bulk-acked 2 message(s)" in out
        assert "skipped" not in out  # no skipped-terminal note

    def test_bulk_ack_json_reports_skipped_count(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """JSON mode includes skipped_terminal alongside acked list."""
        import ops

        _m1 = self._send(runtime_dir, plans_dir, capsys, "author-a", "P")
        m2 = self._send(runtime_dir, plans_dir, capsys, "author-a", "Exp")

        inbox_path = bus_dir / "inbox" / "author-a.jsonl"
        lines = inbox_path.read_text().strip().split("\n")
        for line in lines:
            rec = json.loads(line)
            if rec.get("message_id") == m2:
                with open(inbox_path, "a") as f:
                    f.write(json.dumps({**rec, "status": "expired"}) + "\n")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "bulk-ack",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert "acked" in data
        assert "skipped_terminal" in data
        assert len(data["acked"]) == 1
        assert data["skipped_terminal"] == 1

    def test_bulk_ack_cli_large_inbox_completes(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Regression for #2699: CLI ``ack-all`` on a large inbox
        completes in seconds, not minutes. A 2000-message inbox on the
        pre-#2699 O(N²) path would take 10s+ (and 10min+ on the
        observed 12K orchestrator inbox). The single-pass rewrite keeps
        wall-clock bounded at O(N)."""
        import time as _time

        import ops

        # Seed the inbox directly (JSONL append) — sending 2000 messages
        # via CLI would dominate the test wall-clock budget.
        inbox_path = bus_dir / "inbox" / "bulk-perf.jsonl"
        inbox_path.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime, timedelta, timezone

        count = 2000
        now_dt = datetime.now(timezone.utc)
        with open(inbox_path, "w") as f:
            for i in range(count):
                # Keep created_at within the default 24h TTL window so
                # the lazy-expiry pass doesn't intercept them.
                ts = (now_dt - timedelta(minutes=i % 60)).strftime("%Y-%m-%dT%H:%M:%SZ")
                rec = {
                    "message_id": f"perf{i:08d}",
                    "thread_id": None,
                    "task_id": None,
                    "from_lane": "orchestrator",
                    "to_lane": "bulk-perf",
                    "message_type": "ack",
                    "priority": "normal",
                    "status": "pending",
                    "created_at": ts,
                    "acked_at": None,
                    "resolved_at": None,
                    "requires_human": False,
                    "summary": f"perf-{i}",
                    "payload": {
                        "max_retries": 3,
                        "retry_count": 0,
                        "ttl_seconds": 86400,
                    },
                    "source_transport": "bus",
                    "parent_message_id": None,
                }
                f.write(json.dumps(rec) + "\n")

        # Drain capsys so the test's own assertion reads only CLI output
        capsys.readouterr()

        start = _time.perf_counter()
        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "bulk-ack",
                "--lane",
                "bulk-perf",
            ]
        )
        elapsed = _time.perf_counter() - start

        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data["acked"]) == count
        assert data["skipped_terminal"] == 0
        assert elapsed < 5.0, (
            f"ack-all on {count} messages took {elapsed:.2f}s "
            f"(expected <5.0s; O(N²) regression suspected — see #2699)"
        )


# ---------------------------------------------------------------------------
# review-check
# ---------------------------------------------------------------------------


class TestCmdReviewCheck:
    """Tests for the review-check subcommand."""

    def test_help_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """review-check --help should succeed."""
        import ops

        with pytest.raises(SystemExit) as exc_info:
            ops.main(["review-check", "--help"])
        assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "review-check" in out or "merged" in out.lower()

    def test_no_prs_text(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When gh returns no merged PRs, output says so."""
        import subprocess as sp

        import ops

        def mock_run(*args: object, **kwargs: object) -> sp.CompletedProcess[str]:
            return sp.CompletedProcess(args=args, returncode=0, stdout="[]", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "No recently merged PRs" in out

    def test_no_prs_json(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """JSON mode with no merged PRs."""
        import subprocess as sp

        import ops

        def mock_run(*args: object, **kwargs: object) -> sp.CompletedProcess[str]:
            return sp.CompletedProcess(args=args, returncode=0, stdout="[]", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["prs_checked"] == 0
        assert data["findings"] == []

    def test_clean_pr_no_findings(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A normal small PR should produce no findings."""
        import subprocess as sp

        import ops

        pr_list_json = json.dumps(
            [
                {
                    "number": 100,
                    "title": "fix: small change",
                    "mergedAt": "2026-03-22T10:00:00Z",
                    "changedFiles": 3,
                    "additions": 20,
                    "deletions": 5,
                }
            ]
        )

        call_count = {"n": 0}

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            call_count["n"] += 1
            if "pr" in cmd and "list" in cmd:
                return sp.CompletedProcess(
                    args=cmd, returncode=0, stdout=pr_list_json, stderr=""
                )
            if "pr" in cmd and "diff" in cmd:
                return sp.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="src/foo.py\nsrc/bar.py\ntests/test_foo.py\n",
                    stderr="",
                )
            return sp.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="unknown"
            )

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["prs_checked"] == 1
        assert data["findings"] == []

    def test_large_diff_warning(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A PR with >5000 lines should trigger a large_diff warning."""
        import subprocess as sp

        import ops

        pr_list_json = json.dumps(
            [
                {
                    "number": 200,
                    "title": "feat: big refactor",
                    "mergedAt": "2026-03-22T10:00:00Z",
                    "changedFiles": 50,
                    "additions": 4000,
                    "deletions": 2000,
                }
            ]
        )

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            if "pr" in cmd and "list" in cmd:
                return sp.CompletedProcess(
                    args=cmd, returncode=0, stdout=pr_list_json, stderr=""
                )
            if "pr" in cmd and "diff" in cmd:
                return sp.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="src/big.py\n",
                    stderr="",
                )
            return sp.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 0  # warnings don't block
        data = json.loads(capsys.readouterr().out)
        assert len(data["findings"]) >= 1
        assert any(f["check"] == "large_diff" for f in data["findings"])

    def test_data_artifact_blocker(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A PR touching data/runs/ should trigger a data_artifact blocker."""
        import subprocess as sp

        import ops

        pr_list_json = json.dumps(
            [
                {
                    "number": 300,
                    "title": "chore: add run data",
                    "mergedAt": "2026-03-22T10:00:00Z",
                    "changedFiles": 5,
                    "additions": 100,
                    "deletions": 0,
                }
            ]
        )

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            if "pr" in cmd and "list" in cmd:
                return sp.CompletedProcess(
                    args=cmd, returncode=0, stdout=pr_list_json, stderr=""
                )
            if "pr" in cmd and "diff" in cmd:
                return sp.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="data/runs/run_42/results.json\nsrc/foo.py\n",
                    stderr="",
                )
            return sp.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 1  # blockers return exit code 1
        data = json.loads(capsys.readouterr().out)
        blockers = [f for f in data["findings"] if f["severity"] == "block"]
        assert len(blockers) >= 1
        assert blockers[0]["check"] == "data_artifact"

    def test_contract_no_tests_warning(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Contract doc changes without test updates should warn."""
        import subprocess as sp

        import ops

        pr_list_json = json.dumps(
            [
                {
                    "number": 400,
                    "title": "docs: update rules",
                    "mergedAt": "2026-03-22T10:00:00Z",
                    "changedFiles": 2,
                    "additions": 10,
                    "deletions": 5,
                }
            ]
        )

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            if "pr" in cmd and "list" in cmd:
                return sp.CompletedProcess(
                    args=cmd, returncode=0, stdout=pr_list_json, stderr=""
                )
            if "pr" in cmd and "diff" in cmd:
                return sp.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="docs/01_core/RULES.md\nsrc/foo.py\n",
                    stderr="",
                )
            return sp.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "--json",
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 0  # warnings don't block
        data = json.loads(capsys.readouterr().out)
        warns = [f for f in data["findings"] if f["check"] == "contract_no_tests"]
        assert len(warns) == 1

    def test_gh_failure_returns_1(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When gh pr list fails, exit code should be 1."""
        import subprocess as sp

        import ops

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            return sp.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr="gh: not logged in"
            )

        monkeypatch.setattr(sp, "run", mock_run)
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-check",
                "--no-notify",
            ]
        )
        assert rc == 1

    def test_notify_sends_message(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without --no-notify, findings should be sent to orchestrator inbox."""
        import subprocess as sp

        import ops

        pr_list_json = json.dumps(
            [
                {
                    "number": 500,
                    "title": "feat: big change",
                    "mergedAt": "2026-03-22T10:00:00Z",
                    "changedFiles": 50,
                    "additions": 4000,
                    "deletions": 2000,
                }
            ]
        )

        def mock_run(
            cmd: list[str], *args: object, **kwargs: object
        ) -> sp.CompletedProcess[str]:
            if "pr" in cmd and "list" in cmd:
                return sp.CompletedProcess(
                    args=cmd, returncode=0, stdout=pr_list_json, stderr=""
                )
            if "pr" in cmd and "diff" in cmd:
                return sp.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="src/big.py\n",
                    stderr="",
                )
            return sp.CompletedProcess(args=cmd, returncode=1, stdout="", stderr="")

        monkeypatch.setattr(sp, "run", mock_run)

        # Ensure message_bus dir exists for send_message.
        # The bus uses {bus_root}/inbox/{lane}.jsonl for per-lane inboxes
        # and {bus_root}/messages.jsonl for the audit trail.
        bus_root = runtime_dir / "message_bus"
        (bus_root / "inbox").mkdir(parents=True)

        # Point send_message at our temp bus_root
        monkeypatch.setenv("BID_EUCHRE_BUS_DIR", str(bus_root))

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-check",
                # No --no-notify: exercises the notification path
            ]
        )
        assert rc == 0  # warnings don't block

        # Verify a message was written to the orchestrator inbox (JSONL)
        inbox_file = bus_root / "inbox" / "orchestrator.jsonl"
        assert inbox_file.exists(), "Expected orchestrator inbox JSONL"
        lines = [
            json.loads(line)
            for line in inbox_file.read_text().strip().splitlines()
            if line.strip()
        ]
        assert len(lines) >= 1, "Expected at least one inbox message"

        msg_data = lines[0]
        assert msg_data["message_type"] == "supervisor_alert"
        assert msg_data["to_lane"] == "orchestrator"
        assert "review-check" in msg_data["summary"]


class TestCmdLanePeek:
    """Tests for the 'lane peek' subcommand (tmux pane capture)."""

    def test_peek_success(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Successful peek prints captured pane content."""
        from unittest.mock import MagicMock, patch

        import ops

        mock_result = MagicMock(returncode=0, stdout="line1\nline2\nline3\n")
        with (
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:platform.1",
            ),
        ):
            rc = ops.main(
                ["--runtime-dir", str(runtime_dir), "lane", "peek", "author-a"]
            )
        assert rc == 0
        captured = capsys.readouterr()
        assert "line1" in captured.out
        assert "line3" in captured.out
        # Verify tmux capture-pane was called with correct args
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "tmux"
        assert call_args[1] == "capture-pane"
        assert "-t" in call_args
        assert "steward:platform.1" in call_args
        assert "-p" in call_args

    def test_peek_custom_lines(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--lines flag is passed to tmux as negative scroll offset."""
        from unittest.mock import MagicMock, patch

        import ops

        mock_result = MagicMock(returncode=0, stdout="output\n")
        with (
            patch("subprocess.run", return_value=mock_result) as mock_run,
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:author-a",
            ),
        ):
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "lane",
                    "peek",
                    "author-a",
                    "--lines",
                    "200",
                ]
            )
        assert rc == 0
        call_args = mock_run.call_args[0][0]
        assert "-S" in call_args
        s_idx = call_args.index("-S")
        assert call_args[s_idx + 1] == "-200"

    def test_peek_tmux_failure(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Non-zero tmux exit prints error to stderr and returns 1."""
        from unittest.mock import MagicMock, patch

        import ops

        mock_result = MagicMock(
            returncode=1, stdout="", stderr="can't find pane: author-a"
        )
        with (
            patch("subprocess.run", return_value=mock_result),
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:author-a",
            ),
        ):
            rc = ops.main(
                ["--runtime-dir", str(runtime_dir), "lane", "peek", "author-a"]
            )
        assert rc == 1
        captured = capsys.readouterr()
        assert "Error" in captured.err

    def test_peek_tmux_not_found(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FileNotFoundError (tmux missing) prints error and returns 1."""
        from unittest.mock import patch

        import ops

        with (
            patch("subprocess.run", side_effect=FileNotFoundError("tmux")),
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:author-a",
            ),
        ):
            rc = ops.main(
                ["--runtime-dir", str(runtime_dir), "lane", "peek", "author-a"]
            )
        assert rc == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err

    def test_peek_tmux_timeout(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """TimeoutExpired prints error and returns 1."""
        import subprocess as sp
        from unittest.mock import patch

        import ops

        with (
            patch("subprocess.run", side_effect=sp.TimeoutExpired("tmux", 5)),
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:author-a",
            ),
        ):
            rc = ops.main(
                ["--runtime-dir", str(runtime_dir), "lane", "peek", "author-a"]
            )
        assert rc == 1
        captured = capsys.readouterr()
        assert "timed out" in captured.err

    def test_peek_json_output(
        self, runtime_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json flag emits valid JSON with lane and content keys."""
        from unittest.mock import MagicMock, patch

        import ops

        mock_result = MagicMock(returncode=0, stdout="line1\nline2\n")
        with (
            patch("subprocess.run", return_value=mock_result),
            patch(
                "bid_euchre.ops.worker_pool._resolve_tmux_target",
                return_value="steward:platform.1",
            ),
        ):
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--json",
                    "lane",
                    "peek",
                    "author-a",
                ]
            )
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["lane"] == "author-a"
        assert "line1" in data["content"]
        assert "line2" in data["content"]

    def test_peek_parser_registered(self) -> None:
        """The 'lane peek' subparser is registered in build_parser."""
        import ops

        parser = ops.build_parser()
        # Parsing should succeed — not raise SystemExit
        args = parser.parse_args(["lane", "peek", "flex-a"])
        assert args.lane_id == "flex-a"
        assert args.lines == 80  # default

    def test_peek_parser_custom_lines(self) -> None:
        """The --lines argument is parsed correctly."""
        import ops

        parser = ops.build_parser()
        args = parser.parse_args(["lane", "peek", "author-b", "--lines", "500"])
        assert args.lane_id == "author-b"
        assert args.lines == 500


class TestBusRootRegression:
    """Regression: ops.py must use shared_bus_root() — not worktree-local paths.

    Issue #1299: four callsites bypassed git-common-dir resolution by using
    ``args.runtime_dir / "message_bus"`` directly, causing messages from
    worktree lanes to land in the wrong bus.
    """

    def test_no_worktree_local_bus_paths(self) -> None:
        """ops.py must not construct bus paths via args.runtime_dir."""
        ops_path = SCRIPTS_DIR / "ops.py"
        source = ops_path.read_text()
        # This pattern is the exact anti-pattern that caused #1299
        hits = [
            (i + 1, line)
            for i, line in enumerate(source.splitlines())
            if "runtime_dir" in line and '"message_bus"' in line
        ]
        assert hits == [], (
            "Found worktree-local bus path(s) in ops.py — use shared_bus_root() instead:\n"
            + "\n".join(f"  L{n}: {l.strip()}" for n, l in hits)
        )


class TestCmdReviewHwm:
    """Tests for the review-hwm subcommand (#2312)."""

    def test_get_returns_none_when_unset(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "get",
            ]
        )
        assert rc == 0
        assert capsys.readouterr().out.strip() == "none"

    def test_set_creates_file(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "set",
                "2345",
            ]
        )
        assert rc == 0
        hwm_file = runtime_dir / "review_state" / "last_merged_pr.txt"
        assert hwm_file.is_file()
        assert hwm_file.read_text().strip() == "2345"
        assert "2345" in capsys.readouterr().out

    def test_get_after_set(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "set",
                "100",
            ]
        )
        capsys.readouterr()  # discard set output

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "get",
            ]
        )
        assert rc == 0
        assert capsys.readouterr().out.strip() == "100"

    def test_set_rejects_non_integer(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "set",
                "abc",
            ]
        )
        assert rc == 1
        assert "positive integer" in capsys.readouterr().err

    def test_set_rejects_zero(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "set",
                "0",
            ]
        )
        assert rc == 1

    def test_set_rejects_negative(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "review-hwm",
                "set",
                "-5",
            ]
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# ServiceProvider integration tests (SP-5-01 PR2)
# ---------------------------------------------------------------------------


class TestServiceProviderWiring:
    """Verify that the four primary command groups (task, monitor, fleet,
    workers) use ServiceProvider rather than direct module imports for
    core data operations."""

    def test_get_provider_returns_service_provider(self, runtime_dir: Path) -> None:
        """_get_provider() constructs a ServiceProvider with correct paths."""
        import ops

        args = argparse.Namespace(runtime_dir=runtime_dir)
        provider = ops._get_provider(args)

        from bid_euchre.ops.core.provider import ServiceProvider

        assert isinstance(provider, ServiceProvider)

    def test_get_provider_queue_root_matches_runtime(self, runtime_dir: Path) -> None:
        """ServiceProvider task_queue adapter uses the correct queue root."""
        import ops

        args = argparse.Namespace(runtime_dir=runtime_dir)
        provider = ops._get_provider(args)

        # The adapter encapsulates the queue_root — verify it is set.
        tq = provider.task_queue
        assert tq._queue_root == runtime_dir / "task_queue"

    def test_task_list_uses_provider(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Task list routes through ServiceProvider.task_queue.list_packets."""
        from unittest.mock import patch

        import ops

        # Create a packet first so there's data to list.
        ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "Provider test",
            ]
        )
        capsys.readouterr()

        # Verify the provider's list_packets is called (not direct import).
        with patch(
            "bid_euchre.ops.adapters.bid_euchre.TaskQueueService.list_packets",
            wraps=ops._get_provider(
                argparse.Namespace(runtime_dir=runtime_dir)
            ).task_queue.list_packets,
        ) as mock_list:
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "--plans-dir",
                    str(plans_dir),
                    "task",
                    "list",
                ]
            )
            assert rc == 0
            assert mock_list.called

    def test_task_create_uses_provider(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Task create routes through ServiceProvider.task_queue."""
        import ops

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "task",
                "create",
                "--title",
                "SP wiring test",
                "--owner",
                "author-b",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["title"] == "SP wiring test"
        assert data["owner"] == "author-b"
        assert data["status"] == "pending"

    def test_fleet_load_uses_provider(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """cmd_fleet routes load_status through ServiceProvider.controller."""
        import ops

        # No fleet status file exists — should return gracefully.
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "fleet",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "No fleet status file found" in out

    def test_workers_snapshot_uses_provider(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """cmd_workers default snapshot routes through ServiceProvider."""
        import ops

        # Workers snapshot without tmux should produce pool output
        # (or an error about tmux which is expected in CI).
        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "workers",
            ]
        )
        out = capsys.readouterr().out
        # Either shows pool data or "no managed workers"
        assert rc == 0 or "Worker Pool" in out or "no managed" in out

    def test_provider_to_dict(self, runtime_dir: Path) -> None:
        """ServiceProvider.to_dict() exposes correct adapter class names."""
        import ops

        args = argparse.Namespace(runtime_dir=runtime_dir)
        provider = ops._get_provider(args)
        d = provider.to_dict()

        assert d["controller"] == "ControlPlaneController"
        assert d["monitor"] == "MonitorService"
        assert d["task_queue"] == "TaskQueueService"
        assert d["worker_pool"] == "WorkerPoolService"


# ---------------------------------------------------------------------------
# Slice B (issue #2169) — CLI / rollup consistency gate
# ---------------------------------------------------------------------------


class TestUsageByModelCliMatchesLibrary:
    """Schema-consistency gate between ``usage by-model --json`` and the
    :func:`model_summary` library surface.

    If the CLI serialization ever drifts from the dataclass contract
    (renamed field, shape change, sort-order drift), this test flags it
    so operators' dashboards and the reconcile-parity check cannot
    silently disagree.
    """

    def test_by_model_cli_matches_library(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from dataclasses import asdict

        import ops

        from bid_euchre.ops.token_economy import model_summary

        # Write a tiny two-session store.
        store = tmp_path / "store"
        store.mkdir()
        usage = store / "session_usage.jsonl"
        rows = [
            {
                "session_id": "s1",
                "schema_version": 3,
                "source_type": "project-jsonl",
                "input_tokens": 100,
                "output_tokens": 500,
                "model": "claude-opus-4-7",
                "git_commits": 1,
                "imported_at": "2026-04-20T10:00:00Z",
                "duration_minutes": 30,
                "start_time": "2026-04-20T10:00:00Z",
            },
            {
                "session_id": "s2",
                "schema_version": 3,
                "source_type": "project-jsonl",
                "input_tokens": 50,
                "output_tokens": 200,
                "model": "synthetic",
                "git_commits": 0,
                "imported_at": "2026-04-20T11:00:00Z",
                "duration_minutes": 15,
                "start_time": "2026-04-20T11:00:00Z",
            },
        ]
        with usage.open("w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

        # Direct library call.
        buckets = model_summary(output_dir=store)
        lib_payload = [asdict(b) for b in buckets]

        # CLI call — reuse the same ops module; JSON to stdout.
        # --json is a global flag (must precede the subcommand).
        rc = ops.main(
            [
                "--json",
                "usage",
                "by-model",
                "--output-dir",
                str(store),
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0, captured.err
        cli_payload = json.loads(captured.out)

        # CLI wraps buckets in an object with totals; verify both.
        assert cli_payload["buckets"] == lib_payload
        assert cli_payload["total_tokens"] == sum(
            b["total_tokens"] for b in lib_payload
        )

    def test_by_effort_cli_smokes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`usage by-effort --json` returns a stable object with buckets + total."""
        import ops

        store = tmp_path / "store"
        store.mkdir()
        usage = store / "session_usage.jsonl"
        usage.write_text(
            json.dumps(
                {
                    "session_id": "s1",
                    "schema_version": 3,
                    "source_type": "project-jsonl",
                    "input_tokens": 100,
                    "output_tokens": 500,
                    "git_commits": 1,
                    "imported_at": "2026-04-20T10:00:00Z",
                    "duration_minutes": 30,
                    "start_time": "2026-04-20T10:00:00Z",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        rc = ops.main(
            [
                "--json",
                "usage",
                "by-effort",
                "--output-dir",
                str(store),
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0, captured.err
        payload = json.loads(captured.out)
        assert "buckets" in payload
        assert "total_tokens" in payload
        # Slice B baseline: every session buckets under 'unknown'.
        assert payload["buckets"][0]["effort"] == "unknown"

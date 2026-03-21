"""Tests for the ops.py CLI entrypoint."""

from __future__ import annotations

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

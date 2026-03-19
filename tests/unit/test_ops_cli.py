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
        """Test `ops.py drain` subcommand (canonical drain interface)."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "drain",
            ]
        )
        assert rc == 0
        assert "Drained 0" in capsys.readouterr().out


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

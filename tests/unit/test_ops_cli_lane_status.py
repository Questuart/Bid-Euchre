"""CLI shape tests for ``ops.py lane status`` (issue #2415, PR 2/3).

Verifies that the ``lane status`` subcommand:

- Renders a table header + per-lane row when ``--all`` is passed.
- Renders a single lane's row when a lane id is given positionally
  or via ``--lane``.
- Emits a JSON array when the top-level ``--json`` flag is combined
  with ``lane status``.
- Reports clear exit codes (``1``) for missing args, unknown lanes,
  and positional/flag collisions.
- Surfaces heartbeat fields (``age_seconds``, ``last_tool``,
  ``phase``) in the JSON payload when a per-lane heartbeat file is
  present in the lane's worktree.
- Skips the tmux/pgrep reconciler when ``--no-process-tree`` is
  passed (important for subprocess-free monitoring loops).

These tests are complementary to ``test_ops_status_heartbeat.py``,
which covers the underlying Signal-0 probe.  This file exercises the
CLI integration surface: argparse wiring, row formatting, JSON
encoding, and error reporting.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ``ops.py`` lives under ``scripts/internal`` (not on the package path).
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


@pytest.fixture(autouse=True)
def _add_scripts_path() -> None:
    """Make ``scripts/internal/ops.py`` importable as ``ops``."""
    path_str = str(SCRIPTS_DIR)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Minimal runtime layout expected by ``aggregate_status``."""
    rd = tmp_path / "runtime"
    for sub in (
        "worktree_registry",
        "session_metadata",
        "task_state",
        "events",
        "scheduler",
    ):
        (rd / sub).mkdir(parents=True)
    return rd


def _write_registry_entry(
    runtime_dir: Path,
    *,
    lane_id: str,
    lane_class: str,
    worktree_path: Path,
) -> None:
    """Write a v2 worktree registry entry for a lane."""
    entry = {
        "schema_version": 2,
        "lane_id": lane_id,
        "lane_class": lane_class,
        "worktree_path": str(worktree_path),
        "role": lane_class,
        "display_name": lane_id,
        "legacy_role": lane_class,
        "tmux_session": "steward",
        "tmux_window": lane_id,
        "tmux_pane": "0",
        "session_handle": None,
        "visibility": None,
    }
    path = runtime_dir / "worktree_registry" / f"{lane_id}.json"
    path.write_text(json.dumps(entry))


def _write_heartbeat(
    worktree_path: Path,
    *,
    lane_id: str,
    age_seconds: int,
    last_tool: str = "Bash",
    phase: str = "implementing",
) -> None:
    """Write a heartbeat JSON into a lane's worktree at a pinned age."""
    hb_dir = worktree_path / ".claude" / "runtime" / "lane_status"
    hb_dir.mkdir(parents=True, exist_ok=True)
    updated = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    payload = {
        "schema_version": 1,
        "lane_id": lane_id,
        "pid": 99999,
        "session_id": "test-session",
        "updated_at": updated.isoformat().replace("+00:00", "Z"),
        "last_tool": last_tool,
        "phase": phase,
        "extras": {"cwd": str(worktree_path)},
    }
    (hb_dir / f"{lane_id}.json").write_text(json.dumps(payload))


@pytest.fixture()
def two_lane_fixture(runtime_dir: Path, tmp_path: Path) -> dict[str, Any]:
    """Two registered lanes; author-a has a fresh heartbeat, author-b is
    idle (no heartbeat file).  Both worktree directories exist.
    """
    wt_a = tmp_path / "Bid-Euchre-steward-author-a"
    wt_b = tmp_path / "Bid-Euchre-steward-author-b"
    wt_a.mkdir()
    wt_b.mkdir()
    _write_registry_entry(
        runtime_dir, lane_id="author-a", lane_class="author", worktree_path=wt_a
    )
    _write_registry_entry(
        runtime_dir, lane_id="author-b", lane_class="author", worktree_path=wt_b
    )
    _write_heartbeat(wt_a, lane_id="author-a", age_seconds=30, last_tool="Edit")
    return {"wt_a": wt_a, "wt_b": wt_b}


# ---------------------------------------------------------------------------
# --all text rendering
# ---------------------------------------------------------------------------


class TestLaneStatusAll:
    """``ops.py lane status --all`` — table shape."""

    def test_prints_header_and_one_row_per_lane(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "--all",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # Header columns
        assert "LANE" in out
        assert "PHASE" in out
        assert "FRESH" in out
        assert "LAST_TOOL" in out
        assert "SUMMARY" in out
        # One row per lane
        assert "author-a" in out
        assert "author-b" in out
        # Fresh heartbeat leaks last_tool into row
        assert "Edit" in out

    def test_all_respects_no_process_tree_and_stays_subprocess_free(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
    ) -> None:
        """``--no-process-tree`` ⇒ no tmux/pgrep subprocesses are spawned
        from the probe path."""
        import ops

        with patch(
            "bid_euchre.ops.monitor._detect_background_validation",
            side_effect=AssertionError("reconciler must not run"),
        ):
            rc = ops.main(
                [
                    "--runtime-dir",
                    str(runtime_dir),
                    "lane",
                    "status",
                    "--all",
                    "--no-process-tree",
                ]
            )
        assert rc == 0


# ---------------------------------------------------------------------------
# Single-lane filter (positional and --lane alias)
# ---------------------------------------------------------------------------


class TestLaneStatusFilter:
    """Single-lane selection via positional or ``--lane`` alias."""

    def test_positional_lane_id_filters_output(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "author-a",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "author-a" in out
        assert "author-b" not in out

    def test_flag_alias_matches_positional(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "--lane",
                "author-b",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "author-b" in out
        assert "author-a" not in out

    def test_unknown_lane_returns_error(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "ghost-lane",
                "--no-process-tree",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "ghost-lane" in err
        assert "not found" in err.lower()

    def test_positional_and_flag_collision_errors(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Passing both positional + ``--lane`` with different values must
        fail loudly rather than silently preferring one."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "author-a",
                "--lane",
                "author-b",
                "--no-process-tree",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "disagree" in err.lower() or "conflict" in err.lower()

    def test_no_args_returns_error(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Neither ``--all`` nor a lane id is a usage error."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "lane",
                "status",
                "--no-process-tree",
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "required" in err.lower() or "lane" in err.lower()


# ---------------------------------------------------------------------------
# JSON output shape
# ---------------------------------------------------------------------------


class TestLaneStatusJson:
    """``--json`` flag emits a valid JSON array with the documented schema."""

    def test_json_all_is_valid_array(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--json",
                "lane",
                "status",
                "--all",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        ids = {row["lane_id"] for row in parsed}
        assert ids == {"author-a", "author-b"}

    def test_json_single_lane_is_valid_array_of_one(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--json",
                "lane",
                "status",
                "author-b",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["lane_id"] == "author-b"

    def test_json_row_surfaces_heartbeat_fields(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--json",
                "lane",
                "status",
                "author-a",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        row = parsed[0]
        # Documented top-level fields
        for field in (
            "lane_id",
            "lane_class",
            "phase",
            "has_active_session",
            "liveness_source",
            "attention_needed",
            "heartbeat",
            "summary",
        ):
            assert field in row, f"missing field {field!r} in row keys={list(row)}"
        # Heartbeat sub-object is populated because author-a has a
        # fresh file at age=30s.
        hb = row["heartbeat"]
        assert hb["present"] is True
        assert hb["last_tool"] == "Edit"
        assert hb["phase"] == "implementing"
        # age is non-negative integer seconds (we wrote at 30s; clock
        # may have advanced during the test, so accept >= 30 as well).
        assert isinstance(hb["age_seconds"], int)
        assert hb["age_seconds"] >= 0

    def test_json_row_for_lane_without_heartbeat(
        self,
        runtime_dir: Path,
        two_lane_fixture: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A lane with no heartbeat file reports ``heartbeat.present = False``."""
        import ops

        rc = ops.main(
            [
                "--runtime-dir",
                str(runtime_dir),
                "--json",
                "lane",
                "status",
                "author-b",
                "--no-process-tree",
            ]
        )
        assert rc == 0
        parsed = json.loads(capsys.readouterr().out)
        row = parsed[0]
        assert row["lane_id"] == "author-b"
        assert row["heartbeat"] == {"present": False}


# ---------------------------------------------------------------------------
# Parser wiring (defensive guards)
# ---------------------------------------------------------------------------


class TestLaneStatusParser:
    """Guard against accidental removal of subparser / flags."""

    def test_subparser_registered(self) -> None:
        """``lane status`` is reachable from the top-level parser."""
        import ops

        parser = ops.build_parser()
        # Parse a minimal invocation that the parser will accept without
        # actually running the command (we use a fake runtime-dir and
        # trust the ``rc`` path above for behaviour tests).
        ns = parser.parse_args(["lane", "status", "author-a", "--no-process-tree"])
        assert ns.command == "lane"
        assert ns.lane_action == "status"
        assert ns.lane_id == "author-a"
        assert ns.no_process_tree is True

    def test_all_flag_exposed(self) -> None:
        import ops

        parser = ops.build_parser()
        ns = parser.parse_args(["lane", "status", "--all"])
        assert ns.all is True

    def test_lane_flag_alias_exposed(self) -> None:
        import ops

        parser = ops.build_parser()
        ns = parser.parse_args(["lane", "status", "--lane", "author-c"])
        assert ns.lane_flag == "author-c"

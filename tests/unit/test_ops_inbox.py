"""Tests for ops.py inbox ack-all blocker/escalation exclusion (#2792)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


@pytest.fixture(autouse=True)
def _add_scripts_path() -> None:
    path_str = str(SCRIPTS_DIR)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    (rd / "scheduler").mkdir(parents=True)
    return rd


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    d = tmp_path / "plans"
    d.mkdir()
    return d


@pytest.fixture()
def bus_dir(runtime_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = runtime_dir / "message_bus"
    (d / "inbox").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BID_EUCHRE_BUS_DIR", str(d))
    return d


def _send(
    runtime_dir: Path,
    plans_dir: Path,
    capsys: pytest.CaptureFixture[str],
    to: str,
    summary: str,
    msg_type: str = "ack",
    priority: str = "normal",
) -> str:
    """Send a message via CLI and return its id."""
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
            msg_type,
            "--priority",
            priority,
            "--summary",
            summary,
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    return data["message_id"]


class TestAckAllExcludesBlockers:
    """#2792: ack-all must not silently drain blocker/escalation types."""

    def test_ack_all_excludes_blockers_by_default(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        blocker_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "Primitive E scope request",
            msg_type="blocker",
            priority="high",
        )
        ack_id = _send(runtime_dir, plans_dir, capsys, "author-a", "Routine ack")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack-all",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)

        acked_ids = [m["message_id"] for m in data["acked"]]
        assert (
            blocker_id not in acked_ids
        ), f"Blocker {blocker_id} was silently acked — #2792 regression"
        assert ack_id in acked_ids

    def test_ack_all_excludes_escalations_by_default(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        esc_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "Lane stuck on permission prompt",
            msg_type="escalation",
            priority="urgent",
        )
        ack_id = _send(runtime_dir, plans_dir, capsys, "author-a", "Ack1")

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack-all",
                "--lane",
                "author-a",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        acked_ids = [m["message_id"] for m in data["acked"]]
        assert esc_id not in acked_ids
        assert ack_id in acked_ids

    def test_ack_all_include_types_blocker_opts_in(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        blocker_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "Blocker summary",
            msg_type="blocker",
            priority="high",
        )

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack-all",
                "--lane",
                "author-a",
                "--include-types",
                "blocker",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        acked_ids = [m["message_id"] for m in data["acked"]]
        assert (
            blocker_id in acked_ids
        ), "--include-types blocker did not opt-in to acking the blocker"

    def test_ack_all_include_types_both_opts_in(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        import ops

        blocker_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "BlockerSum",
            msg_type="blocker",
            priority="high",
        )
        esc_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "EscSum",
            msg_type="escalation",
            priority="urgent",
        )

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack-all",
                "--lane",
                "author-a",
                "--include-types",
                "blocker,escalation",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        acked_ids = [m["message_id"] for m in data["acked"]]
        assert blocker_id in acked_ids
        assert esc_id in acked_ids

    def test_ack_all_exclude_types_overrides_default(
        self,
        runtime_dir: Path,
        plans_dir: Path,
        bus_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--exclude-types explicitly overrides the default exclusion list."""
        import ops

        blocker_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "Blocker-overridden",
            msg_type="blocker",
            priority="high",
        )
        prog_id = _send(
            runtime_dir,
            plans_dir,
            capsys,
            "author-a",
            "Progress msg",
            msg_type="progress",
        )

        rc = ops.main(
            [
                "--json",
                "--runtime-dir",
                str(runtime_dir),
                "--plans-dir",
                str(plans_dir),
                "inbox",
                "ack-all",
                "--lane",
                "author-a",
                "--exclude-types",
                "progress",
            ]
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        acked_ids = [m["message_id"] for m in data["acked"]]
        assert prog_id not in acked_ids
        assert (
            blocker_id in acked_ids
        ), "--exclude-types progress should have overridden the default blocker filter"

    def test_ack_all_help_mentions_exclusion(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Help text for ack-all must document the default exclusion behavior."""
        import ops

        with pytest.raises(SystemExit):
            ops.main(["inbox", "ack-all", "--help"])
        out = capsys.readouterr().out
        assert "blocker" in out.lower()
        assert "escalation" in out.lower()

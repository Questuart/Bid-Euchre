"""Contract tests for the ``lane-heartbeat-post-tool.sh`` hook (issue #2689).

These tests lock in the schema contract between the shell hook writer and the
Python reader in :mod:`bid_euchre.ops.lane_heartbeat`.  They exist so that the
perf rewrite of the hook (replacing the per-call ``uv run python`` with a
pure-shell ``printf``/``mv``) cannot silently drift the on-disk format.

Strategy:
    For each case we shell out to the actual hook script with a fresh tmp
    runtime dir (via ``CLAUDE_HEARTBEAT_RUNTIME_DIR``), feed a PostToolUse
    JSON payload on stdin, then parse the produced file through
    :func:`bid_euchre.ops.lane_heartbeat.read_heartbeat`.  Because we go
    through the canonical reader, any schema divergence — missing field,
    wrong type, malformed JSON — turns the round-trip into ``None`` and the
    test fails loudly.

Coverage:
    - Round-trip for a well-formed payload (``tool_name`` present)
    - Missing ``tool_name`` → ``last_tool`` becomes ``None``
    - Tool names with whitespace/quotes are JSON-encoded safely
    - Missing lane id → hook is a no-op (no file written, exit 0)
    - Empty stdin → hook still runs without failing

Invariants asserted on every successful write:
    - Hook exits 0
    - File round-trips through ``read_heartbeat`` (not ``None``)
    - ``is_fresh(hb)`` returns ``True`` against wall clock
    - ``schema_version`` matches the Python writer
    - ``lane_id`` matches the resolved lane
    - ``updated_at`` is a parseable ISO-8601 ``Z`` timestamp
    - ``pid`` is a positive integer
    - ``extras`` is a dict (empty by default)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from bid_euchre.ops.lane_heartbeat import (
    SCHEMA_VERSION,
    is_fresh,
    read_heartbeat,
)

# Resolve the hook once per session.  All tests invoke the same physical
# script so changes to the hook surface are exercised immediately.
REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "lane-heartbeat-post-tool.sh"


def _run_hook(
    *,
    stdin_payload: str,
    runtime_dir: Path,
    agent_name: str | None = "steward-author-a",
    project_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the hook with a controlled env and return the completed process.

    Args:
        stdin_payload: JSON (or garbage) text piped to the hook via stdin.
        runtime_dir: Heartbeat output dir, injected via
            ``CLAUDE_HEARTBEAT_RUNTIME_DIR`` so tests never write to the
            real ``.claude/runtime/lane_status/`` directory.
        agent_name: Sets ``CLAUDE_AGENT_NAME``.  Pass ``None`` and no
            ``project_dir`` to simulate a no-lane session.
        project_dir: Sets ``CLAUDE_PROJECT_DIR``.  Defaults to the repo
            root so the fallback lane resolution by basename can be
            exercised separately.
    """
    env = os.environ.copy()
    # Strip any inherited lane identity so the test env is deterministic.
    env.pop("CLAUDE_AGENT_NAME", None)
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_SESSION_ID", None)
    if agent_name is not None:
        env["CLAUDE_AGENT_NAME"] = agent_name
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env["CLAUDE_HEARTBEAT_RUNTIME_DIR"] = str(runtime_dir)

    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


# ---------------------------------------------------------------------------
# Happy-path round-trip
# ---------------------------------------------------------------------------


def test_hook_round_trips_through_reader(tmp_path: Path) -> None:
    """A well-formed PostToolUse payload yields a file the reader accepts."""
    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Bash"}),
        runtime_dir=tmp_path,
    )
    assert (
        result.returncode == 0
    ), f"hook exited non-zero: {result.returncode} stderr={result.stderr!r}"

    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None, "reader rejected the hook-produced file"
    assert hb.schema_version == SCHEMA_VERSION
    assert hb.lane_id == "author-a"
    assert hb.last_tool == "Bash"
    assert hb.pid > 0
    assert hb.extras == {}
    assert is_fresh(hb), "freshly-written heartbeat must be fresh"


def test_hook_handles_missing_tool_name(tmp_path: Path) -> None:
    """An empty/missing ``tool_name`` maps to ``last_tool is None``.

    This mirrors the Python writer's behavior: omitting ``tool_name`` on
    :func:`write_heartbeat` stores ``None``.  The shell writer must make
    the same mapping so consumers see uniform semantics regardless of
    which writer ran.
    """
    result = _run_hook(
        stdin_payload=json.dumps({}),
        runtime_dir=tmp_path,
    )
    assert result.returncode == 0

    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.last_tool is None


def test_hook_handles_empty_stdin(tmp_path: Path) -> None:
    """An empty stdin payload does not crash the hook.

    Claude Code always sends a JSON object, but defensive behavior here
    keeps the hook safe under manual testing and unusual harness
    conditions.
    """
    result = _run_hook(
        stdin_payload="",
        runtime_dir=tmp_path,
    )
    assert result.returncode == 0

    # With no lane id resolvable from env, we still expect exit 0.  Since
    # we did set CLAUDE_AGENT_NAME, the file should still be written with
    # last_tool None.
    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.last_tool is None


def test_hook_json_escapes_tool_name_with_quotes(tmp_path: Path) -> None:
    """Tool names with embedded quotes/backslashes produce valid JSON.

    The shell writer must not naïvely interpolate ``$TOOL_NAME`` into the
    JSON payload — doing so would corrupt the file for any tool name
    containing a double-quote, backslash, or control character.  ``jq
    -Rcn 'inputs'`` handles this correctly.
    """
    weird = 'tool "with" \\slashes\\ and\ttabs'
    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": weird}),
        runtime_dir=tmp_path,
    )
    assert result.returncode == 0

    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None, "reader must accept hook-produced JSON"
    assert (
        hb.last_tool == weird
    ), f"tool name corrupted by escaping: got {hb.last_tool!r}"


# ---------------------------------------------------------------------------
# Lane resolution
# ---------------------------------------------------------------------------


def test_hook_resolves_lane_from_agent_name(tmp_path: Path) -> None:
    """``CLAUDE_AGENT_NAME`` strips the ``steward-`` prefix."""
    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Edit"}),
        runtime_dir=tmp_path,
        agent_name="steward-author-c",
    )
    assert result.returncode == 0

    hb = read_heartbeat("author-c", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.lane_id == "author-c"


def test_hook_resolves_lane_from_project_dir_basename(tmp_path: Path) -> None:
    """Fallback: basename of ``CLAUDE_PROJECT_DIR`` maps to a lane id.

    This mirrors the case-statement in the hook.  We simulate a
    ``steward-analyst-b`` worktree by creating a tmpdir with that suffix.
    """
    fake_worktree = tmp_path / "Bid-Euchre-steward-analyst-b"
    fake_worktree.mkdir()
    runtime = tmp_path / "lane_status"

    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Bash"}),
        runtime_dir=runtime,
        agent_name=None,
        project_dir=fake_worktree,
    )
    assert result.returncode == 0

    hb = read_heartbeat("analyst-b", runtime_dir=runtime)
    assert hb is not None
    assert hb.lane_id == "analyst-b"


def test_hook_no_lane_id_is_noop(tmp_path: Path) -> None:
    """Without a resolvable lane id the hook exits 0 without writing."""
    # No CLAUDE_AGENT_NAME, and CLAUDE_PROJECT_DIR points to a dir whose
    # basename is not in the lane-id case-statement.
    ad_hoc = tmp_path / "some-random-dev-laptop"
    ad_hoc.mkdir()
    runtime = tmp_path / "lane_status"

    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Bash"}),
        runtime_dir=runtime,
        agent_name=None,
        project_dir=ad_hoc,
    )
    assert result.returncode == 0

    # No file should have been written.  The runtime dir may or may not
    # exist depending on mkdir-before-lane-check ordering; either is fine
    # as long as no lane file appears.
    if runtime.exists():
        assert (
            list(runtime.glob("*.json")) == []
        ), "no-lane session must not produce any heartbeat file"


# ---------------------------------------------------------------------------
# Always exits 0
# ---------------------------------------------------------------------------


def test_hook_exits_zero_on_malformed_stdin(tmp_path: Path) -> None:
    """Non-JSON stdin must never cause the hook to fail."""
    result = _run_hook(
        stdin_payload="this is not json at all {{",
        runtime_dir=tmp_path,
    )
    assert result.returncode == 0


def test_hook_exits_zero_on_unwritable_runtime_dir(tmp_path: Path) -> None:
    """If the runtime dir cannot be created or written, hook still exits 0.

    Simulated by pointing the runtime dir at a path whose parent is a
    regular file, making ``mkdir -p`` fail.
    """
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    unwritable = blocker / "child"

    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Bash"}),
        runtime_dir=unwritable,
    )
    assert (
        result.returncode == 0
    ), "heartbeat-write failure must never propagate to tool-call pipeline"


# ---------------------------------------------------------------------------
# Parity with the Python writer
# ---------------------------------------------------------------------------


def test_hook_schema_matches_python_writer(tmp_path: Path) -> None:
    """The shell writer and Python writer produce the same schema.

    Structural check: the sorted key sets of the two outputs must match.
    This is the fundamental contract — if the writers diverge, consumer
    code that handles one but not the other breaks silently.
    """
    # Shell side.
    shell_dir = tmp_path / "shell"
    result = _run_hook(
        stdin_payload=json.dumps({"tool_name": "Bash"}),
        runtime_dir=shell_dir,
    )
    assert result.returncode == 0

    shell_file = shell_dir / "author-a.json"
    assert shell_file.exists()
    shell_json = json.loads(shell_file.read_text())

    # Python side.
    from bid_euchre.ops.lane_heartbeat import write_heartbeat

    py_dir = tmp_path / "python"
    py_dir.mkdir()
    write_heartbeat("author-a", tool_name="Bash", runtime_dir=py_dir)
    py_json = json.loads((py_dir / "author-a.json").read_text())

    assert sorted(shell_json.keys()) == sorted(py_json.keys()), (
        f"schema drift between shell and python writers:\n"
        f"  shell keys:  {sorted(shell_json.keys())}\n"
        f"  python keys: {sorted(py_json.keys())}"
    )

    # Value-level equality on the schema-fixed fields.
    for field in ("schema_version", "lane_id", "last_tool", "phase", "extras"):
        assert shell_json[field] == py_json[field], (
            f"field {field!r} differs: shell={shell_json[field]!r} "
            f"python={py_json[field]!r}"
        )


@pytest.mark.skipif(not HOOK_PATH.exists(), reason="hook script not present")
def test_hook_script_exists() -> None:
    """Guardrail — the hook path resolves to a real file."""
    assert HOOK_PATH.is_file()

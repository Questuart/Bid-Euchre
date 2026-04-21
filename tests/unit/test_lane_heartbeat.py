"""Tests for the lane-heartbeat writer (issue #2415 — PR 1 of 3).

PR 1 is strictly writer-only — no consumer reads these files yet.  The
test surface proves:

- Schema round-trip:  ``write_heartbeat`` → ``read_heartbeat`` yields the
  same values on a well-formed file.
- Freshness semantics:  :func:`is_fresh` honors the ``threshold_seconds``
  boundary inclusively and treats missing / malformed / future-dated
  inputs conservatively.
- Graceful degradation:  missing file, malformed JSON, shape mismatch,
  and non-dict JSON all return ``None`` from ``read_heartbeat`` without
  raising.
- Atomic write pattern:  the writer serializes to a sibling ``.tmp``
  file, then calls :func:`os.replace` onto the final path.  Proven
  structurally by patching ``os.replace`` inside the module.
- Phase vocabulary:  documented phase values round-trip unchanged;
  unknown phases do not crash the writer or the reader.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.ops import lane_heartbeat
from bid_euchre.ops.lane_heartbeat import (
    DEFAULT_FRESHNESS_SECONDS,
    KNOWN_PHASES,
    SCHEMA_VERSION,
    Heartbeat,
    is_fresh,
    read_heartbeat,
    write_heartbeat,
)

# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_preserves_fields(tmp_path: Path) -> None:
    """write → read yields the same lane_id, tool, phase, and extras."""
    path = write_heartbeat(
        "author-a",
        tool_name="Bash",
        phase="implementing",
        extras={"cwd": "/tmp/author-a", "pr": "#2415"},
        runtime_dir=tmp_path,
    )
    assert path == tmp_path / "author-a.json"
    assert path.exists()

    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.schema_version == SCHEMA_VERSION
    assert hb.lane_id == "author-a"
    assert hb.pid == os.getpid()
    assert hb.last_tool == "Bash"
    assert hb.phase == "implementing"
    assert hb.extras == {"cwd": "/tmp/author-a", "pr": "#2415"}


def test_round_trip_omits_optional_fields(tmp_path: Path) -> None:
    """Optional fields default to None / empty dict, not missing keys."""
    write_heartbeat("author-b", runtime_dir=tmp_path)
    hb = read_heartbeat("author-b", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.last_tool is None
    assert hb.phase is None
    assert hb.extras == {}


def test_second_write_overwrites(tmp_path: Path) -> None:
    """A later write replaces the earlier heartbeat wholesale."""
    write_heartbeat("author-c", tool_name="Bash", runtime_dir=tmp_path)
    write_heartbeat("author-c", tool_name="Edit", phase="idle", runtime_dir=tmp_path)

    hb = read_heartbeat("author-c", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.last_tool == "Edit"
    assert hb.phase == "idle"


# ---------------------------------------------------------------------------
# Freshness boundary
# ---------------------------------------------------------------------------


def _hb_at(ts: datetime) -> Heartbeat:
    """Build an in-memory Heartbeat stamped at ``ts`` (UTC)."""
    return Heartbeat(
        schema_version=SCHEMA_VERSION,
        lane_id="author-a",
        pid=1,
        session_id=None,
        updated_at=ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        last_tool=None,
        phase=None,
        extras={},
    )


def test_is_fresh_well_within_threshold() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb = _hb_at(now - timedelta(seconds=30))
    assert is_fresh(hb, threshold_seconds=120, now=now) is True


def test_is_fresh_at_exact_boundary_is_inclusive() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb = _hb_at(now - timedelta(seconds=120))
    # Exactly threshold_seconds old counts as fresh.
    assert is_fresh(hb, threshold_seconds=120, now=now) is True


def test_is_fresh_one_second_past_threshold_is_stale() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb = _hb_at(now - timedelta(seconds=121))
    assert is_fresh(hb, threshold_seconds=120, now=now) is False


def test_is_fresh_none_heartbeat_is_stale() -> None:
    assert is_fresh(None) is False


def test_is_fresh_unparseable_timestamp_is_stale() -> None:
    hb = _hb_at(datetime.now(timezone.utc))
    hb.updated_at = "not-a-timestamp"
    assert is_fresh(hb) is False


def test_is_fresh_default_threshold_is_ten_minutes() -> None:
    assert DEFAULT_FRESHNESS_SECONDS == 600


def test_is_fresh_future_timestamp_is_fresh() -> None:
    """Clock skew into the future does not mark a lane stale."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb = _hb_at(now + timedelta(seconds=30))
    assert is_fresh(hb, threshold_seconds=60, now=now) is True


def test_is_fresh_negative_threshold_treated_as_zero() -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb = _hb_at(now - timedelta(seconds=1))
    assert is_fresh(hb, threshold_seconds=-5, now=now) is False


# ---------------------------------------------------------------------------
# Graceful degradation on read
# ---------------------------------------------------------------------------


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_heartbeat("nonexistent-lane", runtime_dir=tmp_path) is None


def test_read_malformed_json_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "author-a.json"
    path.write_text("{not json")
    assert read_heartbeat("author-a", runtime_dir=tmp_path) is None


def test_read_non_object_json_returns_none(tmp_path: Path) -> None:
    """JSON that parses to a list / scalar is not a valid Heartbeat."""
    path = tmp_path / "author-a.json"
    path.write_text("[1, 2, 3]")
    assert read_heartbeat("author-a", runtime_dir=tmp_path) is None


def test_read_missing_required_field_returns_none(tmp_path: Path) -> None:
    """A JSON object that lacks a required field is rejected."""
    path = tmp_path / "author-a.json"
    # Missing ``lane_id`` — ``Heartbeat.from_json`` raises KeyError,
    # which the reader must swallow into ``None``.
    path.write_text(json.dumps({"schema_version": 1, "pid": 1}))
    assert read_heartbeat("author-a", runtime_dir=tmp_path) is None


def test_read_wrong_type_returns_none(tmp_path: Path) -> None:
    """A field with the wrong type is rejected without raising."""
    path = tmp_path / "author-a.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "not-an-int",
                "lane_id": "author-a",
                "pid": 1,
                "session_id": None,
                "updated_at": "2026-04-20T23:00:00Z",
                "last_tool": None,
                "phase": None,
                "extras": {},
            }
        )
    )
    assert read_heartbeat("author-a", runtime_dir=tmp_path) is None


# ---------------------------------------------------------------------------
# Atomic write (structural)
# ---------------------------------------------------------------------------


def test_write_uses_atomic_tempfile_and_replace(tmp_path: Path) -> None:
    """Prove the writer serializes to a sibling ``.tmp`` file and then
    calls :func:`os.replace` onto the final path.

    A concurrent reader must never observe a partial file.  Patching
    ``os.replace`` on the module under test captures the pre-rename
    state so we can assert:

    1. The tempfile path has a ``.tmp`` suffix, lives in the same
       directory as the target, and contains valid JSON.
    2. ``os.replace`` is called exactly once per write, with (tmp, target).
    """
    observed: dict = {}

    def fake_replace(src: str, dst: str) -> None:
        observed["src"] = str(src)
        observed["dst"] = str(dst)
        # Verify the tempfile exists and is valid JSON at the moment the
        # rename would have happened — the whole point of atomic rename.
        assert Path(src).exists(), "tempfile must exist before rename"
        assert Path(src).read_text().strip() != "", "tempfile must not be empty"
        data = json.loads(Path(src).read_text())
        assert data["lane_id"] == "author-a"
        # Do the real rename so subsequent assertions on the target work.
        os.rename(src, dst)

    with patch.object(lane_heartbeat.os, "replace", side_effect=fake_replace) as m:
        write_heartbeat("author-a", tool_name="Bash", runtime_dir=tmp_path)

    assert m.call_count == 1, "exactly one atomic rename per write"
    assert observed["src"].endswith(".tmp"), "source must be a tempfile"
    assert observed["dst"].endswith("author-a.json"), "dest must be the target"
    assert Path(observed["src"]).parent == Path(observed["dst"]).parent, (
        "tempfile must be in the same directory as the target "
        "so os.replace is guaranteed atomic on POSIX"
    )
    # After the real rename, tempfile should be gone, target present.
    assert not Path(observed["src"]).exists()
    assert Path(observed["dst"]).exists()


def test_write_creates_runtime_dir_if_missing(tmp_path: Path) -> None:
    """The writer is safe to invoke even before the runtime dir exists."""
    target_dir = tmp_path / "does-not-exist-yet"
    assert not target_dir.exists()
    write_heartbeat("author-a", runtime_dir=target_dir)
    assert target_dir.is_dir()
    assert (target_dir / "author-a.json").is_file()


# ---------------------------------------------------------------------------
# Phase vocabulary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", sorted(KNOWN_PHASES))
def test_documented_phase_values_round_trip(phase: str, tmp_path: Path) -> None:
    """Every documented phase value survives write → read unchanged."""
    write_heartbeat("author-a", phase=phase, runtime_dir=tmp_path)
    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.phase == phase


def test_unknown_phase_does_not_crash(tmp_path: Path) -> None:
    """The writer accepts free-form phases; the reader returns them intact."""
    write_heartbeat("author-a", phase="some-new-label-future-pr", runtime_dir=tmp_path)
    hb = read_heartbeat("author-a", runtime_dir=tmp_path)
    assert hb is not None
    assert hb.phase == "some-new-label-future-pr"


def test_known_phases_cover_documented_vocabulary() -> None:
    """Guard rail: the KNOWN_PHASES constant must match the README doc."""
    # If this set changes, update .claude/runtime/lane_status/README.md.
    assert KNOWN_PHASES == {"implementing", "validating", "waiting", "idle"}


# ---------------------------------------------------------------------------
# Shell writer parity (issue #2689)
# ---------------------------------------------------------------------------
#
# The PostToolUse hook has a pure-shell writer at
# .claude/hooks/lane-heartbeat-post-tool.sh that was rewritten to drop the
# per-tool-call ``uv run python`` spawn.  The Python writer in this module
# remains the canonical reference and stays available as a test/fallback
# path.  These tests lock the invariant that the two writers produce
# compatible on-disk schemas — any divergence is a regression that would
# break consumers.


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "hooks"
    / "lane-heartbeat-post-tool.sh"
)


def _run_shell_writer(runtime_dir: Path, lane: str, tool_name: str) -> None:
    """Invoke the shell hook with a controlled env to write a heartbeat."""
    env = {
        **os.environ,
        "CLAUDE_AGENT_NAME": f"steward-{lane}",
        "CLAUDE_HEARTBEAT_RUNTIME_DIR": str(runtime_dir),
    }
    # Scrub inherited project dir so the lane comes from the agent name
    # alone, making the test deterministic on any host.
    env.pop("CLAUDE_PROJECT_DIR", None)
    env.pop("CLAUDE_SESSION_ID", None)
    subprocess.run(
        ["bash", str(_HOOK_PATH)],
        input=json.dumps({"tool_name": tool_name}),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=True,
    )


@pytest.mark.skipif(not _HOOK_PATH.exists(), reason="hook script not present")
def test_shell_writer_schema_matches_python_writer(tmp_path: Path) -> None:
    """Shell-produced heartbeat has the same keys + primitive values.

    This is the single strongest invariant across the two writers: their
    on-disk JSON schemas must agree on every field consumers read.  The
    timestamp, pid, and session_id fields naturally differ (they reflect
    the writing process); everything else must match.
    """
    shell_dir = tmp_path / "shell"
    _run_shell_writer(shell_dir, lane="author-a", tool_name="Bash")

    py_dir = tmp_path / "python"
    py_dir.mkdir()
    write_heartbeat("author-a", tool_name="Bash", runtime_dir=py_dir)

    shell_json = json.loads((shell_dir / "author-a.json").read_text())
    py_json = json.loads((py_dir / "author-a.json").read_text())

    assert sorted(shell_json.keys()) == sorted(py_json.keys()), (
        "shell and python writers must emit the same key set; divergence "
        "means consumers could see different shapes depending on which "
        "writer ran"
    )
    # Schema-fixed fields: identical values.
    assert shell_json["schema_version"] == py_json["schema_version"]
    assert shell_json["lane_id"] == py_json["lane_id"]
    assert shell_json["last_tool"] == py_json["last_tool"]
    assert shell_json["phase"] == py_json["phase"]
    assert shell_json["extras"] == py_json["extras"]


@pytest.mark.skipif(not _HOOK_PATH.exists(), reason="hook script not present")
def test_shell_writer_output_round_trips_through_reader(tmp_path: Path) -> None:
    """read_heartbeat must accept shell-produced files as-is.

    The reader is the canonical consumer of the on-disk format.  If this
    test fails, the shell writer has drifted from the schema defined by
    :class:`Heartbeat.from_json` and the fleet dashboard (PR 3/3 of
    #2415) will silently drop the lane's heartbeat on the floor.
    """
    _run_shell_writer(tmp_path, lane="author-b", tool_name="Edit")
    hb = read_heartbeat("author-b", runtime_dir=tmp_path)
    assert hb is not None, "canonical reader rejected shell-produced file"
    assert hb.lane_id == "author-b"
    assert hb.last_tool == "Edit"
    assert hb.schema_version == SCHEMA_VERSION


@pytest.mark.skipif(not _HOOK_PATH.exists(), reason="hook script not present")
def test_shell_writer_is_fresh_against_wall_clock(tmp_path: Path) -> None:
    """Newly shell-written heartbeats are fresh by the default threshold.

    The shell writer stamps with ``date -u +"%Y-%m-%dT%H:%M:%SZ"`` and
    must produce a parseable ISO timestamp that :func:`is_fresh` treats
    as current.
    """
    _run_shell_writer(tmp_path, lane="author-c", tool_name="Bash")
    hb = read_heartbeat("author-c", runtime_dir=tmp_path)
    assert hb is not None
    assert is_fresh(hb), (
        f"shell-produced heartbeat not fresh against wall clock; "
        f"updated_at={hb.updated_at!r}"
    )

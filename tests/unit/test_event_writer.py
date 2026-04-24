"""Unit tests for ``bid_euchre.ops.event_writer``.

Covers:

- Happy-path write + sidecar population (§3.2 metadata contract)
- Rotation at ``STEWARD_EVENTS_MAX_FILE_BYTES`` boundary
- Corruption-safety: damaged sidecar is overwritten, not fatal
- Seq + turn counters: monotonicity, fresh start behavior
- Cross-process ordering via file lock (smoke: single-process concurrent
  threads as a proxy — POSIX flock is re-entrant per-process anyway)
- Introspection helpers: ``list_active_files``, ``iter_sidecars``,
  ``read_sidecar``

Per Phase 0 Readiness (shaping §6.2): JSONL round-trip + locking + sidecar
schema must be demonstrable before Packet 3 closes.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from bid_euchre.ops import event_writer as ew
from bid_euchre.ops.event_schema import SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Isolated events log dir per test."""
    d = tmp_path / "events"
    d.mkdir()
    return d


def _record(
    event_type: str = "task_started",
    *,
    seq: int = 1,
    timestamp_ns: int = 1_700_000_000_000_000_000,
    **extra,
) -> dict:
    rec = {
        "event_type": event_type,
        "seq": seq,
        "timestamp_ns": timestamp_ns,
        "schema_version": SCHEMA_VERSION,
        "lane_id": "author-a",
    }
    rec.update(extra)
    return rec


# ---------------------------------------------------------------------------
# Happy-path write
# ---------------------------------------------------------------------------


def test_write_event_creates_jsonl_file(log_dir: Path) -> None:
    path = ew.write_event(_record(), log_dir=log_dir)
    assert path.exists()
    assert path.suffix == ".jsonl"
    assert path.parent == log_dir


def test_write_event_appends_one_line_per_call(log_dir: Path) -> None:
    p1 = ew.write_event(_record(event_type="task_started", seq=1), log_dir=log_dir)
    p2 = ew.write_event(_record(event_type="task_completed", seq=2), log_dir=log_dir)
    assert p1 == p2  # Same file (no rotation)
    lines = p1.read_text().splitlines()
    assert len(lines) == 2
    # Each line is valid JSON
    rec1 = json.loads(lines[0])
    rec2 = json.loads(lines[1])
    assert rec1["event_type"] == "task_started"
    assert rec2["event_type"] == "task_completed"


def test_write_event_filename_uses_utc_date_and_counter(log_dir: Path) -> None:
    path = ew.write_event(_record(), log_dir=log_dir)
    # events-YYYY-MM-DD-NNN.jsonl
    parts = path.stem.split("-")
    assert parts[0] == "events"
    # Date portion has 3 hyphens inside: YYYY-MM-DD
    assert len(parts) == 5
    assert parts[-1] == "001"  # First rotation on a fresh day


def test_write_event_jsonl_line_is_valid_json(log_dir: Path) -> None:
    ew.write_event(_record(extra_token="hello"), log_dir=log_dir)
    path = next(iter(log_dir.glob("*.jsonl")))
    line = path.read_text().strip()
    parsed = json.loads(line)
    assert parsed["extra_token"] == "hello"


# ---------------------------------------------------------------------------
# Sidecar metadata contract
# ---------------------------------------------------------------------------


def test_sidecar_populates_first_and_last_seq(log_dir: Path) -> None:
    ew.write_event(
        _record(seq=5, timestamp_ns=1_700_000_000_000_000_000), log_dir=log_dir
    )
    ew.write_event(
        _record(seq=6, timestamp_ns=1_700_000_000_000_000_500), log_dir=log_dir
    )
    ew.write_event(
        _record(seq=7, timestamp_ns=1_700_000_000_000_001_000), log_dir=log_dir
    )
    meta_path = next(iter(log_dir.glob("*.meta.json")))
    meta = json.loads(meta_path.read_text())
    assert meta["first_seq"] == 5
    assert meta["last_seq"] == 7
    assert meta["first_timestamp_ns"] == 1_700_000_000_000_000_000
    assert meta["last_timestamp_ns"] == 1_700_000_000_000_001_000
    assert meta["event_count"] == 3
    assert meta["schema_version"] == SCHEMA_VERSION


def test_sidecar_tracks_event_types_sorted(log_dir: Path) -> None:
    ew.write_event(_record(event_type="task_started", seq=1), log_dir=log_dir)
    ew.write_event(_record(event_type="task_completed", seq=2), log_dir=log_dir)
    ew.write_event(_record(event_type="task_started", seq=3), log_dir=log_dir)
    meta_path = next(iter(log_dir.glob("*.meta.json")))
    meta = json.loads(meta_path.read_text())
    assert meta["event_types"] == ["task_completed", "task_started"]


def test_sidecar_corruption_is_recovered_not_raised(log_dir: Path) -> None:
    """A damaged .meta.json file should be overwritten, not crash the writer."""
    ew.write_event(_record(seq=1), log_dir=log_dir)
    meta_path = next(iter(log_dir.glob("*.meta.json")))
    # Corrupt the sidecar
    meta_path.write_text("not valid json {{{")
    # Next write should recover and produce valid JSON
    ew.write_event(_record(seq=2), log_dir=log_dir)
    meta = json.loads(meta_path.read_text())
    # Recovered meta starts fresh from the second write
    assert meta["event_count"] == 1
    assert meta["first_seq"] == 2
    assert meta["last_seq"] == 2


def test_read_sidecar_returns_none_for_missing(log_dir: Path) -> None:
    assert ew.read_sidecar(log_dir / "nonexistent.meta.json") is None


def test_read_sidecar_returns_none_for_corrupt(log_dir: Path) -> None:
    bad = log_dir / "bad.meta.json"
    bad.write_text("{{{{")
    assert ew.read_sidecar(bad) is None


def test_read_sidecar_roundtrip(log_dir: Path) -> None:
    ew.write_event(_record(seq=1), log_dir=log_dir)
    meta_path = next(iter(log_dir.glob("*.meta.json")))
    meta = ew.read_sidecar(meta_path)
    assert meta is not None
    assert meta["event_count"] == 1
    assert meta["schema_version"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------


def test_rotation_triggers_at_max_bytes(log_dir: Path, monkeypatch) -> None:
    """When the active file exceeds max_bytes, next write goes to a new file."""
    monkeypatch.setenv("STEWARD_EVENTS_MAX_FILE_BYTES", "1024")  # 1 KB floor

    # Write a batch of ~2 KB to force rotation
    for i in range(20):  # each record ~200 bytes
        ew.write_event(_record(seq=i, extra_padding="x" * 100), log_dir=log_dir)

    files = sorted(log_dir.glob("events-*.jsonl"))
    assert len(files) >= 2, f"Expected rotation to produce multiple files, got {files}"
    # Counters 001 and 002 must be distinct
    stems = [f.stem for f in files]
    assert any(s.endswith("-001") for s in stems)
    assert any(s.endswith("-002") for s in stems)


def test_rotation_preserves_per_file_sidecar(log_dir: Path, monkeypatch) -> None:
    """Each rotated file gets its own sidecar."""
    monkeypatch.setenv("STEWARD_EVENTS_MAX_FILE_BYTES", "1024")

    for i in range(20):
        ew.write_event(_record(seq=i, extra_padding="y" * 100), log_dir=log_dir)

    jsonl_files = sorted(log_dir.glob("events-*.jsonl"))
    for jsonl_path in jsonl_files:
        sidecar = jsonl_path.with_suffix(".meta.json")
        assert sidecar.exists(), f"missing sidecar for {jsonl_path}"
        meta = json.loads(sidecar.read_text())
        assert meta["event_count"] > 0
        assert meta["first_seq"] <= meta["last_seq"]


def test_no_rotation_when_under_max_bytes(log_dir: Path, monkeypatch) -> None:
    """Default 50 MB max — one-shot writes should stay in counter 001."""
    # Use default (~50 MB)
    monkeypatch.delenv("STEWARD_EVENTS_MAX_FILE_BYTES", raising=False)
    for i in range(5):
        ew.write_event(_record(seq=i), log_dir=log_dir)
    files = list(log_dir.glob("events-*.jsonl"))
    assert len(files) == 1
    assert files[0].stem.endswith("-001")


def test_max_file_bytes_floor_prevents_pathological_rotation(
    log_dir: Path, monkeypatch
) -> None:
    """Values under 1 KB are clamped to 1 KB floor (prevents DoS)."""
    monkeypatch.setenv("STEWARD_EVENTS_MAX_FILE_BYTES", "1")
    # Write 3 records (~200 bytes each) — all should land in counter 001
    # because the effective floor is 1 KB.
    for i in range(3):
        ew.write_event(_record(seq=i), log_dir=log_dir)
    files = list(log_dir.glob("events-*.jsonl"))
    assert len(files) == 1  # Floor prevented rotation


def test_invalid_max_file_bytes_falls_back_to_default(
    log_dir: Path, monkeypatch
) -> None:
    monkeypatch.setenv("STEWARD_EVENTS_MAX_FILE_BYTES", "not-a-number")
    # Should not raise
    ew.write_event(_record(), log_dir=log_dir)
    assert ew._env_max_file_bytes() == ew.DEFAULT_MAX_FILE_BYTES


# ---------------------------------------------------------------------------
# Seq + turn counters
# ---------------------------------------------------------------------------


def test_next_seq_is_monotonic(log_dir: Path) -> None:
    s1 = ew.next_seq(log_dir=log_dir)
    s2 = ew.next_seq(log_dir=log_dir)
    s3 = ew.next_seq(log_dir=log_dir)
    assert s2 == s1 + 1
    assert s3 == s2 + 1


def test_next_seq_starts_at_one_for_fresh_dir(log_dir: Path) -> None:
    assert ew.next_seq(log_dir=log_dir) == 1


def test_next_seq_persists_across_calls(log_dir: Path) -> None:
    ew.next_seq(log_dir=log_dir)
    ew.next_seq(log_dir=log_dir)
    seq_file = log_dir / ew.SEQ_FILE_NAME
    assert seq_file.exists()
    assert int(seq_file.read_text().strip()) == 2


def test_get_turn_id_returns_zero_initially(log_dir: Path) -> None:
    assert ew.get_turn_id(log_dir=log_dir) == 0


def test_increment_turn_id_is_monotonic(log_dir: Path) -> None:
    t1 = ew.increment_turn_id(log_dir=log_dir)
    t2 = ew.increment_turn_id(log_dir=log_dir)
    assert t1 == 1
    assert t2 == 2
    assert ew.get_turn_id(log_dir=log_dir) == 2


def test_turn_id_recovers_from_corrupted_file(log_dir: Path) -> None:
    turn_path = log_dir / ew.TURN_FILE_NAME
    turn_path.write_text("not-a-number")
    # Should recover to 0 and increment to 1
    assert ew.increment_turn_id(log_dir=log_dir) == 1


# ---------------------------------------------------------------------------
# Env knob routing
# ---------------------------------------------------------------------------


def test_env_log_dir_override(tmp_path: Path, monkeypatch) -> None:
    custom_dir = tmp_path / "custom-events"
    monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(custom_dir))
    path = ew.write_event(_record())
    assert custom_dir in path.parents


def test_env_log_dir_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("STEWARD_EVENTS_LOG_DIR", raising=False)
    assert ew._env_log_dir() == ew.DEFAULT_LOG_DIR


# ---------------------------------------------------------------------------
# Introspection helpers
# ---------------------------------------------------------------------------


def test_list_active_files_returns_todays_files_only(log_dir: Path) -> None:
    # Write today's event
    ew.write_event(_record(), log_dir=log_dir)
    # Create a stale file for a different date
    stale = log_dir / "events-2020-01-01-001.jsonl"
    stale.write_text('{"event_type":"old"}\n')
    active = ew.list_active_files(log_dir=log_dir)
    assert len(active) == 1
    assert "2020-01-01" not in active[0].name


def test_list_active_files_empty_dir(tmp_path: Path) -> None:
    assert ew.list_active_files(log_dir=tmp_path / "nonexistent") == []


def test_iter_sidecars_returns_all(log_dir: Path) -> None:
    ew.write_event(_record(seq=1), log_dir=log_dir)
    # Also create an arbitrary-date sidecar
    extra_meta = log_dir / "events-2020-01-01-001.meta.json"
    extra_meta.write_text(json.dumps({"event_count": 5}))
    sidecars = ew.iter_sidecars(log_dir=log_dir)
    assert len(sidecars) == 2


def test_iter_sidecars_empty_dir(tmp_path: Path) -> None:
    assert ew.iter_sidecars(log_dir=tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# Concurrency (smoke)
# ---------------------------------------------------------------------------


def test_concurrent_writers_produce_one_line_per_write(log_dir: Path) -> None:
    """File lock ensures no interleaved partial lines.

    We can't easily reproduce cross-process fcntl semantics in-process
    (same PID re-enters the lock), but we can assert that each line
    produced is valid JSON and that the total count matches.
    """
    n_threads = 8
    n_per = 10

    def worker(start_seq: int) -> None:
        for i in range(n_per):
            ew.write_event(
                _record(seq=start_seq + i, event_type="task_started"),
                log_dir=log_dir,
            )

    threads = [
        threading.Thread(target=worker, args=(t * n_per,)) for t in range(n_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    path = next(iter(log_dir.glob("*.jsonl")))
    lines = path.read_text().splitlines()
    assert len(lines) == n_threads * n_per
    # Every line parses as JSON
    for line in lines:
        json.loads(line)


# ---------------------------------------------------------------------------
# Sidecar path helper
# ---------------------------------------------------------------------------


def test_sidecar_path_transforms_suffix(tmp_path: Path) -> None:
    jsonl = tmp_path / "events-2026-01-01-001.jsonl"
    assert ew._sidecar_path(jsonl).name == "events-2026-01-01-001.meta.json"

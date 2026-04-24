"""Unit tests for ``scripts/internal/memory_compact.py``.

Per Primitive C shaping §5.1 row C.10
(``plans/steward_platform/3_primitive_C/shaping.md``). The shape says
"compaction preserves high-priority entries by schema-defined rule";
these tests lock the parsing + partition + rendering behavior so the
schema cannot drift silently.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "internal" / "memory_compact.py"


def _load_module():
    if "memory_compact" in sys.modules:
        return sys.modules["memory_compact"]
    spec = importlib.util.spec_from_file_location("memory_compact", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["memory_compact"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_ANCHOR_ONLY = """\
# Project Memory

## Operational Tips

- Rule one.
- Rule two.

## Governing Plans

| Initiative | Status |
|---|---|
| Alpha | COMPLETE |
"""

_WITH_SESSIONS = """\
# Project Memory

## Operational Tips

- Rule one.

## Governing Plans

| Initiative | Status |
|---|---|
| Alpha | ACTIVE |

### Session 2026-01-01 — Oldest

Lorem ipsum dolor sit amet.

### Session 2026-02-15 — Middle

Consectetur adipiscing elit.

### Session 2026-03-20 — Newest

Sed do eiusmod tempor.

## Known Debt

- Item A.
- Item B.

## Key Rules

- Always seed experiments.
"""

_WITH_HIGH_PRIORITY = """\
# Project Memory

## Overview

Anchor text.

### Session 2025-06-01 — Phase Closeout for Arc D

This is old but high-priority.

### Session 2026-01-10 — Routine A

Routine session 1.

### Session 2026-02-20 — Routine B

Routine session 2.

### Session 2026-03-30 — Routine C

Routine session 3.

### Session 2026-04-10 — Routine D

Routine session 4.

## Closing Notes

Trailer content.
"""

_WITH_DATE_RANGE_HEADING = """\
# Project Memory

## Overview

Top matter.

### Session 2026-04-22c → 2026-04-23 — Multi-day session

Body spanning two days.

### Session 2026-04-01 — Earlier session

Shorter body.

## Trailer
"""


# ---------------------------------------------------------------------------
# parse_memory
# ---------------------------------------------------------------------------


def test_parse_memory_anchor_only() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_ANCHOR_ONLY)
    assert parsed.sessions == ()
    assert "Project Memory" in "".join(parsed.anchor)
    assert parsed.trailer == ()


def test_parse_memory_with_sessions_three_blocks() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    assert len(parsed.sessions) == 3
    headings = [s.heading for s in parsed.sessions]
    assert "Oldest" in headings[0]
    assert "Middle" in headings[1]
    assert "Newest" in headings[2]


def test_parse_memory_trailer_is_preserved() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    trailer_text = "".join(parsed.trailer)
    assert "## Known Debt" in trailer_text
    assert "## Key Rules" in trailer_text


def test_parse_memory_date_range_picks_latest() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_DATE_RANGE_HEADING)
    assert parsed.sessions[0].date == _dt.date(2026, 4, 23)
    assert parsed.sessions[1].date == _dt.date(2026, 4, 1)


def test_parse_memory_high_priority_flag() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_HIGH_PRIORITY)
    assert parsed.sessions[0].high_priority is True
    assert all(s.high_priority is False for s in parsed.sessions[1:])


# ---------------------------------------------------------------------------
# partition_sessions
# ---------------------------------------------------------------------------


def test_partition_keep_zero_ejects_all_non_hp(tmp_path: Path) -> None:
    del tmp_path
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    preserved, ejected = mod.partition_sessions(parsed.sessions, keep=0)
    assert preserved == []
    assert len(ejected) == 3


def test_partition_keep_two_preserves_two_most_recent() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    preserved, ejected = mod.partition_sessions(parsed.sessions, keep=2)
    preserved_headings = [s.heading for s in preserved]
    ejected_headings = [s.heading for s in ejected]
    # Middle + Newest preserved; Oldest ejected.
    assert any("Middle" in h for h in preserved_headings)
    assert any("Newest" in h for h in preserved_headings)
    assert any("Oldest" in h for h in ejected_headings)


def test_partition_preserves_source_order() -> None:
    """Preserved sessions retain their source order (no re-sort)."""
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    preserved, _ = mod.partition_sessions(parsed.sessions, keep=2)
    # Source order was Oldest → Middle → Newest; preserved should be Middle → Newest.
    assert "Middle" in preserved[0].heading
    assert "Newest" in preserved[1].heading


def test_partition_high_priority_always_preserved() -> None:
    """High-priority sessions never eject, even when keep=0."""
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_HIGH_PRIORITY)
    preserved, ejected = mod.partition_sessions(parsed.sessions, keep=0)
    # The Phase-Closeout session is 2025-06-01 and HP; it must be preserved.
    hp_preserved = [s for s in preserved if s.high_priority]
    assert len(hp_preserved) == 1
    assert "Phase Closeout" in hp_preserved[0].heading
    # All 4 non-HP sessions ejected.
    assert len(ejected) == 4


def test_partition_high_priority_plus_recent_kept_together() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_HIGH_PRIORITY)
    preserved, ejected = mod.partition_sessions(parsed.sessions, keep=2)
    # HP session + 2 most-recent non-HP = 3 preserved.
    assert len(preserved) == 3
    assert len(ejected) == 2
    # Preserved retains source order: HP (first), then Routine C, then Routine D.
    assert "Phase Closeout" in preserved[0].heading
    assert "Routine C" in preserved[1].heading
    assert "Routine D" in preserved[2].heading


def test_partition_rejects_negative_keep() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    try:
        mod.partition_sessions(parsed.sessions, keep=-1)
    except ValueError as e:
        assert "keep" in str(e)
    else:
        raise AssertionError("expected ValueError for negative keep")


# ---------------------------------------------------------------------------
# render_compacted
# ---------------------------------------------------------------------------


def test_render_compacted_roundtrip_no_ejection() -> None:
    """When nothing is ejected, rendered output equals original input."""
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    preserved, ejected = mod.partition_sessions(parsed.sessions, keep=99)
    assert ejected == []
    rendered = mod.render_compacted(parsed, preserved)
    assert rendered == _WITH_SESSIONS


def test_render_compacted_drops_ejected_blocks() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    preserved, _ = mod.partition_sessions(parsed.sessions, keep=1)
    rendered = mod.render_compacted(parsed, preserved)
    assert "Oldest" not in rendered
    assert "Middle" not in rendered
    assert "Newest" in rendered
    # Anchor + trailer still present.
    assert "## Operational Tips" in rendered
    assert "## Known Debt" in rendered


# ---------------------------------------------------------------------------
# render_ejection
# ---------------------------------------------------------------------------


def test_render_ejection_has_timestamp_header_and_body() -> None:
    mod = _load_module()
    parsed = mod.parse_memory(_WITH_SESSIONS)
    _, ejected = mod.partition_sessions(parsed.sessions, keep=1)
    now = _dt.datetime(2026, 5, 1, 12, 0, 0, tzinfo=_dt.UTC)
    rendered = mod.render_ejection(ejected, now=now)
    assert "memory_compact ejection" in rendered
    assert "2026-05-01T12:00:00" in rendered
    assert "2 session(s)" in rendered
    assert "Oldest" in rendered
    assert "Middle" in rendered


# ---------------------------------------------------------------------------
# CLI smoke
# ---------------------------------------------------------------------------


def _write_source(tmp_path: Path, body: str) -> Path:
    src = tmp_path / "MEMORY.md"
    src.write_text(body, encoding="utf-8")
    return src


def test_cli_dry_run_default_does_not_modify(tmp_path: Path) -> None:
    src = _write_source(tmp_path, _WITH_SESSIONS)
    dest = tmp_path / "session_history.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(src),
            "--dest",
            str(dest),
            "--keep",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Dry-run" in result.stdout
    # No changes to either file.
    assert src.read_text(encoding="utf-8") == _WITH_SESSIONS
    assert not dest.exists()


def test_cli_write_modifies_source_and_appends_dest(tmp_path: Path) -> None:
    src = _write_source(tmp_path, _WITH_SESSIONS)
    dest = tmp_path / "session_history.md"
    dest.write_text("# Session History\n\nPrior content.\n", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(src),
            "--dest",
            str(dest),
            "--keep",
            "1",
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    new_src = src.read_text(encoding="utf-8")
    assert "Newest" in new_src
    assert "Oldest" not in new_src
    assert "Middle" not in new_src
    # Trailer preserved.
    assert "## Known Debt" in new_src

    appended = dest.read_text(encoding="utf-8")
    # Original destination content preserved + new ejection appended.
    assert "Prior content" in appended
    assert "memory_compact ejection" in appended
    assert "Oldest" in appended
    assert "Middle" in appended


def test_cli_missing_source_exits_two(tmp_path: Path) -> None:
    missing = tmp_path / "nope.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--source", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "source not found" in result.stderr


def test_cli_default_dest_uses_source_dir(tmp_path: Path) -> None:
    src = _write_source(tmp_path, _WITH_SESSIONS)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(src),
            "--keep",
            "1",
            "--write",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    default_dest = tmp_path / "session_history.md"
    assert default_dest.exists()
    assert "Oldest" in default_dest.read_text(encoding="utf-8")

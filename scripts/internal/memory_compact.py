#!/usr/bin/env python3
"""MEMORY.md compaction script (Primitive C deliverable C.10).

Per Primitive C shaping §5.1 row C.10
(``plans/steward_platform/3_primitive_C/shaping.md``). MEMORY.md
accumulates per-session narrative blocks; unbounded growth breaks the
agent-readability scorecard item 6 ("MEMORY.md indexes rather than
recaps"). This script compacts the file by ejecting older session
blocks into a history file while preserving the top-level index,
governing-plan status, and the N most recent session blocks.

**Schema-defined preservation rule:**

* **Anchor region** (always preserved in place) — everything from the
  file start through the final non-session heading before the first
  session block. Examples: document title, "Operational Tips",
  "Governing Plans" table, "Browser Game Hosting: COMPLETE" section,
  the "Agentic Orchestration Platform" intro (up to but not including
  its first session).
* **Session block** — a contiguous region beginning at an H3 heading
  matching ``^### Session`` or an H2 heading matching ``^## Session``,
  and running up to the next session heading or the next H2 heading
  of non-session type, whichever comes first.
* **High-priority session** — any session block whose heading contains
  one of the tokens in ``HIGH_PRIORITY_TOKENS`` (e.g. "Phase Closeout",
  "Platform-10 COMPLETE"). High-priority sessions are never ejected.
* **Trailing region** — anything after the last session block (e.g.
  "Known Debt", "Key Rules", "Key Files") is always preserved in
  place.

**Compaction operation:**

1. Parse the source file into (anchor, sessions, trailer).
2. Partition sessions into (preserved, ejected) per the rule:
   * Always preserve high-priority sessions.
   * Of the remaining, preserve the ``--keep`` most recent by the
     date extracted from the heading (ISO YYYY-MM-DD substring).
   * Eject the rest.
3. Emit the ejected blocks to ``--dest`` (prepended with a
   divider + timestamp). If ``--dest`` does not exist it is created.
4. Rewrite the source as anchor + preserved sessions + trailer.

``--dry-run`` (default) prints a summary to stdout and makes no
changes. ``--write`` performs the compaction.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


# Session heading: H2 or H3 starting with "Session" or "Sessions".
_SESSION_HEADING_RE = re.compile(r"^(#{2,3})\s+Sessions?\b", re.IGNORECASE)
# Non-session H2 heading (terminates a session block when we encounter one).
_H2_HEADING_RE = re.compile(r"^##\s+")
# ISO date substring (YYYY-MM-DD) used to rank sessions by recency.
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

# Heading-substring tokens that mark a session as high-priority (never
# ejected). Case-insensitive substring match on the heading line.
HIGH_PRIORITY_TOKENS: tuple[str, ...] = (
    "PHASE CLOSEOUT",
    "PLATFORM-10 COMPLETE",
    "PROMOTED",
    "KILL CRITERION",
    "INCIDENT",
)


@dataclass(frozen=True)
class SessionBlock:
    """One session narrative block parsed from MEMORY.md."""

    heading: str
    lines: tuple[str, ...]
    date: _dt.date | None
    high_priority: bool

    def is_session(self) -> bool:
        return True


@dataclass(frozen=True)
class ParsedMemory:
    """MEMORY.md split into anchor / sessions / trailer."""

    anchor: tuple[str, ...]
    sessions: tuple[SessionBlock, ...]
    trailer: tuple[str, ...]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _heading_is_session(line: str) -> bool:
    return bool(_SESSION_HEADING_RE.match(line))


def _heading_is_terminator(line: str) -> bool:
    """Return True when *line* terminates the session region.

    A session region ends when we hit either a new session heading OR
    an H2 heading that is NOT itself a session heading. The latter
    case marks the start of the trailer (e.g. "## Known Debt").
    """
    if _heading_is_session(line):
        return True
    if _H2_HEADING_RE.match(line):
        return True
    return False


def _extract_date(heading: str) -> _dt.date | None:
    """Extract the first ISO date from *heading*, if any.

    Multiple dates in a heading (e.g. "Session 2026-04-22c → 2026-04-23")
    resolve to the **latest** date found — sessions span ranges and
    the later date is the most recent touchpoint.
    """
    candidates: list[_dt.date] = []
    for m in _DATE_RE.finditer(heading):
        try:
            candidates.append(_dt.date.fromisoformat(m.group(1)))
        except ValueError:
            continue
    if not candidates:
        return None
    return max(candidates)


def _is_high_priority(heading: str) -> bool:
    upper = heading.upper()
    return any(tok in upper for tok in HIGH_PRIORITY_TOKENS)


def parse_memory(text: str) -> ParsedMemory:
    """Split *text* into anchor / sessions / trailer per the schema."""
    lines = text.splitlines(keepends=True)
    n = len(lines)

    # Anchor: everything up to (but not including) the first session heading.
    anchor_end = n
    for i, line in enumerate(lines):
        if _heading_is_session(line):
            anchor_end = i
            break

    anchor = tuple(lines[:anchor_end])

    # Sessions: from anchor_end to the first non-session H2 heading
    # encountered AFTER at least one session block. If we encounter a
    # non-session H2 before any session (unlikely — anchor_end would
    # already be n), there are no sessions.
    sessions: list[SessionBlock] = []
    i = anchor_end
    trailer_start = n
    while i < n:
        line = lines[i]
        if _heading_is_session(line):
            heading = line.rstrip("\n")
            block_start = i
            i += 1
            while i < n and not _heading_is_terminator(lines[i]):
                i += 1
            # i now points to either next heading or EOF
            block_lines = tuple(lines[block_start:i])
            sessions.append(
                SessionBlock(
                    heading=heading,
                    lines=block_lines,
                    date=_extract_date(heading),
                    high_priority=_is_high_priority(heading),
                )
            )
            # If terminator is a non-session H2, that's the trailer start.
            if (
                i < n
                and _H2_HEADING_RE.match(lines[i])
                and not _heading_is_session(lines[i])
            ):
                trailer_start = i
                break
            # Otherwise loop continues at the next session heading.
            continue
        # Non-session line between sessions or before first session — we
        # only reach here if anchor parsing left a gap, which shouldn't
        # happen given _heading_is_session is the anchor terminator. Be
        # defensive and treat as trailer start.
        trailer_start = i
        break

    trailer = tuple(lines[trailer_start:])

    return ParsedMemory(anchor=anchor, sessions=tuple(sessions), trailer=trailer)


# ---------------------------------------------------------------------------
# Partition rule (high-priority preservation, recency ranking)
# ---------------------------------------------------------------------------


def partition_sessions(
    sessions: tuple[SessionBlock, ...],
    *,
    keep: int,
) -> tuple[list[SessionBlock], list[SessionBlock]]:
    """Return ``(preserved, ejected)`` per the schema-defined rule.

    Preservation order in the rewritten source file matches the
    original source order (no reordering).
    """
    if keep < 0:
        raise ValueError(f"keep must be ≥ 0; got {keep}")

    # High-priority: always preserved, regardless of --keep.
    high_priority_set = {id(s) for s in sessions if s.high_priority}
    non_hp = [s for s in sessions if id(s) not in high_priority_set]

    # Rank non-HP by date (most recent first); tie-break on source order
    # (later source index wins, matching "most recent" intuition).
    indexed = list(enumerate(non_hp))
    _sentinel = _dt.date.min

    def _sort_key(pair: tuple[int, SessionBlock]) -> tuple[_dt.date, int]:
        idx, block = pair
        return (block.date or _sentinel, idx)

    indexed.sort(key=_sort_key, reverse=True)
    keep_ids = {id(pair[1]) for pair in indexed[:keep]}

    preserved: list[SessionBlock] = []
    ejected: list[SessionBlock] = []
    for block in sessions:
        if id(block) in high_priority_set or id(block) in keep_ids:
            preserved.append(block)
        else:
            ejected.append(block)
    return preserved, ejected


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_compacted(parsed: ParsedMemory, preserved: list[SessionBlock]) -> str:
    """Render the new source-file contents."""
    parts: list[str] = []
    parts.append("".join(parsed.anchor))
    for block in preserved:
        parts.append("".join(block.lines))
    parts.append("".join(parsed.trailer))
    return "".join(parts)


def render_ejection(
    ejected: list[SessionBlock],
    *,
    now: _dt.datetime | None = None,
) -> str:
    """Render the block that gets appended to the history file."""
    if now is None:
        now = _dt.datetime.now(_dt.UTC)
    header = (
        f"\n<!-- memory_compact ejection "
        f"at {now.isoformat(timespec='seconds')}; "
        f"{len(ejected)} session(s) -->\n\n"
    )
    body = "".join("".join(b.lines) for b in ejected)
    return header + body


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _summarize(preserved: list[SessionBlock], ejected: list[SessionBlock]) -> str:
    def _label(b: SessionBlock) -> str:
        tag = " [HP]" if b.high_priority else ""
        date = b.date.isoformat() if b.date else "—"
        return f"  - {date}{tag}: {b.heading}"

    lines = [
        f"Preserved ({len(preserved)}):",
        *[_label(b) for b in preserved],
        f"Ejected ({len(ejected)}):",
        *[_label(b) for b in ejected],
    ]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="memory_compact",
        description=(
            "Compact MEMORY.md by ejecting older session blocks to a "
            "history file. See plans/steward_platform/3_primitive_C/"
            "shaping.md §5.1 row C.10 for the schema."
        ),
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to MEMORY.md",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination history file (default: <source-dir>/session_history.md)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=3,
        help="Number of most-recent non-HP sessions to preserve (default: 3)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print summary; make no changes (default)",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Perform the compaction (modify source, append to dest)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    source: Path = args.source
    if not source.exists():
        sys.stderr.write(f"memory_compact: source not found: {source}\n")
        return 2

    dest: Path = args.dest or (source.parent / "session_history.md")

    text = source.read_text(encoding="utf-8")
    parsed = parse_memory(text)
    preserved, ejected = partition_sessions(parsed.sessions, keep=args.keep)

    sys.stdout.write(_summarize(preserved, ejected) + "\n")

    if args.write:
        new_source = render_compacted(parsed, preserved)
        if ejected:
            ejection = render_ejection(ejected)
            # Append (create if missing).
            existing = dest.read_text(encoding="utf-8") if dest.exists() else ""
            dest.write_text(existing + ejection, encoding="utf-8")
        source.write_text(new_source, encoding="utf-8")
        sys.stdout.write(
            f"\nWrote {source} ({len(preserved)} sessions preserved); "
            f"appended {len(ejected)} session(s) to {dest}.\n"
        )
    else:
        sys.stdout.write("\nDry-run: no changes written. Pass --write to commit.\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

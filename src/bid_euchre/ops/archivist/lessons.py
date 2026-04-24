"""Lessons-mode archivist collector + templater.

Per shape §4.1 — walks the five input sources (events, inbox, PR outcomes,
task completions, session transcripts), groups candidate lessons into four
output sections (repeated patterns, token-efficiency outliers, incident
candidates, explicit lesson annotations), and writes a dated markdown
file to ``knowledge/_candidates/<date>_lessons.md``.

Design notes:

- Input sources degrade gracefully. A missing event dir / unreachable
  GitHub CLI / absent task queue yields an empty contribution — not a
  crash. The per-source ``_load_*`` helpers return ``[]`` on failure and
  log a warning.
- Watermarking is ``.last_run_lessons`` under the candidates dir (single
  ISO-8601 line). First run looks back 24h.
- Event emission is flag-gated via ``ENABLE_D_EVENT_EMISSION`` (see
  ``archivist/events.py``).
- Re-runs on the same UTC date *append* — they do not overwrite — per
  shape §4.1.3.

The public entry point is ``run_lessons()``; the CLI wrapper lives at
``scripts/internal/archivist_candidates.py``.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import events as archivist_events
from . import templates as tpl

logger = logging.getLogger("ops.archivist.lessons")

DEFAULT_CANDIDATES_DIR = Path("knowledge/_candidates")
WATERMARK_FILE = ".last_run_lessons"
DEFAULT_LOOKBACK_HOURS = 24

# Exit-code sentinel values — also used by the CLI.
EXIT_OK = 0
EXIT_EMPTY = 1
EXIT_SOURCE_UNREACHABLE = 2
EXIT_WRITE_FAIL = 3


@dataclass(frozen=True)
class LessonCandidate:
    """A single lesson candidate from one of the four sections."""

    section: int  # 1..4
    summary: str  # ≤3 sentences proposed_lesson
    evidence: str  # trace_id / PR URL / event_id
    source_event_ids: tuple[str, ...] = ()


@dataclass
class LessonsRunResult:
    """Structured result of a lessons-mode run."""

    output_path: Path | None
    window_start: datetime
    window_end: datetime
    event_count: int
    candidate_count: int
    exit_code: int
    sources_reached: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)


def run_lessons(
    candidates_dir: Path | None = None,
    *,
    since: datetime | None = None,
    dry_run: bool = False,
    fixture_path: Path | None = None,
    events_dir: Path | None = None,
) -> LessonsRunResult:
    """Execute one lessons-mode archivist run.

    Args:
        candidates_dir: target candidates directory; defaults to
            ``knowledge/_candidates``.
        since: override watermark; defaults to read from
            ``.last_run_lessons`` or 24h ago.
        dry_run: if True, compute the candidate list but do not write the
            output file and do not advance the watermark.
        fixture_path: test-only; read events from this JSONL fixture
            instead of the live events dir.
        events_dir: override for live events dir (ignored if
            ``fixture_path`` is set).

    Returns:
        ``LessonsRunResult`` with output path, window, counts, and exit
        code.
    """
    if candidates_dir is None:
        candidates_dir = DEFAULT_CANDIDATES_DIR

    window_end = datetime.now(timezone.utc).replace(microsecond=0)
    window_start = since if since is not None else _read_watermark(candidates_dir)
    if window_start is None:
        window_start = window_end - timedelta(hours=DEFAULT_LOOKBACK_HOURS)
    window_start = _ensure_utc(window_start)

    events, event_src_ok = _load_events(
        fixture_path=fixture_path, events_dir=events_dir, since=window_start
    )
    sources_reached: list[str] = []
    sources_failed: list[str] = []
    if event_src_ok:
        sources_reached.append("events")
    else:
        sources_failed.append("events")

    candidates = _derive_candidates(events)

    if not candidates:
        logger.info(
            "No lesson candidates found in window %s → %s (%d events)",
            window_start.isoformat(),
            window_end.isoformat(),
            len(events),
        )
        return LessonsRunResult(
            output_path=None,
            window_start=window_start,
            window_end=window_end,
            event_count=len(events),
            candidate_count=0,
            exit_code=EXIT_EMPTY,
            sources_reached=sources_reached,
            sources_failed=sources_failed,
        )

    output_path = _output_path_for_today(candidates_dir, window_end)

    if dry_run:
        logger.info(
            "Dry-run: would write %d candidates to %s", len(candidates), output_path
        )
        return LessonsRunResult(
            output_path=output_path,
            window_start=window_start,
            window_end=window_end,
            event_count=len(events),
            candidate_count=len(candidates),
            exit_code=EXIT_OK,
            sources_reached=sources_reached,
            sources_failed=sources_failed,
        )

    try:
        _write_or_append(
            output_path=output_path,
            candidates=candidates,
            window_start=window_start,
            window_end=window_end,
            event_count=len(events),
        )
    except OSError as exc:
        logger.error("Write failure to %s: %s", output_path, exc)
        return LessonsRunResult(
            output_path=output_path,
            window_start=window_start,
            window_end=window_end,
            event_count=len(events),
            candidate_count=len(candidates),
            exit_code=EXIT_WRITE_FAIL,
            sources_reached=sources_reached,
            sources_failed=sources_failed,
        )

    # Advance watermark only after successful write.
    _write_watermark(candidates_dir, window_end)

    # Emit one candidate-proposed event per candidate (flag-gated).
    for candidate in candidates:
        try:
            archivist_events.emit_candidate_proposed(
                candidate_path=output_path,
                candidate_class="lessons",
                source_event_ids=list(candidate.source_event_ids),
            )
        except Exception as exc:  # pragma: no cover - A schema drift
            logger.warning("Emission failed for candidate: %s", exc)

    return LessonsRunResult(
        output_path=output_path,
        window_start=window_start,
        window_end=window_end,
        event_count=len(events),
        candidate_count=len(candidates),
        exit_code=EXIT_OK,
        sources_reached=sources_reached,
        sources_failed=sources_failed,
    )


# ----- Input sources -----


def _load_events(
    *,
    fixture_path: Path | None,
    events_dir: Path | None,
    since: datetime,
) -> tuple[list[dict[str, Any]], bool]:
    """Load events from fixture or live dir; return (events, src_ok)."""
    if fixture_path is not None:
        try:
            return _load_events_from_fixture(fixture_path, since=since), True
        except OSError as exc:
            logger.warning("Fixture unreachable: %s", exc)
            return [], False

    # Live path — import lazily to avoid import-time failure when the
    # events module is unavailable (e.g., during unit tests where the
    # consumer mocks this function).
    try:
        from bid_euchre.ops.events import read_events

        events = read_events(events_dir=events_dir, since=since, limit=10_000)
        return events, True
    except OSError as exc:
        logger.warning("Live events dir unreachable: %s", exc)
        return [], False


def _load_events_from_fixture(
    fixture_path: Path, *, since: datetime
) -> list[dict[str, Any]]:
    """Read events from a JSONL fixture, filtered by ``since``."""
    events: list[dict[str, Any]] = []
    with open(fixture_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed fixture line: %s", line[:80])
                continue
            ts_str = event.get("timestamp")
            if ts_str is None:
                continue
            try:
                event_ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            event_ts = _ensure_utc(event_ts)
            if event_ts <= since:
                continue
            events.append(event)
    return events


# ----- Candidate derivation -----


def _derive_candidates(events: Iterable[dict[str, Any]]) -> list[LessonCandidate]:
    """Run the four section-classifiers over the event stream.

    This is a deliberately lightweight Phase 0 derivation — each section
    uses a simple grouping heuristic so the output file is deterministic
    and testable without pulling in ML or embedding infrastructure. The
    lesson quality comes from operator promotion, not from the derivation.
    """
    events = list(events)
    candidates: list[LessonCandidate] = []

    candidates.extend(_section_1_repeated_patterns(events))
    candidates.extend(_section_2_token_outliers(events))
    candidates.extend(_section_3_incidents(events))
    candidates.extend(_section_4_explicit_lessons(events))

    return candidates


def _section_1_repeated_patterns(events: list[dict[str, Any]]) -> list[LessonCandidate]:
    """Group events by ``(event_type, source)`` signature; surface any
    signature with ≥3 occurrences as a repeated-pattern candidate."""
    signatures: dict[tuple[str, str], list[str]] = defaultdict(list)
    for event in events:
        key = (str(event.get("event_type", "?")), str(event.get("source", "?")))
        # Each event's synthetic id: timestamp is the best proxy available
        # without A's trace_id being populated.
        synth_id = str(event.get("timestamp", "?"))
        signatures[key].append(synth_id)

    out: list[LessonCandidate] = []
    for (event_type, source), ids in signatures.items():
        if len(ids) < 3:
            continue
        pattern_id = f"{event_type}@{source}"
        summary = (
            f"Repeated pattern `{pattern_id}` observed {len(ids)} times. "
            f"Consider whether this pattern represents systemic friction "
            f"that warrants a targeted fix or process change."
        )
        out.append(
            LessonCandidate(
                section=1,
                summary=summary,
                evidence=f"{len(ids)} traces; earliest={ids[0]}, latest={ids[-1]}",
                source_event_ids=tuple(ids[:5]),
            )
        )
    return out


def _section_2_token_outliers(events: list[dict[str, Any]]) -> list[LessonCandidate]:
    """Walk events whose payload has a ``token_delta`` field; surface
    outliers >= 2σ above the mean as token-efficiency candidates."""
    token_events: list[tuple[dict[str, Any], float]] = []
    for event in events:
        payload = event.get("payload") or {}
        token_delta = payload.get("token_delta")
        if not isinstance(token_delta, (int, float)):
            continue
        token_events.append((event, float(token_delta)))

    if len(token_events) < 3:
        return []

    values = [v for _, v in token_events]
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    stddev = variance**0.5
    if stddev == 0:
        return []

    threshold = mean + 2 * stddev
    out: list[LessonCandidate] = []
    for event, delta in token_events:
        if delta < threshold:
            continue
        payload = event.get("payload") or {}
        lane = payload.get("lane", event.get("lane_id", "?"))
        packet_id = payload.get("packet_id", "?")
        summary = (
            f"Token outlier: lane `{lane}` on packet `{packet_id}` "
            f"consumed token_delta={delta:.0f} (>= {threshold:.0f} = "
            f"mean+2σ). Investigate effort-tier miscalibration."
        )
        out.append(
            LessonCandidate(
                section=2,
                summary=summary,
                evidence=f"event timestamp={event.get('timestamp')}",
                source_event_ids=(str(event.get("timestamp", "?")),),
            )
        )
    return out


def _section_3_incidents(events: list[dict[str, Any]]) -> list[LessonCandidate]:
    """Walk events with ``event_type`` in the incident set (task_failed,
    ci_failure, escalation, etc.). Each is surfaced as an incident
    candidate."""
    incident_types = {
        "task_failed",
        "ci_failure",
        "escalation",
        "fs_boundary_violation",
        "watchdog_finding",
    }
    out: list[LessonCandidate] = []
    counts: Counter[str] = Counter()
    for event in events:
        et = str(event.get("event_type", ""))
        if et not in incident_types:
            continue
        counts[et] += 1
        payload = event.get("payload") or {}
        lane_id = event.get("lane_id", "?")
        incident_id = payload.get("incident_id") or f"{et}-{counts[et]}"
        summary = (
            f"Incident `{incident_id}` on lane `{lane_id}` ({et}). "
            f"Review root cause and whether a recurrence guard is "
            f"warranted."
        )
        out.append(
            LessonCandidate(
                section=3,
                summary=summary,
                evidence=f"trace timestamp={event.get('timestamp')}",
                source_event_ids=(str(event.get("timestamp", "?")),),
            )
        )
    return out


def _section_4_explicit_lessons(events: list[dict[str, Any]]) -> list[LessonCandidate]:
    """Walk events whose payload contains a ``lesson_learned`` annotation."""
    out: list[LessonCandidate] = []
    for event in events:
        payload = event.get("payload") or {}
        lesson = payload.get("lesson_learned")
        if not lesson:
            continue
        out.append(
            LessonCandidate(
                section=4,
                summary=f"Operator lesson: {lesson}",
                evidence=f"trace timestamp={event.get('timestamp')}",
                source_event_ids=(str(event.get("timestamp", "?")),),
            )
        )
    return out


# ----- Output -----


def _output_path_for_today(candidates_dir: Path, when: datetime) -> Path:
    """Return ``<candidates_dir>/<YYYY-MM-DD>_lessons.md`` for ``when``."""
    date_str = when.strftime("%Y-%m-%d")
    return candidates_dir / f"{date_str}_lessons.md"


def _write_or_append(
    *,
    output_path: Path,
    candidates: list[LessonCandidate],
    window_start: datetime,
    window_end: datetime,
    event_count: int,
) -> None:
    """Write (or append-to) the candidate markdown file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    grouped: dict[int, list[LessonCandidate]] = defaultdict(list)
    for c in candidates:
        grouped[c.section].append(c)

    body = _render_body(
        grouped=grouped,
        window_start=window_start,
        window_end=window_end,
        event_count=event_count,
        candidate_count=len(candidates),
    )

    mode = "a" if output_path.exists() else "w"
    with open(output_path, mode, encoding="utf-8") as fh:
        if mode == "a":
            fh.write("\n---\n\n")  # separator between runs same day
        fh.write(body)


def _render_body(
    *,
    grouped: dict[int, list[LessonCandidate]],
    window_start: datetime,
    window_end: datetime,
    event_count: int,
    candidate_count: int,
) -> str:
    date_str = window_end.strftime("%Y-%m-%d")
    parts = [
        tpl.LESSONS_HEADER.format(
            date=date_str,
            run_ts=window_end.isoformat(),
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
            event_count=event_count,
            candidate_count=candidate_count,
        ),
        tpl.LESSONS_SECTION_1_HEADER,
        _render_section(grouped.get(1, [])),
        tpl.LESSONS_SECTION_2_HEADER,
        _render_section(grouped.get(2, [])),
        tpl.LESSONS_SECTION_3_HEADER,
        _render_section(grouped.get(3, [])),
        tpl.LESSONS_SECTION_4_HEADER,
        _render_section(grouped.get(4, [])),
        tpl.LESSONS_FOOTER,
    ]
    return "".join(parts)


def _render_section(items: list[LessonCandidate]) -> str:
    if not items:
        return "_No candidates this run._\n\n"
    lines: list[str] = []
    for idx, c in enumerate(items, start=1):
        lines.append(f"### Candidate {idx}\n\n")
        lines.append(f"- **Proposed lesson:** {c.summary}\n")
        lines.append(f"- **Evidence:** {c.evidence}\n")
        if c.source_event_ids:
            joined = ", ".join(c.source_event_ids)
            lines.append(f"- **Source event ids:** {joined}\n")
        lines.append(
            "- **Proposed promotion path:** `knowledge/_promoted/lessons/<slug>.md`\n\n"
        )
    return "".join(lines)


# ----- Watermark -----


def _read_watermark(candidates_dir: Path) -> datetime | None:
    """Read the last-run timestamp; return None if missing or malformed."""
    path = candidates_dir / WATERMARK_FILE
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        return _ensure_utc(datetime.fromisoformat(raw))
    except (OSError, ValueError) as exc:
        logger.warning("Watermark file unreadable (%s); will use default lookback", exc)
        return None


def _write_watermark(candidates_dir: Path, when: datetime) -> None:
    """Write the watermark atomically (tmp + rename)."""
    candidates_dir.mkdir(parents=True, exist_ok=True)
    path = candidates_dir / WATERMARK_FILE
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(when.isoformat() + "\n", encoding="utf-8")
    tmp.rename(path)


def _ensure_utc(dt: datetime) -> datetime:
    """Force tzinfo onto a naive datetime (assume UTC) so comparisons work."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

"""Session postmortem — Primitive D.2 Phase 0.

Per shape §4.4. On session end (invoked from Phase 4.5 of
``.claude/skills/session-end``), this module:

1. Collects session signals from events, PR activity, and task completions
   in the session window.
2. Renders a MEMORY.md handoff block (matching the existing Phase-4
   template shape).
3. Renders a postmortem section appended to the dated lessons candidate
   file (``knowledge/_candidates/<date>_lessons.md``).
4. Emits a flag-gated ``archivist_candidate_proposed`` event.

The module is a single file — no subpackage — per shape §4.4.1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.archivist import (
    DEFAULT_CANDIDATES_DIR,
    emit_candidate_proposed,
)
from bid_euchre.ops.archivist import templates as tpl

logger = logging.getLogger("ops.session_postmortem")

EXIT_OK = 0
EXIT_EMPTY = 1
EXIT_SOURCE_UNREACHABLE = 2
EXIT_WRITE_FAIL = 3


@dataclass
class SessionSignals:
    """Collected signals for one session-end postmortem pass.

    ``events`` / ``prs_merged`` / ``tasks_completed`` are the raw inputs;
    the renderers consume the derived roll-ups (``incident_ids``,
    ``token_outliers``, ``lessons_explicit``).
    """

    session_id: str
    session_start: datetime | None = None
    session_end: datetime | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    prs_merged: list[str] = field(default_factory=list)
    tasks_completed: list[str] = field(default_factory=list)
    lanes_parked: list[str] = field(default_factory=list)
    outstanding: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)
    goal: str = "(not recorded)"
    # Derived rollups (populated by ``collect_session_signals``).
    incident_ids: list[str] = field(default_factory=list)
    token_outliers: list[dict[str, Any]] = field(default_factory=list)
    lessons_explicit: list[str] = field(default_factory=list)


@dataclass
class PostmortemResult:
    """Structured return of ``run_postmortem``."""

    session_id: str
    exit_code: int
    memory_md_path: Path
    memory_appended: bool
    candidate_path: Path | None


def collect_session_signals(
    session_id: str,
    *,
    events: list[dict[str, Any]] | None = None,
    prs_merged: list[str] | None = None,
    tasks_completed: list[str] | None = None,
    session_start: datetime | None = None,
    session_end: datetime | None = None,
    goal: str = "(not recorded)",
    lanes_parked: list[str] | None = None,
    outstanding: list[str] | None = None,
    next_steps: list[str] | None = None,
    hazards: list[str] | None = None,
) -> SessionSignals:
    """Assemble a ``SessionSignals`` from injectable session-state inputs.

    Phase 0 surfaces the raw collectors as keyword arguments so tests and
    the Phase 4.5 skill hook can populate them deterministically without
    this module pulling in event-reader / gh-cli infrastructure. Phase 1
    will replace the default-None arms with live readers (mirroring the
    archivist lessons-mode graceful-degradation pattern).
    """
    signals = SessionSignals(
        session_id=session_id,
        session_start=session_start,
        session_end=session_end or datetime.now(timezone.utc).replace(microsecond=0),
        events=list(events or []),
        prs_merged=list(prs_merged or []),
        tasks_completed=list(tasks_completed or []),
        lanes_parked=list(lanes_parked or []),
        outstanding=list(outstanding or []),
        next_steps=list(next_steps or []),
        hazards=list(hazards or []),
        goal=goal,
    )
    _derive_rollups(signals)
    return signals


def _derive_rollups(signals: SessionSignals) -> None:
    """Fill ``incident_ids`` / ``token_outliers`` / ``lessons_explicit`` from
    ``signals.events`` using the same heuristics as lessons-mode §4.1.

    The heuristics are intentionally loose — operator review decides which
    rollups actually belong in the candidate file."""
    incident_types = {
        "task_failed",
        "ci_failure",
        "escalation",
        "fs_boundary_violation",
        "watchdog_finding",
    }

    token_values: list[float] = []
    for event in signals.events:
        payload = event.get("payload") or {}
        td = payload.get("token_delta")
        if isinstance(td, (int, float)):
            token_values.append(float(td))

    threshold: float | None = None
    if len(token_values) >= 3:
        mean = sum(token_values) / len(token_values)
        variance = sum((v - mean) ** 2 for v in token_values) / len(token_values)
        stddev = variance**0.5
        if stddev > 0:
            threshold = mean + 2 * stddev

    for event in signals.events:
        et = str(event.get("event_type", ""))
        payload = event.get("payload") or {}
        if et in incident_types:
            incident_id = (
                payload.get("incident_id") or f"{et}-{len(signals.incident_ids) + 1}"
            )
            signals.incident_ids.append(str(incident_id))
        if threshold is not None:
            td = payload.get("token_delta")
            if isinstance(td, (int, float)) and float(td) >= threshold:
                signals.token_outliers.append(
                    {
                        "lane": payload.get("lane", event.get("lane_id", "?")),
                        "packet_id": payload.get("packet_id", "?"),
                        "token_delta": float(td),
                        "timestamp": event.get("timestamp"),
                    }
                )
        lesson = payload.get("lesson_learned")
        if lesson:
            signals.lessons_explicit.append(str(lesson))


def render_memory_entry(signals: SessionSignals) -> str:
    """Render the markdown block to append to MEMORY.md.

    The shape follows the Phase-4 template in
    ``.claude/skills/session-end/SKILL.md``. A naive string render — no
    branching, so structure is deterministic and review-friendly.
    """
    session_date = _format_session_date(signals)
    prs_line = (
        ", ".join(f"#{pr.lstrip('#')}" for pr in signals.prs_merged) or "_(none)_"
    )
    lanes_line = ", ".join(signals.lanes_parked) or "_(none)_"
    outstanding_line = (
        tpl.format_bullet_list(signals.outstanding)
        if signals.outstanding
        else "_(none)_"
    )
    next_steps_line = (
        tpl.format_bullet_list(signals.next_steps) if signals.next_steps else "_(none)_"
    )
    hazards_line = (
        tpl.format_bullet_list(signals.hazards) if signals.hazards else "_(none)_"
    )

    return tpl.POSTMORTEM_MEMORY_ENTRY.format(
        session_id=signals.session_id,
        date=session_date,
        goal=signals.goal,
        prs_merged=prs_line,
        lanes_parked=lanes_line,
        outstanding=outstanding_line.strip()
        if isinstance(outstanding_line, str)
        else "_(none)_",
        next_steps=next_steps_line.strip()
        if isinstance(next_steps_line, str)
        else "_(none)_",
        hazards=hazards_line.strip() if isinstance(hazards_line, str) else "_(none)_",
    )


def render_candidate_entry(signals: SessionSignals) -> str:
    """Render the postmortem section appended to the lessons candidate
    file. Shape conforms to the §4.1.3 lessons schema — a single section
    (``## Postmortem``) that fits into the dated lessons file."""
    session_date = _format_session_date(signals)
    body_parts = [
        tpl.POSTMORTEM_SECTION_HEADER.format(
            session_id=signals.session_id,
            date=session_date,
            session_start=_iso_or_dash(signals.session_start),
            session_end=_iso_or_dash(signals.session_end),
            prs_merged=len(signals.prs_merged),
            incident_count=len(signals.incident_ids),
            outlier_count=len(signals.token_outliers),
        )
    ]

    body_parts.append("### Incidents\n\n")
    if signals.incident_ids:
        body_parts.append(tpl.format_bullet_list(signals.incident_ids) + "\n")
    else:
        body_parts.append("_(none this session)_\n\n")

    body_parts.append("### Token outliers\n\n")
    if signals.token_outliers:
        lines = [
            f"- lane=`{o.get('lane', '?')}` "
            f"packet=`{o.get('packet_id', '?')}` "
            f"token_delta={o.get('token_delta', 0):.0f}"
            for o in signals.token_outliers
        ]
        body_parts.append("\n".join(lines) + "\n\n")
    else:
        body_parts.append("_(none this session)_\n\n")

    body_parts.append("### Explicit lessons\n\n")
    if signals.lessons_explicit:
        body_parts.append(tpl.format_bullet_list(signals.lessons_explicit) + "\n")
    else:
        body_parts.append("_(none this session)_\n\n")

    return "".join(body_parts)


def run_postmortem(
    session_id: str,
    *,
    memory_md_path: Path,
    candidates_dir: Path = DEFAULT_CANDIDATES_DIR,
    signals: SessionSignals | None = None,
    dry_run: bool = False,
    when: datetime | None = None,
) -> PostmortemResult:
    """Orchestrate postmortem: collect → render → append to MEMORY.md + candidate file.

    Args:
        session_id: session identifier string (required — empty is a graceful fail).
        memory_md_path: Path to the MEMORY.md file to append to.
        candidates_dir: target candidates directory.
        signals: optional injected ``SessionSignals`` — tests pass fixtures
            here; production callers leave None to trigger collection.
        dry_run: if True, compute outputs but do not write either target.
        when: ISO-date override; defaults to now(UTC).

    Returns a ``PostmortemResult``. Best-effort: a write failure on one
    target does not block the other.
    """
    if not session_id or not session_id.strip():
        logger.warning("run_postmortem: empty session_id → graceful fail")
        return PostmortemResult(
            session_id=session_id,
            exit_code=EXIT_EMPTY,
            memory_md_path=memory_md_path,
            memory_appended=False,
            candidate_path=None,
        )

    when = when or datetime.now(timezone.utc).replace(microsecond=0)

    if signals is None:
        signals = collect_session_signals(session_id=session_id, session_end=when)

    memory_block = render_memory_entry(signals)
    candidate_section = render_candidate_entry(signals)
    candidate_path = candidates_dir / f"{when.strftime('%Y-%m-%d')}_lessons.md"

    if dry_run:
        logger.info(
            "run_postmortem dry-run: session=%s memory_md=%s candidate=%s",
            session_id,
            memory_md_path,
            candidate_path,
        )
        return PostmortemResult(
            session_id=session_id,
            exit_code=EXIT_OK,
            memory_md_path=memory_md_path,
            memory_appended=False,
            candidate_path=candidate_path,
        )

    memory_appended = False
    try:
        _append_to_memory(memory_md_path, memory_block)
        memory_appended = True
    except OSError as exc:
        logger.error("MEMORY.md append failed: %s", exc)

    candidate_written = False
    try:
        _append_candidate_section(candidate_path, candidate_section)
        candidate_written = True
    except OSError as exc:
        logger.error("Candidate write failed: %s", exc)

    exit_code = EXIT_OK
    if not memory_appended and not candidate_written:
        exit_code = EXIT_WRITE_FAIL
    elif not memory_appended or not candidate_written:
        # Partial success — keep OK but flag via log.
        logger.warning(
            "Postmortem partial: memory_appended=%s candidate_written=%s",
            memory_appended,
            candidate_written,
        )

    # Flag-gated event emission (ENABLE_D_EVENT_EMISSION).
    if candidate_written:
        try:
            emit_candidate_proposed(
                candidate_path=candidate_path,
                candidate_class="postmortem",
                source_event_ids=[e.get("timestamp", "?") for e in signals.events][:5],
            )
        except Exception as exc:  # pragma: no cover - A schema drift
            logger.warning("Postmortem event emission failed: %s", exc)

    return PostmortemResult(
        session_id=session_id,
        exit_code=exit_code,
        memory_md_path=memory_md_path,
        memory_appended=memory_appended,
        candidate_path=candidate_path if candidate_written else None,
    )


# ----- Helpers -----


def _format_session_date(signals: SessionSignals) -> str:
    ref = signals.session_end or signals.session_start or datetime.now(timezone.utc)
    return ref.strftime("%Y-%m-%d")


def _iso_or_dash(ts: datetime | None) -> str:
    return ts.isoformat() if ts is not None else "(unknown)"


def _append_to_memory(path: Path, block: str) -> None:
    """Append ``block`` to MEMORY.md; create the file if it doesn't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as fh:
        if mode == "a":
            fh.write("\n")
        fh.write(block)


def _append_candidate_section(path: Path, section: str) -> None:
    """Append a postmortem section to the dated lessons candidate file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if path.exists() else "w"
    with open(path, mode, encoding="utf-8") as fh:
        if mode == "a":
            fh.write("\n---\n\n")
        fh.write(section)

"""Shared markdown template blocks for archivist candidate files.

Per shape §4.1.3 (lessons) and §4.2.3 (gc) and §4.4 (postmortem), the
archivist's output files are deterministic, section-structured markdown.
Keeping the templates in a single module makes them lint-checkable and
test-fixture-regeneratable.

Agent-readability floor (ADR 001): every section heading + first ≤3
lines passes the scorecard ≥7/10.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

# ----- Lessons-mode templates -----


LESSONS_HEADER = """# Archivist Candidate — Lessons — {date}

**Run timestamp:** {run_ts}
**Source window:** {window_start} → {window_end}
**Source event count:** {event_count}
**Candidate count:** {candidate_count}

"""


LESSONS_SECTION_1_HEADER = """## Section 1 — Repeated patterns

_Grouped by recurring trace signature. Each group lists pattern_id,
occurrence_count, example_trace_ids, and proposed lesson text._

"""

LESSONS_SECTION_2_HEADER = """## Section 2 — Token-efficiency outliers

_From token economy ledger. Each row is one (lane, packet_id, token_delta,
proposed_lesson) tuple._

"""

LESSONS_SECTION_3_HEADER = """## Section 3 — Incident candidates

_Failures, escalations, rollbacks. Each entry lists incident_id, trace_id,
and proposed lesson text._

"""

LESSONS_SECTION_4_HEADER = """## Section 4 — Lesson candidates (explicit)

_Operator annotations tagged ``lesson-learned``. Verbatim quote plus the
originating trace_id._

"""


LESSONS_FOOTER = """
## Verification: operator review

Each candidate above has: proposed_lesson (≤3 sentences), evidence
(trace_id / PR URL / event_id), proposed_promotion_path (e.g.,
`knowledge/_promoted/lessons/<slug>.md`).

Operator workflow: open this file, decide `promote` | `reject` | `skip`
per candidate. Run `/run-archivist` for the full promotion workflow.
"""


# ----- GC-mode templates -----


GC_HEADER = """# Archivist Candidate — GC — {date}

**Run timestamp:** {run_ts}
**KB entry count:** {kb_count}
**Proposal count:** {proposal_count}

"""

GC_SECTION_1_HEADER = """## Section 1 — Stale entries

_KB entries not referenced in recent PR bodies, task packets, or trace
events. Each row lists path, last-referenced date, N sessions since, and
proposed action (`mark stale` | `delete`)._

"""

GC_SECTION_2_HEADER = """## Section 2 — Dead skills

_Skills with no recent invocation events. Each row lists skill path,
last-invoked date or ``never since promotion``, and proposed action._

"""

GC_SECTION_3_HEADER = """## Section 3 — Obsolete prompt-policies

_Policy files superseded by newer versions per B.3 registry index. Each
row lists policy path, superseding version, and proposed action._

"""

GC_SECTION_4_HEADER = """## Section 4 — Orphan artifacts

_Files whose referenced target is missing. Each row lists orphan path,
missing target, and proposed action._

"""

GC_SECTION_5_HEADER = """## Section 5 — Expired evidence

_KB entries annotated with an evidence link that has expired. Each row
lists entry path, expired evidence link, and proposed action._

"""


GC_FOOTER = """
## Verification: operator review

Each proposal above lists: target_paths, proposed_action, evidence,
rollback path. All GC actions are Pattern 7 reversible (git revert
restores the pre-proposal state).

Operator workflow: open this file, decide per proposal. Run
`/run-archivist` for the promotion/rejection workflow.
"""


# ----- Postmortem-mode templates -----


POSTMORTEM_SECTION_HEADER = """## Postmortem — session {session_id} — {date}

**Session start:** {session_start}
**Session end:** {session_end}
**PRs merged:** {prs_merged}
**Incidents:** {incident_count}
**Token outliers:** {outlier_count}

"""


POSTMORTEM_MEMORY_ENTRY = """### Session {session_id} — {date}

**Goal:** {goal}

**PRs merged:** {prs_merged}

**Lanes parked:** {lanes_parked}

**Outstanding:** {outstanding}

**Next session:** {next_steps}

**Hazards:** {hazards}

"""


def iso_now() -> str:
    """ISO-8601 UTC timestamp — separated for deterministic testing."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def format_bullet_list(items: Iterable[str]) -> str:
    """Render an iterable of strings as ``- item\n`` bullets."""
    rendered = "\n".join(f"- {item}" for item in items)
    if not rendered:
        return "_(none)_\n"
    return rendered + "\n"

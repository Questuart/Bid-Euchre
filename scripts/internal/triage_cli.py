"""Triage CLI — Primitive E Phase 0 Packet E1 (SCAFFOLD only, no runtime).

Provides the programmatic surface for the `triaging-issues` skill. Both the
operator-invocable `/triaging-issues` flow and the event-driven
`active_triage` runtime (post-Primitive-A) consume this module.

**Runtime status (2026-04-24):** SCAFFOLD. `file_or_recur(...)` raises
`NotImplementedError` pointing at Primitive A Packet 3 as the unblocker.
The dataclass + vocabularies are stable and safe to consume for type
annotations / import-graph checks.

See:
- `.claude/skills/triaging-issues/SKILL.md` § Programmatic Invocation
- `plans/steward_platform/5_primitive_E/shaping.md` §5 (contract)
- `plans/steward_platform/1_primitive_A/shaping.md` (event schema — blocker)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Closed vocabularies — single source of truth for signal classes and priority tiers.
# These are pinned by `tests/unit/test_triage_cli_scaffold.py`; adding a value
# requires updating the test and the SKILL.md contract section together.

SIGNAL_CLASSES: tuple[str, ...] = (
    "ci_red",
    "review_blocked",
    "stalled_lane",
    "orphan_worktree",
    "token_burn",
)

PRIORITIES: tuple[str, ...] = (
    "low",
    "normal",
    "high",
    "urgent",
)

SignalClass = Literal[
    "ci_red",
    "review_blocked",
    "stalled_lane",
    "orphan_worktree",
    "token_burn",
]

Priority = Literal["low", "normal", "high", "urgent"]


@dataclass(frozen=True)
class TriageInput:
    """Structured input for programmatic triage filing.

    Fields match `plans/steward_platform/5_primitive_E/shaping.md` §5.2.
    """

    signal_class: SignalClass
    title_hint: str
    body_sections: dict[str, str]
    labels: list[str]
    priority: Priority
    incident_fingerprint: str
    source_event_id: str
    extra_context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TriageResult:
    """Outcome of a `file_or_recur` call.

    The live implementation populates these fields after querying / writing
    GitHub. Scaffold never returns one (always raises).
    """

    action: Literal["created", "recurrence_appended", "coalesced_ignored"]
    issue_number: int | None
    comment_url: str | None
    fingerprint: str
    rationale: str


class TriageRuntimeUnavailable(NotImplementedError):
    """Raised by the scaffold to signal the runtime is blocked on Primitive A."""


def file_or_recur(payload: TriageInput) -> TriageResult:  # pragma: no cover - scaffold
    """File a new triage issue or append a recurrence comment (SCAFFOLD).

    Live behavior (post-Primitive-A merge):
    1. Query ``gh issue list --label follow-up --state open --search <fingerprint>``
       to find an open follow-up matching the incident fingerprint.
    2. If a match exists AND the original issue is <24h old: append a
       `## Recurrence observed` comment; return ``action="recurrence_appended"``.
    3. Otherwise: open a new issue; embed the fingerprint as an HTML comment;
       return ``action="created"``.

    Scaffold behavior: raise ``TriageRuntimeUnavailable`` with a pointer to
    Primitive A Packet 3 as the unblocker.
    """
    raise TriageRuntimeUnavailable(
        "triage_cli.file_or_recur is a scaffold — live runtime is blocked on "
        "Primitive A Packet 3 (event schema + dispatcher). See "
        "`plans/steward_platform/5_primitive_E/shaping.md` §5 and "
        "`plans/steward_platform/5_primitive_E/phase0_readiness.md` for the "
        "unblock path. Payload signal_class=%s fingerprint=%s"
        % (payload.signal_class, payload.incident_fingerprint)
    )


def is_valid_signal_class(value: str) -> bool:
    """Return True iff ``value`` is a registered signal class."""
    return value in SIGNAL_CLASSES


def is_valid_priority(value: str) -> bool:
    """Return True iff ``value`` is a registered priority tier."""
    return value in PRIORITIES


__all__ = [
    "PRIORITIES",
    "Priority",
    "SIGNAL_CLASSES",
    "SignalClass",
    "TriageInput",
    "TriageResult",
    "TriageRuntimeUnavailable",
    "file_or_recur",
    "is_valid_priority",
    "is_valid_signal_class",
]

"""Candidate-entry schema for changelog review.

Per Primitive D shape §4.5.4 (Output file schema), each candidate in the
dated output file is a ``## Candidate N — <feature name>`` section with a
fixed bullet list. This module provides:

- ``CandidateEntry`` dataclass — in-memory representation with the schema
  fields shape §4.5.4 enumerates
- ``validate_candidate`` — schema validator used by the scraper and CLI
- ``render_candidate_section`` — rendering helper that produces the
  operator-review markdown the dated file records

Design constraint: the schema is *purely textual* — the operator fills
``operator_decision`` + ``decision_date`` + ``follow_up`` post-review,
so the validator accepts the pre-review shape (those fields may be
``None``) and the rendered output uses ``_(pending)_`` placeholders.

Native-substrate-signal integration (shape §4.5.5):

- ``native_substrate_signal`` is computed from two rules:
  1. ``stales_harness_assumption`` is truthy, OR
  2. ``tier_recommendation`` is ``"S"`` or ``"A"`` (per
     ``claude_code_changelog_implications.md`` §5 rubric)
- the rendered bullet line is the literal string
  ``Native-substrate-signal: yes`` (or ``no``) — the digest compiler
  (``compile_decision_inputs.py``, §15.4) greps for this exact line

Agent-readability (ADR 001): every field has a docstring fragment and a
default; rendering uses section-header + ≤3-line-lede discipline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# ----- Controlled vocabularies (shape §4.5.4) -----

VALID_PRIMITIVES: frozenset[str] = frozenset({"A", "B", "C", "D", "E", "F", "G", "H"})
"""Acceptable ``affected_primitives`` values (shape §4.5.4)."""

VALID_TIERS: frozenset[str] = frozenset({"S", "A", "B", "C"})
"""Acceptable ``tier_recommendation`` values (per
``claude_code_changelog_implications.md`` §5 rubric)."""

VALID_DECISIONS: frozenset[str] = frozenset({"accept", "defer", "reject"})
"""Acceptable post-review ``operator_decision`` values."""

# Tiers for which shape §4.5.5 rule 2 sets native-substrate-signal = yes.
NATIVE_FIRST_TIERS: frozenset[str] = frozenset({"S", "A"})


@dataclass
class CandidateEntry:
    """One changelog-review candidate.

    Fields mirror shape §4.5.4 bullet schema 1:1. Post-review fields
    (``operator_decision``, ``decision_date``, ``follow_up``) default to
    ``None`` so the pre-review file renders with ``_(pending)_`` placeholders.
    """

    feature_name: str
    source_url: str
    # ``affected_primitives`` is a list so one candidate can mark multiple
    # primitives (e.g., a new MCP surface that lands in both B and D).
    affected_primitives: list[str] = field(default_factory=list)
    stales_harness_assumption: bool = False
    # Identifier of the stale entry when ``stales_harness_assumption`` is
    # True; the fixture uses the ``## Entry N`` handle convention from
    # ``knowledge/harness_assumptions.md``.
    stale_entry_id: Optional[str] = None
    tier_recommendation: str = "C"
    # Override the auto-computed native-substrate-signal; default None
    # lets ``__post_init__`` compute it per shape §4.5.5.
    native_substrate_signal: Optional[bool] = None
    operator_decision: Optional[str] = None
    decision_date: Optional[str] = None
    follow_up: Optional[str] = None

    def __post_init__(self) -> None:
        """Compute default ``native_substrate_signal`` per §4.5.5 rules."""
        if self.native_substrate_signal is None:
            self.native_substrate_signal = compute_native_substrate_signal(
                stales_harness_assumption=self.stales_harness_assumption,
                tier_recommendation=self.tier_recommendation,
            )


def compute_native_substrate_signal(
    *, stales_harness_assumption: bool, tier_recommendation: str
) -> bool:
    """Apply shape §4.5.5 rules 1 and 2.

    Rule 1: staleness flag True → signal yes.
    Rule 2: tier ∈ {S, A} → signal yes.
    Otherwise no.
    """
    if stales_harness_assumption:
        return True
    if tier_recommendation in NATIVE_FIRST_TIERS:
        return True
    return False


def validate_candidate(entry: CandidateEntry) -> list[str]:
    """Return a list of schema-violation messages; empty list means valid.

    The scraper calls this on every entry; CLI `--dry-run` aggregates the
    messages per-source for operator visibility. Never raises — downstream
    consumers decide whether validation errors block the run or just get
    surfaced in the candidate file.
    """
    errors: list[str] = []
    if not entry.feature_name or not entry.feature_name.strip():
        errors.append("feature_name is empty")
    if not entry.source_url or not entry.source_url.strip():
        errors.append("source_url is empty")
    if not entry.affected_primitives:
        errors.append("affected_primitives is empty (need at least one)")
    for prim in entry.affected_primitives:
        if prim not in VALID_PRIMITIVES:
            errors.append(
                f"affected_primitives contains invalid value {prim!r} "
                f"(expected one of {sorted(VALID_PRIMITIVES)})"
            )
    if entry.tier_recommendation not in VALID_TIERS:
        errors.append(
            f"tier_recommendation {entry.tier_recommendation!r} "
            f"not in {sorted(VALID_TIERS)}"
        )
    if entry.stales_harness_assumption and not entry.stale_entry_id:
        errors.append(
            "stales_harness_assumption=True requires a non-empty stale_entry_id"
        )
    if (
        entry.operator_decision is not None
        and entry.operator_decision not in VALID_DECISIONS
    ):
        errors.append(
            f"operator_decision {entry.operator_decision!r} "
            f"not in {sorted(VALID_DECISIONS)}"
        )
    return errors


def render_candidate_section(index: int, entry: CandidateEntry) -> str:
    """Render one ``## Candidate N — <name>`` section per shape §4.5.4.

    ``index`` is 1-based. Pre-review fields render as ``_(pending)_``.
    The ``Native-substrate-signal:`` line is always rendered literally
    (the §15.3 digest compiler greps for the exact string).
    """
    primitives = (
        ", ".join(entry.affected_primitives)
        if entry.affected_primitives
        else "_(none)_"
    )
    stale_line = _format_stale_line(entry)
    signal = "yes" if entry.native_substrate_signal else "no"
    decision = entry.operator_decision or "_(pending)_"
    decision_date = entry.decision_date or "_(pending)_"
    follow_up = entry.follow_up or "n/a"

    # Note: the Native-substrate-signal bullet is intentionally *not*
    # markdown-bolded — shape §4.5.5 mandates the literal string
    # ``Native-substrate-signal: yes`` so ``compile_decision_inputs.py``
    # (§15.4) can grep for it. The other bullets keep standard bold
    # emphasis; the digest compiler does not grep those.
    return (
        f"## Candidate {index} — {entry.feature_name}\n"
        f"- **Source URL:** {entry.source_url}\n"
        f"- **Affected primitive(s):** {primitives}\n"
        f"- **Stales harness assumption:** {stale_line}\n"
        f"- **Tier recommendation:** {entry.tier_recommendation}\n"
        f"- Native-substrate-signal: {signal}\n"
        f"- **Operator decision:** {decision}\n"
        f"- **Decision date:** {decision_date}\n"
        f"- **Follow-up:** {follow_up}\n"
    )


def _format_stale_line(entry: CandidateEntry) -> str:
    """Render the ``Stales harness assumption`` bullet value."""
    if not entry.stales_harness_assumption:
        return "no"
    entry_id = entry.stale_entry_id or "unknown"
    return f"yes — entry_id: {entry_id}"


def validate_many(entries: Iterable[CandidateEntry]) -> dict[int, list[str]]:
    """Validate a batch of entries; return ``{index: [errors]}`` for invalid ones."""
    out: dict[int, list[str]] = {}
    for idx, entry in enumerate(entries):
        errors = validate_candidate(entry)
        if errors:
            out[idx] = errors
    return out

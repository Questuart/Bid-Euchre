"""Review-quality audit: measure where the review loop misses or over-reports.

Scans local review-loop artifacts (state files, round findings,
confidence-scoring reports) and produces a bounded summary that
distinguishes:

  1. Missed blockers — post-merge fixes that the loop should have caught
  2. Noisy findings — check_ids with high filter/false-positive rates
  3. Deterministic-check candidates — repeated Codex findings that could
     become prechecks

Usage::

    # Audit all local review-loop data
    python scripts/internal/review_quality_audit.py

    # Audit with JSON output
    python scripts/internal/review_quality_audit.py --json

    # Audit specific base directory (for testing)
    python scripts/internal/review_quality_audit.py --base /path/to/review_loops

This module is repo-local measurement only.  It does not change the
``reviewing-changes`` contract or the merge gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class LoopOutcome:
    """Summary of one review-loop run."""

    pr_number: int
    terminal_state: str
    iteration_count: int
    stop_reason: str | None
    total_findings: int = 0
    filtered_findings: int = 0
    codex_findings: int = 0
    precheck_findings: int = 0


@dataclass
class FindingAggregate:
    """Aggregate stats for one (check_id, source) pair."""

    check_id: str
    source: str  # "deterministic_precheck", "codex_cli"
    total: int = 0
    filtered: int = 0  # filtered by confidence scorer
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    auto_fixed: int = 0
    skipped: int = 0  # skipped by fix adapter


@dataclass
class MissedBlockerSignal:
    """A post-merge fix that the pre-merge loop should have caught."""

    pr_number: int
    title: str
    category: str  # extracted from title prefix like "fix:", "fix(fix:convention):"


@dataclass
class AuditSummary:
    """Top-level audit report."""

    total_loops: int = 0
    outcome_distribution: dict[str, int] = field(default_factory=dict)
    completion_rate: float = 0.0
    finding_aggregates: list[FindingAggregate] = field(default_factory=list)
    noisy_check_ids: list[str] = field(default_factory=list)
    missed_blocker_signals: list[MissedBlockerSignal] = field(default_factory=list)
    deterministic_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def scan_loop_outcomes(base: Path) -> list[LoopOutcome]:
    """Scan review-loop state files and return per-PR outcomes."""
    outcomes: list[LoopOutcome] = []

    if not base.is_dir():
        return outcomes

    for pr_dir in sorted(base.iterdir()):
        if not pr_dir.is_dir() or not pr_dir.name.startswith("pr_"):
            continue

        state_path = pr_dir / "state.json"
        if not state_path.exists():
            continue

        try:
            state = json.loads(state_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        pr_num = state.get("pr_number", 0)
        outcome = LoopOutcome(
            pr_number=pr_num,
            terminal_state=state.get("state", "unknown"),
            iteration_count=state.get("iteration_count", 0),
            stop_reason=state.get("stop_reason"),
        )

        # Aggregate findings across rounds
        for round_dir in sorted(pr_dir.iterdir()):
            if not round_dir.is_dir() or not round_dir.name.startswith("round_"):
                continue
            _enrich_from_round(outcome, round_dir)

        outcomes.append(outcome)

    return outcomes


def _enrich_from_round(outcome: LoopOutcome, round_dir: Path) -> None:
    """Add finding counts from a single round directory."""
    # Prechecks
    prechecks_path = round_dir / "prechecks.json"
    if prechecks_path.exists():
        try:
            prechecks = json.loads(prechecks_path.read_text())
            if isinstance(prechecks, list):
                outcome.precheck_findings += len(prechecks)
                outcome.total_findings += len(prechecks)
        except (json.JSONDecodeError, OSError):
            pass

    # Codex review
    codex_path = round_dir / "codex_review.json"
    if codex_path.exists():
        try:
            codex = json.loads(codex_path.read_text())
            findings = codex.get("findings", [])
            outcome.codex_findings += len(findings)
            outcome.total_findings += len(findings)
        except (json.JSONDecodeError, OSError):
            pass

    # Confidence scoring (filter counts)
    scoring_path = round_dir / "confidence_scoring.json"
    if scoring_path.exists():
        try:
            scoring = json.loads(scoring_path.read_text())
            outcome.filtered_findings += scoring.get("filtered", 0)
        except (json.JSONDecodeError, OSError):
            pass


# ---------------------------------------------------------------------------
# Finding aggregation
# ---------------------------------------------------------------------------


def aggregate_findings(base: Path) -> list[FindingAggregate]:
    """Aggregate findings by (check_id, source) across all rounds."""
    agg: dict[tuple[str, str], FindingAggregate] = {}

    if not base.is_dir():
        return []

    for pr_dir in sorted(base.iterdir()):
        if not pr_dir.is_dir() or not pr_dir.name.startswith("pr_"):
            continue

        for round_dir in sorted(pr_dir.iterdir()):
            if not round_dir.is_dir() or not round_dir.name.startswith("round_"):
                continue

            _aggregate_prechecks(round_dir, agg)
            _aggregate_codex(round_dir, agg)
            _aggregate_scoring(round_dir, agg)
            _aggregate_fixes(round_dir, agg)

    return sorted(agg.values(), key=lambda a: a.total, reverse=True)


def _get_or_create(
    agg: dict[tuple[str, str], FindingAggregate],
    check_id: str,
    source: str,
) -> FindingAggregate:
    """Get or create an aggregate entry."""
    key = (check_id, source)
    if key not in agg:
        agg[key] = FindingAggregate(check_id=check_id, source=source)
    return agg[key]


def _aggregate_prechecks(
    round_dir: Path, agg: dict[tuple[str, str], FindingAggregate]
) -> None:
    """Aggregate precheck findings from a round."""
    path = round_dir / "prechecks.json"
    if not path.exists():
        return
    try:
        findings = json.loads(path.read_text())
        if not isinstance(findings, list):
            return
    except (json.JSONDecodeError, OSError):
        return

    for f in findings:
        check_id = f.get("check_id") or "unstructured"
        entry = _get_or_create(agg, check_id, "deterministic_precheck")
        entry.total += 1
        sev = f.get("severity", "P2")
        if sev == "P0":
            entry.p0_count += 1
        elif sev == "P1":
            entry.p1_count += 1
        else:
            entry.p2_count += 1


def _aggregate_codex(
    round_dir: Path, agg: dict[tuple[str, str], FindingAggregate]
) -> None:
    """Aggregate Codex CLI findings from a round."""
    path = round_dir / "codex_review.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        findings = data.get("findings", [])
    except (json.JSONDecodeError, OSError):
        return

    for f in findings:
        check_id = f.get("check_id") or "unstructured"
        entry = _get_or_create(agg, check_id, "codex_cli")
        entry.total += 1
        sev = f.get("severity", "P2")
        if sev == "P0":
            entry.p0_count += 1
        elif sev == "P1":
            entry.p1_count += 1
        else:
            entry.p2_count += 1


def _aggregate_scoring(
    round_dir: Path, agg: dict[tuple[str, str], FindingAggregate]
) -> None:
    """Aggregate confidence-scoring filter counts."""
    path = round_dir / "confidence_scoring.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        findings = data.get("findings", [])
    except (json.JSONDecodeError, OSError):
        return

    for f in findings:
        if f.get("filtered"):
            check_id = f.get("check_id") or "unstructured"
            # Try to infer source — scoring happens after codex review
            entry = _get_or_create(agg, check_id, "codex_cli")
            entry.filtered += 1


def _aggregate_fixes(
    round_dir: Path, agg: dict[tuple[str, str], FindingAggregate]
) -> None:
    """Aggregate auto-fix results."""
    path = round_dir / "fix_summary.json"
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        actions = data.get("actions", [])
    except (json.JSONDecodeError, OSError):
        return

    for action in actions:
        check_id = action.get("check_id") or "unstructured"
        status = action.get("status", "")
        # Auto-fix actions come from Codex findings
        entry = _get_or_create(agg, check_id, "codex_cli")
        if status == "applied":
            entry.auto_fixed += 1
        elif status == "skipped":
            entry.skipped += 1


# ---------------------------------------------------------------------------
# Noise detection
# ---------------------------------------------------------------------------


def identify_noisy_check_ids(
    aggregates: list[FindingAggregate],
    min_occurrences: int = 3,
    min_filter_rate: float = 0.5,
) -> list[str]:
    """Identify check_ids with high confidence-filter rates.

    A check_id is noisy if it has appeared at least *min_occurrences*
    times and more than *min_filter_rate* fraction of its P2 findings
    were filtered by the confidence scorer.

    Returns:
        Sorted list of noisy check_id strings.
    """
    noisy: list[str] = []
    for a in aggregates:
        if a.p2_count < min_occurrences:
            continue
        if a.p2_count > 0 and a.filtered / a.p2_count >= min_filter_rate:
            noisy.append(a.check_id)
    return sorted(set(noisy))


# ---------------------------------------------------------------------------
# Missed-blocker signals
# ---------------------------------------------------------------------------


def classify_fix_pr(title: str) -> str | None:
    """Extract fix category from a PR title.

    Returns the category string (e.g. "bug", "convention", "test") or
    None if the title doesn't look like a fix PR.
    """
    title_lower = title.lower().strip()

    # Pattern: "fix(fix:category): ..."
    if title_lower.startswith("fix(fix:"):
        try:
            end = title_lower.index(")")
            return title_lower[8:end].strip() or "general"
        except ValueError:
            return "general"

    # Pattern: "fix: ..."
    if title_lower.startswith("fix:"):
        return "general"

    # Pattern: "fix(category): ..."
    if title_lower.startswith("fix("):
        try:
            end = title_lower.index(")")
            return title_lower[4:end].strip() or "general"
        except ValueError:
            return "general"

    return None


def extract_missed_blocker_signals(
    fix_prs: list[dict[str, Any]],
) -> list[MissedBlockerSignal]:
    """Extract missed-blocker signals from post-merge fix PRs.

    Args:
        fix_prs: List of dicts with keys: number, title.

    Returns:
        List of MissedBlockerSignal for PRs that look like post-merge fixes.
    """
    signals: list[MissedBlockerSignal] = []
    for pr in fix_prs:
        title = pr.get("title", "")
        category = classify_fix_pr(title)
        if category is not None:
            signals.append(
                MissedBlockerSignal(
                    pr_number=pr.get("number", 0),
                    title=title,
                    category=category,
                )
            )
    return signals


# ---------------------------------------------------------------------------
# Deterministic-check candidates
# ---------------------------------------------------------------------------


def identify_deterministic_candidates(
    aggregates: list[FindingAggregate],
    min_occurrences: int = 2,
) -> list[str]:
    """Identify Codex findings that recur enough to become deterministic prechecks.

    A candidate is a Codex CLI finding with a structured check_id
    (not 'unstructured') that appeared at least *min_occurrences* times
    and is not already a deterministic precheck.

    Returns:
        Sorted list of candidate check_id strings.
    """
    # Collect existing deterministic precheck check_ids
    existing: set[str] = set()
    for a in aggregates:
        if a.source == "deterministic_precheck":
            existing.add(a.check_id)

    candidates: list[str] = []
    for a in aggregates:
        if a.source != "codex_cli":
            continue
        if a.check_id in ("unstructured", "unknown"):
            continue
        if a.check_id in existing:
            continue
        if a.total >= min_occurrences:
            candidates.append(a.check_id)

    return sorted(set(candidates))


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------


def generate_summary(
    outcomes: list[LoopOutcome],
    aggregates: list[FindingAggregate],
    missed_signals: list[MissedBlockerSignal],
    *,
    noisy_min_occurrences: int = 3,
    noisy_min_filter_rate: float = 0.5,
    deterministic_min_occurrences: int = 2,
) -> AuditSummary:
    """Generate the full audit summary from scanned data."""
    outcome_dist: Counter[str] = Counter()
    for o in outcomes:
        outcome_dist[o.terminal_state] += 1

    merged_count = outcome_dist.get("merged", 0)
    total = len(outcomes)
    completion_rate = merged_count / total if total > 0 else 0.0

    noisy = identify_noisy_check_ids(
        aggregates,
        min_occurrences=noisy_min_occurrences,
        min_filter_rate=noisy_min_filter_rate,
    )
    deterministic = identify_deterministic_candidates(
        aggregates,
        min_occurrences=deterministic_min_occurrences,
    )

    # Categorize missed-blocker signals
    missed_categories: Counter[str] = Counter()
    for s in missed_signals:
        missed_categories[s.category] += 1

    return AuditSummary(
        total_loops=total,
        outcome_distribution=dict(outcome_dist),
        completion_rate=round(completion_rate, 3),
        finding_aggregates=aggregates,
        noisy_check_ids=noisy,
        missed_blocker_signals=missed_signals,
        deterministic_candidates=deterministic,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_markdown(summary: AuditSummary) -> str:
    """Format audit summary as Markdown for handoff/plan updates."""
    lines: list[str] = []
    lines.append("# Review Quality Audit")
    lines.append("")

    # Outcome distribution
    lines.append("## Loop Outcome Distribution")
    lines.append("")
    lines.append(f"**Total loops:** {summary.total_loops}")
    lines.append(f"**Completion rate (merged):** {summary.completion_rate:.1%}")
    lines.append("")
    lines.append("| State | Count |")
    lines.append("|-------|-------|")
    for state, count in sorted(
        summary.outcome_distribution.items(), key=lambda x: -x[1]
    ):
        lines.append(f"| {state} | {count} |")
    lines.append("")

    # Finding aggregates
    if summary.finding_aggregates:
        lines.append("## Finding Aggregates (by check_id × source)")
        lines.append("")
        lines.append(
            "| check_id | source | total | P0 | P1 | P2 | filtered | auto_fixed | skipped |"
        )
        lines.append(
            "|----------|--------|-------|----|----|----|----------|------------|---------|"
        )
        for a in summary.finding_aggregates:
            lines.append(
                f"| {a.check_id} | {a.source} | {a.total} | {a.p0_count} "
                f"| {a.p1_count} | {a.p2_count} | {a.filtered} "
                f"| {a.auto_fixed} | {a.skipped} |"
            )
        lines.append("")

    # Noisy check_ids
    if summary.noisy_check_ids:
        lines.append("## Noisy Check IDs (high filter rate)")
        lines.append("")
        for cid in summary.noisy_check_ids:
            lines.append(f"- `{cid}`")
        lines.append("")

    # Missed blockers
    if summary.missed_blocker_signals:
        lines.append("## Missed Blocker Signals (post-merge fix PRs)")
        lines.append("")
        cat_counts: Counter[str] = Counter()
        for s in summary.missed_blocker_signals:
            cat_counts[s.category] += 1
        lines.append("**By category:**")
        lines.append("")
        for cat, count in cat_counts.most_common():
            lines.append(f"- `{cat}`: {count}")
        lines.append("")
        lines.append("**Recent fix PRs:**")
        lines.append("")
        for s in summary.missed_blocker_signals[:20]:
            lines.append(f"- #{s.pr_number}: {s.title}")
        if len(summary.missed_blocker_signals) > 20:
            lines.append(f"- ... and {len(summary.missed_blocker_signals) - 20} more")
        lines.append("")

    # Deterministic candidates
    if summary.deterministic_candidates:
        lines.append("## Deterministic-Check Candidates")
        lines.append("")
        lines.append(
            "These Codex CLI findings recur frequently and could become "
            "deterministic prechecks:"
        )
        lines.append("")
        for cid in summary.deterministic_candidates:
            lines.append(f"- `{cid}`")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the review-quality audit."""
    parser = argparse.ArgumentParser(
        description="Review-quality audit for the local review loop"
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=Path(".claude/runtime/review_loops"),
        help="Base directory containing review-loop state (default: .claude/runtime/review_loops)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON instead of Markdown",
    )
    parser.add_argument(
        "--fix-prs-json",
        type=Path,
        default=None,
        help="Path to JSON file of merged fix PRs (each: {number, title})",
    )
    args = parser.parse_args(argv)

    # Scan outcomes and findings
    outcomes = scan_loop_outcomes(args.base)
    aggregates = aggregate_findings(args.base)

    # Load fix PRs if provided
    missed_signals: list[MissedBlockerSignal] = []
    if args.fix_prs_json and args.fix_prs_json.exists():
        try:
            fix_prs = json.loads(args.fix_prs_json.read_text())
            missed_signals = extract_missed_blocker_signals(fix_prs)
        except (json.JSONDecodeError, OSError):
            pass

    summary = generate_summary(outcomes, aggregates, missed_signals)

    if args.json_output:
        print(json.dumps(summary.to_dict(), indent=2))
    else:
        print(format_markdown(summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())

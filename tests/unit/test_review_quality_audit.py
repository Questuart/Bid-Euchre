"""Tests for review_quality_audit — review-loop quality measurement."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# The module under test lives in scripts/internal/, not in the installed package.
_SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from review_quality_audit import (
    AuditSummary,
    FindingAggregate,
    MissedBlockerSignal,
    aggregate_findings,
    classify_fix_pr,
    extract_missed_blocker_signals,
    format_markdown,
    generate_summary,
    identify_deterministic_candidates,
    identify_noisy_check_ids,
    scan_loop_outcomes,
)

# ---------------------------------------------------------------------------
# Fixtures — create synthetic review-loop directories
# ---------------------------------------------------------------------------


def _write_state(pr_dir: Path, state: dict) -> None:
    """Write a state.json into a PR directory."""
    pr_dir.mkdir(parents=True, exist_ok=True)
    (pr_dir / "state.json").write_text(json.dumps(state))


def _write_round(
    pr_dir: Path,
    round_num: int,
    *,
    prechecks: list | None = None,
    codex_review: dict | None = None,
    confidence_scoring: dict | None = None,
    fix_summary: dict | None = None,
) -> None:
    """Write round artifacts into a PR round directory."""
    round_dir = pr_dir / f"round_{round_num}"
    round_dir.mkdir(parents=True, exist_ok=True)

    if prechecks is not None:
        (round_dir / "prechecks.json").write_text(json.dumps(prechecks))
    if codex_review is not None:
        (round_dir / "codex_review.json").write_text(json.dumps(codex_review))
    if confidence_scoring is not None:
        (round_dir / "confidence_scoring.json").write_text(
            json.dumps(confidence_scoring)
        )
    if fix_summary is not None:
        (round_dir / "fix_summary.json").write_text(json.dumps(fix_summary))


@pytest.fixture
def review_base(tmp_path: Path) -> Path:
    """Create a synthetic review-loop base with realistic data."""
    base = tmp_path / "review_loops"

    # PR 100: merged successfully, had some findings
    pr100 = base / "pr_100"
    _write_state(
        pr100,
        {
            "pr_number": 100,
            "state": "merged",
            "iteration_count": 1,
            "stop_reason": None,
        },
    )
    _write_round(
        pr100,
        1,
        prechecks=[
            {
                "severity": "P2",
                "check_id": "PV1",
                "file": "<PR body>",
                "line": 0,
                "message": "No plan ref",
                "raw_source": "plan_validation",
            }
        ],
        codex_review={
            "success": True,
            "findings": [
                {
                    "severity": "P2",
                    "file": "src/foo.py",
                    "line": 10,
                    "check_id": "C4",
                    "message": "Function too long",
                    "raw_source": "codex_cli",
                }
            ],
        },
        confidence_scoring={
            "total_findings": 1,
            "passed": 0,
            "filtered": 1,
            "threshold": 75,
            "findings": [
                {
                    "file": "src/foo.py",
                    "line": 10,
                    "check_id": "C4",
                    "severity": "P2",
                    "confidence": 40,
                    "filtered": True,
                }
            ],
        },
        fix_summary={
            "fixes_applied": 0,
            "fixes_skipped": 1,
            "actions": [
                {
                    "file": "src/foo.py",
                    "check_id": "C4",
                    "status": "skipped",
                    "reason": "Not auto-fixable",
                }
            ],
        },
    )

    # PR 200: stopped_ci_failure
    pr200 = base / "pr_200"
    _write_state(
        pr200,
        {
            "pr_number": 200,
            "state": "stopped_ci_failure",
            "iteration_count": 0,
            "stop_reason": "CI failed",
        },
    )

    # PR 300: merged, no findings
    pr300 = base / "pr_300"
    _write_state(
        pr300,
        {
            "pr_number": 300,
            "state": "merged",
            "iteration_count": 0,
            "stop_reason": None,
        },
    )

    # PR 400: stopped_review_failure
    pr400 = base / "pr_400"
    _write_state(
        pr400,
        {
            "pr_number": 400,
            "state": "stopped_review_failure",
            "iteration_count": 1,
            "stop_reason": "Codex CLI unavailable",
        },
    )
    _write_round(
        pr400,
        1,
        prechecks=[
            {
                "severity": "P1",
                "check_id": "C1",
                "file": "src/bar.py",
                "line": 5,
                "message": "Unseeded RNG",
                "raw_source": "deterministic_precheck",
            },
            {
                "severity": "P2",
                "check_id": "X3",
                "file": "src/bar.py",
                "line": 12,
                "message": "breakpoint()",
                "raw_source": "deterministic_precheck",
            },
        ],
    )

    # PR 500: merged with codex findings that have structured check_ids
    pr500 = base / "pr_500"
    _write_state(
        pr500,
        {
            "pr_number": 500,
            "state": "merged",
            "iteration_count": 1,
            "stop_reason": None,
        },
    )
    _write_round(
        pr500,
        1,
        codex_review={
            "success": True,
            "findings": [
                {
                    "severity": "P1",
                    "file": "src/baz.py",
                    "line": 20,
                    "check_id": "T1",
                    "message": "Untested behavior change",
                    "raw_source": "codex_cli",
                },
                {
                    "severity": "P2",
                    "file": "src/baz.py",
                    "line": 30,
                    "check_id": "T1",
                    "message": "Another untested change",
                    "raw_source": "codex_cli",
                },
                {
                    "severity": "P2",
                    "file": "src/baz.py",
                    "line": 40,
                    "check_id": None,
                    "message": "Unstructured prose finding",
                    "raw_source": "codex_cli",
                },
            ],
        },
        confidence_scoring={
            "total_findings": 3,
            "passed": 2,
            "filtered": 1,
            "threshold": 75,
            "findings": [
                {
                    "check_id": "T1",
                    "severity": "P1",
                    "confidence": 100,
                    "filtered": False,
                },
                {
                    "check_id": "T1",
                    "severity": "P2",
                    "confidence": 60,
                    "filtered": True,
                },
                {
                    "check_id": None,
                    "severity": "P2",
                    "confidence": 80,
                    "filtered": False,
                },
            ],
        },
    )

    return base


# ---------------------------------------------------------------------------
# scan_loop_outcomes
# ---------------------------------------------------------------------------


class TestScanLoopOutcomes:
    """Verify loop-outcome scanning from state files."""

    def test_scans_all_prs(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        assert len(outcomes) == 5
        pr_nums = {o.pr_number for o in outcomes}
        assert pr_nums == {100, 200, 300, 400, 500}

    def test_terminal_states(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        states = {o.pr_number: o.terminal_state for o in outcomes}
        assert states[100] == "merged"
        assert states[200] == "stopped_ci_failure"
        assert states[400] == "stopped_review_failure"

    def test_finding_counts_enriched(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        pr100 = next(o for o in outcomes if o.pr_number == 100)
        assert pr100.precheck_findings == 1
        assert pr100.codex_findings == 1
        assert pr100.total_findings == 2
        assert pr100.filtered_findings == 1

    def test_empty_base(self, tmp_path: Path):
        outcomes = scan_loop_outcomes(tmp_path / "nonexistent")
        assert outcomes == []

    def test_malformed_state_skipped(self, tmp_path: Path):
        base = tmp_path / "loops"
        pr_dir = base / "pr_999"
        pr_dir.mkdir(parents=True)
        (pr_dir / "state.json").write_text("not json")
        outcomes = scan_loop_outcomes(base)
        assert outcomes == []

    def test_non_pr_directories_skipped(self, tmp_path: Path):
        base = tmp_path / "loops"
        (base / "not_a_pr").mkdir(parents=True)
        (base / "readme.txt").parent.mkdir(parents=True, exist_ok=True)
        (base / "readme.txt").write_text("ignore")
        outcomes = scan_loop_outcomes(base)
        assert outcomes == []


# ---------------------------------------------------------------------------
# aggregate_findings
# ---------------------------------------------------------------------------


class TestAggregateFindings:
    """Verify finding aggregation by (check_id, source)."""

    def test_aggregates_by_check_id_and_source(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        # Should have entries for precheck and codex sources
        sources = {a.source for a in aggs}
        assert "deterministic_precheck" in sources
        assert "codex_cli" in sources

    def test_precheck_counts(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        pv1 = next(
            (
                a
                for a in aggs
                if a.check_id == "PV1" and a.source == "deterministic_precheck"
            ),
            None,
        )
        assert pv1 is not None
        assert pv1.total == 1
        assert pv1.p2_count == 1

    def test_codex_counts(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        t1_codex = next(
            (a for a in aggs if a.check_id == "T1" and a.source == "codex_cli"),
            None,
        )
        assert t1_codex is not None
        assert t1_codex.total == 2  # One P1 + one P2
        assert t1_codex.p1_count == 1
        assert t1_codex.p2_count == 1

    def test_filter_counts_from_scoring(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        c4 = next(
            (a for a in aggs if a.check_id == "C4" and a.source == "codex_cli"),
            None,
        )
        assert c4 is not None
        assert c4.filtered == 1

    def test_fix_skipped_counts(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        c4 = next(
            (a for a in aggs if a.check_id == "C4" and a.source == "codex_cli"),
            None,
        )
        assert c4 is not None
        assert c4.skipped == 1

    def test_unstructured_codex_findings(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        unstructured = next(
            (
                a
                for a in aggs
                if a.check_id == "unstructured" and a.source == "codex_cli"
            ),
            None,
        )
        assert unstructured is not None
        assert unstructured.total == 1

    def test_sorted_by_total_descending(self, review_base: Path):
        aggs = aggregate_findings(review_base)
        totals = [a.total for a in aggs]
        assert totals == sorted(totals, reverse=True)

    def test_empty_base(self, tmp_path: Path):
        aggs = aggregate_findings(tmp_path / "nonexistent")
        assert aggs == []


# ---------------------------------------------------------------------------
# identify_noisy_check_ids
# ---------------------------------------------------------------------------


class TestIdentifyNoisyCheckIds:
    """Verify noisy-check detection."""

    def test_high_filter_rate_detected(self):
        aggs = [
            FindingAggregate(
                check_id="N3",
                source="codex_cli",
                total=10,
                p2_count=8,
                filtered=6,
            ),
        ]
        noisy = identify_noisy_check_ids(aggs, min_occurrences=3, min_filter_rate=0.5)
        assert "N3" in noisy

    def test_low_filter_rate_not_detected(self):
        aggs = [
            FindingAggregate(
                check_id="C1",
                source="codex_cli",
                total=10,
                p2_count=10,
                filtered=1,
            ),
        ]
        noisy = identify_noisy_check_ids(aggs, min_occurrences=3, min_filter_rate=0.5)
        assert "C1" not in noisy

    def test_below_min_occurrences_not_detected(self):
        aggs = [
            FindingAggregate(
                check_id="X1",
                source="codex_cli",
                total=2,
                p2_count=2,
                filtered=2,
            ),
        ]
        noisy = identify_noisy_check_ids(aggs, min_occurrences=3, min_filter_rate=0.5)
        assert "X1" not in noisy

    def test_empty_aggregates(self):
        noisy = identify_noisy_check_ids([])
        assert noisy == []

    def test_deduplicates(self):
        aggs = [
            FindingAggregate(
                check_id="N3",
                source="codex_cli",
                total=5,
                p2_count=5,
                filtered=5,
            ),
            FindingAggregate(
                check_id="N3",
                source="deterministic_precheck",
                total=4,
                p2_count=4,
                filtered=4,
            ),
        ]
        noisy = identify_noisy_check_ids(aggs, min_occurrences=3, min_filter_rate=0.5)
        assert noisy.count("N3") == 1


# ---------------------------------------------------------------------------
# classify_fix_pr
# ---------------------------------------------------------------------------


class TestClassifyFixPr:
    """Verify PR title classification."""

    def test_fix_colon(self):
        assert classify_fix_pr("fix: improve error handling") == "general"

    def test_fix_convention(self):
        assert (
            classify_fix_pr("fix(fix:convention): follow-up for PR #100")
            == "convention"
        )

    def test_fix_bug(self):
        assert classify_fix_pr("fix(fix:bug): handle null pointer") == "bug"

    def test_fix_test(self):
        assert classify_fix_pr("fix(fix:test): add missing coverage") == "test"

    def test_fix_category_parens(self):
        assert classify_fix_pr("fix(ops): harden scheduler") == "ops"

    def test_not_fix(self):
        assert classify_fix_pr("feat: add new bidding strategy") is None

    def test_docs_not_fix(self):
        assert classify_fix_pr("docs: update architecture guide") is None

    def test_case_insensitive(self):
        assert classify_fix_pr("Fix: uppercase fix") == "general"

    def test_empty_category(self):
        assert classify_fix_pr("fix(): empty parens") == "general"

    def test_fix_fix_missing_paren(self):
        """fix(fix:convention without closing paren should not raise ValueError."""
        assert classify_fix_pr("fix(fix:convention: missing paren") == "general"

    def test_fix_category_missing_paren(self):
        """fix(ops without closing paren should not raise ValueError."""
        assert classify_fix_pr("fix(ops: missing paren") == "general"


# ---------------------------------------------------------------------------
# extract_missed_blocker_signals
# ---------------------------------------------------------------------------


class TestExtractMissedBlockerSignals:
    """Verify missed-blocker extraction from PR lists."""

    def test_extracts_fix_prs(self):
        prs = [
            {"number": 1, "title": "fix: handle edge case"},
            {"number": 2, "title": "feat: new feature"},
            {"number": 3, "title": "fix(fix:bug): null pointer"},
        ]
        signals = extract_missed_blocker_signals(prs)
        assert len(signals) == 2
        assert signals[0].pr_number == 1
        assert signals[0].category == "general"
        assert signals[1].pr_number == 3
        assert signals[1].category == "bug"

    def test_empty_list(self):
        signals = extract_missed_blocker_signals([])
        assert signals == []

    def test_no_fix_prs(self):
        prs = [
            {"number": 1, "title": "docs: update readme"},
            {"number": 2, "title": "feat: new bidder"},
        ]
        signals = extract_missed_blocker_signals(prs)
        assert signals == []


# ---------------------------------------------------------------------------
# identify_deterministic_candidates
# ---------------------------------------------------------------------------


class TestIdentifyDeterministicCandidates:
    """Verify deterministic-check candidate identification."""

    def test_recurring_codex_check_id_is_candidate(self):
        aggs = [
            FindingAggregate(check_id="T1", source="codex_cli", total=5),
        ]
        candidates = identify_deterministic_candidates(aggs, min_occurrences=2)
        assert "T1" in candidates

    def test_precheck_check_ids_excluded(self):
        aggs = [
            FindingAggregate(check_id="C1", source="deterministic_precheck", total=10),
            FindingAggregate(check_id="C1", source="codex_cli", total=5),
        ]
        candidates = identify_deterministic_candidates(aggs, min_occurrences=2)
        # C1 is already a deterministic precheck, so not a candidate
        assert "C1" not in candidates

    def test_unstructured_excluded(self):
        aggs = [
            FindingAggregate(check_id="unstructured", source="codex_cli", total=20),
        ]
        candidates = identify_deterministic_candidates(aggs, min_occurrences=2)
        assert "unstructured" not in candidates

    def test_below_min_occurrences_excluded(self):
        aggs = [
            FindingAggregate(check_id="T2", source="codex_cli", total=1),
        ]
        candidates = identify_deterministic_candidates(aggs, min_occurrences=2)
        assert "T2" not in candidates

    def test_empty_aggregates(self):
        candidates = identify_deterministic_candidates([])
        assert candidates == []


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    """Verify end-to-end summary generation."""

    def test_basic_summary(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        aggregates = aggregate_findings(review_base)
        missed = extract_missed_blocker_signals(
            [
                {"number": 10, "title": "fix: handle crash"},
                {"number": 20, "title": "fix(fix:convention): style issue"},
            ]
        )
        summary = generate_summary(outcomes, aggregates, missed)

        assert summary.total_loops == 5
        assert summary.outcome_distribution["merged"] == 3
        assert summary.outcome_distribution["stopped_ci_failure"] == 1
        assert summary.completion_rate == pytest.approx(0.6, abs=0.01)
        assert len(summary.finding_aggregates) > 0
        assert len(summary.missed_blocker_signals) == 2

    def test_empty_data(self):
        summary = generate_summary([], [], [])
        assert summary.total_loops == 0
        assert summary.completion_rate == 0.0
        assert summary.finding_aggregates == []
        assert summary.noisy_check_ids == []
        assert summary.missed_blocker_signals == []
        assert summary.deterministic_candidates == []

    def test_to_dict(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        aggregates = aggregate_findings(review_base)
        summary = generate_summary(outcomes, aggregates, [])
        d = summary.to_dict()
        assert isinstance(d, dict)
        assert "total_loops" in d
        assert "outcome_distribution" in d
        assert "finding_aggregates" in d
        assert isinstance(d["finding_aggregates"], list)


# ---------------------------------------------------------------------------
# format_markdown
# ---------------------------------------------------------------------------


class TestFormatMarkdown:
    """Verify Markdown output formatting."""

    def test_contains_header(self):
        summary = AuditSummary(total_loops=10, outcome_distribution={"merged": 5})
        md = format_markdown(summary)
        assert "# Review Quality Audit" in md
        assert "**Total loops:** 10" in md

    def test_outcome_table(self):
        summary = AuditSummary(
            total_loops=4,
            outcome_distribution={"merged": 2, "stopped_ci_failure": 2},
            completion_rate=0.5,
        )
        md = format_markdown(summary)
        assert "| merged | 2 |" in md
        assert "| stopped_ci_failure | 2 |" in md
        assert "50.0%" in md

    def test_noisy_section(self):
        summary = AuditSummary(
            total_loops=1,
            outcome_distribution={},
            noisy_check_ids=["N3", "X3"],
        )
        md = format_markdown(summary)
        assert "Noisy Check IDs" in md
        assert "`N3`" in md
        assert "`X3`" in md

    def test_missed_blockers_section(self):
        summary = AuditSummary(
            total_loops=1,
            outcome_distribution={},
            missed_blocker_signals=[
                MissedBlockerSignal(
                    pr_number=42, title="fix: crash", category="general"
                ),
            ],
        )
        md = format_markdown(summary)
        assert "Missed Blocker Signals" in md
        assert "#42" in md

    def test_deterministic_section(self):
        summary = AuditSummary(
            total_loops=1,
            outcome_distribution={},
            deterministic_candidates=["T1"],
        )
        md = format_markdown(summary)
        assert "Deterministic-Check Candidates" in md
        assert "`T1`" in md

    def test_finding_aggregates_table(self):
        summary = AuditSummary(
            total_loops=1,
            outcome_distribution={},
            finding_aggregates=[
                FindingAggregate(
                    check_id="C4",
                    source="codex_cli",
                    total=5,
                    p0_count=0,
                    p1_count=1,
                    p2_count=4,
                    filtered=3,
                    auto_fixed=0,
                    skipped=2,
                ),
            ],
        )
        md = format_markdown(summary)
        assert "| C4 | codex_cli |" in md

    def test_empty_summary_no_crash(self):
        summary = AuditSummary()
        md = format_markdown(summary)
        assert "# Review Quality Audit" in md

    def test_truncated_missed_blockers(self):
        signals = [
            MissedBlockerSignal(
                pr_number=i, title=f"fix: issue {i}", category="general"
            )
            for i in range(30)
        ]
        summary = AuditSummary(
            total_loops=1,
            outcome_distribution={},
            missed_blocker_signals=signals,
        )
        md = format_markdown(summary)
        assert "... and 10 more" in md


# ---------------------------------------------------------------------------
# Integration: full pipeline on synthetic data
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """End-to-end integration of scan → aggregate → summary → format."""

    def test_full_pipeline(self, review_base: Path):
        outcomes = scan_loop_outcomes(review_base)
        aggregates = aggregate_findings(review_base)
        missed = extract_missed_blocker_signals(
            [{"number": 99, "title": "fix: post-merge fix"}]
        )

        summary = generate_summary(outcomes, aggregates, missed)
        md = format_markdown(summary)

        # Verify pipeline produces coherent output
        assert summary.total_loops == 5
        assert len(md) > 100
        assert "# Review Quality Audit" in md
        assert "Loop Outcome Distribution" in md

        # JSON round-trip
        d = summary.to_dict()
        assert json.loads(json.dumps(d)) == d

    def test_pipeline_on_empty_data(self, tmp_path: Path):
        base = tmp_path / "empty"
        base.mkdir()

        outcomes = scan_loop_outcomes(base)
        aggregates = aggregate_findings(base)
        summary = generate_summary(outcomes, aggregates, [])
        md = format_markdown(summary)

        assert summary.total_loops == 0
        assert "# Review Quality Audit" in md

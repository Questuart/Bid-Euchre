"""Tests for verify_issue_closure.py — tier classification and linkage extraction."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from verify_issue_closure import (
    IssueInfo,
    classify_issue_tier,
    extract_linkages,
    is_auto_close_keyword,
)

# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


class TestClassifyIssueTier:
    """Tests for classify_issue_tier heuristics."""

    def test_simple_issue_is_tier1(self) -> None:
        issue = IssueInfo(
            number=1,
            title="fix: typo in README",
            body="Small typo fix.",
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 1
        assert signals == []

    def test_needs_verification_label_is_tier2(self) -> None:
        issue = IssueInfo(
            number=2,
            title="ops: fix fleet stall",
            body="Fleet stalls on lane-a.",
            state="OPEN",
            labels=["needs-verification"],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("needs-verification" in s for s in signals)

    def test_needs_human_label_is_tier2(self) -> None:
        issue = IssueInfo(
            number=3,
            title="ops: investigate crash",
            body="Crash in monitor cycle.",
            state="OPEN",
            labels=["needs-human"],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("needs-human" in s for s in signals)

    def test_acceptance_criteria_in_body_is_tier2(self) -> None:
        issue = IssueInfo(
            number=4,
            title="feat: add export feature",
            body="## Acceptance Criteria\n- Export works in production\n- Data is valid",
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("acceptance criteria" in s.lower() for s in signals)

    def test_fleet_mention_is_tier2(self) -> None:
        issue = IssueInfo(
            number=5,
            title="ops: fix fleet dispatch",
            body="The fleet dispatch fails when all lanes are busy.",
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("fleet" in s.lower() for s in signals)

    def test_production_mention_is_tier2(self) -> None:
        issue = IssueInfo(
            number=6,
            title="fix: production config",
            body="Production config is missing env var.",
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("production" in s.lower() for s in signals)

    def test_previously_reopened_is_tier2(self) -> None:
        issue = IssueInfo(
            number=7,
            title="fix: recurring bug",
            body="This bug keeps coming back.",
            state="OPEN",
            labels=[],
            was_reopened=True,
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("reopened" in s.lower() for s in signals)

    def test_long_body_is_tier2(self) -> None:
        issue = IssueInfo(
            number=8,
            title="feat: complex feature",
            body="x" * 1600,
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("substantial" in s.lower() or ">1500" in s for s in signals)

    def test_multiple_signals_accumulate(self) -> None:
        issue = IssueInfo(
            number=9,
            title="ops: fleet verification needed",
            body="## Acceptance Criteria\nVerify in fleet conditions.",
            state="OPEN",
            labels=["needs-verification"],
            was_reopened=True,
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert len(signals) >= 3  # label + body + reopened

    def test_done_when_in_body_is_tier2(self) -> None:
        issue = IssueInfo(
            number=10,
            title="ops: improve monitoring",
            body="Done when the monitoring cycle detects stalls.",
            state="OPEN",
            labels=[],
        )
        tier, signals = classify_issue_tier(issue)
        assert tier == 2
        assert any("done when" in s.lower() for s in signals)


# ---------------------------------------------------------------------------
# Linkage extraction
# ---------------------------------------------------------------------------


class TestExtractLinkages:
    """Tests for extract_linkages regex extraction."""

    def test_fixes_keyword(self) -> None:
        body = "Fixes #123"
        result = extract_linkages(body)
        assert result == [("Fixes", 123)]

    def test_refs_keyword(self) -> None:
        body = "Refs #456"
        result = extract_linkages(body)
        assert result == [("Refs", 456)]

    def test_closes_keyword(self) -> None:
        body = "Closes #789"
        result = extract_linkages(body)
        assert result == [("Closes", 789)]

    def test_resolves_keyword(self) -> None:
        body = "Resolves #100"
        result = extract_linkages(body)
        assert result == [("Resolves", 100)]

    def test_multiple_linkages(self) -> None:
        body = "Fixes #10\nRefs #20\nCloses #30"
        result = extract_linkages(body)
        assert len(result) == 3
        assert ("Fixes", 10) in result
        assert ("Refs", 20) in result
        assert ("Closes", 30) in result

    def test_case_insensitive(self) -> None:
        body = "fixes #42"
        result = extract_linkages(body)
        assert result == [("fixes", 42)]

    def test_no_linkages(self) -> None:
        body = "This PR improves performance."
        result = extract_linkages(body)
        assert result == []

    def test_linkage_in_markdown(self) -> None:
        body = "## Issue Linkage\nRefs #2306\n"
        result = extract_linkages(body)
        assert result == [("Refs", 2306)]

    def test_fix_singular(self) -> None:
        body = "Fix #55"
        result = extract_linkages(body)
        assert result == [("Fix", 55)]

    def test_ref_singular(self) -> None:
        body = "Ref #77"
        result = extract_linkages(body)
        assert result == [("Ref", 77)]


# ---------------------------------------------------------------------------
# Auto-close keyword detection
# ---------------------------------------------------------------------------


class TestIsAutoCloseKeyword:
    """Tests for is_auto_close_keyword."""

    def test_fixes_is_auto_close(self) -> None:
        assert is_auto_close_keyword("Fixes") is True

    def test_closes_is_auto_close(self) -> None:
        assert is_auto_close_keyword("Closes") is True

    def test_resolves_is_auto_close(self) -> None:
        assert is_auto_close_keyword("Resolves") is True

    def test_refs_is_not_auto_close(self) -> None:
        assert is_auto_close_keyword("Refs") is False

    def test_ref_is_not_auto_close(self) -> None:
        assert is_auto_close_keyword("Ref") is False

    def test_case_insensitive(self) -> None:
        assert is_auto_close_keyword("fixes") is True
        assert is_auto_close_keyword("FIXES") is True
        assert is_auto_close_keyword("refs") is False

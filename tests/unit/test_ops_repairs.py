"""Tests for the post-merge repair queue eligibility and visibility helpers.

Covers: eligibility criteria (all conditions), edge cases (needs-human,
active PR, missing labels, unassigned), queue building with mocked gh
output, text and JSON formatting.
"""

from __future__ import annotations

import json

from bid_euchre.ops.repairs import (
    BLOCKING_LABELS,
    MAX_REPAIR_ATTEMPTS,
    REPAIR_PR_PREFIX,
    REQUIRED_LABELS,
    EligibilityResult,
    RepairIssue,
    RepairPR,
    RepairQueue,
    _pr_targets_issue,
    build_repair_queue,
    check_eligibility,
    fetch_candidate_issues,
    fetch_open_repair_prs,
)

# ── Fixtures ────────────────────────────────────────────────────


def _make_issue(
    number: int = 1,
    title: str = "[fix] ops: test issue",
    labels: frozenset[str] | None = None,
    assignees: list[str] | None = None,
    state: str = "OPEN",
    body: str = "",
) -> RepairIssue:
    """Helper to create a RepairIssue with sensible defaults."""
    if labels is None:
        labels = frozenset({"agent-ready", "triage", "fix:bug"})
    if assignees is None:
        assignees = ["author-a"]
    return RepairIssue(
        number=number,
        title=title,
        labels=labels,
        assignees=assignees,
        state=state,
        body=body,
    )


def _make_pr(
    number: int = 100,
    title: str = "fix(repair): something",
    state: str = "OPEN",
    head_branch: str = "fix/repair-something",
    body: str = "",
) -> RepairPR:
    """Helper to create a RepairPR."""
    return RepairPR(
        number=number,
        title=title,
        state=state,
        head_branch=head_branch,
        body=body,
    )


# ── RepairIssue.from_gh_json ───────────────────────────────────


class TestRepairIssueFromGhJson:
    def test_basic_parsing(self) -> None:
        data = {
            "number": 42,
            "title": "[fix] ops: stale event",
            "labels": [{"name": "agent-ready"}, {"name": "fix:bug"}],
            "assignees": [{"login": "author-a"}],
            "state": "OPEN",
            "body": "Some context",
        }
        issue = RepairIssue.from_gh_json(data)
        assert issue.number == 42
        assert issue.title == "[fix] ops: stale event"
        assert issue.labels == frozenset({"agent-ready", "fix:bug"})
        assert issue.assignees == ["author-a"]
        assert issue.state == "OPEN"
        assert issue.body == "Some context"

    def test_empty_labels_and_assignees(self) -> None:
        data = {
            "number": 1,
            "title": "test",
            "labels": [],
            "assignees": [],
            "state": "OPEN",
        }
        issue = RepairIssue.from_gh_json(data)
        assert issue.labels == frozenset()
        assert issue.assignees == []

    def test_missing_fields_default(self) -> None:
        data: dict = {}
        issue = RepairIssue.from_gh_json(data)
        assert issue.number == 0
        assert issue.title == ""
        assert issue.labels == frozenset()
        assert issue.assignees == []
        assert issue.state == "OPEN"

    def test_string_labels_fallback(self) -> None:
        """Labels may come as plain strings in some gh versions."""
        data = {
            "number": 5,
            "title": "test",
            "labels": ["agent-ready", "fix:bug"],
            "assignees": ["author-b"],
            "state": "OPEN",
        }
        issue = RepairIssue.from_gh_json(data)
        assert "agent-ready" in issue.labels


# ── RepairPR.from_gh_json ──────────────────────────────────────


class TestRepairPRFromGhJson:
    def test_basic_parsing(self) -> None:
        data = {
            "number": 99,
            "title": "fix(repair): stale event",
            "state": "OPEN",
            "headRefName": "fix/repair-stale-event",
            "body": "Fixes #42",
        }
        pr = RepairPR.from_gh_json(data)
        assert pr.number == 99
        assert pr.state == "OPEN"
        assert pr.head_branch == "fix/repair-stale-event"
        assert pr.body == "Fixes #42"


# ── check_eligibility ──────────────────────────────────────────


class TestCheckEligibility:
    def test_fully_eligible(self) -> None:
        issue = _make_issue()
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is True
        assert result.reasons == []
        assert result.active_repair_pr is None

    def test_closed_issue(self) -> None:
        issue = _make_issue(state="CLOSED")
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is False
        assert any("not open" in r for r in result.reasons)

    def test_missing_agent_ready(self) -> None:
        issue = _make_issue(labels=frozenset({"triage", "fix:bug"}))
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is False
        assert any("agent-ready" in r for r in result.reasons)

    def test_has_needs_human(self) -> None:
        issue = _make_issue(labels=frozenset({"agent-ready", "needs-human", "fix:bug"}))
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is False
        assert any("needs-human" in r for r in result.reasons)

    def test_unassigned(self) -> None:
        issue = _make_issue(assignees=[])
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is False
        assert any("not assigned" in r for r in result.reasons)

    def test_active_repair_pr_in_title(self) -> None:
        issue = _make_issue(number=42)
        pr = _make_pr(number=100, title="fix(repair): stale event #42")
        result = check_eligibility(issue, open_repair_prs=[pr])
        assert result.eligible is False
        assert any("#100" in r for r in result.reasons)
        assert result.active_repair_pr == pr

    def test_active_repair_pr_in_body(self) -> None:
        issue = _make_issue(number=42)
        pr = _make_pr(number=101, body="Fixes #42")
        result = check_eligibility(issue, open_repair_prs=[pr])
        assert result.eligible is False
        assert result.active_repair_pr == pr

    def test_unrelated_pr_does_not_block(self) -> None:
        issue = _make_issue(number=42)
        pr = _make_pr(number=100, title="fix(repair): other thing", body="Fixes #99")
        result = check_eligibility(issue, open_repair_prs=[pr])
        assert result.eligible is True

    def test_none_prs_skips_pr_check(self) -> None:
        """When open_repair_prs is None, PR check is skipped."""
        issue = _make_issue(number=42)
        result = check_eligibility(issue, open_repair_prs=None)
        assert result.eligible is True

    def test_multiple_failures_accumulate(self) -> None:
        issue = _make_issue(
            state="CLOSED",
            labels=frozenset({"needs-human"}),
            assignees=[],
        )
        result = check_eligibility(issue, open_repair_prs=[])
        assert result.eligible is False
        assert len(result.reasons) >= 3


# ── _pr_targets_issue ──────────────────────────────────────────


class TestPrTargetsIssue:
    def test_match_in_title(self) -> None:
        pr = _make_pr(title="fix(repair): something #42")
        assert _pr_targets_issue(pr, 42) is True

    def test_match_in_body(self) -> None:
        pr = _make_pr(body="Fixes #42\n\nMore context")
        assert _pr_targets_issue(pr, 42) is True

    def test_no_match(self) -> None:
        pr = _make_pr(title="fix(repair): unrelated", body="No issue ref")
        assert _pr_targets_issue(pr, 42) is False

    def test_partial_number_no_false_positive(self) -> None:
        """#4 should not match #42."""
        pr = _make_pr(title="fix(repair): issue #4")
        # #4 is a substring of #42's text but "#42" is not present
        assert _pr_targets_issue(pr, 42) is False

    def test_superstring_number_no_false_positive(self) -> None:
        """#42 should not match when the PR references #421."""
        pr = _make_pr(title="fix(repair): issue #421", body="Closes #421")
        assert _pr_targets_issue(pr, 42) is False

    def test_superstring_number_in_body_no_false_positive(self) -> None:
        """#42 should not match #4200 in body."""
        pr = _make_pr(body="Fixes #4200\n\nMore context")
        assert _pr_targets_issue(pr, 42) is False


# ── EligibilityResult.to_dict ──────────────────────────────────


class TestEligibilityResultToDict:
    def test_eligible_to_dict(self) -> None:
        issue = _make_issue(number=10)
        result = EligibilityResult(issue=issue, eligible=True, reasons=[])
        d = result.to_dict()
        assert d["issue_number"] == 10
        assert d["eligible"] is True
        assert d["reasons"] == []
        assert "active_repair_pr" not in d

    def test_ineligible_to_dict(self) -> None:
        issue = _make_issue(number=10)
        pr = _make_pr(number=50)
        result = EligibilityResult(
            issue=issue,
            eligible=False,
            reasons=["active repair PR #50 already open"],
            active_repair_pr=pr,
        )
        d = result.to_dict()
        assert d["eligible"] is False
        assert d["active_repair_pr"] == 50


# ── RepairQueue ────────────────────────────────────────────────


class TestRepairQueue:
    def test_to_dict(self) -> None:
        issue1 = _make_issue(number=1)
        issue2 = _make_issue(number=2, assignees=[])
        r1 = EligibilityResult(issue=issue1, eligible=True, reasons=[])
        r2 = EligibilityResult(issue=issue2, eligible=False, reasons=["not assigned"])
        queue = RepairQueue(eligible=[r1], ineligible=[r2], total_candidates=2)
        d = queue.to_dict()
        assert d["total_candidates"] == 2
        assert d["eligible_count"] == 1
        assert d["ineligible_count"] == 1
        assert len(d["eligible"]) == 1
        assert len(d["ineligible"]) == 1

    def test_format_text(self) -> None:
        issue1 = _make_issue(number=1, title="Fix stale events")
        r1 = EligibilityResult(issue=issue1, eligible=True, reasons=[])
        queue = RepairQueue(eligible=[r1], ineligible=[], total_candidates=1)
        text = queue.format_text()
        assert "Repair Queue" in text
        assert "Eligible: 1" in text
        assert "#    1" in text

    def test_format_text_empty(self) -> None:
        queue = RepairQueue(eligible=[], ineligible=[], total_candidates=0)
        text = queue.format_text()
        assert "Candidates: 0" in text

    def test_format_text_ineligible(self) -> None:
        issue = _make_issue(number=5, title="Blocked issue", assignees=[])
        r = EligibilityResult(issue=issue, eligible=False, reasons=["not assigned"])
        queue = RepairQueue(eligible=[], ineligible=[r], total_candidates=1)
        text = queue.format_text()
        assert "Not eligible" in text
        assert "not assigned" in text


# ── fetch helpers (mocked gh) ──────────────────────────────────


class TestFetchCandidateIssues:
    def test_parses_gh_output(self) -> None:
        gh_output = json.dumps(
            [
                {
                    "number": 42,
                    "title": "[fix] ops: stale",
                    "labels": [{"name": "agent-ready"}, {"name": "fix:bug"}],
                    "assignees": [{"login": "author-a"}],
                    "state": "OPEN",
                    "body": "repro context",
                }
            ]
        )

        def mock_gh(args: list[str]) -> str:
            return gh_output

        issues = fetch_candidate_issues(run_gh=mock_gh)
        assert len(issues) == 1
        assert issues[0].number == 42

    def test_empty_output(self) -> None:
        def mock_gh(args: list[str]) -> str:
            return "[]"

        issues = fetch_candidate_issues(run_gh=mock_gh)
        assert issues == []

    def test_whitespace_only_output(self) -> None:
        def mock_gh(args: list[str]) -> str:
            return "  \n  "

        issues = fetch_candidate_issues(run_gh=mock_gh)
        assert issues == []


class TestFetchOpenRepairPrs:
    def test_parses_gh_output(self) -> None:
        gh_output = json.dumps(
            [
                {
                    "number": 100,
                    "title": "fix(repair): stale event",
                    "state": "OPEN",
                    "headRefName": "fix/repair-stale",
                    "body": "Fixes #42",
                }
            ]
        )

        def mock_gh(args: list[str]) -> str:
            return gh_output

        prs = fetch_open_repair_prs(run_gh=mock_gh)
        assert len(prs) == 1
        assert prs[0].number == 100


# ── build_repair_queue (integration with mocked gh) ────────────


class TestBuildRepairQueue:
    def test_end_to_end(self) -> None:
        """Full queue build with one eligible and one ineligible issue."""
        call_count = 0

        def mock_gh(args: list[str]) -> str:
            nonlocal call_count
            call_count += 1
            if "issue" in args:
                return json.dumps(
                    [
                        {
                            "number": 1,
                            "title": "[fix] ops: eligible",
                            "labels": [{"name": "agent-ready"}, {"name": "fix:bug"}],
                            "assignees": [{"login": "author-a"}],
                            "state": "OPEN",
                            "body": "repro",
                        },
                        {
                            "number": 2,
                            "title": "[fix] ops: needs human",
                            "labels": [
                                {"name": "agent-ready"},
                                {"name": "needs-human"},
                            ],
                            "assignees": [{"login": "author-b"}],
                            "state": "OPEN",
                            "body": "complex",
                        },
                    ]
                )
            else:
                return "[]"

        queue = build_repair_queue(run_gh=mock_gh)
        assert call_count == 2  # issues + PRs
        assert queue.total_candidates == 2
        assert len(queue.eligible) == 1
        assert len(queue.ineligible) == 1
        assert queue.eligible[0].issue.number == 1
        assert queue.ineligible[0].issue.number == 2

    def test_empty_queue(self) -> None:
        def mock_gh(args: list[str]) -> str:
            return "[]"

        queue = build_repair_queue(run_gh=mock_gh)
        assert queue.total_candidates == 0
        assert queue.eligible == []
        assert queue.ineligible == []

    def test_json_serializable(self) -> None:
        """Queue.to_dict() produces valid JSON."""

        def mock_gh(args: list[str]) -> str:
            if "issue" in args:
                return json.dumps(
                    [
                        {
                            "number": 1,
                            "title": "test",
                            "labels": [{"name": "agent-ready"}],
                            "assignees": [{"login": "a"}],
                            "state": "OPEN",
                            "body": "",
                        }
                    ]
                )
            return "[]"

        queue = build_repair_queue(run_gh=mock_gh)
        # Should not raise
        result = json.dumps(queue.to_dict(), indent=2)
        parsed = json.loads(result)
        assert "eligible_count" in parsed


# ── Constants ──────────────────────────────────────────────────


class TestConstants:
    def test_required_labels(self) -> None:
        assert "agent-ready" in REQUIRED_LABELS

    def test_blocking_labels(self) -> None:
        assert "needs-human" in BLOCKING_LABELS

    def test_max_repair_attempts(self) -> None:
        assert MAX_REPAIR_ATTEMPTS == 2

    def test_repair_pr_prefix(self) -> None:
        assert REPAIR_PR_PREFIX == "fix(repair):"

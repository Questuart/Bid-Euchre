"""Tests for repair queue visibility (ops/repairs.py)."""

from __future__ import annotations

from bid_euchre.ops.repairs import (
    RepairCandidate,
    filter_eligible,
    format_repair_table,
    query_repair_candidates,
)

# ---------------------------------------------------------------------------
# RepairCandidate property tests
# ---------------------------------------------------------------------------


def test_eligible_basic():
    """Issue with agent-ready + follow-up and no blockers is eligible."""
    c = RepairCandidate(
        number=100,
        title="fix(bug): unseeded random",
        url="https://github.com/test/repo/issues/100",
        labels=["agent-ready", "follow-up", "fix:bug"],
    )
    assert c.is_eligible
    assert c.status_summary == "eligible"


def test_eligible_triage_source():
    """Issue with agent-ready + triage label is eligible."""
    c = RepairCandidate(
        number=101,
        title="[triage] ops: stale event",
        url="https://github.com/test/repo/issues/101",
        labels=["agent-ready", "triage", "fix:process"],
    )
    assert c.is_eligible


def test_not_eligible_missing_agent_ready():
    """Issue without agent-ready is not eligible."""
    c = RepairCandidate(
        number=102,
        title="fix(bug): something",
        url="",
        labels=["follow-up", "fix:bug"],
    )
    assert not c.is_eligible
    assert c.status_summary == "not-ready"


def test_not_eligible_needs_human():
    """Issue with needs-human is not eligible."""
    c = RepairCandidate(
        number=103,
        title="fix(bug): complex issue",
        url="",
        labels=["agent-ready", "follow-up", "fix:bug", "needs-human"],
    )
    assert not c.is_eligible
    assert c.status_summary == "needs-human"


def test_not_eligible_active_repair_pr():
    """Issue with an active repair PR is not eligible."""
    c = RepairCandidate(
        number=104,
        title="fix(bug): already being fixed",
        url="",
        labels=["agent-ready", "follow-up", "fix:bug"],
        has_active_repair_pr=True,
    )
    assert not c.is_eligible
    assert c.status_summary == "active-pr"


def test_not_eligible_no_repair_source_label():
    """Issue with agent-ready but no follow-up or triage label is not eligible."""
    c = RepairCandidate(
        number=105,
        title="some issue",
        url="",
        labels=["agent-ready", "fix:bug"],
    )
    assert not c.is_eligible


def test_claimed_status():
    """Eligible issue with assignees shows as claimed."""
    c = RepairCandidate(
        number=106,
        title="fix(bug): claimed",
        url="",
        labels=["agent-ready", "follow-up", "fix:bug"],
        assignees=["author-a"],
    )
    assert c.is_eligible
    assert c.is_claimed
    assert c.status_summary == "claimed"


def test_not_claimed():
    """Eligible issue without assignees is not claimed."""
    c = RepairCandidate(
        number=107,
        title="fix(bug): unclaimed",
        url="",
        labels=["agent-ready", "follow-up", "fix:bug"],
    )
    assert not c.is_claimed


# ---------------------------------------------------------------------------
# filter_eligible tests
# ---------------------------------------------------------------------------


def test_filter_eligible():
    """filter_eligible returns only eligible candidates."""
    eligible = RepairCandidate(
        number=1,
        title="good",
        url="",
        labels=["agent-ready", "follow-up"],
    )
    not_eligible = RepairCandidate(
        number=2,
        title="bad",
        url="",
        labels=["follow-up"],
    )
    blocked = RepairCandidate(
        number=3,
        title="blocked",
        url="",
        labels=["agent-ready", "follow-up", "needs-human"],
    )
    result = filter_eligible([eligible, not_eligible, blocked])
    assert len(result) == 1
    assert result[0].number == 1


# ---------------------------------------------------------------------------
# query_repair_candidates with injected data
# ---------------------------------------------------------------------------


def test_query_with_no_issues():
    """Empty issue list returns empty candidates."""
    candidates = query_repair_candidates(_issues=[], _open_prs=[])
    assert candidates == []


def test_query_basic_eligible():
    """Issue with correct labels is returned as eligible."""
    issues = [
        {
            "number": 200,
            "title": "fix(bug): test issue",
            "url": "https://github.com/test/repo/issues/200",
            "labels": [{"name": "agent-ready"}, {"name": "follow-up"}],
            "assignees": [],
        }
    ]
    candidates = query_repair_candidates(_issues=issues, _open_prs=[])
    assert len(candidates) == 1
    assert candidates[0].is_eligible
    assert not candidates[0].has_active_repair_pr


def test_query_detects_active_repair_pr():
    """Issue is marked as having an active repair PR when a PR references it."""
    issues = [
        {
            "number": 201,
            "title": "fix(bug): needs fix",
            "url": "",
            "labels": [{"name": "agent-ready"}, {"name": "follow-up"}],
            "assignees": [],
        }
    ]
    open_prs = [
        {
            "number": 300,
            "title": "fix: repair issue 201",
            "body": "This PR addresses the problem.\n\nFixes #201",
        }
    ]
    candidates = query_repair_candidates(_issues=issues, _open_prs=open_prs)
    assert len(candidates) == 1
    assert candidates[0].has_active_repair_pr
    assert not candidates[0].is_eligible


def test_query_no_false_positive_pr_match():
    """PR referencing a different issue number does not match."""
    issues = [
        {
            "number": 202,
            "title": "fix(bug): unrelated",
            "url": "",
            "labels": [{"name": "agent-ready"}, {"name": "triage"}],
            "assignees": [],
        }
    ]
    open_prs = [
        {
            "number": 301,
            "title": "fix: repair issue 999",
            "body": "Fixes #999",
        }
    ]
    candidates = query_repair_candidates(_issues=issues, _open_prs=open_prs)
    assert len(candidates) == 1
    assert not candidates[0].has_active_repair_pr
    assert candidates[0].is_eligible


def test_query_pr_closes_variant():
    """PR using 'Closes #N' also matches as active repair."""
    issues = [
        {
            "number": 203,
            "title": "fix(convention): test",
            "url": "",
            "labels": [{"name": "agent-ready"}, {"name": "follow-up"}],
            "assignees": [],
        }
    ]
    open_prs = [
        {
            "number": 302,
            "title": "fix: cleanup",
            "body": "Closes #203\n\nDetails here.",
        }
    ]
    candidates = query_repair_candidates(_issues=issues, _open_prs=open_prs)
    assert candidates[0].has_active_repair_pr


def test_query_with_assignees():
    """Assignees from GitHub are parsed correctly."""
    issues = [
        {
            "number": 204,
            "title": "fix(bug): assigned",
            "url": "",
            "labels": [{"name": "agent-ready"}, {"name": "follow-up"}],
            "assignees": [{"login": "author-a"}],
        }
    ]
    candidates = query_repair_candidates(_issues=issues, _open_prs=[])
    assert candidates[0].assignees == ["author-a"]
    assert candidates[0].is_claimed


# ---------------------------------------------------------------------------
# format_repair_table tests
# ---------------------------------------------------------------------------


def test_format_empty():
    """Empty candidate list produces a 'no issues' message."""
    output = format_repair_table([])
    assert "No repair-eligible issues found" in output


def test_format_table_structure():
    """Table output includes header, data rows, and summary."""
    candidates = [
        RepairCandidate(
            number=1,
            title="fix(bug): test",
            url="",
            labels=["agent-ready", "follow-up"],
        ),
        RepairCandidate(
            number=2,
            title="needs human",
            url="",
            labels=["agent-ready", "follow-up", "needs-human"],
        ),
    ]
    output = format_repair_table(candidates)
    # Header
    assert "Status" in output
    assert "Title" in output
    # Data
    assert "#1" in output
    assert "#2" in output
    # Summary
    assert "1 eligible" in output
    assert "1 available" in output


def test_format_claimed_shows_assignee():
    """Claimed issues show the assignee in the table."""
    candidates = [
        RepairCandidate(
            number=10,
            title="fix: claimed issue",
            url="",
            labels=["agent-ready", "follow-up"],
            assignees=["author-b"],
        ),
    ]
    output = format_repair_table(candidates)
    assert "author-b" in output
    assert "claimed" in output

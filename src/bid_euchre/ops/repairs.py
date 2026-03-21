"""Post-merge repair queue — eligibility and visibility helpers.

This module implements the bounded repair-lane contract defined in
``docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md`` (Repair Execution section).

A repair-eligible issue is one that an autonomous agent may pick up and
fix through a follow-up PR. Eligibility is determined by label state,
assignment, and the absence of an already-open repair PR for the same issue.

The module is designed to be testable without live GitHub access: all
``gh`` calls are isolated behind thin wrapper functions that tests can
mock.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Labels that must be present for repair eligibility.
REQUIRED_LABELS: frozenset[str] = frozenset({"agent-ready"})

#: Labels whose presence blocks repair eligibility.
BLOCKING_LABELS: frozenset[str] = frozenset({"needs-human"})

#: Maximum number of concurrent repair attempts per issue before escalation.
MAX_REPAIR_ATTEMPTS: int = 2

#: PR title prefix used by repair PRs for dedup / detection.
REPAIR_PR_PREFIX: str = "fix(repair):"

#: Label applied to repair follow-up PRs.
REPAIR_PR_LABEL: str = "follow-up"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RepairIssue:
    """Snapshot of a GitHub issue relevant to repair eligibility."""

    number: int
    title: str
    labels: frozenset[str]
    assignees: list[str]
    state: str  # "OPEN" / "CLOSED"
    body: str = ""

    @classmethod
    def from_gh_json(cls, data: dict[str, Any]) -> RepairIssue:
        """Construct from ``gh issue list --json`` output."""
        labels_raw = data.get("labels") or []
        label_names: list[str] = []
        for lab in labels_raw:
            if isinstance(lab, dict):
                label_names.append(lab.get("name", ""))
            else:
                label_names.append(str(lab))

        assignees_raw = data.get("assignees") or []
        assignee_logins: list[str] = []
        for a in assignees_raw:
            if isinstance(a, dict):
                assignee_logins.append(a.get("login", ""))
            else:
                assignee_logins.append(str(a))

        return cls(
            number=int(data.get("number", 0)),
            title=str(data.get("title", "")),
            labels=frozenset(label_names),
            assignees=assignee_logins,
            state=str(data.get("state", "OPEN")).upper(),
            body=str(data.get("body", "")),
        )


@dataclass(frozen=True)
class RepairPR:
    """Snapshot of a potentially-related repair PR."""

    number: int
    title: str
    state: str  # "OPEN" / "CLOSED" / "MERGED"
    head_branch: str = ""
    body: str = ""

    @classmethod
    def from_gh_json(cls, data: dict[str, Any]) -> RepairPR:
        """Construct from ``gh pr list --json`` output."""
        return cls(
            number=int(data.get("number", 0)),
            title=str(data.get("title", "")),
            state=str(data.get("state", "OPEN")).upper(),
            head_branch=str(data.get("headRefName", "")),
            body=str(data.get("body", "")),
        )


@dataclass
class EligibilityResult:
    """Result of checking a single issue for repair eligibility."""

    issue: RepairIssue
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    active_repair_pr: RepairPR | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "issue_number": self.issue.number,
            "title": self.issue.title,
            "eligible": self.eligible,
            "reasons": self.reasons,
            "labels": sorted(self.issue.labels),
            "assignees": self.issue.assignees,
        }
        if self.active_repair_pr is not None:
            result["active_repair_pr"] = self.active_repair_pr.number
        return result


# ---------------------------------------------------------------------------
# Eligibility logic (pure — no I/O)
# ---------------------------------------------------------------------------


def check_eligibility(
    issue: RepairIssue,
    open_repair_prs: list[RepairPR] | None = None,
) -> EligibilityResult:
    """Determine whether *issue* is eligible for autonomous repair.

    Eligibility requires **all** of:

    1. Issue is open.
    2. Issue has the ``agent-ready`` label.
    3. Issue does **not** have the ``needs-human`` label.
    4. Issue is assigned to at least one lane / person.
    5. No open repair PR already targets this issue.

    Parameters
    ----------
    issue:
        The issue to evaluate.
    open_repair_prs:
        Currently-open repair PRs. Used to detect whether a repair is
        already in flight for this issue. If ``None``, this check is
        skipped (useful when PR data is unavailable).

    Returns
    -------
    EligibilityResult
        Contains the boolean verdict and human-readable reasons for any
        disqualification.
    """
    reasons: list[str] = []
    active_pr: RepairPR | None = None

    # 1. Must be open
    if issue.state != "OPEN":
        reasons.append(f"issue is {issue.state.lower()}, not open")

    # 2. Must have required labels
    missing = REQUIRED_LABELS - issue.labels
    if missing:
        reasons.append(f"missing required labels: {', '.join(sorted(missing))}")

    # 3. Must not have blocking labels
    present_blockers = BLOCKING_LABELS & issue.labels
    if present_blockers:
        reasons.append(f"has blocking labels: {', '.join(sorted(present_blockers))}")

    # 4. Must be assigned
    if not issue.assignees:
        reasons.append("not assigned to any lane or person")

    # 5. No active repair PR for this issue
    if open_repair_prs is not None:
        for pr in open_repair_prs:
            if _pr_targets_issue(pr, issue.number):
                reasons.append(f"active repair PR #{pr.number} already open")
                active_pr = pr
                break

    eligible = len(reasons) == 0
    return EligibilityResult(
        issue=issue,
        eligible=eligible,
        reasons=reasons,
        active_repair_pr=active_pr,
    )


def _pr_targets_issue(pr: RepairPR, issue_number: int) -> bool:
    """Heuristic: does *pr* appear to target *issue_number*?

    Checks the PR title and body for references like ``#123`` or
    ``Fixes #123``.
    """
    ref = f"#{issue_number}"
    if ref in pr.title:
        return True
    if ref in pr.body:
        return True
    return False


# ---------------------------------------------------------------------------
# GitHub helpers (thin wrappers — mock these in tests)
# ---------------------------------------------------------------------------


def _run_gh(args: list[str]) -> str:
    """Run a ``gh`` CLI command and return stdout."""
    result = subprocess.run(  # noqa: S603
        ["gh", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"gh command failed (rc={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def fetch_candidate_issues(*, run_gh: Any = None) -> list[RepairIssue]:
    """Fetch open issues with the ``agent-ready`` label from GitHub.

    Parameters
    ----------
    run_gh:
        Optional override for the ``gh`` runner function (for testing).
        Must accept ``list[str]`` and return ``str``.
    """
    runner = run_gh or _run_gh
    raw = runner(
        [
            "issue",
            "list",
            "--label",
            "agent-ready",
            "--state",
            "open",
            "--json",
            "number,title,labels,assignees,state,body",
            "--limit",
            "50",
        ]
    )
    data = json.loads(raw) if raw.strip() else []
    return [RepairIssue.from_gh_json(item) for item in data]


def fetch_open_repair_prs(*, run_gh: Any = None) -> list[RepairPR]:
    """Fetch open PRs that look like repair follow-ups.

    Parameters
    ----------
    run_gh:
        Optional override for the ``gh`` runner function (for testing).
    """
    runner = run_gh or _run_gh
    raw = runner(
        [
            "pr",
            "list",
            "--label",
            "follow-up",
            "--state",
            "open",
            "--json",
            "number,title,state,headRefName,body",
            "--limit",
            "50",
        ]
    )
    data = json.loads(raw) if raw.strip() else []
    return [RepairPR.from_gh_json(item) for item in data]


# ---------------------------------------------------------------------------
# Queue view (orchestrates eligibility across all candidates)
# ---------------------------------------------------------------------------


@dataclass
class RepairQueue:
    """Full repair-queue snapshot."""

    eligible: list[EligibilityResult]
    ineligible: list[EligibilityResult]
    total_candidates: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_candidates": self.total_candidates,
            "eligible_count": len(self.eligible),
            "ineligible_count": len(self.ineligible),
            "eligible": [e.to_dict() for e in self.eligible],
            "ineligible": [e.to_dict() for e in self.ineligible],
        }

    def format_text(self) -> str:
        """Human-readable summary for CLI output."""
        lines: list[str] = []
        lines.append("=== Repair Queue ===")
        lines.append("")
        lines.append(
            f"Candidates: {self.total_candidates}  "
            f"Eligible: {len(self.eligible)}  "
            f"Ineligible: {len(self.ineligible)}"
        )

        if self.eligible:
            lines.append("")
            lines.append("Eligible for repair:")
            for er in self.eligible:
                assignees = ", ".join(er.issue.assignees) or "(none)"
                lines.append(
                    f"  #{er.issue.number:>5d}  {er.issue.title[:60]:<60s}  "
                    f"assigned={assignees}"
                )

        if self.ineligible:
            lines.append("")
            lines.append("Not eligible:")
            for er in self.ineligible:
                reason_str = "; ".join(er.reasons)
                lines.append(
                    f"  #{er.issue.number:>5d}  {er.issue.title[:60]:<60s}  "
                    f"({reason_str})"
                )

        return "\n".join(lines)


def build_repair_queue(
    *,
    run_gh: Any = None,
) -> RepairQueue:
    """Build a full repair-queue snapshot from live GitHub data.

    Parameters
    ----------
    run_gh:
        Optional ``gh`` runner override for testing.
    """
    issues = fetch_candidate_issues(run_gh=run_gh)
    prs = fetch_open_repair_prs(run_gh=run_gh)

    eligible: list[EligibilityResult] = []
    ineligible: list[EligibilityResult] = []

    for issue in issues:
        result = check_eligibility(issue, open_repair_prs=prs)
        if result.eligible:
            eligible.append(result)
        else:
            ineligible.append(result)

    return RepairQueue(
        eligible=eligible,
        ineligible=ineligible,
        total_candidates=len(issues),
    )

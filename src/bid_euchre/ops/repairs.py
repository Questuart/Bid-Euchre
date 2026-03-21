"""Repair queue visibility — query GitHub for repair-eligible issues.

An issue is repair-eligible when it meets all criteria from the repair
eligibility contract in ``docs/02_agent/ISSUE_TRIAGE_WORKFLOW.md``:

- Open
- Labeled ``agent-ready``
- Labeled ``follow-up`` or ``triage`` (repair source)
- NOT labeled ``needs-human``
- No open repair PR already linked to it

This module provides pure-logic helpers plus a thin ``gh`` CLI wrapper.
The CLI surface is wired through ``scripts/internal/ops.py repairs``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger("bid_euchre.ops.repairs")

# Labels that mark an issue as a potential repair source.
REPAIR_SOURCE_LABELS = frozenset({"follow-up", "triage"})

# Label that gates autonomous execution.
AGENT_READY_LABEL = "agent-ready"

# Label that blocks autonomous execution.
NEEDS_HUMAN_LABEL = "needs-human"


@dataclass
class RepairCandidate:
    """A GitHub issue that may be eligible for autonomous repair."""

    number: int
    title: str
    url: str
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    has_active_repair_pr: bool = False

    @property
    def is_claimed(self) -> bool:
        """Whether the issue has been claimed by a lane (has assignees)."""
        return len(self.assignees) > 0

    @property
    def is_eligible(self) -> bool:
        """Whether the issue meets all repair eligibility criteria."""
        return (
            AGENT_READY_LABEL in self.labels
            and any(lbl in REPAIR_SOURCE_LABELS for lbl in self.labels)
            and NEEDS_HUMAN_LABEL not in self.labels
            and not self.has_active_repair_pr
        )

    @property
    def status_summary(self) -> str:
        """Human-readable status for display."""
        if self.has_active_repair_pr:
            return "active-pr"
        if NEEDS_HUMAN_LABEL in self.labels:
            return "needs-human"
        if not self.is_eligible:
            return "not-ready"
        if self.is_claimed:
            return "claimed"
        return "eligible"


def filter_eligible(candidates: list[RepairCandidate]) -> list[RepairCandidate]:
    """Return only candidates that are fully eligible for repair."""
    return [c for c in candidates if c.is_eligible]


def _parse_issue(raw: dict) -> RepairCandidate:
    """Parse a raw GitHub issue JSON object into a RepairCandidate."""
    labels = [lbl["name"] for lbl in raw.get("labels", [])]
    assignees = [a["login"] for a in raw.get("assignees", [])]
    return RepairCandidate(
        number=raw["number"],
        title=raw["title"],
        url=raw.get("url", ""),
        labels=labels,
        assignees=assignees,
    )


def _has_open_repair_pr(issue_number: int, open_prs: list[dict]) -> bool:
    """Check if any open PR references ``Fixes #<issue_number>``."""
    pattern = re.compile(
        rf"(?:fixes|closes|resolves)\s+#?{issue_number}\b", re.IGNORECASE
    )
    for pr in open_prs:
        body = pr.get("body", "") or ""
        if pattern.search(body):
            return True
    return False


def query_repair_candidates(
    *,
    repo: str | None = None,
    _issues: list[dict] | None = None,
    _open_prs: list[dict] | None = None,
) -> list[RepairCandidate]:
    """Query GitHub for repair-eligible issues.

    Parameters
    ----------
    repo:
        GitHub repo in ``owner/name`` format.  Defaults to inferring from
        ``gh repo view``.
    _issues:
        Pre-fetched issue list (for testing).  When provided, skips the
        ``gh issue list`` call.
    _open_prs:
        Pre-fetched open PR list (for testing).  When provided, skips the
        ``gh pr list`` call.

    Returns
    -------
    list[RepairCandidate]
        All issues that have ``agent-ready`` plus a repair-source label,
        annotated with active-PR and eligibility status.
    """
    if _issues is None:
        _issues = _gh_list_issues(repo=repo)
    if _open_prs is None:
        _open_prs = _gh_list_open_prs(repo=repo)

    candidates: list[RepairCandidate] = []
    for raw in _issues:
        candidate = _parse_issue(raw)
        candidate.has_active_repair_pr = _has_open_repair_pr(
            candidate.number, _open_prs
        )
        candidates.append(candidate)

    return candidates


def _gh_list_issues(*, repo: str | None = None) -> list[dict]:
    """Fetch open issues labeled ``agent-ready`` from GitHub."""
    cmd = [
        "gh",
        "issue",
        "list",
        "--state",
        "open",
        "--label",
        AGENT_READY_LABEL,
        "--limit",
        "100",
        "--json",
        "number,title,labels,assignees,url",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("gh issue list failed: %s", result.stderr.strip())
        return []
    return json.loads(result.stdout)


def _gh_list_open_prs(*, repo: str | None = None) -> list[dict]:
    """Fetch open PRs to cross-check for active repair PRs."""
    cmd = [
        "gh",
        "pr",
        "list",
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,title,body",
    ]
    if repo:
        cmd.extend(["--repo", repo])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning("gh pr list failed: %s", result.stderr.strip())
        return []
    return json.loads(result.stdout)


def format_repair_table(candidates: list[RepairCandidate]) -> str:
    """Format candidates as a human-readable table.

    Returns a multi-line string suitable for terminal output.
    """
    if not candidates:
        return "No repair-eligible issues found."

    lines: list[str] = []
    # Header
    lines.append(f"{'#':<7} {'Status':<14} {'Claimed':<12} {'Title'}")
    lines.append("-" * 70)

    for c in candidates:
        claimed = ", ".join(c.assignees) if c.assignees else "-"
        lines.append(f"#{c.number:<6} {c.status_summary:<14} {claimed:<12} {c.title}")

    # Summary
    eligible = sum(1 for c in candidates if c.is_eligible)
    claimed = sum(1 for c in candidates if c.is_eligible and c.is_claimed)
    lines.append("")
    lines.append(
        f"Total: {len(candidates)} issues | "
        f"{eligible} eligible | "
        f"{claimed} claimed | "
        f"{eligible - claimed} available"
    )

    return "\n".join(lines)

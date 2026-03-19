"""Provider-neutral PR review outcome aggregation.

Queries GitHub for open PRs and enriches each with CI status,
review commit-status, and deterministic precheck status.

GitHub is the source of truth for review outcomes (online-first).
This module does NOT depend on .claude/runtime/review_loops/** —
those are transitional/legacy only.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass

logger = logging.getLogger("ops.reviews")


@dataclass
class ReviewOutcome:
    """Provider-neutral summary of a PR's review/CI state."""

    pr_number: int
    title: str
    branch: str
    ci_status: str  # "success", "failure", "pending", "unknown"
    review_status: str  # "success", "failure", "pending", "none"
    has_precheck_ci: bool  # whether deterministic-prechecks check exists
    url: str
    checks: list[dict] | None = None  # per-check breakdown when available

    def to_dict(self) -> dict:
        return asdict(self)


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a gh CLI command and return the result."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )


def _get_open_prs() -> list[dict]:
    """List open PRs via gh CLI.

    Returns:
        List of dicts with keys: number, title, headRefName, url.
    """
    result = _run_gh(
        [
            "pr",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,headRefName,url",
            "--limit",
            "50",
        ]
    )
    if result.returncode != 0:
        logger.warning("gh pr list failed: %s", result.stderr[:200])
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning("Invalid JSON from gh pr list: %s", result.stdout[:200])
        return []


def _get_pr_checks(pr_number: int) -> list[dict]:
    """Get all checks/statuses for a PR.

    Returns:
        List of dicts with keys: name, state, description (when available).
    """
    result = _run_gh(
        [
            "pr",
            "checks",
            str(pr_number),
            "--json",
            "name,state",
        ]
    )
    if result.returncode != 0:
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def _classify_ci_status(checks: list[dict]) -> str:
    """Classify overall CI status from individual checks.

    Excludes the reviewing-changes status to avoid circular dependency.

    Returns:
        "success", "failure", "pending", or "unknown"
    """
    # Filter out review loop's own status
    ci_checks = [c for c in checks if c.get("name") != "reviewing-changes"]
    if not ci_checks:
        return "pending"

    states = [c.get("state", "PENDING") for c in ci_checks]

    if any(s == "FAILURE" for s in states):
        return "failure"
    if any(s in ("PENDING", "IN_PROGRESS") for s in states):
        return "pending"
    if all(s == "SUCCESS" for s in states):
        return "success"
    return "unknown"


def _get_review_status(checks: list[dict]) -> str:
    """Extract the reviewing-changes commit status.

    Returns:
        "success", "failure", "pending", or "none" (if no such status exists).
    """
    for check in checks:
        if check.get("name") == "reviewing-changes":
            state = check.get("state", "PENDING")
            return {
                "SUCCESS": "success",
                "FAILURE": "failure",
                "PENDING": "pending",
                "IN_PROGRESS": "pending",
            }.get(state, "unknown")
    return "none"


def _has_precheck_ci(checks: list[dict]) -> bool:
    """Check whether a deterministic-prechecks GitHub check exists."""
    return any(
        "deterministic" in c.get("name", "").lower()
        or "precheck" in c.get("name", "").lower()
        for c in checks
    )


def get_open_pr_reviews() -> list[ReviewOutcome]:
    """Get review outcomes for all open PRs.

    Queries GitHub for open PRs, then enriches each with CI status,
    review commit-status, and deterministic precheck status.

    Returns:
        List of ReviewOutcome objects, sorted by PR number.
    """
    prs = _get_open_prs()
    outcomes: list[ReviewOutcome] = []

    for pr in prs:
        pr_number = pr["number"]
        checks = _get_pr_checks(pr_number)

        outcomes.append(
            ReviewOutcome(
                pr_number=pr_number,
                title=pr.get("title", ""),
                branch=pr.get("headRefName", ""),
                ci_status=_classify_ci_status(checks),
                review_status=_get_review_status(checks),
                has_precheck_ci=_has_precheck_ci(checks),
                url=pr.get("url", ""),
                checks=checks,
            )
        )

    return sorted(outcomes, key=lambda o: o.pr_number)


def get_pr_review_detail(pr_number: int) -> ReviewOutcome:
    """Get detailed review outcome for a single PR.

    Args:
        pr_number: PR number.

    Returns:
        ReviewOutcome with per-check breakdown.

    Raises:
        RuntimeError: If PR metadata cannot be fetched.
    """
    result = _run_gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,headRefName,url",
        ]
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get PR #{pr_number}: {result.stderr}")

    try:
        pr = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON for PR #{pr_number}: {e}") from e

    checks = _get_pr_checks(pr_number)

    return ReviewOutcome(
        pr_number=pr["number"],
        title=pr.get("title", ""),
        branch=pr.get("headRefName", ""),
        ci_status=_classify_ci_status(checks),
        review_status=_get_review_status(checks),
        has_precheck_ci=_has_precheck_ci(checks),
        url=pr.get("url", ""),
        checks=checks,
    )


# --- Formatting ---


def format_reviews_text(outcomes: list[ReviewOutcome]) -> str:
    """Format review outcomes as human-readable text."""
    if not outcomes:
        return "=== PR Reviews ===\n\nNo open PRs."

    lines = ["=== PR Reviews ===", ""]
    for o in outcomes:
        ci_icon = {"success": "+", "failure": "x", "pending": "~"}.get(o.ci_status, "?")
        review_icon = {"success": "+", "failure": "x", "pending": "~"}.get(
            o.review_status, "-"
        )
        precheck = "yes" if o.has_precheck_ci else "no"
        lines.append(
            f"  #{o.pr_number:<5d} CI=[{ci_icon}] Review=[{review_icon}] "
            f"Precheck=[{precheck}]"
        )
        lines.append(f"         {o.title}")
        lines.append(f"         {o.branch} | {o.url}")
        lines.append("")

    lines.append(f"Total: {len(outcomes)} open PR(s)")
    return "\n".join(lines)


def format_reviews_json(outcomes: list[ReviewOutcome]) -> list[dict]:
    """Format review outcomes as JSON-serializable list."""
    return [
        {
            "pr_number": o.pr_number,
            "title": o.title,
            "branch": o.branch,
            "ci_status": o.ci_status,
            "review_status": o.review_status,
            "has_precheck_ci": o.has_precheck_ci,
            "url": o.url,
        }
        for o in outcomes
    ]

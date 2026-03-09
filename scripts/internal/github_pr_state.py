"""GitHub PR state queries via gh CLI.

Thin wrappers around `gh` commands for querying PR metadata,
CI status, and publishing review status. Used by the review
loop state machine.

Does NOT merge PRs (rollout constraint).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class PRMetadata:
    """Subset of PR metadata needed by the review loop."""

    number: int
    title: str
    branch: str
    state: str  # "OPEN", "CLOSED", "MERGED"
    head_sha: str
    url: str


def get_pr_metadata(pr_number: int) -> PRMetadata:
    """Get PR metadata from GitHub."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,headRefName,state,headRefOid,url",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get PR #{pr_number}: {result.stderr}")

    data = json.loads(result.stdout)
    return PRMetadata(
        number=data["number"],
        title=data["title"],
        branch=data["headRefName"],
        state=data["state"],
        head_sha=data["headRefOid"],
        url=data["url"],
    )


def get_pr_head_sha(pr_number: int) -> str:
    """Get the HEAD SHA of a PR."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "headRefOid",
            "--jq",
            ".headRefOid",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get PR #{pr_number} head SHA: {result.stderr}")
    return result.stdout.strip()


def get_ci_status(pr_number: int) -> str:
    """Get the CI status of a PR.

    Returns:
        "success", "failure", "pending", or "unknown"
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "checks",
            str(pr_number),
            "--json",
            "name,state,conclusion",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"

    checks = json.loads(result.stdout)
    if not checks:
        return "pending"

    states = []
    for check in checks:
        conclusion = check.get("conclusion", "")
        state = check.get("state", "")
        if state == "COMPLETED":
            states.append(conclusion)
        else:
            states.append("PENDING")

    if any(s == "FAILURE" for s in states):
        return "failure"
    if any(s == "PENDING" for s in states):
        return "pending"
    if all(s == "SUCCESS" for s in states):
        return "success"
    return "unknown"


def publish_review_status(
    pr_number: int,
    state: str,
    description: str,
    *,
    context: str = "reviewing-changes",
) -> bool:
    """Publish a commit status via set_review_status.sh.

    Args:
        pr_number: PR number (used to get HEAD SHA).
        state: One of "pending", "success", "failure", "error".
        description: Short description (max 140 chars).
        context: Status context name.

    Returns:
        True if status was published, False if script not found or failed.
    """
    from pathlib import Path

    script = Path("scripts/internal/set_review_status.sh")
    if not script.exists():
        return False

    try:
        sha = get_pr_head_sha(pr_number)
    except RuntimeError:
        return False

    result = subprocess.run(
        [str(script), state, description, "", context, sha],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

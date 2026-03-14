"""GitHub PR state queries via gh CLI.

Thin wrappers around `gh` commands for querying PR metadata,
CI status, publishing review status, and enabling auto-merge.
Used by the review loop state machine.
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
    body: str = ""


def get_pr_metadata(pr_number: int) -> PRMetadata:
    """Get PR metadata from GitHub."""
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "number,title,headRefName,state,headRefOid,url,body",
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
        body=data.get("body", ""),
    )


def get_pr_body(pr_number: int) -> str:
    """Get the body (description) of a PR.

    Args:
        pr_number: PR number.

    Returns:
        PR body text.

    Raises:
        RuntimeError: If the gh CLI call fails.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "body",
            "--jq",
            ".body",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get PR #{pr_number} body: {result.stderr}")
    return result.stdout.strip()


def get_pr_changed_files(pr_number: int) -> list[str]:
    """Get the list of files changed in a PR.

    Args:
        pr_number: PR number.

    Returns:
        List of relative file paths changed in the PR.

    Raises:
        RuntimeError: If the gh CLI call fails.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "diff",
            str(pr_number),
            "--name-only",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to get PR #{pr_number} changed files: {result.stderr}"
        )
    return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]


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

    Excludes the ``reviewing-changes`` commit status to avoid circular
    dependency (the review loop publishes that status itself).

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
            "name,state",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "unknown"

    checks = json.loads(result.stdout)
    # Filter out the review loop's own status to avoid circular dependency
    checks = [c for c in checks if c.get("name") != "reviewing-changes"]
    if not checks:
        return "pending"

    states = [c.get("state", "PENDING") for c in checks]

    if any(s == "FAILURE" for s in states):
        return "failure"
    if any(s in ("PENDING", "IN_PROGRESS") for s in states):
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


def enable_auto_merge(pr_number: int, *, method: str = "squash") -> bool:
    """Enable GitHub auto-merge on a PR.

    Uses `gh pr merge --auto` which queues the merge for when all
    branch protection requirements are satisfied (CI, required statuses).

    Args:
        pr_number: PR number.
        method: Merge method ("squash", "merge", "rebase").

    Returns:
        True if auto-merge was enabled, False otherwise.
    """
    flag = f"--{method}"
    result = subprocess.run(
        ["gh", "pr", "merge", str(pr_number), "--auto", flag],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

"""GitHub PR state queries via gh CLI.

Thin wrappers around `gh` commands for querying PR metadata,
CI status, publishing review status, enabling auto-merge,
and managing machine-owned PR comments.
Used by the review loop state machine.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("github_pr_state")

# HTML comment marker for deduplication of machine-owned PR comments.
REVIEW_COMMENT_MARKER = "<!-- review-loop-comment -->"


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


# CI check classification — single source of truth is classify_check()
# in bid_euchre.ops (fail-open denylist: unknown checks default to "ci").
# See #1036 for the unification rationale.
try:
    from bid_euchre.ops import classify_check as _classify_check
except ImportError:
    # Fallback for environments where bid_euchre is not installed.
    # Inline the denylist logic so new CI jobs are still included by default.
    # Keep in sync with REVIEW_GATE_CONTEXTS + ADVISORY_CONTEXTS in ops/__init__.py.
    _FALLBACK_NON_CI: frozenset[str] = frozenset(
        {"reviewing-changes", "claude-review", "enable-auto-merge"}
    )

    def _classify_check(name: str) -> str:  # type: ignore[misc]
        """Inline fallback for classify_check when bid_euchre is not installed."""
        if name in _FALLBACK_NON_CI:
            return "non_ci"
        return "ci"


def get_ci_status(pr_number: int) -> str:
    """Get the CI status of a PR.

    Uses :func:`classify_check` (fail-open denylist) so that only known
    non-CI checks (review gates, advisory) are excluded.  New CI jobs
    are included by default without needing allowlist updates.

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
    # Exclude non-CI checks (review gate + advisory) via classify_check
    ci_checks = [c for c in checks if _classify_check(c.get("name", "")) == "ci"]
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


def _find_review_comment_id(pr_number: int) -> int | None:
    """Search for an existing machine-owned review comment on a PR.

    Looks for a comment containing the ``REVIEW_COMMENT_MARKER`` HTML
    comment tag.

    Args:
        pr_number: PR number.

    Returns:
        Comment node ID (integer) if found, None otherwise.
    """
    result = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
            "--jq",
            ".[].id",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning(
            "PR #%d: failed to list comments: %s", pr_number, result.stderr[:200]
        )
        return None

    comment_ids = [
        int(line.strip()) for line in result.stdout.strip().split("\n") if line.strip()
    ]
    if not comment_ids:
        return None

    # Check each comment for our marker
    for cid in comment_ids:
        body_result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/issues/comments/{cid}",
                "--jq",
                ".body",
            ],
            capture_output=True,
            text=True,
        )
        if body_result.returncode == 0 and REVIEW_COMMENT_MARKER in body_result.stdout:
            return cid

    return None


def upsert_review_comment(pr_number: int, body: str) -> bool:
    """Create or update a single machine-owned PR comment.

    Uses ``REVIEW_COMMENT_MARKER`` (an HTML comment tag) for deduplication.
    If a comment with the marker already exists, it is updated in place.
    Otherwise a new comment is created.

    The marker is prepended to the body automatically if not already present.

    Args:
        pr_number: PR number.
        body: Full markdown body for the comment.

    Returns:
        True if the comment was created or updated successfully.
    """
    # Ensure marker is present
    if REVIEW_COMMENT_MARKER not in body:
        body = f"{REVIEW_COMMENT_MARKER}\n{body}"

    existing_id = _find_review_comment_id(pr_number)

    if existing_id is not None:
        # Update existing comment
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{{owner}}/{{repo}}/issues/comments/{existing_id}",
                "--method",
                "PATCH",
                "--field",
                f"body={body}",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info(
                "PR #%d: updated review comment (id=%d)", pr_number, existing_id
            )
            return True
        logger.warning(
            "PR #%d: failed to update comment %d: %s",
            pr_number,
            existing_id,
            result.stderr[:200],
        )
        return False

    # Create new comment
    result = subprocess.run(
        [
            "gh",
            "pr",
            "comment",
            str(pr_number),
            "--body",
            body,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        logger.info("PR #%d: created review comment", pr_number)
        return True
    logger.warning(
        "PR #%d: failed to create comment: %s",
        pr_number,
        result.stderr[:200],
    )
    return False

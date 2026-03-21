"""Provider-neutral PR review outcome aggregation.

Queries GitHub for open PRs and enriches each with CI status,
review commit-status, deterministic precheck status, and
comment-based review overlays (e.g., Codex Cloud bot comments).

GitHub is the source of truth for review outcomes (online-first).
This module does NOT depend on .claude/runtime/review_loops/** —
those are transitional/legacy only.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bid_euchre.ops import (
    ADVISORY_CONTEXTS,
    DEFAULT_REVIEW_CONTEXTS,  # noqa: F401 — re-exported for backward compat
    GH_TIMEOUT_SECONDS,
    REVIEW_GATE_CONTEXTS,
    classify_check,
)

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
    advisory_status: str = "none"  # "success", "failure", "pending", "none"
    checks: list[dict] | None = None  # per-check breakdown when available

    def to_dict(self) -> dict:
        return asdict(self)


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a gh CLI command and return the result.

    Uses ``GH_TIMEOUT_SECONDS`` to prevent indefinite hangs. On timeout,
    returns a synthetic failure result so callers degrade gracefully.
    """
    try:
        return subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.warning(
            "gh CLI timed out after %ds: gh %s", GH_TIMEOUT_SECONDS, " ".join(args)
        )
        return subprocess.CompletedProcess(
            args=["gh", *args],
            returncode=1,
            stdout="",
            stderr=f"Timed out after {GH_TIMEOUT_SECONDS}s",
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
        if "Timed out" in result.stderr:
            logger.error(
                "gh pr list timed out — review data unavailable: %s",
                result.stderr[:200],
            )
        else:
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


def _classify_ci_status(
    checks: list[dict],
    review_contexts: tuple[str, ...] | None = None,
) -> str:
    """Classify overall CI status from individual checks.

    Excludes non-CI status contexts (review gate + advisory) to avoid
    circular dependency and prevent advisory infra failures from poisoning
    CI status.

    Args:
        checks: List of check dicts with ``name`` and ``state`` keys.
        review_contexts: Explicit check names to exclude. When ``None``
            (default), uses ``classify_check()`` to dynamically identify
            non-CI checks. Pass an explicit tuple for backward compatibility.

    Returns:
        "success", "failure", "pending", or "unknown"
    """
    if review_contexts is not None:
        # Backward-compatible: explicit exclusion list
        ci_checks = [c for c in checks if c.get("name") not in review_contexts]
    else:
        # Default: use classify_check() to exclude all non-CI checks
        ci_checks = [c for c in checks if classify_check(c.get("name", "")) == "ci"]
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


def _get_review_status(
    checks: list[dict],
    review_contexts: tuple[str, ...] = REVIEW_GATE_CONTEXTS,
) -> str:
    """Extract review status from recognized review contexts.

    Collects all checks matching ``review_contexts`` and aggregates
    deterministically: any FAILURE → ``"failure"``, any PENDING →
    ``"pending"``, all SUCCESS → ``"success"``.  When multiple review
    providers coexist, this avoids silently ignoring a failing provider
    just because another provider appears first in the check list.

    Args:
        checks: List of check dicts with ``name`` and ``state`` keys.
        review_contexts: Check names recognized as review outcomes.

    Returns:
        "success", "failure", "pending", or "none" (if no review context found).
    """
    states = [
        check.get("state", "PENDING")
        for check in checks
        if check.get("name") in review_contexts
    ]
    if not states:
        return "none"
    if any(s == "FAILURE" for s in states):
        return "failure"
    if any(s in ("PENDING", "IN_PROGRESS") for s in states):
        return "pending"
    if all(s == "SUCCESS" for s in states):
        return "success"
    return "unknown"


def _has_precheck_ci(checks: list[dict]) -> bool:
    """Check whether a deterministic-prechecks GitHub check exists."""
    return any(
        "deterministic" in c.get("name", "").lower()
        or "precheck" in c.get("name", "").lower()
        for c in checks
    )


def _get_advisory_status(
    checks: list[dict],
    advisory_contexts: tuple[str, ...] = ADVISORY_CONTEXTS,
) -> str:
    """Extract advisory review status from recognized advisory contexts.

    Same aggregation pattern as ``_get_review_status`` but filters on
    ``ADVISORY_CONTEXTS`` (informational checks that must not block CI).

    Args:
        checks: List of check dicts with ``name`` and ``state`` keys.
        advisory_contexts: Check names recognized as advisory outcomes.

    Returns:
        "success", "failure", "pending", or "none" (if no advisory context found).
    """
    states = [
        check.get("state", "PENDING")
        for check in checks
        if check.get("name") in advisory_contexts
    ]
    if not states:
        return "none"
    if any(s == "FAILURE" for s in states):
        return "failure"
    if any(s in ("PENDING", "IN_PROGRESS") for s in states):
        return "pending"
    if all(s == "SUCCESS" for s in states):
        return "success"
    return "unknown"


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
                advisory_status=_get_advisory_status(checks),
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
        advisory_status=_get_advisory_status(checks),
        checks=checks,
    )


# --- Event Emission ---


def emit_review_event(
    outcome: ReviewOutcome,
    lane_id: str,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit a ``review_outcome`` event based on a ``ReviewOutcome``.

    This is the review-side counterpart to ``ci.emit_ci_events()``.
    It translates a PR review outcome into a durable event:

    - ``review_status`` in ``("success", "failure")`` → ``review_outcome``
    - ``review_status`` in ``("pending", "none")`` → no event (returns None)

    .. note::

        This function is **not yet wired** into any production polling
        path (scheduler, ops CLI, or review loop). It must be called
        explicitly by the caller. Production wiring is tracked as
        follow-up work.

    Args:
        outcome: Review outcome from ``get_open_pr_reviews()`` or
            ``get_pr_review_detail()``.
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        events_dir: Override for events directory. Defaults to
            ``.claude/runtime/events``.

    Returns:
        The emitted event dict, or None if the review status does not
        warrant an event (pending/none).
    """
    if outcome.review_status not in ("success", "failure"):
        return None

    from bid_euchre.ops.events import append_event

    payload: dict[str, Any] = {
        "pr_number": outcome.pr_number,
        "review_status": outcome.review_status,
        "ci_status": outcome.ci_status,
        "branch": outcome.branch,
    }

    if outcome.advisory_status != "none":
        payload["advisory_status"] = outcome.advisory_status

    return append_event(
        event_type="review_outcome",
        source="ops.reviews",
        lane_id=lane_id,
        payload=payload,
        events_dir=events_dir,
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
        advisory_icon = {"success": "+", "failure": "x", "pending": "~"}.get(
            o.advisory_status, "-"
        )
        precheck = "yes" if o.has_precheck_ci else "no"
        lines.append(
            f"  #{o.pr_number:<5d} CI=[{ci_icon}] Review=[{review_icon}] "
            f"Advisory=[{advisory_icon}] Precheck=[{precheck}]"
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
            "advisory_status": o.advisory_status,
            "has_precheck_ci": o.has_precheck_ci,
            "url": o.url,
        }
        for o in outcomes
    ]


# --- Comment-Based Review Overlays ---
# PR issue comments are a separate signal channel from checks/statuses.
# Codex Cloud arrives as issue comments, not checks — these overlays surface
# comment-derived signals without conflating them with CI or the merge gate.
# This is the SINGLE canonical location for comment-author classification.

# Trusted bot logins for comment-based review signals (never speculative).
TRUSTED_BOT_LOGINS: frozenset[str] = frozenset(
    {
        "chatgpt-codex-connector[bot]",
    }
)

# GitHub user types that indicate bot accounts.
_BOT_USER_TYPES: frozenset[str] = frozenset({"Bot", "bot"})

# Maximum body excerpt length for comment overlay summaries.
_MAX_EXCERPT_LEN: int = 200


def classify_comment_author(login: str, user_type: str = "") -> str:
    """Classify a comment author as human, trusted_bot, or other_bot.

    Args:
        login: GitHub username (e.g., ``"octocat"`` or
            ``"chatgpt-codex-connector[bot]"``).
        user_type: GitHub user type field (e.g., ``"User"``, ``"Bot"``).
            When empty, classification falls back to login pattern matching.

    Returns:
        ``"trusted_bot"`` if login is in ``TRUSTED_BOT_LOGINS``,
        ``"other_bot"`` if user_type is ``"Bot"`` or login ends with ``[bot]``,
        ``"human"`` otherwise.
    """
    if login in TRUSTED_BOT_LOGINS:
        return "trusted_bot"
    if user_type in _BOT_USER_TYPES or login.endswith("[bot]"):
        return "other_bot"
    return "human"


@dataclass
class CommentOverlay:
    """Per-PR summary of comment-based review signals.

    Surfaces PR issue comments as operational overlays, separate from
    CI checks and the ``reviewing-changes`` status gate.
    """

    pr_number: int
    total_comments: int = 0
    trusted_bot_comments: int = 0
    human_comments: int = 0
    other_bot_comments: int = 0
    latest_trusted_bot_excerpt: str | None = None
    latest_trusted_bot_author: str | None = None
    latest_trusted_bot_time: str | None = None
    comments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _get_pr_issue_comments(pr_number: int) -> list[dict]:
    """Fetch issue comments for a PR via gh API.

    Returns:
        List of dicts with keys: id, login, user_type, created_at, body.
        Returns empty list on failure (graceful degradation).
    """
    jq_expr = (
        "[.[] | {id: .id, login: .user.login, user_type: .user.type, "
        "created_at: .created_at, body: .body}]"
    )
    result = _run_gh(
        [
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
            "--jq",
            jq_expr,
        ]
    )
    if result.returncode != 0:
        logger.warning(
            "PR #%d: failed to fetch comments: %s",
            pr_number,
            result.stderr[:200],
        )
        return []

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(
            "PR #%d: invalid JSON from comment fetch: %s",
            pr_number,
            result.stdout[:200],
        )
        return []


def get_pr_comment_overlay(
    pr_number: int,
    *,
    raw_comments: list[dict] | None = None,
) -> CommentOverlay:
    """Build a comment overlay for a single PR.

    Fetches issue comments from GitHub (or accepts pre-fetched data),
    classifies each by author identity, and produces an overlay summary.

    Args:
        pr_number: PR number.
        raw_comments: Pre-fetched comment dicts (for testing or batching).
            When ``None``, fetches from GitHub.

    Returns:
        :class:`CommentOverlay` summarizing comment signals.
    """
    if raw_comments is None:
        raw_comments = _get_pr_issue_comments(pr_number)

    overlay = CommentOverlay(pr_number=pr_number)
    overlay.total_comments = len(raw_comments)

    latest_trusted: dict | None = None

    for raw in raw_comments:
        login = raw.get("login", "")
        user_type = raw.get("user_type", "")
        author_type = classify_comment_author(login, user_type)

        comment_record = {
            "comment_id": raw.get("id", 0),
            "author_login": login,
            "author_type": author_type,
            "created_at": raw.get("created_at", ""),
            "body_excerpt": (raw.get("body", "") or "")[:_MAX_EXCERPT_LEN],
        }
        overlay.comments.append(comment_record)

        if author_type == "trusted_bot":
            overlay.trusted_bot_comments += 1
            if latest_trusted is None or raw.get("created_at", "") > latest_trusted.get(
                "created_at", ""
            ):
                latest_trusted = raw
        elif author_type == "other_bot":
            overlay.other_bot_comments += 1
        else:
            overlay.human_comments += 1

    if latest_trusted is not None:
        body = latest_trusted.get("body", "") or ""
        overlay.latest_trusted_bot_excerpt = body[:_MAX_EXCERPT_LEN]
        overlay.latest_trusted_bot_author = latest_trusted.get("login", "")
        overlay.latest_trusted_bot_time = latest_trusted.get("created_at", "")

    return overlay


def format_comment_overlays_text(overlays: list[CommentOverlay]) -> str:
    """Format comment overlays as human-readable text."""
    if not overlays:
        return "=== PR Comment Overlays ===\n\nNo comment data."

    lines = ["=== PR Comment Overlays ===", ""]
    for o in overlays:
        trusted_icon = "+" if o.trusted_bot_comments > 0 else "-"
        lines.append(
            f"  #{o.pr_number:<5d} Comments={o.total_comments} "
            f"Trusted=[{trusted_icon}:{o.trusted_bot_comments}] "
            f"Human={o.human_comments} OtherBot={o.other_bot_comments}"
        )
        if o.latest_trusted_bot_author:
            lines.append(
                f"         Latest trusted: {o.latest_trusted_bot_author} "
                f"@ {o.latest_trusted_bot_time}"
            )
            if o.latest_trusted_bot_excerpt:
                excerpt = o.latest_trusted_bot_excerpt.replace("\n", " ")[:80]
                lines.append(f"         > {excerpt}...")
        lines.append("")

    return "\n".join(lines)


def format_comment_overlays_json(overlays: list[CommentOverlay]) -> list[dict]:
    """Format comment overlays as JSON-serializable list."""
    return [
        {
            "pr_number": o.pr_number,
            "total_comments": o.total_comments,
            "trusted_bot_comments": o.trusted_bot_comments,
            "human_comments": o.human_comments,
            "other_bot_comments": o.other_bot_comments,
            "latest_trusted_bot_excerpt": o.latest_trusted_bot_excerpt,
            "latest_trusted_bot_author": o.latest_trusted_bot_author,
            "latest_trusted_bot_time": o.latest_trusted_bot_time,
            "comments": o.comments,
        }
        for o in overlays
    ]


# ---------------------------------------------------------------------------
# Review Queue Visibility (PR3)
# ---------------------------------------------------------------------------
# Read-only view into the local review_queue substrate.  This surfaces
# request + verdict packet state so operators can see pending / blocked /
# clean / stale / error states before the PR4 cutover.
#
# Conceptually separate from the online GitHub-based ReviewOutcome above.
# ---------------------------------------------------------------------------

# Effective status values for queue entries
QUEUE_NO_REQUEST = "no_request"
QUEUE_PENDING = "pending"
QUEUE_RUNNING = "running"
QUEUE_PASSED = "passed"
QUEUE_BLOCKED = "blocked"
QUEUE_FAILED = "failed"
QUEUE_STALE = "stale"
QUEUE_ERROR = "error"


@dataclass
class QueueEntry:
    """Summary of a single PR's review queue state.

    Combines request + verdict packet data into a single operator-facing
    view with an ``effective_status`` that makes the state obvious.
    """

    pr_number: int
    has_request: bool
    request_sha: str | None = None
    request_branch: str | None = None
    request_requester: str | None = None
    request_created_at: str | None = None
    has_verdict: bool = False
    verdict_status: str | None = None
    verdict_sha: str | None = None
    verdict_reason: str | None = None
    verdict_created_at: str | None = None
    verdict_findings_count: int = 0
    is_stale: bool = False
    effective_status: str = QUEUE_NO_REQUEST

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_number": self.pr_number,
            "has_request": self.has_request,
            "request_sha": self.request_sha,
            "request_branch": self.request_branch,
            "request_requester": self.request_requester,
            "request_created_at": self.request_created_at,
            "has_verdict": self.has_verdict,
            "verdict_status": self.verdict_status,
            "verdict_sha": self.verdict_sha,
            "verdict_reason": self.verdict_reason,
            "verdict_created_at": self.verdict_created_at,
            "verdict_findings_count": self.verdict_findings_count,
            "is_stale": self.is_stale,
            "effective_status": self.effective_status,
        }


def _compute_effective_status(
    request: Any | None,
    verdict: Any | None,
) -> tuple[str, bool]:
    """Compute effective status and staleness from request + verdict.

    Args:
        request: A ``ReviewRequest`` or ``None``.
        verdict: A ``ReviewVerdict`` or ``None``.

    Returns:
        (effective_status, is_stale) tuple.
    """
    if request is None:
        return (QUEUE_NO_REQUEST, False)

    if verdict is None:
        return (QUEUE_PENDING, False)

    # Check staleness: verdict covers a different SHA than the request
    is_stale = verdict.reviewed_sha != request.head_sha
    if is_stale:
        return (QUEUE_STALE, True)

    # Fresh verdict — map status
    status_map = {
        "pending": QUEUE_PENDING,
        "running": QUEUE_RUNNING,
        "passed": QUEUE_PASSED,
        "blocked": QUEUE_BLOCKED,
        "failed": QUEUE_FAILED,
    }
    effective = status_map.get(verdict.status, QUEUE_ERROR)
    return (effective, False)


def get_queue_entry(
    pr_number: int,
    queue_dir: Path | None = None,
) -> QueueEntry:
    """Build a queue entry for a single PR by reading its packet state.

    Gracefully handles missing or corrupt files — never raises on bad data.

    Args:
        pr_number: PR number.
        queue_dir: Override for queue root directory.

    Returns:
        :class:`QueueEntry` summarizing the PR's queue state.
    """
    from bid_euchre.ops.review_queue import read_request, read_verdict

    request = None
    verdict = None
    request_corrupt = False
    verdict_corrupt = False

    try:
        request = read_request(pr_number, queue_dir)
    except Exception:
        logger.warning("PR #%d: failed to read request packet", pr_number)
        request_corrupt = True

    try:
        verdict = read_verdict(pr_number, queue_dir)
    except Exception:
        logger.warning("PR #%d: failed to read verdict packet", pr_number)
        verdict_corrupt = True

    has_request = request is not None
    has_verdict = verdict is not None

    # If both files are missing (not corrupt), the slot is empty
    if (
        not has_request
        and not has_verdict
        and not request_corrupt
        and not verdict_corrupt
    ):
        return QueueEntry(
            pr_number=pr_number,
            has_request=False,
            effective_status=QUEUE_NO_REQUEST,
        )

    # Corrupt files → surface as error so operators see the problem
    if request_corrupt or verdict_corrupt:
        return QueueEntry(
            pr_number=pr_number,
            has_request=has_request,
            request_sha=request.head_sha if request else None,
            request_branch=request.branch if request else None,
            request_requester=request.requester if request else None,
            request_created_at=request.created_at if request else None,
            has_verdict=has_verdict,
            verdict_status=verdict.status if verdict else None,
            verdict_sha=verdict.reviewed_sha if verdict else None,
            verdict_reason=verdict.reason if verdict else None,
            verdict_created_at=verdict.created_at if verdict else None,
            verdict_findings_count=len(verdict.findings) if verdict else 0,
            is_stale=False,
            effective_status=QUEUE_ERROR,
        )

    effective_status, is_stale = _compute_effective_status(request, verdict)

    # Verdict without request is an anomalous state
    if not has_request and has_verdict:
        effective_status = QUEUE_ERROR

    return QueueEntry(
        pr_number=pr_number,
        has_request=has_request,
        request_sha=request.head_sha if request else None,
        request_branch=request.branch if request else None,
        request_requester=request.requester if request else None,
        request_created_at=request.created_at if request else None,
        has_verdict=has_verdict,
        verdict_status=verdict.status if verdict else None,
        verdict_sha=verdict.reviewed_sha if verdict else None,
        verdict_reason=verdict.reason if verdict else None,
        verdict_created_at=verdict.created_at if verdict else None,
        verdict_findings_count=len(verdict.findings) if verdict else 0,
        is_stale=is_stale,
        effective_status=effective_status,
    )


def get_queue_entries(
    queue_dir: Path | None = None,
) -> list[QueueEntry]:
    """Scan the review queue directory and return entries for all PRs.

    Discovers PR slots by scanning for ``pr_<N>/`` directories under the
    queue root. Returns an entry for each discovered slot, sorted by PR
    number.

    Gracefully handles a missing queue directory (returns empty list).

    Args:
        queue_dir: Override for queue root directory.

    Returns:
        List of :class:`QueueEntry`, sorted by PR number.
    """
    from bid_euchre.ops.review_queue import DEFAULT_QUEUE_DIR

    root = queue_dir or DEFAULT_QUEUE_DIR
    if not root.is_dir():
        return []

    pr_numbers: list[int] = []
    for child in root.iterdir():
        if not child.is_dir() or not child.name.startswith("pr_"):
            continue
        try:
            pr_numbers.append(int(child.name.removeprefix("pr_")))
        except ValueError:
            logger.warning("Skipping non-numeric queue dir: %s", child.name)

    return [get_queue_entry(pr, queue_dir) for pr in sorted(pr_numbers)]


# --- Queue formatting ---

_QUEUE_STATUS_ICONS: dict[str, str] = {
    QUEUE_NO_REQUEST: " ",
    QUEUE_PENDING: "~",
    QUEUE_RUNNING: "⟳",
    QUEUE_PASSED: "+",
    QUEUE_BLOCKED: "!",
    QUEUE_FAILED: "x",
    QUEUE_STALE: "?",
    QUEUE_ERROR: "E",
}


def format_queue_text(entries: list[QueueEntry]) -> str:
    """Format queue entries as human-readable text.

    Shows request SHA and verdict SHA side by side so staleness is
    visually obvious.
    """
    if not entries:
        return "=== Review Queue ===\n\nNo queued reviews."

    lines = ["=== Review Queue ===", ""]
    for e in entries:
        icon = _QUEUE_STATUS_ICONS.get(e.effective_status, "?")
        lines.append(f"  [{icon}] #{e.pr_number:<5d} {e.effective_status}")

        if e.has_request:
            lines.append(
                f"         request:  {_short_sha(e.request_sha)} "
                f"branch={e.request_branch or '?'} "
                f"by={e.request_requester or '?'}"
            )
        else:
            lines.append("         request:  (none)")

        if e.has_verdict:
            lines.append(
                f"         verdict:  {_short_sha(e.verdict_sha)} "
                f"status={e.verdict_status or '?'} "
                f"findings={e.verdict_findings_count}"
            )
            if e.verdict_reason:
                lines.append(f"         reason:   {e.verdict_reason}")
        else:
            lines.append("         verdict:  (none)")

        if e.is_stale:
            lines.append(
                f"         ⚠ STALE: verdict covers {_short_sha(e.verdict_sha)}"
                f" but request is {_short_sha(e.request_sha)}"
            )

        lines.append("")

    # Summary counts
    status_counts: dict[str, int] = {}
    for e in entries:
        status_counts[e.effective_status] = status_counts.get(e.effective_status, 0) + 1
    summary_parts = [f"{k}={v}" for k, v in sorted(status_counts.items())]
    lines.append(f"Total: {len(entries)} PR(s) — {', '.join(summary_parts)}")
    return "\n".join(lines)


def format_queue_json(entries: list[QueueEntry]) -> list[dict]:
    """Format queue entries as JSON-serializable list."""
    return [e.to_dict() for e in entries]


def _short_sha(sha: str | None) -> str:
    """Return first 8 chars of a SHA, or '(none)' if missing."""
    if sha is None:
        return "(none)"
    return sha[:8]

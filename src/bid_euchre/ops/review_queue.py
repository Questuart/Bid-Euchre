"""Durable review-queue substrate keyed by PR + HEAD SHA.

Provides request/verdict models, file-layout helpers, stale-verdict
detection, and a deterministic precheck-to-blocked-verdict path.

Storage layout::

    <main_repo>/.claude/runtime/review_queue/
        pr_<N>/
            request.json        -- current review request
            verdict.json        -- latest verdict (may be stale)

The queue root is shared across all git worktrees for the same
repository via :func:`shared_queue_root`, which derives the path from
``git rev-parse --git-common-dir``.  This ensures a verdict written in
one worktree is visible to the merge guard running in any other
worktree.

All files are JSON. The queue is append-friendly but not append-only:
each PR slot holds exactly one request and one verdict at a time.
Stale verdicts are detected by comparing the verdict's ``reviewed_sha``
against the request's ``head_sha``.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.events import append_event

logger = logging.getLogger("ops.review_queue")

DEFAULT_QUEUE_DIR = Path(".claude/runtime/review_queue")


# ---------------------------------------------------------------------------
# Shared queue root — canonical across all worktrees for the same repo
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _resolve_git_common_queue_root() -> Path:
    """Resolve the review queue root from git's common directory.

    The git common directory (``git rev-parse --git-common-dir``) is shared
    across all worktrees for the same repository.  Its parent is the main
    checkout root, so we can derive a single canonical queue path that every
    worktree agrees on.

    Cached for the lifetime of the process (one subprocess call).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_common = Path(result.stdout.strip())
            if not git_common.is_absolute():
                git_common = (Path.cwd() / git_common).resolve()
            else:
                git_common = git_common.resolve()
            # Parent of .git dir is the main repo root
            main_root = git_common.parent
            return main_root / ".claude" / "runtime" / "review_queue"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return DEFAULT_QUEUE_DIR


def shared_queue_root() -> Path:
    """Return the canonical review queue root shared across all worktrees.

    Resolution order:

    1. ``BID_EUCHRE_REVIEW_QUEUE_DIR`` environment variable (test/debug override).
    2. Derived from ``git rev-parse --git-common-dir`` (cached).
    3. Falls back to :data:`DEFAULT_QUEUE_DIR` if git is unavailable.

    All queue readers and writers should use this (via the path helpers) so
    that a verdict written in worktree A is visible to the merge guard
    running in worktree B.
    """
    env_override = os.environ.get("BID_EUCHRE_REVIEW_QUEUE_DIR")
    if env_override:
        return Path(env_override)
    return _resolve_git_common_queue_root()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

# Verdict status values
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_PASSED = "passed"
STATUS_BLOCKED = "blocked"
STATUS_FAILED = "failed"

VALID_STATUSES = frozenset(
    {STATUS_PENDING, STATUS_RUNNING, STATUS_PASSED, STATUS_BLOCKED, STATUS_FAILED}
)


@dataclass(frozen=True)
class ReviewRequest:
    """A request for pre-merge review of a specific PR at a specific SHA.

    Attributes:
        pr_number: GitHub PR number.
        head_sha: The commit SHA to review.
        branch: Source branch name.
        requester: Lane or agent that requested the review.
        created_at: ISO 8601 timestamp of request creation.
    """

    pr_number: int
    head_sha: str
    branch: str
    requester: str
    created_at: str = field(default_factory=lambda: _now_iso())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewRequest:
        return cls(
            pr_number=int(data["pr_number"]),
            head_sha=str(data["head_sha"]),
            branch=str(data["branch"]),
            requester=str(data["requester"]),
            created_at=str(data.get("created_at", _now_iso())),
        )


@dataclass(frozen=True)
class ReviewVerdict:
    """A verdict for a review of a specific PR at a specific SHA.

    Every verdict carries the SHA it reviewed, enabling deterministic
    stale-verdict detection.

    Attributes:
        pr_number: GitHub PR number.
        reviewed_sha: The commit SHA this verdict covers.
        status: One of ``VALID_STATUSES``.
        reason: Human-readable explanation.
        findings: List of structured finding dicts (optional).
        created_at: ISO 8601 timestamp of verdict creation.
        writer: Identity of the process that wrote this verdict
            (e.g., ``"review_driver"``, ``"review"``). Used to
            discriminate between dual writers (#1184).
    """

    pr_number: int
    reviewed_sha: str
    status: str
    reason: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now_iso())
    writer: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid verdict status {self.status!r}. "
                f"Valid: {sorted(VALID_STATUSES)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewVerdict:
        return cls(
            pr_number=int(data["pr_number"]),
            reviewed_sha=str(data["reviewed_sha"]),
            status=str(data["status"]),
            reason=str(data["reason"]),
            findings=list(data.get("findings", [])),
            created_at=str(data.get("created_at", _now_iso())),
            writer=str(data.get("writer", "")),
        )


# ---------------------------------------------------------------------------
# File layout helpers
# ---------------------------------------------------------------------------


def pr_dir(pr_number: int, queue_dir: Path | None = None) -> Path:
    """Return the directory for a PR's review queue slot.

    Args:
        pr_number: GitHub PR number.
        queue_dir: Override for queue root. Defaults to :func:`shared_queue_root`.

    Returns:
        Path like ``<main_repo>/.claude/runtime/review_queue/pr_42``.
    """
    root = queue_dir if queue_dir is not None else shared_queue_root()
    return root / f"pr_{pr_number}"


def request_path(pr_number: int, queue_dir: Path | None = None) -> Path:
    """Return the path for a PR's request file."""
    return pr_dir(pr_number, queue_dir) / "request.json"


def verdict_path(pr_number: int, queue_dir: Path | None = None) -> Path:
    """Return the path for a PR's verdict file."""
    return pr_dir(pr_number, queue_dir) / "verdict.json"


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON to a file atomically via temp + fsync + replace.

    Ensures a crash mid-write cannot leave a truncated or corrupt file.
    Pattern from ``memory.py`` (PR #951).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, sort_keys=True) + "\n"

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    closed = False
    try:
        os.write(fd, content.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, str(path))
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Read / write helpers
# ---------------------------------------------------------------------------


def write_request(
    req: ReviewRequest,
    queue_dir: Path | None = None,
    *,
    emit_event: bool = True,
    events_dir: Path | None = None,
) -> Path:
    """Write a review request to disk and optionally emit an event.

    Args:
        req: The review request to persist.
        queue_dir: Override for queue root directory.
        emit_event: Whether to emit a ``review_request`` event.
        events_dir: Override for events directory.

    Returns:
        The path where the request was written.
    """
    path = request_path(req.pr_number, queue_dir)
    _atomic_write_json(path, req.to_dict())

    if emit_event:
        append_event(
            event_type="review_request",
            source="review_queue",
            lane_id=req.requester,
            payload={
                "pr_number": req.pr_number,
                "head_sha": req.head_sha,
                "branch": req.branch,
            },
            events_dir=events_dir,
        )

    logger.info("Review request written: PR #%d @ %s", req.pr_number, req.head_sha)
    return path


def read_request(pr_number: int, queue_dir: Path | None = None) -> ReviewRequest | None:
    """Read a review request from disk.

    Returns:
        The request, or ``None`` if the file is missing or corrupt.
    """
    path = request_path(pr_number, queue_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return ReviewRequest.from_dict(data)
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning("Corrupt request file for PR #%d: %s", pr_number, e)
        return None


TERMINAL_VERDICT_STATUSES = frozenset({STATUS_PASSED, STATUS_BLOCKED, STATUS_FAILED})


def write_verdict(
    verdict: ReviewVerdict,
    queue_dir: Path | None = None,
    *,
    emit_event: bool = True,
    lane_id: str = "review",
    events_dir: Path | None = None,
    emit_bus_message: bool = True,
    bus_root: Path | None = None,
) -> Path:
    """Write a review verdict to disk and optionally emit an event.

    When the verdict is terminal (passed/blocked/failed) and
    ``emit_bus_message`` is ``True``, a progress message is sent to the
    orchestrator via the message bus so the ops lane can track review
    outcomes without polling.

    Args:
        verdict: The review verdict to persist.
        queue_dir: Override for queue root directory.
        emit_event: Whether to emit a ``review_verdict`` event.
        lane_id: Lane identity for the event.
        events_dir: Override for events directory.
        emit_bus_message: Whether to send a bus message to the orchestrator
            on terminal verdicts. Default ``True``.
        bus_root: Override for message bus root directory.

    Returns:
        The path where the verdict was written.
    """
    # Thread lane_id into the verdict as writer for dual-writer discrimination (#1184)
    if lane_id and not verdict.writer:
        # frozen dataclass — reconstruct with writer set
        verdict = ReviewVerdict(
            pr_number=verdict.pr_number,
            reviewed_sha=verdict.reviewed_sha,
            status=verdict.status,
            reason=verdict.reason,
            findings=verdict.findings,
            created_at=verdict.created_at,
            writer=lane_id,
        )

    path = verdict_path(verdict.pr_number, queue_dir)
    _atomic_write_json(path, verdict.to_dict())

    if emit_event:
        append_event(
            event_type="review_verdict",
            source="review_queue",
            lane_id=lane_id,
            payload={
                "pr_number": verdict.pr_number,
                "reviewed_sha": verdict.reviewed_sha,
                "status": verdict.status,
                "reason": verdict.reason,
                "n_findings": len(verdict.findings),
            },
            events_dir=events_dir,
        )

    # Bus bridge: notify orchestrator of terminal verdicts
    if emit_bus_message and verdict.status in TERMINAL_VERDICT_STATUSES:
        _emit_verdict_bus_message(verdict, lane_id=lane_id, bus_root=bus_root)

    logger.info(
        "Review verdict written: PR #%d @ %s -> %s",
        verdict.pr_number,
        verdict.reviewed_sha,
        verdict.status,
    )
    return path


def _is_verdict_already_notified(
    pr_number: int,
    reviewed_sha: str,
    bus_root: Path,
) -> bool:
    """Check if the orchestrator inbox already has a verdict for this PR+SHA.

    Semantic dedup: prevents duplicate verdict bus messages when multiple
    writers (review_driver, post-merge review) or retry rounds produce
    verdicts for the same PR at the same SHA.  Content-based dedup in
    ``send_message`` catches exact-summary matches; this catches cases
    where the summary text differs but the underlying PR+SHA is the same
    (e.g., different verdict statuses across rounds).

    Returns ``True`` if a non-terminal inbox message already carries a
    verdict notification for the given ``(pr_number, reviewed_sha)`` pair.
    """
    from bid_euchre.ops.message_bus import _read_inbox_raw

    raw = _read_inbox_raw("orchestrator", bus_root)

    # Deduplicate: latest record per message_id wins
    by_id: dict[str, dict[str, Any]] = {}
    for rec in raw:
        mid = rec.get("message_id")
        if mid:
            by_id[mid] = rec

    terminal = {"resolved", "expired", "dead_lettered"}
    for rec in by_id.values():
        if rec.get("status") in terminal:
            continue
        payload = rec.get("payload", {})
        if (
            payload.get("pr_number") == pr_number
            and payload.get("reviewed_sha") == reviewed_sha
            and payload.get("verdict_status") is not None
        ):
            return True
    return False


def _emit_verdict_bus_message(
    verdict: ReviewVerdict,
    *,
    lane_id: str = "review",
    bus_root: Path | None = None,
) -> None:
    """Send a bus message to the orchestrator about a terminal verdict.

    Applies semantic dedup: if the orchestrator inbox already contains a
    verdict notification for the same ``(pr_number, reviewed_sha)`` pair,
    the send is skipped regardless of summary text differences.  This
    prevents noise from multiple writers or review rounds.

    Best-effort: failures are logged but do not propagate — the verdict
    file is already written and the event already emitted by this point.
    """
    try:
        from bid_euchre.ops.message_bus import (
            create_message,
            send_message,
            shared_bus_root,
        )

        root = shared_bus_root(bus_root)

        # Semantic dedup: skip if orchestrator already knows about this PR+SHA
        if _is_verdict_already_notified(verdict.pr_number, verdict.reviewed_sha, root):
            logger.info(
                "Verdict bus message suppressed (semantic dedup): "
                "PR #%d @ %s already notified",
                verdict.pr_number,
                verdict.reviewed_sha[:8],
            )
            return

        msg = create_message(
            from_lane=lane_id,
            to_lane="orchestrator",
            message_type="progress",
            summary=(
                f"Review verdict for PR #{verdict.pr_number} "
                f"@ {verdict.reviewed_sha[:8]}: {verdict.status}"
            ),
            payload={
                "pr_number": verdict.pr_number,
                "reviewed_sha": verdict.reviewed_sha,
                "verdict_status": verdict.status,
                "n_findings": len(verdict.findings),
                "reason": verdict.reason,
                "ttl_seconds": 3600,  # 1h — verdicts are ephemeral signals
            },
        )
        send_message(msg, bus_root=root, deduplicate=True)
        logger.info(
            "Bus message sent to orchestrator: PR #%d verdict=%s",
            verdict.pr_number,
            verdict.reviewed_sha[:8],
        )
    except Exception:
        logger.warning(
            "Failed to send bus message for PR #%d verdict",
            verdict.pr_number,
            exc_info=True,
        )


def read_verdict(pr_number: int, queue_dir: Path | None = None) -> ReviewVerdict | None:
    """Read a review verdict from disk.

    Returns:
        The verdict, or ``None`` if the file is missing or corrupt.
    """
    path = verdict_path(pr_number, queue_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return ReviewVerdict.from_dict(data)
    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning("Corrupt verdict file for PR #%d: %s", pr_number, e)
        return None


# ---------------------------------------------------------------------------
# Stale-verdict detection
# ---------------------------------------------------------------------------


def is_verdict_stale(
    pr_number: int, current_head_sha: str, queue_dir: Path | None = None
) -> bool:
    """Check whether the stored verdict for a PR is stale.

    A verdict is stale when its ``reviewed_sha`` does not match the
    ``current_head_sha``. A missing verdict is not considered stale
    (there's nothing to invalidate).

    Args:
        pr_number: GitHub PR number.
        current_head_sha: The SHA currently at the PR's HEAD.
        queue_dir: Override for queue root directory.

    Returns:
        ``True`` if a verdict exists and its SHA differs from
        ``current_head_sha``. ``False`` otherwise.
    """
    verdict = read_verdict(pr_number, queue_dir)
    if verdict is None:
        return False
    return verdict.reviewed_sha != current_head_sha


def invalidate_stale_verdict(
    pr_number: int, current_head_sha: str, queue_dir: Path | None = None
) -> bool:
    """Remove a verdict file if it is stale.

    Args:
        pr_number: GitHub PR number.
        current_head_sha: The SHA currently at the PR's HEAD.
        queue_dir: Override for queue root directory.

    Returns:
        ``True`` if a stale verdict was removed, ``False`` otherwise.
    """
    verdict = read_verdict(pr_number, queue_dir)
    if verdict is None:
        return False
    if verdict.reviewed_sha == current_head_sha:
        return False

    stale_sha = verdict.reviewed_sha
    path = verdict_path(pr_number, queue_dir)
    path.unlink(missing_ok=True)
    logger.info(
        "Stale verdict removed for PR #%d (reviewed %s, current %s)",
        pr_number,
        stale_sha,
        current_head_sha,
    )
    return True


# ---------------------------------------------------------------------------
# Deterministic precheck -> blocked verdict
# ---------------------------------------------------------------------------

# Precheck IDs aligned with the review gate definitions in
# docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md and .claude/rules/deferred/60_review_gate.md.
PRECHECK_IDS = frozenset({"C1", "C2", "N1", "N2", "N3", "T1", "X2", "X3"})


@dataclass(frozen=True)
class PrecheckFinding:
    """A single deterministic precheck finding.

    Attributes:
        check_id: Precheck identifier (e.g., "C1", "X3").
        severity: "BLOCK" or "WARN".
        message: Human-readable description.
        file: Optional file path.
        line: Optional line number.
    """

    check_id: str
    severity: str
    message: str
    file: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "check_id": self.check_id,
            "severity": self.severity,
            "message": self.message,
        }
        if self.file is not None:
            d["file"] = self.file
        if self.line is not None:
            d["line"] = self.line
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrecheckFinding:
        return cls(
            check_id=str(data["check_id"]),
            severity=str(data["severity"]),
            message=str(data["message"]),
            file=data.get("file"),
            line=data.get("line"),
        )


def precheck_to_verdict(
    pr_number: int,
    head_sha: str,
    findings: list[PrecheckFinding],
    queue_dir: Path | None = None,
    *,
    emit_event: bool = True,
    lane_id: str = "review",
    events_dir: Path | None = None,
) -> ReviewVerdict:
    """Convert deterministic precheck findings into a review verdict.

    If any finding has severity ``"BLOCK"``, the verdict status is
    ``"blocked"``. Otherwise it is ``"passed"``.

    The verdict is written to disk and an event is emitted.

    Args:
        pr_number: GitHub PR number.
        head_sha: The commit SHA that was prechecked.
        findings: List of precheck findings.
        queue_dir: Override for queue root directory.
        emit_event: Whether to emit a ``review_verdict`` event.
        lane_id: Lane identity for the event.
        events_dir: Override for events directory.

    Returns:
        The created ``ReviewVerdict``.
    """
    blockers = [f for f in findings if f.severity == "BLOCK"]
    has_blockers = len(blockers) > 0

    status = STATUS_BLOCKED if has_blockers else STATUS_PASSED
    if has_blockers:
        reason = f"Deterministic precheck blocked: {len(blockers)} blocker(s) found"
    elif findings:
        reason = f"Deterministic precheck passed with {len(findings)} warning(s)"
    else:
        reason = "Deterministic precheck passed — clean"

    verdict = ReviewVerdict(
        pr_number=pr_number,
        reviewed_sha=head_sha,
        status=status,
        reason=reason,
        findings=[f.to_dict() for f in findings],
    )

    write_verdict(
        verdict,
        queue_dir,
        emit_event=emit_event,
        lane_id=lane_id,
        events_dir=events_dir,
    )

    return verdict


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()

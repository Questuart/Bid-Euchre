"""Review lane runner — shadow-mode queue processor for the review lane.

Scans the review queue for pending requests, claims them, invokes the
``steward-review`` agent, and writes SHA-bound verdict packets.

Shadow mode: verdicts are written to disk but do NOT gate merges.
The runner is the only writer of final verdicts via the ``review`` lane.

Entry point::

    uv run python scripts/internal/review_lane_runner.py [--queue-dir DIR] [--once] [--dry-run]

Design invariants:

- Every verdict is bound to the exact PR head SHA at claim time.
- A stale SHA (request SHA != current PR head) causes the run to be skipped.
- Reviewer failure writes ``failed`` or ``error``, never ``passed``.
- Shadow mode: no commit-status publishing, no merge authority.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from bid_euchre.ops.review_queue import (
    DEFAULT_QUEUE_DIR,
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_RUNNING,
    ReviewRequest,
    ReviewVerdict,
    read_request,
    read_verdict,
    write_verdict,
)

logger = logging.getLogger("review_lane_runner")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LANE_ID = "review"
GH_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 30
MAX_POLL_CYCLES = 30  # 30 * 30s = 15 min max runtime

# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------


def get_pr_head_sha(pr_number: int) -> str | None:
    """Fetch the current HEAD SHA for a PR from GitHub.

    Returns:
        The SHA string, or ``None`` if the lookup fails.
    """
    try:
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
            timeout=GH_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.warning(
                "gh pr view failed for PR #%d: %s", pr_number, result.stderr.strip()
            )
            return None
        sha = result.stdout.strip()
        return sha if sha else None
    except subprocess.TimeoutExpired:
        logger.warning("gh pr view timed out for PR #%d", pr_number)
        return None
    except FileNotFoundError:
        logger.error("gh CLI not found")
        return None


# ---------------------------------------------------------------------------
# Queue scanning
# ---------------------------------------------------------------------------


# Maximum age (in minutes) for a ``running`` verdict before it becomes
# re-claimable.  Protects against runner crashes that leave a PR stuck
# in ``running`` forever (#1183).
RUNNING_STALENESS_MINUTES = 15


def _is_verdict_stale_running(verdict: ReviewVerdict) -> bool:
    """Check whether a ``running`` verdict is stale (older than threshold).

    Args:
        verdict: A verdict with status ``running``.

    Returns:
        ``True`` if the verdict's ``created_at`` is older than
        ``RUNNING_STALENESS_MINUTES``.
    """
    if verdict.status != STATUS_RUNNING:
        return False
    try:
        from datetime import datetime, timezone

        created = datetime.fromisoformat(verdict.created_at)
        age_minutes = (datetime.now(timezone.utc) - created).total_seconds() / 60
        return age_minutes > RUNNING_STALENESS_MINUTES
    except (ValueError, TypeError):
        # Unparseable timestamp — treat as stale to avoid permanent stuck state
        return True


def find_pending_requests(queue_dir: Path | None = None) -> list[ReviewRequest]:
    """Scan the queue for PRs with pending review requests.

    A request is "claimable" when:
    1. A ``request.json`` exists.
    2. No verdict exists, OR the existing verdict is ``pending``, OR
       the verdict is ``running`` but older than ``RUNNING_STALENESS_MINUTES``
       (protects against runner crashes leaving a PR stuck — #1183).

    Returns:
        List of ``ReviewRequest`` objects sorted by PR number (FIFO-ish).
    """
    root = queue_dir or DEFAULT_QUEUE_DIR
    if not root.exists():
        return []

    pending: list[ReviewRequest] = []
    for pr_subdir in sorted(root.iterdir()):
        if not pr_subdir.is_dir() or not pr_subdir.name.startswith("pr_"):
            continue

        try:
            pr_number = int(pr_subdir.name.removeprefix("pr_"))
        except ValueError:
            continue

        req = read_request(pr_number, queue_dir)
        if req is None:
            continue

        verdict = read_verdict(pr_number, queue_dir)
        if verdict is not None and verdict.status not in (STATUS_PENDING,):
            # Re-claimable if running and stale (#1183)
            if verdict.status == STATUS_RUNNING and _is_verdict_stale_running(verdict):
                logger.info(
                    "PR #%d: re-claiming stale running verdict (created %s)",
                    pr_number,
                    verdict.created_at,
                )
            else:
                # Already has a non-pending/non-stale verdict — skip.
                continue

        pending.append(req)

    return pending


# ---------------------------------------------------------------------------
# Review invocation
# ---------------------------------------------------------------------------


def invoke_review(pr_number: int, branch: str, head_sha: str) -> dict[str, Any]:
    """Invoke the steward-review agent for a PR.

    This is a subprocess call to ``claude`` with the ``steward-review`` agent.
    In shadow mode, we capture its output but do not publish any status.

    Returns:
        A dict with keys:
        - ``success``: bool — whether the review completed without error.
        - ``status``: str — verdict status (``passed``, ``blocked``, ``failed``).
        - ``reason``: str — human-readable explanation.
        - ``findings``: list[dict] — structured findings (may be empty).
    """
    prompt = (
        f"Review PR #{pr_number} on branch '{branch}' at SHA {head_sha}. "
        f"Review the diff against main. Produce structured findings with "
        f"severity (BLOCK/WARN/INFO), file path, and description. "
        f"Output a JSON object with keys: status (passed/blocked/failed), "
        f"reason (string), findings (list of dicts with severity, file, message)."
    )

    try:
        result = subprocess.run(
            [
                "claude",
                "--agent",
                "steward-review",
                "--print",
                "--output-format",
                "json",
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for review
            cwd=str(_REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        logger.error("steward-review timed out for PR #%d", pr_number)
        return {
            "success": False,
            "status": STATUS_FAILED,
            "reason": "Review agent timed out after 600s",
            "findings": [],
        }
    except FileNotFoundError:
        logger.error("claude CLI not found — cannot invoke steward-review")
        return {
            "success": False,
            "status": STATUS_FAILED,
            "reason": "claude CLI not found",
            "findings": [],
        }

    if result.returncode != 0:
        logger.error(
            "steward-review failed for PR #%d (exit %d): %s",
            pr_number,
            result.returncode,
            result.stderr.strip()[:500],
        )
        return {
            "success": False,
            "status": STATUS_FAILED,
            "reason": f"Review agent exited with code {result.returncode}",
            "findings": [],
        }

    return _parse_review_output(result.stdout)


def _parse_review_output(raw_output: str) -> dict[str, Any]:
    """Parse the steward-review agent's output into a structured result.

    Attempts JSON parsing first, then falls back to heuristic extraction.
    On any parse failure, returns a ``failed`` result — never ``passed``.
    """
    if not raw_output.strip():
        return {
            "success": False,
            "status": STATUS_FAILED,
            "reason": "Review agent produced empty output",
            "findings": [],
        }

    # Try direct JSON parse
    try:
        data = json.loads(raw_output)
        if isinstance(data, dict):
            status = data.get("status", "")
            if status not in ("passed", "blocked", "failed"):
                # Unparseable status — treat as failed, never as passed.
                return {
                    "success": False,
                    "status": STATUS_FAILED,
                    "reason": f"Review agent returned invalid status: {status!r}",
                    "findings": data.get("findings", []),
                }
            return {
                "success": True,
                "status": status,
                "reason": data.get("reason", f"Review completed with status: {status}"),
                "findings": data.get("findings", []),
            }
    except (json.JSONDecodeError, TypeError):
        pass

    # Try extracting JSON from within the output (agent may wrap it in text)
    json_match = re.search(r"\{[^{}]*\"status\"\s*:", raw_output, re.DOTALL)
    if json_match:
        # Find the matching closing brace
        start = json_match.start()
        brace_depth = 0
        for i, c in enumerate(raw_output[start:], start):
            if c == "{":
                brace_depth += 1
            elif c == "}":
                brace_depth -= 1
                if brace_depth == 0:
                    try:
                        data = json.loads(raw_output[start : i + 1])
                        status = data.get("status", "")
                        if status not in ("passed", "blocked", "failed"):
                            return {
                                "success": False,
                                "status": STATUS_FAILED,
                                "reason": f"Extracted invalid status: {status!r}",
                                "findings": data.get("findings", []),
                            }
                        return {
                            "success": True,
                            "status": status,
                            "reason": data.get("reason", f"Review completed: {status}"),
                            "findings": data.get("findings", []),
                        }
                    except (json.JSONDecodeError, TypeError):
                        pass
                    break

    # Could not parse — fail safe. Never collapse to passed.
    return {
        "success": False,
        "status": STATUS_FAILED,
        "reason": "Could not parse review agent output",
        "findings": [],
    }


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------


def process_request(
    req: ReviewRequest,
    queue_dir: Path | None = None,
    *,
    dry_run: bool = False,
    events_dir: Path | None = None,
) -> ReviewVerdict:
    """Process a single review request end-to-end.

    Steps:
    1. Verify the current PR head SHA matches the request.
    2. Write a ``running`` verdict (claim).
    3. Invoke the steward-review agent.
    4. Write the final verdict bound to the reviewed SHA.

    On any error, writes a ``failed`` verdict — never ``passed``.

    Args:
        req: The review request to process.
        queue_dir: Override for queue root directory.
        dry_run: If True, skip the actual review invocation.
        events_dir: Override for events directory.

    Returns:
        The final ``ReviewVerdict``.
    """
    pr = req.pr_number
    logger.info("Processing review request: PR #%d @ %s", pr, req.head_sha)

    # Step 1: Verify SHA freshness
    current_sha = get_pr_head_sha(pr)
    if current_sha is None:
        logger.error("Could not fetch HEAD SHA for PR #%d — writing error verdict", pr)
        return _write_error_verdict(
            pr,
            req.head_sha,
            "Could not fetch current HEAD SHA from GitHub",
            queue_dir=queue_dir,
            events_dir=events_dir,
        )

    if current_sha != req.head_sha:
        logger.warning(
            "Stale SHA for PR #%d: request=%s, current=%s — skipping",
            pr,
            req.head_sha,
            current_sha,
        )
        return _write_error_verdict(
            pr,
            req.head_sha,
            f"Stale SHA: request {req.head_sha[:8]} != current {current_sha[:8]}",
            queue_dir=queue_dir,
            events_dir=events_dir,
        )

    # Step 2: Claim — write running verdict
    running_verdict = ReviewVerdict(
        pr_number=pr,
        reviewed_sha=req.head_sha,
        status=STATUS_RUNNING,
        reason="Review in progress",
    )
    write_verdict(
        running_verdict,
        queue_dir,
        emit_event=True,
        lane_id=LANE_ID,
        events_dir=events_dir,
    )
    logger.info("Claimed PR #%d — running verdict written", pr)

    # Step 3: Invoke review
    if dry_run:
        logger.info("Dry-run mode — skipping actual review for PR #%d", pr)
        review_result = {
            "success": True,
            "status": STATUS_PASSED,
            "reason": "Dry-run: review skipped",
            "findings": [],
        }
    else:
        try:
            review_result = invoke_review(pr, req.branch, req.head_sha)
        except Exception as exc:
            logger.exception("Unexpected error during review of PR #%d", pr)
            return _write_error_verdict(
                pr,
                req.head_sha,
                f"Unexpected error: {exc}",
                queue_dir=queue_dir,
                events_dir=events_dir,
            )

    # Step 4: Verify SHA hasn't changed during review
    post_review_sha = get_pr_head_sha(pr)
    if post_review_sha is None:
        logger.error(
            "Could not verify HEAD SHA after review of PR #%d — discarding result",
            pr,
        )
        return _write_error_verdict(
            pr,
            req.head_sha,
            "Could not verify HEAD SHA after review (API failure)",
            queue_dir=queue_dir,
            events_dir=events_dir,
        )
    if post_review_sha != req.head_sha:
        logger.warning(
            "SHA changed during review of PR #%d: %s -> %s — discarding result",
            pr,
            req.head_sha,
            post_review_sha,
        )
        return _write_error_verdict(
            pr,
            req.head_sha,
            f"SHA changed during review: {req.head_sha[:8]} -> {post_review_sha[:8]}",
            queue_dir=queue_dir,
            events_dir=events_dir,
        )

    # Step 5: Write final verdict
    status = review_result["status"]
    # Safety: never allow unparseable/unknown status to become passed
    if status not in (STATUS_PASSED, STATUS_BLOCKED, STATUS_FAILED):
        logger.error(
            "Invalid review status %r for PR #%d — mapping to failed", status, pr
        )
        status = STATUS_FAILED

    final_verdict = ReviewVerdict(
        pr_number=pr,
        reviewed_sha=req.head_sha,
        status=status,
        reason=review_result.get("reason", f"Review completed: {status}"),
        findings=review_result.get("findings", []),
    )
    write_verdict(
        final_verdict,
        queue_dir,
        emit_event=True,
        lane_id=LANE_ID,
        events_dir=events_dir,
    )
    logger.info(
        "Final verdict for PR #%d @ %s: %s", pr, req.head_sha, final_verdict.status
    )
    return final_verdict


def _write_error_verdict(
    pr_number: int,
    reviewed_sha: str,
    reason: str,
    *,
    queue_dir: Path | None = None,
    events_dir: Path | None = None,
) -> ReviewVerdict:
    """Write a ``failed`` verdict for error conditions.

    This helper ensures errors always produce a ``failed`` verdict,
    never ``passed``.
    """
    verdict = ReviewVerdict(
        pr_number=pr_number,
        reviewed_sha=reviewed_sha,
        status=STATUS_FAILED,
        reason=reason,
    )
    write_verdict(
        verdict,
        queue_dir,
        emit_event=True,
        lane_id=LANE_ID,
        events_dir=events_dir,
    )
    return verdict


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_once(
    queue_dir: Path | None = None,
    *,
    dry_run: bool = False,
    events_dir: Path | None = None,
) -> list[ReviewVerdict]:
    """Scan the queue and process all pending requests.

    Returns:
        List of verdicts written during this cycle.
    """
    pending = find_pending_requests(queue_dir)
    if not pending:
        logger.debug("No pending review requests found")
        return []

    logger.info("Found %d pending request(s)", len(pending))
    verdicts: list[ReviewVerdict] = []
    for req in pending:
        verdict = process_request(
            req, queue_dir, dry_run=dry_run, events_dir=events_dir
        )
        verdicts.append(verdict)

    return verdicts


def run_loop(
    queue_dir: Path | None = None,
    *,
    dry_run: bool = False,
    events_dir: Path | None = None,
    max_cycles: int = MAX_POLL_CYCLES,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> None:
    """Run the review lane in a polling loop.

    Processes pending requests each cycle, then sleeps.
    Exits after ``max_cycles`` iterations or when interrupted.
    """
    logger.info(
        "Review lane runner starting (shadow mode, max_cycles=%d, interval=%.0fs)",
        max_cycles,
        poll_interval,
    )
    for cycle in range(1, max_cycles + 1):
        logger.debug("Poll cycle %d/%d", cycle, max_cycles)
        verdicts = run_once(queue_dir, dry_run=dry_run, events_dir=events_dir)
        if verdicts:
            logger.info(
                "Cycle %d: processed %d request(s) — %s",
                cycle,
                len(verdicts),
                ", ".join(f"PR#{v.pr_number}:{v.status}" for v in verdicts),
            )
        if cycle < max_cycles:
            time.sleep(poll_interval)

    logger.info("Review lane runner finished (%d cycles)", max_cycles)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review lane runner — shadow-mode queue processor"
    )
    parser.add_argument(
        "--queue-dir",
        type=Path,
        default=None,
        help="Override queue root directory (default: .claude/runtime/review_queue)",
    )
    parser.add_argument(
        "--events-dir",
        type=Path,
        default=None,
        help="Override events directory",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process pending requests once and exit (no polling loop)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip actual review invocation (for testing)",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=MAX_POLL_CYCLES,
        help=f"Maximum poll cycles (default: {MAX_POLL_CYCLES})",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL_SECONDS,
        help=f"Seconds between poll cycles (default: {POLL_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.once:
        verdicts = run_once(
            args.queue_dir, dry_run=args.dry_run, events_dir=args.events_dir
        )
        for v in verdicts:
            print(
                json.dumps(
                    {"pr": v.pr_number, "sha": v.reviewed_sha, "status": v.status}
                )
            )
        sys.exit(0 if all(v.status != STATUS_FAILED for v in verdicts) else 1)
    else:
        run_loop(
            args.queue_dir,
            dry_run=args.dry_run,
            events_dir=args.events_dir,
            max_cycles=args.max_cycles,
            poll_interval=args.poll_interval,
        )


if __name__ == "__main__":
    main()

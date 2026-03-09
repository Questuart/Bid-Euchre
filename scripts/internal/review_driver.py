"""Review loop driver — main orchestrator for the autonomous review loop.

Each invocation:
1. Loads state from disk (or initializes if new)
2. If terminal state → no-op
3. Advances one step (bounded progress)
4. Saves state and round artifacts
5. Exits

Idempotent: duplicate triggers are harmless.
Entry point: python scripts/internal/review_driver.py --pr <N> --trigger <event>

The driver skeleton handles state transitions and prechecks.
Codex CLI invocation and fix application are in PR 2 (separate modules).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from review_state import (
    TERMINAL_STATES,
    ReviewLoopState,
    ReviewMode,
    ReviewState,
    load_state,
    round_dir,
    save_state,
)

logger = logging.getLogger("review_driver")


def classify_review_mode(changed_files: list[str]) -> ReviewMode:
    """Determine review mode from the set of changed files.

    Most restrictive mode wins if mixed file types.
    """
    has_reports = any(f.startswith("docs/04_reports/") for f in changed_files)
    has_plans = any(f.startswith("plans/") for f in changed_files)

    if has_reports:
        return ReviewMode.REPORT_AUDIT
    if has_plans:
        return ReviewMode.PLAN_AUDIT
    return ReviewMode.STANDARD


def initialize_state(
    pr_number: int,
    branch: str,
    mode: ReviewMode,
    max_iterations: int = 5,
) -> ReviewLoopState:
    """Create initial state for a new review loop."""
    return ReviewLoopState(
        pr_number=pr_number,
        branch=branch,
        mode=mode.value,
        state=ReviewState.INITIALIZED.value,
        max_iterations=max_iterations,
    )


def step(
    loop_state: ReviewLoopState,
    *,
    base_dir: Path | None = None,
) -> ReviewLoopState:
    """Advance the state machine by one step.

    This is the main dispatch function. Each call makes bounded progress
    (one transition) and returns the updated state.

    Args:
        loop_state: Current state.
        base_dir: Override for state persistence directory.

    Returns:
        Updated state (also persisted to disk).
    """
    current = loop_state.current_state

    # Terminal states → no-op
    if current in TERMINAL_STATES:
        logger.info(
            "PR #%d: terminal state %s — no-op",
            loop_state.pr_number,
            current.value,
        )
        return loop_state

    # Check max iterations (global stop condition)
    if loop_state.iteration_count >= loop_state.max_iterations:
        loop_state.transition(ReviewState.STOPPED_MAX_ITERATIONS)
        loop_state.stop_reason = f"Hit max iterations ({loop_state.max_iterations})"
        save_state(loop_state, base_dir)
        logger.warning(
            "PR #%d: stopped — max iterations (%d)",
            loop_state.pr_number,
            loop_state.max_iterations,
        )
        return loop_state

    # Dispatch by current state
    if current == ReviewState.INITIALIZED:
        return _step_initialized(loop_state, base_dir)
    elif current == ReviewState.PR_OPEN:
        return _step_pr_open(loop_state, base_dir)
    elif current == ReviewState.WAITING_FOR_CI:
        return _step_waiting_for_ci(loop_state, base_dir)
    elif current == ReviewState.WAITING_FOR_CODEX:
        return _step_waiting_for_codex(loop_state, base_dir)
    elif current == ReviewState.APPLYING_FIXES:
        return _step_applying_fixes(loop_state, base_dir)
    elif current == ReviewState.RETESTING:
        return _step_retesting(loop_state, base_dir)
    else:
        logger.error(
            "PR #%d: unexpected state %s",
            loop_state.pr_number,
            current.value,
        )
        return loop_state


def _step_initialized(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """INITIALIZED → PR_OPEN: PR exists, transition to open."""
    loop_state.transition(ReviewState.PR_OPEN)
    save_state(loop_state, base_dir)
    logger.info("PR #%d: initialized → pr_open", loop_state.pr_number)
    return loop_state


def _step_pr_open(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """PR_OPEN → WAITING_FOR_CI: Run deterministic prechecks, then wait for CI."""
    from deterministic_prechecks import check_diff, get_blocking_findings

    # Run prechecks
    findings = check_diff(mode=loop_state.mode)
    blocking = get_blocking_findings(findings)

    # Save precheck results for this round
    rdir = round_dir(loop_state.pr_number, loop_state.iteration_count + 1, base_dir)
    rdir.mkdir(parents=True, exist_ok=True)
    with open(rdir / "prechecks.json", "w") as f:
        json.dump([f.to_dict() for f in findings], f, indent=2)

    if blocking:
        # Blocking prechecks → stop (these are deterministic, unfixable by Codex)
        loop_state.transition(ReviewState.STOPPED_CI_FAILURE)
        loop_state.stop_reason = (
            f"Blocking deterministic precheck failures: {len(blocking)} findings"
        )
        save_state(loop_state, base_dir)
        logger.warning(
            "PR #%d: blocking prechecks (%d findings) — stopped",
            loop_state.pr_number,
            len(blocking),
        )
        return loop_state

    loop_state.transition(ReviewState.WAITING_FOR_CI)
    save_state(loop_state, base_dir)
    logger.info("PR #%d: pr_open → waiting_for_ci", loop_state.pr_number)
    return loop_state


def _step_waiting_for_ci(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """WAITING_FOR_CI → WAITING_FOR_CODEX or STOPPED_CI_FAILURE."""
    from github_pr_state import get_ci_status

    ci_status = get_ci_status(loop_state.pr_number)
    loop_state.last_ci_status = ci_status

    if ci_status == "pending":
        # Not ready yet — save state and exit (resume on next trigger)
        save_state(loop_state, base_dir)
        logger.info("PR #%d: CI pending — will resume", loop_state.pr_number)
        return loop_state

    if ci_status == "failure":
        loop_state.transition(ReviewState.STOPPED_CI_FAILURE)
        loop_state.stop_reason = "CI failed"
        save_state(loop_state, base_dir)
        logger.warning("PR #%d: CI failed — stopped", loop_state.pr_number)
        return loop_state

    if ci_status == "success":
        loop_state.transition(ReviewState.WAITING_FOR_CODEX)
        save_state(loop_state, base_dir)
        logger.info(
            "PR #%d: waiting_for_ci → waiting_for_codex",
            loop_state.pr_number,
        )
        return loop_state

    # Unknown CI status — treat as pending
    save_state(loop_state, base_dir)
    logger.info(
        "PR #%d: CI status unknown (%s) — will resume",
        loop_state.pr_number,
        ci_status,
    )
    return loop_state


def _step_waiting_for_codex(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """WAITING_FOR_CODEX → APPLYING_FIXES or READY_TO_MERGE.

    Stub: Codex CLI adapter is in PR 2. Fails safe by stopping
    with STOPPED_REVIEW_FAILURE rather than advancing to READY_TO_MERGE.
    """
    # Fail safe: no adapter = no review = cannot advance
    logger.warning(
        "PR #%d: Codex review adapter not yet implemented — stopping",
        loop_state.pr_number,
    )
    loop_state.transition(ReviewState.STOPPED_REVIEW_FAILURE)
    loop_state.last_codex_status = "stub_no_adapter"
    loop_state.stop_reason = "Codex CLI adapter not yet implemented (PR 2)"
    save_state(loop_state, base_dir)
    return loop_state


def _step_applying_fixes(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """APPLYING_FIXES → RETESTING.

    Stub: Claude fix adapter is in PR 2.
    """
    logger.info(
        "PR #%d: fix adapter stub — no adapter yet",
        loop_state.pr_number,
    )
    loop_state.transition(ReviewState.RETESTING)
    save_state(loop_state, base_dir)
    return loop_state


def _step_retesting(
    loop_state: ReviewLoopState,
    base_dir: Path | None,
) -> ReviewLoopState:
    """RETESTING → WAITING_FOR_CI or STOPPED_CI_FAILURE.

    Stub: make check integration is in PR 2.
    """
    logger.info(
        "PR #%d: retest stub — transitioning to waiting_for_ci",
        loop_state.pr_number,
    )
    loop_state.transition(ReviewState.WAITING_FOR_CI)
    save_state(loop_state, base_dir)
    return loop_state


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Autonomous review loop driver")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument(
        "--trigger",
        choices=["pr_created", "ci_complete", "manual"],
        default="manual",
        help="What triggered this invocation",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch name (required for new loops)",
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "report-audit", "plan-audit"],
        default=None,
        help="Review mode (auto-detected if not specified)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=5,
        help="Maximum review iterations (default: 5)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Load or initialize state
    loop_state = load_state(args.pr)

    if loop_state is None:
        if args.branch is None:
            logger.error("--branch required for new review loops")
            return 1

        if args.mode:
            mode = ReviewMode(args.mode)
        else:
            # Auto-detect from changed files
            import subprocess

            diff_result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                capture_output=True,
                text=True,
            )
            if diff_result.returncode == 0:
                changed = [
                    f.strip()
                    for f in diff_result.stdout.strip().split("\n")
                    if f.strip()
                ]
                mode = classify_review_mode(changed)
            else:
                mode = ReviewMode.STANDARD
        loop_state = initialize_state(
            args.pr,
            args.branch,
            mode,
            args.max_iterations,
        )
        save_state(loop_state)
        logger.info(
            "PR #%d: new loop initialized (mode=%s)",
            args.pr,
            mode.value,
        )

    # Advance one step
    loop_state = step(loop_state)

    # Report final state
    logger.info(
        "PR #%d: state=%s iteration=%d/%d",
        loop_state.pr_number,
        loop_state.current_state.value,
        loop_state.iteration_count,
        loop_state.max_iterations,
    )
    if loop_state.is_terminal:
        logger.info(
            "PR #%d: terminal — reason: %s",
            loop_state.pr_number,
            loop_state.stop_reason or "completed",
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

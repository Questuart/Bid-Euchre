"""Plan review loop driver -- orchestrates iterative Codex -> fix -> re-review cycles.

Entry point: run_plan_review_loop(plan_path, tier=None, max_iter=3)

The loop:
1. Detect tier (or use override)
2. Invoke Codex plan review (with path isolation)
3. If findings: spawn Claude to fix, then re-review
4. If Codex fails: fall back to Claude reviewer, create GitHub issue
5. Repeat up to max_iter times
6. Write sidecar review file to .claude/runtime/plan_reviews/<key>/review.md
7. Return results for conversation output

State is persisted to .claude/runtime/plan_reviews/<key>/state.json
for resumability, but the primary use case is single-session execution.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from codex_plan_review_adapter import (
    PlanReviewFinding,
    detect_plan_tier,
    invoke_claude_failsafe,
    invoke_codex_plan_review,
    plan_state_key,
)
from review_state import (
    PlanReviewLoopState,
    PlanReviewState,
    compute_findings_hash,
    load_plan_review_state,
    plan_review_state_dir,
    save_plan_review_state,
)

logger = logging.getLogger("plan_review_driver")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class PlanReviewLoopResult:
    """Final result of the plan review loop."""

    plan_path: str
    tier: str
    verdict: str  # "READY", "NEEDS_ATTENTION", "NOT_READY"
    iterations: int
    total_findings: int
    open_findings: int
    reviewer: str  # "codex_cli" or "claude_failsafe"
    fallback_used: bool
    fallback_issue_url: str | None
    sidecar_path: str | None
    findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def _compute_verdict(findings: list) -> str:
    """Compute the review verdict from remaining findings.

    Returns:
        "READY" if no findings remain open.
        "NEEDS_ATTENTION" if only WARNING/INFO findings remain.
        "NOT_READY" if any CRITICAL findings remain.
    """
    if not findings:
        return "READY"
    severities = {
        f.severity if hasattr(f, "severity") else f.get("severity", "")
        for f in findings
    }
    if "CRITICAL" in severities:
        return "NOT_READY"
    return "NEEDS_ATTENTION"


# ---------------------------------------------------------------------------
# Fallback issue creation
# ---------------------------------------------------------------------------


def _create_fallback_issue(plan_path: Path, tier: str, error: str) -> str | None:
    """Create a GitHub issue for Codex fallback.

    Args:
        plan_path: Path to the plan file.
        tier: Detected plan tier.
        error: Error message from the Codex invocation.

    Returns:
        URL of the created issue, or None if creation failed.
    """
    title = f"Plan review fallback: {plan_path.name} -- Codex unavailable"
    body = (
        f"## Plan Review Fallback\n\n"
        f"- **Plan file:** `{plan_path}`\n"
        f"- **Tier:** {tier}\n"
        f"- **Codex error:** {error}\n"
        f"- **Fallback reviewer:** claude-agent\n"
        f"- **Timestamp:** {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
    )
    # Try with label first, retry without if label doesn't exist
    for labels in [["--label", "plan-review-fallback"], []]:
        try:
            result = subprocess.run(
                ["gh", "issue", "create", "--title", title, "--body", body, *labels],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                logger.info("Created fallback issue: %s", url)
                return url
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    logger.warning("Failed to create fallback issue for %s", plan_path)
    return None


# ---------------------------------------------------------------------------
# Claude fix application
# ---------------------------------------------------------------------------


def _apply_claude_fixes(plan_path: Path, findings: list) -> bool:
    """Apply fixes via CLAUDE_FIX_CMD env var (test seam).

    Args:
        plan_path: Path to the plan file.
        findings: List of PlanReviewFinding objects.

    Returns:
        True if fixes were applied successfully, False otherwise.
    """
    cmd = os.environ.get("CLAUDE_FIX_CMD", "").strip()
    if not cmd:
        logger.info("CLAUDE_FIX_CMD not set -- skipping automated fixes")
        return False
    findings_json = json.dumps([f.to_dict() for f in findings])
    try:
        result = subprocess.run(
            [*cmd.split(), str(plan_path)],
            input=findings_json,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# Sidecar review file
# ---------------------------------------------------------------------------


def _write_sidecar(
    plan_path: Path,
    loop_state: PlanReviewLoopState,
    all_findings: list[tuple[int, list]],
    reviewer: str,
    base_dir: Path | None = None,
    raw_output: str = "",
) -> Path:
    """Write the review sidecar to .claude/runtime/plan_reviews/<key>/review.md.

    Args:
        plan_path: Path to the plan file.
        loop_state: PlanReviewLoopState object.
        all_findings: List of (iteration, findings) tuples.
        reviewer: Reviewer identifier.
        base_dir: Override for state persistence directory.
        raw_output: Raw output from the last reviewer invocation, for debuggability.

    Returns:
        Path to the written sidecar file.
    """
    sidecar_dir = plan_review_state_dir(loop_state.state_key, base_dir)
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = sidecar_dir / "review.md"

    date = time.strftime("%Y-%m-%d", time.gmtime())

    # Determine verdict from final state
    if loop_state.state == "review_complete":
        verdict = "READY"
    elif loop_state.state == "review_complete_with_issues":
        # Compute from remaining findings
        if all_findings:
            _, last_findings = all_findings[-1]
            verdict = _compute_verdict(last_findings)
        else:
            verdict = "READY"
    else:
        verdict = "UNKNOWN"

    # Build findings table
    rows = []
    for iteration, findings in all_findings:
        for f in findings:
            if hasattr(f, "to_dict"):
                fd = f.to_dict()
            else:
                fd = f
            rows.append(
                f"| {iteration} "
                f"| {fd.get('check_id', '-')} "
                f"| {fd.get('severity', '-')} "
                f"| {fd.get('description', '-')} "
                f"| open |"
            )

    findings_table = (
        "| Iteration | ID | Severity | Finding | Status |\n"
        "|-----------|-----|----------|---------|--------|\n"
    )
    if rows:
        findings_table += "\n".join(rows) + "\n"
    else:
        findings_table += "| - | - | - | No findings | - |\n"

    content = (
        f"# Plan Review: {plan_path.name}\n\n"
        f"- **Reviewer:** {reviewer}\n"
        f"- **Tier:** {loop_state.tier}\n"
        f"- **Iterations:** {loop_state.iteration_count}/{loop_state.max_iterations}\n"
        f"- **Date:** {date}\n"
        f"- **Verdict:** {verdict}\n\n"
        f"## Findings\n\n{findings_table}\n"
        f"## Final State\n\n"
        f"State: `{loop_state.state}`\n"
    )

    # Include raw output for debuggability (especially for unparseable failures)
    if raw_output:
        content += f"\n## Raw Output\n\n```\n{raw_output}\n```\n"

    sidecar_path.write_text(content, encoding="utf-8")
    logger.info("Wrote sidecar review to %s", sidecar_path)
    return sidecar_path


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_plan_review_loop(
    plan_path: Path,
    *,
    tier: str | None = None,
    max_iter: int = 3,
    base_dir: Path | None = None,
) -> PlanReviewLoopResult:
    """Run the plan review loop.

    Args:
        plan_path: Path to the plan file (repo-relative).
        tier: Override for the plan tier. Detected automatically if None.
        max_iter: Maximum number of review iterations.
        base_dir: Override for state persistence directory.

    Returns:
        PlanReviewLoopResult with verdict, findings, and metadata.
    """
    # Step 1: Detect tier
    if tier is None:
        tier = detect_plan_tier(plan_path)
    logger.info(
        "Plan review loop starting: %s (tier=%s, max_iter=%d)",
        plan_path,
        tier,
        max_iter,
    )

    # Step 2: Create or load state
    key = plan_state_key(plan_path)
    loop_state = load_plan_review_state(key, base_dir)
    if loop_state is not None and not loop_state.is_terminal:
        # Resuming from a non-terminal state. Reset to INITIALIZED so the
        # loop can cleanly transition to CODEX_REVIEWING. Without this,
        # restarting from states like CODEX_REVIEWING would raise
        # InvalidTransitionError because self-transitions are not allowed.
        logger.info(
            "Resuming plan review from state %s — resetting to INITIALIZED",
            loop_state.state,
        )
        loop_state.state = PlanReviewState.INITIALIZED.value
        loop_state.updated_at = time.time()
    if loop_state is None or loop_state.is_terminal:
        loop_state = PlanReviewLoopState(
            plan_path=str(plan_path),
            state_key=key,
            tier=tier,
            max_iterations=max_iter,
        )

    all_findings: list[tuple[int, list[PlanReviewFinding]]] = []
    current_findings: list[PlanReviewFinding] = []
    reviewer = "codex_cli"
    fallback_used = False
    fallback_issue_url: str | None = None
    last_raw_output: str = ""

    # Compute the output directory for raw output persistence.
    # Previously this was base_dir (often None), causing _save_raw_output to no-op.
    output_dir = plan_review_state_dir(key, base_dir)

    # Step 3: Loop
    while not loop_state.is_terminal and loop_state.iteration_count < max_iter:
        loop_state.iteration_count += 1
        iteration = loop_state.iteration_count
        logger.info("Plan review iteration %d/%d", iteration, max_iter)

        # 3a: Transition to CODEX_REVIEWING and invoke Codex
        loop_state.transition(PlanReviewState.CODEX_REVIEWING)
        save_plan_review_state(loop_state, base_dir)

        result = invoke_codex_plan_review(plan_path, tier, output_dir=output_dir)
        last_raw_output = result.raw_output

        if not result.success:
            # 3b: Codex failed -> fallback
            logger.warning(
                "Codex failed (iter %d): %s -- triggering Claude fallback",
                iteration,
                result.error,
            )
            loop_state.transition(PlanReviewState.CODEX_FALLBACK)
            loop_state.fallback_used = True
            loop_state.fallback_reason = result.error
            save_plan_review_state(loop_state, base_dir)

            # Invoke Claude failsafe
            loop_state.transition(PlanReviewState.CLAUDE_FALLBACK_REVIEWING)
            save_plan_review_state(loop_state, base_dir)

            fallback_result = invoke_claude_failsafe(
                plan_path, tier, output_dir=output_dir
            )
            fallback_used = True
            reviewer = "claude_failsafe"
            last_raw_output = fallback_result.raw_output

            # Create fallback issue
            fallback_issue_url = _create_fallback_issue(
                plan_path, tier, result.error or "Unknown error"
            )

            if fallback_result.success and fallback_result.findings:
                # Claude found real issues
                current_findings = fallback_result.findings
                loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
                all_findings.append((iteration, current_findings))
            elif fallback_result.success:
                # Claude completed successfully with no findings — clean review
                current_findings = []
                loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
                loop_state.transition(PlanReviewState.REVIEW_COMPLETE)
            else:
                # Both reviewers actually failed — inject synthetic CRITICAL
                # so the verdict is NOT_READY instead of falsely reporting READY.
                no_review_finding = PlanReviewFinding(
                    severity="CRITICAL",
                    category="process",
                    file=str(plan_path),
                    line=0,
                    description=(
                        "No review completed: both Codex CLI and Claude fallback "
                        "failed to produce findings. Plan has not been reviewed."
                    ),
                    check_id=None,
                    source="plan_review_driver",
                )
                current_findings = [no_review_finding]
                loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
                all_findings.append((iteration, current_findings))
                loop_state.transition(PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES)
                loop_state.stop_reason = "Codex and Claude fallback both unavailable"
            save_plan_review_state(loop_state, base_dir)
            break  # Don't iterate after fallback

        # 3c: Codex succeeded
        current_findings = result.findings

        if not current_findings:
            # Clean review
            loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
            loop_state.transition(PlanReviewState.REVIEW_COMPLETE)
            save_plan_review_state(loop_state, base_dir)
            break

        # 3d: Has findings -> check stagnation
        loop_state.transition(PlanReviewState.FINDINGS_RECEIVED)
        all_findings.append((iteration, current_findings))

        findings_hash = compute_findings_hash([f.to_dict() for f in current_findings])
        if findings_hash == loop_state.last_findings_hash:
            logger.info("Stagnation detected (iter %d): same findings hash", iteration)
            loop_state.stop_reason = "Stagnation: same findings after fix attempt"
            loop_state.transition(PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES)
            save_plan_review_state(loop_state, base_dir)
            break
        loop_state.last_findings_hash = findings_hash

        # 3e: If more iterations available, try fixing
        if iteration < max_iter:
            loop_state.transition(PlanReviewState.CLAUDE_FIXING)
            save_plan_review_state(loop_state, base_dir)

            fixed = _apply_claude_fixes(plan_path, current_findings)
            if not fixed:
                logger.info("No fixes applied (iter %d) -- stopping", iteration)
                loop_state.transition(PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES)
                loop_state.stop_reason = "No automated fixes available"
                save_plan_review_state(loop_state, base_dir)
                break
            # Loop back to CODEX_REVIEWING on next iteration
        else:
            # Max iterations reached
            loop_state.transition(PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES)
            loop_state.stop_reason = f"Max iterations ({max_iter}) reached"
            save_plan_review_state(loop_state, base_dir)

    # Handle case where we exit the while-loop due to iteration count
    if not loop_state.is_terminal:
        loop_state.transition(PlanReviewState.REVIEW_COMPLETE_WITH_ISSUES)
        loop_state.stop_reason = f"Max iterations ({max_iter}) reached"
        save_plan_review_state(loop_state, base_dir)

    # Step 4: Write sidecar (include raw output for debuggability)
    sidecar_path = _write_sidecar(
        plan_path,
        loop_state,
        all_findings,
        reviewer,
        base_dir,
        raw_output=last_raw_output,
    )

    # Step 5: Save final state
    save_plan_review_state(loop_state, base_dir)

    # Step 6: Compute verdict
    verdict = _compute_verdict(current_findings)

    # Flatten all findings for result
    flat_findings: list[dict] = []
    for _, findings_list in all_findings:
        for f in findings_list:
            flat_findings.append(f.to_dict() if hasattr(f, "to_dict") else f)

    return PlanReviewLoopResult(
        plan_path=str(plan_path),
        tier=tier,
        verdict=verdict,
        iterations=loop_state.iteration_count,
        total_findings=len(flat_findings),
        open_findings=len(current_findings),
        reviewer=reviewer,
        fallback_used=fallback_used,
        fallback_issue_url=fallback_issue_url,
        sidecar_path=str(sidecar_path),
        findings=flat_findings,
    )

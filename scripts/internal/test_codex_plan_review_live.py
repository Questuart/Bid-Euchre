#!/usr/bin/env python3
"""Live smoke/quick/full test for Codex CLI plan review pipeline.

Tests the plan review adapter and driver against the actual Codex CLI
to verify end-to-end functionality without mocks.

Usage:
    # Smoke only (~30s) -- tests auth + single small plan review
    uv run python scripts/internal/test_codex_plan_review_live.py --mode smoke

    # Quick (~2min) -- smoke + medium plan that previously timed out
    uv run python scripts/internal/test_codex_plan_review_live.py --mode quick

    # Full (~5min) -- quick + governing plan + simulated long session
    uv run python scripts/internal/test_codex_plan_review_live.py --mode full

Exit codes:
    0 = all tests passed
    1 = test failure
    2 = setup error (auth missing, plan files missing)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Import sibling modules from scripts/internal/ via importlib
_scripts_dir = str(Path(__file__).resolve().parent)


def _import_sibling(module_name: str):
    """Import a sibling module from scripts/internal/ without sys.path mutation.

    Registers the module in sys.modules so that transitive imports
    (e.g., plan_review_driver importing codex_plan_review_adapter)
    resolve correctly through the standard import machinery.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        module_name, Path(_scripts_dir) / f"{module_name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Load order matters: plan_review_driver transitively imports both
# codex_plan_review_adapter and review_state, so they must be registered
# in sys.modules first.
_adapter = _import_sibling("codex_plan_review_adapter")
_import_sibling("review_state")
_driver = _import_sibling("plan_review_driver")

PlanReviewResult = _adapter.PlanReviewResult
_check_codex_auth = _adapter._check_codex_auth
detect_plan_tier = _adapter.detect_plan_tier
invoke_codex_plan_review = _adapter.invoke_codex_plan_review
run_plan_review_loop = _driver.run_plan_review_loop

# --- Test Plans ---

# Small plan (should exist after the fix PR)
SMALL_PLAN = Path("plans/sessions/2026-03-15_fix-codex-plan-review-timeout.md")

# Medium plan (the one that originally timed out at 300s)
MEDIUM_PLAN = Path("plans/sessions/2026-03-15_full-backfill-r0-r2.md")

# Governing plan (heaviest workload)
GOVERNING_PLAN = Path("plans/browser_game/governing_plan.md")

# Latency threshold -- anything above this suggests the old hang behavior
MAX_ACCEPTABLE_LATENCY = 180.0  # seconds


def _banner(msg: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {msg}")
    print(f"{'=' * 60}\n")


def _check_plan_exists(plan: Path) -> bool:
    if plan.exists():
        return True
    print(f"  SKIP: {plan} not found")
    return False


def _report_result(
    label: str,
    result: PlanReviewResult,
    *,
    max_latency: float = MAX_ACCEPTABLE_LATENCY,
) -> bool:
    """Print result summary and return True if test passed."""
    passed = True
    status = "PASS" if result.success else "FAIL"

    print(f"  [{status}] {label}")
    print(f"    Reviewer:  {result.reviewer}")
    print(f"    Latency:   {result.latency_seconds:.1f}s")
    print(f"    Findings:  {len(result.findings)}")
    if result.error:
        print(f"    Error:     {result.error}")

    if not result.success:
        print("    FAILED: Codex review did not succeed")
        passed = False

    if result.latency_seconds > max_latency:
        print(
            f"    FAILED: Latency {result.latency_seconds:.1f}s "
            f"> threshold {max_latency}s (possible hang)"
        )
        passed = False

    if result.error and "Timeout" in result.error:
        print("    FAILED: Hit timeout -- the old bug may still be present")
        passed = False

    return passed


def _report_loop_result(label: str, result) -> bool:
    """Print loop result summary and return True if test passed."""
    passed = True

    verdict_ok = result.verdict in ("READY", "NEEDS_ATTENTION")
    status = "PASS" if verdict_ok else "FAIL"

    print(f"  [{status}] {label}")
    print(f"    Verdict:    {result.verdict}")
    print(f"    Iterations: {result.iterations}")
    print(f"    Reviewer:   {result.reviewer}")
    print(f"    Findings:   {result.total_findings} total, {result.open_findings} open")
    print(f"    Fallback:   {result.fallback_used}")
    if result.sidecar_path:
        print(f"    Sidecar:    {result.sidecar_path}")

    if not verdict_ok:
        print(
            f"    FAILED: Verdict {result.verdict} (expected READY or NEEDS_ATTENTION)"
        )
        passed = False

    if result.fallback_used:
        print("    WARNING: Fallback was used -- Codex CLI may not be working")

    return passed


# --- Test Tiers ---


def test_smoke() -> bool:
    """Smoke test: auth check + single small plan review."""
    _banner("SMOKE TEST: Auth + Small Plan Review")
    all_passed = True

    # Test 1: Auth pre-flight
    print("Test 1: Pre-flight auth check")
    auth_err = _check_codex_auth()
    if auth_err:
        print(f"  FAIL: Auth check failed: {auth_err}")
        print("  FIX:  Run 'npx @openai/codex login' to authenticate")
        return False
    print("  PASS: Auth check OK\n")

    # Test 2: Tier detection
    print("Test 2: Tier detection")
    if _check_plan_exists(SMALL_PLAN):
        tier = detect_plan_tier(SMALL_PLAN)
        print(f"  PASS: {SMALL_PLAN.name} -> tier={tier}\n")

    # Test 3: Direct adapter invocation on small plan
    print("Test 3: invoke_codex_plan_review (small plan, 120s timeout)")
    if _check_plan_exists(SMALL_PLAN):
        result = invoke_codex_plan_review(SMALL_PLAN, "small", timeout=120)
        if not _report_result("Small plan review", result, max_latency=120):
            all_passed = False
    print()

    return all_passed


def test_quick() -> bool:
    """Quick test: smoke + medium plan via driver loop."""
    all_passed = test_smoke()
    _banner("QUICK TEST: Medium Plan via Driver Loop")

    # Test 4: Full driver loop on the plan that originally timed out
    print("Test 4: run_plan_review_loop (medium plan -- previously timed out)")
    if _check_plan_exists(MEDIUM_PLAN):
        result = run_plan_review_loop(MEDIUM_PLAN, max_iter=2)
        if not _report_loop_result("Medium plan loop", result):
            all_passed = False
    print()

    # Test 5: Small plan through the driver loop
    print("Test 5: run_plan_review_loop (small plan)")
    if _check_plan_exists(SMALL_PLAN):
        result = run_plan_review_loop(SMALL_PLAN, max_iter=1)
        if not _report_loop_result("Small plan loop", result):
            all_passed = False
    print()

    return all_passed


def test_full() -> bool:
    """Full test: quick + governing plan + simulated long session."""
    all_passed = test_quick()
    _banner("FULL TEST: Governing Plan + Long Session Simulation")

    # Test 6: Governing plan (heaviest workload)
    print("Test 6: run_plan_review_loop (governing plan -- heaviest workload)")
    if _check_plan_exists(GOVERNING_PLAN):
        result = run_plan_review_loop(GOVERNING_PLAN, max_iter=2)
        if not _report_loop_result("Governing plan loop", result):
            all_passed = False
    print()

    # Test 7: Simulated long session -- run 3 sequential reviews
    # to verify auth doesn't degrade across multiple invocations
    _banner("LONG SESSION TEST: 3 Sequential Reviews")
    print("Test 7: Sequential review stability (simulates orchestrator session)")
    plans = [p for p in [SMALL_PLAN, MEDIUM_PLAN, GOVERNING_PLAN] if p.exists()]
    if not plans:
        print("  SKIP: No plan files available")
    else:
        for i, plan in enumerate(plans, 1):
            print(f"\n  Round {i}/{len(plans)}: {plan.name}")
            start = time.monotonic()
            result = invoke_codex_plan_review(plan, detect_plan_tier(plan), timeout=180)
            elapsed = time.monotonic() - start

            if not result.success:
                print(
                    f"    FAIL: Round {i} failed after {elapsed:.1f}s: {result.error}"
                )
                all_passed = False
            else:
                print(
                    f"    PASS: Completed in {result.latency_seconds:.1f}s, "
                    f"{len(result.findings)} findings"
                )

            # Check auth is still valid between rounds
            auth_err = _check_codex_auth()
            if auth_err:
                print(f"    FAIL: Auth degraded after round {i}: {auth_err}")
                all_passed = False
            else:
                print(f"    Auth still valid after round {i}")
    print()

    return all_passed


# --- Main ---


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live test for Codex CLI plan review pipeline"
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick", "full"],
        default="smoke",
        help="Test tier: smoke (~30s), quick (~2min), full (~5min)",
    )
    args = parser.parse_args()

    _banner(f"Codex Plan Review Live Test -- mode={args.mode}")

    # Verify we're in the repo root
    if not Path("CLAUDE.md").exists():
        print("ERROR: Must be run from the repo root")
        return 2

    test_fn = {"smoke": test_smoke, "quick": test_quick, "full": test_full}[args.mode]

    start = time.monotonic()
    passed = test_fn()
    total = time.monotonic() - start

    _banner(f"RESULT: {'ALL PASSED' if passed else 'FAILURES DETECTED'} ({total:.1f}s)")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

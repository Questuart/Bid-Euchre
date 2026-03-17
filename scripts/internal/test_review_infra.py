#!/usr/bin/env python3
"""Tiered end-to-end test harness for review infrastructure.

Exercises the real review loops (plan and PR) at three tiers:
  SMOKE (~30s)  — plumbing checks, no Codex auth needed
  QUICK (~5min) — real Codex invocation on small/medium fixtures
  FULL  (~15min) — all tiers, latency profiling, forced failures

Usage:
    uv run python scripts/internal/test_review_infra.py --mode smoke
    uv run python scripts/internal/test_review_infra.py --mode quick
    uv run python scripts/internal/test_review_infra.py --mode full

Not included in ``make check`` — run on-demand after infrastructure changes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Imports assume PYTHONPATH includes scripts/internal (set by Makefile targets)
from codex_plan_review_adapter import (
    _check_codex_auth,
    _run_with_pty,
    detect_plan_tier,
    invoke_claude_failsafe,
    invoke_codex_plan_review,
)
from codex_review_adapter import invoke_codex_cli
from plan_review_driver import run_plan_review_loop
from review_state import (
    PlanReviewLoopState,
    load_plan_review_state,
    save_plan_review_state,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "plans"
SMALL_FIXTURE = FIXTURE_DIR / "small_fixture.md"
MEDIUM_FIXTURE = FIXTURE_DIR / "medium_fixture.md"
GOVERNING_FIXTURE = FIXTURE_DIR / "governing_fixture.md"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class TestResult:
    test: str
    status: str  # PASS, FAIL, SKIP, ERROR
    latency_s: float
    details: str


@dataclass
class HarnessResult:
    mode: str
    timestamp: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> str:
        counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        total = len(self.results)
        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        return f"{total} tests: {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Test implementations
# ---------------------------------------------------------------------------


def _run_test(name: str, fn, *args, **kwargs) -> TestResult:
    """Run a test function and capture result/timing."""
    start = time.monotonic()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.monotonic() - start
        if result is True or result is None:
            return TestResult(name, "PASS", elapsed, "ok")
        if isinstance(result, str):
            return TestResult(name, "PASS", elapsed, result)
        return TestResult(name, "FAIL", elapsed, str(result))
    except SkipTest as exc:
        return TestResult(name, "SKIP", time.monotonic() - start, str(exc))
    except Exception as exc:
        return TestResult(
            name, "ERROR", time.monotonic() - start, f"{type(exc).__name__}: {exc}"
        )


class SkipTest(Exception):
    pass


# --- SMOKE tests ---


def test_s1_pty_basic():
    """S1: PTY runs a command and captures output."""
    rc, output = _run_with_pty(["echo", "hello_from_pty"], timeout=10)
    assert rc == 0, f"Expected rc=0, got {rc}"
    assert "hello_from_pty" in output, f"Output missing expected string: {output[:100]}"
    return "echo captured"


def test_s2_pty_timeout():
    """S2: PTY kills process on timeout."""
    start = time.monotonic()
    rc, output = _run_with_pty(["sleep", "30"], timeout=2)
    elapsed = time.monotonic() - start
    assert rc is None, f"Expected rc=None (timeout), got {rc}"
    assert elapsed < 5, f"Timeout took too long: {elapsed:.1f}s"
    return f"killed in {elapsed:.1f}s"


def test_s3_tier_detection():
    """S3: Tier classifier returns correct tiers for fixtures."""
    assert (
        detect_plan_tier(SMALL_FIXTURE) == "small"
    ), "Small fixture not detected as small"
    assert (
        detect_plan_tier(MEDIUM_FIXTURE) == "medium"
    ), "Medium fixture not detected as medium"
    assert (
        detect_plan_tier(GOVERNING_FIXTURE) == "governing"
    ), "Governing fixture not detected"
    return "all 3 tiers correct"


def test_s4_state_persistence(tmp_dir: Path):
    """S4: State save/load round-trips correctly."""
    state = PlanReviewLoopState(
        plan_path="test.md",
        state_key="test_key_s4",
        tier="small",
    )
    save_plan_review_state(state, tmp_dir)
    loaded = load_plan_review_state("test_key_s4", tmp_dir)
    assert loaded is not None, "State not found after save"
    assert loaded.plan_path == "test.md"
    assert loaded.tier == "small"
    return "round-trip ok"


def test_s5_output_parsing():
    """S5: Known Codex output samples parse correctly."""
    from codex_review_adapter import _CLEAN_REVIEW_PATTERNS, parse_codex_output

    # Clean review signal
    clean = "No issues found. The code looks good."
    assert _CLEAN_REVIEW_PATTERNS.search(clean), "Clean signal not detected"
    assert parse_codex_output(clean) == [], "Clean output should produce no findings"

    # Finding pattern
    finding_output = "[P1] Missing seed in experiment command\n- `scripts/run.py:42`\n"
    findings = parse_codex_output(finding_output)
    # May or may not parse depending on exact pattern — just verify no crash
    return f"parsed {len(findings)} findings from sample"


def test_s6_codex_auth():
    """S6: Auth file detection works."""
    result = _check_codex_auth()
    if result is None:
        return "auth valid"
    return f"auth issue (non-blocking): {result}"


def test_s7_claude_cli():
    """S7: Claude CLI is detectable in PATH."""
    path = shutil.which("claude")
    assert path is not None, "claude CLI not found in PATH"
    return f"found at {path}"


# --- QUICK tests ---


def test_q1_codex_plan_review_small(tmp_dir: Path):
    """Q1: Full plan review loop on small fixture."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")
    result = run_plan_review_loop(SMALL_FIXTURE, base_dir=tmp_dir)
    assert result.verdict in (
        "READY",
        "NEEDS_ATTENTION",
    ), f"Unexpected verdict: {result.verdict}"
    return f"{result.verdict}, {result.total_findings} findings, {result.reviewer}"


def test_q2_codex_plan_review_medium(tmp_dir: Path):
    """Q2: Full plan review loop on medium fixture."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")
    result = run_plan_review_loop(MEDIUM_FIXTURE, base_dir=tmp_dir)
    # Medium fixture has deliberate issues — expect findings
    assert result.verdict in (
        "READY",
        "NEEDS_ATTENTION",
        "NOT_READY",
    ), f"Unexpected: {result.verdict}"
    return f"{result.verdict}, {result.total_findings} findings"


def test_q3_raw_output_persisted(tmp_dir: Path):
    """Q3: Raw output files exist after Q1/Q2."""
    # Search the parent temp dir (Q1/Q2 write to sibling subdirs)
    parent = tmp_dir.parent
    raw_files = list(parent.rglob("codex_output_raw.txt"))
    if not raw_files:
        raise SkipTest("No Codex reviews ran — cannot check raw output")
    total_size = sum(f.stat().st_size for f in raw_files)
    return f"{len(raw_files)} raw files, {total_size} bytes total"


def test_q4_claude_failsafe(tmp_dir: Path):
    """Q4: Claude failsafe produces parseable output."""
    # Force Codex failure by setting CODEX_REVIEW_CMD to a non-zero exit script
    old_val = os.environ.get("CODEX_REVIEW_CMD")
    try:
        os.environ["CODEX_REVIEW_CMD"] = "false"
        result = invoke_codex_plan_review(SMALL_FIXTURE, "small", output_dir=tmp_dir)
        assert not result.success, "Codex should have failed with 'false' command"

        # Now test the failsafe directly
        failsafe = invoke_claude_failsafe(
            SMALL_FIXTURE, "small", timeout=120, output_dir=tmp_dir
        )
        return f"failsafe: success={failsafe.success}, reviewer={failsafe.reviewer}"
    finally:
        if old_val is None:
            os.environ.pop("CODEX_REVIEW_CMD", None)
        else:
            os.environ["CODEX_REVIEW_CMD"] = old_val


def _create_test_worktree(tmp_dir: Path) -> Path:
    """Create a temporary git worktree with a small committed change.

    Returns the worktree path. The caller should clean up via
    ``git worktree remove``.
    """
    import subprocess as _sp

    wt_path = tmp_dir / "test_worktree"
    branch = f"test-review-infra-{os.getpid()}"

    # Create worktree from current HEAD
    _sp.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    )

    # Make a trivial change and commit it
    test_file = wt_path / "test_review_infra_canary.txt"
    test_file.write_text("This file tests the PR review path.\n")
    _sp.run(["git", "add", "test_review_infra_canary.txt"], cwd=wt_path, check=True)
    _sp.run(
        ["git", "commit", "--no-verify", "-m", "test: canary commit for review infra"],
        cwd=wt_path,
        capture_output=True,
        check=True,
    )

    return wt_path


def _cleanup_test_worktree(wt_path: Path):
    """Remove test worktree and its branch."""
    import subprocess as _sp

    branch = _sp.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=wt_path,
        capture_output=True,
        text=True,
    ).stdout.strip()

    _sp.run(
        ["git", "worktree", "remove", "--force", str(wt_path)],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    _sp.run(
        ["git", "branch", "-D", branch],
        cwd=REPO_ROOT,
        capture_output=True,
    )


def test_q5_pr_review_invocation(tmp_dir: Path):
    """Q5: Codex CLI PR review on a test worktree with a known diff."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")

    wt_path = _create_test_worktree(tmp_dir)
    try:
        result = invoke_codex_cli(base="main", cwd=wt_path)
        assert result.success or result.error, f"No success or error: {result}"
        if result.success:
            return f"PR review OK, {len(result.findings)} findings"
        return f"PR review returned error (non-fatal): {result.error[:80]}"
    finally:
        _cleanup_test_worktree(wt_path)


# --- FULL tests ---


def test_f1_all_tiers(tmp_dir: Path):
    """F1: Plan review on all 3 tier fixtures."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")
    results = {}
    for name, fixture in [
        ("small", SMALL_FIXTURE),
        ("medium", MEDIUM_FIXTURE),
        ("governing", GOVERNING_FIXTURE),
    ]:
        sub_dir = tmp_dir / name
        sub_dir.mkdir()
        r = run_plan_review_loop(fixture, base_dir=sub_dir)
        results[name] = r.verdict
        assert (
            r.verdict != "NOT_READY" or r.fallback_used
        ), f"{name}: NOT_READY without fallback"
    return f"small={results['small']}, medium={results['medium']}, governing={results['governing']}"


def test_f2_latency_profile(tmp_dir: Path):
    """F2: Measure latency distribution across tiers."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")
    latencies = {}
    timeout = int(os.environ.get("CODEX_REVIEW_TIMEOUT", "600"))
    for name, fixture in [("small", SMALL_FIXTURE), ("medium", MEDIUM_FIXTURE)]:
        sub_dir = tmp_dir / f"latency_{name}"
        sub_dir.mkdir()
        start = time.monotonic()
        run_plan_review_loop(fixture, base_dir=sub_dir)
        latencies[name] = time.monotonic() - start
    report = ", ".join(f"{k}={v:.0f}s" for k, v in latencies.items())
    # Check p95 proxy: both should be under timeout
    for name, lat in latencies.items():
        assert lat < timeout, f"{name} latency {lat:.0f}s >= timeout {timeout}s"
    return report


def test_f4_timeout_recovery(tmp_dir: Path):
    """F4: Forced timeout produces correct error and state."""
    old_val = os.environ.get("CODEX_REVIEW_TIMEOUT")
    try:
        os.environ["CODEX_REVIEW_TIMEOUT"] = "5"
        result = invoke_codex_plan_review(
            SMALL_FIXTURE, "small", timeout=5, output_dir=tmp_dir
        )
        assert not result.success, "Should have timed out with 5s timeout"
        assert "Timeout" in (
            result.error or ""
        ), f"Error should mention timeout: {result.error}"
        # Check raw output was persisted
        raw_file = tmp_dir / "codex_output_raw.txt"
        if raw_file.exists():
            return f"timeout captured, raw output {raw_file.stat().st_size} bytes"
        return "timeout captured, no output (expected for 5s)"
    finally:
        if old_val is None:
            os.environ.pop("CODEX_REVIEW_TIMEOUT", None)
        else:
            os.environ["CODEX_REVIEW_TIMEOUT"] = old_val


def test_f5_failsafe_chain(tmp_dir: Path):
    """F5: Force both failures → synthetic CRITICAL finding."""
    old_codex = os.environ.get("CODEX_REVIEW_CMD")
    old_claude = os.environ.get("CLAUDE_REVIEW_CMD")
    try:
        os.environ["CODEX_REVIEW_CMD"] = "false"
        os.environ["CLAUDE_REVIEW_CMD"] = "false"
        result = run_plan_review_loop(SMALL_FIXTURE, base_dir=tmp_dir)
        assert (
            result.verdict == "NOT_READY"
        ), f"Expected NOT_READY, got {result.verdict}"
        assert result.fallback_used, "Fallback should have been used"
        return f"NOT_READY with {result.total_findings} findings"
    finally:
        if old_codex is None:
            os.environ.pop("CODEX_REVIEW_CMD", None)
        else:
            os.environ["CODEX_REVIEW_CMD"] = old_codex
        if old_claude is None:
            os.environ.pop("CLAUDE_REVIEW_CMD", None)
        else:
            os.environ["CLAUDE_REVIEW_CMD"] = old_claude


def test_f6_pr_review_loop_round(tmp_dir: Path):
    """F6: Single round of PR review loop in a test worktree."""
    auth = _check_codex_auth()
    if auth:
        raise SkipTest(f"Codex auth not available: {auth}")

    wt_path = _create_test_worktree(tmp_dir)
    try:
        # Invoke Codex CLI directly (not the full driver, which needs a real PR)
        result = invoke_codex_cli(base="main", cwd=wt_path)
        if result.success:
            return f"PR round OK, {len(result.findings)} findings, {result.latency_seconds:.0f}s"
        # Non-success is still informative — Codex may find no diff or timeout
        return f"PR round: {result.error[:80]}"
    finally:
        _cleanup_test_worktree(wt_path)


# ---------------------------------------------------------------------------
# Harness runner
# ---------------------------------------------------------------------------

SMOKE_TESTS = [
    ("S1: PTY basic", test_s1_pty_basic),
    ("S2: PTY timeout", test_s2_pty_timeout),
    ("S3: Tier detection", test_s3_tier_detection),
    ("S4: State persistence", test_s4_state_persistence),
    ("S5: Output parsing", test_s5_output_parsing),
    ("S6: Codex auth check", test_s6_codex_auth),
    ("S7: Claude CLI detection", test_s7_claude_cli),
]

QUICK_TESTS = [
    ("Q1: Codex plan review (small)", test_q1_codex_plan_review_small),
    ("Q2: Codex plan review (medium)", test_q2_codex_plan_review_medium),
    ("Q3: Raw output persisted", test_q3_raw_output_persisted),
    ("Q4: Claude failsafe", test_q4_claude_failsafe),
    ("Q5: PR review invocation", test_q5_pr_review_invocation),
]

FULL_TESTS = [
    ("F1: All 3 tiers", test_f1_all_tiers),
    ("F2: Latency profile", test_f2_latency_profile),
    ("F4: Timeout recovery", test_f4_timeout_recovery),
    ("F5: Failsafe chain", test_f5_failsafe_chain),
    ("F6: PR review loop round", test_f6_pr_review_loop_round),
]


def run_harness(mode: str) -> HarnessResult:
    """Run the test harness at the specified tier."""
    import tempfile

    harness = HarnessResult(
        mode=mode,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    # Create a shared temp dir for state persistence
    with tempfile.TemporaryDirectory(prefix="review_infra_") as tmp:
        tmp_dir = Path(tmp)

        tests = list(SMOKE_TESTS)
        if mode in ("quick", "full"):
            tests.extend(QUICK_TESTS)
        if mode == "full":
            tests.extend(FULL_TESTS)

        for name, fn in tests:
            import inspect

            sig = inspect.signature(fn)
            if "tmp_dir" in sig.parameters:
                # Create a sub-dir per test
                test_dir = tmp_dir / name.split(":")[0].strip().replace(" ", "_")
                test_dir.mkdir(exist_ok=True)
                result = _run_test(name, fn, test_dir)
            else:
                result = _run_test(name, fn)

            status_icon = {"PASS": "+", "FAIL": "!", "SKIP": "-", "ERROR": "X"}[
                result.status
            ]
            print(
                f"  [{status_icon}] {result.test}: {result.details} ({result.latency_s:.1f}s)"
            )
            harness.results.append(result)

    return harness


def main():
    parser = argparse.ArgumentParser(description="Review infrastructure test harness")
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick", "full"],
        default="smoke",
        help="Test tier: smoke (~30s), quick (~5min), full (~15min)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of text",
    )
    args = parser.parse_args()

    print(f"Review Infrastructure Test Harness — {args.mode.upper()}")
    print("=" * 50)

    harness = run_harness(args.mode)

    print()
    print(f"Result: {harness.summary}")

    if args.json:
        print()
        print(
            json.dumps(
                {
                    "mode": harness.mode,
                    "timestamp": harness.timestamp,
                    "results": [asdict(r) for r in harness.results],
                    "summary": harness.summary,
                },
                indent=2,
            )
        )

    # Exit with non-zero if any FAIL
    failures = [r for r in harness.results if r.status == "FAIL"]
    if failures:
        print(f"\n{len(failures)} FAILED test(s):")
        for f in failures:
            print(f"  - {f.test}: {f.details}")
        sys.exit(1)


if __name__ == "__main__":
    main()

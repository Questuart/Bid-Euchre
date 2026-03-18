"""Tests for daemon failure notification — sentinel writes and hook behavior."""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from review_driver import _write_failure_sentinel
from review_state import ReviewLoopState, ReviewState

HOOK_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "hooks"
    / "post-tool-daemon-notify.sh"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temporary runtime directory mimicking .claude/runtime/."""
    rd = tmp_path / ".claude" / "runtime"
    rd.mkdir(parents=True)
    return rd


def _make_loop_state(
    pr_number: int = 42,
    state: ReviewState = ReviewState.STOPPED_CI_FAILURE,
    stop_reason: str = "CI failed",
) -> ReviewLoopState:
    """Create a minimal ReviewLoopState for testing."""
    ls = ReviewLoopState(
        pr_number=pr_number,
        branch="test-branch",
        run_id="test-run",
    )
    # Set state directly (bypass transition validation)
    ls.state = state.value
    ls.stop_reason = stop_reason
    return ls


# ---------------------------------------------------------------------------
# _write_failure_sentinel tests
# ---------------------------------------------------------------------------


class TestWriteFailureSentinel:
    """Tests for _write_failure_sentinel in review_driver.py."""

    def test_writes_sentinel_on_ci_failure(self, tmp_path: Path) -> None:
        ls = _make_loop_state(
            state=ReviewState.STOPPED_CI_FAILURE, stop_reason="CI failed"
        )
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert sentinel.exists()
        content = sentinel.read_text()
        assert "STOPPED_CI_FAILURE" in content
        assert "CI failed" in content

    def test_writes_sentinel_on_review_failure(self, tmp_path: Path) -> None:
        ls = _make_loop_state(
            state=ReviewState.STOPPED_REVIEW_FAILURE,
            stop_reason="Codex CLI failed 3 times",
        )
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert sentinel.exists()
        assert "Codex CLI failed" in sentinel.read_text()

    def test_writes_sentinel_on_max_iterations(self, tmp_path: Path) -> None:
        ls = _make_loop_state(
            state=ReviewState.STOPPED_MAX_ITERATIONS,
            stop_reason="Hit max iterations (3)",
        )
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert sentinel.exists()
        assert "max iterations" in sentinel.read_text()

    def test_writes_sentinel_on_no_progress(self, tmp_path: Path) -> None:
        ls = _make_loop_state(
            state=ReviewState.STOPPED_NO_PROGRESS,
            stop_reason="No findings resolved after fix attempt",
        )
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert sentinel.exists()

    def test_no_sentinel_on_success(self, tmp_path: Path) -> None:
        """Non-failure terminal states (MERGED) should NOT write sentinels."""
        ls = _make_loop_state(state=ReviewState.MERGED, stop_reason="")
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert not sentinel.exists()

    def test_no_sentinel_on_non_terminal(self, tmp_path: Path) -> None:
        """Non-terminal states should NOT write sentinels."""
        ls = _make_loop_state(state=ReviewState.WAITING_FOR_CI, stop_reason="")
        with _chdir(tmp_path):
            _write_failure_sentinel(ls)
        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert not sentinel.exists()


# ---------------------------------------------------------------------------
# post-tool-daemon-notify.sh hook tests
# ---------------------------------------------------------------------------


class TestDaemonNotifyHook:
    """Tests for .claude/hooks/post-tool-daemon-notify.sh."""

    def test_no_output_when_no_sentinels(self, tmp_path: Path) -> None:
        """Hook should produce no output when no FAILED sentinels exist."""
        runtime = tmp_path / ".claude" / "runtime"
        runtime.mkdir(parents=True)
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_no_output_when_runtime_missing(self, tmp_path: Path) -> None:
        """Hook should exit cleanly when runtime dir doesn't exist."""
        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_ci_poller_failure_detected(self, tmp_path: Path) -> None:
        """Hook should detect and report CI poller FAILED sentinel."""
        ci_dir = tmp_path / ".claude" / "runtime" / "ci_polls" / "pr_99"
        ci_dir.mkdir(parents=True)
        (ci_dir / "FAILED").write_text("CI_FAILED: Failed checks: tests\n")

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "CI poller" in ctx
        assert "PR #99" in ctx
        assert "CI_FAILED" in ctx

    def test_review_loop_failure_detected(self, tmp_path: Path) -> None:
        """Hook should detect and report review loop FAILED sentinel."""
        rl_dir = tmp_path / ".claude" / "runtime" / "review_loops" / "pr_55"
        rl_dir.mkdir(parents=True)
        (rl_dir / "FAILED").write_text("STOPPED_CI_FAILURE: CI failed\n")

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "Review loop" in ctx
        assert "PR #55" in ctx

    def test_sentinel_renamed_to_notified(self, tmp_path: Path) -> None:
        """After reporting, FAILED should be renamed to NOTIFIED."""
        ci_dir = tmp_path / ".claude" / "runtime" / "ci_polls" / "pr_10"
        ci_dir.mkdir(parents=True)
        (ci_dir / "FAILED").write_text("CI_TIMEOUT: timed out\n")

        _run_hook(tmp_path)

        assert not (ci_dir / "FAILED").exists()
        assert (ci_dir / "NOTIFIED").exists()

    def test_notified_sentinel_not_re_reported(self, tmp_path: Path) -> None:
        """Already-NOTIFIED sentinels should not trigger output."""
        ci_dir = tmp_path / ".claude" / "runtime" / "ci_polls" / "pr_10"
        ci_dir.mkdir(parents=True)
        (ci_dir / "NOTIFIED").write_text("CI_TIMEOUT: timed out\n")

        result = _run_hook(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_multiple_failures_combined(self, tmp_path: Path) -> None:
        """Multiple FAILED sentinels should be combined into one output."""
        ci_dir = tmp_path / ".claude" / "runtime" / "ci_polls" / "pr_10"
        ci_dir.mkdir(parents=True)
        (ci_dir / "FAILED").write_text("CI_FAILED: tests failed\n")

        rl_dir = tmp_path / ".claude" / "runtime" / "review_loops" / "pr_20"
        rl_dir.mkdir(parents=True)
        (rl_dir / "FAILED").write_text("STOPPED_REVIEW_FAILURE: crashed\n")

        result = _run_hook(tmp_path)
        assert result.returncode == 0

        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "PR #10" in ctx
        assert "PR #20" in ctx
        # Both should be renamed
        assert not (ci_dir / "FAILED").exists()
        assert not (rl_dir / "FAILED").exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _chdir(path: Path):
    """Context manager to change cwd temporarily."""
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def _run_hook(project_dir: Path) -> subprocess.CompletedProcess:
    """Run the daemon notify hook with CLAUDE_PROJECT_DIR set."""
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["bash", str(HOOK_SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=10,
    )

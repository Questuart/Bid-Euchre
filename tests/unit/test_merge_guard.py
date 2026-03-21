"""Tests for the pre-merge review guard and review_driver verdict writing.

Tests verdict writing at terminal states (via review_driver._write_verdict_if_applicable)
and the merge guard logic (verdict presence, SHA matching, status checks).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from bid_euchre.ops.review_queue import (
    STATUS_BLOCKED,
    STATUS_PASSED,
    ReviewVerdict,
    read_verdict,
    write_verdict,
)

# ---------------------------------------------------------------------------
# Verdict file read/write round-trip (guard relies on these)
# ---------------------------------------------------------------------------


class TestVerdictRoundTrip:
    """Guard reads verdict files — verify they survive write→read."""

    def test_passed_verdict_survives_round_trip(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc1234567890",
            status=STATUS_PASSED,
            reason="Review passed -- clean",
        )
        write_verdict(v, tmp_path, emit_event=False)
        loaded = read_verdict(42, tmp_path)
        assert loaded is not None
        assert loaded.status == STATUS_PASSED
        assert loaded.reviewed_sha == "abc1234567890"

    def test_blocked_verdict_survives_round_trip(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc1234567890",
            status=STATUS_BLOCKED,
            reason="Blocking precheck failures",
        )
        write_verdict(v, tmp_path, emit_event=False)
        loaded = read_verdict(42, tmp_path)
        assert loaded is not None
        assert loaded.status == STATUS_BLOCKED

    def test_missing_verdict_returns_none(self, tmp_path: Path) -> None:
        loaded = read_verdict(999, tmp_path)
        assert loaded is None


# ---------------------------------------------------------------------------
# Merge guard decision logic
# ---------------------------------------------------------------------------


def _guard_check(
    pr_number: int,
    current_sha: str,
    ci_status: str,
    queue_dir: Path,
) -> tuple[bool, str]:
    """Pure-Python equivalent of the merge guard bash logic.

    Returns (allowed, reason) matching the guard's decision flow.
    """
    verdict = read_verdict(pr_number, queue_dir)

    if verdict is None:
        return False, f"No review verdict found for PR #{pr_number}"

    if verdict.reviewed_sha != current_sha:
        return False, (
            f"Stale verdict: covers {verdict.reviewed_sha[:8]} "
            f"but current HEAD is {current_sha[:8]}"
        )

    if verdict.status != STATUS_PASSED:
        return False, f'Review verdict is "{verdict.status}", not "passed"'

    if ci_status != "success":
        return False, f'CI status is "{ci_status}", not "success"'

    return True, "Ready to merge"


class TestMergeGuardLogic:
    """Test the merge guard decision logic."""

    def test_allows_passed_verdict_matching_sha_ci_green(self, tmp_path: Path) -> None:
        sha = "abc1234567890"
        v = ReviewVerdict(
            pr_number=42, reviewed_sha=sha, status=STATUS_PASSED, reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)

        allowed, reason = _guard_check(42, sha, "success", tmp_path)
        assert allowed is True
        assert "Ready" in reason

    def test_blocks_no_verdict(self, tmp_path: Path) -> None:
        allowed, reason = _guard_check(42, "abc123", "success", tmp_path)
        assert allowed is False
        assert "No review verdict" in reason

    def test_blocks_stale_verdict(self, tmp_path: Path) -> None:
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="old_sha_1234",
            status=STATUS_PASSED,
            reason="clean",
        )
        write_verdict(v, tmp_path, emit_event=False)

        allowed, reason = _guard_check(42, "new_sha_5678", "success", tmp_path)
        assert allowed is False
        assert "Stale" in reason

    def test_blocks_non_passed_verdict(self, tmp_path: Path) -> None:
        sha = "abc1234567890"
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha=sha,
            status=STATUS_BLOCKED,
            reason="Blocking findings",
        )
        write_verdict(v, tmp_path, emit_event=False)

        allowed, reason = _guard_check(42, sha, "success", tmp_path)
        assert allowed is False
        assert "blocked" in reason

    def test_blocks_ci_failure(self, tmp_path: Path) -> None:
        sha = "abc1234567890"
        v = ReviewVerdict(
            pr_number=42, reviewed_sha=sha, status=STATUS_PASSED, reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)

        allowed, reason = _guard_check(42, sha, "failure", tmp_path)
        assert allowed is False
        assert "CI" in reason

    def test_blocks_ci_pending(self, tmp_path: Path) -> None:
        sha = "abc1234567890"
        v = ReviewVerdict(
            pr_number=42, reviewed_sha=sha, status=STATUS_PASSED, reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)

        allowed, reason = _guard_check(42, sha, "pending", tmp_path)
        assert allowed is False
        assert "CI" in reason

    def test_allows_ci_success_with_skipped(self, tmp_path: Path) -> None:
        """Guard must allow merge when CI reports 'success' (which now includes SKIPPED)."""
        sha = "abc1234567890"
        v = ReviewVerdict(
            pr_number=42, reviewed_sha=sha, status=STATUS_PASSED, reason="clean"
        )
        write_verdict(v, tmp_path, emit_event=False)

        # The guard receives the aggregated CI status, not raw check states.
        # get_ci_status() now returns "success" for SUCCESS+SKIPPED mixes.
        allowed, reason = _guard_check(42, sha, "success", tmp_path)
        assert allowed is True
        assert "Ready" in reason


# ---------------------------------------------------------------------------
# review_driver._write_verdict_if_applicable integration
# ---------------------------------------------------------------------------


class TestReviewDriverVerdictWriting:
    """Test that _write_verdict_if_applicable writes verdicts correctly."""

    def test_writes_passed_on_ready_to_merge(self, tmp_path: Path) -> None:
        """READY_TO_MERGE state should produce a 'passed' verdict."""
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test",
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="sha_abc123",
        )

        # Patch shared_queue_root to redirect writes to tmp_path
        with patch(
            "bid_euchre.ops.review_queue.shared_queue_root", return_value=tmp_path
        ):
            from review_driver import _write_verdict_if_applicable

            _write_verdict_if_applicable(loop)

        verdict = read_verdict(42, tmp_path)
        assert verdict is not None
        assert verdict.status == STATUS_PASSED
        assert verdict.reviewed_sha == "sha_abc123"

    def test_writes_blocked_on_failure_state(self, tmp_path: Path) -> None:
        """STOPPED_CI_FAILURE should produce a 'blocked' verdict."""
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test",
            state=ReviewState.STOPPED_CI_FAILURE.value,
            current_head_sha="sha_def456",
            stop_reason="CI failed",
        )

        with patch(
            "bid_euchre.ops.review_queue.shared_queue_root", return_value=tmp_path
        ):
            from review_driver import _write_verdict_if_applicable

            _write_verdict_if_applicable(loop)

        verdict = read_verdict(42, tmp_path)
        assert verdict is not None
        assert verdict.status == STATUS_BLOCKED
        assert "CI failed" in verdict.reason

    def test_no_verdict_on_non_terminal_state(self, tmp_path: Path) -> None:
        """WAITING_FOR_CI should NOT produce a verdict."""
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test",
            state=ReviewState.WAITING_FOR_CI.value,
            current_head_sha="sha_ghi789",
        )

        with patch(
            "bid_euchre.ops.review_queue.shared_queue_root", return_value=tmp_path
        ):
            from review_driver import _write_verdict_if_applicable

            _write_verdict_if_applicable(loop)

        verdict = read_verdict(42, tmp_path)
        assert verdict is None

    def test_override_status_honored(self, tmp_path: Path) -> None:
        """override_status should replace the default mapping."""
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test",
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="sha_jkl012",
            stop_reason="Codex output unparseable (degraded pass)",
        )

        with patch(
            "bid_euchre.ops.review_queue.shared_queue_root", return_value=tmp_path
        ):
            from review_driver import _write_verdict_if_applicable

            _write_verdict_if_applicable(loop, override_status=STATUS_PASSED)

        verdict = read_verdict(42, tmp_path)
        assert verdict is not None
        assert verdict.status == STATUS_PASSED


# ---------------------------------------------------------------------------
# _step_ready_to_merge no longer calls enable_auto_merge
# ---------------------------------------------------------------------------


class TestStepReadyToMergeNoAutoMerge:
    """Verify _step_ready_to_merge does NOT call enable_auto_merge."""

    @patch("review_driver._publish_status")
    def test_no_enable_auto_merge_call(
        self, mock_publish: Mock, tmp_path: Path
    ) -> None:
        from review_state import ReviewLoopState, ReviewMode, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test",
            mode=ReviewMode.STANDARD.value,
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="sha_test",
        )

        from review_driver import _step_ready_to_merge

        with patch("review_driver.save_state"):
            result = _step_ready_to_merge(loop, tmp_path)

        # Should transition to MERGED (terminal) — no enable_auto_merge call
        assert result.current_state == ReviewState.MERGED
        # The publish_status should have been called with success
        mock_publish.assert_called_once()
        args = mock_publish.call_args[0]
        assert args[1] == "success"


# ---------------------------------------------------------------------------
# Bash guard integration test (H5)
# ---------------------------------------------------------------------------


class TestBashGuardIntegration:
    """Test the actual bash guard script to catch field-name mismatches."""

    def _guard_script(self) -> Path:
        return (
            Path(__file__).resolve().parents[2]
            / ".claude"
            / "hooks"
            / "pre-merge-review-guard.sh"
        )

    def _run_guard(self, command: str, env_override: dict | None = None) -> int:
        """Run the bash guard with a fake PreToolUse JSON on stdin.

        Returns the exit code.
        """
        import json
        import os
        import subprocess

        stdin_payload = json.dumps({"tool_input": {"command": command}})

        env = os.environ.copy()
        if env_override:
            env.update(env_override)

        result = subprocess.run(
            ["bash", str(self._guard_script())],
            input=stdin_payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        return result.returncode

    def test_blocks_when_no_verdict_file(self, tmp_path: Path) -> None:
        """Guard should block (exit 2) when verdict file is missing."""
        # Use BID_EUCHRE_REVIEW_QUEUE_DIR to point guard at empty tmp dir
        queue_dir = tmp_path / "empty_queue"
        queue_dir.mkdir()
        exit_code = self._run_guard(
            "gh pr merge 42 --squash",
            env_override={"BID_EUCHRE_REVIEW_QUEUE_DIR": str(queue_dir)},
        )
        assert exit_code == 2

    def test_blocks_when_verdict_status_not_passed(self, tmp_path: Path) -> None:
        """Guard should block when verdict status is 'blocked'."""
        queue_dir = tmp_path / "queue"
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc1234567890",
            status=STATUS_BLOCKED,
            reason="Blocking findings",
        )
        write_verdict(v, queue_dir, emit_event=False)

        exit_code = self._run_guard(
            "gh pr merge 42 --squash",
            env_override={"BID_EUCHRE_REVIEW_QUEUE_DIR": str(queue_dir)},
        )
        assert exit_code == 2

    def test_verdict_field_names_match_jq_queries(self, tmp_path: Path) -> None:
        """Verify write_verdict() field names match what the bash guard reads with jq.

        This is the key regression test: if ReviewVerdict.to_dict() changes
        field names, the guard's jq queries would silently return empty strings.
        """
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc1234567890",
            status=STATUS_PASSED,
            reason="clean review",
        )
        queue_dir = tmp_path / "queue"
        write_verdict(v, queue_dir, emit_event=False)

        # Read the verdict file and verify the jq-queried fields exist
        import json

        vfile = queue_dir / "pr_42" / "verdict.json"
        data = json.loads(vfile.read_text())

        # These are the exact field names the bash guard queries with jq
        assert "reviewed_sha" in data, "Guard queries .reviewed_sha"
        assert "status" in data, "Guard queries .status"
        assert "reason" in data, "Guard queries .reason"
        assert data["reviewed_sha"] == "abc1234567890"
        assert data["status"] == "passed"


# ---------------------------------------------------------------------------
# Cross-worktree merge guard tests
# ---------------------------------------------------------------------------


class TestCrossWorktreeMergeGuard:
    """Verify the merge guard uses the shared queue root.

    The guard resolves the queue root via Python's shared_queue_root(),
    which respects BID_EUCHRE_REVIEW_QUEUE_DIR. This simulates verdicts
    being written from one worktree and the guard running from another.
    """

    def test_guard_blocks_when_no_shared_verdict(self, tmp_path: Path) -> None:
        """Guard from worktree B should block when shared queue has no verdict."""
        shared_queue = tmp_path / "shared_queue"
        shared_queue.mkdir()

        # Pure-Python guard check against empty shared queue
        allowed, reason = _guard_check(42, "abc123", "success", shared_queue)
        assert allowed is False
        assert "No review verdict" in reason

    def test_guard_allows_with_shared_passed_verdict(self, tmp_path: Path) -> None:
        """Guard from worktree B should allow when worktree A wrote a passed verdict."""
        shared_queue = tmp_path / "shared_queue"
        sha = "abc1234567890"

        # Simulate worktree A writing a verdict to the shared queue
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha=sha,
            status=STATUS_PASSED,
            reason="Clean review from worktree A",
        )
        write_verdict(v, shared_queue, emit_event=False)

        # Simulate worktree B checking the guard against the same shared queue
        allowed, reason = _guard_check(42, sha, "success", shared_queue)
        assert allowed is True
        assert "Ready" in reason

    def test_guard_blocks_stale_shared_verdict(self, tmp_path: Path) -> None:
        """Guard should block when shared verdict SHA doesn't match current HEAD."""
        shared_queue = tmp_path / "shared_queue"

        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="old_sha_1234",
            status=STATUS_PASSED,
            reason="Clean",
        )
        write_verdict(v, shared_queue, emit_event=False)

        # Current HEAD is different — guard should block
        allowed, reason = _guard_check(42, "new_sha_5678", "success", shared_queue)
        assert allowed is False
        assert "Stale" in reason

    def test_write_from_worktree_a_read_from_worktree_b(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: write via shared_queue_root(), read via shared_queue_root()."""
        shared_dir = tmp_path / "shared"
        monkeypatch.setenv("BID_EUCHRE_REVIEW_QUEUE_DIR", str(shared_dir))

        sha = "sha_cross_wt"

        # "Worktree A" writes a verdict (no explicit queue_dir)
        v = ReviewVerdict(
            pr_number=77,
            reviewed_sha=sha,
            status=STATUS_PASSED,
            reason="Review from A",
        )
        write_verdict(v, emit_event=False)

        # "Worktree B" reads and checks (no explicit queue_dir)
        loaded = read_verdict(77)
        assert loaded is not None
        assert loaded.status == STATUS_PASSED
        assert loaded.reviewed_sha == sha

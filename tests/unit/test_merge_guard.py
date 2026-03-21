"""Tests for the pre-merge review guard and review_driver verdict writing.

Tests verdict writing at terminal states (via review_driver._write_verdict_if_applicable)
and the merge guard logic (verdict presence, SHA matching, status checks).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

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

        # Patch the write_verdict to use tmp_path
        with patch("bid_euchre.ops.review_queue.DEFAULT_QUEUE_DIR", tmp_path):
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

        with patch("bid_euchre.ops.review_queue.DEFAULT_QUEUE_DIR", tmp_path):
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

        with patch("bid_euchre.ops.review_queue.DEFAULT_QUEUE_DIR", tmp_path):
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

        with patch("bid_euchre.ops.review_queue.DEFAULT_QUEUE_DIR", tmp_path):
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

        # Should NOT have called enable_auto_merge (no import even happens)
        assert result.current_state == ReviewState.READY_TO_MERGE
        # The publish_status should have been called with success
        mock_publish.assert_called_once()
        args = mock_publish.call_args[0]
        assert args[1] == "success"

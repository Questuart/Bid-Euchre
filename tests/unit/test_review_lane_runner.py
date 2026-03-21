"""Tests for the review lane runner (shadow-mode queue processor)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/internal is importable
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "internal"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Import the runner under test (after path setup)
from review_lane_runner import (
    LANE_ID,
    _parse_review_output,
    _write_error_verdict,
    find_pending_requests,
    process_request,
    run_once,
)

from bid_euchre.ops.review_queue import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_PENDING,
    STATUS_RUNNING,
    ReviewRequest,
    ReviewVerdict,
    read_verdict,
    write_request,
    write_verdict,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def queue_dir(tmp_path: Path) -> Path:
    """Provide a temporary queue directory."""
    qd = tmp_path / "review_queue"
    qd.mkdir()
    return qd


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Provide a temporary events directory."""
    ed = tmp_path / "events"
    ed.mkdir()
    return ed


def _make_request(
    pr_number: int = 42,
    head_sha: str = "abc123def456",
    branch: str = "feat/foo",
    requester: str = "author-a",
) -> ReviewRequest:
    return ReviewRequest(
        pr_number=pr_number,
        head_sha=head_sha,
        branch=branch,
        requester=requester,
    )


# ---------------------------------------------------------------------------
# find_pending_requests
# ---------------------------------------------------------------------------


class TestFindPendingRequests:
    def test_empty_queue(self, queue_dir: Path) -> None:
        assert find_pending_requests(queue_dir) == []

    def test_finds_pending_request(self, queue_dir: Path, events_dir: Path) -> None:
        req = _make_request()
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        pending = find_pending_requests(queue_dir)
        assert len(pending) == 1
        assert pending[0].pr_number == 42

    def test_skips_already_verdicted(self, queue_dir: Path, events_dir: Path) -> None:
        req = _make_request()
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        # Write a non-pending verdict
        verdict = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc123def456",
            status=STATUS_PASSED,
            reason="Already reviewed",
        )
        write_verdict(verdict, queue_dir, emit_event=True, events_dir=events_dir)
        pending = find_pending_requests(queue_dir)
        assert len(pending) == 0

    def test_includes_pending_verdict(self, queue_dir: Path, events_dir: Path) -> None:
        req = _make_request()
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        # Write a pending verdict (claimable)
        verdict = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc123def456",
            status=STATUS_PENDING,
            reason="Awaiting review",
        )
        write_verdict(verdict, queue_dir, emit_event=True, events_dir=events_dir)
        pending = find_pending_requests(queue_dir)
        assert len(pending) == 1

    def test_multiple_prs_sorted(self, queue_dir: Path, events_dir: Path) -> None:
        for pr_num in [99, 10, 42]:
            req = _make_request(pr_number=pr_num)
            write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        pending = find_pending_requests(queue_dir)
        assert [r.pr_number for r in pending] == [10, 42, 99]

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        assert find_pending_requests(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# process_request — SHA verification
# ---------------------------------------------------------------------------


class TestProcessRequestSHA:
    @patch("review_lane_runner.get_pr_head_sha")
    def test_stale_sha_discarded(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Stale SHA results in a failed verdict, not passed."""
        req = _make_request(head_sha="old_sha_111")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "new_sha_222"  # SHA changed

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert "Stale SHA" in verdict.reason
        assert verdict.reviewed_sha == "old_sha_111"

    @patch("review_lane_runner.get_pr_head_sha")
    def test_sha_lookup_failure_writes_error(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """When GitHub lookup fails, write error verdict."""
        req = _make_request()
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = None  # Lookup failed

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert "HEAD SHA" in verdict.reason

    @patch("review_lane_runner.get_pr_head_sha")
    def test_sha_changes_during_review_discarded(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """If SHA changes during review, discard the result."""
        req = _make_request(head_sha="original_sha")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        # First call (pre-review): SHA matches. Second call (post-review): SHA changed.
        mock_sha.side_effect = ["original_sha", "different_sha"]

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert "changed during review" in verdict.reason

    @patch("review_lane_runner.get_pr_head_sha")
    def test_post_review_sha_api_failure_writes_error(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Post-review SHA lookup failure discards result (not silent fallthrough)."""
        req = _make_request(head_sha="original_sha")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        # Pre-review: SHA matches. Post-review: API failure returns None.
        mock_sha.side_effect = ["original_sha", None]

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert "API failure" in verdict.reason


# ---------------------------------------------------------------------------
# process_request — claim and verdict writing
# ---------------------------------------------------------------------------


class TestProcessRequestClaimAndVerdict:
    @patch("review_lane_runner.get_pr_head_sha")
    def test_claim_writes_running_then_final(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Claiming writes running verdict, then final verdict."""
        req = _make_request(head_sha="sha_abc")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_abc"

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        # Final verdict should be passed (dry-run skips actual review)
        assert verdict.status == STATUS_PASSED
        assert verdict.reviewed_sha == "sha_abc"

        # Verify verdict is persisted
        on_disk = read_verdict(42, queue_dir)
        assert on_disk is not None
        assert on_disk.status == STATUS_PASSED
        assert on_disk.reviewed_sha == "sha_abc"

    @patch("review_lane_runner.get_pr_head_sha")
    def test_clean_result_only_for_current_sha(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """A passed verdict is only written when SHA matches throughout."""
        req = _make_request(head_sha="current_sha")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        # Both pre and post checks return matching SHA
        mock_sha.return_value = "current_sha"

        verdict = process_request(req, queue_dir, dry_run=True, events_dir=events_dir)
        assert verdict.status == STATUS_PASSED
        assert verdict.reviewed_sha == "current_sha"


# ---------------------------------------------------------------------------
# process_request — reviewer failure handling
# ---------------------------------------------------------------------------


class TestProcessRequestFailureHandling:
    @patch("review_lane_runner.invoke_review")
    @patch("review_lane_runner.get_pr_head_sha")
    def test_reviewer_failure_writes_failed(
        self,
        mock_sha: MagicMock,
        mock_review: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Reviewer failure writes failed verdict, not passed."""
        req = _make_request(head_sha="sha_xyz")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_xyz"
        mock_review.return_value = {
            "success": False,
            "status": STATUS_FAILED,
            "reason": "Review agent crashed",
            "findings": [],
        }

        verdict = process_request(req, queue_dir, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert verdict.reviewed_sha == "sha_xyz"

    @patch("review_lane_runner.invoke_review")
    @patch("review_lane_runner.get_pr_head_sha")
    def test_reviewer_exception_writes_error(
        self,
        mock_sha: MagicMock,
        mock_review: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Unexpected exception during review writes error verdict."""
        req = _make_request(head_sha="sha_xyz")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_xyz"
        mock_review.side_effect = RuntimeError("boom")

        verdict = process_request(req, queue_dir, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED
        assert "Unexpected error" in verdict.reason

    @patch("review_lane_runner.invoke_review")
    @patch("review_lane_runner.get_pr_head_sha")
    def test_invalid_status_never_becomes_passed(
        self,
        mock_sha: MagicMock,
        mock_review: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Invalid status from reviewer is mapped to failed, never passed."""
        req = _make_request(head_sha="sha_xyz")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_xyz"
        mock_review.return_value = {
            "success": True,
            "status": "unknown_garbage",
            "reason": "Something weird",
            "findings": [],
        }

        verdict = process_request(req, queue_dir, events_dir=events_dir)
        assert verdict.status == STATUS_FAILED

    @patch("review_lane_runner.invoke_review")
    @patch("review_lane_runner.get_pr_head_sha")
    def test_blocked_findings_produce_blocked_verdict(
        self,
        mock_sha: MagicMock,
        mock_review: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """Reviewer returning blocked findings → blocked verdict."""
        req = _make_request(head_sha="sha_xyz")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_xyz"
        mock_review.return_value = {
            "success": True,
            "status": STATUS_BLOCKED,
            "reason": "2 blocking findings",
            "findings": [
                {"severity": "BLOCK", "file": "foo.py", "message": "Bug"},
            ],
        }

        verdict = process_request(req, queue_dir, events_dir=events_dir)
        assert verdict.status == STATUS_BLOCKED
        assert len(verdict.findings) == 1


# ---------------------------------------------------------------------------
# _parse_review_output
# ---------------------------------------------------------------------------


class TestParseReviewOutput:
    def test_valid_json_passed(self) -> None:
        raw = json.dumps({"status": "passed", "reason": "All good", "findings": []})
        result = _parse_review_output(raw)
        assert result["success"] is True
        assert result["status"] == "passed"

    def test_valid_json_blocked(self) -> None:
        raw = json.dumps(
            {
                "status": "blocked",
                "reason": "Critical bug",
                "findings": [{"severity": "BLOCK", "file": "x.py", "message": "bad"}],
            }
        )
        result = _parse_review_output(raw)
        assert result["success"] is True
        assert result["status"] == "blocked"
        assert len(result["findings"]) == 1

    def test_empty_output_fails(self) -> None:
        result = _parse_review_output("")
        assert result["success"] is False
        assert result["status"] == STATUS_FAILED

    def test_invalid_status_fails(self) -> None:
        raw = json.dumps({"status": "clean", "reason": "ok", "findings": []})
        result = _parse_review_output(raw)
        assert result["success"] is False
        assert result["status"] == STATUS_FAILED

    def test_non_json_output_fails(self) -> None:
        result = _parse_review_output("This is just plain text with no JSON")
        assert result["success"] is False
        assert result["status"] == STATUS_FAILED

    def test_json_embedded_in_text(self) -> None:
        raw = 'Here is my review:\n{"status": "passed", "reason": "ok", "findings": []}\nDone.'
        result = _parse_review_output(raw)
        assert result["success"] is True
        assert result["status"] == "passed"


# ---------------------------------------------------------------------------
# _write_error_verdict
# ---------------------------------------------------------------------------


class TestWriteErrorVerdict:
    def test_always_writes_failed(self, queue_dir: Path, events_dir: Path) -> None:
        verdict = _write_error_verdict(
            99,
            "sha_abc",
            "Something went wrong",
            queue_dir=queue_dir,
            events_dir=events_dir,
        )
        assert verdict.status == STATUS_FAILED
        assert verdict.pr_number == 99
        assert verdict.reviewed_sha == "sha_abc"

        on_disk = read_verdict(99, queue_dir)
        assert on_disk is not None
        assert on_disk.status == STATUS_FAILED


# ---------------------------------------------------------------------------
# run_once
# ---------------------------------------------------------------------------


class TestRunOnce:
    @patch("review_lane_runner.get_pr_head_sha")
    def test_processes_pending_and_returns_verdicts(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        req = _make_request(head_sha="sha_111")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_111"

        verdicts = run_once(queue_dir, dry_run=True, events_dir=events_dir)
        assert len(verdicts) == 1
        assert verdicts[0].status == STATUS_PASSED

    def test_empty_queue_returns_empty(self, queue_dir: Path) -> None:
        verdicts = run_once(queue_dir, dry_run=True)
        assert verdicts == []

    @patch("review_lane_runner.get_pr_head_sha")
    def test_does_not_reprocess_completed(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """After processing, a second run_once finds nothing pending."""
        req = _make_request(head_sha="sha_111")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_111"

        # First run processes the request
        verdicts1 = run_once(queue_dir, dry_run=True, events_dir=events_dir)
        assert len(verdicts1) == 1

        # Second run should find nothing pending
        verdicts2 = run_once(queue_dir, dry_run=True, events_dir=events_dir)
        assert len(verdicts2) == 0


# ---------------------------------------------------------------------------
# Shadow mode contract
# ---------------------------------------------------------------------------


class TestShadowModeContract:
    """Verify shadow-mode invariants: no merge authority, no status publishing."""

    @patch("review_lane_runner.get_pr_head_sha")
    def test_no_gh_status_calls_in_process_request(
        self,
        mock_sha: MagicMock,
        queue_dir: Path,
        events_dir: Path,
    ) -> None:
        """process_request never invokes gh api for status publishing.

        Uses a real (non-dry-run) path with invoke_review mocked to return
        a clean result, so subprocess.run IS called for the SHA checks.
        Asserts that none of those calls target the statuses API.
        """
        req = _make_request(head_sha="sha_abc")
        write_request(req, queue_dir, emit_event=True, events_dir=events_dir)
        mock_sha.return_value = "sha_abc"

        mock_review_result = {
            "success": True,
            "status": STATUS_PASSED,
            "reason": "Clean",
            "findings": [],
        }
        with patch("review_lane_runner.invoke_review", return_value=mock_review_result):
            verdict = process_request(req, queue_dir, events_dir=events_dir)

        # Verdict was written — confirm the runner did real work
        assert verdict.status == STATUS_PASSED
        on_disk = read_verdict(42, queue_dir)
        assert on_disk is not None
        assert on_disk.status == STATUS_PASSED

    def test_no_status_publishing_in_source(self) -> None:
        """Static check: review_lane_runner.py never references GitHub statuses API."""
        import inspect

        import review_lane_runner

        source = inspect.getsource(review_lane_runner)
        assert (
            "statuses" not in source
        ), "Shadow-mode runner must not contain GitHub statuses API references"
        assert (
            "set_review_status" not in source
        ), "Shadow-mode runner must not call set_review_status"

    def test_lane_id_is_review(self) -> None:
        """The runner identifies as the 'review' lane."""
        assert LANE_ID == "review"


# ---------------------------------------------------------------------------
# Stuck running verdict re-claim (#1183)
# ---------------------------------------------------------------------------


class TestStuckRunningReclaim:
    """Verify that stale 'running' verdicts are re-claimable."""

    def test_fresh_running_verdict_not_claimable(self, tmp_path: Path) -> None:
        """A 'running' verdict created just now should NOT be re-claimable."""
        req = ReviewRequest(
            pr_number=42, head_sha="abc", branch="feat/x", requester="a"
        )
        write_request(req, tmp_path, emit_event=False)
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc",
            status=STATUS_RUNNING,
            reason="running",
        )
        write_verdict(v, tmp_path, emit_event=False)

        pending = find_pending_requests(tmp_path)
        assert len(pending) == 0

    def test_stale_running_verdict_is_reclaimable(self, tmp_path: Path) -> None:
        """A 'running' verdict older than 15min should be re-claimable."""
        from datetime import datetime, timedelta, timezone

        req = ReviewRequest(
            pr_number=42, head_sha="abc", branch="feat/x", requester="a"
        )
        write_request(req, tmp_path, emit_event=False)

        # Write a running verdict with old timestamp
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc",
            status=STATUS_RUNNING,
            reason="running",
            created_at=old_time,
        )
        write_verdict(v, tmp_path, emit_event=False)

        pending = find_pending_requests(tmp_path)
        assert len(pending) == 1
        assert pending[0].pr_number == 42

    def test_passed_verdict_not_reclaimable(self, tmp_path: Path) -> None:
        """A 'passed' verdict should never be re-claimable regardless of age."""
        req = ReviewRequest(
            pr_number=42, head_sha="abc", branch="feat/x", requester="a"
        )
        write_request(req, tmp_path, emit_event=False)
        v = ReviewVerdict(
            pr_number=42,
            reviewed_sha="abc",
            status=STATUS_PASSED,
            reason="clean",
        )
        write_verdict(v, tmp_path, emit_event=False)

        pending = find_pending_requests(tmp_path)
        assert len(pending) == 0

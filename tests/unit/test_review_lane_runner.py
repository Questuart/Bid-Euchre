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
    _check_worktree_health,
    _cleanup_stale_locks,
    _parse_review_output,
    _write_error_verdict,
    find_pending_requests,
    preflight_health_check,
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

    def test_none_queue_dir_delegates_to_shared_queue_root(
        self, queue_dir: Path, events_dir: Path
    ) -> None:
        """When queue_dir is None, find_pending_requests uses shared_queue_root().

        Regression test for #1196: the runner previously fell back to the
        relative DEFAULT_QUEUE_DIR, which is invisible in linked worktrees.
        """
        req = _make_request(pr_number=55)
        write_request(req, queue_dir, emit_event=False, events_dir=events_dir)

        with patch(
            "review_lane_runner.shared_queue_root", return_value=queue_dir
        ) as mock_sqr:
            pending = find_pending_requests(None)
            mock_sqr.assert_called_once()
        assert len(pending) == 1
        assert pending[0].pr_number == 55


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


# ---------------------------------------------------------------------------
# Pre-flight health checks (#2075)
# ---------------------------------------------------------------------------


class TestCheckWorktreeHealth:
    """Tests for _check_worktree_health()."""

    @patch("review_lane_runner.subprocess.run")
    def test_healthy_worktree_on_branch(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Normal branch (not detached) with no commits behind."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch origin main
            MagicMock(returncode=0),
            # rev-list count behind
            MagicMock(returncode=0, stdout="0\n"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is True
        assert "healthy" in msg.lower() or "up to date" in msg.lower()

    @patch("review_lane_runner.subprocess.run")
    def test_detached_head_recovers(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Detached HEAD with successful checkout main recovery."""
        mock_run.side_effect = [
            # symbolic-ref → detached HEAD
            MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: ref HEAD is not a symbolic ref",
            ),
            # checkout main → success
            MagicMock(returncode=0),
            # fetch origin main
            MagicMock(returncode=0),
            # rev-list count
            MagicMock(returncode=0, stdout="0\n"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is True

    @patch("review_lane_runner.subprocess.run")
    def test_detached_head_checkout_fails(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Detached HEAD with failed checkout reports unhealthy."""
        mock_run.side_effect = [
            # symbolic-ref → detached HEAD
            MagicMock(returncode=128, stdout="", stderr="fatal"),
            # checkout main → fail
            MagicMock(returncode=1, stderr="error: pathspec 'main' not found"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is False
        assert "detached" in msg.lower() or "checkout" in msg.lower()

    @patch("review_lane_runner.subprocess.run")
    def test_behind_main_pulls(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Worktree behind main triggers a pull."""
        mock_run.side_effect = [
            # symbolic-ref
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 5 behind
            MagicMock(returncode=0, stdout="5\n"),
            # pull --ff-only → success
            MagicMock(returncode=0),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is True

    @patch("review_lane_runner.subprocess.run")
    def test_pull_fails_clean_tree_resets(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """When ff-only pull fails and tree is clean, reset --hard succeeds."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 3 behind
            MagicMock(returncode=0, stdout="3\n"),
            # pull --ff-only → fails (diverged)
            MagicMock(returncode=1, stderr="fatal: Not possible to fast-forward"),
            # git status --porcelain → clean
            MagicMock(returncode=0, stdout=""),
            # git reset --hard → success
            MagicMock(returncode=0),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is True

    @patch("review_lane_runner.subprocess.run")
    def test_pull_fails_dirty_tree_refuses_reset(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """When ff-only pull fails and tree is dirty, refuse to reset (#2181)."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 2 behind
            MagicMock(returncode=0, stdout="2\n"),
            # pull --ff-only → fails
            MagicMock(returncode=1, stderr="fatal: Not possible to fast-forward"),
            # git status --porcelain → dirty
            MagicMock(returncode=0, stdout=" M some_file.py\n"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is False
        assert "uncommitted" in msg.lower()

    @patch("review_lane_runner.subprocess.run")
    def test_pull_fails_untracked_only_allows_reset(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Untracked files (??) should not block reset — they survive it (#2195)."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 1 behind
            MagicMock(returncode=0, stdout="1\n"),
            # pull --ff-only → fails
            MagicMock(returncode=1, stderr="fatal: Not possible to fast-forward"),
            # git status --porcelain → only untracked files
            MagicMock(returncode=0, stdout="?? new_file.py\n?? another.txt\n"),
            # git reset --hard → succeeds
            MagicMock(returncode=0),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is True

    @patch("review_lane_runner.subprocess.run")
    def test_pull_fails_mixed_dirty_and_untracked_refuses_reset(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Mixed modified + untracked should still block reset (#2195)."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 1 behind
            MagicMock(returncode=0, stdout="1\n"),
            # pull --ff-only → fails
            MagicMock(returncode=1, stderr="fatal: Not possible to fast-forward"),
            # git status --porcelain → modified + untracked
            MagicMock(returncode=0, stdout="?? new_file.py\n M dirty.py\n"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is False
        assert "uncommitted" in msg.lower()

    @patch("review_lane_runner.subprocess.run")
    def test_pull_fails_reset_fails(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """When ff-only pull fails and reset also fails, report error."""
        mock_run.side_effect = [
            # symbolic-ref → on a branch
            MagicMock(returncode=0, stdout="main\n"),
            # fetch
            MagicMock(returncode=0),
            # rev-list count → 1 behind
            MagicMock(returncode=0, stdout="1\n"),
            # pull --ff-only → fails
            MagicMock(returncode=1, stderr="fatal: Not possible to fast-forward"),
            # git status --porcelain → clean
            MagicMock(returncode=0, stdout=""),
            # git reset --hard → fails
            MagicMock(returncode=1, stderr="error: could not reset"),
        ]
        healthy, msg = _check_worktree_health(tmp_path)
        assert healthy is False
        assert "could not sync" in msg.lower() or "reset" in msg.lower()


class TestCleanupStaleLocks:
    """Tests for _cleanup_stale_locks()."""

    def test_no_lock_files(self, tmp_path: Path) -> None:
        removed = _cleanup_stale_locks(tmp_path)
        assert removed == 0

    def test_stale_lock_removed(self, tmp_path: Path) -> None:
        """Lock file older than threshold is removed."""
        import os

        lock_dir = tmp_path / ".claude"
        lock_dir.mkdir()
        lock_path = lock_dir / "scheduled_tasks.lock"
        lock_path.touch()
        # Age the file to be clearly stale
        old_time = os.path.getmtime(str(lock_path)) - 600
        os.utime(str(lock_path), (old_time, old_time))

        removed = _cleanup_stale_locks(tmp_path)
        assert removed == 1
        assert not lock_path.exists()

    def test_fresh_lock_kept(self, tmp_path: Path) -> None:
        """Lock file newer than threshold is preserved."""
        lock_dir = tmp_path / ".claude"
        lock_dir.mkdir()
        lock_path = lock_dir / "scheduled_tasks.lock"
        lock_path.touch()
        # File is just created — should be fresh

        removed = _cleanup_stale_locks(tmp_path)
        assert removed == 0
        assert lock_path.exists()


class TestPreflightHealthCheck:
    """Tests for preflight_health_check()."""

    @patch("review_lane_runner._check_codex_auth")
    @patch("review_lane_runner._check_worktree_health")
    def test_all_checks_pass(
        self,
        mock_wt: MagicMock,
        mock_auth: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_wt.return_value = (True, "Worktree healthy and up to date")
        mock_auth.return_value = (True, "Logged in")

        results = preflight_health_check(tmp_path)
        assert len(results) == 3  # worktree, locks, auth
        assert all(passed for _, passed, _ in results)

    @patch("review_lane_runner._check_codex_auth")
    @patch("review_lane_runner._check_worktree_health")
    def test_auth_failure_is_non_fatal(
        self,
        mock_wt: MagicMock,
        mock_auth: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Auth failure is logged but doesn't block processing."""
        mock_wt.return_value = (True, "OK")
        mock_auth.return_value = (False, "Not logged in")

        results = preflight_health_check(tmp_path)
        auth_results = [r for r in results if r[0] == "codex_auth"]
        assert len(auth_results) == 1
        assert auth_results[0][1] is False

    @patch("review_lane_runner._check_worktree_health")
    def test_skip_auth(
        self,
        mock_wt: MagicMock,
        tmp_path: Path,
    ) -> None:
        """skip_auth=True omits the Codex auth check."""
        mock_wt.return_value = (True, "OK")

        results = preflight_health_check(tmp_path, skip_auth=True)
        check_names = {name for name, _, _ in results}
        assert "codex_auth" not in check_names


class TestRunOnceWithPreflight:
    """Verify run_once integrates pre-flight checks."""

    @patch("review_lane_runner.preflight_health_check")
    def test_run_once_calls_preflight(
        self,
        mock_preflight: MagicMock,
        queue_dir: Path,
    ) -> None:
        """run_once calls preflight_health_check by default."""
        mock_preflight.return_value = [
            ("worktree_health", True, "OK"),
            ("lock_cleanup", True, "0 locks"),
            ("codex_auth", True, "OK"),
        ]
        run_once(queue_dir, dry_run=True)
        mock_preflight.assert_called_once()

    @patch("review_lane_runner.preflight_health_check")
    def test_run_once_skips_preflight(
        self,
        mock_preflight: MagicMock,
        queue_dir: Path,
    ) -> None:
        """run_once with skip_preflight=True does not call preflight."""
        run_once(queue_dir, dry_run=True, skip_preflight=True)
        mock_preflight.assert_not_called()


class TestInvokeReviewPermissionModeByModelTier:
    """Tests for model-tier-aware permission-mode selection on ``invoke_review`` (#2767).

    ``invoke_review`` spawns ``claude`` as a subprocess. The launch flag must be
    a function of the review lane's model tier, NOT a fleet-wide constant:

    * ``opus`` →  argv contains ``--permission-mode auto`` (classifier-gated).
    * ``sonnet`` / ``haiku`` → argv contains ``--dangerously-skip-permissions``
      (explicit reduced safety envelope).

    Passing ``--permission-mode auto`` to a non-Opus session silently falls
    back to ``bypassPermissions`` with no enforcement legibility — the
    failure mode documented in #2767 and ``.claude/rules/80_permission_model.md``
    § "Model-tier activation constraint".

    These tests mock ``subprocess.run`` to inspect the argument list, and
    patch ``permission_mode_args_for_lane`` (or the underlying
    ``load_lane_models`` loader via a tmp-path config) to simulate each tier.
    """

    @staticmethod
    def _mock_subprocess_ok(mock_run: MagicMock) -> None:
        """Make subprocess.run return a successful JSON payload."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"status": "passed", "reason": "clean", "findings": []}),
            stderr="",
        )

    @patch("review_lane_runner.permission_mode_args_for_lane")
    @patch("review_lane_runner.subprocess.run")
    def test_opus_lane_emits_permission_mode_auto(
        self, mock_run: MagicMock, mock_perm: MagicMock
    ) -> None:
        """Opus tier → argv includes ``--permission-mode auto``."""
        import review_lane_runner

        self._mock_subprocess_ok(mock_run)
        mock_perm.return_value = ["--permission-mode", "auto"]

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        assert mock_perm.called, "invoke_review must call permission_mode_args_for_lane"
        # Helper must be called with the review lane id.
        perm_args, _ = mock_perm.call_args
        assert perm_args[0] == "review", (
            "permission_mode_args_for_lane must be called with LANE_ID='review', "
            f"got {perm_args[0]!r}"
        )

        assert mock_run.called, "invoke_review must call subprocess.run"
        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert isinstance(argv, list), "subprocess.run must be called with an argv list"
        assert argv[0] == "claude", f"First arg must be 'claude', got {argv[0]!r}"

        assert "--permission-mode" in argv, (
            "Opus-tier argv must include '--permission-mode' " f"(got {argv})"
        )
        idx = argv.index("--permission-mode")
        assert idx + 1 < len(argv), "--permission-mode must be followed by a value"
        assert argv[idx + 1] == "auto", (
            f"Opus-tier --permission-mode must be followed by 'auto' "
            f"(got {argv[idx + 1]!r})"
        )
        assert "--dangerously-skip-permissions" not in argv, (
            "Opus-tier argv must NOT include --dangerously-skip-permissions "
            f"(got {argv})"
        )

    @patch("review_lane_runner.permission_mode_args_for_lane")
    @patch("review_lane_runner.subprocess.run")
    def test_sonnet_lane_emits_dangerously_skip_permissions(
        self, mock_run: MagicMock, mock_perm: MagicMock
    ) -> None:
        """Sonnet tier → argv includes ``--dangerously-skip-permissions``."""
        import review_lane_runner

        self._mock_subprocess_ok(mock_run)
        mock_perm.return_value = ["--dangerously-skip-permissions"]

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert "--dangerously-skip-permissions" in argv, (
            "Sonnet-tier argv must include '--dangerously-skip-permissions' "
            f"(got {argv})"
        )
        assert "--permission-mode" not in argv, (
            "Sonnet-tier argv must NOT include '--permission-mode' — "
            "cross-wiring flags silently falls back to bypassPermissions "
            f"(got {argv})"
        )
        assert "auto" not in argv, (
            "Sonnet-tier argv must NOT include the 'auto' token " f"(got {argv})"
        )

    @patch("review_lane_runner.permission_mode_args_for_lane")
    @patch("review_lane_runner.subprocess.run")
    def test_haiku_lane_emits_dangerously_skip_permissions(
        self, mock_run: MagicMock, mock_perm: MagicMock
    ) -> None:
        """Haiku tier → argv includes ``--dangerously-skip-permissions``."""
        import review_lane_runner

        self._mock_subprocess_ok(mock_run)
        mock_perm.return_value = ["--dangerously-skip-permissions"]

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert "--dangerously-skip-permissions" in argv, (
            "Haiku-tier argv must include '--dangerously-skip-permissions' "
            f"(got {argv})"
        )
        assert "--permission-mode" not in argv, (
            "Haiku-tier argv must NOT include '--permission-mode' " f"(got {argv})"
        )

    @patch("review_lane_runner.permission_mode_args_for_lane")
    @patch("review_lane_runner.subprocess.run")
    def test_existing_flags_preserved_on_opus(
        self, mock_run: MagicMock, mock_perm: MagicMock
    ) -> None:
        """Model-tier conditioning must not drop --agent, --print, -p, --output-format."""
        import review_lane_runner

        self._mock_subprocess_ok(mock_run)
        mock_perm.return_value = ["--permission-mode", "auto"]

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert (
            "--agent" in argv and "steward-review" in argv
        ), f"--agent steward-review must be preserved: {argv}"
        assert "--print" in argv, f"--print must be preserved: {argv}"
        assert "-p" in argv, f"-p prompt flag must be preserved: {argv}"
        assert (
            "--output-format" in argv and "json" in argv
        ), f"--output-format json must be preserved: {argv}"

    @patch("review_lane_runner.permission_mode_args_for_lane")
    @patch("review_lane_runner.subprocess.run")
    def test_existing_flags_preserved_on_sonnet(
        self, mock_run: MagicMock, mock_perm: MagicMock
    ) -> None:
        """Sonnet-tier path must not drop --agent, --print, -p, --output-format."""
        import review_lane_runner

        self._mock_subprocess_ok(mock_run)
        mock_perm.return_value = ["--dangerously-skip-permissions"]

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert (
            "--agent" in argv and "steward-review" in argv
        ), f"--agent steward-review must be preserved: {argv}"
        assert "--print" in argv, f"--print must be preserved: {argv}"
        assert "-p" in argv, f"-p prompt flag must be preserved: {argv}"
        assert (
            "--output-format" in argv and "json" in argv
        ), f"--output-format json must be preserved: {argv}"

    @patch("review_lane_runner.subprocess.run")
    def test_integration_with_real_loader_opus_config(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: real loader + explicit opus config → argv has '--permission-mode auto'.

        Uses the real ``permission_mode_args_for_lane`` function against a
        tmp-path config file to ensure the wiring from lane_models.json through
        the review runner emits the correct argv for an Opus-tier lane.
        """
        import lane_models
        import review_lane_runner

        # Build a minimal config where "review" is explicitly opus.
        cfg_path = tmp_path / "lane_models.json"
        cfg_path.write_text(
            json.dumps({"_schema_version": 1, "lanes": {"review": {"model": "opus"}}})
        )

        # Monkeypatch the module-level import in review_lane_runner to route
        # through a lambda that uses our tmp config.
        monkeypatch.setattr(
            review_lane_runner,
            "permission_mode_args_for_lane",
            lambda lane_id: lane_models.permission_mode_args_for_lane(
                lane_id, config_path=cfg_path
            ),
        )

        self._mock_subprocess_ok(mock_run)

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert (
            "--permission-mode" in argv
        ), f"Real loader + opus config must emit --permission-mode: {argv}"
        idx = argv.index("--permission-mode")
        assert (
            argv[idx + 1] == "auto"
        ), f"Real loader + opus config must emit 'auto': {argv[idx + 1]!r}"

    @patch("review_lane_runner.subprocess.run")
    def test_integration_with_real_loader_sonnet_config(
        self, mock_run: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: real loader + sonnet config → argv has '--dangerously-skip-permissions'.

        Guard against the silent-fallback footgun: if the loader routed a
        sonnet lane to ``--permission-mode auto``, the lane would launch with
        ``bypassPermissions`` and lose classifier enforcement (#2767).
        """
        import lane_models
        import review_lane_runner

        cfg_path = tmp_path / "lane_models.json"
        cfg_path.write_text(
            json.dumps({"_schema_version": 1, "lanes": {"review": {"model": "sonnet"}}})
        )

        monkeypatch.setattr(
            review_lane_runner,
            "permission_mode_args_for_lane",
            lambda lane_id: lane_models.permission_mode_args_for_lane(
                lane_id, config_path=cfg_path
            ),
        )

        self._mock_subprocess_ok(mock_run)

        review_lane_runner.invoke_review(
            pr_number=42, branch="feat/foo", head_sha="abc123"
        )

        call_args, _ = mock_run.call_args
        argv = call_args[0]
        assert (
            "--dangerously-skip-permissions" in argv
        ), f"Real loader + sonnet config must emit --dangerously-skip-permissions: {argv}"
        assert "--permission-mode" not in argv, (
            "Real loader + sonnet config must NOT cross-wire '--permission-mode' "
            f"(silent-fallback footgun): {argv}"
        )

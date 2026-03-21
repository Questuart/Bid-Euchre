"""Tests for ops/reviews.py — provider-neutral PR review outcome aggregation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.ops.reviews import (
    DEFAULT_REVIEW_CONTEXTS,
    TRUSTED_BOT_LOGINS,
    CommentOverlay,
    ReviewOutcome,
    _classify_ci_status,
    _get_advisory_status,
    _get_review_status,
    _has_precheck_ci,
    classify_comment_author,
    emit_review_event,
    format_comment_overlays_json,
    format_comment_overlays_text,
    format_reviews_json,
    format_reviews_text,
    get_open_pr_reviews,
    get_pr_comment_overlay,
    get_pr_review_detail,
)

# --- Helper to create mock subprocess results ---


def _mock_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> object:
    """Create a mock subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# --- Unit tests for classification helpers ---


class TestClassifyCIStatus:
    """Tests for _classify_ci_status()."""

    def test_empty_checks_returns_pending(self) -> None:
        assert _classify_ci_status([]) == "pending"

    def test_all_success(self) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "lint", "state": "SUCCESS"},
        ]
        assert _classify_ci_status(checks) == "success"

    def test_any_failure(self) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "lint", "state": "FAILURE"},
        ]
        assert _classify_ci_status(checks) == "failure"

    def test_any_pending(self) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "build", "state": "PENDING"},
        ]
        assert _classify_ci_status(checks) == "pending"

    def test_in_progress_counts_as_pending(self) -> None:
        checks = [{"name": "tests", "state": "IN_PROGRESS"}]
        assert _classify_ci_status(checks) == "pending"

    def test_excludes_reviewing_changes(self) -> None:
        checks = [
            {"name": "reviewing-changes", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        assert _classify_ci_status(checks) == "success"

    def test_only_reviewing_changes_returns_pending(self) -> None:
        checks = [{"name": "reviewing-changes", "state": "SUCCESS"}]
        assert _classify_ci_status(checks) == "pending"

    def test_unknown_state(self) -> None:
        checks = [{"name": "tests", "state": "CANCELLED"}]
        assert _classify_ci_status(checks) == "unknown"


class TestGetReviewStatus:
    """Tests for _get_review_status()."""

    def test_success(self) -> None:
        checks = [{"name": "reviewing-changes", "state": "SUCCESS"}]
        assert _get_review_status(checks) == "success"

    def test_failure(self) -> None:
        checks = [{"name": "reviewing-changes", "state": "FAILURE"}]
        assert _get_review_status(checks) == "failure"

    def test_pending(self) -> None:
        checks = [{"name": "reviewing-changes", "state": "PENDING"}]
        assert _get_review_status(checks) == "pending"

    def test_in_progress_maps_to_pending(self) -> None:
        checks = [{"name": "reviewing-changes", "state": "IN_PROGRESS"}]
        assert _get_review_status(checks) == "pending"

    def test_no_reviewing_changes_returns_none(self) -> None:
        checks = [{"name": "tests", "state": "SUCCESS"}]
        assert _get_review_status(checks) == "none"

    def test_empty_checks(self) -> None:
        assert _get_review_status([]) == "none"

    def test_custom_review_context(self) -> None:
        """Custom review context is recognized when passed."""
        checks = [{"name": "codex-review", "state": "SUCCESS"}]
        assert (
            _get_review_status(checks, review_contexts=("codex-review",)) == "success"
        )

    def test_custom_context_excludes_default(self) -> None:
        """Custom contexts don't include defaults unless explicitly listed."""
        checks = [{"name": "reviewing-changes", "state": "SUCCESS"}]
        assert _get_review_status(checks, review_contexts=("codex-review",)) == "none"

    def test_default_contexts_constant(self) -> None:
        """DEFAULT_REVIEW_CONTEXTS includes reviewing-changes."""
        assert "reviewing-changes" in DEFAULT_REVIEW_CONTEXTS

    def test_multiple_contexts_all_success(self) -> None:
        """Multiple review providers all passing → success (#920)."""
        checks = [
            {"name": "reviewing-changes", "state": "SUCCESS"},
            {"name": "codex-review", "state": "SUCCESS"},
        ]
        assert (
            _get_review_status(
                checks, review_contexts=("reviewing-changes", "codex-review")
            )
            == "success"
        )

    def test_multiple_contexts_one_failure(self) -> None:
        """One review provider failing → failure, even if another passes (#920)."""
        checks = [
            {"name": "reviewing-changes", "state": "SUCCESS"},
            {"name": "codex-review", "state": "FAILURE"},
        ]
        assert (
            _get_review_status(
                checks, review_contexts=("reviewing-changes", "codex-review")
            )
            == "failure"
        )

    def test_multiple_contexts_one_pending(self) -> None:
        """One review provider pending → pending (#920)."""
        checks = [
            {"name": "reviewing-changes", "state": "SUCCESS"},
            {"name": "codex-review", "state": "PENDING"},
        ]
        assert (
            _get_review_status(
                checks, review_contexts=("reviewing-changes", "codex-review")
            )
            == "pending"
        )


class TestClassifyCIStatusDefaultExcludesAdvisory:
    """Tests for _classify_ci_status() default excluding advisory checks."""

    def test_default_excludes_claude_review(self) -> None:
        """Default (None) excludes claude-review from CI status."""
        checks = [
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        assert _classify_ci_status(checks) == "success"

    def test_default_excludes_reviewing_changes(self) -> None:
        """Default (None) still excludes reviewing-changes."""
        checks = [
            {"name": "reviewing-changes", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        assert _classify_ci_status(checks) == "success"

    def test_default_excludes_both(self) -> None:
        """Default (None) excludes both review gate and advisory."""
        checks = [
            {"name": "reviewing-changes", "state": "FAILURE"},
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        assert _classify_ci_status(checks) == "success"

    def test_explicit_override_uses_old_logic(self) -> None:
        """Explicit review_contexts uses the override, not classify_check."""
        checks = [
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        # With explicit override that does NOT include claude-review,
        # it should count as CI and cause failure.
        assert (
            _classify_ci_status(checks, review_contexts=("reviewing-changes",))
            == "failure"
        )


class TestClassifyCIStatusCustomContexts:
    """Tests for _classify_ci_status() with custom review contexts."""

    def test_custom_review_context_excluded_from_ci(self) -> None:
        checks = [
            {"name": "codex-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        # codex-review is a review context, not CI — should be excluded
        assert (
            _classify_ci_status(checks, review_contexts=("codex-review",)) == "success"
        )


class TestHasPrecheckCI:
    """Tests for _has_precheck_ci()."""

    def test_has_deterministic_prechecks(self) -> None:
        checks = [{"name": "deterministic-prechecks", "state": "SUCCESS"}]
        assert _has_precheck_ci(checks) is True

    def test_has_precheck_variant(self) -> None:
        checks = [{"name": "Precheck Suite", "state": "SUCCESS"}]
        assert _has_precheck_ci(checks) is True

    def test_no_precheck(self) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "lint", "state": "SUCCESS"},
        ]
        assert _has_precheck_ci(checks) is False

    def test_empty_checks(self) -> None:
        assert _has_precheck_ci([]) is False


class TestGetAdvisoryStatus:
    """Tests for _get_advisory_status()."""

    def test_claude_review_success(self) -> None:
        checks = [{"name": "claude-review", "state": "SUCCESS"}]
        assert _get_advisory_status(checks) == "success"

    def test_claude_review_failure(self) -> None:
        checks = [{"name": "claude-review", "state": "FAILURE"}]
        assert _get_advisory_status(checks) == "failure"

    def test_claude_review_pending(self) -> None:
        checks = [{"name": "claude-review", "state": "PENDING"}]
        assert _get_advisory_status(checks) == "pending"

    def test_no_advisory_checks_returns_none(self) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "reviewing-changes", "state": "SUCCESS"},
        ]
        assert _get_advisory_status(checks) == "none"

    def test_empty_checks(self) -> None:
        assert _get_advisory_status([]) == "none"


# --- Integration tests with mocked gh ---


class TestGetOpenPRReviews:
    """Tests for get_open_pr_reviews() with mocked gh CLI."""

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_no_open_prs(self, mock_gh: object) -> None:
        mock_gh.return_value = _mock_result(stdout="[]")
        outcomes = get_open_pr_reviews()
        assert outcomes == []

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_single_pr_all_green(self, mock_gh: object) -> None:
        pr_list = [
            {
                "number": 100,
                "title": "Fix bug",
                "headRefName": "fix/bug",
                "url": "https://github.com/org/repo/pull/100",
            }
        ]
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "lint", "state": "SUCCESS"},
            {"name": "reviewing-changes", "state": "SUCCESS"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 1
        assert outcomes[0].pr_number == 100
        assert outcomes[0].ci_status == "success"
        assert outcomes[0].review_status == "success"
        assert outcomes[0].has_precheck_ci is False

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_multiple_prs_sorted(self, mock_gh: object) -> None:
        pr_list = [
            {
                "number": 200,
                "title": "Second PR",
                "headRefName": "feat/b",
                "url": "https://github.com/org/repo/pull/200",
            },
            {
                "number": 100,
                "title": "First PR",
                "headRefName": "feat/a",
                "url": "https://github.com/org/repo/pull/100",
            },
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps([])),  # checks for PR 200
            _mock_result(stdout=json.dumps([])),  # checks for PR 100
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 2
        assert outcomes[0].pr_number == 100
        assert outcomes[1].pr_number == 200

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_gh_failure_returns_empty(self, mock_gh: object) -> None:
        mock_gh.return_value = _mock_result(returncode=1, stderr="auth error")
        outcomes = get_open_pr_reviews()
        assert outcomes == []

    @patch("bid_euchre.ops.reviews.subprocess.run")
    def test_gh_timeout_returns_empty(self, mock_run: object) -> None:
        """Timeout on gh CLI returns empty list, not a hang."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)
        outcomes = get_open_pr_reviews()
        assert outcomes == []

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_invalid_json_returns_empty(self, mock_gh: object) -> None:
        mock_gh.return_value = _mock_result(stdout="not json")
        outcomes = get_open_pr_reviews()
        assert outcomes == []

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_pr_with_deterministic_prechecks(self, mock_gh: object) -> None:
        pr_list = [
            {
                "number": 300,
                "title": "PR with prechecks",
                "headRefName": "feat/c",
                "url": "https://github.com/org/repo/pull/300",
            }
        ]
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "deterministic-prechecks", "state": "SUCCESS"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 1
        assert outcomes[0].has_precheck_ci is True

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_pr_with_failing_ci(self, mock_gh: object) -> None:
        pr_list = [
            {
                "number": 400,
                "title": "Failing PR",
                "headRefName": "fix/broken",
                "url": "https://github.com/org/repo/pull/400",
            }
        ]
        checks = [
            {"name": "tests", "state": "FAILURE"},
            {"name": "reviewing-changes", "state": "PENDING"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 1
        assert outcomes[0].ci_status == "failure"
        assert outcomes[0].review_status == "pending"

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_advisory_status_populated(self, mock_gh: object) -> None:
        """advisory_status is populated from claude-review check."""
        pr_list = [
            {
                "number": 500,
                "title": "PR with advisory",
                "headRefName": "feat/d",
                "url": "https://github.com/org/repo/pull/500",
            }
        ]
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "reviewing-changes", "state": "SUCCESS"},
            {"name": "claude-review", "state": "FAILURE"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 1
        assert outcomes[0].ci_status == "success"
        assert outcomes[0].review_status == "success"
        assert outcomes[0].advisory_status == "failure"

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_advisory_status_none_when_absent(self, mock_gh: object) -> None:
        """advisory_status is 'none' when no advisory check exists."""
        pr_list = [
            {
                "number": 501,
                "title": "PR without advisory",
                "headRefName": "feat/e",
                "url": "https://github.com/org/repo/pull/501",
            }
        ]
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "reviewing-changes", "state": "SUCCESS"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_list)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcomes = get_open_pr_reviews()
        assert len(outcomes) == 1
        assert outcomes[0].advisory_status == "none"


class TestGetPRReviewDetail:
    """Tests for get_pr_review_detail() with mocked gh CLI."""

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_successful_detail(self, mock_gh: object) -> None:
        pr_data = {
            "number": 100,
            "title": "Fix bug",
            "headRefName": "fix/bug",
            "url": "https://github.com/org/repo/pull/100",
        }
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "reviewing-changes", "state": "SUCCESS"},
        ]
        mock_gh.side_effect = [
            _mock_result(stdout=json.dumps(pr_data)),
            _mock_result(stdout=json.dumps(checks)),
        ]

        outcome = get_pr_review_detail(100)
        assert outcome.pr_number == 100
        assert outcome.ci_status == "success"
        assert outcome.review_status == "success"
        assert outcome.checks is not None

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_gh_failure_raises(self, mock_gh: object) -> None:
        mock_gh.return_value = _mock_result(returncode=1, stderr="not found")

        with pytest.raises(RuntimeError, match="Failed to get PR"):
            get_pr_review_detail(999)

    @patch("bid_euchre.ops.reviews._run_gh")
    def test_invalid_json_raises(self, mock_gh: object) -> None:
        mock_gh.return_value = _mock_result(stdout="not json{")

        with pytest.raises(RuntimeError, match="Invalid JSON"):
            get_pr_review_detail(999)


# --- Formatting tests ---


class TestFormatReviewsText:
    """Tests for format_reviews_text()."""

    def test_empty(self) -> None:
        text = format_reviews_text([])
        assert "No open PRs" in text

    def test_single_outcome(self) -> None:
        outcomes = [
            ReviewOutcome(
                pr_number=42,
                title="Test PR",
                branch="feat/test",
                ci_status="success",
                review_status="pending",
                has_precheck_ci=True,
                url="https://github.com/org/repo/pull/42",
            )
        ]
        text = format_reviews_text(outcomes)
        assert "#42" in text
        assert "Test PR" in text
        assert "feat/test" in text
        assert "CI=[+]" in text
        assert "Review=[~]" in text
        assert "Advisory=[-]" in text  # default "none" → "-"
        assert "Precheck=[yes]" in text

    def test_advisory_failure_icon(self) -> None:
        outcomes = [
            ReviewOutcome(
                pr_number=99,
                title="Advisory fail",
                branch="b",
                ci_status="success",
                review_status="success",
                has_precheck_ci=False,
                url="u",
                advisory_status="failure",
            )
        ]
        text = format_reviews_text(outcomes)
        assert "Advisory=[x]" in text

    def test_failure_icons(self) -> None:
        outcomes = [
            ReviewOutcome(
                pr_number=1,
                title="Failing",
                branch="b",
                ci_status="failure",
                review_status="failure",
                has_precheck_ci=False,
                url="u",
            )
        ]
        text = format_reviews_text(outcomes)
        assert "CI=[x]" in text
        assert "Review=[x]" in text


class TestFormatReviewsJSON:
    """Tests for format_reviews_json()."""

    def test_empty(self) -> None:
        assert format_reviews_json([]) == []

    def test_serializable(self) -> None:
        outcomes = [
            ReviewOutcome(
                pr_number=42,
                title="Test",
                branch="b",
                ci_status="success",
                review_status="none",
                has_precheck_ci=False,
                url="u",
            )
        ]
        result = format_reviews_json(outcomes)
        assert len(result) == 1
        assert result[0]["pr_number"] == 42
        assert result[0]["advisory_status"] == "none"
        # Verify it's JSON-serializable
        json.dumps(result)

    def test_advisory_status_in_json(self) -> None:
        outcomes = [
            ReviewOutcome(
                pr_number=42,
                title="Test",
                branch="b",
                ci_status="success",
                review_status="success",
                has_precheck_ci=False,
                url="u",
                advisory_status="failure",
            )
        ]
        result = format_reviews_json(outcomes)
        assert result[0]["advisory_status"] == "failure"


# --- emit_review_event tests ---


class TestEmitReviewEvent:
    """Tests for emit_review_event() — review event emission (#slice7)."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def _make_outcome(
        self,
        review_status: str = "success",
        ci_status: str = "success",
        advisory_status: str = "none",
    ) -> ReviewOutcome:
        return ReviewOutcome(
            pr_number=42,
            title="Test PR",
            branch="fix/test",
            ci_status=ci_status,
            review_status=review_status,
            has_precheck_ci=True,
            url="https://github.com/org/repo/pull/42",
            advisory_status=advisory_status,
        )

    def test_success_emits_review_outcome(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="success")
        result = emit_review_event(outcome, "author-a", events_dir)
        assert result is not None
        assert result["event_type"] == "review_outcome"
        assert result["source"] == "ops.reviews"
        assert result["lane_id"] == "author-a"
        assert result["payload"]["pr_number"] == 42
        assert result["payload"]["review_status"] == "success"
        assert result["payload"]["ci_status"] == "success"
        assert result["payload"]["branch"] == "fix/test"

    def test_failure_emits_review_outcome(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="failure")
        result = emit_review_event(outcome, "author-b", events_dir)
        assert result is not None
        assert result["event_type"] == "review_outcome"
        assert result["payload"]["review_status"] == "failure"

    def test_pending_returns_none(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="pending")
        result = emit_review_event(outcome, "author-a", events_dir)
        assert result is None

    def test_none_returns_none(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="none")
        result = emit_review_event(outcome, "author-a", events_dir)
        assert result is None

    def test_advisory_status_included_when_present(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="success", advisory_status="failure")
        result = emit_review_event(outcome, "author-a", events_dir)
        assert result is not None
        assert result["payload"]["advisory_status"] == "failure"

    def test_advisory_status_omitted_when_none(self, events_dir: Path) -> None:
        outcome = self._make_outcome(review_status="success", advisory_status="none")
        result = emit_review_event(outcome, "author-a", events_dir)
        assert result is not None
        assert "advisory_status" not in result["payload"]

    def test_event_persisted_to_jsonl(self, events_dir: Path) -> None:
        """Verify the event is actually readable from the log."""
        from bid_euchre.ops.events import read_events

        outcome = self._make_outcome(review_status="success")
        emit_review_event(outcome, "author-a", events_dir)

        events = read_events(events_dir)
        assert len(events) == 1
        assert events[0]["event_type"] == "review_outcome"
        assert events[0]["payload"]["pr_number"] == 42


# --- Comment-Based Review Overlay tests ---


class TestClassifyCommentAuthor:
    """Tests for classify_comment_author() identity classification."""

    def test_trusted_bot(self) -> None:
        assert classify_comment_author("chatgpt-codex-connector[bot]") == "trusted_bot"

    def test_trusted_bot_ignores_user_type(self) -> None:
        # Even if user_type says "User", login takes precedence
        assert (
            classify_comment_author("chatgpt-codex-connector[bot]", "User")
            == "trusted_bot"
        )

    def test_other_bot_by_user_type(self) -> None:
        assert classify_comment_author("dependabot[bot]", "Bot") == "other_bot"

    def test_other_bot_by_login_suffix(self) -> None:
        assert classify_comment_author("some-other[bot]") == "other_bot"

    def test_human_with_user_type(self) -> None:
        assert classify_comment_author("octocat", "User") == "human"

    def test_human_default(self) -> None:
        assert classify_comment_author("octocat") == "human"

    def test_empty_login(self) -> None:
        assert classify_comment_author("") == "human"


class TestTrustedBotLogins:
    """Test TRUSTED_BOT_LOGINS constant."""

    def test_contains_codex_connector(self) -> None:
        assert "chatgpt-codex-connector[bot]" in TRUSTED_BOT_LOGINS

    def test_is_frozenset(self) -> None:
        assert isinstance(TRUSTED_BOT_LOGINS, frozenset)


class TestCommentOverlay:
    """Tests for CommentOverlay dataclass."""

    def test_defaults(self) -> None:
        overlay = CommentOverlay(pr_number=42)
        assert overlay.pr_number == 42
        assert overlay.total_comments == 0
        assert overlay.trusted_bot_comments == 0
        assert overlay.human_comments == 0
        assert overlay.other_bot_comments == 0
        assert overlay.latest_trusted_bot_excerpt is None
        assert overlay.comments == []

    def test_to_dict(self) -> None:
        overlay = CommentOverlay(pr_number=42, total_comments=3)
        d = overlay.to_dict()
        assert d["pr_number"] == 42
        assert d["total_comments"] == 3


class TestGetPRCommentOverlay:
    """Tests for get_pr_comment_overlay() with pre-fetched data."""

    def test_empty_comments(self) -> None:
        overlay = get_pr_comment_overlay(42, raw_comments=[])
        assert overlay.pr_number == 42
        assert overlay.total_comments == 0
        assert overlay.trusted_bot_comments == 0
        assert overlay.human_comments == 0
        assert overlay.comments == []

    def test_mixed_authors(self) -> None:
        raw = [
            {
                "id": 1,
                "login": "chatgpt-codex-connector[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T10:00:00Z",
                "body": "Review complete: LGTM",
            },
            {
                "id": 2,
                "login": "octocat",
                "user_type": "User",
                "created_at": "2026-03-20T11:00:00Z",
                "body": "Thanks for the review!",
            },
            {
                "id": 3,
                "login": "dependabot[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T09:00:00Z",
                "body": "Dependency update available",
            },
        ]
        overlay = get_pr_comment_overlay(42, raw_comments=raw)
        assert overlay.total_comments == 3
        assert overlay.trusted_bot_comments == 1
        assert overlay.human_comments == 1
        assert overlay.other_bot_comments == 1
        assert overlay.latest_trusted_bot_author == "chatgpt-codex-connector[bot]"
        assert overlay.latest_trusted_bot_time == "2026-03-20T10:00:00Z"
        assert "Review complete" in (overlay.latest_trusted_bot_excerpt or "")

    def test_latest_trusted_bot_chronological(self) -> None:
        """Should pick the latest trusted bot comment by timestamp."""
        raw = [
            {
                "id": 1,
                "login": "chatgpt-codex-connector[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T08:00:00Z",
                "body": "First review",
            },
            {
                "id": 2,
                "login": "chatgpt-codex-connector[bot]",
                "user_type": "Bot",
                "created_at": "2026-03-20T12:00:00Z",
                "body": "Second review",
            },
        ]
        overlay = get_pr_comment_overlay(42, raw_comments=raw)
        assert overlay.trusted_bot_comments == 2
        assert overlay.latest_trusted_bot_time == "2026-03-20T12:00:00Z"
        assert "Second review" in (overlay.latest_trusted_bot_excerpt or "")

    def test_comment_records_populated(self) -> None:
        raw = [
            {
                "id": 100,
                "login": "octocat",
                "user_type": "User",
                "created_at": "2026-03-20T10:00:00Z",
                "body": "Nice work!",
            },
        ]
        overlay = get_pr_comment_overlay(42, raw_comments=raw)
        assert len(overlay.comments) == 1
        c = overlay.comments[0]
        assert c["comment_id"] == 100
        assert c["author_login"] == "octocat"
        assert c["author_type"] == "human"
        assert c["body_excerpt"] == "Nice work!"


class TestFormatCommentOverlaysText:
    """Tests for format_comment_overlays_text()."""

    def test_empty(self) -> None:
        text = format_comment_overlays_text([])
        assert "No comment data" in text

    def test_with_trusted_bot(self) -> None:
        overlay = CommentOverlay(
            pr_number=42,
            total_comments=2,
            trusted_bot_comments=1,
            human_comments=1,
            latest_trusted_bot_author="chatgpt-codex-connector[bot]",
            latest_trusted_bot_time="2026-03-20T10:00:00Z",
            latest_trusted_bot_excerpt="Review complete",
        )
        text = format_comment_overlays_text([overlay])
        assert "#42" in text
        assert "Trusted=[+:1]" in text
        assert "chatgpt-codex-connector[bot]" in text

    def test_without_trusted_bot(self) -> None:
        overlay = CommentOverlay(
            pr_number=42,
            total_comments=1,
            human_comments=1,
        )
        text = format_comment_overlays_text([overlay])
        assert "Trusted=[-:0]" in text


class TestFormatCommentOverlaysJSON:
    """Tests for format_comment_overlays_json()."""

    def test_empty(self) -> None:
        assert format_comment_overlays_json([]) == []

    def test_serializable(self) -> None:
        overlay = CommentOverlay(pr_number=42, total_comments=1, human_comments=1)
        result = format_comment_overlays_json([overlay])
        assert len(result) == 1
        assert result[0]["pr_number"] == 42
        assert result[0]["total_comments"] == 1
        # Verify JSON-serializable
        json.dumps(result)

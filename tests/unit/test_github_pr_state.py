"""Tests for github_pr_state.py — PR metadata, body, changed files, CI status, comment upsert."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from github_pr_state import (
    _CI_CHECK_NAMES,
    REVIEW_COMMENT_MARKER,
    PRMetadata,
    get_ci_status,
    get_pr_body,
    get_pr_changed_files,
    get_pr_metadata,
    upsert_review_comment,
)


class TestPRMetadata:
    """Test PRMetadata dataclass."""

    def test_body_field_default(self) -> None:
        """body field defaults to empty string for backward compatibility."""
        meta = PRMetadata(
            number=1,
            title="test",
            branch="main",
            state="OPEN",
            head_sha="abc123",
            url="https://example.com",
        )
        assert meta.body == ""

    def test_body_field_set(self) -> None:
        meta = PRMetadata(
            number=1,
            title="test",
            branch="main",
            state="OPEN",
            head_sha="abc123",
            url="https://example.com",
            body="## Plan\nN/A",
        )
        assert meta.body == "## Plan\nN/A"


class TestGetPRMetadata:
    """Test get_pr_metadata includes body."""

    @patch("github_pr_state.subprocess.run")
    def test_includes_body_in_request(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "number": 42,
                    "title": "test PR",
                    "headRefName": "feature-branch",
                    "state": "OPEN",
                    "headRefOid": "abc1234567890",
                    "url": "https://github.com/org/repo/pull/42",
                    "body": "## Plan\nplans/sessions/test.md",
                }
            ),
        )
        meta = get_pr_metadata(42)
        # Verify body field in gh CLI request
        cmd = mock_run.call_args[0][0]
        assert "body" in cmd[5]  # The --json fields string
        assert meta.body == "## Plan\nplans/sessions/test.md"

    @patch("github_pr_state.subprocess.run")
    def test_body_defaults_on_missing(self, mock_run: Mock) -> None:
        """If body is missing from API response, default to empty string."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "number": 42,
                    "title": "test PR",
                    "headRefName": "feature-branch",
                    "state": "OPEN",
                    "headRefOid": "abc1234567890",
                    "url": "https://github.com/org/repo/pull/42",
                    # No body key
                }
            ),
        )
        meta = get_pr_metadata(42)
        assert meta.body == ""


class TestGetPRBody:
    """Test get_pr_body standalone function."""

    @patch("github_pr_state.subprocess.run")
    def test_returns_body_text(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="## Plan\nplans/sessions/test.md\n\n## Summary\n- Added feature\n",
        )
        body = get_pr_body(42)
        assert "## Plan" in body
        assert "plans/sessions/test.md" in body

    @patch("github_pr_state.subprocess.run")
    def test_strips_trailing_whitespace(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="body text\n\n")
        assert get_pr_body(1) == "body text"

    @patch("github_pr_state.subprocess.run")
    def test_raises_on_failure(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=1, stderr="not found")
        with pytest.raises(RuntimeError, match="Failed to get PR #99 body"):
            get_pr_body(99)

    @patch("github_pr_state.subprocess.run")
    def test_uses_jq_for_body(self, mock_run: Mock) -> None:
        """Verify the gh CLI command uses --jq .body for efficient extraction."""
        mock_run.return_value = Mock(returncode=0, stdout="body text")
        get_pr_body(42)
        cmd = mock_run.call_args[0][0]
        assert "--jq" in cmd
        assert ".body" in cmd


class TestGetPRChangedFiles:
    """Test get_pr_changed_files function."""

    @patch("github_pr_state.subprocess.run")
    def test_returns_file_list(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="scripts/internal/review_driver.py\ntests/unit/test_review.py\n",
        )
        files = get_pr_changed_files(42)
        assert files == [
            "scripts/internal/review_driver.py",
            "tests/unit/test_review.py",
        ]

    @patch("github_pr_state.subprocess.run")
    def test_strips_whitespace(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="  src/foo.py  \n  src/bar.py  \n",
        )
        files = get_pr_changed_files(1)
        assert files == ["src/foo.py", "src/bar.py"]

    @patch("github_pr_state.subprocess.run")
    def test_skips_empty_lines(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="src/foo.py\n\nsrc/bar.py\n\n",
        )
        files = get_pr_changed_files(1)
        assert files == ["src/foo.py", "src/bar.py"]

    @patch("github_pr_state.subprocess.run")
    def test_raises_on_failure(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=1, stderr="not found")
        with pytest.raises(RuntimeError, match="Failed to get PR #99"):
            get_pr_changed_files(99)

    @patch("github_pr_state.subprocess.run")
    def test_empty_diff_returns_empty_list(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="")
        files = get_pr_changed_files(1)
        assert files == []


# ---------------------------------------------------------------------------
# get_ci_status tests — allowlist-based CI classification
# ---------------------------------------------------------------------------


def _mock_checks_result(checks: list[dict]) -> Mock:
    """Build a Mock subprocess result for get_ci_status."""
    return Mock(returncode=0, stdout=json.dumps(checks))


class TestCICheckAllowlist:
    """Verify the CI allowlist contains expected check names."""

    def test_contains_tests(self) -> None:
        assert "tests" in _CI_CHECK_NAMES

    def test_contains_prechecks(self) -> None:
        assert "prechecks" in _CI_CHECK_NAMES

    def test_contains_governance(self) -> None:
        assert "governance" in _CI_CHECK_NAMES

    def test_does_not_contain_non_validation_checks(self) -> None:
        """Review, advisory, and plumbing checks must not appear in CI allowlist."""
        assert "reviewing-changes" not in _CI_CHECK_NAMES
        assert "claude-review" not in _CI_CHECK_NAMES
        assert "enable-auto-merge" not in _CI_CHECK_NAMES

    def test_matches_shared_constant(self) -> None:
        """Local _CI_CHECK_NAMES must equal the shared CI_CHECK_NAMES constant."""
        from bid_euchre.ops import CI_CHECK_NAMES

        assert set(_CI_CHECK_NAMES) == set(CI_CHECK_NAMES)


class TestGetCIStatus:
    """Test get_ci_status with allowlist-based classification."""

    @patch("github_pr_state.subprocess.run")
    def test_all_ci_checks_pass(self, mock_run: Mock) -> None:
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "tests", "state": "SUCCESS"},
                {"name": "prechecks", "state": "SUCCESS"},
                {"name": "governance", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "success"

    @patch("github_pr_state.subprocess.run")
    def test_ci_failure(self, mock_run: Mock) -> None:
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "tests", "state": "FAILURE"},
                {"name": "prechecks", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "failure"

    @patch("github_pr_state.subprocess.run")
    def test_ci_pending(self, mock_run: Mock) -> None:
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "tests", "state": "PENDING"},
                {"name": "prechecks", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "pending"

    @patch("github_pr_state.subprocess.run")
    def test_reviewing_changes_failure_ignored(self, mock_run: Mock) -> None:
        """reviewing-changes is not in the CI allowlist — ignored."""
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "reviewing-changes", "state": "FAILURE"},
                {"name": "tests", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "success"

    @patch("github_pr_state.subprocess.run")
    def test_claude_review_failure_ignored(self, mock_run: Mock) -> None:
        """claude-review is not in the CI allowlist — ignored."""
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "claude-review", "state": "FAILURE"},
                {"name": "tests", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "success"

    @patch("github_pr_state.subprocess.run")
    def test_enable_auto_merge_failure_ignored(self, mock_run: Mock) -> None:
        """enable-auto-merge is plumbing, not validation — ignored."""
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "enable-auto-merge", "state": "FAILURE"},
                {"name": "tests", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "success"

    @patch("github_pr_state.subprocess.run")
    def test_future_unknown_check_ignored(self, mock_run: Mock) -> None:
        """Any unknown check name not in allowlist is ignored."""
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "some-new-advisory-thing", "state": "FAILURE"},
                {"name": "tests", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "success"

    @patch("github_pr_state.subprocess.run")
    def test_only_non_ci_checks_returns_pending(self, mock_run: Mock) -> None:
        """If no CI checks exist, treat as pending."""
        mock_run.return_value = _mock_checks_result(
            [
                {"name": "reviewing-changes", "state": "SUCCESS"},
                {"name": "claude-review", "state": "SUCCESS"},
            ]
        )
        assert get_ci_status(1) == "pending"

    @patch("github_pr_state.subprocess.run")
    def test_gh_failure_returns_unknown(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=1, stderr="not found")
        assert get_ci_status(1) == "unknown"

    @patch("github_pr_state.subprocess.run")
    def test_empty_checks_returns_pending(self, mock_run: Mock) -> None:
        mock_run.return_value = _mock_checks_result([])
        assert get_ci_status(1) == "pending"


# ---------------------------------------------------------------------------
# upsert_review_comment tests
# ---------------------------------------------------------------------------


class TestUpsertReviewComment:
    """Test upsert_review_comment create/update behavior."""

    @patch("github_pr_state.subprocess.run")
    def test_creates_new_comment_when_none_exists(self, mock_run: Mock) -> None:
        """When no existing comment is found, create a new one."""
        # First call: list comments (returns empty)
        # Second call: create comment
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # list comments — empty
            Mock(returncode=0, stdout=""),  # create comment — success
        ]

        body = "## Review Loop -- Blocked\nSome details"
        result = upsert_review_comment(42, body)

        assert result is True
        # The create call should use gh pr comment
        create_call = mock_run.call_args_list[1]
        cmd = create_call[0][0]
        assert cmd[0] == "gh"
        assert cmd[1] == "pr"
        assert cmd[2] == "comment"
        assert "42" in cmd
        # Body should include the marker
        body_arg = cmd[cmd.index("--body") + 1]
        assert REVIEW_COMMENT_MARKER in body_arg

    @patch("github_pr_state.subprocess.run")
    def test_updates_existing_comment(self, mock_run: Mock) -> None:
        """When existing comment with marker is found, update it."""
        # First call: list comment IDs
        # Second call: get comment body (has marker)
        # Third call: update comment
        mock_run.side_effect = [
            Mock(returncode=0, stdout="12345\n67890\n"),  # list IDs
            Mock(
                returncode=0,
                stdout=f"{REVIEW_COMMENT_MARKER}\nold body",
            ),  # get body of ID 12345 — has marker
            Mock(returncode=0, stdout=""),  # update — success
        ]

        body = "## Review Loop -- Passed\nNew details"
        result = upsert_review_comment(42, body)

        assert result is True
        # The update call should be a PATCH
        update_call = mock_run.call_args_list[2]
        cmd = update_call[0][0]
        assert "--method" in cmd
        assert "PATCH" in cmd

    @patch("github_pr_state.subprocess.run")
    def test_marker_prepended_if_missing(self, mock_run: Mock) -> None:
        """Body gets marker prepended if not already present."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # list — empty
            Mock(returncode=0, stdout=""),  # create — success
        ]

        body = "## Review Loop -- Blocked"
        upsert_review_comment(42, body)

        create_call = mock_run.call_args_list[1]
        cmd = create_call[0][0]
        body_arg = cmd[cmd.index("--body") + 1]
        assert body_arg.startswith(REVIEW_COMMENT_MARKER)

    @patch("github_pr_state.subprocess.run")
    def test_marker_not_duplicated_if_present(self, mock_run: Mock) -> None:
        """If body already contains marker, don't add it again."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # list — empty
            Mock(returncode=0, stdout=""),  # create — success
        ]

        body = f"{REVIEW_COMMENT_MARKER}\n## Review Loop -- Blocked"
        upsert_review_comment(42, body)

        create_call = mock_run.call_args_list[1]
        cmd = create_call[0][0]
        body_arg = cmd[cmd.index("--body") + 1]
        # Should appear exactly once
        assert body_arg.count(REVIEW_COMMENT_MARKER) == 1

    @patch("github_pr_state.subprocess.run")
    def test_returns_false_on_create_failure(self, mock_run: Mock) -> None:
        mock_run.side_effect = [
            Mock(returncode=0, stdout=""),  # list — empty
            Mock(returncode=1, stderr="permission denied"),  # create — fail
        ]

        result = upsert_review_comment(42, "body")
        assert result is False

    @patch("github_pr_state.subprocess.run")
    def test_returns_false_on_update_failure(self, mock_run: Mock) -> None:
        mock_run.side_effect = [
            Mock(returncode=0, stdout="111\n"),  # list IDs
            Mock(
                returncode=0,
                stdout=f"{REVIEW_COMMENT_MARKER}\nold",
            ),  # body has marker
            Mock(returncode=1, stderr="update failed"),  # update — fail
        ]

        result = upsert_review_comment(42, "new body")
        assert result is False

    @patch("github_pr_state.subprocess.run")
    def test_skips_non_matching_comments(self, mock_run: Mock) -> None:
        """Comments without marker are skipped; creates new if none match."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="111\n222\n"),  # list IDs
            Mock(returncode=0, stdout="regular comment body"),  # ID 111 — no marker
            Mock(returncode=0, stdout="another comment"),  # ID 222 — no marker
            Mock(returncode=0, stdout=""),  # create — success
        ]

        result = upsert_review_comment(42, "body")
        assert result is True
        # Should have made 4 calls: list, get 111, get 222, create
        assert mock_run.call_count == 4

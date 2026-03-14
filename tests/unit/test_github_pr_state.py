"""Tests for github_pr_state.py — PR metadata, body retrieval, changed files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from github_pr_state import (
    PRMetadata,
    get_pr_body,
    get_pr_changed_files,
    get_pr_metadata,
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

"""Tests for verify_squash_merge.py — stacked-PR squash merge verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from verify_squash_merge import (
    format_report,
    get_merge_commit_files,
    get_pr_files,
    main,
    verify_stack,
)

# ---------------------------------------------------------------------------
# Unit tests for verify_stack (pure logic, no subprocess)
# ---------------------------------------------------------------------------


class TestVerifyStack:
    """Test the core verification logic."""

    def test_no_dropped_files(self) -> None:
        """All stack files present in bottom — no drops."""
        bottom = {"a.py", "b.py", "c.py"}
        stack = {101: {"a.py", "b.py"}, 102: {"c.py"}}
        dropped = verify_stack(bottom, stack)
        assert dropped == []

    def test_dropped_file_detected(self) -> None:
        """File in stack PR but missing from bottom is flagged."""
        bottom = {"a.py"}
        stack = {101: {"a.py", "b.py"}}
        dropped = verify_stack(bottom, stack)
        assert len(dropped) == 1
        assert dropped[0]["file"] == "b.py"
        assert dropped[0]["source_prs"] == [101]

    def test_multiple_dropped_files(self) -> None:
        """Multiple files dropped from different PRs."""
        bottom = {"keep.py"}
        stack = {
            101: {"keep.py", "dropped1.py"},
            102: {"dropped2.html", "keep.py"},
        }
        dropped = verify_stack(bottom, stack)
        assert len(dropped) == 2
        files = [d["file"] for d in dropped]
        assert "dropped1.py" in files
        assert "dropped2.html" in files

    def test_file_in_multiple_stack_prs(self) -> None:
        """File changed in multiple stack PRs — all sources listed."""
        bottom: set[str] = set()
        stack = {101: {"shared.py"}, 102: {"shared.py"}}
        dropped = verify_stack(bottom, stack)
        assert len(dropped) == 1
        assert dropped[0]["source_prs"] == [101, 102]

    def test_bottom_has_extra_files(self) -> None:
        """Bottom PR has files not in stack — that's fine."""
        bottom = {"a.py", "b.py", "extra.py"}
        stack = {101: {"a.py"}}
        dropped = verify_stack(bottom, stack)
        assert dropped == []

    def test_empty_stack(self) -> None:
        """Empty stack PRs — no drops possible."""
        bottom = {"a.py"}
        stack: dict[int, set[str]] = {101: set()}
        dropped = verify_stack(bottom, stack)
        assert dropped == []

    def test_empty_bottom(self) -> None:
        """Empty bottom — all stack files are dropped."""
        bottom: set[str] = set()
        stack = {101: {"a.py"}, 102: {"b.py"}}
        dropped = verify_stack(bottom, stack)
        assert len(dropped) == 2

    def test_results_sorted_by_file(self) -> None:
        """Dropped files are returned in sorted order."""
        bottom: set[str] = set()
        stack = {101: {"z.py", "a.py", "m.py"}}
        dropped = verify_stack(bottom, stack)
        files = [d["file"] for d in dropped]
        assert files == ["a.py", "m.py", "z.py"]


# ---------------------------------------------------------------------------
# Unit tests for get_pr_files (mocked subprocess)
# ---------------------------------------------------------------------------


class TestGetPRFiles:
    """Test PR file retrieval with mocked gh CLI."""

    @patch("verify_squash_merge.subprocess.run")
    def test_parses_file_list(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="src/a.py\nsrc/b.py\ntests/test_a.py\n",
        )
        files = get_pr_files(42)
        assert files == {"src/a.py", "src/b.py", "tests/test_a.py"}

    @patch("verify_squash_merge.subprocess.run")
    def test_strips_whitespace(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="  a.py  \n\nb.py\n  \n",
        )
        files = get_pr_files(42)
        assert files == {"a.py", "b.py"}

    @patch("verify_squash_merge.subprocess.run")
    def test_empty_diff(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=0, stdout="")
        files = get_pr_files(42)
        assert files == set()

    @patch("verify_squash_merge.subprocess.run")
    def test_error_raises(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=1, stderr="not found")
        with pytest.raises(RuntimeError, match="Failed to get PR #42"):
            get_pr_files(42)


# ---------------------------------------------------------------------------
# Unit tests for get_merge_commit_files (mocked subprocess)
# ---------------------------------------------------------------------------


class TestGetMergeCommitFiles:
    """Test merge commit file retrieval with mocked git CLI."""

    @patch("verify_squash_merge.subprocess.run")
    def test_parses_diff_tree(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="src/a.py\nsrc/b.py\n",
        )
        files = get_merge_commit_files("abc123")
        assert files == {"src/a.py", "src/b.py"}
        cmd = mock_run.call_args[0][0]
        assert "diff-tree" in cmd
        assert "abc123" in cmd

    @patch("verify_squash_merge.subprocess.run")
    def test_error_raises(self, mock_run: Mock) -> None:
        mock_run.return_value = Mock(returncode=1, stderr="bad object")
        with pytest.raises(RuntimeError, match="Failed to get files for commit"):
            get_merge_commit_files("bad_sha")


# ---------------------------------------------------------------------------
# Unit tests for format_report
# ---------------------------------------------------------------------------


class TestFormatReport:
    """Test human-readable report formatting."""

    def test_clean_report(self) -> None:
        report = format_report([], "PR #100", [101, 102], 5, 4)
        assert "✅" in report
        assert "no dropped files" in report

    def test_dropped_report(self) -> None:
        dropped = [
            {"file": "a.html", "source_prs": [101]},
            {"file": "b.py", "source_prs": [101, 102]},
        ]
        report = format_report(dropped, "PR #100", [101, 102], 3, 5)
        assert "❌" in report
        assert "2 file(s) potentially dropped" in report
        assert "a.html" in report
        assert "#101, #102" in report


# ---------------------------------------------------------------------------
# Integration test for main() with mocked subprocess
# ---------------------------------------------------------------------------


class TestMain:
    """Test CLI entry point with mocked subprocess calls."""

    @patch("verify_squash_merge.subprocess.run")
    def test_clean_exit_zero(self, mock_run: Mock) -> None:
        """Clean stack returns exit code 0."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="a.py\nb.py\n",
        )
        rc = main(["--bottom-pr", "100", "--stack-prs", "101"])
        assert rc == 0

    @patch("verify_squash_merge.subprocess.run")
    def test_dropped_exit_one(self, mock_run: Mock) -> None:
        """Dropped files return exit code 1."""

        def side_effect(cmd: list[str], **_kw: object) -> Mock:
            pr_num = cmd[3]  # gh pr diff <num> --name-only
            if pr_num == "100":
                return Mock(returncode=0, stdout="a.py\n")
            else:
                return Mock(returncode=0, stdout="a.py\nb.py\n")

        mock_run.side_effect = side_effect
        rc = main(["--bottom-pr", "100", "--stack-prs", "101"])
        assert rc == 1

    @patch("verify_squash_merge.subprocess.run")
    def test_json_output(
        self, mock_run: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output mode produces valid JSON."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="a.py\nb.py\n",
        )
        rc = main(["--bottom-pr", "100", "--stack-prs", "101", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["ok"] is True
        assert data["dropped_count"] == 0

    @patch("verify_squash_merge.subprocess.run")
    def test_json_output_with_drops(
        self, mock_run: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """JSON output includes dropped file details."""

        def side_effect(cmd: list[str], **_kw: object) -> Mock:
            pr_num = cmd[3]
            if pr_num == "100":
                return Mock(returncode=0, stdout="a.py\n")
            else:
                return Mock(returncode=0, stdout="a.py\ndropped.html\n")

        mock_run.side_effect = side_effect
        rc = main(["--bottom-pr", "100", "--stack-prs", "101", "--json"])
        assert rc == 1
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["ok"] is False
        assert data["dropped_count"] == 1
        assert data["dropped"][0]["file"] == "dropped.html"

    @patch("verify_squash_merge.subprocess.run")
    def test_merge_sha_mode(self, mock_run: Mock) -> None:
        """Post-merge audit mode via --merge-sha."""

        def side_effect(cmd: list[str], **_kw: object) -> Mock:
            if "diff-tree" in cmd:
                return Mock(returncode=0, stdout="a.py\nb.py\n")
            else:
                return Mock(returncode=0, stdout="a.py\nb.py\n")

        mock_run.side_effect = side_effect
        rc = main(["--merge-sha", "abc123def", "--stack-prs", "101", "102"])
        assert rc == 0

    @patch("verify_squash_merge.subprocess.run")
    def test_gh_error_exit_two(self, mock_run: Mock) -> None:
        """gh CLI failure returns exit code 2."""
        mock_run.return_value = Mock(returncode=1, stderr="not found")
        rc = main(["--bottom-pr", "999", "--stack-prs", "101"])
        assert rc == 2

    @patch("verify_squash_merge.subprocess.run")
    def test_multiple_stack_prs(self, mock_run: Mock) -> None:
        """Multiple stack PRs are collected and union-compared."""
        call_count = 0

        def side_effect(cmd: list[str], **_kw: object) -> Mock:
            nonlocal call_count
            call_count += 1
            pr_num = cmd[3]
            if pr_num == "100":
                return Mock(returncode=0, stdout="a.py\n")
            elif pr_num == "101":
                return Mock(returncode=0, stdout="a.py\nb.py\n")
            elif pr_num == "102":
                return Mock(returncode=0, stdout="a.py\nc.py\n")
            return Mock(returncode=0, stdout="")

        mock_run.side_effect = side_effect
        rc = main(["--bottom-pr", "100", "--stack-prs", "101", "102"])
        assert rc == 1  # b.py and c.py are dropped

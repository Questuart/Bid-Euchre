"""Tests for review_driver.py — plan parsing, plan validation, scope drift, and driver logic."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from review_driver import (
    _format_review_comment,
    _parse_plan_files,
    check_scope_drift,
    classify_review_mode,
    parse_plan_reference,
    validate_plan,
)

# ---------------------------------------------------------------------------
# Fixtures: PR body samples
# ---------------------------------------------------------------------------

BODY_WITH_PLAN_PATH = """\
## Plan
plans/sessions/2026-03-14_plan-aware-autonomous-review.md

## Summary
- Added plan validation
"""

BODY_WITH_BACKTICK_PATH = """\
## Plan
`plans/sessions/2026-03-14_plan-aware-autonomous-review.md`

## Summary
- Added plan validation
"""

BODY_WITH_MARKDOWN_LINK = """\
## Plan
[Plan file](plans/sessions/2026-03-14_plan-aware-autonomous-review.md)

## Summary
- Added plan validation
"""

BODY_WITH_LIST_ITEM = """\
## Plan
- plans/sessions/2026-03-14_plan-aware-autonomous-review.md

## Summary
- Added plan validation
"""

BODY_WITH_NA = """\
## Plan
<!-- Link to the plan file that authorized this PR, or N/A for trivial changes -->
N/A

## Summary
- Trivial fix
"""

BODY_WITH_NONE = """\
## Plan
none

## Summary
- Trivial fix
"""

BODY_WITH_DASH = """\
## Plan
<!-- Link to the plan file that authorized this PR, or N/A for trivial changes -->
-

## Summary
- Empty template
"""

BODY_EMPTY_PLAN = """\
## Plan

## Summary
- Missing plan reference
"""

BODY_NO_PLAN_SECTION = """\
## Summary
- No plan section at all
"""

BODY_WITH_COMMENT_ONLY = """\
## Plan
<!-- Link to the plan file that authorized this PR, or N/A for trivial changes -->

## Summary
- Only comment in plan section
"""

BODY_DOCS_PLAN_PATH = """\
## Plan
docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md

## Summary
- Updated docs
"""

BODY_WITH_BACKTICK_LIST = """\
## Plan
- `plans/sessions/2026-03-14_foo.md`

## Summary
- path in backticks with list prefix
"""


# ---------------------------------------------------------------------------
# parse_plan_reference tests
# ---------------------------------------------------------------------------


class TestParsePlanReference:
    """Test plan reference extraction from PR body text."""

    def test_plain_path(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_PLAN_PATH)
        assert path == "plans/sessions/2026-03-14_plan-aware-autonomous-review.md"
        assert not opted_out

    def test_backtick_path(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_BACKTICK_PATH)
        assert path == "plans/sessions/2026-03-14_plan-aware-autonomous-review.md"
        assert not opted_out

    def test_markdown_link(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_MARKDOWN_LINK)
        assert path == "plans/sessions/2026-03-14_plan-aware-autonomous-review.md"
        assert not opted_out

    def test_list_item_path(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_LIST_ITEM)
        assert path == "plans/sessions/2026-03-14_plan-aware-autonomous-review.md"
        assert not opted_out

    def test_backtick_with_list(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_BACKTICK_LIST)
        assert path == "plans/sessions/2026-03-14_foo.md"
        assert not opted_out

    def test_docs_path(self) -> None:
        path, opted_out = parse_plan_reference(BODY_DOCS_PLAN_PATH)
        assert path == "docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md"
        assert not opted_out

    def test_na_explicit_optout(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_NA)
        assert path is None
        assert opted_out

    def test_none_explicit_optout(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_NONE)
        assert path is None
        assert opted_out

    def test_dash_explicit_optout(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_DASH)
        assert path is None
        assert opted_out

    def test_empty_plan_section(self) -> None:
        path, opted_out = parse_plan_reference(BODY_EMPTY_PLAN)
        assert path is None
        assert not opted_out

    def test_no_plan_section(self) -> None:
        path, opted_out = parse_plan_reference(BODY_NO_PLAN_SECTION)
        assert path is None
        assert not opted_out

    def test_comment_only_section(self) -> None:
        path, opted_out = parse_plan_reference(BODY_WITH_COMMENT_ONLY)
        assert path is None
        assert not opted_out

    def test_empty_body(self) -> None:
        path, opted_out = parse_plan_reference("")
        assert path is None
        assert not opted_out


# ---------------------------------------------------------------------------
# validate_plan tests
# ---------------------------------------------------------------------------


class TestValidatePlan:
    """Test plan validation logic."""

    @patch("github_pr_state.get_pr_body")
    def test_na_produces_no_findings(self, mock_body) -> None:
        mock_body.return_value = BODY_WITH_NA
        plan_path, findings = validate_plan(1)
        assert plan_path is None
        assert findings == []

    @patch("github_pr_state.get_pr_body")
    def test_missing_plan_produces_p2(self, mock_body) -> None:
        mock_body.return_value = BODY_EMPTY_PLAN
        plan_path, findings = validate_plan(1)
        assert plan_path is None
        assert len(findings) == 1
        assert findings[0]["severity"] == "P2"
        assert findings[0]["check_id"] == "PV1"

    @patch("github_pr_state.get_pr_body")
    def test_no_plan_section_produces_p2(self, mock_body) -> None:
        mock_body.return_value = BODY_NO_PLAN_SECTION
        plan_path, findings = validate_plan(1)
        assert plan_path is None
        assert len(findings) == 1
        assert findings[0]["check_id"] == "PV1"

    @patch("github_pr_state.get_pr_body")
    def test_broken_reference_produces_p1(self, mock_body, tmp_path) -> None:
        mock_body.return_value = (
            "## Plan\nplans/sessions/nonexistent.md\n\n## Summary\n- test\n"
        )
        plan_path, findings = validate_plan(1, repo_root=tmp_path)
        assert plan_path == "plans/sessions/nonexistent.md"
        assert len(findings) == 1
        assert findings[0]["severity"] == "P1"
        assert findings[0]["check_id"] == "PV2"

    @patch("github_pr_state.get_pr_body")
    def test_valid_plan_no_findings(self, mock_body, tmp_path) -> None:
        # Create a plan file with real content
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test.md"
        plan_file.write_text(
            "# Test Plan\n\n"
            "## Plan\n"
            "This plan implements the foo feature with bar approach. "
            "It modifies several files and adds comprehensive tests. "
            "The validation strategy uses targeted pytest runs.\n"
        )
        mock_body.return_value = "## Plan\nplans/sessions/test.md\n\n## Summary\n"
        plan_path, findings = validate_plan(1, repo_root=tmp_path)
        assert plan_path == "plans/sessions/test.md"
        assert findings == []

    @patch("github_pr_state.get_pr_body")
    def test_empty_plan_file_produces_p2(self, mock_body, tmp_path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "empty.md"
        plan_file.write_text("# Empty Plan\n")
        mock_body.return_value = "## Plan\nplans/sessions/empty.md\n\n## Summary\n"
        plan_path, findings = validate_plan(1, repo_root=tmp_path)
        assert plan_path == "plans/sessions/empty.md"
        assert len(findings) == 1
        assert findings[0]["severity"] == "P2"
        assert findings[0]["check_id"] == "PV3"

    @patch("github_pr_state.get_pr_body")
    def test_body_fetch_failure_is_non_blocking(self, mock_body) -> None:
        mock_body.side_effect = RuntimeError("gh CLI failed")
        plan_path, findings = validate_plan(1)
        assert plan_path is None
        assert findings == []

    @patch("github_pr_state.get_pr_body")
    def test_plan_path_stored_in_result(self, mock_body, tmp_path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "real.md"
        plan_file.write_text(
            "# Real Plan\n\n"
            "## Plan\n"
            "Detailed implementation plan with enough content "
            "to pass the minimum content length check easily.\n"
        )
        mock_body.return_value = "## Plan\nplans/sessions/real.md\n\n## Summary\n"
        plan_path, _ = validate_plan(1, repo_root=tmp_path)
        assert plan_path == "plans/sessions/real.md"


# ---------------------------------------------------------------------------
# classify_review_mode tests (existing function, extended coverage)
# ---------------------------------------------------------------------------


class TestClassifyReviewMode:
    """Test review mode classification from changed files."""

    def test_standard_mode(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(["src/bid_euchre/core/rules.py"])
        assert mode == ReviewMode.STANDARD

    def test_report_audit_mode(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["docs/04_reports/r0/report.md", "src/bid_euchre/core/rules.py"]
        )
        assert mode == ReviewMode.REPORT_AUDIT

    def test_plan_audit_mode(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(["plans/sessions/2026-03-14_test.md"])
        assert mode == ReviewMode.PLAN_AUDIT

    def test_report_takes_precedence_over_plan(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["docs/04_reports/r0/report.md", "plans/sessions/test.md"]
        )
        assert mode == ReviewMode.REPORT_AUDIT


# ---------------------------------------------------------------------------
# _parse_plan_files tests
# ---------------------------------------------------------------------------

PLAN_WITH_FILES_BACKTICK = """\
# Test Plan

## Summary
Some summary.

## Files
- `scripts/internal/review_driver.py` — add scope-drift detection
- `scripts/internal/github_pr_state.py` — add upsert_review_comment
- `tests/unit/test_review_driver.py` — extend tests

## Validation
- make check
"""

PLAN_WITH_FILES_PLAIN = """\
# Test Plan

## Files
- scripts/internal/review_driver.py — add scope-drift detection
- scripts/internal/github_pr_state.py — add upsert_review_comment
"""

PLAN_WITHOUT_FILES_SECTION = """\
# Test Plan

## Summary
No files section here.
"""

PLAN_WITH_FILES_EMDASH = """\
# Test Plan

## Files
- `src/foo.py` -- description
- `src/bar.py`
"""


class TestParsePlanFiles:
    """Test plan file extraction from plan documents."""

    def test_backtick_quoted_paths(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        (plan_dir / "test.md").write_text(PLAN_WITH_FILES_BACKTICK)

        files = _parse_plan_files("plans/sessions/test.md", tmp_path)
        assert files == [
            "scripts/internal/review_driver.py",
            "scripts/internal/github_pr_state.py",
            "tests/unit/test_review_driver.py",
        ]

    def test_plain_paths(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        (plan_dir / "test.md").write_text(PLAN_WITH_FILES_PLAIN)

        files = _parse_plan_files("plans/sessions/test.md", tmp_path)
        assert files == [
            "scripts/internal/review_driver.py",
            "scripts/internal/github_pr_state.py",
        ]

    def test_no_files_section_returns_empty(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        (plan_dir / "test.md").write_text(PLAN_WITHOUT_FILES_SECTION)

        files = _parse_plan_files("plans/sessions/test.md", tmp_path)
        assert files == []

    def test_nonexistent_plan_returns_empty(self, tmp_path: Path) -> None:
        files = _parse_plan_files("plans/sessions/nonexistent.md", tmp_path)
        assert files == []

    def test_emdash_and_mixed_formats(self, tmp_path: Path) -> None:
        plan_dir = tmp_path / "plans" / "sessions"
        plan_dir.mkdir(parents=True)
        (plan_dir / "test.md").write_text(PLAN_WITH_FILES_EMDASH)

        files = _parse_plan_files("plans/sessions/test.md", tmp_path)
        assert "src/foo.py" in files
        assert "src/bar.py" in files


# ---------------------------------------------------------------------------
# check_scope_drift tests
# ---------------------------------------------------------------------------


class TestCheckScopeDrift:
    """Test scope-drift detection logic."""

    def test_no_drift_when_files_match(self) -> None:
        changed = ["src/foo.py", "src/bar.py"]
        declared = ["src/foo.py", "src/bar.py"]
        findings = check_scope_drift(changed, declared)
        assert findings == []

    def test_drift_on_extra_files(self) -> None:
        changed = ["src/foo.py", "src/bar.py", "src/baz.py"]
        declared = ["src/foo.py", "src/bar.py"]
        findings = check_scope_drift(changed, declared)
        assert len(findings) == 1
        assert findings[0]["file"] == "src/baz.py"
        assert findings[0]["check_id"] == "SD1"
        assert findings[0]["severity"] == "P2"

    def test_no_drift_when_subset(self) -> None:
        """Changed files are a subset of declared — no drift."""
        changed = ["src/foo.py"]
        declared = ["src/foo.py", "src/bar.py"]
        findings = check_scope_drift(changed, declared)
        assert findings == []

    def test_empty_declared_returns_no_findings(self) -> None:
        """No declared files = no scope contract to check."""
        changed = ["src/foo.py", "src/bar.py"]
        findings = check_scope_drift(changed, [])
        assert findings == []

    def test_all_findings_are_p2(self) -> None:
        changed = ["a.py", "b.py", "c.py"]
        declared = ["a.py"]
        findings = check_scope_drift(changed, declared)
        assert len(findings) == 2
        for f in findings:
            assert f["severity"] == "P2"
            assert f["check_id"] == "SD1"

    def test_duplicate_changed_files_deduplicated(self) -> None:
        changed = ["src/foo.py", "src/foo.py", "src/bar.py"]
        declared = ["src/foo.py"]
        findings = check_scope_drift(changed, declared)
        assert len(findings) == 1
        assert findings[0]["file"] == "src/bar.py"


# ---------------------------------------------------------------------------
# _format_review_comment tests
# ---------------------------------------------------------------------------


class TestFormatReviewComment:
    """Test review comment formatting."""

    def test_blocked_comment_includes_header(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.STOPPED_CI_FAILURE.value,
            current_head_sha="abc1234567890",
        )
        state.stop_reason = "CI failed"
        body = _format_review_comment(state, [], "blocked")
        assert "## Review Loop -- Blocked" in body
        assert "abc1234567890" in body
        assert "CI failed" in body
        assert "<!-- review-loop-comment -->" in body

    def test_passed_comment_includes_header(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="def4567890abc",
        )
        body = _format_review_comment(state, [], "passed")
        assert "## Review Loop -- Passed" in body
        assert "No findings." in body

    def test_blockers_rendered_as_table(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.STOPPED_CI_FAILURE.value,
        )
        findings = [
            {
                "severity": "P1",
                "file": "src/foo.py",
                "check_id": "PV2",
                "message": "Plan file missing",
            }
        ]
        body = _format_review_comment(state, findings, "blocked")
        assert "### Blocking Findings" in body
        assert "PV2" in body
        assert "src/foo.py" in body

    def test_warnings_rendered_as_table(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.STOPPED_CI_FAILURE.value,
        )
        findings = [
            {
                "severity": "P2",
                "file": "src/extra.py",
                "check_id": "SD1",
                "message": "File not declared in plan",
            }
        ]
        body = _format_review_comment(state, findings, "blocked")
        assert "### Warnings" in body
        assert "SD1" in body

    def test_recovery_command_included(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=99,
            branch="test-branch",
            state=ReviewState.STOPPED_CI_FAILURE.value,
        )
        body = _format_review_comment(state, [], "blocked")
        assert "--pr 99 --trigger manual" in body

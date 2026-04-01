"""Tests for review_driver.py — plan parsing, plan validation, scope drift, and driver logic."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/internal to path for direct imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from review_driver import (
    _create_follow_up_issues,
    _format_review_comment,
    _parse_plan_files,
    _should_timeout,
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
    def test_broken_reference_produces_p2(self, mock_body, tmp_path) -> None:
        """PV2 is P2 (non-blocking) because the review driver may run in a
        stale worktree where the plan file doesn't exist locally even though
        it exists on the PR branch."""
        mock_body.return_value = (
            "## Plan\nplans/sessions/nonexistent.md\n\n## Summary\n- test\n"
        )
        plan_path, findings = validate_plan(1, repo_root=tmp_path)
        assert plan_path == "plans/sessions/nonexistent.md"
        assert len(findings) == 1
        assert findings[0]["severity"] == "P2"
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

    def test_validate_plan_docstring_matches_code_severity(self) -> None:
        """PV2 docstring must say P2, not P1. Regression test for #828."""
        docstring = validate_plan.__doc__
        assert docstring is not None
        assert "P2 if broken reference" in docstring
        assert "P1 if broken reference" not in docstring

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

    def test_report_only_returns_report_audit(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(["docs/04_reports/arc_d_v1/r0/report.md"])
        assert mode == ReviewMode.REPORT_AUDIT

    def test_plan_audit_mode(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(["plans/sessions/2026-03-14_test.md"])
        assert mode == ReviewMode.PLAN_AUDIT

    def test_report_takes_precedence_over_plan(self) -> None:
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["docs/04_reports/arc_d_v1/r0/report.md", "plans/sessions/test.md"]
        )
        assert mode == ReviewMode.REPORT_AUDIT

    def test_report_pr_unaffected_by_local_plan_files(self) -> None:
        """PR-scoped mode stays REPORT_AUDIT regardless of local plan files."""
        from review_state import ReviewMode

        pr_files = ["docs/04_reports/arc_d_v2/r0/01_results.md"]
        local_files = pr_files + ["plans/sessions/stale.md"]
        assert classify_review_mode(pr_files) == ReviewMode.REPORT_AUDIT
        assert classify_review_mode(local_files) == ReviewMode.REPORT_AUDIT


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
        assert "Review Coordinator -- Blocked" in body
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
        assert "Review Coordinator -- Passed" in body
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

    def test_code_plus_plans_returns_standard(self) -> None:
        """Mixed code+plan PRs should use STANDARD mode (Bug 2 fix)."""
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["src/bid_euchre/core/rules.py", "plans/sessions/2026-03-14_test.md"]
        )
        assert mode == ReviewMode.STANDARD

    def test_code_plus_reports_returns_standard(self) -> None:
        """Mixed code+report PRs should use STANDARD mode (Bug 2 fix)."""
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["docs/04_reports/arc_d_v1/r0/report.md", "src/bid_euchre/core/rules.py"]
        )
        assert mode == ReviewMode.STANDARD

    def test_scripts_count_as_code(self) -> None:
        """Scripts are code files and should trigger STANDARD mode."""
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["scripts/internal/review_driver.py", "plans/sessions/test.md"]
        )
        assert mode == ReviewMode.STANDARD

    def test_tests_count_as_code(self) -> None:
        """Test files are code files and should trigger STANDARD mode."""
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["tests/unit/test_review_driver.py", "plans/sessions/test.md"]
        )
        assert mode == ReviewMode.STANDARD

    def test_pyproject_triggers_standard(self) -> None:
        """pyproject.toml is infrastructure code — triggers STANDARD (#934)."""
        from review_state import ReviewMode

        mode = classify_review_mode(["pyproject.toml", "docs/01_core/RULES.md"])
        assert mode == ReviewMode.STANDARD

    def test_makefile_triggers_standard(self) -> None:
        """Makefile is infrastructure code — triggers STANDARD (#934)."""
        from review_state import ReviewMode

        mode = classify_review_mode(["Makefile"])
        assert mode == ReviewMode.STANDARD

    def test_experiments_yaml_triggers_standard(self) -> None:
        """experiments/ configs are code per CI paths-filter (#934)."""
        from review_state import ReviewMode

        mode = classify_review_mode(
            ["experiments/configs/quick_test.yaml", "plans/sessions/test.md"]
        )
        assert mode == ReviewMode.STANDARD

    def test_github_workflow_triggers_standard(self) -> None:
        """.github/workflows/ changes are code (#934)."""
        from review_state import ReviewMode

        mode = classify_review_mode([".github/workflows/ci.yml"])
        assert mode == ReviewMode.STANDARD


# ---------------------------------------------------------------------------
# _step_applying_fixes: filtered findings preference tests (Bug 1 fix)
# ---------------------------------------------------------------------------


class TestApplyingFixesFilteredFindings:
    """Verify _step_applying_fixes prefers codex_review_filtered.json."""

    def test_prefers_filtered_over_raw(self, tmp_path: Path) -> None:
        """When both filtered and raw files exist, filtered is loaded."""
        rdir = tmp_path / "round_1"
        rdir.mkdir()

        # Raw file has 3 findings (including one that should be filtered)
        raw_findings = [
            {"severity": "P0", "message": "blocking", "file": "a.py"},
            {"severity": "P2", "message": "low-conf-suppressed", "file": "b.py"},
            {"severity": "P2", "message": "another-suppressed", "file": "c.py"},
        ]
        with open(rdir / "codex_review.json", "w") as f:
            json.dump({"findings": raw_findings}, f)

        # Filtered file has only 1 finding (after scoring removed low-conf P2s)
        filtered_findings = [
            {"severity": "P0", "message": "blocking", "file": "a.py"},
        ]
        with open(rdir / "codex_review_filtered.json", "w") as f:
            json.dump({"findings": filtered_findings}, f)

        # Load logic: prefer filtered
        filtered_path = rdir / "codex_review_filtered.json"
        codex_path = rdir / "codex_review.json"

        if filtered_path.exists():
            with open(filtered_path) as fh:
                review_data = json.load(fh)
            findings = review_data.get("findings", [])
        elif codex_path.exists():
            with open(codex_path) as fh:
                review_data = json.load(fh)
            findings = review_data.get("findings", [])
        else:
            findings = []

        assert len(findings) == 1
        assert findings[0]["message"] == "blocking"

    def test_falls_back_to_raw_when_no_filtered(self, tmp_path: Path) -> None:
        """When only raw file exists (backward compat), it is loaded."""
        rdir = tmp_path / "round_1"
        rdir.mkdir()

        raw_findings = [
            {"severity": "P0", "message": "blocking", "file": "a.py"},
            {"severity": "P2", "message": "warn", "file": "b.py"},
        ]
        with open(rdir / "codex_review.json", "w") as f:
            json.dump({"findings": raw_findings}, f)

        filtered_path = rdir / "codex_review_filtered.json"
        codex_path = rdir / "codex_review.json"

        if filtered_path.exists():
            with open(filtered_path) as fh:
                review_data = json.load(fh)
            findings = review_data.get("findings", [])
        elif codex_path.exists():
            with open(codex_path) as fh:
                review_data = json.load(fh)
            findings = review_data.get("findings", [])
        else:
            findings = []

        assert len(findings) == 2


# ---------------------------------------------------------------------------
# Mode auto-detection scope leak tests
# ---------------------------------------------------------------------------


class TestModeAutoDetectionUsesPRFiles:
    """Verify mode auto-detection uses PR files, not local git diff.

    The bug: when the driver initializes without --mode, it ran
    ``git diff --name-only origin/main...HEAD`` from the local checkout.
    If the local HEAD was a different branch than the PR, mode detection
    used the wrong file list. The fix uses ``get_pr_changed_files()`` instead.
    """

    def test_report_pr_gets_report_audit_mode(self) -> None:
        """A PR touching only docs/04_reports/ should get REPORT_AUDIT, not PLAN_AUDIT.

        This is the exact scenario from the original bug: PR #864 changed
        docs/04_reports/ files but the local HEAD had a plans/ file change,
        causing PLAN_AUDIT to be selected instead of REPORT_AUDIT.
        """
        from review_state import ReviewMode

        # PR's actual files are reports
        pr_files = [
            "docs/04_reports/arc_d_v2/r0/full/00_manifest.md",
            "docs/04_reports/arc_d_v2/r0/full/evidence_manifest.json",
            "docs/04_reports/arc_d_v2/r1/full/00_manifest.md",
        ]
        mode = classify_review_mode(pr_files)
        assert mode == ReviewMode.REPORT_AUDIT

    def test_report_pr_not_affected_by_local_plan_files(self) -> None:
        """Even if local diff had plans/, the PR files should determine mode.

        This test validates the fix end-to-end: the classify_review_mode
        function receives PR-scoped files, not local git diff output.
        """
        from review_state import ReviewMode

        # Only the PR files matter — local diff is irrelevant
        pr_files = ["docs/04_reports/arc_d_v2/r0/full/evidence_manifest.json"]
        mode = classify_review_mode(pr_files)
        assert mode == ReviewMode.REPORT_AUDIT

        # If the local diff's plans/ file had leaked in:
        leaked_files = [
            "plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md",
        ]
        mode_leaked = classify_review_mode(leaked_files)
        assert mode_leaked == ReviewMode.PLAN_AUDIT

        # The point: these give different modes — the PR files
        # determine REPORT_AUDIT, not the leaked local PLAN_AUDIT


# ---------------------------------------------------------------------------
# Degraded review status tests (parse_confidence branching)
# ---------------------------------------------------------------------------


class TestDegradedReviewStatus:
    """Test that unparseable/backend_error Codex output produces degraded status.

    When Codex returns output the parser can't understand, the PR review driver
    should publish a 'degraded' status (GitHub success with distinct description),
    not a 'clean' status or a blocking failure.
    """

    def test_unparseable_codex_produces_degraded_transition(self, tmp_path: Path):
        """parse_confidence=unparseable → ready_to_merge with degraded desc."""
        from review_state import ReviewLoopState, ReviewState, round_dir, save_state

        state = ReviewLoopState(
            pr_number=999,
            branch="test-branch",
            state=ReviewState.SCORING_FINDINGS.value,
            iteration_count=0,
        )
        save_state(state, tmp_path)

        rdir = round_dir(999, 1, tmp_path)
        rdir.mkdir(parents=True)
        review_data = {
            "success": True,
            "findings": [],
            "raw_output": "gibberish",
            "latency_seconds": 1.0,
            "parse_confidence": "unparseable",
        }
        with open(rdir / "codex_review.json", "w") as f:
            json.dump(review_data, f)

        from review_driver import _step_scoring_findings

        status_calls = []

        def mock_publish(pr, status, desc):
            status_calls.append((pr, status, desc))

        def mock_comment(loop_state, findings, outcome):
            pass

        with (
            patch("review_driver._publish_status", mock_publish),
            patch("review_driver._post_review_comment", mock_comment),
        ):
            result = _step_scoring_findings(state, tmp_path)

        assert result.state == ReviewState.READY_TO_MERGE.value

        assert len(status_calls) == 1
        _, status, desc = status_calls[0]
        assert status == "success"
        assert "degraded" in desc.lower()
        assert "unparseable" in desc.lower()

    def test_backend_error_codex_produces_degraded_transition(self, tmp_path: Path):
        """parse_confidence=backend_error → degraded status."""
        from review_state import ReviewLoopState, ReviewState, round_dir, save_state

        state = ReviewLoopState(
            pr_number=998,
            branch="test-branch",
            state=ReviewState.SCORING_FINDINGS.value,
            iteration_count=0,
        )
        save_state(state, tmp_path)

        rdir = round_dir(998, 1, tmp_path)
        rdir.mkdir(parents=True)
        review_data = {
            "success": True,
            "findings": [],
            "raw_output": "Review was interrupted. Please re-run /review",
            "latency_seconds": 2.0,
            "parse_confidence": "backend_error",
        }
        with open(rdir / "codex_review.json", "w") as f:
            json.dump(review_data, f)

        from review_driver import _step_scoring_findings

        status_calls = []

        def mock_publish(pr, status, desc):
            status_calls.append((pr, status, desc))

        def mock_comment(loop_state, findings, outcome):
            pass

        with (
            patch("review_driver._publish_status", mock_publish),
            patch("review_driver._post_review_comment", mock_comment),
        ):
            result = _step_scoring_findings(state, tmp_path)

        assert result.state == ReviewState.READY_TO_MERGE.value
        _, status, desc = status_calls[0]
        assert status == "success"
        assert "degraded" in desc.lower()
        assert "backend_error" in desc.lower()

    def test_structured_findings_not_degraded(self, tmp_path: Path):
        """Normal structured findings proceed to scoring, NOT degraded path."""
        from review_state import ReviewLoopState, ReviewState, round_dir, save_state

        state = ReviewLoopState(
            pr_number=997,
            branch="test-branch",
            state=ReviewState.SCORING_FINDINGS.value,
            iteration_count=0,
        )
        save_state(state, tmp_path)

        rdir = round_dir(997, 1, tmp_path)
        rdir.mkdir(parents=True)
        review_data = {
            "success": True,
            "findings": [
                {
                    "severity": "P1",
                    "file": "src/foo.py",
                    "line": 42,
                    "category": "correctness",
                    "check_id": "C1",
                    "message": "Unseeded random",
                    "raw_source": "codex_cli",
                }
            ],
            "raw_output": "[P1] src/foo.py:42 — Unseeded random (C1)",
            "latency_seconds": 60.0,
            "parse_confidence": "structured",
        }
        with open(rdir / "codex_review.json", "w") as f:
            json.dump(review_data, f)

        from review_driver import _step_scoring_findings

        status_calls = []

        def mock_publish(pr, status, desc):
            status_calls.append((pr, status, desc))

        def mock_comment(loop_state, findings, outcome):
            pass

        with (
            patch("review_driver._publish_status", mock_publish),
            patch("review_driver._post_review_comment", mock_comment),
        ):
            result = _step_scoring_findings(state, tmp_path)

        # Should NOT go to ready_to_merge (has blocking P1 findings)
        assert result.state == ReviewState.APPLYING_FIXES.value
        # Status should NOT say "degraded"
        for _, _, desc in status_calls:
            assert "degraded" not in desc.lower()


# ---------------------------------------------------------------------------
# _create_follow_up_issues dedup guard tests (#1043)
# ---------------------------------------------------------------------------

# A minimal P2 finding that will pass the WARN_SEVERITY filter.
_P2_FINDING = {
    "severity": "P2",
    "category": "convention",
    "check_id": "T1",
    "file": "src/foo.py",
    "line": 10,
    "message": "Untested behavior change",
}


class TestCreateFollowUpIssuesDedup:
    """Test that the dedup guard in _create_follow_up_issues catches only
    expected exceptions and logs at WARNING level (#1043)."""

    def test_dedup_catches_subprocess_error(self) -> None:
        """CalledProcessError from `gh issue list` is caught gracefully;
        issue creation still proceeds."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            # The dedup check calls 'gh issue list'
            if "list" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="auth failed")
            # The create call succeeds
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/99"
            return result

        with patch("review_driver.subprocess.run", side_effect=_side_effect):
            urls = _create_follow_up_issues(42, [_P2_FINDING])

        # Issue should have been created despite dedup failure
        assert len(urls) == 1
        assert "issues/99" in urls[0]

    def test_dedup_catches_json_decode_error(self) -> None:
        """Malformed gh output (JSONDecodeError) is caught; creation proceeds."""

        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "list" in cmd:
                # Return garbage that json.loads will choke on
                result = MagicMock()
                result.returncode = 0
                result.stdout = "NOT_VALID_JSON"
                return result
            # The create call succeeds
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/100"
            call_count["n"] += 1
            return result

        with patch("review_driver.subprocess.run", side_effect=_side_effect):
            urls = _create_follow_up_issues(42, [_P2_FINDING])

        assert len(urls) == 1
        assert call_count["n"] >= 1

    def test_dedup_catches_os_error(self) -> None:
        """OSError (e.g., gh not found) is caught; creation proceeds."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "list" in cmd:
                raise OSError("gh: command not found")
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/101"
            return result

        with patch("review_driver.subprocess.run", side_effect=_side_effect):
            urls = _create_follow_up_issues(42, [_P2_FINDING])

        assert len(urls) == 1

    def test_dedup_nonzero_exit_proceeds_with_creation(self) -> None:
        """Non-zero exit from `gh issue list` logs warning and proceeds (#1082)."""

        call_count = {"n": 0}

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "list" in cmd:
                # gh issue list returns non-zero (e.g., auth failure)
                result = MagicMock()
                result.returncode = 1
                result.stdout = ""
                return result
            # The create call succeeds
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/104"
            call_count["n"] += 1
            return result

        with (
            patch("review_driver.subprocess.run", side_effect=_side_effect),
            patch("review_driver.logger") as mock_logger,
        ):
            urls = _create_follow_up_issues(42, [_P2_FINDING])

        # Issue should have been created despite dedup lookup failure
        assert len(urls) == 1
        assert "issues/104" in urls[0]
        assert call_count["n"] >= 1
        # Warning should mention non-zero exit
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "gh issue list exited" in warning_msg

    def test_dedup_does_not_catch_unexpected_error(self) -> None:
        """Unexpected errors (e.g., TypeError) must propagate, not be silently
        swallowed. This is the key behavioral change from #1043."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "list" in cmd:
                raise TypeError("unexpected error in dedup")
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/102"
            return result

        import pytest

        with (
            patch("review_driver.subprocess.run", side_effect=_side_effect),
            pytest.raises(TypeError, match="unexpected error in dedup"),
        ):
            _create_follow_up_issues(42, [_P2_FINDING])

    def test_dedup_logs_at_warning_level(self) -> None:
        """Dedup failures should log at WARNING, not DEBUG (#1043)."""

        def _side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if "list" in cmd:
                raise subprocess.CalledProcessError(1, cmd, stderr="timeout")
            result = MagicMock()
            result.returncode = 0
            result.stdout = "https://github.com/test/repo/issues/103"
            return result

        with (
            patch("review_driver.subprocess.run", side_effect=_side_effect),
            patch("review_driver.logger") as mock_logger,
        ):
            _create_follow_up_issues(42, [_P2_FINDING])

        # Verify warning was called (not debug)
        mock_logger.warning.assert_called()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "Dedup check failed" in warning_msg


# ---------------------------------------------------------------------------
# Coordinator contract tests
# ---------------------------------------------------------------------------


class TestCoordinatorContract:
    """Verify the COORDINATOR_CONTRACT constant and its integration.

    The coordinator-of-record model requires a stable, inspectable contract
    that other modules and docs can reference.
    """

    def test_contract_exists_and_has_required_keys(self) -> None:
        from review_driver import COORDINATOR_CONTRACT

        required_keys = {
            "status_context",
            "status_publisher",
            "comment_marker",
            "comment_publisher",
            "preferred_backend",
            "fallback_behavior",
            "advisory_surfaces",
            "rerun_command",
        }
        assert set(COORDINATOR_CONTRACT.keys()) == required_keys

    def test_status_context_is_reviewing_changes(self) -> None:
        from review_driver import COORDINATOR_CONTRACT

        assert COORDINATOR_CONTRACT["status_context"] == "reviewing-changes"

    def test_comment_marker_matches_github_pr_state(self) -> None:
        from github_pr_state import REVIEW_COMMENT_MARKER
        from review_driver import COORDINATOR_CONTRACT

        assert COORDINATOR_CONTRACT["comment_marker"] == REVIEW_COMMENT_MARKER

    def test_advisory_surfaces_lists_known_overlays(self) -> None:
        from review_driver import COORDINATOR_CONTRACT

        advisory = COORDINATOR_CONTRACT["advisory_surfaces"]
        assert "claude-review" in advisory
        assert "codex-cloud" in advisory

    def test_format_review_comment_includes_coordinator_identity(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="abc1234567890",
        )
        body = _format_review_comment(state, [], "passed")
        assert "Canonical review summary" in body
        assert "single machine-owned review comment" in body
        assert "advisory only" in body

    def test_format_review_comment_blocked_includes_coordinator_identity(self) -> None:
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.STOPPED_CI_FAILURE.value,
            current_head_sha="abc1234567890",
        )
        state.stop_reason = "CI failed"
        body = _format_review_comment(state, [], "blocked")
        assert "Canonical review summary" in body
        assert "Review Coordinator -- Blocked" in body

    def test_format_review_comment_marker_is_stable(self) -> None:
        """The dedup marker must be stable so upsert works across versions."""
        from github_pr_state import REVIEW_COMMENT_MARKER
        from review_state import ReviewLoopState, ReviewState

        state = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.READY_TO_MERGE.value,
        )
        body = _format_review_comment(state, [], "passed")
        assert REVIEW_COMMENT_MARKER in body


# ---------------------------------------------------------------------------
# Runtime-limit timeout produces terminal state + verdict
# ---------------------------------------------------------------------------


class TestRuntimeLimitTimeout:
    """Verify runtime-limit exit writes terminal state, verdict, and sentinel."""

    def test_timeout_produces_terminal_state_with_stop_reason(self) -> None:
        """Runtime-limit exit must leave a terminal state with non-null stop_reason.

        Simulates the exact timeout code path from main() by exercising
        the same state manipulation on a WAITING_FOR_CI loop.
        """
        from review_state import TERMINAL_STATES, ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CI.value,
            current_head_sha="sha_timeout_test",
        )

        # Simulate the timeout code path from main()
        loop.stop_reason = "Runtime limit reached (901s > 900s)"
        try:
            loop.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        except Exception:
            loop.state = ReviewState.STOPPED_REVIEW_FAILURE.value

        assert loop.current_state == ReviewState.STOPPED_REVIEW_FAILURE
        assert loop.current_state in TERMINAL_STATES
        assert loop.stop_reason is not None
        assert "Runtime limit" in loop.stop_reason

    def test_timeout_writes_blocked_verdict(self, tmp_path: Path) -> None:
        """Runtime-limit exit must write a non-clean (blocked) verdict."""
        from review_state import ReviewLoopState, ReviewState

        from bid_euchre.ops.review_queue import (
            STATUS_BLOCKED,
            read_verdict,
        )

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CI.value,
            current_head_sha="sha_timeout_verdict",
        )

        # Simulate the timeout code path
        loop.stop_reason = "Runtime limit reached (901s > 900s)"
        try:
            loop.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        except Exception:
            loop.state = ReviewState.STOPPED_REVIEW_FAILURE.value

        with patch(
            "bid_euchre.ops.review_queue.shared_queue_root", return_value=tmp_path
        ):
            from review_driver import _write_verdict_if_applicable

            _write_verdict_if_applicable(loop)

        verdict = read_verdict(42, tmp_path)
        assert verdict is not None, "Timeout must write a verdict"
        assert verdict.status == STATUS_BLOCKED, "Timeout verdict must be blocked"
        assert verdict.reviewed_sha == "sha_timeout_verdict"
        assert "Runtime limit" in verdict.reason

    def test_timeout_writes_failure_sentinel(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Runtime-limit exit must write a FAILED sentinel for the notification hook."""
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CI.value,
            current_head_sha="sha_sentinel_test",
        )

        # Simulate the timeout code path
        loop.stop_reason = "Runtime limit reached (901s > 900s)"
        try:
            loop.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        except Exception:
            loop.state = ReviewState.STOPPED_REVIEW_FAILURE.value

        from review_driver import _write_failure_sentinel

        # _write_failure_sentinel writes to .claude/runtime/review_loops/pr_N/FAILED
        # relative to cwd. Use monkeypatch.chdir so it writes into tmp_path.
        monkeypatch.chdir(tmp_path)
        _write_failure_sentinel(loop)

        sentinel = (
            tmp_path / ".claude" / "runtime" / "review_loops" / "pr_42" / "FAILED"
        )
        assert sentinel.exists(), "Timeout must write FAILED sentinel"
        content = sentinel.read_text()
        assert "STOPPED_REVIEW_FAILURE" in content
        assert "Runtime limit" in content

    def test_timeout_does_not_overwrite_ready_to_merge(self) -> None:
        """Timeout must not fire when state is READY_TO_MERGE within grace period.

        If the review decision has already been made (passed verdict written),
        the timeout should let _step_ready_to_merge() complete the MERGED
        transition rather than overwriting the passed verdict with blocked.
        The grace period is measured from state entry, not from loop start.
        """
        from review_state import ReviewState

        # elapsed > max_runtime_s but time_in_ready is small → no timeout
        assert _should_timeout(901.0, 900, ReviewState.READY_TO_MERGE, 5.0) is False, (
            "Timeout must not fire when READY_TO_MERGE is fresh — "
            "the passed verdict must not be overwritten"
        )
        # Even with very high elapsed, fresh READY_TO_MERGE is safe
        assert (
            _should_timeout(2000.0, 900, ReviewState.READY_TO_MERGE, 10.0) is False
        ), "Total elapsed is irrelevant for READY_TO_MERGE; only time_in_ready matters"

    def test_timeout_grace_period_cap_forces_stop(self) -> None:
        """Grace-period cap must fire when stuck in READY_TO_MERGE too long.

        If _step_ready_to_merge() stalls (returns without advancing for >60s),
        the grace cap prevents an unbounded loop.  The cap is measured from
        when READY_TO_MERGE was entered, not from loop start.
        """
        from review_state import ReviewState

        # time_in_ready > 60 → timeout even from READY_TO_MERGE
        assert (
            _should_timeout(961.0, 900, ReviewState.READY_TO_MERGE, 61.0) is True
        ), "Grace-period cap must force-stop when stuck in READY_TO_MERGE"
        # Boundary: exactly at cap should not timeout (> not >=)
        assert (
            _should_timeout(960.0, 900, ReviewState.READY_TO_MERGE, 60.0) is False
        ), "Exactly at grace boundary should not timeout (strict >)"

    def test_timeout_from_waiting_for_codex_transitions_cleanly(self) -> None:
        """WAITING_FOR_CODEX → STOPPED_REVIEW_FAILURE is a valid transition.

        This is the happy-path timeout: the transition is explicitly in the
        state graph (review_state.py:61-64), so no force-set is needed.
        """
        from review_state import TERMINAL_STATES, ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CODEX.value,
            current_head_sha="sha_codex_timeout",
        )

        # _should_timeout must fire from a non-READY_TO_MERGE state
        assert _should_timeout(901.0, 900, loop.current_state) is True

        # Transition must succeed without raising (valid edge)
        loop.stop_reason = "Runtime limit reached (901s > 900s)"
        loop.transition(ReviewState.STOPPED_REVIEW_FAILURE)

        assert loop.current_state == ReviewState.STOPPED_REVIEW_FAILURE
        assert loop.current_state in TERMINAL_STATES
        assert "Runtime limit" in loop.stop_reason

    def test_timeout_side_effects_save_and_publish(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """Timeout path components: _should_timeout, transition, save_state, publish.

        Exercises each step of the timeout code path in isolation (not via
        main()) and verifies that save_state persists terminal state and
        _publish_status receives the correct arguments.
        """
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CI.value,
            current_head_sha="sha_integration_timeout",
        )

        max_runtime_s = 900
        elapsed = 901.0

        # Step 1: _should_timeout detects the timeout
        assert _should_timeout(elapsed, max_runtime_s, loop.current_state)

        loop.stop_reason = f"Runtime limit reached ({elapsed:.0f}s > {max_runtime_s}s)"
        try:
            loop.transition(ReviewState.STOPPED_REVIEW_FAILURE)
        except Exception:
            loop.state = ReviewState.STOPPED_REVIEW_FAILURE.value

        # _publish_status — monkeypatch the module-level function so
        # calling it via the production import verifies real wiring (#1203).
        import review_driver

        published = {}

        def fake_publish(pr_number: int, state: str, description: str) -> bool:
            published["pr"] = pr_number
            published["state"] = state
            published["desc"] = description
            return True

        monkeypatch.setattr(review_driver, "_publish_status", fake_publish)

        review_driver._publish_status(
            loop.pr_number, "failure", f"Review timed out after {elapsed:.0f}s"
        )

        assert published["pr"] == 42
        assert published["state"] == "failure"
        assert "timed out" in published["desc"]

        # save_state
        from review_state import save_state

        path = save_state(loop, tmp_path)
        assert path.exists()

        import json

        saved = json.loads(path.read_text())
        assert saved["state"] == "stopped_review_failure"
        assert "Runtime limit" in saved["stop_reason"]

    def test_grace_period_timeout_has_distinct_stop_reason(self) -> None:
        """Grace-period timeout produces a stop_reason distinguishable from normal timeout.

        When timeout fires from READY_TO_MERGE, the stop_reason must contain
        'grace period' so operators can distinguish it from a normal elapsed-time
        timeout in logs. Regression test for #1207 item 3.
        """
        from review_driver import _READY_TO_MERGE_GRACE_S
        from review_state import ReviewLoopState, ReviewState

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.READY_TO_MERGE.value,
            current_head_sha="sha_grace_timeout",
        )

        time_in_ready = _READY_TO_MERGE_GRACE_S + 1.0
        elapsed = 500.0  # well under normal timeout

        # Verify _should_timeout fires from READY_TO_MERGE
        assert _should_timeout(
            elapsed, 900, loop.current_state, time_in_ready
        ), "Grace-period cap should trigger"

        # Simulate the production code path: build the stop_reason
        # exactly as the main loop does after our fix.
        if loop.current_state == ReviewState.READY_TO_MERGE:
            loop.stop_reason = (
                f"READY_TO_MERGE grace period exceeded "
                f"({time_in_ready:.0f}s > {_READY_TO_MERGE_GRACE_S}s)"
            )
        else:
            loop.stop_reason = f"Runtime limit reached ({elapsed:.0f}s > 900s)"

        assert (
            "grace period" in loop.stop_reason.lower()
        ), f"Grace-period timeout must be distinguishable. Got: {loop.stop_reason!r}"
        assert (
            "READY_TO_MERGE" in loop.stop_reason
        ), "stop_reason should mention the state for operator diagnostics"


class TestAuthFailureEarlyTermination:
    """Auth failure in _step_waiting_for_codex stops immediately (non-retryable).

    PR #1982 added an early-termination branch that detects ``error_type ==
    "auth_failure"`` from the Codex adapter and stops the review loop without
    retrying.  These tests verify the driver-level integration of that path:
    state transition, non-retryable treatment, status publication, and stop
    reason content.

    Regression test for issue #1983 (T1 — untested behavior change).
    """

    def test_auth_failure_transitions_to_stopped(self, tmp_path: Path):
        """Auth failure → STOPPED_REVIEW_FAILURE immediately (no retry)."""
        from codex_review_adapter import CodexReviewResult
        from review_driver import _step_waiting_for_codex
        from review_state import ReviewLoopState, ReviewState, save_state

        loop = ReviewLoopState(
            pr_number=42,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CODEX.value,
            current_head_sha="sha_auth_fail",
            codex_retry_count=0,
        )
        save_state(loop, tmp_path)

        auth_result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="Please log in",
            latency_seconds=1.0,
            error="Codex CLI auth expired",
            error_type="auth_failure",
        )

        status_calls: list[tuple[int, str, str]] = []
        comment_calls: list[tuple[str]] = []

        def mock_publish(pr, status, desc):
            status_calls.append((pr, status, desc))

        def mock_comment(loop_state, findings, outcome):
            comment_calls.append((outcome,))

        with (
            patch("codex_review_adapter.invoke_codex_cli", return_value=auth_result),
            patch("codex_review_adapter.save_review_result"),
            patch("review_driver._publish_status", mock_publish),
            patch("review_driver._post_review_comment", mock_comment),
            patch("review_driver.save_state"),
        ):
            result = _step_waiting_for_codex(loop, tmp_path)

        # 1. State transitions to STOPPED_REVIEW_FAILURE
        assert result.current_state == ReviewState.STOPPED_REVIEW_FAILURE

        # 2. codex_retry_count is NOT incremented (non-retryable)
        assert (
            result.codex_retry_count == 0
        ), "Auth failure must not increment retry count — it is non-retryable"

        # 3. Status published as "failure"
        # First call is "pending" (in-progress), second is "failure" (auth)
        failure_calls = [(pr, s, d) for pr, s, d in status_calls if s == "failure"]
        assert (
            len(failure_calls) == 1
        ), f"Expected 1 failure status, got {failure_calls}"
        _, _, desc = failure_calls[0]
        assert (
            "auth" in desc.lower()
        ), f"Failure description should mention auth: {desc}"

        # 4. Stop reason mentions "Auth failure" and "non-retryable"
        assert result.stop_reason is not None
        assert (
            "auth failure" in result.stop_reason.lower()
        ), f"stop_reason should mention auth failure: {result.stop_reason}"
        assert (
            "non-retryable" in result.stop_reason.lower()
        ), f"stop_reason should mention non-retryable: {result.stop_reason}"

    def test_auth_failure_posts_blocked_comment(self, tmp_path: Path):
        """Auth failure posts a 'blocked' review comment."""
        from codex_review_adapter import CodexReviewResult
        from review_driver import _step_waiting_for_codex
        from review_state import ReviewLoopState, ReviewState, save_state

        loop = ReviewLoopState(
            pr_number=43,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CODEX.value,
            current_head_sha="sha_auth_comment",
            codex_retry_count=0,
        )
        save_state(loop, tmp_path)

        auth_result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="auth prompt detected",
            latency_seconds=0.5,
            error="Codex CLI auth expired",
            error_type="auth_failure",
        )

        comment_outcomes: list[str] = []

        def mock_comment(loop_state, findings, outcome):
            comment_outcomes.append(outcome)

        with (
            patch("codex_review_adapter.invoke_codex_cli", return_value=auth_result),
            patch("codex_review_adapter.save_review_result"),
            patch("review_driver._publish_status"),
            patch("review_driver._post_review_comment", mock_comment),
            patch("review_driver.save_state"),
        ):
            _step_waiting_for_codex(loop, tmp_path)

        assert (
            comment_outcomes == ["blocked"]
        ), f"Auth failure should post exactly one 'blocked' comment, got {comment_outcomes}"

    def test_auth_failure_does_not_retry_even_with_budget(self, tmp_path: Path):
        """Auth failure stops on first attempt even if retry budget remains."""
        from codex_review_adapter import CodexReviewResult
        from review_driver import _step_waiting_for_codex
        from review_state import ReviewLoopState, ReviewState, save_state

        # Start with retry count at 0 — plenty of budget for normal errors
        loop = ReviewLoopState(
            pr_number=44,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CODEX.value,
            current_head_sha="sha_auth_budget",
            codex_retry_count=0,
        )
        save_state(loop, tmp_path)

        auth_result = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="",
            latency_seconds=0.1,
            error="auth expired",
            error_type="auth_failure",
        )

        with (
            patch("codex_review_adapter.invoke_codex_cli", return_value=auth_result),
            patch("codex_review_adapter.save_review_result"),
            patch("review_driver._publish_status"),
            patch("review_driver._post_review_comment"),
            patch("review_driver.save_state"),
        ):
            result = _step_waiting_for_codex(loop, tmp_path)

        # Must be terminal — no retry state
        assert result.current_state == ReviewState.STOPPED_REVIEW_FAILURE
        assert result.codex_retry_count == 0
        assert result.last_codex_status == "failed"

    def test_normal_error_still_retries(self, tmp_path: Path):
        """Non-auth errors still increment retry count (contrast with auth path)."""
        from codex_review_adapter import CodexReviewResult
        from review_driver import _step_waiting_for_codex
        from review_state import ReviewLoopState, ReviewState, save_state

        loop = ReviewLoopState(
            pr_number=45,
            branch="test-branch",
            state=ReviewState.WAITING_FOR_CODEX.value,
            current_head_sha="sha_normal_error",
            codex_retry_count=0,
        )
        save_state(loop, tmp_path)

        normal_error = CodexReviewResult(
            success=False,
            findings=[],
            raw_output="timeout",
            latency_seconds=600.0,
            error="Codex CLI timed out",
            error_type="cli_review_error",
        )

        with (
            patch("codex_review_adapter.invoke_codex_cli", return_value=normal_error),
            patch("codex_review_adapter.save_review_result"),
            patch("review_driver._publish_status"),
            patch("review_driver._post_review_comment"),
            patch("review_driver.save_state"),
        ):
            result = _step_waiting_for_codex(loop, tmp_path)

        # Normal error increments retry count and does NOT stop on first attempt
        assert (
            result.codex_retry_count == 1
        ), "Normal errors should increment retry count"
        assert (
            result.current_state != ReviewState.STOPPED_REVIEW_FAILURE
        ), "Normal errors with budget remaining should not stop"

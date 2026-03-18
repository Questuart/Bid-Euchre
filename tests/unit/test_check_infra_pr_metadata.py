"""Tests for the infra PR metadata checker (scripts/check_infra_pr_metadata.py)."""

from __future__ import annotations

from scripts.check_infra_pr_metadata import (
    check,
    check_infra_fields,
    has_infra_incident_section,
    is_infra_path,
)

# -- is_infra_path tests -----------------------------------------------------


class TestIsInfraPath:
    """Tests for the is_infra_path helper."""

    def test_workflow_file(self):
        assert is_infra_path(".github/workflows/ci.yml") is True

    def test_hook_file(self):
        assert is_infra_path(".claude/hooks/post-push-ci-check.sh") is True

    def test_scripts_internal(self):
        assert is_infra_path("scripts/internal/review_driver.py") is True

    def test_makefile(self):
        assert is_infra_path("Makefile") is True

    def test_src_not_infra(self):
        assert is_infra_path("src/bid_euchre/core/rules.py") is False

    def test_tests_not_infra(self):
        assert is_infra_path("tests/unit/test_rules.py") is False

    def test_top_level_scripts_not_infra(self):
        assert is_infra_path("scripts/lint_repo.py") is False

    def test_markdown_under_hooks_exempt(self):
        assert is_infra_path(".claude/hooks/README.md") is False

    def test_txt_under_workflows_exempt(self):
        assert is_infra_path(".github/workflows/notes.txt") is False


# -- has_infra_incident_section tests -----------------------------------------


class TestHasInfraIncidentSection:
    """Tests for PR body section detection."""

    def test_present(self):
        body = "## Summary\nStuff\n\n## Infra Incident\n- Issue: #123\n"
        assert has_infra_incident_section(body) is True

    def test_absent(self):
        body = "## Summary\nStuff\n\n## Tests\n- pytest\n"
        assert has_infra_incident_section(body) is False

    def test_case_insensitive(self):
        body = "## infra incident\n- Issue: #100\n"
        assert has_infra_incident_section(body) is True

    def test_extra_spaces(self):
        body = "##  Infra  Incident\n- Issue: #100\n"
        assert has_infra_incident_section(body) is True

    def test_empty_body(self):
        assert has_infra_incident_section("") is False


# -- check_infra_fields tests ------------------------------------------------


class TestCheckInfraFields:
    """Tests for field validation within the Infra Incident section."""

    def test_all_fields_present(self):
        body = (
            "## Infra Incident\n"
            "- Issue: #123\n"
            "- Regression test: tests/unit/test_ci.py\n"
        )
        assert check_infra_fields(body) == []

    def test_missing_issue(self):
        body = "## Infra Incident\n- Issue:\n- Regression test: tests/unit/test_ci.py\n"
        missing = check_infra_fields(body)
        assert "Issue" in missing

    def test_missing_regression_test(self):
        body = "## Infra Incident\n- Issue: #123\n- Regression test:\n"
        missing = check_infra_fields(body)
        assert "Regression test" in missing

    def test_all_fields_empty(self):
        body = "## Infra Incident\n- Issue:\n- Regression test:\n"
        missing = check_infra_fields(body)
        assert len(missing) == 2


# -- check() integration tests -----------------------------------------------


class TestCheck:
    """Tests for the top-level check() function."""

    def test_no_infra_files_returns_no_warnings(self):
        has_infra, warnings = check(
            "## Summary\nStuff",
            ["src/bid_euchre/core/rules.py", "tests/unit/test_rules.py"],
        )
        assert has_infra is False
        assert warnings == []

    def test_infra_files_no_section_warns(self):
        has_infra, warnings = check(
            "## Summary\nFixed CI",
            [".github/workflows/ci.yml"],
        )
        assert has_infra is True
        assert len(warnings) == 1
        assert "Infra Incident" in warnings[0]

    def test_infra_files_with_complete_section_passes(self):
        body = (
            "## Summary\nFixed CI\n\n"
            "## Infra Incident\n"
            "- Issue: #100\n"
            "- First occurrence or repeat: repeat\n"
            "- Regression test: tests/unit/test_ci.py\n"
            "- Detection/logging note: CI logs\n"
        )
        has_infra, warnings = check(body, [".github/workflows/ci.yml"])
        assert has_infra is True
        assert warnings == []

    def test_infra_files_with_incomplete_section_warns(self):
        body = (
            "## Summary\nFixed CI\n\n## Infra Incident\n- Issue:\n- Regression test:\n"
        )
        has_infra, warnings = check(body, ["scripts/internal/ci_poller.sh"])
        assert has_infra is True
        assert len(warnings) == 1
        assert "missing" in warnings[0].lower()

    def test_makefile_triggers_check(self):
        has_infra, warnings = check("## Summary\nUpdated build", ["Makefile"])
        assert has_infra is True
        assert len(warnings) == 1

    def test_doc_only_infra_change_exempt(self):
        """Markdown files under infra paths don't trigger the check."""
        has_infra, warnings = check(
            "## Summary\nUpdated README",
            [".claude/hooks/README.md"],
        )
        assert has_infra is False
        assert warnings == []

    def test_multiple_infra_files_counted(self):
        has_infra, warnings = check(
            "## Summary\nBig refactor",
            [
                ".github/workflows/ci.yml",
                "scripts/internal/review_driver.py",
                "Makefile",
            ],
        )
        assert has_infra is True
        assert "3 infra file(s)" in warnings[0]

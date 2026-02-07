"""
Tests for generate_report.py sanity gate functionality.

Tests the summarize_sanity_results helper function that powers:
1. Status counting for console output
2. Canonical summary JSON/MD generation
3. --fail-on-sanity-failures gate logic
"""

from generate_report import summarize_sanity_results

# We need to import SanityTestResult from the actual module
from bid_euchre.diagnostics.sanity_tests import SanityTestResult


class TestSummarizeSanityResults:
    """Tests for summarize_sanity_results helper."""

    def test_counts_all_statuses(self):
        """Correctly counts PASS, WARN, FAIL, SKIP."""
        results = {
            "test_pass_1": SanityTestResult(
                name="test_pass_1", status="PASS", message="ok", details={}
            ),
            "test_pass_2": SanityTestResult(
                name="test_pass_2", status="PASS", message="ok", details={}
            ),
            "test_warn": SanityTestResult(
                name="test_warn", status="WARN", message="warning", details={}
            ),
            "test_fail": SanityTestResult(
                name="test_fail", status="FAIL", message="failed", details={}
            ),
            "test_skip_1": SanityTestResult(
                name="test_skip_1", status="SKIP", message="skipped", details={}
            ),
            "test_skip_2": SanityTestResult(
                name="test_skip_2", status="SKIP", message="skipped", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert summary["pass_count"] == 2
        assert summary["warn_count"] == 1
        assert summary["fail_count"] == 1
        assert summary["skip_count"] == 2

    def test_identifies_failing_tests(self):
        """Lists names of tests with FAIL status."""
        results = {
            "test_ok": SanityTestResult(
                name="test_ok", status="PASS", message="ok", details={}
            ),
            "test_fail_one": SanityTestResult(
                name="test_fail_one", status="FAIL", message="failed", details={}
            ),
            "test_fail_two": SanityTestResult(
                name="test_fail_two", status="FAIL", message="also failed", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert len(summary["failing_tests"]) == 2
        assert "test_fail_one" in summary["failing_tests"]
        assert "test_fail_two" in summary["failing_tests"]
        assert "test_ok" not in summary["failing_tests"]

    def test_all_passed_true_when_no_fails(self):
        """all_passed=True when fail_count == 0."""
        results = {
            "test_pass": SanityTestResult(
                name="test_pass", status="PASS", message="ok", details={}
            ),
            "test_warn": SanityTestResult(
                name="test_warn", status="WARN", message="warning", details={}
            ),
            "test_skip": SanityTestResult(
                name="test_skip", status="SKIP", message="skipped", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert summary["all_passed"] is True
        assert summary["fail_count"] == 0

    def test_all_passed_false_when_fails(self):
        """all_passed=False when fail_count > 0."""
        results = {
            "test_pass": SanityTestResult(
                name="test_pass", status="PASS", message="ok", details={}
            ),
            "test_fail": SanityTestResult(
                name="test_fail", status="FAIL", message="failed", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert summary["all_passed"] is False
        assert summary["fail_count"] == 1

    def test_empty_results(self):
        """Handles empty results dict (all counts 0, all_passed=True)."""
        summary = summarize_sanity_results({})

        assert summary["pass_count"] == 0
        assert summary["warn_count"] == 0
        assert summary["fail_count"] == 0
        assert summary["skip_count"] == 0
        assert summary["failing_tests"] == []
        assert summary["all_passed"] is True

    def test_only_passes(self):
        """All PASS results yields all_passed=True."""
        results = {
            "test_1": SanityTestResult(
                name="test_1", status="PASS", message="ok", details={}
            ),
            "test_2": SanityTestResult(
                name="test_2", status="PASS", message="ok", details={}
            ),
            "test_3": SanityTestResult(
                name="test_3", status="PASS", message="ok", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert summary["pass_count"] == 3
        assert summary["warn_count"] == 0
        assert summary["fail_count"] == 0
        assert summary["skip_count"] == 0
        assert summary["all_passed"] is True
        assert summary["failing_tests"] == []

    def test_only_fails(self):
        """All FAIL results yields all_passed=False with all tests in failing_tests."""
        results = {
            "test_fail_a": SanityTestResult(
                name="test_fail_a", status="FAIL", message="failed", details={}
            ),
            "test_fail_b": SanityTestResult(
                name="test_fail_b", status="FAIL", message="failed", details={}
            ),
        }

        summary = summarize_sanity_results(results)

        assert summary["pass_count"] == 0
        assert summary["fail_count"] == 2
        assert summary["all_passed"] is False
        assert len(summary["failing_tests"]) == 2

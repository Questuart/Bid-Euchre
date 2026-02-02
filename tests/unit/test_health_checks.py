"""Unit tests for health check filtering and display functions."""

from bid_euchre.diagnostics.health_checks import (
    CheckResult,
    HealthScorecard,
    display_issues,
)


def test_get_warnings_filters_correctly():
    """Test that get_warnings returns only WARN status checks."""
    scorecard = HealthScorecard(
        checks=[
            CheckResult(name="check1", status="PASS", message="All good"),
            CheckResult(name="check2", status="WARN", message="Minor issue"),
            CheckResult(name="check3", status="FAIL", message="Critical error"),
            CheckResult(name="check4", status="WARN", message="Another warning"),
        ]
    )

    warnings = scorecard.get_warnings()

    assert len(warnings) == 2
    assert all(c.status == "WARN" for c in warnings)
    assert warnings[0].name == "check2"
    assert warnings[1].name == "check4"


def test_get_failures_filters_correctly():
    """Test that get_failures returns only FAIL status checks."""
    scorecard = HealthScorecard(
        checks=[
            CheckResult(name="check1", status="PASS", message="All good"),
            CheckResult(name="check2", status="WARN", message="Minor issue"),
            CheckResult(name="check3", status="FAIL", message="Critical error"),
            CheckResult(name="check4", status="FAIL", message="Another failure"),
        ]
    )

    failures = scorecard.get_failures()

    assert len(failures) == 2
    assert all(c.status == "FAIL" for c in failures)
    assert failures[0].name == "check3"
    assert failures[1].name == "check4"


def test_display_issues_empty_when_no_issues():
    """Test that display_issues returns empty string when all checks pass."""
    scorecard = HealthScorecard(
        checks=[
            CheckResult(name="check1", status="PASS", message="All good"),
            CheckResult(name="check2", status="PASS", message="Also good"),
        ]
    )

    result = display_issues(scorecard)

    assert result == ""


def test_display_issues_shows_failures_before_warnings():
    """Test that failures appear before warnings in display_issues output."""
    scorecard = HealthScorecard(
        checks=[
            CheckResult(name="check1", status="PASS", message="All good"),
            CheckResult(name="check2", status="WARN", message="Minor issue"),
            CheckResult(name="check3", status="FAIL", message="Critical error"),
            CheckResult(name="check4", status="WARN", message="Another warning"),
        ]
    )

    result = display_issues(scorecard)

    assert result != ""
    lines = result.split("\n")
    assert lines[0] == "Issues found:"

    # Check that failures appear before warnings in the output
    # Find indices of failure and warning lines
    fail_indices = [i for i, line in enumerate(lines) if "❌" in line]
    warn_indices = [i for i, line in enumerate(lines) if "⚠️" in line]

    assert len(fail_indices) == 1
    assert len(warn_indices) == 2
    assert all(f_idx < w_idx for f_idx in fail_indices for w_idx in warn_indices)


def test_display_issues_includes_check_names_and_messages():
    """Test that display_issues includes both check name and message."""
    scorecard = HealthScorecard(
        checks=[
            CheckResult(
                name="feature_variance",
                status="WARN",
                message="2 feature(s) have zero variance",
            ),
        ]
    )

    result = display_issues(scorecard)

    assert "feature_variance" in result
    assert "2 feature(s) have zero variance" in result
    assert "⚠️" in result

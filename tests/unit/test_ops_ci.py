"""Tests for ops/ci.py — CI failure classification and status polling."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from bid_euchre.ops.ci import (
    CI_FAILURE_CLASSES,
    CICheckResult,
    CIFailureClassification,
    CIStatusReport,
    classify_ci_failure,
    emit_ci_events,
    format_ci_json,
    format_ci_text,
    poll_ci_status,
)

# --- Helper ---


def _mock_result(returncode: int = 0, stdout: str = "", stderr: str = "") -> object:
    """Create a mock subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


# --- Classification tests (pure Python, no mocking needed) ---


class TestClassifyCIFailure:
    """Tests for classify_ci_failure() — pure Python classification."""

    # --- Lint/format ---

    def test_ruff_check(self) -> None:
        result = classify_ci_failure("ruff check found 3 errors")
        assert result.failure_class == "lint_format"
        assert result.auto_remediable is True

    def test_ruff_format(self) -> None:
        result = classify_ci_failure("ruff format --check failed")
        assert result.failure_class == "lint_format"

    def test_black_check(self) -> None:
        result = classify_ci_failure("black --check failed: would reformat 2 files")
        assert result.failure_class == "lint_format"

    def test_ruff_error_code(self) -> None:
        result = classify_ci_failure("E501 line too long")
        assert result.failure_class == "lint_format"

    def test_pyflakes_code(self) -> None:
        result = classify_ci_failure("F401 imported but unused")
        assert result.failure_class == "lint_format"

    def test_formatting_differ(self) -> None:
        result = classify_ci_failure("formatting would differ in 3 files")
        assert result.failure_class == "lint_format"

    # --- Deterministic test ---

    def test_pytest_failed(self) -> None:
        result = classify_ci_failure("FAILED tests/unit/test_foo.py::test_bar")
        assert result.failure_class == "deterministic_test"
        assert result.auto_remediable is True

    def test_pytest_errors(self) -> None:
        result = classify_ci_failure("== 1 FAILED, 2 ERRORS ==")
        assert result.failure_class == "deterministic_test"

    def test_assertion_error(self) -> None:
        result = classify_ci_failure("AssertionError: expected 5 got 3")
        assert result.failure_class == "deterministic_test"

    def test_test_failed_message(self) -> None:
        result = classify_ci_failure("3 tests failed")
        assert result.failure_class == "deterministic_test"

    # --- Missing config ---

    def test_module_not_found(self) -> None:
        result = classify_ci_failure("ModuleNotFoundError: No module named 'foo'")
        assert result.failure_class == "missing_config"
        assert result.auto_remediable is True

    def test_file_not_found(self) -> None:
        result = classify_ci_failure("FileNotFoundError: config.yaml")
        assert result.failure_class == "missing_config"

    def test_no_such_file(self) -> None:
        result = classify_ci_failure(
            "No such file or directory: 'data/fixtures/test.json'"
        )
        assert result.failure_class == "missing_config"

    def test_import_error(self) -> None:
        result = classify_ci_failure("ImportError: cannot import name 'Foo'")
        assert result.failure_class == "missing_config"

    # --- Flaky/external ---

    def test_timeout(self) -> None:
        result = classify_ci_failure("TimeoutError: connection timed out")
        assert result.failure_class == "flaky_external"
        assert result.auto_remediable is False

    def test_connection_refused(self) -> None:
        result = classify_ci_failure("ConnectionError: connection refused")
        assert result.failure_class == "flaky_external"

    def test_http_error(self) -> None:
        result = classify_ci_failure("HTTPError: HTTP 503 Service Unavailable")
        assert result.failure_class == "flaky_external"

    def test_rate_limit(self) -> None:
        result = classify_ci_failure("rate limit exceeded, retry later")
        assert result.failure_class == "flaky_external"

    # --- Infra/auth ---

    def test_permission_denied(self) -> None:
        result = classify_ci_failure("PermissionError: permission denied")
        assert result.failure_class == "infra_auth"
        assert result.auto_remediable is False

    def test_credentials_expired(self) -> None:
        result = classify_ci_failure("credentials expired")
        assert result.failure_class == "infra_auth"

    def test_token_invalid(self) -> None:
        result = classify_ci_failure("token invalid or expired")
        assert result.failure_class == "infra_auth"

    def test_auth_failed(self) -> None:
        result = classify_ci_failure("authentication failed for user foo")
        assert result.failure_class == "infra_auth"

    # --- Risky/destructive ---

    def test_force_push(self) -> None:
        result = classify_ci_failure("git push --force origin main")
        assert result.failure_class == "risky_destructive"
        assert result.auto_remediable is False

    def test_reset_hard(self) -> None:
        result = classify_ci_failure("git reset --hard HEAD~1")
        assert result.failure_class == "risky_destructive"

    def test_rm_rf_root(self) -> None:
        result = classify_ci_failure("rm -rf /important/data")
        assert result.failure_class == "risky_destructive"

    # --- Fallback (log_output mode) ---

    def test_unknown_output_falls_back_to_deterministic_test(self) -> None:
        result = classify_ci_failure("something unexpected happened")
        assert result.failure_class == "deterministic_test"
        assert result.details == "No specific pattern matched"

    def test_empty_output_falls_back(self) -> None:
        result = classify_ci_failure("")
        assert result.failure_class == "deterministic_test"

    # --- name_only evidence level ---

    def test_name_only_with_matching_pattern(self) -> None:
        """Name-only still classifies when the name contains a pattern."""
        result = classify_ci_failure("ruff check", evidence_level="name_only")
        assert result.failure_class == "lint_format"

    def test_name_only_generic_falls_to_unclassified(self) -> None:
        """Generic job name like 'tests' should NOT guess a class."""
        result = classify_ci_failure("tests", evidence_level="name_only")
        assert result.failure_class == "unclassified"
        assert result.auto_remediable is False
        assert "tests" in result.details

    def test_name_only_unknown_falls_to_unclassified(self) -> None:
        result = classify_ci_failure("build", evidence_level="name_only")
        assert result.failure_class == "unclassified"

    # --- Classification output structure ---

    def test_classification_has_all_fields(self) -> None:
        result = classify_ci_failure("ruff check failed")
        assert isinstance(result.failure_class, str)
        assert isinstance(result.auto_remediable, bool)
        assert isinstance(result.description, str)
        assert isinstance(result.details, str)
        assert isinstance(result.remediation_hint, str)

    def test_to_dict(self) -> None:
        result = classify_ci_failure("ruff check failed")
        d = result.to_dict()
        assert d["failure_class"] == "lint_format"
        assert "auto_remediable" in d
        assert "remediation_hint" in d


class TestCIFailureClasses:
    """Tests for CI_FAILURE_CLASSES taxonomy."""

    def test_all_classes_have_required_keys(self) -> None:
        for name, meta in CI_FAILURE_CLASSES.items():
            assert "auto_remediable" in meta, f"{name} missing auto_remediable"
            assert "max_retries" in meta, f"{name} missing max_retries"
            assert "description" in meta, f"{name} missing description"
            assert "hint" in meta, f"{name} missing hint"

    def test_expected_classes_exist(self) -> None:
        expected = {
            "lint_format",
            "deterministic_test",
            "missing_config",
            "flaky_external",
            "infra_auth",
            "risky_destructive",
            "unclassified",
        }
        assert set(CI_FAILURE_CLASSES.keys()) == expected

    def test_auto_remediable_classes(self) -> None:
        auto = {k for k, v in CI_FAILURE_CLASSES.items() if v["auto_remediable"]}
        assert auto == {"lint_format", "deterministic_test", "missing_config"}

    def test_non_remediable_classes(self) -> None:
        manual = {k for k, v in CI_FAILURE_CLASSES.items() if not v["auto_remediable"]}
        assert manual == {
            "flaky_external",
            "infra_auth",
            "risky_destructive",
            "unclassified",
        }


# --- poll_ci_status tests (mocked gh) ---


class TestPollCIStatus:
    """Tests for poll_ci_status() with mocked gh CLI."""

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_all_success(self, mock_run: object) -> None:
        checks = [
            {"name": "tests", "state": "SUCCESS"},
            {"name": "prechecks", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(100)
        assert report.pr_number == 100
        assert report.overall == "success"
        assert len(report.checks) == 2
        assert report.classifications == []

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_failure_classified(self, mock_run: object) -> None:
        checks = [
            {"name": "tests", "state": "FAILURE"},
            {"name": "prechecks", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(200)
        assert report.overall == "failure"
        assert len(report.classifications) == 1
        # "tests" is a generic name — name_only evidence → unclassified
        assert report.classifications[0].failure_class == "unclassified"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_prechecks_failure_classified(self, mock_run: object) -> None:
        """Prechecks failure is classified (prechecks is in CI allowlist)."""
        checks = [
            {"name": "prechecks", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(300)
        assert report.overall == "failure"
        assert len(report.classifications) == 1

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_non_allowlisted_check_excluded(self, mock_run: object) -> None:
        """Checks not in the CI allowlist are excluded from the report."""
        checks = [
            {"name": "ruff check", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(300)
        # "ruff check" is not in CI_CHECK_NAMES, so it's excluded
        assert report.overall == "success"
        assert len(report.checks) == 1
        assert report.checks[0].name == "tests"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_pending_checks(self, mock_run: object) -> None:
        checks = [
            {"name": "tests", "state": "PENDING"},
            {"name": "prechecks", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(400)
        assert report.overall == "pending"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_excludes_reviewing_changes(self, mock_run: object) -> None:
        checks = [
            {"name": "reviewing-changes", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(500)
        assert report.overall == "success"
        assert len(report.checks) == 1
        assert report.checks[0].name == "tests"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_gh_failure_returns_unknown(self, mock_run: object) -> None:
        mock_run.return_value = _mock_result(returncode=1, stderr="error")

        report = poll_ci_status(600)
        assert report.overall == "unknown"
        assert report.checks == []

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_invalid_json_returns_unknown(self, mock_run: object) -> None:
        mock_run.return_value = _mock_result(stdout="not json{")

        report = poll_ci_status(700)
        assert report.overall == "unknown"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_empty_checks_returns_pending(self, mock_run: object) -> None:
        mock_run.return_value = _mock_result(stdout="[]")

        report = poll_ci_status(800)
        assert report.overall == "pending"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_default_excludes_claude_review(self, mock_run: object) -> None:
        """Default (None) excludes claude-review from CI checks."""
        checks = [
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(901)
        assert report.overall == "success"
        assert len(report.checks) == 1
        assert report.checks[0].name == "tests"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_default_excludes_both_non_ci(self, mock_run: object) -> None:
        """Default excludes both reviewing-changes and claude-review."""
        checks = [
            {"name": "reviewing-changes", "state": "FAILURE"},
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(902)
        assert report.overall == "success"
        assert len(report.checks) == 1

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_explicit_override_uses_old_logic(self, mock_run: object) -> None:
        """Explicit review_contexts uses old exclusion logic."""
        checks = [
            {"name": "claude-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        # Only excluding reviewing-changes, so claude-review counts as CI
        report = poll_ci_status(903, review_contexts=("reviewing-changes",))
        assert report.overall == "failure"
        assert len(report.checks) == 2

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_custom_review_context_excluded(self, mock_run: object) -> None:
        """Custom review contexts are excluded from CI checks."""
        checks = [
            {"name": "codex-review", "state": "FAILURE"},
            {"name": "tests", "state": "SUCCESS"},
        ]
        mock_run.return_value = _mock_result(stdout=json.dumps(checks))

        report = poll_ci_status(900)
        assert report.overall == "success"
        assert len(report.checks) == 1
        assert report.checks[0].name == "tests"

    @patch("bid_euchre.ops.ci.subprocess.run")
    def test_timeout_returns_unknown(self, mock_run: object) -> None:
        """Timeout on gh CLI returns unknown status."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)

        report = poll_ci_status(999)
        assert report.overall == "unknown"
        assert report.checks == []


# --- Formatting tests ---


class TestFormatCIText:
    """Tests for format_ci_text()."""

    def test_success_report(self) -> None:
        report = CIStatusReport(
            pr_number=42,
            overall="success",
            checks=[
                CICheckResult(name="tests", state="SUCCESS"),
                CICheckResult(name="lint", state="SUCCESS"),
            ],
            classifications=[],
        )
        text = format_ci_text(report)
        assert "PR #42" in text
        assert "success" in text
        assert "[+] tests" in text
        assert "[+] lint" in text

    def test_failure_report(self) -> None:
        classification = CIFailureClassification(
            failure_class="lint_format",
            auto_remediable=True,
            description="Linting failure",
            details="ruff check",
            remediation_hint="Run make lint",
        )
        report = CIStatusReport(
            pr_number=99,
            overall="failure",
            checks=[
                CICheckResult(
                    name="lint", state="FAILURE", classification=classification
                ),
            ],
            classifications=[classification],
        )
        text = format_ci_text(report)
        assert "failure" in text
        assert "[x] lint" in text
        assert "lint_format" in text
        assert "Linting failure" in text

    def test_no_checks(self) -> None:
        report = CIStatusReport(
            pr_number=1, overall="unknown", checks=[], classifications=[]
        )
        text = format_ci_text(report)
        assert "No checks found" in text


class TestFormatCIJSON:
    """Tests for format_ci_json()."""

    def test_serializable(self) -> None:
        report = CIStatusReport(
            pr_number=42,
            overall="success",
            checks=[CICheckResult(name="tests", state="SUCCESS")],
            classifications=[],
        )
        result = format_ci_json(report)
        assert result["pr_number"] == 42
        assert result["overall"] == "success"
        # Verify JSON-serializable
        json.dumps(result)

    def test_with_classification(self) -> None:
        classification = CIFailureClassification(
            failure_class="lint_format",
            auto_remediable=True,
            description="Lint",
            details="ruff",
            remediation_hint="fix",
        )
        report = CIStatusReport(
            pr_number=1,
            overall="failure",
            checks=[
                CICheckResult(
                    name="lint", state="FAILURE", classification=classification
                )
            ],
            classifications=[classification],
        )
        result = format_ci_json(report)
        assert len(result["classifications"]) == 1
        assert result["classifications"][0]["failure_class"] == "lint_format"
        json.dumps(result)


# --- emit_ci_events tests (#928) ---


class TestEmitCIEvents:
    """Tests for emit_ci_events() -- CI event producer for watchdogs (#928)."""

    @pytest.fixture()
    def events_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "events"
        d.mkdir()
        return d

    def test_failure_emits_ci_failure(self, events_dir: Path) -> None:
        classification = CIFailureClassification(
            failure_class="lint_format",
            auto_remediable=True,
            description="Lint failure",
            details="ruff check",
            remediation_hint="Run make lint",
        )
        report = CIStatusReport(
            pr_number=42,
            overall="failure",
            checks=[
                CICheckResult(
                    name="lint", state="FAILURE", classification=classification
                ),
            ],
            classifications=[classification],
        )
        result = emit_ci_events(report, "author-a", events_dir)
        assert result is not None
        assert result["event_type"] == "ci_failure"
        assert result["lane_id"] == "author-a"
        assert result["source"] == "ops.ci"
        assert result["payload"]["pr_number"] == 42
        assert result["payload"]["failure_class"] == "lint_format"

    def test_success_emits_ci_success(self, events_dir: Path) -> None:
        report = CIStatusReport(
            pr_number=99,
            overall="success",
            checks=[CICheckResult(name="tests", state="SUCCESS")],
            classifications=[],
        )
        result = emit_ci_events(report, "author-b", events_dir)
        assert result is not None
        assert result["event_type"] == "ci_success"
        assert result["payload"]["pr_number"] == 99

    def test_pending_returns_none(self, events_dir: Path) -> None:
        report = CIStatusReport(
            pr_number=50,
            overall="pending",
            checks=[CICheckResult(name="tests", state="PENDING")],
            classifications=[],
        )
        result = emit_ci_events(report, "author-a", events_dir)
        assert result is None

    def test_unknown_returns_none(self, events_dir: Path) -> None:
        report = CIStatusReport(
            pr_number=60,
            overall="unknown",
            checks=[],
            classifications=[],
        )
        result = emit_ci_events(report, "ops", events_dir)
        assert result is None

    def test_event_persisted_to_jsonl(self, events_dir: Path) -> None:
        """Verify the emitted event is actually readable from the log."""
        from bid_euchre.ops.events import read_events

        report = CIStatusReport(
            pr_number=77,
            overall="success",
            checks=[CICheckResult(name="tests", state="SUCCESS")],
            classifications=[],
        )
        emit_ci_events(report, "author-a", events_dir)

        events = read_events(events_dir)
        assert len(events) == 1
        assert events[0]["event_type"] == "ci_success"
        assert events[0]["payload"]["pr_number"] == 77

    def test_multiple_failure_classes_joined(self, events_dir: Path) -> None:
        """Multiple failure classifications are joined in the payload."""
        cls1 = CIFailureClassification(
            failure_class="lint_format",
            auto_remediable=True,
            description="Lint",
            details="ruff",
            remediation_hint="fix",
        )
        cls2 = CIFailureClassification(
            failure_class="deterministic_test",
            auto_remediable=True,
            description="Test failure",
            details="pytest",
            remediation_hint="fix tests",
        )
        report = CIStatusReport(
            pr_number=88,
            overall="failure",
            checks=[
                CICheckResult(name="lint", state="FAILURE", classification=cls1),
                CICheckResult(name="tests", state="FAILURE", classification=cls2),
            ],
            classifications=[cls1, cls2],
        )
        result = emit_ci_events(report, "author-a", events_dir)
        assert result is not None
        # Classes sorted alphabetically
        assert result["payload"]["failure_class"] == "deterministic_test, lint_format"


class TestCICheckNamesConsistency:
    """Verify CI classification constants are consistent."""

    def test_ci_check_names_accessible(self) -> None:
        """CI_CHECK_NAMES allowlist is importable and has expected members."""
        from bid_euchre.ops import CI_CHECK_NAMES

        assert "tests" in CI_CHECK_NAMES
        assert "prechecks" in CI_CHECK_NAMES
        assert "governance" in CI_CHECK_NAMES
        assert "reviewing-changes" not in CI_CHECK_NAMES

    def test_classify_check_consistent_with_non_ci(self) -> None:
        """classify_check categorizes review/advisory contexts as non-CI."""
        from bid_euchre.ops import classify_check

        assert classify_check("reviewing-changes") == "review_gate"
        assert classify_check("claude-review") == "advisory"
        assert classify_check("tests") == "ci"
        assert classify_check("prechecks") == "ci"

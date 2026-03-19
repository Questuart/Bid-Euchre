"""CI status polling and failure classification.

Classifies CI check failures into actionable categories with
remediation hints. Classification logic is pure Python — fully
testable without GitHub access.

The ``poll_ci_status()`` function wraps ``gh pr checks`` for
per-check breakdown.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass

logger = logging.getLogger("ops.ci")


# --- Failure classification taxonomy ---

CI_FAILURE_CLASSES: dict[str, dict] = {
    "lint_format": {
        "auto_remediable": True,
        "max_retries": 3,
        "description": "Linting or formatting failure (ruff, black, etc.)",
        "hint": "Run `make lint` or `ruff check --fix && ruff format`",
    },
    "deterministic_test": {
        "auto_remediable": True,
        "max_retries": 3,
        "description": "Deterministic test failure (pytest)",
        "hint": "Run the failing test locally with `uv run python -m pytest <test_file> -v`",
    },
    "missing_config": {
        "auto_remediable": True,
        "max_retries": 2,
        "description": "Missing configuration, fixture, or dependency",
        "hint": "Check for missing files or unsynced dependencies (`make sync`)",
    },
    "flaky_external": {
        "auto_remediable": False,
        "max_retries": 1,
        "description": "Flaky or external-dependency failure (network, API)",
        "hint": "Retry once; if persistent, check external service status",
    },
    "infra_auth": {
        "auto_remediable": False,
        "max_retries": 0,
        "description": "Infrastructure or authentication failure",
        "hint": "Check CI runner credentials, tokens, and permissions",
    },
    "risky_destructive": {
        "auto_remediable": False,
        "max_retries": 0,
        "description": "Potentially destructive operation detected",
        "hint": "Review the change manually before retrying",
    },
}


@dataclass
class CIFailureClassification:
    """Classified CI failure with remediation guidance."""

    failure_class: str
    auto_remediable: bool
    description: str
    details: str  # raw match details
    remediation_hint: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CICheckResult:
    """Result of a single CI check."""

    name: str
    state: str  # "SUCCESS", "FAILURE", "PENDING", "IN_PROGRESS"
    classification: CIFailureClassification | None = None

    def to_dict(self) -> dict:
        d: dict = {"name": self.name, "state": self.state}
        if self.classification is not None:
            d["classification"] = self.classification.to_dict()
        return d


@dataclass
class CIStatusReport:
    """Aggregated CI status for a PR."""

    pr_number: int
    overall: str  # "success", "failure", "pending", "unknown"
    checks: list[CICheckResult]
    classifications: list[CIFailureClassification]

    def to_dict(self) -> dict:
        return {
            "pr_number": self.pr_number,
            "overall": self.overall,
            "checks": [c.to_dict() for c in self.checks],
            "classifications": [c.to_dict() for c in self.classifications],
        }


# --- Classification patterns ---
# Each tuple: (regex_pattern, failure_class)
# Order matters: first match wins.

_CLASSIFICATION_PATTERNS: list[tuple[str, str]] = [
    # Lint / format
    (r"ruff\s+check", "lint_format"),
    (r"ruff\s+format", "lint_format"),
    (r"black\s+.*--check", "lint_format"),
    (r"flake8", "lint_format"),
    (r"isort\s+.*--check", "lint_format"),
    (r"mypy", "lint_format"),
    (r"E\d{3,4}\s", "lint_format"),  # ruff error codes like E501
    (r"W\d{3,4}\s", "lint_format"),  # ruff warning codes
    (r"F\d{3,4}\s", "lint_format"),  # ruff pyflakes codes
    (r"I\d{3,4}\s", "lint_format"),  # isort codes
    (r"formatting.*differ|would reformat", "lint_format"),
    # Deterministic test failures
    (r"FAILED\s+tests/", "deterministic_test"),
    (r"pytest.*ERRORS?|pytest.*FAILED", "deterministic_test"),
    (r"AssertionError|assert\s+\w+\s*==", "deterministic_test"),
    (r"test.*failed|tests?\s+failed", "deterministic_test"),
    (r"FAILURES?$", "deterministic_test"),
    # Missing config / dependency
    (r"ModuleNotFoundError", "missing_config"),
    (r"FileNotFoundError", "missing_config"),
    (r"No such file or directory", "missing_config"),
    (r"ImportError", "missing_config"),
    (r"uv sync|pip install.*failed", "missing_config"),
    (r"fixture.*not found", "missing_config"),
    # Flaky / external
    (r"TimeoutError|timed?\s*out", "flaky_external"),
    (r"ConnectionError|connection\s+refused", "flaky_external"),
    (r"HTTPError|HTTP\s+\d{3}", "flaky_external"),
    (r"rate.limit|quota.exceeded", "flaky_external"),
    (r"RETRY|retrying", "flaky_external"),
    # Infrastructure / auth
    (r"PermissionError|permission\s+denied", "infra_auth"),
    (r"EACCES|EPERM", "infra_auth"),
    (r"credentials?\s+.*(?:invalid|expired|missing)", "infra_auth"),
    (r"token\s+.*(?:invalid|expired)", "infra_auth"),
    (r"auth(?:entication|orization)\s+failed", "infra_auth"),
    # Risky / destructive
    (r"force\s+push|--force", "risky_destructive"),
    (r"reset\s+--hard", "risky_destructive"),
    (r"git\s+clean\s+-f", "risky_destructive"),
    (r"rm\s+-rf\s+/", "risky_destructive"),
]


def classify_ci_failure(check_output: str) -> CIFailureClassification:
    """Classify a CI failure from its output text.

    Uses pattern matching to categorize the failure. Falls back to
    ``deterministic_test`` if no pattern matches.

    Args:
        check_output: The CI check output/log text.

    Returns:
        CIFailureClassification with category, remediation hint, and details.
    """
    for pattern, failure_class in _CLASSIFICATION_PATTERNS:
        match = re.search(pattern, check_output, re.IGNORECASE | re.MULTILINE)
        if match:
            meta = CI_FAILURE_CLASSES[failure_class]
            return CIFailureClassification(
                failure_class=failure_class,
                auto_remediable=meta["auto_remediable"],
                description=meta["description"],
                details=match.group(0),
                remediation_hint=meta["hint"],
            )

    # Fallback: classify as deterministic test failure
    meta = CI_FAILURE_CLASSES["deterministic_test"]
    return CIFailureClassification(
        failure_class="deterministic_test",
        auto_remediable=meta["auto_remediable"],
        description=meta["description"],
        details="No specific pattern matched",
        remediation_hint=meta["hint"],
    )


def poll_ci_status(pr_number: int) -> CIStatusReport:
    """Poll CI status for a PR with per-check breakdown.

    Args:
        pr_number: GitHub PR number.

    Returns:
        CIStatusReport with overall status and per-check results.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "checks",
            str(pr_number),
            "--json",
            "name,state",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return CIStatusReport(
            pr_number=pr_number,
            overall="unknown",
            checks=[],
            classifications=[],
        )

    try:
        raw_checks = json.loads(result.stdout)
    except json.JSONDecodeError:
        return CIStatusReport(
            pr_number=pr_number,
            overall="unknown",
            checks=[],
            classifications=[],
        )

    # Filter out reviewing-changes to avoid circular dependency
    ci_checks = [c for c in raw_checks if c.get("name") != "reviewing-changes"]

    check_results: list[CICheckResult] = []
    classifications: list[CIFailureClassification] = []

    for check in ci_checks:
        name = check.get("name", "unknown")
        state = check.get("state", "PENDING")

        check_result = CICheckResult(name=name, state=state)

        if state == "FAILURE":
            # Classify based on check name (we don't have the full log here)
            classification = classify_ci_failure(name)
            check_result.classification = classification
            classifications.append(classification)

        check_results.append(check_result)

    # Determine overall status
    if not check_results:
        overall = "pending"
    elif any(c.state == "FAILURE" for c in check_results):
        overall = "failure"
    elif any(c.state in ("PENDING", "IN_PROGRESS") for c in check_results):
        overall = "pending"
    elif all(c.state == "SUCCESS" for c in check_results):
        overall = "success"
    else:
        overall = "unknown"

    return CIStatusReport(
        pr_number=pr_number,
        overall=overall,
        checks=check_results,
        classifications=classifications,
    )


# --- Formatting ---


def format_ci_text(report: CIStatusReport) -> str:
    """Format CI status report as human-readable text."""
    lines = [f"=== CI Status — PR #{report.pr_number} ===", ""]
    lines.append(f"Overall: {report.overall}")
    lines.append("")

    if not report.checks:
        lines.append("No checks found.")
        return "\n".join(lines)

    lines.append("Checks:")
    for check in report.checks:
        icon = {"SUCCESS": "+", "FAILURE": "x", "PENDING": "~"}.get(check.state, "?")
        line = f"  [{icon}] {check.name}: {check.state}"
        if check.classification:
            line += f" ({check.classification.failure_class})"
        lines.append(line)

    if report.classifications:
        lines.append("")
        lines.append("Failure classifications:")
        for cls in report.classifications:
            lines.append(f"  - {cls.failure_class}: {cls.description}")
            lines.append(f"    Hint: {cls.remediation_hint}")
            lines.append(
                f"    Auto-remediable: {'yes' if cls.auto_remediable else 'no'}"
            )

    return "\n".join(lines)


def format_ci_json(report: CIStatusReport) -> dict:
    """Format CI status report as JSON-serializable dict."""
    return report.to_dict()

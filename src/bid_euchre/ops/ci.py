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
from pathlib import Path
from typing import Any

from bid_euchre.ops import DEFAULT_REVIEW_CONTEXTS, GH_TIMEOUT_SECONDS

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
    "unclassified": {
        "auto_remediable": False,
        "max_retries": 1,
        "description": "Failure class unknown — insufficient evidence to classify",
        "hint": "Inspect the CI check logs for details",
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


def classify_ci_failure(
    check_output: str,
    *,
    evidence_level: str = "log_output",
) -> CIFailureClassification:
    """Classify a CI failure from its output text.

    Uses pattern matching to categorize the failure. When only a check
    name is available (``evidence_level="name_only"``), classification is
    best-effort — if no pattern matches, the failure is reported as
    ``unclassified`` rather than defaulting to ``deterministic_test``.

    Args:
        check_output: The CI check output/log text (or check name when
            evidence_level is "name_only").
        evidence_level: Quality of the input evidence. One of:
            - ``"log_output"`` — full CI log text (default, highest confidence).
            - ``"name_only"`` — only the check name is available (lower confidence;
              falls back to ``unclassified`` instead of guessing).

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

    # Fallback depends on evidence level
    if evidence_level == "name_only":
        # Insufficient evidence — do not guess
        meta = CI_FAILURE_CLASSES["unclassified"]
        return CIFailureClassification(
            failure_class="unclassified",
            auto_remediable=meta["auto_remediable"],
            description=meta["description"],
            details=f"Check name only: {check_output!r}",
            remediation_hint=meta["hint"],
        )

    # Full log output but no pattern matched — likely a test failure
    meta = CI_FAILURE_CLASSES["deterministic_test"]
    return CIFailureClassification(
        failure_class="deterministic_test",
        auto_remediable=meta["auto_remediable"],
        description=meta["description"],
        details="No specific pattern matched",
        remediation_hint=meta["hint"],
    )


def poll_ci_status(
    pr_number: int,
    *,
    review_contexts: tuple[str, ...] = DEFAULT_REVIEW_CONTEXTS,
) -> CIStatusReport:
    """Poll CI status for a PR with per-check breakdown.

    Args:
        pr_number: GitHub PR number.
        review_contexts: Check names to exclude from CI aggregation
            (they represent review outcomes, not CI results). Uses the
            same shared default as ``reviews.py``.

    Returns:
        CIStatusReport with overall status and per-check results.
    """
    try:
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
            timeout=GH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.warning("gh pr checks timed out for PR #%d", pr_number)
        return CIStatusReport(
            pr_number=pr_number,
            overall="unknown",
            checks=[],
            classifications=[],
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

    # Filter out review contexts to avoid counting review status as CI
    ci_checks = [c for c in raw_checks if c.get("name") not in review_contexts]

    check_results: list[CICheckResult] = []
    classifications: list[CIFailureClassification] = []

    for check in ci_checks:
        name = check.get("name", "unknown")
        state = check.get("state", "PENDING")

        check_result = CICheckResult(name=name, state=state)

        if state == "FAILURE":
            # Classify from check name — evidence_level="name_only" since
            # we don't have the full log from `gh pr checks`.
            classification = classify_ci_failure(name, evidence_level="name_only")
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


def emit_ci_events(
    report: CIStatusReport,
    lane_id: str,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit a durable CI event based on a ``CIStatusReport``.

    This is the Python-level counterpart to ``ci_poller.sh:emit_ci_event()``.
    It translates the ``overall`` field of a polled CI status report into
    the appropriate durable event:

    - ``"failure"`` -> ``ci_failure`` with ``pr_number`` and ``failure_class``
    - ``"success"`` -> ``ci_success`` with ``pr_number``
    - otherwise -> no event (returns None)

    Args:
        report: CI status report from ``poll_ci_status()``.
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        events_dir: Override for events directory. Defaults to
            ``.claude/runtime/events``.

    Returns:
        The emitted event dict, or None if the report does not warrant
        an event (pending/unknown status).
    """
    from bid_euchre.ops.events import append_event

    if report.overall == "failure":
        # Collect unique failure classes from classifications
        failure_classes = sorted({c.failure_class for c in report.classifications})
        failure_class = (
            ", ".join(failure_classes) if failure_classes else "unclassified"
        )

        return append_event(
            event_type="ci_failure",
            source="ops.ci",
            lane_id=lane_id,
            payload={
                "pr_number": report.pr_number,
                "failure_class": failure_class,
            },
            events_dir=events_dir,
        )

    if report.overall == "success":
        return append_event(
            event_type="ci_success",
            source="ops.ci",
            lane_id=lane_id,
            payload={
                "pr_number": report.pr_number,
            },
            events_dir=events_dir,
        )

    # pending / unknown — no event
    return None


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

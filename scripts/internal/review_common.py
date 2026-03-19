"""Shared severity constants and predicates for the review pipeline.

Used by deterministic_prechecks.py, codex_review_adapter.py, and
review_driver.py to avoid duplicating the P0/P1/P2 severity mapping.
"""

from __future__ import annotations

# Severity levels that block merge
BLOCKING_SEVERITIES: frozenset[str] = frozenset(("P0", "P1"))

# Severity level for non-blocking warnings (follow-up issues)
WARN_SEVERITY: str = "P2"


def is_blocking_severity(severity: str) -> bool:
    """Return True if the severity level blocks merge."""
    return severity in BLOCKING_SEVERITIES


def is_warning_severity(severity: str) -> bool:
    """Return True if the severity level is a non-blocking warning."""
    return severity == WARN_SEVERITY

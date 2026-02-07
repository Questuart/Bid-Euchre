"""Promotion eligibility computation with freeze enforcement."""
from __future__ import annotations

from bid_euchre.models.freeze import require_frozen


def check_artifacts_frozen(artifact_paths: list[str], strict: bool = True) -> list[str]:
    """Check that all artifacts are frozen. Returns list of violation messages.

    Args:
        artifact_paths: List of paths to artifact JSON files.
        strict: If True (default), require_frozen raises on unfrozen.
                If False, require_frozen warns instead.

    Returns:
        List of violation message strings (empty if all frozen).
    """
    violations = []
    for path in artifact_paths:
        try:
            require_frozen(path, strict=strict)
        except ValueError as e:
            violations.append(str(e))
    return violations

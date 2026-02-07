"""
Promotion eligibility computation.

Determines whether a batch of experiment runs is eligible for
promotion to canonical status based on artifact inspection.
"""

from __future__ import annotations

from typing import Any


def compute_eligibility(
    member_statuses: list[dict[str, Any]],
    expected_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Compute batch promotion eligibility from member run statuses.

    Args:
        member_statuses: List of dicts with keys:
            - run_id: str
            - batch_role: str or None
            - sanity_pass: int
            - sanity_warn: int
            - sanity_fail: int
            - sanity_skip: int
            - gate_status: "PASS" | "FAIL" | "UNKNOWN"
        expected_roles: If provided, verify all roles are present.

    Returns:
        Dict with:
            - eligible: bool
            - reasons: list[str] explaining non-eligibility
    """
    reasons: list[str] = []

    # Check all runs completed
    if not member_statuses:
        reasons.append("No member runs found")
        return {"eligible": False, "reasons": reasons}

    # Check no FAIL across all runs
    total_fail = sum(m.get("sanity_fail", 0) for m in member_statuses)
    if total_fail > 0:
        failing_runs = [
            m["run_id"] for m in member_statuses if m.get("sanity_fail", 0) > 0
        ]
        reasons.append(f"Sanity FAILs in: {', '.join(failing_runs)}")

    # Check WARN <= 2 per run
    for m in member_statuses:
        if m.get("sanity_warn", 0) > 2:
            reasons.append(
                f"Excessive WARNs ({m['sanity_warn']}) in: {m['run_id']}"
            )

    # Check gate_status
    for m in member_statuses:
        if m.get("gate_status") == "FAIL":
            reasons.append(f"Gate FAIL in: {m['run_id']}")

    # Check expected roles
    if expected_roles:
        present_roles = {m.get("batch_role") for m in member_statuses}
        missing = set(expected_roles) - present_roles
        if missing:
            reasons.append(f"Missing batch roles: {', '.join(sorted(missing))}")

    eligible = len(reasons) == 0
    return {"eligible": eligible, "reasons": reasons}

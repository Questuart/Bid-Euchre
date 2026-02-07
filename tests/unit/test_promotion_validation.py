"""Tests for promotion eligibility computation."""

from bid_euchre.validation.promotion import compute_eligibility


def test_all_passing():
    """All runs passing = eligible."""
    statuses = [
        {
            "run_id": "run1",
            "batch_role": "dataset_greedy",
            "sanity_pass": 3,
            "sanity_warn": 0,
            "sanity_fail": 0,
            "sanity_skip": 1,
            "gate_status": "PASS",
        },
        {
            "run_id": "run2",
            "batch_role": "dataset_glutton",
            "sanity_pass": 3,
            "sanity_warn": 0,
            "sanity_fail": 0,
            "sanity_skip": 1,
            "gate_status": "PASS",
        },
    ]
    result = compute_eligibility(statuses)
    assert result["eligible"] is True
    assert result["reasons"] == []


def test_sanity_failure():
    """Sanity FAIL makes ineligible."""
    statuses = [
        {
            "run_id": "run1",
            "sanity_pass": 2,
            "sanity_warn": 0,
            "sanity_fail": 1,
            "sanity_skip": 0,
            "gate_status": "FAIL",
        },
    ]
    result = compute_eligibility(statuses)
    assert result["eligible"] is False
    assert any("FAIL" in r for r in result["reasons"])


def test_excessive_warnings():
    """More than 2 WARNs per run makes ineligible."""
    statuses = [
        {
            "run_id": "run1",
            "sanity_pass": 1,
            "sanity_warn": 3,
            "sanity_fail": 0,
            "sanity_skip": 0,
            "gate_status": "PASS",
        },
    ]
    result = compute_eligibility(statuses)
    assert result["eligible"] is False
    assert any("WARN" in r for r in result["reasons"])


def test_missing_roles():
    """Missing expected roles makes ineligible."""
    statuses = [
        {
            "run_id": "run1",
            "batch_role": "dataset_greedy",
            "sanity_pass": 3,
            "sanity_warn": 0,
            "sanity_fail": 0,
            "sanity_skip": 0,
            "gate_status": "PASS",
        },
    ]
    result = compute_eligibility(
        statuses, expected_roles=["dataset_greedy", "dataset_glutton"]
    )
    assert result["eligible"] is False
    assert any("Missing" in r for r in result["reasons"])


def test_empty_statuses():
    """Empty member list = ineligible."""
    result = compute_eligibility([])
    assert result["eligible"] is False


def test_gate_failure():
    """Gate FAIL makes ineligible."""
    statuses = [
        {
            "run_id": "run1",
            "sanity_pass": 3,
            "sanity_warn": 0,
            "sanity_fail": 0,
            "sanity_skip": 0,
            "gate_status": "FAIL",
        },
    ]
    result = compute_eligibility(statuses)
    assert result["eligible"] is False


def test_two_warns_ok():
    """Exactly 2 WARNs is acceptable."""
    statuses = [
        {
            "run_id": "run1",
            "sanity_pass": 2,
            "sanity_warn": 2,
            "sanity_fail": 0,
            "sanity_skip": 0,
            "gate_status": "PASS",
        },
    ]
    result = compute_eligibility(statuses)
    assert result["eligible"] is True

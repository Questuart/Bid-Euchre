"""Tests for Arc D reporting: semantic gate extensions and rung report generator.

Covers:
- check_team_balance_by_contract (3 tests)
- check_bid_distribution_sanity (3 tests)
- check_dual_arm_coherence (2 tests)
- generate_arc_d_rung_report (2 tests)
- generate_dashboard (4 tests)
"""

import importlib.util
import json

import numpy as np
import pandas as pd

from bid_euchre.diagnostics.semantic_gate import (
    check_bid_distribution_sanity,
    check_dual_arm_coherence,
    check_team_balance_by_contract,
)
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report

# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────


def _make_balanced_df(n_hands=500, seed=42):
    """Create a balanced DataFrame with per-contract data."""
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n_hands):
        ct = ["suit", "high", "low"][i % 3]
        for seat in range(4):
            # Base value ~5.0 per hand + small per-seat noise
            tricks = 5.0 + rng.normal(0, 0.3)
            tricks = max(0, min(10, tricks))
            rows.append(
                {
                    "hand_id": i,
                    "seat": seat,
                    "contract_type": ct,
                    "tricks_won": tricks,
                    "trump_suit": ["C", "D", "H", "S"][seat % 4]
                    if ct == "suit"
                    else None,
                    "bid_won": seat == 0,
                }
            )
    return pd.DataFrame(rows)


def _make_unbalanced_df(n_hands=500, seed=42):
    """Create a DataFrame with one unbalanced contract type."""
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n_hands):
        ct = ["suit", "high", "low"][i % 3]
        for seat in range(4):
            # Make "high" contracts have mean tricks ~3.5 (far from 5.0)
            if ct == "high":
                tricks = 3.5 + rng.normal(0, 0.3)
            else:
                tricks = 5.0 + rng.normal(0, 0.3)
            tricks = max(0, min(10, tricks))
            rows.append(
                {
                    "hand_id": i,
                    "seat": seat,
                    "contract_type": ct,
                    "tricks_won": tricks,
                    "trump_suit": ["C", "D", "H", "S"][seat % 4]
                    if ct == "suit"
                    else None,
                    "bid_won": seat == 0,
                }
            )
    return pd.DataFrame(rows)


def _make_gate_artifact(checks, gate_status="PASS"):
    """Create a minimal gate artifact dict."""
    return {
        "schema_version": 1,
        "gate_status": gate_status,
        "checks": checks,
    }


def _make_bundle(tmp_path, rung_id="r0"):
    """Create a minimal rung bundle JSON on disk."""
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": rung_id,
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "artifact_sha256": "abc12345deadbeef",
            "net_eppd": 0.15,
            "selected_features": {
                "suit": ["bowers", "trump_count", "offsuit_aces"],
                "high": ["offsuit_aces"],
                "low": ["offsuit_tens_count"],
            },
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "artifact_sha256": "def67890cafebabe",
            "net_eppd": 0.22,
            "selected_features": {
                "suit": [
                    "bowers",
                    "trump_count",
                    "offsuit_aces",
                    "void_count",
                    "trump_power_sum",
                ],
                "high": ["offsuit_aces", "high_card_count"],
                "low": ["offsuit_tens_count", "low_card_count"],
            },
        },
        "split_manifest": "split_manifest_r0_suit.json",
        "training_report": "training_report_r0.json",
    }
    path = tmp_path / "rung_bundle_r0.json"
    path.write_text(json.dumps(bundle, indent=2))
    return path


def _load_dashboard_module():
    """Import the dashboard generator script via importlib."""
    spec = importlib.util.spec_from_file_location(
        "gen_dashboard",
        "scripts/internal/generate_arc_dashboard.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ──────────────────────────────────────────────
#  check_team_balance_by_contract tests
# ──────────────────────────────────────────────


def test_team_balance_by_contract_pass():
    """All contract types balanced around 5.0 -> all PASS."""
    df = _make_balanced_df()
    results = check_team_balance_by_contract(df, "FULL")
    assert all(r["status"] == "PASS" for r in results)
    assert len(results) == 3  # suit, high, low


def test_team_balance_by_contract_one_fails():
    """One contract type unbalanced -> that one FAIL, others PASS."""
    df = _make_unbalanced_df()
    results = check_team_balance_by_contract(df, "FULL")
    statuses = {r.get("contract_type"): r["status"] for r in results}
    assert statuses["high"] == "FAIL"
    assert statuses["suit"] == "PASS"
    assert statuses["low"] == "PASS"


def test_team_balance_by_contract_smoke_skips():
    """SMOKE mode -> SKIP."""
    df = _make_balanced_df()
    results = check_team_balance_by_contract(df, "SMOKE")
    assert len(results) == 1
    assert results[0]["status"] == "SKIP"


# ──────────────────────────────────────────────
#  check_bid_distribution_sanity tests
# ──────────────────────────────────────────────


def test_bid_distribution_pass():
    """Normal bid rate -> PASS."""
    df = _make_balanced_df()
    # Default balanced df has bid_won=True for seat 0 on every hand,
    # giving bid_rate=1.0 which exceeds max_rate=0.95.
    # Set ~50% of hands to have no bid to get a realistic mid-range rate.
    rng = np.random.RandomState(99)
    no_bid_hands = set(rng.choice(df["hand_id"].unique(), size=250, replace=False))
    df.loc[df["hand_id"].isin(no_bid_hands), "bid_won"] = False
    result = check_bid_distribution_sanity(df, "FULL")
    assert result["status"] == "PASS"


def test_bid_distribution_extreme_rate_fails():
    """Bid rate outside [0.05, 0.95] -> FAIL."""
    df = _make_balanced_df()
    # Make almost no bids (all bid_won=False)
    df["bid_won"] = False
    result = check_bid_distribution_sanity(df, "FULL")
    assert result["status"] == "FAIL"


def test_bid_distribution_single_contract_dominates():
    """Single contract > 80% of bids -> FAIL via dominance check."""
    df = _make_balanced_df()
    # First, reduce bid rate to ~50% so the rate check passes
    rng = np.random.RandomState(99)
    no_bid_hands = set(rng.choice(df["hand_id"].unique(), size=250, replace=False))
    df.loc[df["hand_id"].isin(no_bid_hands), "bid_won"] = False
    # Force ALL remaining bids to suit — 100% single-contract dominance
    df.loc[df["bid_won"], "contract_type"] = "suit"
    result = check_bid_distribution_sanity(df, "FULL")
    assert result["status"] == "FAIL"
    assert (
        "dominat" in result["detail"].lower()
    ), f"Expected dominance failure, got: {result['detail']}"


# ──────────────────────────────────────────────
#  check_dual_arm_coherence tests
# ──────────────────────────────────────────────


def test_dual_arm_coherence_low():
    """Low divergence -> PASS."""
    checks = [
        {"check_id": "a", "status": "PASS"},
        {"check_id": "b", "status": "PASS"},
        {"check_id": "c", "status": "FAIL"},
    ]
    g1 = _make_gate_artifact(checks)
    g2 = _make_gate_artifact(checks)  # identical
    result = check_dual_arm_coherence(g1, g2)
    assert result["status"] == "PASS"


def test_dual_arm_coherence_high_divergence():
    """High divergence -> WARN."""
    checks1 = [
        {"check_id": "a", "status": "PASS"},
        {"check_id": "b", "status": "PASS"},
        {"check_id": "c", "status": "PASS"},
        {"check_id": "d", "status": "PASS"},
        {"check_id": "e", "status": "PASS"},
    ]
    checks2 = [
        {"check_id": "a", "status": "FAIL"},
        {"check_id": "b", "status": "FAIL"},
        {"check_id": "c", "status": "FAIL"},
        {"check_id": "d", "status": "FAIL"},
        {"check_id": "e", "status": "PASS"},
    ]
    g1 = _make_gate_artifact(checks1)
    g2 = _make_gate_artifact(checks2)
    result = check_dual_arm_coherence(g1, g2)
    assert result["status"] == "WARN"


def test_dual_arm_coherence_faceted_checks():
    """Faceted checks (same check_id, different contract_type) are keyed separately."""
    # Arm 1: all three contract_type facets PASS
    checks1 = [
        {"check_id": "seat_balance", "contract_type": "suit", "status": "PASS"},
        {"check_id": "seat_balance", "contract_type": "high", "status": "PASS"},
        {"check_id": "seat_balance", "contract_type": "low", "status": "PASS"},
    ]
    # Arm 2: suit FAIL, high PASS, low PASS -> 1 mismatch (within threshold)
    checks2_one_diverge = [
        {"check_id": "seat_balance", "contract_type": "suit", "status": "FAIL"},
        {"check_id": "seat_balance", "contract_type": "high", "status": "PASS"},
        {"check_id": "seat_balance", "contract_type": "low", "status": "PASS"},
    ]
    g1 = _make_gate_artifact(checks1)
    g2 = _make_gate_artifact(checks2_one_diverge)
    result = check_dual_arm_coherence(g1, g2, max_divergence=1)
    assert result["status"] == "PASS"
    assert "1 mismatches" in result["observed"]

    # Arm 2b: suit FAIL and high FAIL -> 2 mismatches (exceeds max_divergence=1)
    checks2_two_diverge = [
        {"check_id": "seat_balance", "contract_type": "suit", "status": "FAIL"},
        {"check_id": "seat_balance", "contract_type": "high", "status": "FAIL"},
        {"check_id": "seat_balance", "contract_type": "low", "status": "PASS"},
    ]
    g1b = _make_gate_artifact(checks1)
    g2b = _make_gate_artifact(checks2_two_diverge)
    result2 = check_dual_arm_coherence(g1b, g2b, max_divergence=1)
    assert result2["status"] == "WARN"
    assert "2 mismatches" in result2["observed"]


# ──────────────────────────────────────────────
#  Report generation tests
# ──────────────────────────────────────────────


def test_rung_report_sections(tmp_path):
    """Report contains expected section headers and computed attribution gap."""
    bundle_path = _make_bundle(tmp_path)
    report = generate_arc_d_rung_report(bundle_path)
    assert "# ARC_D Rung R0 Report" in report
    assert "## Dual-Arm Comparison" in report
    assert "## Feature Selection" in report
    assert "## Attribution Gap" in report
    # Check computed gap table is present with net_eppd values
    assert "0.1500" in report  # olsa net_eppd
    assert "0.2200" in report  # olsa_full net_eppd
    assert "+0.0700" in report  # gap = 0.22 - 0.15
    assert "Positive gap" in report


def test_rung_report_dual_arm_table(tmp_path):
    """Report contains dual-arm comparison table with feature counts."""
    bundle_path = _make_bundle(tmp_path)
    report = generate_arc_d_rung_report(bundle_path)
    assert "OLSa (constrained)" in report
    assert "OLSa_Full (promotional)" in report
    # Feature counts should appear
    assert "suit:" in report


def test_rung_report_attribution_gap_pending(tmp_path):
    """Report shows pending message when net_eppd is absent."""
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
    }
    path = tmp_path / "rung_bundle_r0.json"
    path.write_text(json.dumps(bundle, indent=2))
    report = generate_arc_d_rung_report(path)
    assert "pending" in report.lower()
    assert "## Attribution Gap" in report


# ──────────────────────────────────────────────
#  Dashboard tests
# ──────────────────────────────────────────────


def test_dashboard_reads_bundles(tmp_path):
    """Dashboard reads bundles and produces a table with net_eppd and Gap."""
    # Create a rung bundle
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {
            "selected_features": {"suit": ["a", "b", "c"]},
            "net_eppd": 0.15,
        },
        "olsa_full": {
            "selected_features": {"suit": ["a", "b", "c", "d", "e"]},
            "net_eppd": 0.22,
        },
    }
    (rung_dir / "rung_bundle_r0.json").write_text(json.dumps(bundle))

    output = tmp_path / "dashboard.md"
    mod = _load_dashboard_module()
    result = mod.generate_dashboard(str(tmp_path), str(output))
    assert "r0" in result
    assert "Arc D Progression Dashboard" in result
    assert output.exists()
    # Verify net_eppd and Gap columns
    assert "net_eppd" in result
    assert "Gap" in result
    assert "0.1500" in result
    assert "0.2200" in result
    assert "+0.0700" in result


def test_dashboard_empty_artifacts(tmp_path):
    """Dashboard handles empty artifact directory gracefully."""
    mod = _load_dashboard_module()
    output = tmp_path / "dashboard.md"
    result = mod.generate_dashboard(str(tmp_path / "nonexistent"), str(output))
    assert "No completed rung bundles found" in result


def test_dashboard_gate_status_from_decision(tmp_path):
    """Dashboard emits gate_status line from promotion decision file."""
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {"selected_features": {"suit": ["a"]}},
        "olsa_full": {"selected_features": {"suit": ["a", "b"]}},
    }
    (rung_dir / "rung_bundle_r0.json").write_text(json.dumps(bundle))
    decision = {"decision": "PROMOTED", "attribution_gap": -0.14}
    (rung_dir / "promotion_decision_r0.json").write_text(json.dumps(decision))

    output = tmp_path / "dashboard.md"
    mod = _load_dashboard_module()
    result = mod.generate_dashboard(str(tmp_path), str(output))
    assert "gate_status: r0=PROMOTED" in result


def test_dashboard_metrics_fallback_decision(tmp_path):
    """Dashboard populates net_eppd from decision JSON when bundle lacks inline values."""
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()
    # Bundle WITHOUT inline net_eppd (matches real bundle schema)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {"selected_features": {"suit": ["a"]}},
        "olsa_full": {"selected_features": {"suit": ["a", "b"]}},
    }
    (rung_dir / "rung_bundle_r0.json").write_text(json.dumps(bundle))
    # Decision WITH per-arm metrics
    decision = {
        "decision": "PROMOTED",
        "attribution_gap": -0.1437,
        "challenger": {
            "arm": "OLSa_Full",
            "metrics_seed42": {"net_expected_points_per_deal": 1.4837},
        },
        "olsa_arm": {
            "arm": "OLSa",
            "metrics_seed42": {"net_expected_points_per_deal": 1.6274},
        },
    }
    (rung_dir / "promotion_decision_r0.json").write_text(json.dumps(decision))

    output = tmp_path / "dashboard.md"
    mod = _load_dashboard_module()
    result = mod.generate_dashboard(str(tmp_path), str(output))
    assert "1.6274" in result  # OLSa net_eppd from decision
    assert "1.4837" in result  # Full net_eppd from decision
    assert "-0.1437" in result  # Gap computed from decision metrics

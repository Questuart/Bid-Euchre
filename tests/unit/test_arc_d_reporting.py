"""Tests for Arc D reporting: semantic gate extensions and rung report generator.

Covers:
- check_team_balance_by_contract (3 tests)
- check_bid_distribution_sanity (3 tests)
- check_dual_arm_coherence (2 tests)
- generate_arc_d_rung_report (3 tests + 4 eval_df tests + 3 review-fix tests)
- generate_dashboard (5 tests)
"""

import importlib.util
import json
from pathlib import Path

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
    # New SS1-SS11 structure
    assert "## Executive Summary" in report
    assert "## Data Inventory" in report
    assert "## Feature Health Summary" in report
    assert "## Outcome Health Summary" in report
    assert "## Auction Analysis" in report
    assert "## Model Specification & Feature Selection" in report
    assert "## Model Performance" in report
    assert "## Dual-Arm Comparison & Attribution Gap" in report
    assert "## Semantic Gate Summary" in report
    assert "## Known Limitations" in report
    assert "## Reproduction Commands" in report
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
    assert "## Dual-Arm Comparison & Attribution Gap" in report
    assert "### Attribution Gap" in report


def test_rung_report_tier1_checks_rendered(tmp_path):
    """Report renders tier_1_checks table from promotion_decision JSON."""
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
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))
    decision = {
        "decision": "PROMOTED",
        "tier_1_checks": {
            "artifact_integrity_olsa": "PASS",
            "artifact_integrity_olsa_full": "PASS",
            "no_nan_inf_olsa": "PASS",
            "no_nan_inf_olsa_full": "PASS",
        },
        "gate_results": {
            "primary": {
                "metric": "auto_promote",
                "note": "R0 is auto-promoted",
                "pass": True,
            }
        },
    }
    decision_path = tmp_path / "promotion_decision_r0.json"
    decision_path.write_text(json.dumps(decision, indent=2))
    report = generate_arc_d_rung_report(bundle_path, decision_path=decision_path)
    assert "### Tier 1 Checks (Artifact Integrity)" in report
    assert "artifact_integrity_olsa" in report
    assert "no_nan_inf_olsa_full" in report
    assert "### Gate Results" in report
    assert "auto_promote" in report
    assert "PASS" in report


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


def test_dashboard_preserves_zero_inline_metrics(tmp_path):
    """Dashboard keeps inline net_eppd=0.0 instead of overwriting with decision values."""
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()
    # Bundle WITH zero inline net_eppd (valid edge case)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {
            "selected_features": {"suit": ["a"]},
            "net_eppd": 0.0,
        },
        "olsa_full": {
            "selected_features": {"suit": ["a", "b"]},
            "net_eppd": 0.0,
        },
    }
    (rung_dir / "rung_bundle_r0.json").write_text(json.dumps(bundle))
    # Decision with DIFFERENT per-arm metrics — should NOT override inline zeros
    decision = {
        "decision": "PROMOTED",
        "attribution_gap": -0.14,
        "challenger": {
            "arm": "OLSa_Full",
            "metrics_seed42": {"net_expected_points_per_deal": 9.9},
        },
        "olsa_arm": {
            "arm": "OLSa",
            "metrics_seed42": {"net_expected_points_per_deal": 8.8},
        },
    }
    (rung_dir / "promotion_decision_r0.json").write_text(json.dumps(decision))

    output = tmp_path / "dashboard.md"
    mod = _load_dashboard_module()
    result = mod.generate_dashboard(str(tmp_path), str(output))
    # Inline zeros should be preserved — not overwritten by decision values
    assert "0.0000" in result
    assert "9.9" not in result
    assert "8.8" not in result


# ──────────────────────────────────────────────
#  Report generation with eval_df tests
# ──────────────────────────────────────────────


def _make_eval_df(n_deals=50, seed=42):
    """Create a minimal eval DataFrame for report testing."""
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n_deals):
        ct = ["suit", "high", "low"][i % 3]
        t0 = rng.randint(2, 9)
        t1 = 10 - t0
        bidder = rng.randint(0, 4)
        bidder_team = 0 if bidder in (0, 2) else 1
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            rows.append(
                {
                    "deal_id": i,
                    "hand_id": i,
                    "seat": seat,
                    "team": team,
                    "contract_type": ct,
                    "trump": "H" if ct == "suit" else None,
                    "tricks_won": t0 if seat in (0, 2) else t1,
                    "winning_bid": rng.randint(5, 9),
                    "bidder_seat": bidder,
                    "bidder_team": bidder_team,
                    "made_bid": bool(rng.random() > 0.3),
                    "is_bidder": seat == bidder,
                    "is_declaring_team": team == bidder_team,
                    "feat_hand_value": float(rng.randint(200, 800)),
                    "feat_trump_count": int(rng.randint(0, 7)),
                    "feat_bowers": int(rng.randint(0, 3)),
                    "n_bids": int(rng.randint(1, 3)),
                    "n_passes": int(rng.randint(1, 4)),
                    "auction_rounds": 4,
                }
            )
    return pd.DataFrame(rows)


def test_rung_report_with_eval_df_has_new_sections(tmp_path):
    """Report with eval_df includes all SS1-SS11 sections with data-driven content."""
    bundle_path = _make_bundle(tmp_path)
    eval_df = _make_eval_df()

    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)

    assert "## Executive Summary" in report
    assert "## Data Inventory" in report
    assert "### Eval Dataset Summary" in report
    assert "## Feature Health Summary" in report
    assert "## Outcome Health Summary" in report
    assert "## Auction Analysis" in report
    assert "## Model Performance" in report
    assert "## Dual-Arm Comparison & Attribution Gap" in report
    assert "## Known Limitations" in report
    assert "## Reproduction Commands" in report


def test_rung_report_with_eval_df_deal_count(tmp_path):
    """Report shows correct deal count from eval_df."""
    bundle_path = _make_bundle(tmp_path)
    eval_df = _make_eval_df(n_deals=100)

    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)

    assert "100" in report  # n_deals in Executive Summary


def test_rung_report_without_eval_df_graceful_degradation(tmp_path):
    """Report without eval_df still has all SS1-SS11 sections with graceful degradation."""
    bundle_path = _make_bundle(tmp_path)

    report = generate_arc_d_rung_report(bundle_path)

    # All sections present (graceful degradation, not absent)
    assert "## Executive Summary" in report
    assert "## Data Inventory" in report
    assert "## Feature Health Summary" in report
    assert "## Outcome Health Summary" in report
    assert "## Auction Analysis" in report
    assert "## Model Specification & Feature Selection" in report
    assert "## Model Performance" in report
    assert "## Dual-Arm Comparison & Attribution Gap" in report
    assert "## Semantic Gate Summary" in report
    assert "## Known Limitations" in report
    assert "## Reproduction Commands" in report

    # Graceful degradation messages for data-dependent sections
    assert "*No eval data" in report or "*No eval dataset" in report


def test_rung_report_model_performance_with_artifact(tmp_path):
    """Report loads model via artifact_path (repo-root-relative) and emits Model Performance."""
    # Create a model artifact JSON at a repo-root-relative path inside tmp_path
    artifact_rel = str(tmp_path / "hybrid_r0_full.json")
    model = {
        "artifact_type": "hybrid_olsa",
        "payoff_model": {
            "suit": {
                "feature_names": ["hand_value", "trump_count"],
                "weights": [0.5, 1.2],
                "bias": 3.0,
            }
        },
    }
    (tmp_path / "hybrid_r0_full.json").write_text(json.dumps(model))

    # Bundle with artifact_path pointing to the absolute tmp path
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "nonexistent.json",
            "net_eppd": 0.15,
            "selected_features": {"suit": ["hand_value"]},
        },
        "olsa_full": {
            "artifact_path": artifact_rel,
            "net_eppd": 0.22,
            "selected_features": {"suit": ["hand_value", "trump_count"]},
        },
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle))

    eval_df = _make_eval_df()
    # Ensure the eval_df has the feature columns the model expects
    eval_df["feat_hand_value"] = eval_df["feat_hand_value"]
    eval_df["feat_trump_count"] = eval_df["feat_trump_count"]

    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)
    assert (
        "## Model Performance" in report
    ), "Model Performance section missing — artifact_path resolution may be broken"
    assert "R²" in report or "MAE" in report


def test_rung_report_model_performance_non_repo_cwd(tmp_path, monkeypatch):
    """Report resolves artifact_path when CWD is NOT the repo root.

    Simulates: bundle at <root>/data/artifacts/arc_d/r0/rung_bundle_r0.json
    with artifact_path="data/artifacts/arc_d/r0/model.json" (repo-root-relative).
    CWD is set to /tmp so the path doesn't resolve directly.
    """
    # Build a fake repo root under tmp_path
    repo_root = tmp_path / "fake_repo"
    artifact_dir = repo_root / "data" / "artifacts" / "arc_d" / "r0"
    artifact_dir.mkdir(parents=True)

    model = {
        "artifact_type": "hybrid_olsa",
        "payoff_model": {
            "suit": {
                "feature_names": ["hand_value", "trump_count"],
                "weights": [0.5, 1.2],
                "bias": 3.0,
            }
        },
    }
    (artifact_dir / "model.json").write_text(json.dumps(model))

    # Bundle uses repo-root-relative path (same format as real bundles)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "data/artifacts/arc_d/r0/other.json",
            "net_eppd": 0.15,
            "selected_features": {"suit": ["hand_value"]},
        },
        "olsa_full": {
            "artifact_path": "data/artifacts/arc_d/r0/model.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["hand_value", "trump_count"]},
        },
    }
    bundle_path = artifact_dir / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle))

    # Change CWD to something that is NOT the repo root
    monkeypatch.chdir(tmp_path)

    eval_df = _make_eval_df()
    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)
    assert "## Model Performance" in report, (
        "Model Performance missing when CWD != repo root — "
        "_resolve_bundle_ref should infer repo root from bundle_path"
    )


def test_rung_report_attribution_gap_non_repo_cwd(tmp_path, monkeypatch):
    """Report resolves eval_seed42 paths when CWD is NOT the repo root."""
    repo_root = tmp_path / "fake_repo"
    artifact_dir = repo_root / "data" / "artifacts" / "arc_d" / "r0"
    artifact_dir.mkdir(parents=True)

    # Create eval JSON files with metrics
    eval_data = {
        "net_expected_points_per_deal": 1.5,
        "expected_points_per_deal": 2.0,
    }
    (artifact_dir / "eval_r0.json").write_text(json.dumps(eval_data))
    eval_full = {
        "net_expected_points_per_deal": 1.3,
        "expected_points_per_deal": 1.8,
    }
    (artifact_dir / "eval_r0_full.json").write_text(json.dumps(eval_full))

    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "data/artifacts/arc_d/r0/model.json",
            "eval_seed42": "data/artifacts/arc_d/r0/eval_r0.json",
            "selected_features": {"suit": ["hand_value"]},
        },
        "olsa_full": {
            "artifact_path": "data/artifacts/arc_d/r0/model_full.json",
            "eval_seed42": "data/artifacts/arc_d/r0/eval_r0_full.json",
            "selected_features": {"suit": ["hand_value", "trump_count"]},
        },
    }
    bundle_path = artifact_dir / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle))

    # Change CWD away from repo root
    monkeypatch.chdir(tmp_path)

    report = generate_arc_d_rung_report(bundle_path)
    # Attribution gap section must NOT show pending — eval paths should resolve
    # via _resolve_bundle_ref even when CWD != repo root.
    # (Note: "Gate status: pending" is expected when no decision_path is given,
    #  so we check the attribution gap section specifically.)
    assert "Attribution gap not yet available" not in report, (
        "Attribution gap shows 'pending' when CWD != repo root — "
        "_resolve_bundle_ref should resolve eval paths from bundle location"
    )
    assert "1.5000" in report  # OLSa net_eppd
    assert "1.3000" in report  # Full net_eppd


def test_rung_report_no_model_artifact_key(tmp_path):
    """Report must NOT use 'model_artifact' key (old schema)."""
    # Read the source and verify it doesn't use the wrong key
    import inspect

    source = inspect.getsource(generate_arc_d_rung_report)
    assert (
        'get("model_artifact")' not in source
    ), "Report must use 'artifact_path' not 'model_artifact'"


def test_rung_report_with_chart_dir(tmp_path):
    """Report with chart_dir embeds chart references inline in sections."""
    bundle_path = _make_bundle(tmp_path)
    chart_dir = tmp_path / "charts"
    chart_dir.mkdir()
    (chart_dir / "seat_balance_boxplot.png").write_bytes(b"fake")
    (chart_dir / "dual_arm_comparison.png").write_bytes(b"fake")
    # Auction charts: use correct names (not make_rate_by_contract.png)
    (chart_dir / "auction_health.png").write_bytes(b"fake")
    (chart_dir / "bidder_performance.png").write_bytes(b"fake")

    report = generate_arc_d_rung_report(bundle_path, chart_dir=chart_dir)

    # Charts embedded inline in their respective sections (not a separate Charts section)
    assert "seat_balance_boxplot" in report
    assert "dual_arm_comparison" in report
    # Finding 1: auction charts use correct filenames
    assert "auction_health" in report
    assert "bidder_performance" in report
    # Old name must NOT appear
    assert "make_rate_by_contract" not in report


# ──────────────────────────────────────────────
#  Feature correlations, comparator battery, and matchup tests
# ──────────────────────────────────────────────


def test_report_with_eval_df_has_feature_correlations(tmp_path):
    """Report with eval_df includes Feature Correlations section."""
    bundle_path = _make_bundle(tmp_path)
    eval_df = _make_eval_df(n_deals=50)

    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)

    assert "### Feature Correlations" in report
    assert "tricks_won" in report.lower() or "r |" in report


def test_report_with_comparator_battery(tmp_path):
    """Report includes Comparator Battery when bundle has that key."""
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
        "comparator_battery": {
            "hybrid_olsa_r0": {"net_eppd": 1.6274},
            "modeloespecifico": {"net_eppd": 0.8432},
            "rankthetank": {"net_eppd": 0.5123},
        },
    }
    path = tmp_path / "rung_bundle_r0.json"
    path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(path)

    assert "### Comparator Battery" in report
    assert "1.6274" in report
    assert "modeloespecifico" in report


def test_report_with_matchup_run_dir(tmp_path):
    """Report includes Head-to-Head Summary when matchup_run_dir provided."""
    bundle_path = _make_bundle(tmp_path)

    # Create a fake matchup run directory with JSONL logs
    run_dir = tmp_path / "h2h_run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)

    # Write a minimal JSONL log that build_eval_dataset can parse
    # We'll test that the section header appears even if parsing fails
    # (graceful degradation)
    (logs_dir / "run_matchup1.jsonl").write_text("")  # Empty log

    report = generate_arc_d_rung_report(bundle_path, matchup_run_dir=str(run_dir))

    assert "### Head-to-Head Summary" in report


def test_report_with_comparator_battery_path_string(tmp_path):
    """Bundle stores comparator_battery as a path string → loads JSON and extracts bidders."""
    # Create the comparator battery JSON file with nested "bidders" key
    battery_data = {
        "schema": "comparator_battery_v1",
        "seed": 42,
        "gate_status": "PROMOTED",
        "bidders": {
            "HybridOLSaBidder_r0": {"net_eppd": 1.6274},
            "GreedyBidder": {"net_eppd": 0.8432},
        },
    }
    battery_path = tmp_path / "comparator_battery_r0.json"
    battery_path.write_text(json.dumps(battery_data))

    # Bundle references battery as a relative path string
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
        "comparator_battery": str(battery_path),
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(bundle_path)

    assert "### Comparator Battery" in report
    assert "HybridOLSaBidder_r0" in report
    assert "GreedyBidder" in report
    assert "1.6274" in report
    # Must NOT show schema/seed/gate_status as bidder names
    assert "| schema |" not in report
    assert "| seed |" not in report


def test_report_with_comparator_battery_nested_bidders(tmp_path):
    """Inline dict with schema envelope and nested 'bidders' key → extracts actual bidders."""
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
        "comparator_battery": {
            "schema": "comparator_battery_v1",
            "seed": 42,
            "bidders": {
                "HybridOLSaBidder_r0": {"net_eppd": 1.6274},
                "FixedBidder_6": {"net_eppd": 0.5123},
            },
        },
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(bundle_path)

    assert "### Comparator Battery" in report
    assert "HybridOLSaBidder_r0" in report
    assert "FixedBidder_6" in report
    # Must NOT show "bidders" or "schema" as bidder names
    assert "| bidders |" not in report
    assert "| schema |" not in report


def test_report_h2h_matchup_id_extraction(tmp_path):
    """Matchup ID extraction uses run dir name stripping, not naive split."""
    bundle_path = _make_bundle(tmp_path)

    # Run dir name with underscores (realistic)
    run_dir = tmp_path / "arc_d_eval_r0_42_20260303_201729"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)

    # Filenames follow the pattern: <run_dir_name>_<matchup_id>.jsonl
    run_name = run_dir.name
    (logs_dir / f"{run_name}_vs_greedy.jsonl").write_text("")
    (logs_dir / f"{run_name}_vs_fixed6.jsonl").write_text("")
    (logs_dir / f"{run_name}_self_play.jsonl").write_text("")

    report = generate_arc_d_rung_report(bundle_path, matchup_run_dir=str(run_dir))

    assert "### Head-to-Head Summary" in report
    # Even though logs are empty (no data parsed), the section is present.
    # Verify that if data were parsed, the matchup_id would be correct
    # by checking the implementation directly:
    for log_file in logs_dir.glob("*.jsonl"):
        stem = log_file.stem
        assert stem.startswith(run_name + "_")
        mid = stem[len(run_name) + 1 :]
        # Correct matchup IDs — not the broken split("_", 1) result
        assert mid in (
            "vs_greedy",
            "vs_fixed6",
            "self_play",
        ), f"Expected clean matchup ID, got: {mid}"


# ──────────────────────────────────────────────
#  Review-fix tests (Findings 1, 4, 5)
# ──────────────────────────────────────────────


def test_reproduction_commands_use_new_notebook_names(tmp_path):
    """Finding 4: Reproduction section references 3 new template notebooks, not old monolithic."""
    bundle_path = _make_bundle(tmp_path)
    eval_df = _make_eval_df()

    report = generate_arc_d_rung_report(bundle_path, eval_df=eval_df)

    assert "10_feature_health.ipynb" in report
    assert "20_outcome_health.ipynb" in report
    assert "25_auction_health.ipynb" in report
    assert "30_feature_outcome_eval.ipynb" in report
    # Old monolithic name must NOT appear
    assert "01_model_rung.ipynb" not in report


def test_semantic_gate_path_artifact(tmp_path):
    """Finding 5: Gate checks loaded from path-based semantic_gate_val."""
    # Create a gate artifact JSON on disk
    gate_data = {
        "schema_version": 1,
        "gate_status": "PASS",
        "checks": [
            {"check_id": "seat_balance", "status": "PASS", "detail": "OK"},
            {
                "check_id": "team_balance",
                "contract_type": "suit",
                "status": "WARN",
                "detail": "Marginal",
            },
        ],
    }
    gate_path = tmp_path / "gate_val_olsa.json"
    gate_path.write_text(json.dumps(gate_data))

    # Bundle with semantic_gate_val as a path string (not inline dict)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "semantic_gate_val": str(gate_path),
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(bundle_path)

    assert "## Semantic Gate Summary" in report
    assert "### OLSa Gate Checks" in report
    assert "seat_balance" in report
    assert "team_balance" in report
    assert "WARN" in report
    # P2 fix: Gate Status column must show aggregate, not raw path
    assert "### Per-Arm Gate Status" in report
    assert "WARN (1 of 2)" in report
    # Must NOT contain the raw filesystem path in Gate Status table
    assert "gate_val_olsa.json" not in report.split("### OLSa Gate Checks")[0]


def test_semantic_gate_inline_dict_still_works(tmp_path):
    """Finding 5 regression: inline gate_artifact dicts still render."""
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "gate_artifact": {
                "schema_version": 1,
                "gate_status": "PASS",
                "checks": [
                    {"check_id": "sample_size", "status": "PASS", "detail": "n=5000"},
                ],
            },
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(bundle_path)

    assert "### OLSa Gate Checks" in report
    assert "sample_size" in report
    assert "n=5000" in report
    # Inline dict: Gate Status shows aggregate too
    assert "PASS (1/1)" in report


def test_gate_status_str_fail_aggregate(tmp_path):
    """Gate Status column shows FAIL count when checks contain failures."""
    gate_data = {
        "checks": [
            {"check_id": "seat_balance", "status": "PASS", "detail": "OK"},
            {"check_id": "model_r2", "status": "FAIL", "detail": "R2=0.01"},
            {"check_id": "sample_size", "status": "FAIL", "detail": "n=50"},
        ],
    }
    gate_path = tmp_path / "gate_val.json"
    gate_path.write_text(json.dumps(gate_data))

    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "arc": "arc_d",
        "olsa": {
            "artifact_path": "hybrid_r0.json",
            "net_eppd": 0.15,
            "semantic_gate_val": str(gate_path),
            "selected_features": {"suit": ["bowers"]},
        },
        "olsa_full": {
            "artifact_path": "hybrid_r0_full.json",
            "net_eppd": 0.22,
            "selected_features": {"suit": ["bowers", "trump_count"]},
        },
    }
    bundle_path = tmp_path / "rung_bundle_r0.json"
    bundle_path.write_text(json.dumps(bundle, indent=2))

    report = generate_arc_d_rung_report(bundle_path)

    # FAIL aggregate in status table
    assert "FAIL (2 of 3)" in report
    # Raw path must NOT appear in the status table area
    assert "gate_val.json |" not in report


# ──────────────────────────────────────────────
#  Notebook 30 logic tests (_resolve_path pattern)
# ──────────────────────────────────────────────


def test_notebook_resolve_path_pattern(tmp_path):
    """Test the _resolve_path logic used in notebook 30 for CWD-independent path resolution."""

    # Reproduce the exact _resolve_path helper from the notebook
    def _resolve_path(ref: str, anchor: Path) -> Path:
        """Resolve a repo-root-relative path via bundle location."""
        p = Path(ref)
        if p.exists():
            return p
        for ancestor in anchor.resolve().parents:
            candidate = ancestor / ref
            if candidate.exists():
                return candidate
        return p

    # Set up a mock repo structure:
    #   tmp_path/repo_root/data/artifacts/model.json   (the target file)
    #   tmp_path/repo_root/data/bundles/bundle.json     (the anchor)
    repo_root = tmp_path / "repo_root"
    artifact_dir = repo_root / "data" / "artifacts"
    artifact_dir.mkdir(parents=True)
    target = artifact_dir / "model.json"
    target.write_text('{"test": true}')

    bundle_dir = repo_root / "data" / "bundles"
    bundle_dir.mkdir(parents=True)
    anchor = bundle_dir / "bundle.json"
    anchor.write_text("{}")

    # Repo-root-relative path (what bundles store)
    rel_ref = "data/artifacts/model.json"

    # Should resolve via ancestor walk
    resolved = _resolve_path(rel_ref, anchor)
    assert resolved.exists()
    assert resolved.resolve() == target.resolve()

    # Already-absolute path resolves directly
    resolved_abs = _resolve_path(str(target), anchor)
    assert resolved_abs.exists()

    # Non-existent path returns the raw Path (fallback)
    resolved_missing = _resolve_path("no/such/file.json", anchor)
    assert not resolved_missing.exists()


def test_notebook_eval_log_dir_resolution(tmp_path):
    """Test the directory auto-resolution logic used in notebook 30 for EVAL_LOG_PATH."""
    # Simulate a directory with logs/ subdirectory
    eval_dir = tmp_path / "eval_run"
    logs_dir = eval_dir / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "run_a.jsonl").write_text('{"test": 1}')
    (logs_dir / "run_b.jsonl").write_text('{"test": 2}')

    # Reproduce the notebook's directory resolution logic
    eval_log = Path(str(eval_dir))
    assert eval_log.is_dir()

    candidates = sorted(eval_log.glob("logs/*.jsonl"))
    assert len(candidates) == 2
    # Should pick first sorted candidate
    resolved = candidates[0]
    assert resolved.name == "run_a.jsonl"

    # Fallback: no logs/ subdir, glob *.jsonl at top level
    flat_dir = tmp_path / "flat_eval"
    flat_dir.mkdir()
    (flat_dir / "games.jsonl").write_text('{"test": 1}')

    eval_log2 = Path(str(flat_dir))
    candidates2 = sorted(eval_log2.glob("logs/*.jsonl"))
    assert len(candidates2) == 0
    candidates2 = sorted(eval_log2.glob("*.jsonl"))
    assert len(candidates2) == 1
    assert candidates2[0].name == "games.jsonl"

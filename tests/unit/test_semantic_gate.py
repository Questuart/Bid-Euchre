"""Tests for semantic gate evaluation engine.

Covers all 12 checks across 2 tiers, gate aggregation logic,
schema emission, and mode-dependent behavior.
"""

import json

import numpy as np
import pandas as pd

from bid_euchre.diagnostics.semantic_gate import (
    SEMANTIC_CHECK_REQUIRED_FIELDS,
    SEMANTIC_GATE_REQUIRED_FIELDS,
    SEMANTIC_GATE_SCHEMA_VERSION,
    check_contract_type_balance,
    check_feature_count,
    check_mae_ceiling,
    check_min_sample_size,
    check_no_nan_features,
    check_prediction_correlation,
    check_r_squared_floor,
    check_seat_balance,
    check_team_balance,
    check_tricks_range,
    check_trump_suit_invariance,
    check_val_split_integrity,
    compute_semantic_gate,
    emit_semantic_gate,
)

# ──────────────────────────────────────────────
#  Fixtures
# ──────────────────────────────────────────────

FEATURE_COLS = [
    "bowers",
    "trump_count",
    "offsuit_aces",
    "offsuit_non_ace_count",
    "hand_value",
    "trump_rb_count",
    "trump_lb_count",
    "trump_ace_count",
    "trump_king_count",
    "trump_queen_count",
    "trump_ten_count",
    "highest_trump_rank",
    "second_highest_trump_rank",
    "third_highest_trump_rank",
    "trump_power_sum",
    "trump_duplicate_pairs",
    "offsuit_king_count_total",
    "offsuit_queen_count_total",
    "offsuit_suits_with_ace",
    "offsuit_suits_with_double_ace",
    "offsuit_suits_with_ace_and_king",
    "void_count",
    "max_suit_len",
    "second_suit_len",
    "third_suit_len",
    "fourth_suit_len",
    "num_singletons",
    "num_doubletons",
    "offsuit_tens_count",
    "offsuit_length_3plus_count",
    "offsuit_best_rank_sum",
    "offsuit_secondbest_rank_sum",
    "double_ten_jack_count",
    "high_card_count",
    "low_card_count",
    "trump_count_x_void_count",
    "trump_count_x_offsuit_ace",
    "losing_tricks_count",
    "quick_tricks",
]


def _make_df(
    n_hands: int = 500,
    seats: tuple[int, ...] = (0, 1, 2, 3),
    trump_suits: tuple[str, ...] = ("C", "D", "H", "S"),
    seed: int = 42,
    include_features: bool = True,
    contract_ratio: str = "standard",
) -> pd.DataFrame:
    """Build a synthetic DataFrame for testing gate checks.

    Uses 4:1:1 contract-type ratios (standard 6-scenario config) and
    balanced data across trump suits and seats.

    When ``contract_ratio="equal"``, uses 1:1:1 instead (for tests that
    override expected ratios).
    """
    rng = np.random.RandomState(seed)
    rows = []

    # Build contract_type sequence: 4 suit, 1 high, 1 low per cycle
    if contract_ratio == "equal":
        ct_sequence = ["suit", "high", "low"]
    else:
        ct_sequence = ["suit", "suit", "suit", "suit", "high", "low"]

    # Pre-generate hand_value/tricks per-group to ensure cross-group balance
    suit_idx = 0
    for hand_id in range(n_hands):
        ct = ct_sequence[hand_id % len(ct_sequence)]

        if ct == "suit":
            ts = trump_suits[suit_idx % len(trump_suits)]
            suit_idx += 1
        else:
            ts = None

        # Draw from same distribution regardless of group
        hv_base = 400.0 + rng.normal(0, 30)
        tw_base = 5.0 + rng.normal(0, 1.0)

        for seat in seats:
            row = {
                "hand_id": hand_id,
                "seat": seat,
                "contract_type": ct,
                "trump_suit": ts,
                "tricks_won": tw_base + rng.normal(0, 0.05),
                "hand_value": hv_base + rng.normal(0, 2),
            }
            if include_features:
                for fc in FEATURE_COLS:
                    if fc == "hand_value":
                        continue  # already set
                    row[fc] = rng.uniform(0, 10)
            rows.append(row)

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
#  Tier 1 — Framework Health Checks
# ──────────────────────────────────────────────


class TestFeatureCount:
    def test_pass(self):
        df = _make_df()
        result = check_feature_count(df, FEATURE_COLS)
        assert result["status"] == "PASS"

    def test_fail(self):
        # Missing 2 features
        result = check_feature_count(_make_df(), FEATURE_COLS[:37])
        assert result["status"] == "FAIL"
        assert "37" in result["observed"]


class TestNoNanFeatures:
    def test_pass(self):
        df = _make_df()
        result = check_no_nan_features(df, FEATURE_COLS)
        assert result["status"] == "PASS"

    def test_fail(self):
        df = _make_df()
        df.loc[0, "bowers"] = np.nan
        df.loc[1, "trump_count"] = np.nan
        result = check_no_nan_features(df, FEATURE_COLS)
        assert result["status"] == "FAIL"
        assert "2" in result["observed"]

    def test_fail_missing_columns(self):
        """Missing feature columns → FAIL (not KeyError)."""
        df = _make_df()
        bogus_cols = FEATURE_COLS + ["nonexistent_feature", "another_missing"]
        result = check_no_nan_features(df, bogus_cols)
        assert result["status"] == "FAIL"
        assert "missing" in result["observed"].lower()
        assert "nonexistent_feature" in result["detail"]


class TestTricksRange:
    def test_pass(self):
        df = _make_df()
        result = check_tricks_range(df)
        assert result["status"] == "PASS"

    def test_fail_above(self):
        df = _make_df()
        df.loc[0, "tricks_won"] = 11
        result = check_tricks_range(df)
        assert result["status"] == "FAIL"

    def test_fail_below(self):
        df = _make_df()
        df.loc[0, "tricks_won"] = -1
        result = check_tricks_range(df)
        assert result["status"] == "FAIL"

    def test_missing_column(self):
        df = _make_df().drop(columns=["tricks_won"])
        result = check_tricks_range(df)
        assert result["status"] == "FAIL"


class TestMinSampleSize:
    def test_pass_full(self):
        df = _make_df(n_hands=2500)
        result = check_min_sample_size(df, "FULL")
        assert result["status"] == "PASS"

    def test_fail_full(self):
        df = _make_df(n_hands=100)
        result = check_min_sample_size(df, "FULL")
        assert result["status"] == "FAIL"

    def test_pass_smoke(self):
        df = _make_df(n_hands=15)
        result = check_min_sample_size(df, "SMOKE")
        assert result["status"] == "PASS"

    def test_fail_smoke(self):
        df = _make_df(n_hands=5)
        result = check_min_sample_size(df, "SMOKE")
        assert result["status"] == "FAIL"

    def test_pass_quick(self):
        df = _make_df(n_hands=150)
        result = check_min_sample_size(df, "QUICK")
        assert result["status"] == "PASS"


class TestValSplitIntegrity:
    def test_skip_no_manifest(self):
        """No manifest provided → SKIP (not PASS) to avoid silent bypass."""
        df = _make_df()
        result = check_val_split_integrity(df, manifest=None, seed=42)
        assert result["status"] == "SKIP"

    def test_pass_with_manifest(self, tmp_path):
        from bid_euchre.models.splits import create_grouped_split

        rows = [
            {"hand_id": i, "seat": s, "tricks_won": 5.0}
            for i in range(100)
            for s in range(4)
        ]
        df = pd.DataFrame(rows)
        pq = tmp_path / "test.parquet"
        df.to_parquet(pq)

        _, _, _, manifest = create_grouped_split(
            df,
            seed=42,
            source_run_id="test",
            source_parquet_path=str(pq),
        )
        result = check_val_split_integrity(df, manifest, seed=42)
        assert result["status"] == "PASS"

    def test_fail_wrong_seed(self, tmp_path):
        from bid_euchre.models.splits import create_grouped_split

        rows = [
            {"hand_id": i, "seat": s, "tricks_won": 5.0}
            for i in range(100)
            for s in range(4)
        ]
        df = pd.DataFrame(rows)
        pq = tmp_path / "test.parquet"
        df.to_parquet(pq)

        _, _, _, manifest = create_grouped_split(
            df,
            seed=42,
            source_run_id="test",
            source_parquet_path=str(pq),
        )
        result = check_val_split_integrity(df, manifest, seed=99)
        assert result["status"] == "FAIL"


# ──────────────────────────────────────────────
#  Tier 2 — Fairness Checks
# ──────────────────────────────────────────────


class TestSeatBalance:
    def test_pass(self):
        # Balanced data — ANOVA should not reject
        df = _make_df(n_hands=1000)
        results = check_seat_balance(df, "FULL")
        for r in results:
            assert r["status"] in ("PASS", "SKIP")

    def test_fail_injected_bias(self):
        df = _make_df(n_hands=1000)
        # Inject large seat bias for suit contracts
        mask = (df["contract_type"] == "suit") & (df["seat"] == 0)
        df.loc[mask, "hand_value"] += 500
        results = check_seat_balance(df, "FULL")
        suit_results = [r for r in results if r.get("contract_type") == "suit"]
        assert any(r["status"] == "FAIL" for r in suit_results)

    def test_skip_small_n(self):
        df = _make_df(n_hands=20)
        results = check_seat_balance(df, "FULL")
        assert all(r["status"] == "SKIP" for r in results)

    def test_missing_columns(self):
        df = _make_df().drop(columns=["seat"])
        results = check_seat_balance(df, "FULL")
        assert results[0]["status"] == "SKIP"

    def test_skip_smoke_large_n(self):
        """SMOKE mode skips statistical tests even with large datasets."""
        df = _make_df(n_hands=1000)
        results = check_seat_balance(df, "SMOKE")
        assert all(r["status"] == "SKIP" for r in results)
        assert len(results) == 1  # Single SKIP entry, no per-contract breakdown


class TestContractTypeBalance:
    def test_pass(self):
        # Standard 4:1:1 ratio from _make_df
        df = _make_df(n_hands=600)
        result = check_contract_type_balance(df, "FULL")
        assert result["status"] == "PASS"

    def test_fail_skewed(self):
        # Create heavily skewed distribution
        rng = np.random.RandomState(42)
        rows = []
        for i in range(800):
            ct = "suit"  # All suit contracts
            for seat in range(4):
                rows.append(
                    {
                        "hand_id": i,
                        "seat": seat,
                        "contract_type": ct,
                        "tricks_won": 5.0,
                        "hand_value": rng.uniform(200, 600),
                    }
                )
        for i in range(800, 810):
            ct = "high"
            for seat in range(4):
                rows.append(
                    {
                        "hand_id": i,
                        "seat": seat,
                        "contract_type": ct,
                        "tricks_won": 5.0,
                        "hand_value": rng.uniform(200, 600),
                    }
                )
        df = pd.DataFrame(rows)
        result = check_contract_type_balance(df, "FULL")
        assert result["status"] == "FAIL"

    def test_skip_smoke(self):
        df = _make_df(n_hands=30)
        result = check_contract_type_balance(df, "SMOKE")
        assert result["status"] == "SKIP"

    def test_skip_small_n(self):
        df = _make_df(n_hands=30)
        result = check_contract_type_balance(df, "FULL")
        assert result["status"] == "SKIP"

    def test_fail_missing_contract_type(self):
        """Data with only suit+high but expected 4:1:1 (low missing) → FAIL."""
        rng = np.random.RandomState(42)
        rows = []
        for i in range(500):
            ct = "suit" if i % 2 == 0 else "high"
            for seat in range(4):
                rows.append(
                    {
                        "hand_id": i,
                        "seat": seat,
                        "contract_type": ct,
                        "tricks_won": 5.0,
                        "hand_value": rng.uniform(200, 600),
                    }
                )
        df = pd.DataFrame(rows)
        result = check_contract_type_balance(df, "FULL")
        assert result["status"] == "FAIL"
        assert "missing" in result["observed"].lower()
        assert "low" in result["detail"]


class TestTrumpSuitInvariance:
    def test_pass(self):
        # Build explicitly balanced data to guarantee low spread
        rng = np.random.RandomState(42)
        rows = []
        suits = ("C", "D", "H", "S")
        for hand_id in range(4000):
            ts = suits[hand_id % 4]
            for seat in range(4):
                rows.append(
                    {
                        "hand_id": hand_id,
                        "seat": seat,
                        "contract_type": "suit",
                        "trump_suit": ts,
                        # Same distribution for all trump suits
                        "hand_value": rng.uniform(300, 500),
                        "tricks_won": 5.0,
                    }
                )
        df = pd.DataFrame(rows)
        result = check_trump_suit_invariance(df, "FULL")
        assert result["status"] == "PASS"

    def test_fail_large_spread(self):
        rng = np.random.RandomState(42)
        rows = []
        suits = ("C", "D", "H", "S")
        for hand_id in range(4000):
            ts = suits[hand_id % 4]
            for seat in range(4):
                # Hearts get a big boost -> large spread
                boost = 200 if ts == "H" else 0
                rows.append(
                    {
                        "hand_id": hand_id,
                        "seat": seat,
                        "contract_type": "suit",
                        "trump_suit": ts,
                        "hand_value": rng.uniform(300, 500) + boost,
                        "tricks_won": 5.0,
                    }
                )
        df = pd.DataFrame(rows)
        result = check_trump_suit_invariance(df, "FULL")
        assert result["status"] == "FAIL"

    def test_skip_smoke(self):
        result = check_trump_suit_invariance(_make_df(), "SMOKE")
        assert result["status"] == "SKIP"


class TestTeamBalance:
    def test_pass(self):
        df = _make_df(n_hands=500)
        result = check_team_balance(df, "FULL")
        assert result["status"] == "PASS"

    def test_fail_biased(self):
        df = _make_df(n_hands=500)
        df["tricks_won"] = 7.5  # Far from 5.0
        result = check_team_balance(df, "FULL")
        assert result["status"] == "FAIL"

    def test_skip_smoke(self):
        result = check_team_balance(_make_df(), "SMOKE")
        assert result["status"] == "SKIP"


# ──────────────────────────────────────────────
#  Tier 2 — Directional Sanity Checks
# ──────────────────────────────────────────────


class TestPredictionCorrelation:
    def test_pass(self):
        df = _make_df(n_hands=1000)
        # Predictions correlated with tricks_won
        noise = np.random.RandomState(42).normal(0, 0.5, len(df))
        preds = df["tricks_won"].values + noise
        results = check_prediction_correlation(df, preds, "FULL")
        passing = [r for r in results if r["status"] == "PASS"]
        assert len(passing) > 0

    def test_fail_uncorrelated(self):
        df = _make_df(n_hands=1000)
        # Random predictions — uncorrelated
        preds = np.random.RandomState(99).uniform(0, 10, len(df))
        results = check_prediction_correlation(df, preds, "FULL")
        # Some contract types may fail
        statuses = {r["status"] for r in results}
        assert "FAIL" in statuses or "SKIP" in statuses

    def test_skip_no_predictions(self):
        df = _make_df()
        results = check_prediction_correlation(df, None, "FULL")
        assert results[0]["status"] == "SKIP"

    def test_skip_smoke(self):
        df = _make_df()
        preds = np.ones(len(df))
        results = check_prediction_correlation(df, preds, "SMOKE")
        assert results[0]["status"] == "SKIP"


class TestRSquaredFloor:
    def test_pass(self):
        df = _make_df(n_hands=1000)
        noise = np.random.RandomState(42).normal(0, 0.3, len(df))
        preds = df["tricks_won"].values + noise
        results = check_r_squared_floor(df, preds, "FULL")
        passing = [r for r in results if r["status"] == "PASS"]
        assert len(passing) > 0

    def test_fail_garbage(self):
        df = _make_df(n_hands=1000)
        # Constant predictions — R² = 0
        preds = np.full(len(df), 5.0)
        results = check_r_squared_floor(df, preds, "FULL")
        failing = [r for r in results if r["status"] == "FAIL"]
        assert len(failing) > 0

    def test_skip_no_predictions(self):
        results = check_r_squared_floor(_make_df(), None, "FULL")
        assert results[0]["status"] == "SKIP"


class TestMaeCeiling:
    def test_pass(self):
        df = _make_df(n_hands=1000)
        noise = np.random.RandomState(42).normal(0, 0.5, len(df))
        preds = df["tricks_won"].values + noise
        results = check_mae_ceiling(df, preds, "FULL")
        passing = [r for r in results if r["status"] == "PASS"]
        assert len(passing) > 0

    def test_fail_high_error(self):
        df = _make_df(n_hands=1000)
        # Predictions 5 tricks off
        preds = df["tricks_won"].values + 5.0
        results = check_mae_ceiling(df, preds, "FULL")
        failing = [r for r in results if r["status"] == "FAIL"]
        assert len(failing) > 0

    def test_skip_no_predictions(self):
        results = check_mae_ceiling(_make_df(), None, "FULL")
        assert results[0]["status"] == "SKIP"


# ──────────────────────────────────────────────
#  Gate Aggregation
# ──────────────────────────────────────────────


class TestGateAggregation:
    def test_gate_status_all_pass(self):
        df = _make_df(n_hands=2500)
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        # No predictions means directional checks skip, health checks should pass
        assert gate["gate_status"] == "PASS"

    def test_gate_status_any_fail(self):
        df = _make_df(n_hands=2500)
        df.loc[0, "tricks_won"] = 11  # Force tricks_range FAIL
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        assert gate["gate_status"] == "FAIL"
        assert gate["failed_checks"] > 0

    def test_warn_does_not_fail_gate(self):
        # Currently no checks emit WARN, but verify logic:
        # All SKIP + PASS should still be PASS
        df = _make_df(n_hands=2500)
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        # Without predictions, directional checks SKIP
        assert gate["gate_status"] == "PASS"

    def test_skip_does_not_fail_gate(self):
        df = _make_df(n_hands=15)
        gate = compute_semantic_gate(df, "SMOKE", "val", 42)
        # Most checks should SKIP in SMOKE mode
        skips = [c for c in gate["checks"] if c["status"] == "SKIP"]
        assert len(skips) > 0
        assert gate["gate_status"] == "PASS"


class TestSchemaEmission:
    def test_required_fields_present(self):
        df = _make_df(n_hands=500)
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        for field in SEMANTIC_GATE_REQUIRED_FIELDS:
            assert field in gate, f"Missing required field: {field}"

    def test_check_entries_have_required_fields(self):
        df = _make_df(n_hands=500)
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        for check in gate["checks"]:
            for field in SEMANTIC_CHECK_REQUIRED_FIELDS:
                assert (
                    field in check
                ), f"Missing field {field} in check {check.get('check_id')}"

    def test_schema_version(self):
        df = _make_df()
        gate = compute_semantic_gate(df, "SMOKE", "val", 42)
        assert gate["schema_version"] == SEMANTIC_GATE_SCHEMA_VERSION

    def test_json_serializable(self):
        df = _make_df(n_hands=500)
        gate = compute_semantic_gate(df, "FULL", "val", 42)
        # Should not raise
        json.dumps(gate)


class TestSmokeMode:
    def test_smoke_skips_statistical(self):
        df = _make_df(n_hands=15)
        gate = compute_semantic_gate(df, "SMOKE", "val", 42)
        for check in gate["checks"]:
            if check["category"] in ("fairness", "directional_sanity"):
                assert check["status"] == "SKIP", (
                    f"Expected SKIP for {check['check_id']} in SMOKE mode, "
                    f"got {check['status']}"
                )

    def test_smoke_runs_health_checks(self):
        df = _make_df(n_hands=15)
        gate = compute_semantic_gate(df, "SMOKE", "val", 42)
        health = [c for c in gate["checks"] if c["category"] == "health"]
        # Should have health checks that aren't all SKIP
        non_skip = [c for c in health if c["status"] != "SKIP"]
        assert len(non_skip) > 0

    def test_smoke_large_n_still_skips_statistical(self):
        """SMOKE mode must skip statistical checks even with large datasets."""
        df = _make_df(n_hands=1000)
        gate = compute_semantic_gate(df, "SMOKE", "val", 42)
        for check in gate["checks"]:
            if check["category"] in ("fairness", "directional_sanity"):
                assert check["status"] == "SKIP", (
                    f"Expected SKIP for {check['check_id']} in SMOKE mode "
                    f"with large N, got {check['status']}"
                )


class TestFullMode:
    def test_full_runs_all_with_predictions(self):
        df = _make_df(n_hands=2500)
        noise = np.random.RandomState(42).normal(0, 0.5, len(df))
        preds = df["tricks_won"].values + noise
        gate = compute_semantic_gate(
            df,
            "FULL",
            "val",
            42,
            feature_cols=FEATURE_COLS,
            predictions=preds,
        )
        # With sufficient data and predictions, no checks should SKIP
        # (except possibly per-contract checks with small N)
        skips = [c for c in gate["checks"] if c["status"] == "SKIP"]
        # Very few skips expected
        assert (
            len(skips) <= 3
        ), f"Too many skips in FULL mode: {[s['check_id'] for s in skips]}"


class TestCustomThresholds:
    def test_tighter_r_squared(self):
        df = _make_df(n_hands=1000)
        # Predictions with moderate correlation
        noise = np.random.RandomState(42).normal(0, 1.5, len(df))
        preds = df["tricks_won"].values + noise
        # With very tight threshold (0.99), should fail
        gate_tight = compute_semantic_gate(
            df,
            "FULL",
            "val",
            42,
            predictions=preds,
            custom_thresholds={"min_r_squared": 0.99},
        )
        r2_tight = [
            c for c in gate_tight["checks"] if c["check_id"] == "r_squared_floor"
        ]
        assert any(c["status"] == "FAIL" for c in r2_tight)


class TestEmitSemanticGate:
    def test_writes_val_file(self, tmp_path):
        gate = {"gate_status": "PASS", "active_split": "val", "checks": []}
        path = emit_semantic_gate(gate, tmp_path)
        assert path.name == "semantic_gate_val.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["gate_status"] == "PASS"

    def test_writes_test_file(self, tmp_path):
        gate = {"gate_status": "PASS", "active_split": "test", "checks": []}
        path = emit_semantic_gate(gate, tmp_path)
        assert path.name == "semantic_gate_test.json"

    def test_override_split(self, tmp_path):
        gate = {"gate_status": "PASS", "active_split": "val", "checks": []}
        path = emit_semantic_gate(gate, tmp_path, active_split="test")
        assert path.name == "semantic_gate_test.json"

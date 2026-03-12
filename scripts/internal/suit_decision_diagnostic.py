"""R1.5.3 Step 0: Decision-level suit diagnostic.

Decomposes the -0.142 suit net_eppd deficit into decision failure modes
to determine which treatment track (A/B/C) to pursue.

Four analyses:
1. Error taxonomy: over-bid, under-bid, wrong contract, wrong level
2. Disagreement state analysis: AV v1 vs R0 suit bid differences
3. Make/set boundary behavior: where do costly errors concentrate?
4. Bid-level headroom (H13): does always-bid-4 leave value on table?

Usage:
    uv run python scripts/internal/suit_decision_diagnostic.py \
        --h2h-dir data/runs/arc_d_r0_h2h_battery_42_20260308_173038 \
        --cf-dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
        --seed 42 \
        --output-dir data/artifacts/r1_5_3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── Imports from bid_euchre ──────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from bid_euchre.core.time import utc_now_iso  # noqa: E402
from bid_euchre.datasets.eval_dataset import build_eval_dataset  # noqa: E402
from bid_euchre.strategy.bidding import (  # noqa: E402
    predict_ols,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────

# Matchup file patterns for AV v1 vs R0 (hybrid_olsa_r0)
_AV1_VS_R0_PATTERN = "action_value_v1_vs_hybrid_olsa_r0"
_R0_VS_AV1_PATTERN = "hybrid_olsa_r0_vs_action_value_v1"

# Also include hybrid_olsa_full_r0 matchups for broader R0 comparison
_AV1_VS_R0F_PATTERN = "action_value_v1_vs_hybrid_olsa_full_r0"
_R0F_VS_AV1_PATTERN = "hybrid_olsa_full_r0_vs_action_value_v1"


# ── Data Loading ─────────────────────────────────────────────


def load_h2h_suit_hands(log_dir: Path) -> pd.DataFrame:
    """Load AV v1 vs R0 H2H matchups, returning suit-contract bidder rows.

    Loads from both AV1-vs-R0 and R0-vs-AV1 log files to capture both
    seat configurations. Filters to suit contract, is_bidder == True.

    Returns DataFrame with columns from build_eval_dataset plus:
    - matchup: which log file the hand came from
    - av1_team: which team (0 or 1) AV v1 is on
    """
    logs_dir = log_dir / "logs"
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    patterns = [
        (_AV1_VS_R0_PATTERN, 0),  # AV v1 is team 0
        (_R0_VS_AV1_PATTERN, 1),  # AV v1 is team 1
        (_AV1_VS_R0F_PATTERN, 0),  # AV v1 is team 0 (vs full)
        (_R0F_VS_AV1_PATTERN, 1),  # AV v1 is team 1 (vs full)
    ]

    frames = []
    for pattern, av1_team in patterns:
        matches = list(logs_dir.glob(f"*{pattern}.jsonl"))
        for log_path in matches:
            df = build_eval_dataset(log_path)
            df["matchup"] = pattern
            df["av1_team"] = av1_team
            frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No AV v1 vs R0 log files found in {logs_dir}")

    combined = pd.concat(frames, ignore_index=True)

    # Filter to suit contracts where the AV v1 player is the bidder
    suit_mask = combined["contract_type"] == "suit"
    bidder_mask = combined["is_bidder"]
    # AV v1 bidder: bidder is on the AV v1 team
    av1_bidder_mask = combined.apply(
        lambda row: (row["team"] == row["av1_team"]) if row["is_bidder"] else False,
        axis=1,
    )

    return combined[suit_mask & bidder_mask & av1_bidder_mask].copy()


def load_counterfactual_suit(parquet_path: Path) -> pd.DataFrame:
    """Load counterfactual dataset, filter to suit rows with focal_declared.

    Adds derived columns:
    - made_contract: bool (tricks_won >= bid_n)
    - bid_n_sq: bid_n squared
    """
    df = pd.read_parquet(parquet_path)

    # Filter to suit, declared actions (not pass, not defending)
    suit_mask = df["contract_family"] == "suit"
    declared_mask = df["focal_declared"]

    result = df[suit_mask & declared_mask].copy()
    result["made_contract"] = result["tricks_won"] >= result["bid_n"]
    result["bid_n_sq"] = result["bid_n"] ** 2

    return result


def load_counterfactual_all(parquet_path: Path) -> pd.DataFrame:
    """Load full counterfactual dataset with all contract types.

    For wrong-contract and pass analysis — need to compare suit EV
    against high/low/pass EVs for the same hand.
    """
    df = pd.read_parquet(parquet_path)
    df["bid_n_sq"] = df["bid_n"] ** 2
    df["made_contract"] = np.where(
        df["focal_declared"],
        df["tricks_won"] >= df["bid_n"],
        False,
    )
    return df


def reconstruct_ols_predictions(
    cf_df: pd.DataFrame,
    artifact_path: Path,
) -> np.ndarray:
    """Reconstruct OLS suit predictions from model artifact.

    Maps parquet column names to the feature order expected by predict_ols.
    Returns array of predicted E[net_points] for each row.
    """
    with open(artifact_path) as f:
        artifact = json.load(f)

    suit_model = artifact["models"]["suit"]
    feature_names = suit_model["feature_names"]

    predictions = np.zeros(len(cf_df))
    for i, (_, row) in enumerate(cf_df.iterrows()):
        features = np.zeros(len(feature_names))
        for j, name in enumerate(feature_names):
            if name == "bid_n_sq":
                features[j] = float(row["bid_n"]) ** 2
            elif name in cf_df.columns:
                features[j] = float(row[name])
            else:
                logger.warning("Feature %s not found in dataset", name)
        predictions[i] = predict_ols(suit_model, features)

    return predictions


def reconstruct_ols_predictions_vectorized(
    cf_df: pd.DataFrame,
    artifact_path: Path,
) -> np.ndarray:
    """Vectorized version of OLS prediction reconstruction.

    Much faster than row-by-row for large datasets.
    """
    with open(artifact_path) as f:
        artifact = json.load(f)

    suit_model = artifact["models"]["suit"]
    feature_names = suit_model["feature_names"]
    coefficients = np.asarray(suit_model["coefficients"], dtype=np.float64)
    intercept = float(suit_model.get("intercept", 0.0))

    n_rows = len(cf_df)
    X = np.zeros((n_rows, len(feature_names)))

    for j, name in enumerate(feature_names):
        if name == "bid_n_sq":
            X[:, j] = (cf_df["bid_n"].values ** 2).astype(np.float64)
        elif name in cf_df.columns:
            X[:, j] = cf_df[name].values.astype(np.float64)
        else:
            logger.warning("Feature %s not found in dataset", name)

    return X @ coefficients + intercept


# ── Analysis 1: Error Taxonomy ───────────────────────────────


def analyze_error_taxonomy(
    h2h_df: pd.DataFrame,
    cf_all: pd.DataFrame,
) -> dict:
    """Classify suit bid errors into over-bid, correct, etc.

    Uses H2H data for actual gameplay outcomes. For each suit hand where
    AV v1 is the bidder:
    - Over-bid: bid suit and got set (made_bid == False)
    - Correct made: bid suit and made
    - Then estimate cost relative to what R0 achieves on similar hands.

    For counterfactual analysis (wrong contract, under-bid), uses the CF
    dataset grouped by hand_id.
    """
    # Basic error taxonomy from H2H outcomes
    n_total = len(h2h_df)
    if n_total == 0:
        return {"error": "No suit hands found in H2H data"}

    # Over-bid: AV v1 bid suit but got set
    over_bid = h2h_df[~h2h_df["made_bid"]]
    # Made: AV v1 bid suit and made it
    made = h2h_df[h2h_df["made_bid"]]

    # Points analysis
    avg_points_over_bid = over_bid["points_won"].mean() if len(over_bid) > 0 else 0.0
    avg_points_made = made["points_won"].mean() if len(made) > 0 else 0.0
    avg_points_overall = h2h_df["points_won"].mean()

    # Counterfactual: wrong-contract analysis
    # For each hand_id in CF data, compare suit EV to best alternative
    wrong_contract = _analyze_wrong_contract(cf_all)

    # Counterfactual: under-bid analysis (passed hands where suit was profitable)
    under_bid = _analyze_under_bid(cf_all)

    # Counterfactual: wrong-level analysis
    wrong_level = _analyze_wrong_level(cf_all)

    taxonomy = {
        "n_suit_hands_h2h": n_total,
        "over_bid": {
            "count": len(over_bid),
            "fraction": len(over_bid) / n_total,
            "avg_points": float(avg_points_over_bid),
            "description": "AV v1 bid suit and got set",
        },
        "made": {
            "count": len(made),
            "fraction": len(made) / n_total,
            "avg_points": float(avg_points_made),
            "description": "AV v1 bid suit and made",
        },
        "avg_points_overall": float(avg_points_overall),
        "wrong_contract": wrong_contract,
        "under_bid": under_bid,
        "wrong_level": wrong_level,
    }

    return taxonomy


def _analyze_wrong_contract(cf_all: pd.DataFrame) -> dict:
    """Identify hands where suit was bid but high/low would yield more.

    Groups counterfactual data by hand_id. For each hand where the focal
    player declared suit, compare suit net_points to high/low alternatives.
    """
    # Get suit-declared hands
    suit_declared = cf_all[
        (cf_all["contract_family"] == "suit") & cf_all["focal_declared"]
    ]

    if len(suit_declared) == 0:
        return {"count": 0, "fraction": 0.0, "avg_cost": 0.0}

    # For each hand_id, find the best alternative (high or low)
    hand_ids = suit_declared["hand_id"].unique()

    # Get all actions for these hands
    all_actions = cf_all[cf_all["hand_id"].isin(hand_ids)]

    # Group by hand_id: for each hand, get suit net_points and best alt
    results = []
    for hid in hand_ids:
        hand_actions = all_actions[all_actions["hand_id"] == hid]
        suit_rows = hand_actions[
            (hand_actions["contract_family"] == "suit") & hand_actions["focal_declared"]
        ]
        alt_rows = hand_actions[
            hand_actions["contract_family"].isin(["high", "low"])
            & hand_actions["focal_declared"]
        ]

        if len(suit_rows) == 0 or len(alt_rows) == 0:
            continue

        # Best suit outcome (max net_points across suit bids)
        best_suit = suit_rows["net_points"].max()
        # Best alternative outcome
        best_alt = alt_rows["net_points"].max()

        if best_alt > best_suit:
            results.append(
                {
                    "hand_id": hid,
                    "suit_net_pts": float(best_suit),
                    "best_alt_net_pts": float(best_alt),
                    "cost": float(best_suit - best_alt),  # negative = suit was worse
                }
            )

    n_wrong_contract = len(results)
    n_hands = len(hand_ids)
    avg_cost = np.mean([r["cost"] for r in results]) if results else 0.0

    return {
        "count": n_wrong_contract,
        "n_suit_hands": n_hands,
        "fraction": n_wrong_contract / n_hands if n_hands > 0 else 0.0,
        "avg_cost": float(avg_cost),
        "description": "Hands where high/low would yield more than suit",
    }


def _analyze_under_bid(cf_all: pd.DataFrame) -> dict:
    """Identify hands where pass was chosen but suit would be profitable.

    Looks at pass actions in the CF dataset and checks if suit alternatives
    have positive net_points.
    """
    # Get pass actions
    pass_rows = cf_all[cf_all["action_type"] == "pass"]
    if len(pass_rows) == 0:
        return {"count": 0, "fraction": 0.0, "avg_opportunity": 0.0}

    pass_hand_ids = pass_rows["hand_id"].unique()

    # For each pass hand, check if suit bid would have been profitable
    suit_bids = cf_all[
        (cf_all["hand_id"].isin(pass_hand_ids))
        & (cf_all["contract_family"] == "suit")
        & cf_all["focal_declared"]
    ]

    results = []
    for hid in pass_hand_ids:
        hand_suit = suit_bids[suit_bids["hand_id"] == hid]
        if len(hand_suit) == 0:
            continue
        best_suit = hand_suit["net_points"].max()
        pass_net = pass_rows[pass_rows["hand_id"] == hid]["net_points"].iloc[0]
        if best_suit > pass_net:
            results.append(
                {
                    "hand_id": hid,
                    "pass_net_pts": float(pass_net),
                    "suit_net_pts": float(best_suit),
                    "opportunity": float(best_suit - pass_net),
                }
            )

    n_under_bid = len(results)
    n_pass = len(pass_hand_ids)
    avg_opportunity = np.mean([r["opportunity"] for r in results]) if results else 0.0

    return {
        "count": n_under_bid,
        "n_pass_hands": n_pass,
        "fraction": n_under_bid / n_pass if n_pass > 0 else 0.0,
        "avg_opportunity": float(avg_opportunity),
        "description": "Pass hands where suit would have been profitable",
    }


def _analyze_wrong_level(cf_all: pd.DataFrame) -> dict:
    """Identify suit hands where a different bid level would improve EV.

    For hands with suit bids, compare the chosen level (typically 4)
    to all other legal levels.
    """
    suit_declared = cf_all[
        (cf_all["contract_family"] == "suit") & cf_all["focal_declared"]
    ]

    if len(suit_declared) == 0:
        return {"count": 0, "fraction": 0.0, "avg_cost": 0.0}

    # Group by hand_id: compare net_points across bid levels
    hand_groups = suit_declared.groupby("hand_id")

    wrong_level_count = 0
    total_hands = 0
    costs = []

    for _hid, group in hand_groups:
        if len(group) < 2:
            continue  # Only one level available
        total_hands += 1

        # The minimum legal bid is what AV v1 typically picks (level 4)
        min_bid = group["bid_n"].min()
        min_bid_row = group[group["bid_n"] == min_bid]
        min_bid_pts = min_bid_row["net_points"].values[0]

        # Best level
        best_row = group.loc[group["net_points"].idxmax()]
        best_pts = best_row["net_points"]
        best_level = best_row["bid_n"]

        if best_level != min_bid and best_pts > min_bid_pts:
            wrong_level_count += 1
            costs.append(float(min_bid_pts - best_pts))  # negative = wrong level hurts

    avg_cost = np.mean(costs) if costs else 0.0

    return {
        "count": wrong_level_count,
        "n_suit_hands": total_hands,
        "fraction": wrong_level_count / total_hands if total_hands > 0 else 0.0,
        "avg_cost": float(avg_cost),
        "description": "Suit hands where different bid level would improve EV",
    }


# ── Analysis 2: Disagreement State Analysis ──────────────────


def analyze_disagreements(h2h_df: pd.DataFrame, full_h2h_df: pd.DataFrame) -> dict:
    """Analyze AV v1 vs R0 disagreement states on suit decisions.

    Uses the full H2H DataFrame (all contract types, both bidders) to
    identify hands where AV v1 and R0 made different suit-related decisions.

    Parameters:
        h2h_df: Suit hands where AV v1 is the bidder (from load_h2h_suit_hands)
        full_h2h_df: All H2H hands (all contracts, both bidders)
    """
    # This analysis requires the raw JSONL auction transcripts, which
    # build_eval_dataset() doesn't preserve. We analyze at the outcome
    # level: compare AV v1 suit bid rate and outcomes across matchups.

    n_suit = len(h2h_df)

    # AV v1 suit outcomes by made/set
    made = h2h_df[h2h_df["made_bid"]]
    set_hands = h2h_df[~h2h_df["made_bid"]]

    # Compare to R0 suit rate in the same matchup
    # R0 is on the other team — find R0's suit bid rate from the same logs
    # Filter full_h2h_df for R0 as bidder on suit contracts
    r0_suit = full_h2h_df[
        (full_h2h_df["contract_type"] == "suit")
        & full_h2h_df["is_bidder"]
        & (full_h2h_df["team"] != full_h2h_df["av1_team"])
    ]

    return {
        "av1_suit_hands": n_suit,
        "av1_suit_made_rate": len(made) / n_suit if n_suit > 0 else 0.0,
        "av1_suit_avg_points": float(h2h_df["points_won"].mean())
        if n_suit > 0
        else 0.0,
        "av1_suit_set_rate": len(set_hands) / n_suit if n_suit > 0 else 0.0,
        "av1_suit_set_avg_cost": float(set_hands["points_won"].mean())
        if len(set_hands) > 0
        else 0.0,
        "r0_suit_hands": len(r0_suit),
        "r0_suit_made_rate": float(r0_suit["made_bid"].mean())
        if len(r0_suit) > 0
        else 0.0,
        "r0_suit_avg_points": float(r0_suit["points_won"].mean())
        if len(r0_suit) > 0
        else 0.0,
        "suit_bid_rate_ratio": n_suit / len(r0_suit)
        if len(r0_suit) > 0
        else float("inf"),
        "description": (
            "AV v1 vs R0 suit bidding comparison. Ratio > 1 means AV v1 bids "
            "suit more aggressively than R0."
        ),
    }


# ── Analysis 3: Make/Set Boundary ────────────────────────────


def analyze_boundary(
    cf_suit: pd.DataFrame,
    artifact_path: Path,
) -> dict:
    """Analyze where costly suit errors concentrate relative to make/set boundary.

    Reconstructs OLS predictions and bins by predicted EV to identify
    calibration patterns and error concentration.
    """
    if len(cf_suit) == 0:
        return {"error": "No suit data"}

    # Reconstruct OLS predictions
    predictions = reconstruct_ols_predictions_vectorized(cf_suit, artifact_path)
    actuals = cf_suit["net_points"].values
    made = cf_suit["made_contract"].values

    # Overall calibration
    residuals = actuals - predictions
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((actuals - actuals.mean()) ** 2)
    r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # Bin by predicted EV — 20 bins
    n_bins = 20
    pred_min, pred_max = predictions.min(), predictions.max()
    bin_edges = np.linspace(pred_min, pred_max, n_bins + 1)
    bin_indices = np.digitize(predictions, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)

    calibration_bins = []
    for b in range(n_bins):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        bin_center = (bin_edges[b] + bin_edges[b + 1]) / 2
        calibration_bins.append(
            {
                "bin_center": float(bin_center),
                "bin_low": float(bin_edges[b]),
                "bin_high": float(bin_edges[b + 1]),
                "n": int(mask.sum()),
                "p_make": float(made[mask].mean()),
                "avg_actual": float(actuals[mask].mean()),
                "avg_predicted": float(predictions[mask].mean()),
                "avg_residual": float(residuals[mask].mean()),
            }
        )

    # Define boundary regions by P(make) of the data in each bin
    # Boundary: bins where P(make) is in [0.3, 0.7]
    boundary_mask = np.zeros(len(cf_suit), dtype=bool)
    clear_make_mask = np.zeros(len(cf_suit), dtype=bool)
    clear_set_mask = np.zeros(len(cf_suit), dtype=bool)

    for b in range(n_bins):
        mask = bin_indices == b
        if mask.sum() == 0:
            continue
        p_make = made[mask].mean()
        if 0.3 <= p_make <= 0.7:
            boundary_mask |= mask
        elif p_make > 0.7:
            clear_make_mask |= mask
        else:
            clear_set_mask |= mask

    # Error cost in each region
    def region_stats(mask: np.ndarray) -> dict:
        if mask.sum() == 0:
            return {"n": 0, "avg_residual": 0.0, "total_residual": 0.0, "fraction": 0.0}
        return {
            "n": int(mask.sum()),
            "avg_residual": float(residuals[mask].mean()),
            "total_residual": float(residuals[mask].sum()),
            "p_make": float(made[mask].mean()),
            "avg_actual": float(actuals[mask].mean()),
            "avg_predicted": float(predictions[mask].mean()),
            "fraction": float(mask.sum() / len(cf_suit)),
        }

    # Absolute residual concentration
    abs_residuals = np.abs(residuals)
    total_abs_residual = abs_residuals.sum()

    boundary_abs = abs_residuals[boundary_mask].sum() if boundary_mask.any() else 0.0
    clear_make_abs = (
        abs_residuals[clear_make_mask].sum() if clear_make_mask.any() else 0.0
    )
    clear_set_abs = abs_residuals[clear_set_mask].sum() if clear_set_mask.any() else 0.0

    return {
        "r_squared": float(r_squared),
        "n_rows": len(cf_suit),
        "pred_range": [float(pred_min), float(pred_max)],
        "calibration_bins": calibration_bins,
        "boundary_region": region_stats(boundary_mask),
        "clear_make_region": region_stats(clear_make_mask),
        "clear_set_region": region_stats(clear_set_mask),
        "error_concentration": {
            "boundary_pct": float(boundary_abs / total_abs_residual * 100)
            if total_abs_residual > 0
            else 0.0,
            "clear_make_pct": float(clear_make_abs / total_abs_residual * 100)
            if total_abs_residual > 0
            else 0.0,
            "clear_set_pct": float(clear_set_abs / total_abs_residual * 100)
            if total_abs_residual > 0
            else 0.0,
        },
        "bimodality": {
            "overall_p_make": float(made.mean()),
            "made_avg_net_pts": float(actuals[made].mean()) if made.any() else 0.0,
            "set_avg_net_pts": float(actuals[~made].mean()) if (~made).any() else 0.0,
            "gap": float(actuals[made].mean() - actuals[~made].mean())
            if made.any() and (~made).any()
            else 0.0,
        },
    }


# ── Analysis 4: Bid-Level Headroom (H13) ────────────────────


def analyze_bid_level_headroom(cf_suit: pd.DataFrame) -> dict:
    """Analyze whether always-bidding-4 leaves value on the table.

    For suit hands in the counterfactual dataset, compare net_points
    at bid_n=4 to other bid levels for the same hand.
    """
    if len(cf_suit) == 0:
        return {"error": "No suit data"}

    # Group by hand_id
    hand_groups = cf_suit.groupby("hand_id")

    n_hands = 0
    n_improvable = 0
    improvements = []
    level_distribution = {}

    for _hid, group in hand_groups:
        levels = sorted(group["bid_n"].unique())
        if len(levels) < 2:
            continue

        n_hands += 1

        # Net points at each level
        level_pts = {}
        for _, row in group.iterrows():
            level = int(row["bid_n"])
            level_pts[level] = float(row["net_points"])

        # Minimum legal bid (what AV v1 typically picks)
        min_level = min(levels)
        min_pts = level_pts[min_level]

        # Best level
        best_level = max(level_pts, key=level_pts.get)
        best_pts = level_pts[best_level]

        # Track optimal level distribution
        level_distribution[best_level] = level_distribution.get(best_level, 0) + 1

        if best_level != min_level and best_pts > min_pts:
            n_improvable += 1
            improvements.append(best_pts - min_pts)

    avg_improvement = float(np.mean(improvements)) if improvements else 0.0
    total_headroom = float(np.sum(improvements))
    headroom_per_hand = total_headroom / n_hands if n_hands > 0 else 0.0

    return {
        "n_hands_analyzed": n_hands,
        "n_improvable": n_improvable,
        "pct_improvable": n_improvable / n_hands * 100 if n_hands > 0 else 0.0,
        "avg_improvement_when_improvable": avg_improvement,
        "headroom_per_hand": headroom_per_hand,
        "total_headroom": total_headroom,
        "optimal_level_distribution": {
            str(k): v for k, v in sorted(level_distribution.items())
        },
        "description": (
            "Headroom = how much net_points would improve if optimal bid level "
            "were chosen instead of minimum legal (typically 4)."
        ),
    }


# ── Gate Decision ────────────────────────────────────────────


def determine_gate_decision(
    taxonomy: dict,
    boundary: dict,
    headroom: dict,
) -> dict:
    """Apply gate criteria to determine recommended track.

    Returns gate decision with rationale.
    """
    rationale_parts = []
    recommended_track = None

    # Check error concentration at boundary
    boundary_pct = boundary.get("error_concentration", {}).get("boundary_pct", 0.0)

    # Check bid-level headroom significance
    headroom_per_hand = headroom.get("headroom_per_hand", 0.0)
    # Convert to approximate net_eppd scale (rough: divide by ~20 points/deal range)
    headroom_significant = headroom.get("pct_improvable", 0.0) > 30.0

    # Check wrong-contract fraction
    wrong_contract_frac = taxonomy.get("wrong_contract", {}).get("fraction", 0.0)

    # Gate logic from the decision tree
    if boundary_pct > 60:
        recommended_track = "Track A (Two-Stage Model)"
        rationale_parts.append(
            f"Boundary errors account for {boundary_pct:.1f}% of absolute residual "
            f"(>60% threshold). Classification at the make/set boundary is the right fix."
        )
    elif wrong_contract_frac > 0.3:
        recommended_track = "New direction (contract selection)"
        rationale_parts.append(
            f"Wrong-contract errors at {wrong_contract_frac:.1%} — dominant error "
            f"type is contract selection, not within-suit prediction."
        )
    elif headroom_significant:
        recommended_track = "Bid-level optimization"
        rationale_parts.append(
            f"Bid-level headroom at {headroom.get('pct_improvable', 0):.1f}% of hands "
            f"improvable — lighter-weight fix may capture significant value."
        )
    else:
        recommended_track = "Track B (GBT) or further investigation"
        rationale_parts.append(
            f"Errors spread across calibration range (boundary={boundary_pct:.1f}%). "
            f"Nonlinear model or alternative approach may be needed."
        )

    return {
        "recommended_track": recommended_track,
        "rationale": " ".join(rationale_parts),
        "gate_inputs": {
            "boundary_error_pct": boundary_pct,
            "wrong_contract_frac": wrong_contract_frac,
            "headroom_pct_improvable": headroom.get("pct_improvable", 0.0),
            "headroom_per_hand": headroom_per_hand,
        },
    }


# ── Report Generation ────────────────────────────────────────


def generate_report(results: dict, output_path: Path) -> None:
    """Generate markdown diagnostic report."""
    taxonomy = results["error_taxonomy"]
    disagreements = results["disagreements"]
    boundary = results["boundary_analysis"]
    headroom = results["bid_level_headroom"]
    gate = results["gate_decision"]

    lines = [
        "# R1.5.3 Step 0: Suit Decision Diagnostic",
        "",
        f"**Generated:** {results['metadata']['created_at_utc']}",
        f"**Seed:** {results['metadata']['seed']}",
        f"**Analysis SHA:** {results['metadata'].get('git_sha', 'unknown')}",
        "",
        "## Summary",
        "",
        f"**Gate decision:** {gate['recommended_track']}",
        "",
        f"{gate['rationale']}",
        "",
        "## 1. Error Taxonomy (H2H Data)",
        "",
        f"Total suit hands where AV v1 is bidder: **{taxonomy['n_suit_hands_h2h']:,}**",
        "",
        "| Category | Count | Fraction | Avg Points |",
        "|----------|-------|----------|------------|",
        f"| Over-bid (set) | {taxonomy['over_bid']['count']:,} | {taxonomy['over_bid']['fraction']:.1%} | {taxonomy['over_bid']['avg_points']:.1f} |",
        f"| Made | {taxonomy['made']['count']:,} | {taxonomy['made']['fraction']:.1%} | {taxonomy['made']['avg_points']:.1f} |",
        "",
        f"Overall average points when AV v1 bids suit: **{taxonomy['avg_points_overall']:.2f}**",
        "",
    ]

    # Wrong contract
    wc = taxonomy.get("wrong_contract", {})
    if wc.get("count", 0) > 0:
        lines.extend(
            [
                "### Wrong Contract (Counterfactual)",
                "",
                f"Of {wc.get('n_suit_hands', 0):,} suit-declared hands in CF data, "
                f"**{wc['count']:,}** ({wc['fraction']:.1%}) would have been better "
                f"served by high/low. Average cost: {wc['avg_cost']:.2f} net_pts.",
                "",
            ]
        )

    # Under-bid
    ub = taxonomy.get("under_bid", {})
    if ub.get("count", 0) > 0:
        lines.extend(
            [
                "### Under-Bid (Counterfactual)",
                "",
                f"Of {ub.get('n_pass_hands', 0):,} pass hands in CF data, "
                f"**{ub['count']:,}** ({ub['fraction']:.1%}) had a profitable suit "
                f"alternative. Average opportunity: {ub['avg_opportunity']:.2f} net_pts.",
                "",
            ]
        )

    # Wrong level
    wl = taxonomy.get("wrong_level", {})
    if wl.get("count", 0) > 0:
        lines.extend(
            [
                "### Wrong Level (Counterfactual)",
                "",
                f"Of {wl.get('n_suit_hands', 0):,} multi-level suit hands, "
                f"**{wl['count']:,}** ({wl['fraction']:.1%}) would benefit from "
                f"a different bid level. Average cost: {wl['avg_cost']:.2f} net_pts.",
                "",
            ]
        )

    # Disagreements
    lines.extend(
        [
            "## 2. AV v1 vs R0 Suit Comparison",
            "",
            "| Metric | AV v1 | R0 |",
            "|--------|-------|-----|",
            f"| Suit hands (as bidder) | {disagreements['av1_suit_hands']:,} | {disagreements['r0_suit_hands']:,} |",
            f"| Suit made rate | {disagreements['av1_suit_made_rate']:.1%} | {disagreements['r0_suit_made_rate']:.1%} |",
            f"| Suit avg points | {disagreements['av1_suit_avg_points']:.2f} | {disagreements['r0_suit_avg_points']:.2f} |",
            f"| Suit set rate | {disagreements['av1_suit_set_rate']:.1%} | {1 - disagreements['r0_suit_made_rate']:.1%} |",
            "",
            f"Suit bid rate ratio (AV v1 / R0): **{disagreements['suit_bid_rate_ratio']:.2f}**",
            "",
        ]
    )

    # Boundary analysis
    lines.extend(
        [
            "## 3. Make/Set Boundary Analysis",
            "",
            f"Suit R² (reconstructed): **{boundary['r_squared']:.3f}**",
            f"Rows analyzed: {boundary['n_rows']:,}",
            "",
            "### Bimodality",
            f"- P(make): {boundary['bimodality']['overall_p_make']:.1%}",
            f"- Made avg net_pts: {boundary['bimodality']['made_avg_net_pts']:.2f}",
            f"- Set avg net_pts: {boundary['bimodality']['set_avg_net_pts']:.2f}",
            f"- Gap: {boundary['bimodality']['gap']:.2f}",
            "",
            "### Error Concentration",
            "",
            "| Region | N | Fraction | Abs Residual % | P(make) | Avg Predicted | Avg Actual |",
            "|--------|---|----------|---------------|---------|--------------|------------|",
        ]
    )

    for region_name, region_key in [
        ("Boundary (0.3-0.7)", "boundary_region"),
        ("Clear make (>0.7)", "clear_make_region"),
        ("Clear set (<0.3)", "clear_set_region"),
    ]:
        r = boundary.get(region_key, {})
        ec = boundary.get("error_concentration", {})
        ec_key = region_key.replace("_region", "_pct")
        lines.append(
            f"| {region_name} | {r.get('n', 0):,} | {r.get('fraction', 0):.1%} | "
            f"{ec.get(ec_key, 0):.1f}% | {r.get('p_make', 0):.1%} | "
            f"{r.get('avg_predicted', 0):.2f} | {r.get('avg_actual', 0):.2f} |"
        )

    lines.append("")

    # Bid-level headroom
    lines.extend(
        [
            "## 4. Bid-Level Headroom (H13)",
            "",
            f"Hands analyzed: {headroom['n_hands_analyzed']:,}",
            f"Improvable by different level: **{headroom['n_improvable']:,}** ({headroom['pct_improvable']:.1f}%)",
            f"Average improvement (when improvable): {headroom['avg_improvement_when_improvable']:.2f} net_pts",
            f"Headroom per hand (overall): {headroom['headroom_per_hand']:.3f} net_pts",
            "",
            "### Optimal Level Distribution",
            "",
            "| Level | Count | Fraction |",
            "|-------|-------|----------|",
        ]
    )

    total_optimal = sum(int(v) for v in headroom["optimal_level_distribution"].values())
    for level, count in sorted(headroom["optimal_level_distribution"].items()):
        frac = int(count) / total_optimal if total_optimal > 0 else 0
        lines.append(f"| {level} | {count:,} | {frac:.1%} |")

    lines.extend(
        [
            "",
            "## 5. Gate Decision",
            "",
            f"**Recommended track:** {gate['recommended_track']}",
            "",
            f"{gate['rationale']}",
            "",
            "### Gate Inputs",
            "",
            "| Input | Value | Threshold |",
            "|-------|-------|-----------|",
            f"| Boundary error % | {gate['gate_inputs']['boundary_error_pct']:.1f}% | >60% → Track A |",
            f"| Wrong contract fraction | {gate['gate_inputs']['wrong_contract_frac']:.1%} | >30% → New direction |",
            f"| Bid-level improvable % | {gate['gate_inputs']['headroom_pct_improvable']:.1f}% | >30% → Level fix |",
            f"| Headroom per hand | {gate['gate_inputs']['headroom_per_hand']:.3f} | Qualitative |",
            "",
            "## Provenance",
            "",
            "| Item | Value |",
            "|------|-------|",
            f"| gate_status | {gate['recommended_track']} |",
            f"| analysis_sha | {results['metadata'].get('git_sha', 'unknown')} |",
            f"| seed | {results['metadata']['seed']} |",
            f"| h2h_source | {results['metadata']['h2h_dir']} |",
            f"| cf_source | {results['metadata']['cf_dataset']} |",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    logger.info("Report written to %s", output_path)


# ── Main ─────────────────────────────────────────────────────


def run_diagnostic(
    h2h_dir: Path,
    cf_dataset: Path,
    artifact_path: Path | None,
    seed: int,
    output_dir: Path,
    report_path: Path,
) -> dict:
    """Run the full suit decision diagnostic.

    Returns the complete results dict.
    """
    logger.info("Loading H2H suit hands from %s", h2h_dir)
    h2h_suit = load_h2h_suit_hands(h2h_dir)
    logger.info("Loaded %d suit hands (AV v1 bidder)", len(h2h_suit))

    # Also load full H2H for disagreement analysis
    full_h2h = _load_full_h2h(h2h_dir)

    logger.info("Loading counterfactual dataset from %s", cf_dataset)
    cf_suit = load_counterfactual_suit(cf_dataset)
    logger.info("Loaded %d counterfactual suit rows", len(cf_suit))

    cf_all = load_counterfactual_all(cf_dataset)
    logger.info("Loaded %d total counterfactual rows", len(cf_all))

    # Find artifact path if not provided
    if artifact_path is None:
        artifact_path = _find_artifact(h2h_dir)

    # Analysis 1: Error Taxonomy
    logger.info("Running Analysis 1: Error Taxonomy")
    taxonomy = analyze_error_taxonomy(h2h_suit, cf_all)

    # Analysis 2: Disagreement States
    logger.info("Running Analysis 2: Disagreement States")
    disagreements = analyze_disagreements(h2h_suit, full_h2h)

    # Analysis 3: Make/Set Boundary
    logger.info("Running Analysis 3: Make/Set Boundary")
    boundary = analyze_boundary(cf_suit, artifact_path)

    # Analysis 4: Bid-Level Headroom
    logger.info("Running Analysis 4: Bid-Level Headroom (H13)")
    headroom = analyze_bid_level_headroom(cf_suit)

    # Gate Decision
    gate = determine_gate_decision(taxonomy, boundary, headroom)
    logger.info("Gate decision: %s", gate["recommended_track"])

    # Get git SHA
    try:
        import subprocess

        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        git_sha = "unknown"

    results = {
        "metadata": {
            "created_at_utc": utc_now_iso(),
            "seed": seed,
            "git_sha": git_sha,
            "h2h_dir": str(h2h_dir),
            "cf_dataset": str(cf_dataset),
            "artifact_path": str(artifact_path),
        },
        "error_taxonomy": taxonomy,
        "disagreements": disagreements,
        "boundary_analysis": boundary,
        "bid_level_headroom": headroom,
        "gate_decision": gate,
    }

    # Write JSON artifact
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_out = output_dir / "suit_error_taxonomy.json"
    with open(artifact_out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Artifact written to %s", artifact_out)

    # Generate report
    generate_report(results, report_path)

    return results


def _load_full_h2h(log_dir: Path) -> pd.DataFrame:
    """Load all H2H hands (all contracts, both bidders) for disagreement analysis."""
    logs_dir = log_dir / "logs"
    patterns = [
        (_AV1_VS_R0_PATTERN, 0),
        (_R0_VS_AV1_PATTERN, 1),
        (_AV1_VS_R0F_PATTERN, 0),
        (_R0F_VS_AV1_PATTERN, 1),
    ]

    frames = []
    for pattern, av1_team in patterns:
        matches = list(logs_dir.glob(f"*{pattern}.jsonl"))
        for log_path in matches:
            df = build_eval_dataset(log_path)
            df["matchup"] = pattern
            df["av1_team"] = av1_team
            frames.append(df)

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _find_artifact(h2h_dir: Path) -> Path:
    """Find the AV v1 model artifact from the H2H run directory."""
    artifacts_dir = h2h_dir / "artifacts"
    if artifacts_dir.exists():
        jsons = list(artifacts_dir.glob("*.json"))
        for j in jsons:
            with open(j) as f:
                data = json.load(f)
            if data.get("schema_version") == "action_value_olsa_v1":
                return j

    # Fallback: search in data/artifacts
    fallback = Path("data/artifacts")
    if fallback.exists():
        for j in fallback.rglob("*.json"):
            try:
                with open(j) as f:
                    data = json.load(f)
                if data.get("schema_version") == "action_value_olsa_v1":
                    return j
            except (json.JSONDecodeError, KeyError):
                continue

    raise FileNotFoundError("Could not find action_value_olsa_v1 artifact")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R1.5.3 Step 0: Decision-level suit diagnostic"
    )
    parser.add_argument(
        "--h2h-dir",
        type=Path,
        required=True,
        help="Path to FULL H2H battery run directory",
    )
    parser.add_argument(
        "--cf-dataset",
        type=Path,
        required=True,
        help="Path to counterfactual action-value parquet",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="Path to AV v1 model artifact JSON (auto-detected if omitted)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/artifacts/r1_5_3"),
        help="Output directory for JSON artifact",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/04_reports/r1_5/suit_decision_diagnostic.md"),
        help="Output path for markdown report",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    run_diagnostic(
        h2h_dir=args.h2h_dir,
        cf_dataset=args.cf_dataset,
        artifact_path=args.artifact,
        seed=args.seed,
        output_dir=args.output_dir,
        report_path=args.report,
    )


if __name__ == "__main__":
    main()

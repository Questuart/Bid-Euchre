#!/usr/bin/env python
"""Normalizer offline go/no-go screen.

Fast offline screening pipeline to decide whether Track E normalizer is worth
full A/B implementation. Uses existing oracle-style data — no experiment reruns.

See plans/r0_v2_normalizer_screen_spec.md for full specification.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from bid_euchre.analysis.sweep import (
    bid_level_search_vectorized,
    bootstrap_paired_delta,
    check_guardrails,
    deal_partition,
)
from bid_euchre.datasets.join import join_features_outcomes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONTRACT_KEYS = ["high", "low", "suit_C", "suit_D", "suit_H", "suit_S"]
FAMILY_FOR_KEY = {
    "high": "high",
    "low": "low",
    "suit_C": "suit",
    "suit_D": "suit",
    "suit_H": "suit",
    "suit_S": "suit",
}
FAMILY_NAMES = ["high", "low", "suit"]  # alphabetical, parallel with CONTRACT_KEYS
FAMILY_IDX_FOR_KEY = np.array(
    [FAMILY_NAMES.index(FAMILY_FOR_KEY[k]) for k in CONTRACT_KEYS]
)
# = [0, 1, 2, 2, 2, 2]  (high=0, low=1, suit=2)

N_CONTRACTS = len(CONTRACT_KEYS)
N_FAMILIES = len(FAMILY_NAMES)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalizer offline go/no-go screen",
    )
    parser.add_argument(
        "--bidless-path",
        default=(
            "data/runs/canonical_bidless_dataset_glutton_42_20260221_175752"
            "/datasets/bidless.parquet"
        ),
    )
    parser.add_argument(
        "--outcomes-path",
        default=(
            "data/runs/canonical_bidless_dataset_glutton_42_20260221_175752"
            "/datasets/bidless_outcomes.parquet"
        ),
    )
    parser.add_argument(
        "--artifact-path",
        default="data/artifacts/arc_d/r0/hybrid_r0.json",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pass-threshold", type=float, default=0.0)
    parser.add_argument("--risk-lambda", type=float, default=0.0)
    parser.add_argument("--n-bootstrap", type=int, default=10000)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Data construction
# ---------------------------------------------------------------------------


def load_artifact(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def build_hand_table(
    df: pd.DataFrame,
    artifact: dict,
    pass_threshold: float,
    risk_lambda: float,
    seed: int,
) -> pd.DataFrame:
    """Build per-row predictions: mu, bid_n, utility, actual_net.

    Returns DataFrame with one row per (deal_id, seat, contract_key), sorted
    by (deal_id, seat, contract_key) for reshaping to ``(n_hands, 6)``.
    """
    df = df.copy()

    # Add contract_key: suit_C/suit_D/suit_H/suit_S/high/low
    mask_suit = df["contract_type"] == "suit"
    df["contract_key"] = df["contract_type"]
    df.loc[mask_suit, "contract_key"] = "suit_" + df.loc[mask_suit, "trump_suit"]
    df["contract_family"] = df["contract_type"]

    # Keep only complete groups: each (deal_id, seat) needs all 6 contract_keys
    group_sizes = df.groupby(["deal_id", "seat"])["contract_key"].transform("nunique")
    df = df[group_sizes == N_CONTRACTS].copy()

    # Predict mu per contract family using OLS weights from artifact
    df["mu"] = np.nan
    for family in FAMILY_NAMES:
        model = artifact["payoff_model"][family]
        mask = df["contract_family"] == family
        mu = np.full(mask.sum(), model["bias"])
        for w, fname in zip(model["weights"], model["feature_names"]):
            mu += w * df.loc[mask, fname].values
        df.loc[mask, "mu"] = mu

    # Bid-level search per contract family
    df["bid_n"] = 0
    df["utility"] = -np.inf
    for family in FAMILY_NAMES:
        mask = df["contract_family"] == family
        sigma = math.sqrt(artifact["residual_variance"][family])
        mu_vals = df.loc[mask, "mu"].values
        bid_n, utility = bid_level_search_vectorized(
            mu_vals,
            sigma,
            risk_lambda=risk_lambda,
            pass_threshold=pass_threshold,
            seed=seed,
        )
        df.loc[mask, "bid_n"] = bid_n
        df.loc[mask, "utility"] = utility

    # Compute actual_net: scoring payoff given bid_n and tricks_won
    df["actual_net"] = np.where(
        df["bid_n"] == 0,
        0.0,
        np.where(
            df["tricks_won"] >= df["bid_n"],
            2.0 * df["tricks_won"] - 10.0,  # make
            df["tricks_won"] - df["bid_n"] - 10.0,  # set
        ),
    )

    # Sort for consistent (n_hands, 6) reshaping
    df = df.sort_values(["deal_id", "seat", "contract_key"]).reset_index(drop=True)

    return df[
        [
            "deal_id",
            "seat",
            "contract_key",
            "contract_family",
            "mu",
            "bid_n",
            "utility",
            "actual_net",
            "tricks_won",
        ]
    ]


# ---------------------------------------------------------------------------
# Hand-level decisions
# ---------------------------------------------------------------------------


def make_hand_decisions(hand_table: pd.DataFrame) -> dict:
    """Per-hand oracle and model contract decisions.

    Returns dict of arrays. Scalar arrays have shape ``(n_hands,)``;
    per-contract arrays have shape ``(n_hands, 6)``.
    """
    n_rows = len(hand_table)
    assert n_rows % N_CONTRACTS == 0, f"Rows ({n_rows}) not divisible by {N_CONTRACTS}"
    n_hands = n_rows // N_CONTRACTS

    # Reshape long → wide: each hand gets a row of 6 contracts
    utilities = hand_table["utility"].values.reshape(n_hands, N_CONTRACTS)
    bid_ns = hand_table["bid_n"].values.astype(int).reshape(n_hands, N_CONTRACTS)
    actual_nets = hand_table["actual_net"].values.reshape(n_hands, N_CONTRACTS)
    tricks_won = hand_table["tricks_won"].values.reshape(n_hands, N_CONTRACTS)
    deal_ids = hand_table["deal_id"].values.reshape(n_hands, N_CONTRACTS)[:, 0]
    seats = hand_table["seat"].values.reshape(n_hands, N_CONTRACTS)[:, 0]

    # --- Oracle: argmax actual_net (all contracts eligible since bid_n > 0) ---
    oracle_idx = np.argmax(actual_nets, axis=1)
    oracle_net = np.take_along_axis(actual_nets, oracle_idx[:, None], axis=1).squeeze(
        -1
    )

    # --- Model: argmax utility where utility > 0 ---
    # Tie-break: higher bid_n → higher contract_key index
    model_eligible = utilities > 0
    ck_index = np.arange(N_CONTRACTS)[None, :]
    tiebreak = bid_ns * 1e-10 + ck_index * 1e-14
    model_scores = np.where(model_eligible, utilities + tiebreak, -np.inf)
    model_idx = np.argmax(model_scores, axis=1)
    model_net = np.take_along_axis(actual_nets, model_idx[:, None], axis=1).squeeze(-1)
    # If all utility <= 0, model passes
    all_pass = ~model_eligible.any(axis=1)
    model_idx = np.where(all_pass, -1, model_idx)
    model_net = np.where(all_pass, 0.0, model_net)

    return {
        "deal_ids": deal_ids,
        "seats": seats,
        "utilities": utilities,
        "bid_ns": bid_ns,
        "actual_nets": actual_nets,
        "tricks_won": tricks_won,
        "oracle_idx": oracle_idx,
        "oracle_net": oracle_net,
        "model_idx": model_idx,
        "model_net": model_net,
    }


# ---------------------------------------------------------------------------
# Diagnostic Zero
# ---------------------------------------------------------------------------


def diagnostic_zero(decisions: dict) -> dict:
    """Utility gap distribution on disagreement hands.

    On hands where oracle and model disagree, compute the gap between the
    model's chosen utility and the oracle's chosen utility. Large positive
    gaps indicate model poverty (model is confidently wrong), not
    miscalibration that a normalizer could fix.
    """
    oracle_idx = decisions["oracle_idx"]
    model_idx = decisions["model_idx"]
    utilities = decisions["utilities"]

    both_bid = model_idx >= 0
    disagree = both_bid & (oracle_idx != model_idx)
    n_disagree = int(disagree.sum())
    n_total = int(both_bid.sum())

    if n_disagree == 0:
        return {
            "n_total_hands": n_total,
            "n_disagreement_hands": 0,
            "disagreement_rate": 0.0,
            "utility_gap_quantiles": {"p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0},
            "early_exit": False,
        }

    # Utility gap: model's chosen utility minus oracle's chosen utility
    model_util = utilities[disagree, model_idx[disagree]]
    oracle_util = utilities[disagree, oracle_idx[disagree]]
    gap = model_util - oracle_util

    quantiles = {
        "p25": round(float(np.percentile(gap, 25)), 4),
        "p50": round(float(np.percentile(gap, 50)), 4),
        "p75": round(float(np.percentile(gap, 75)), 4),
        "p90": round(float(np.percentile(gap, 90)), 4),
    }

    # Early exit: model poverty, not miscalibration
    early_exit = quantiles["p50"] > 2.0 and quantiles["p75"] > 3.0

    return {
        "n_total_hands": n_total,
        "n_disagreement_hands": n_disagree,
        "disagreement_rate": round(n_disagree / n_total, 4) if n_total > 0 else 0.0,
        "utility_gap_quantiles": quantiles,
        "early_exit": early_exit,
    }


# ---------------------------------------------------------------------------
# Normalizer fitting
# ---------------------------------------------------------------------------


def softmax_nll(
    params: np.ndarray,
    utilities: np.ndarray,
    oracle_indices: np.ndarray,
    family_indices: np.ndarray,
    lambda_reg: float,
) -> float:
    """Negative log-likelihood of oracle contract under softmax.

    Parameters are ``[alpha_high, alpha_low, alpha_suit, beta_high, beta_low,
    beta_suit]`` — 6 values total, 3 contract families.
    """
    alpha = params[:N_FAMILIES]
    beta = params[N_FAMILIES:]

    alpha_per_key = alpha[family_indices]
    beta_per_key = beta[family_indices]

    u_norm = utilities * alpha_per_key[None, :] + beta_per_key[None, :]

    # Log-softmax (numerically stable)
    max_u = np.max(u_norm, axis=1, keepdims=True)
    log_sum_exp = max_u.squeeze(-1) + np.log(np.sum(np.exp(u_norm - max_u), axis=1))
    oracle_u = u_norm[np.arange(len(oracle_indices)), oracle_indices]

    nll = -np.mean(oracle_u - log_sum_exp)

    # L2 regularization toward identity (alpha=1, beta=0)
    reg = lambda_reg * (np.sum((alpha - 1.0) ** 2) + np.sum(beta**2))

    return nll + reg


def fit_normalizer(
    decisions: dict,
    train_mask: np.ndarray,
    lambda_reg: float = 1e-3,
) -> dict:
    """Fit affine normalizer via softmax NLL on train split.

    Returns dict with optimizer_status, params, train accuracy stats, and
    final loss.
    """
    oracle_valid = decisions["oracle_idx"] >= 0  # always true in practice
    mask = train_mask & oracle_valid

    utilities = decisions["utilities"][mask]
    oracle_indices = decisions["oracle_idx"][mask]

    # Baseline train accuracy
    model_idx_train = decisions["model_idx"][mask]
    train_accuracy_baseline = float(np.mean(model_idx_train == oracle_indices))

    x0 = np.array([1.0] * N_FAMILIES + [0.0] * N_FAMILIES)
    bounds = [(0.5, 2.0)] * N_FAMILIES + [(-5.0, 5.0)] * N_FAMILIES

    result = minimize(
        softmax_nll,
        x0,
        args=(utilities, oracle_indices, FAMILY_IDX_FOR_KEY, lambda_reg),
        method="L-BFGS-B",
        bounds=bounds,
    )

    if not result.success:
        return {
            "optimizer_status": f"FAILED: {result.message}",
            "params": None,
            "train_accuracy_baseline": train_accuracy_baseline,
            "train_accuracy_normalized": None,
            "final_loss": None,
        }

    alpha = result.x[:N_FAMILIES]
    beta = result.x[N_FAMILIES:]
    params = {
        "alpha": {
            name: round(float(alpha[i]), 6) for i, name in enumerate(FAMILY_NAMES)
        },
        "beta": {name: round(float(beta[i]), 6) for i, name in enumerate(FAMILY_NAMES)},
    }

    # Normalized train accuracy
    alpha_per_key = alpha[FAMILY_IDX_FOR_KEY]
    beta_per_key = beta[FAMILY_IDX_FOR_KEY]
    u_norm = utilities * alpha_per_key[None, :] + beta_per_key[None, :]
    norm_eligible = u_norm > 0
    norm_scores = np.where(norm_eligible, u_norm, -np.inf)
    norm_idx = np.argmax(norm_scores, axis=1)
    norm_idx = np.where(norm_eligible.any(axis=1), norm_idx, -1)
    train_accuracy_normalized = float(np.mean(norm_idx == oracle_indices))

    return {
        "optimizer_status": "converged",
        "params": params,
        "train_accuracy_baseline": round(train_accuracy_baseline, 6),
        "train_accuracy_normalized": round(train_accuracy_normalized, 6),
        "final_loss": round(float(result.fun), 6),
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _select_normalized_contract(
    utilities: np.ndarray,
    bid_ns: np.ndarray,
    params: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply normalizer and select contract.

    Returns ``(norm_idx, u_norm)`` where ``norm_idx[i] = -1`` means pass.
    """
    alpha = np.array([params["alpha"][name] for name in FAMILY_NAMES])
    beta = np.array([params["beta"][name] for name in FAMILY_NAMES])
    alpha_per_key = alpha[FAMILY_IDX_FOR_KEY]
    beta_per_key = beta[FAMILY_IDX_FOR_KEY]

    u_norm = utilities * alpha_per_key[None, :] + beta_per_key[None, :]

    norm_eligible = u_norm > 0
    ck_index = np.arange(N_CONTRACTS)[None, :]
    tiebreak = bid_ns * 1e-10 + ck_index * 1e-14
    norm_scores = np.where(norm_eligible, u_norm + tiebreak, -np.inf)
    norm_idx = np.argmax(norm_scores, axis=1)
    all_pass = ~norm_eligible.any(axis=1)
    norm_idx = np.where(all_pass, -1, norm_idx)

    return norm_idx, u_norm


def evaluate_validation(
    decisions: dict,
    val_mask: np.ndarray,
    params: dict,
    n_bootstrap: int,
    seed: int,
) -> dict:
    """Compute all validation metrics on the held-out split."""
    mask = val_mask
    n_val = int(mask.sum())

    utilities = decisions["utilities"][mask]
    oracle_idx = decisions["oracle_idx"][mask]
    model_idx = decisions["model_idx"][mask]
    model_net = decisions["model_net"][mask]
    actual_nets = decisions["actual_nets"][mask]
    bid_ns = decisions["bid_ns"][mask]
    tricks_won = decisions["tricks_won"][mask]
    deal_ids = decisions["deal_ids"][mask]

    # Apply normalizer
    norm_idx, _ = _select_normalized_contract(utilities, bid_ns, params)

    norm_bids = norm_idx >= 0
    norm_net = np.where(
        norm_bids,
        actual_nets[np.arange(n_val), np.clip(norm_idx, 0, N_CONTRACTS - 1)],
        0.0,
    )

    # --- Accuracy metrics ---
    accuracy_baseline = float(np.mean(model_idx == oracle_idx))
    accuracy_normalized = float(np.mean(norm_idx == oracle_idx))
    accuracy_lift = accuracy_normalized - accuracy_baseline

    # --- Net-eppd metrics ---
    net_eppd_baseline = float(np.mean(model_net))
    net_eppd_normalized = float(np.mean(norm_net))
    delta_net_eppd = net_eppd_normalized - net_eppd_baseline

    # Deal-grouped bootstrap for CI
    deal_baseline: dict[int, list[float]] = {}
    deal_candidate: dict[int, list[float]] = {}
    for i in range(n_val):
        d = int(deal_ids[i])
        deal_baseline.setdefault(d, []).append(float(model_net[i]))
        deal_candidate.setdefault(d, []).append(float(norm_net[i]))
    deal_baseline_mean = {d: float(np.mean(vs)) for d, vs in deal_baseline.items()}
    deal_candidate_mean = {d: float(np.mean(vs)) for d, vs in deal_candidate.items()}

    _, ci_low, ci_high = bootstrap_paired_delta(
        deal_baseline_mean,
        deal_candidate_mean,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )

    # --- Pass-decision shift ---
    model_bids = model_idx >= 0
    bid_rate_baseline = float(np.mean(model_bids))
    bid_rate_normalized = float(np.mean(norm_bids))
    bid_rate_delta = bid_rate_normalized - bid_rate_baseline
    new_bidders = int(np.sum(~model_bids & norm_bids))
    lost_bidders = int(np.sum(model_bids & ~norm_bids))

    # --- Make rate for normalized model ---
    if norm_bids.sum() > 0:
        bids_idx = norm_idx[norm_bids]
        chosen_bid_n = bid_ns[norm_bids][np.arange(int(norm_bids.sum())), bids_idx]
        chosen_tricks = tricks_won[norm_bids][np.arange(int(norm_bids.sum())), bids_idx]
        make_rate_normalized = float(np.mean(chosen_tricks >= chosen_bid_n))
    else:
        make_rate_normalized = 1.0

    # --- Guardrails ---
    guardrails_pass, guardrail_violations = check_guardrails(
        {"bid_rate": bid_rate_normalized, "make_rate": make_rate_normalized}
    )

    return {
        "n_val_hands": n_val,
        "accuracy_baseline": round(accuracy_baseline, 6),
        "accuracy_normalized": round(accuracy_normalized, 6),
        "accuracy_lift": round(accuracy_lift, 6),
        "net_eppd_baseline": round(net_eppd_baseline, 4),
        "net_eppd_normalized": round(net_eppd_normalized, 4),
        "delta_net_eppd": round(delta_net_eppd, 4),
        "delta_ci_low": round(ci_low, 4),
        "delta_ci_high": round(ci_high, 4),
        "bid_rate_baseline": round(bid_rate_baseline, 4),
        "bid_rate_normalized": round(bid_rate_normalized, 4),
        "bid_rate_delta": round(bid_rate_delta, 4),
        "new_bidders_count": new_bidders,
        "lost_bidders_count": lost_bidders,
        "make_rate_normalized": round(make_rate_normalized, 4),
        "guardrails_pass": guardrails_pass,
        "guardrail_violations": guardrail_violations,
    }


# ---------------------------------------------------------------------------
# Decision rubric
# ---------------------------------------------------------------------------


def apply_rubric(diag_zero: dict, val_metrics: dict | None) -> tuple[str, list[str]]:
    """Apply go/no-go rubric. Returns (decision, rationale_list)."""
    rationale: list[str] = []

    # Early exit from Diagnostic Zero
    if diag_zero["early_exit"]:
        rationale.append(
            f"Diagnostic Zero early exit: median_gap={diag_zero['utility_gap_quantiles']['p50']:.2f}, "
            f"p75_gap={diag_zero['utility_gap_quantiles']['p75']:.2f} "
            "(model poverty, not miscalibration)"
        )
        return "NO_GO_DEFER_R1", rationale

    if val_metrics is None:
        return "NO_GO_DEFER_R1", ["Optimizer failed, no validation metrics"]

    delta = val_metrics["delta_net_eppd"]
    ci_low = val_metrics["delta_ci_low"]
    ci_high = val_metrics["delta_ci_high"]
    acc_lift = val_metrics["accuracy_lift"]
    guardrails = val_metrics["guardrails_pass"]

    # NO_GO checks (any true → NO_GO)
    no_go_reasons = []
    if delta <= 0:
        no_go_reasons.append(f"delta_net_eppd={delta:.4f} <= 0")
    if ci_high < 0.03:
        no_go_reasons.append(f"ci_high={ci_high:.4f} < +0.03")
    if acc_lift < 0.02:
        no_go_reasons.append(f"accuracy_lift={acc_lift:.4f} < 0.02")

    if no_go_reasons:
        return "NO_GO_DEFER_R1", no_go_reasons

    # GO checks (all must be true)
    go_checks = []
    go_pass = True
    if delta >= 0.08:
        go_checks.append(f"delta_net_eppd={delta:.4f} >= +0.08 ✓")
    else:
        go_checks.append(f"delta_net_eppd={delta:.4f} < +0.08 ✗")
        go_pass = False

    if ci_low > 0:
        go_checks.append(f"ci_low={ci_low:.4f} > 0 (CI excludes 0) ✓")
    else:
        go_checks.append(f"ci_low={ci_low:.4f} <= 0 (CI includes 0) ✗")
        go_pass = False

    if guardrails:
        go_checks.append("guardrails pass ✓")
    else:
        go_checks.append(f"guardrails fail: {val_metrics['guardrail_violations']} ✗")
        go_pass = False

    if acc_lift >= 0.03:
        go_checks.append(f"accuracy_lift={acc_lift:.4f} >= 0.03 ✓")
    else:
        go_checks.append(f"accuracy_lift={acc_lift:.4f} < 0.03 ✗")
        go_pass = False

    if go_pass:
        return "GO_TO_FULL_TRACK_E", go_checks

    return "NEEDS_REVIEW", go_checks


# ---------------------------------------------------------------------------
# Artifact output
# ---------------------------------------------------------------------------


def build_artifact(
    args: argparse.Namespace,
    diag_zero: dict,
    fit_result: dict | None,
    val_metrics: dict | None,
    decision: str,
    rationale: list[str],
) -> dict:
    """Build output JSON artifact."""
    artifact: dict = {
        "schema": "normalizer_offline_screen_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "pass_threshold": args.pass_threshold,
        "risk_lambda": args.risk_lambda,
        "n_bootstrap": args.n_bootstrap,
        "diagnostic_zero": diag_zero,
    }

    if fit_result is not None:
        artifact["fit"] = {
            "optimizer_status": fit_result["optimizer_status"],
            "params": fit_result["params"],
            "train_accuracy_baseline": fit_result["train_accuracy_baseline"],
            "train_accuracy_normalized": fit_result["train_accuracy_normalized"],
            "final_loss": fit_result["final_loss"],
        }

    if val_metrics is not None:
        # Remove internal fields from output
        vm = {k: v for k, v in val_metrics.items() if k != "guardrail_violations"}
        artifact["val_metrics"] = vm

    artifact["decision"] = decision
    artifact["rationale"] = rationale

    return artifact


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> dict:
    """Run the normalizer offline screen pipeline. Returns the artifact dict."""
    args = parse_args(argv)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading artifact from {args.artifact_path}")
    artifact = load_artifact(args.artifact_path)

    print("Joining features and outcomes...")
    df = join_features_outcomes(args.bidless_path, args.outcomes_path)
    print(f"  Joined: {len(df):,} rows")

    print("Building hand table (predictions + actual_net)...")
    hand_table = build_hand_table(
        df, artifact, args.pass_threshold, args.risk_lambda, args.seed
    )
    n_hands = len(hand_table) // N_CONTRACTS
    print(f"  Complete hands: {n_hands:,}")

    print("Computing oracle and model decisions...")
    decisions = make_hand_decisions(hand_table)

    # --- Step 0: Diagnostic Zero ---
    print("\n=== Step 0: Diagnostic Zero ===")
    diag = diagnostic_zero(decisions)
    print(f"  Total hands (model bids): {diag['n_total_hands']:,}")
    print(f"  Disagreement hands: {diag['n_disagreement_hands']:,}")
    print(f"  Disagreement rate: {diag['disagreement_rate']:.1%}")
    print(f"  Utility gap quantiles: {diag['utility_gap_quantiles']}")

    if diag["early_exit"]:
        print("\n  ** EARLY EXIT: Model poverty detected (not miscalibration) **")
        decision, rationale = apply_rubric(diag, None)
        result = build_artifact(args, diag, None, None, decision, rationale)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nDecision: {decision}")
        print(f"Artifact written to {output_path}")
        return result

    # --- Partition ---
    print("\nPartitioning by deal_id...")
    deal_ids = decisions["deal_ids"]
    partition = np.array([deal_partition(str(d), args.seed) for d in deal_ids])
    train_mask = partition == "train"
    val_mask = partition == "val"
    print(f"  Train: {train_mask.sum():,} hands, Val: {val_mask.sum():,} hands")

    # --- Step 1: Fit ---
    print("\n=== Step 1: Normalizer Fit ===")
    fit_result = fit_normalizer(decisions, train_mask)
    print(f"  Optimizer: {fit_result['optimizer_status']}")
    if fit_result["params"]:
        print(f"  Alpha: {fit_result['params']['alpha']}")
        print(f"  Beta:  {fit_result['params']['beta']}")
        print(
            f"  Train accuracy: {fit_result['train_accuracy_baseline']:.4f} → "
            f"{fit_result['train_accuracy_normalized']:.4f}"
        )
        print(f"  Final loss: {fit_result['final_loss']:.6f}")

    if fit_result["params"] is None:
        decision, rationale = apply_rubric(diag, None)
        result = build_artifact(args, diag, fit_result, None, decision, rationale)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nDecision: {decision}")
        print(f"Artifact written to {output_path}")
        return result

    # --- Step 2: Validation ---
    print(f"\n=== Step 2: Validation ({val_mask.sum():,} hands) ===")
    val_metrics = evaluate_validation(
        decisions, val_mask, fit_result["params"], args.n_bootstrap, args.seed
    )
    print(
        f"  Accuracy: {val_metrics['accuracy_baseline']:.4f} → "
        f"{val_metrics['accuracy_normalized']:.4f} "
        f"(lift={val_metrics['accuracy_lift']:+.4f})"
    )
    print(
        f"  Net EPPD: {val_metrics['net_eppd_baseline']:.4f} → "
        f"{val_metrics['net_eppd_normalized']:.4f} "
        f"(Δ={val_metrics['delta_net_eppd']:+.4f})"
    )
    print(
        f"  95% CI: [{val_metrics['delta_ci_low']:+.4f}, "
        f"{val_metrics['delta_ci_high']:+.4f}]"
    )
    print(
        f"  Bid rate: {val_metrics['bid_rate_baseline']:.4f} → "
        f"{val_metrics['bid_rate_normalized']:.4f} "
        f"(Δ={val_metrics['bid_rate_delta']:+.4f})"
    )
    print(
        f"  Pass→Bid: {val_metrics['new_bidders_count']}, "
        f"Bid→Pass: {val_metrics['lost_bidders_count']}"
    )
    print(f"  Make rate (normalized): {val_metrics['make_rate_normalized']:.4f}")
    print(f"  Guardrails: {'PASS' if val_metrics['guardrails_pass'] else 'FAIL'}")

    # --- Decision ---
    decision, rationale = apply_rubric(diag, val_metrics)
    print(f"\n=== Decision: {decision} ===")
    for r in rationale:
        print(f"  • {r}")

    # --- Write artifact ---
    result = build_artifact(args, diag, fit_result, val_metrics, decision, rationale)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nArtifact written to {output_path}")

    return result


if __name__ == "__main__":
    main()

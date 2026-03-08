"""
R1.5 Gate X3 offline evaluation script.

Evaluates action-value model ranking quality against single-rollout
empirical oracle. Computes formal gate metrics (X3-rank, X3-regret,
X3-cal) plus robust alternative metrics (pairwise accuracy, top-k,
regret vs baselines).

CLI usage:
    uv run python scripts/internal/evaluate_gate_x3.py \
        --seed 42 \
        --dataset data/runs/action_value_quick_42/datasets/action_value.parquet \
        --artifact data/runs/action_value_quick_42/action_value_full.json
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations

import numpy as np
import pandas as pd

from bid_euchre.strategy.bidding import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES

# ── Gate X3 Thresholds ──────────────────────────────────────

GATE_X3_RANK_OVERALL = 0.40
GATE_X3_RANK_PER_FAMILY = 0.30
GATE_X3_REGRET = 1.5
GATE_X3_CAL_GAP = 2.0
GATE_X3_CAL_AGREEMENT = 0.60


# ── Prediction Helpers ──────────────────────────────────────


def predict_family(
    sub_df: pd.DataFrame, model: dict, feature_names: list[str]
) -> np.ndarray:
    """Vectorized OLS prediction for a subset of rows."""
    cols = []
    for name in feature_names:
        if name == "bid_n_sq":
            cols.append(sub_df["bid_n"].values.astype(np.float64) ** 2)
        else:
            cols.append(sub_df[name].values.astype(np.float64))
    X = np.column_stack(cols)
    coefs = np.array(model["coefficients"], dtype=np.float64)
    intercept = float(model.get("intercept", 0.0))
    return X @ coefs + intercept


def add_predictions(test_df: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Add model_pred column to test dataframe."""
    bid_features = list(STATE_FEATURE_NAMES) + list(ACTION_FEATURE_NAMES)
    pass_features = list(STATE_FEATURE_NAMES)

    preds = np.zeros(len(test_df))
    mask_pass = test_df["action_type"].values == "pass"
    mask_suit = test_df["contract_family"].values == "suit"
    mask_high = test_df["contract_family"].values == "high"
    mask_low = test_df["contract_family"].values == "low"

    preds[mask_pass] = predict_family(test_df[mask_pass], models["pass"], pass_features)
    preds[mask_suit & ~mask_pass] = predict_family(
        test_df[mask_suit & ~mask_pass], models["suit"], bid_features
    )
    preds[mask_high & ~mask_pass] = predict_family(
        test_df[mask_high & ~mask_pass], models["high"], bid_features
    )
    preds[mask_low & ~mask_pass] = predict_family(
        test_df[mask_low & ~mask_pass], models["low"], bid_features
    )

    test_df = test_df.copy()
    test_df["model_pred"] = preds
    return test_df


# ── Gate X3 Formal Evaluation ──────────────────────────────


def evaluate_x3_rank(test_df: pd.DataFrame) -> dict:
    """Gate X3-rank: top-1 accuracy (exact action match)."""
    states = test_df.groupby(["deal_id", "focal_seat"])

    oracle_actions = []
    model_actions = []
    oracle_families = []

    for (_deal_id, _seat), group in states:
        oracle_idx = group["net_points"].idxmax()
        model_idx = group["model_pred"].idxmax()

        oracle_row = group.loc[oracle_idx]
        model_row = group.loc[model_idx]

        oracle_action = (
            oracle_row["action_type"],
            oracle_row["contract_family"],
            oracle_row["bid_n"],
            oracle_row.get("trump_suit", ""),
        )
        model_action = (
            model_row["action_type"],
            model_row["contract_family"],
            model_row["bid_n"],
            model_row.get("trump_suit", ""),
        )

        oracle_actions.append(str(oracle_action))
        model_actions.append(str(model_action))
        oracle_families.append(
            oracle_row["contract_family"]
            if oracle_row["action_type"] != "pass"
            else "pass"
        )

    oracle_actions_arr = np.array(oracle_actions)
    model_actions_arr = np.array(model_actions)
    oracle_families_arr = np.array(oracle_families)
    top1_match = oracle_actions_arr == model_actions_arr

    results = {
        "overall": float(top1_match.mean()),
        "per_family": {},
    }

    for fam in ["suit", "high", "low", "pass"]:
        mask = oracle_families_arr == fam
        if mask.sum() > 0:
            results["per_family"][fam] = {
                "accuracy": float(top1_match[mask].mean()),
                "n_states": int(mask.sum()),
            }

    return results


def evaluate_x3_regret(test_df: pd.DataFrame, seed: int) -> dict:
    """Gate X3-regret: mean regret of model vs oracle, random, always-pass."""
    states = test_df.groupby(["deal_id", "focal_seat"])
    rng = np.random.RandomState(seed)

    model_regrets = []
    random_regrets = []
    pass_regrets = []
    model_outcomes = []
    random_outcomes = []
    pass_outcomes = []

    for (_deal_id, _seat), group in states:
        oracle_val = group["net_points"].max()

        # Model choice
        model_idx = group["model_pred"].idxmax()
        model_val = group.loc[model_idx, "net_points"]
        model_regrets.append(oracle_val - model_val)
        model_outcomes.append(model_val)

        # Random choice
        rand_idx = group.index[rng.randint(len(group))]
        rand_val = group.loc[rand_idx, "net_points"]
        random_regrets.append(oracle_val - rand_val)
        random_outcomes.append(rand_val)

        # Always-pass
        pass_rows = group[group["action_type"] == "pass"]
        if len(pass_rows) > 0:
            pass_val = pass_rows["net_points"].iloc[0]
            pass_regrets.append(oracle_val - pass_val)
            pass_outcomes.append(pass_val)

    model_r = np.array(model_regrets)
    random_r = np.array(random_regrets)
    pass_r = np.array(pass_regrets)

    return {
        "model": {
            "mean_regret": float(model_r.mean()),
            "median_regret": float(np.median(model_r)),
            "std_regret": float(model_r.std()),
            "mean_outcome": float(np.mean(model_outcomes)),
        },
        "random": {
            "mean_regret": float(random_r.mean()),
            "median_regret": float(np.median(random_r)),
            "std_regret": float(random_r.std()),
            "mean_outcome": float(np.mean(random_outcomes)),
        },
        "always_pass": {
            "mean_regret": float(pass_r.mean()),
            "median_regret": float(np.median(pass_r)),
            "std_regret": float(pass_r.std()),
            "mean_outcome": float(np.mean(pass_outcomes)),
        },
        "improvement_vs_random": float(1 - model_r.mean() / random_r.mean()),
        "improvement_vs_pass": float(1 - model_r.mean() / pass_r.mean()),
    }


def evaluate_x3_cal(test_df: pd.DataFrame) -> dict:
    """Gate X3-cal: cross-contract calibration."""
    states = test_df.groupby(["deal_id", "focal_seat"])

    family_gaps = []
    family_agreements = []

    for (_deal_id, _seat), group in states:
        fam_model_best: dict[str, float] = {}
        fam_oracle_best: dict[str, float] = {}

        pass_rows = group[group["action_type"] == "pass"]
        if len(pass_rows) > 0:
            fam_model_best["pass"] = float(pass_rows["model_pred"].max())
            fam_oracle_best["pass"] = float(pass_rows["net_points"].max())

        for fam in ["suit", "high", "low"]:
            fam_rows = group[
                (group["contract_family"] == fam) & (group["action_type"] == "bid")
            ]
            if len(fam_rows) > 0:
                fam_model_best[fam] = float(fam_rows["model_pred"].max())
                fam_oracle_best[fam] = float(fam_rows["net_points"].max())

        if len(fam_model_best) < 2:
            continue

        # Family-level agreement
        model_best_fam = max(fam_model_best, key=fam_model_best.get)  # type: ignore[arg-type]
        oracle_best_fam = max(fam_oracle_best, key=fam_oracle_best.get)  # type: ignore[arg-type]
        family_agreements.append(model_best_fam == oracle_best_fam)

        # Pairwise gaps
        fam_list = sorted(fam_model_best.keys())
        for i, j in combinations(range(len(fam_list)), 2):
            f1, f2 = fam_list[i], fam_list[j]
            model_gap = fam_model_best[f1] - fam_model_best[f2]
            oracle_gap = fam_oracle_best[f1] - fam_oracle_best[f2]
            family_gaps.append(abs(model_gap - oracle_gap))

    return {
        "mean_prediction_gap": float(np.mean(family_gaps)),
        "family_agreement": float(np.mean(family_agreements)),
    }


# ── Robust Alternative Metrics ─────────────────────────────


def evaluate_pairwise(test_df: pd.DataFrame) -> dict:
    """Pairwise accuracy: for action pairs, does model order correctly?"""
    states = test_df.groupby(["deal_id", "focal_seat"])

    concordant = 0
    discordant = 0
    tied = 0

    for (_deal_id, _seat), group in states:
        idx = group.index.tolist()
        for i, j in combinations(range(len(idx)), 2):
            a, b = idx[i], idx[j]
            emp_diff = group.loc[a, "net_points"] - group.loc[b, "net_points"]
            mod_diff = group.loc[a, "model_pred"] - group.loc[b, "model_pred"]
            if emp_diff == 0:
                tied += 1
            elif (emp_diff > 0 and mod_diff > 0) or (emp_diff < 0 and mod_diff < 0):
                concordant += 1
            else:
                discordant += 1

    non_tied = concordant + discordant
    return {
        "concordant": concordant,
        "discordant": discordant,
        "tied": tied,
        "accuracy": float(concordant / non_tied) if non_tied > 0 else 0.0,
    }


def evaluate_pairwise_slices(test_df: pd.DataFrame) -> dict:
    """Pairwise accuracy on harder slices: close pairs and within-top-k."""
    states = test_df.groupby(["deal_id", "focal_seat"])

    # Close-pair slices
    close_1_conc, close_1_disc = 0, 0
    close_2_conc, close_2_disc = 0, 0

    # Within-top-k slices
    top3_conc, top3_disc = 0, 0
    top5_conc, top5_disc = 0, 0

    for (_deal_id, _seat), group in states:
        idx = group.index.tolist()
        net_pts = group["net_points"]
        mod_pred = group["model_pred"]

        # Close-pair pairwise
        for i, j in combinations(range(len(idx)), 2):
            a, b = idx[i], idx[j]
            emp_diff = net_pts.loc[a] - net_pts.loc[b]
            mod_diff = mod_pred.loc[a] - mod_pred.loc[b]
            abs_emp = abs(emp_diff)

            if emp_diff != 0:
                concordant = (emp_diff > 0 and mod_diff > 0) or (
                    emp_diff < 0 and mod_diff < 0
                )
                if abs_emp <= 1:
                    if concordant:
                        close_1_conc += 1
                    else:
                        close_1_disc += 1
                if abs_emp <= 2:
                    if concordant:
                        close_2_conc += 1
                    else:
                        close_2_disc += 1

        # Within-top-k pairwise (by empirical ranking)
        top_indices = group.nlargest(5, "net_points").index.tolist()
        for k_limit, (conc_ref, disc_ref) in [
            (3, ("top3", None)),
            (5, ("top5", None)),
        ]:
            subset = top_indices[:k_limit]
            for i, j in combinations(range(len(subset)), 2):
                a, b = subset[i], subset[j]
                emp_diff = net_pts.loc[a] - net_pts.loc[b]
                mod_diff = mod_pred.loc[a] - mod_pred.loc[b]
                if emp_diff != 0:
                    concordant = (emp_diff > 0 and mod_diff > 0) or (
                        emp_diff < 0 and mod_diff < 0
                    )
                    if k_limit == 3:
                        if concordant:
                            top3_conc += 1
                        else:
                            top3_disc += 1
                    else:
                        if concordant:
                            top5_conc += 1
                        else:
                            top5_disc += 1

    def _acc(c: int, d: int) -> float:
        return float(c / (c + d)) if (c + d) > 0 else 0.0

    return {
        "close_1": {
            "accuracy": _acc(close_1_conc, close_1_disc),
            "n": close_1_conc + close_1_disc,
        },
        "close_2": {
            "accuracy": _acc(close_2_conc, close_2_disc),
            "n": close_2_conc + close_2_disc,
        },
        "within_top3": {
            "accuracy": _acc(top3_conc, top3_disc),
            "n": top3_conc + top3_disc,
        },
        "within_top5": {
            "accuracy": _acc(top5_conc, top5_disc),
            "n": top5_conc + top5_disc,
        },
    }


def evaluate_within_family_correlation(test_df: pd.DataFrame) -> dict:
    """Per-family correlation and R² between predictions and outcomes."""
    results = {}
    for fam in ["suit", "high", "low"]:
        fam_df = test_df[
            (test_df["contract_family"] == fam) & (test_df["action_type"] == "bid")
        ]
        if len(fam_df) < 2:
            continue
        corr = float(np.corrcoef(fam_df["net_points"], fam_df["model_pred"])[0, 1])
        results[fam] = {"correlation": corr, "r_squared": corr**2}

    pass_df = test_df[test_df["action_type"] == "pass"]
    if len(pass_df) >= 2:
        corr = float(np.corrcoef(pass_df["net_points"], pass_df["model_pred"])[0, 1])
        results["pass"] = {"correlation": corr, "r_squared": corr**2}

    return results


def evaluate_population_oracle(
    full_df: pd.DataFrame, test_df: pd.DataFrame, seed: int
) -> dict:
    """Compare single-rollout oracle against population-mean oracle.

    Uses training split population means per (contract_family, bid_n) to check
    how often the single-rollout oracle agrees with a smoothed baseline.
    This is a diagnostic of oracle unreliability, NOT a ceiling on model accuracy.
    """
    # Reproduce train split
    unique_deals = full_df["deal_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_deals)
    n = len(unique_deals)
    train_ids = set(unique_deals[: int(n * 0.8)])
    train_df = full_df[full_df["deal_id"].isin(train_ids)]

    # Population means by coarse action key
    pop_means = (
        train_df.groupby(["contract_family", "bid_n"])["net_points"].mean().to_dict()
    )

    states = test_df.groupby(["deal_id", "focal_seat"])
    agreements = []

    for (_deal_id, _seat), group in states:
        # Single-rollout oracle
        oracle_idx = group["net_points"].idxmax()
        oracle_key = (
            group.loc[oracle_idx, "contract_family"],
            group.loc[oracle_idx, "bid_n"],
        )

        # Population oracle (best action by training set average)
        best_pop_val = -999.0
        best_pop_key = None
        for _, row in group.iterrows():
            key = (row["contract_family"], row["bid_n"])
            pop_val = pop_means.get(key, -999.0)
            if pop_val > best_pop_val:
                best_pop_val = pop_val
                best_pop_key = key

        agreements.append(oracle_key == best_pop_key)

    return {
        "agreement": float(np.mean(agreements)),
        "note": "Diagnostic of oracle unreliability, NOT a ceiling on model accuracy",
    }


def evaluate_topk(test_df: pd.DataFrame) -> dict:
    """Top-K accuracy for K=1,3,5,10."""
    states = test_df.groupby(["deal_id", "focal_seat"])

    results = {}
    for k in [1, 3, 5, 10]:
        hits = 0
        n_states = 0
        for (_deal_id, _seat), group in states:
            n_states += 1
            model_topk = set(group.nlargest(k, "model_pred").index)
            oracle_best = group["net_points"].idxmax()
            if oracle_best in model_topk:
                hits += 1
        n_actions = test_df.groupby(["deal_id", "focal_seat"]).size().mean()
        results[f"top_{k}"] = {
            "accuracy": float(hits / n_states),
            "random_baseline": float(min(k, n_actions) / n_actions),
        }

    return results


def evaluate_family_distribution(test_df: pd.DataFrame) -> dict:
    """Family-level choice distribution and agreement."""
    states = test_df.groupby(["deal_id", "focal_seat"])

    model_fams: dict[str, int] = {}
    oracle_fams: dict[str, int] = {}
    family_matches = 0
    n_states = 0

    for (_deal_id, _seat), group in states:
        n_states += 1
        fam_model: dict[str, float] = {}
        fam_oracle: dict[str, float] = {}

        pass_rows = group[group["action_type"] == "pass"]
        if len(pass_rows) > 0:
            fam_model["pass"] = float(pass_rows["model_pred"].max())
            fam_oracle["pass"] = float(pass_rows["net_points"].max())

        for fam in ["suit", "high", "low"]:
            fam_rows = group[
                (group["contract_family"] == fam) & (group["action_type"] == "bid")
            ]
            if len(fam_rows) > 0:
                fam_model[fam] = float(fam_rows["model_pred"].max())
                fam_oracle[fam] = float(fam_rows["net_points"].max())

        m_best = max(fam_model, key=fam_model.get)  # type: ignore[arg-type]
        o_best = max(fam_oracle, key=fam_oracle.get)  # type: ignore[arg-type]

        model_fams[m_best] = model_fams.get(m_best, 0) + 1
        oracle_fams[o_best] = oracle_fams.get(o_best, 0) + 1

        if m_best == o_best:
            family_matches += 1

    return {
        "family_top1": float(family_matches / n_states),
        "model_distribution": {k: v / n_states for k, v in sorted(model_fams.items())},
        "oracle_distribution": {
            k: v / n_states for k, v in sorted(oracle_fams.items())
        },
    }


# ── Main ────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="R1.5 Gate X3 offline evaluation")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--dataset", required=True, help="Path to parquet")
    parser.add_argument("--artifact", required=True, help="Path to artifact JSON")
    args = parser.parse_args()

    # Load data and artifact
    print("=== R1.5 Gate X3 Offline Evaluation ===")
    df = pd.read_parquet(args.dataset)
    with open(args.artifact) as f:
        artifact = json.load(f)
    models = artifact["models"]

    # Reproduce test split
    unique_deals = df["deal_id"].unique()
    rng = np.random.RandomState(args.seed)
    rng.shuffle(unique_deals)
    n = len(unique_deals)
    test_ids = set(unique_deals[int(n * 0.9) :])
    test_df = df[df["deal_id"].isin(test_ids)].copy()
    print(
        f"  Test split: {len(test_df)} rows, {len(test_ids)} deals, "
        f"{test_df.groupby(['deal_id', 'focal_seat']).ngroups} states"
    )

    # Add predictions
    test_df = add_predictions(test_df, models)

    # ── Formal Gate X3 ──────────────────────────────────
    print()
    print("=== Gate X3-rank: Top-1 Accuracy ===")
    rank_results = evaluate_x3_rank(test_df)
    overall = rank_results["overall"]
    print(f"  Overall: {overall:.4f} ({overall * 100:.1f}%)")
    print(
        f"  Threshold: >= {GATE_X3_RANK_OVERALL * 100:.0f}%  ->  "
        f"{'PASS' if overall >= GATE_X3_RANK_OVERALL else 'FAIL'}"
    )
    for fam, data in rank_results["per_family"].items():
        acc = data["accuracy"]
        ns = data["n_states"]
        verdict = "PASS" if acc >= GATE_X3_RANK_PER_FAMILY else "FAIL"
        print(f"  {fam}: {acc:.4f} ({acc * 100:.1f}%) [n={ns}]  ->  {verdict}")

    print()
    print("=== Gate X3-regret: Mean Regret ===")
    regret_results = evaluate_x3_regret(test_df, args.seed)
    mr = regret_results["model"]["mean_regret"]
    print(f"  Model mean regret: {mr:.4f}")
    print(
        f"  Threshold: <= {GATE_X3_REGRET}  ->  "
        f"{'PASS' if mr <= GATE_X3_REGRET else 'FAIL'}"
    )
    print(f"  Random mean regret: {regret_results['random']['mean_regret']:.4f}")
    print(
        f"  Always-pass mean regret: {regret_results['always_pass']['mean_regret']:.4f}"
    )
    print(
        f"  Improvement vs random: {regret_results['improvement_vs_random'] * 100:.1f}%"
    )
    print(f"  Improvement vs pass: {regret_results['improvement_vs_pass'] * 100:.1f}%")

    print()
    print("=== Gate X3-cal: Cross-Contract Calibration ===")
    cal_results = evaluate_x3_cal(test_df)
    gap = cal_results["mean_prediction_gap"]
    agree = cal_results["family_agreement"]
    print(f"  Mean prediction gap: {gap:.4f}")
    print(
        f"  Threshold: <= {GATE_X3_CAL_GAP}  ->  "
        f"{'PASS' if gap <= GATE_X3_CAL_GAP else 'FAIL'}"
    )
    print(f"  Family agreement: {agree:.4f} ({agree * 100:.1f}%)")
    print(
        f"  Threshold: >= {GATE_X3_CAL_AGREEMENT * 100:.0f}%  ->  "
        f"{'PASS' if agree >= GATE_X3_CAL_AGREEMENT else 'FAIL'}"
    )

    # ── Robust Metrics ──────────────────────────────────
    print()
    print("=== Pairwise Accuracy ===")
    pairwise = evaluate_pairwise(test_df)
    print(f"  Concordant: {pairwise['concordant']:,}")
    print(f"  Discordant: {pairwise['discordant']:,}")
    print(f"  Tied: {pairwise['tied']:,}")
    print(f"  Accuracy (excl ties): {pairwise['accuracy']:.4f}")

    print()
    print("=== Pairwise Accuracy — Hard Slices ===")
    slices = evaluate_pairwise_slices(test_df)
    for name, data in slices.items():
        print(
            f"  {name}: {data['accuracy']:.4f} ({data['accuracy'] * 100:.1f}%) [n={data['n']:,}]"
        )

    print()
    print("=== Within-Family Correlation (test set) ===")
    corr_results = evaluate_within_family_correlation(test_df)
    for fam, data in corr_results.items():
        print(f"  {fam}: corr={data['correlation']:.4f}, R²={data['r_squared']:.4f}")

    print()
    print("=== Population-Oracle Consistency ===")
    pop_oracle = evaluate_population_oracle(df, test_df, args.seed)
    print(
        f"  Single-rollout vs population-mean agreement: {pop_oracle['agreement']:.4f}"
    )
    print(f"  Note: {pop_oracle['note']}")

    print()
    print("=== Top-K Accuracy ===")
    topk = evaluate_topk(test_df)
    for k_name, data in topk.items():
        acc = data["accuracy"]
        baseline = data["random_baseline"]
        print(
            f"  {k_name}: {acc:.4f} ({acc * 100:.1f}%)  [random: {baseline * 100:.1f}%]"
        )

    print()
    print("=== Family Distribution ===")
    fam_dist = evaluate_family_distribution(test_df)
    print(f"  Family-level top-1: {fam_dist['family_top1']:.4f}")
    print(f"  Model: {fam_dist['model_distribution']}")
    print(f"  Oracle: {fam_dist['oracle_distribution']}")

    print()
    print("=== Mean Outcome of Chosen Action ===")
    print(f"  Model:  {regret_results['model']['mean_outcome']:+.3f}")
    print(f"  Random: {regret_results['random']['mean_outcome']:+.3f}")
    print(f"  Pass:   {regret_results['always_pass']['mean_outcome']:+.3f}")

    # ── Summary ─────────────────────────────────────────
    x3_rank_pass = overall >= GATE_X3_RANK_OVERALL and all(
        d["accuracy"] >= GATE_X3_RANK_PER_FAMILY
        for d in rank_results["per_family"].values()
    )
    x3_regret_pass = mr <= GATE_X3_REGRET
    x3_cal_pass = gap <= GATE_X3_CAL_GAP and agree >= GATE_X3_CAL_AGREEMENT

    print()
    print("=== GATE X3 SUMMARY ===")
    print(f"  X3-rank:   {'PASS' if x3_rank_pass else 'FAIL'}")
    print(f"  X3-regret: {'PASS' if x3_regret_pass else 'FAIL'}")
    print(f"  X3-cal:    {'PASS' if x3_cal_pass else 'FAIL'}")
    overall_pass = x3_rank_pass and x3_regret_pass and x3_cal_pass
    print(f"  Overall:   {'PASS' if overall_pass else 'FAIL'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Generate interpretability artifacts for Arc D v2 rung analysis.

Produces SHAP feature analysis, selection path traces, and pairwise
decision comparison CSVs from trained action-value model artifacts.

CLI:
    uv run python scripts/internal/generate_interpretability.py \\
        --rung-dir data/runs/r0_smoke_42 \\
        --report-dir /tmp/interpretability_report \\
        --eval-sample 5000

Outputs (CSVs in <report-dir>/chart_data/):
  - shap_feature_ranking.csv
  - shap_dependence.csv
  - shap_interactions.csv
  - selection_paths.csv
  - decision_comparison.csv
  - disagreement_outcomes.csv
  - context_feature_usage.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Context feature classification ──────────────────────────

# Features that come from auction context (partner signals), not hand evaluation.
# This list is the canonical source for context vs hand feature tagging.
CONTEXT_FEATURE_NAMES = frozenset(
    [
        "partner_bid_level",
        "partner_passed",
        "partner_suit_match",
        "partner_bid_confidence",
        "auction_position",
        "is_dealer",
    ]
)

# Action features injected by the action-value pipeline
ACTION_FEATURE_NAMES = frozenset(["bid_n", "bid_n_sq"])

# Contract families
CONTRACT_FAMILIES = ("suit", "high", "low", "pass")


# ── Artifact loading ────────────────────────────────────────


def _discover_artifacts(rung_dir: Path) -> list[dict]:
    """Find all action-value JSON artifacts in a rung directory.

    Searches for files matching known schema patterns in artifacts/.
    Returns list of dicts with 'path', 'name', 'schema', 'artifact' keys.
    """
    artifacts_dir = rung_dir / "artifacts"
    if not artifacts_dir.exists():
        logger.warning("No artifacts/ directory in %s", rung_dir)
        return []

    results = []
    for json_path in sorted(artifacts_dir.glob("*.json")):
        try:
            with open(json_path) as f:
                artifact = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping %s: %s", json_path, e)
            continue

        schema = artifact.get("schema_version", "")
        if schema in ("action_value_gbt_v1", "action_value_olsa_v1"):
            results.append(
                {
                    "path": json_path,
                    "name": json_path.stem,
                    "schema": schema,
                    "artifact": artifact,
                }
            )
    return results


def _load_gbt_models(artifact: dict, artifact_dir: Path) -> dict[str, Any] | None:
    """Load GBT sklearn models from joblib files referenced in artifact.

    Returns dict mapping contract family -> sklearn model, or None on failure.
    """
    try:
        import joblib
    except ImportError:
        logger.warning("joblib not available; cannot load GBT models")
        return None

    models = {}
    models_meta = artifact["models"]
    for family in CONTRACT_FAMILIES:
        if family not in models_meta:
            continue
        meta = models_meta[family]
        if "model_file" not in meta:
            continue
        model_path = artifact_dir / meta["model_file"]
        if not model_path.exists():
            logger.warning("Model file not found: %s", model_path)
            return None
        models[family] = joblib.load(model_path)
    return models


def _get_feature_names(artifact: dict, family: str) -> list[str]:
    """Extract feature names for a model family from artifact metadata."""
    models = artifact.get("models", {})
    if family in models and "feature_names" in models[family]:
        return list(models[family]["feature_names"])
    return []


# ── SHAP analysis ───────────────────────────────────────────


def generate_shap_analysis(
    artifact_info: dict,
    eval_df: pd.DataFrame,
    eval_sample: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run SHAP TreeExplainer on GBT models and produce ranking/dependence/interaction CSVs.

    Args:
        artifact_info: Dict with 'name', 'artifact', 'path', 'schema' keys.
        eval_df: Evaluation dataset (parquet-loaded).
        eval_sample: Max rows to subsample for SHAP computation.

    Returns:
        (ranking_df, dependence_df, interactions_df)
    """
    try:
        import shap
    except ImportError:
        logger.warning("shap not installed; skipping SHAP analysis")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    artifact = artifact_info["artifact"]
    artifact_dir = artifact_info["path"].parent
    model_name = artifact_info["name"]

    gbt_models = _load_gbt_models(artifact, artifact_dir)
    if gbt_models is None:
        logger.warning("Could not load GBT models for %s; skipping SHAP", model_name)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    ranking_rows: list[dict] = []
    dependence_rows: list[dict] = []
    interaction_rows: list[dict] = []

    for family in CONTRACT_FAMILIES:
        if family not in gbt_models:
            continue

        model = gbt_models[family]
        feature_names = _get_feature_names(artifact, family)
        if not feature_names:
            logger.warning("No feature_names for %s/%s; skipping", model_name, family)
            continue

        # Filter eval data to this contract family
        if family == "pass":
            family_df = eval_df[eval_df["action_type"] == "pass"]
        else:
            family_df = eval_df[eval_df["contract_family"] == family]

        if len(family_df) == 0:
            logger.warning("No eval data for %s/%s", model_name, family)
            continue

        # Subsample
        if len(family_df) > eval_sample:
            family_df = family_df.sample(n=eval_sample, random_state=42)

        # Build feature matrix
        available_features = [f for f in feature_names if f in family_df.columns]
        if len(available_features) < len(feature_names):
            missing = set(feature_names) - set(available_features)
            logger.warning(
                "Missing features for %s/%s: %s", model_name, family, missing
            )
            continue

        X = family_df[available_features].values

        # TreeExplainer
        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
        except Exception as e:
            logger.warning("SHAP failed for %s/%s: %s", model_name, family, e)
            continue

        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        mean_shap = shap_values.mean(axis=0)

        # Ranking
        sorted_indices = np.argsort(-mean_abs_shap)
        for rank, idx in enumerate(sorted_indices, 1):
            direction = "positive" if mean_shap[idx] > 0 else "negative"
            ranking_rows.append(
                {
                    "model": model_name,
                    "contract": family,
                    "feature": available_features[idx],
                    "rank": rank,
                    "mean_abs_shap": round(float(mean_abs_shap[idx]), 6),
                    "direction": direction,
                }
            )

        # Dependence (top 5 features)
        top_5_indices = sorted_indices[:5]
        for idx in top_5_indices:
            feat_name = available_features[idx]
            for i in range(len(X)):
                dependence_rows.append(
                    {
                        "model": model_name,
                        "contract": family,
                        "feature": feat_name,
                        "feature_value": round(float(X[i, idx]), 6),
                        "shap_value": round(float(shap_values[i, idx]), 6),
                    }
                )

        # Interactions (top 3 pairs by absolute interaction strength)
        # Use SHAP interaction values if available, otherwise approximate
        try:
            interaction_values = explainer.shap_interaction_values(
                X[: min(500, len(X))]
            )
            n_features = interaction_values.shape[2]
            # Sum absolute interaction strengths across samples
            mean_interactions = np.abs(interaction_values).mean(axis=0)
            # Get off-diagonal elements
            pairs = []
            for i in range(n_features):
                for j in range(i + 1, n_features):
                    pairs.append((i, j, float(mean_interactions[i, j])))
            pairs.sort(key=lambda x: x[2], reverse=True)
            for i, j, strength in pairs[:3]:
                interaction_rows.append(
                    {
                        "model": model_name,
                        "contract": family,
                        "feature_1": available_features[i],
                        "feature_2": available_features[j],
                        "interaction_strength": round(strength, 6),
                    }
                )
        except Exception as e:
            logger.info(
                "Interaction values not available for %s/%s: %s", model_name, family, e
            )

    ranking_df = pd.DataFrame(ranking_rows)
    dependence_df = pd.DataFrame(dependence_rows)
    interactions_df = pd.DataFrame(interaction_rows)

    return ranking_df, dependence_df, interactions_df


# ── Selection paths ─────────────────────────────────────────


def extract_selection_paths(artifact_info: dict) -> pd.DataFrame:
    """Extract forward selection path from artifact metadata.

    The selection log is stored in artifact['metadata']['selection_logs']
    when the model was trained with --selection forward.

    Returns DataFrame with columns: model, contract, step, feature_added, oof_r2, delta_r2
    """
    artifact = artifact_info["artifact"]
    model_name = artifact_info["name"]
    metadata = artifact.get("metadata", {})
    selection_logs = metadata.get("selection_logs")

    if selection_logs is None:
        logger.info(
            "No selection_logs in %s metadata; skipping selection paths", model_name
        )
        return pd.DataFrame()

    rows: list[dict] = []
    for contract, log in selection_logs.items():
        steps = log.get("steps", [])
        for step_info in steps:
            step_num = step_info["step"]
            feature = step_info["feature"]
            r2 = step_info["r2"]
            delta = step_info["improvement"]

            rows.append(
                {
                    "model": model_name,
                    "contract": contract,
                    "step": step_num,
                    "feature_added": feature,
                    "oof_r2": round(r2, 6),
                    "delta_r2": round(delta, 6),
                }
            )

    return pd.DataFrame(rows)


# ── Decision comparison ─────────────────────────────────────


def _predict_best_action(
    model: Any,
    feature_names: list[str],
    X_base: np.ndarray,
    max_bid: int = 10,
) -> np.ndarray:
    """Predict the best bid level for each sample using a GBT model.

    For each hand, evaluate bid_n from 1..max_bid and pick the level
    with the highest predicted value. Returns array of best bid levels.

    Args:
        model: Trained sklearn GBT model.
        feature_names: Feature names the model expects.
        X_base: Base feature matrix (n_samples, n_state_features) without action features.
        max_bid: Maximum bid level to evaluate.

    Returns:
        Array of best bid levels (n_samples,).
    """
    # Determine which columns are action features
    bid_n_idx = None
    bid_n_sq_idx = None
    for i, name in enumerate(feature_names):
        if name == "bid_n":
            bid_n_idx = i
        elif name == "bid_n_sq":
            bid_n_sq_idx = i

    if bid_n_idx is None:
        # No action features — model predicts value directly
        preds = model.predict(X_base)
        # Return dummy bid levels
        return np.ones(len(X_base), dtype=int)

    n_samples = X_base.shape[0]
    best_bids = np.ones(n_samples, dtype=int)
    best_values = np.full(n_samples, -np.inf)

    for bid_n in range(1, max_bid + 1):
        X_trial = X_base.copy()
        X_trial[:, bid_n_idx] = bid_n
        if bid_n_sq_idx is not None:
            X_trial[:, bid_n_sq_idx] = bid_n * bid_n

        preds = model.predict(X_trial)
        better = preds > best_values
        best_values[better] = preds[better]
        best_bids[better] = bid_n

    return best_bids


def generate_decision_comparison(
    artifact_infos: list[dict],
    eval_df: pd.DataFrame,
    eval_sample: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare decisions between pairs of models.

    For each pair of GBT models, predicts best action for the same eval set
    and computes agreement rate and outcome differences.

    Returns:
        (comparison_df, disagreement_outcomes_df)
    """
    try:
        import joblib  # noqa: F401
    except ImportError:
        logger.warning("joblib not available; skipping decision comparison")
        return pd.DataFrame(), pd.DataFrame()

    # Load all GBT models and their predictions
    model_predictions: dict[str, dict[str, np.ndarray]] = {}
    model_features: dict[str, dict[str, list[str]]] = {}

    for info in artifact_infos:
        artifact = info["artifact"]
        if info["schema"] != "action_value_gbt_v1":
            continue

        gbt_models = _load_gbt_models(artifact, info["path"].parent)
        if gbt_models is None:
            continue

        model_name = info["name"]
        model_predictions[model_name] = {}
        model_features[model_name] = {}

        for family in ("suit", "high", "low"):
            if family not in gbt_models:
                continue

            feature_names = _get_feature_names(artifact, family)
            if not feature_names:
                continue

            # Filter to contract family
            family_df = eval_df[eval_df["contract_family"] == family]
            if len(family_df) == 0:
                continue

            if len(family_df) > eval_sample:
                family_df = family_df.sample(n=eval_sample, random_state=42)

            available = [f for f in feature_names if f in family_df.columns]
            if len(available) != len(feature_names):
                continue

            X = family_df[available].values.astype(float)

            best_bids = _predict_best_action(gbt_models[family], feature_names, X)
            model_predictions[model_name][family] = best_bids
            model_features[model_name][family] = available

    # Pairwise comparison
    comparison_rows: list[dict] = []
    disagreement_rows: list[dict] = []
    model_names = sorted(model_predictions.keys())

    for i, model_a in enumerate(model_names):
        for model_b in model_names[i + 1 :]:
            for family in ("suit", "high", "low"):
                if family not in model_predictions[model_a]:
                    continue
                if family not in model_predictions[model_b]:
                    continue

                preds_a = model_predictions[model_a][family]
                preds_b = model_predictions[model_b][family]

                # Align lengths (use min since sampling may differ)
                n = min(len(preds_a), len(preds_b))
                preds_a = preds_a[:n]
                preds_b = preds_b[:n]

                agree = (preds_a == preds_b).sum()
                n_disagree = n - agree
                agreement_rate = agree / n if n > 0 else 0.0

                comparison_rows.append(
                    {
                        "model_a": model_a,
                        "model_b": model_b,
                        "contract": family,
                        "agreement_rate": round(float(agreement_rate), 4),
                        "n_disagree": int(n_disagree),
                    }
                )

                # Disagreement outcomes: who bid higher? (proxy for "better")
                if n_disagree > 0:
                    disagree_mask = preds_a != preds_b
                    a_higher = (preds_a[disagree_mask] > preds_b[disagree_mask]).sum()
                    b_higher = (preds_b[disagree_mask] > preds_a[disagree_mask]).sum()
                    a_higher_pct = a_higher / n_disagree
                    b_higher_pct = b_higher / n_disagree
                    tie_pct = 1.0 - a_higher_pct - b_higher_pct
                else:
                    a_higher_pct = 0.0
                    b_higher_pct = 0.0
                    tie_pct = 1.0

                disagreement_rows.append(
                    {
                        "model_a": model_a,
                        "model_b": model_b,
                        "contract": family,
                        "a_better_pct": round(float(a_higher_pct), 4),
                        "b_better_pct": round(float(b_higher_pct), 4),
                        "tie_pct": round(float(tie_pct), 4),
                    }
                )

    return pd.DataFrame(comparison_rows), pd.DataFrame(disagreement_rows)


# ── Context feature usage ───────────────────────────────────


def generate_context_feature_usage(
    shap_ranking_df: pd.DataFrame,
) -> pd.DataFrame:
    """Tag features as hand vs context and check top-10 entry.

    Uses the SHAP ranking to determine whether context features
    (partner signals, auction position) entered the top 10.

    Returns DataFrame with columns:
        model, contract, feature, rank, mean_abs_shap, is_context_feature, entered_top_10
    """
    if shap_ranking_df.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, row in shap_ranking_df.iterrows():
        is_context = row["feature"] in CONTEXT_FEATURE_NAMES
        entered_top_10 = row["rank"] <= 10
        rows.append(
            {
                "model": row["model"],
                "contract": row["contract"],
                "feature": row["feature"],
                "rank": int(row["rank"]),
                "mean_abs_shap": float(row["mean_abs_shap"]),
                "is_context_feature": is_context,
                "entered_top_10": entered_top_10,
            }
        )

    return pd.DataFrame(rows)


# ── Main orchestrator ───────────────────────────────────────


def _find_eval_dataset(rung_dir: Path) -> Path | None:
    """Find the eval dataset (parquet) in the rung directory."""
    # Check datasets/ subdirectory first
    datasets_dir = rung_dir / "datasets"
    if datasets_dir.exists():
        for p in sorted(datasets_dir.glob("*.parquet")):
            return p

    # Check for action_value dataset
    for p in sorted(rung_dir.glob("**/*.parquet")):
        if "action_value" in p.name:
            return p

    return None


def run(
    rung_dir: Path,
    report_dir: Path,
    eval_sample: int = 5000,
) -> dict[str, Path]:
    """Run the full interpretability pipeline.

    Args:
        rung_dir: Path to rung directory containing artifacts/ and datasets/.
        report_dir: Output directory for CSVs.
        eval_sample: Max samples for SHAP computation.

    Returns:
        Dict mapping output name -> file path.
    """
    chart_data_dir = report_dir / "chart_data"
    chart_data_dir.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, Path] = {}

    # Discover artifacts
    artifact_infos = _discover_artifacts(rung_dir)
    if not artifact_infos:
        logger.warning("No action-value artifacts found in %s", rung_dir)
        return outputs

    logger.info(
        "Found %d artifacts: %s",
        len(artifact_infos),
        [a["name"] for a in artifact_infos],
    )

    # Load eval dataset
    eval_path = _find_eval_dataset(rung_dir)
    eval_df = pd.DataFrame()
    if eval_path is not None:
        logger.info("Loading eval dataset: %s", eval_path)
        eval_df = pd.read_parquet(eval_path)
        logger.info(
            "Eval dataset: %d rows, %d columns", len(eval_df), len(eval_df.columns)
        )
    else:
        logger.warning("No eval dataset found in %s", rung_dir)

    # ── SHAP analysis ──
    all_ranking = []
    all_dependence = []
    all_interactions = []

    for info in artifact_infos:
        if info["schema"] != "action_value_gbt_v1":
            logger.info("Skipping SHAP for non-GBT artifact: %s", info["name"])
            continue

        if eval_df.empty:
            logger.warning("No eval data; skipping SHAP for %s", info["name"])
            continue

        ranking, dependence, interactions = generate_shap_analysis(
            info, eval_df, eval_sample
        )
        all_ranking.append(ranking)
        all_dependence.append(dependence)
        all_interactions.append(interactions)

    if all_ranking:
        ranking_df = pd.concat(all_ranking, ignore_index=True)
        if not ranking_df.empty:
            path = chart_data_dir / "shap_feature_ranking.csv"
            ranking_df.to_csv(path, index=False)
            outputs["shap_feature_ranking"] = path
            logger.info("Wrote %s (%d rows)", path, len(ranking_df))

            # Context feature usage
            context_df = generate_context_feature_usage(ranking_df)
            if not context_df.empty:
                path = chart_data_dir / "context_feature_usage.csv"
                context_df.to_csv(path, index=False)
                outputs["context_feature_usage"] = path
                logger.info("Wrote %s (%d rows)", path, len(context_df))

    if all_dependence:
        dep_df = pd.concat(all_dependence, ignore_index=True)
        if not dep_df.empty:
            path = chart_data_dir / "shap_dependence.csv"
            dep_df.to_csv(path, index=False)
            outputs["shap_dependence"] = path
            logger.info("Wrote %s (%d rows)", path, len(dep_df))

    if all_interactions:
        int_df = pd.concat(all_interactions, ignore_index=True)
        if not int_df.empty:
            path = chart_data_dir / "shap_interactions.csv"
            int_df.to_csv(path, index=False)
            outputs["shap_interactions"] = path
            logger.info("Wrote %s (%d rows)", path, len(int_df))

    # ── Selection paths ──
    all_selection = []
    for info in artifact_infos:
        sel_df = extract_selection_paths(info)
        if not sel_df.empty:
            all_selection.append(sel_df)

    if all_selection:
        selection_df = pd.concat(all_selection, ignore_index=True)
        path = chart_data_dir / "selection_paths.csv"
        selection_df.to_csv(path, index=False)
        outputs["selection_paths"] = path
        logger.info("Wrote %s (%d rows)", path, len(selection_df))

    # ── Decision comparison ──
    gbt_infos = [i for i in artifact_infos if i["schema"] == "action_value_gbt_v1"]
    if len(gbt_infos) >= 2 and not eval_df.empty:
        comparison_df, disagreement_df = generate_decision_comparison(
            gbt_infos, eval_df, eval_sample
        )
        if not comparison_df.empty:
            path = chart_data_dir / "decision_comparison.csv"
            comparison_df.to_csv(path, index=False)
            outputs["decision_comparison"] = path
            logger.info("Wrote %s (%d rows)", path, len(comparison_df))

        if not disagreement_df.empty:
            path = chart_data_dir / "disagreement_outcomes.csv"
            disagreement_df.to_csv(path, index=False)
            outputs["disagreement_outcomes"] = path
            logger.info("Wrote %s (%d rows)", path, len(disagreement_df))
    elif len(gbt_infos) < 2:
        logger.info(
            "Need >=2 GBT artifacts for decision comparison; found %d", len(gbt_infos)
        )

    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate interpretability artifacts for Arc D v2 rung analysis"
    )
    parser.add_argument(
        "--rung-dir",
        type=Path,
        required=True,
        help="Path to rung directory containing artifacts/ and datasets/",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        required=True,
        help="Output directory for interpretability CSVs",
    )
    parser.add_argument(
        "--eval-sample",
        type=int,
        default=5000,
        help="Max rows to subsample for SHAP computation (default: 5000)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.rung_dir.exists():
        logger.error("Rung directory does not exist: %s", args.rung_dir)
        sys.exit(1)

    outputs = run(
        rung_dir=args.rung_dir,
        report_dir=args.report_dir,
        eval_sample=args.eval_sample,
    )

    if outputs:
        print(f"\nGenerated {len(outputs)} output files:")
        for name, path in sorted(outputs.items()):
            print(f"  {name}: {path}")
    else:
        print("\nNo output files generated (missing artifacts or eval data)")


if __name__ == "__main__":
    main()

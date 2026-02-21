"""
Hybrid OLSa training pipeline for Arc D promotion-track evaluation.

Trains per-contract OLS models with optional forward feature selection
and produces hybrid_olsa_v1 artifacts for the HybridOLSaBidder.

Supports two arms:
  - OLSa (constrained): locked 3/1/1 features matching CONTRACT_FEATURES
  - OLSa_Full: forward-selected from all 39 features

CLI usage (preferred):
    PYTHONPATH=src python scripts/train_hybrid_olsa.py \\
        --run-dir data/runs/<run_id> --seed 42 --output /tmp/hybrid/
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone

import numpy as np

from ..datasets.join import join_features_outcomes
from .feature_selection import forward_select
from .freeze import freeze_artifact
from .splits import create_grouped_split
from .train_olsa import CONTRACT_FEATURES, _compute_metrics, _fit_ols

logger = logging.getLogger(__name__)

# Columns that are NOT features — known non-feature columns from
# bidless.parquet schema and join outputs.
_NON_FEATURE_COLS = frozenset(
    {
        "hand_id",
        "seat",
        "dealer_seat",
        "deal_id",
        "contract_type",
        "trump_suit",
        "hand_cards",
        "hand_features",
        "hand_feature_schema_version",
        "tricks_won",
        "tricks_team0",
        "tricks_team1",
        "team0_win",
        "strategy_id",
        "play_strategy_id",
    }
)


def _get_all_feature_names(df) -> list[str]:
    """Extract hand feature column names from the joined DataFrame.

    Uses both an explicit exclusion list and a numeric-dtype filter
    as defense-in-depth against non-numeric columns leaking through.
    """
    numeric_cols = set(df.select_dtypes(include="number").columns)
    return [c for c in df.columns if c not in _NON_FEATURE_COLS and c in numeric_cols]


def _git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _build_artifact(
    rung_id: str,
    models: dict,
    residual_variances: dict,
    risk_lambda: float,
    context_features: list[str],
    seed: int,
    source_run_id: str,
    split_type: str,
) -> dict:
    """Build a hybrid_olsa_v1 artifact dict."""
    return {
        "artifact_type": "hybrid_olsa_v1",
        "schema_version": 1,
        "rung_id": rung_id,
        "payoff_model": models,
        "residual_variance": residual_variances,
        "risk_lambda": risk_lambda,
        "context_features": context_features,
        "training_seed": seed,
        "training_run_id": source_run_id,
        "split_type": split_type,
        "frozen_at": None,
        "artifact_sha256": None,
    }


def _train_arm(
    df,
    feature_spec: dict[str, list[str]],
    seed: int,
    source_run_id: str,
    source_parquet_path: str,
    split_type: str,
    output_dir: str,
    arm_name: str,
    rung_id: str = "r0",
    risk_lambda: float = 0.0,
    feature_budget: dict[str, int] | None = None,
    do_forward_select: bool = False,
) -> tuple[dict, dict, dict | None]:
    """Train one arm (constrained or full) and return (artifact, metrics, fs_log)."""
    models = {}
    residual_variances = {}
    training_metrics = {}
    feature_selection_log = {} if do_forward_select else None

    for contract_family in ["suit", "high", "low"]:
        sub = df[df["contract_type"] == contract_family]
        if len(sub) == 0:
            logger.warning("No data for contract_type=%s, skipping", contract_family)
            continue

        train_df, val_df, test_df, manifest = create_grouped_split(
            sub,
            seed,
            source_run_id=source_run_id,
            source_parquet_path=source_parquet_path,
            split_type=split_type,
        )

        # Save split manifest (shared across arms, write once)
        manifest_path = os.path.join(
            output_dir, f"split_manifest_{rung_id}_{contract_family}.json"
        )
        if not os.path.exists(manifest_path):
            manifest.save(manifest_path)

        if do_forward_select:
            # Forward selection from all features
            all_features = _get_all_feature_names(df)
            budget = (feature_budget or {}).get(contract_family)

            X_train_all = train_df[all_features].values.astype(np.float64)
            y_train = train_df["tricks_won"].values.astype(np.float64)
            groups = train_df["hand_id"].values

            selected_names, fs_log = forward_select(
                X_train_all,
                y_train,
                candidate_names=all_features,
                groups=groups,
                max_features=budget,
                seed=seed,
            )
            feature_names = selected_names
            if feature_selection_log is not None:
                feature_selection_log[contract_family] = fs_log
        else:
            # Use prescribed features
            feature_names = feature_spec[contract_family]

        X_train = train_df[feature_names].values.astype(np.float64)
        y_train = train_df["tricks_won"].values.astype(np.float64)
        X_test = test_df[feature_names].values.astype(np.float64)
        y_test = test_df["tricks_won"].values.astype(np.float64)

        weights, bias = _fit_ols(X_train, y_train)

        # Residual variance on TRAIN only
        y_pred_train = X_train @ weights + bias
        residuals = y_train - y_pred_train
        resid_var = float(np.var(residuals))

        # Runtime guard: residual variance must be physically plausible
        # (tricks_won is 0-10, so variance > 25 = std > 5 is implausible)
        if not (0 < resid_var < 25):
            raise ValueError(
                f"Residual variance out of bounds for {contract_family}: "
                f"{resid_var:.4f} (expected 0 < σ² < 25)"
            )

        # Evaluation metrics on train and test
        y_pred_test = X_test @ weights + bias
        metrics_train = _compute_metrics(y_train, y_pred_train)
        metrics_test = _compute_metrics(y_test, y_pred_test)

        # Validation metrics (three_way split only)
        metrics_val = None
        n_val = 0
        if val_df is not None and len(val_df) > 0:
            X_val = val_df[feature_names].values.astype(np.float64)
            y_val = val_df["tricks_won"].values.astype(np.float64)
            y_pred_val = X_val @ weights + bias
            metrics_val = _compute_metrics(y_val, y_pred_val)
            n_val = len(val_df)

        models[contract_family] = {
            "weights": [float(w) for w in weights],
            "bias": float(bias),
            "feature_names": feature_names,
        }
        residual_variances[contract_family] = resid_var

        training_metrics[contract_family] = {
            "r2_train": metrics_train["r2"],
            "r2_test": metrics_test["r2"],
            "mae_train": metrics_train["mae"],
            "mae_test": metrics_test["mae"],
            "n_train": len(train_df),
            "n_test": len(test_df),
            "residual_variance": resid_var,
            "selected_features": feature_names,
        }
        if metrics_val is not None:
            training_metrics[contract_family]["r2_val"] = metrics_val["r2"]
            training_metrics[contract_family]["mae_val"] = metrics_val["mae"]
            training_metrics[contract_family]["n_val"] = n_val

        logger.info(
            "  %s [%s]: R²=%.4f (test), MAE=%.4f, σ²=%.4f, features=%s",
            contract_family,
            arm_name,
            metrics_test["r2"],
            metrics_test["mae"],
            resid_var,
            feature_names,
        )

    artifact = _build_artifact(
        rung_id=rung_id,
        models=models,
        residual_variances=residual_variances,
        risk_lambda=risk_lambda,
        context_features=[],
        seed=seed,
        source_run_id=source_run_id,
        split_type=split_type,
    )

    return artifact, training_metrics, feature_selection_log


def train_hybrid_olsa(
    run_dir: str,
    seed: int,
    output_dir: str,
    split_type: str = "three_way",
    arm_mode: str = "both",
    feature_budget: dict[str, int] | None = None,
    freeze: bool = True,
    rung_id: str = "r0",
    risk_lambda: float = 0.0,
) -> dict:
    """Train hybrid OLSa models from a canonical bidless run directory.

    Args:
        run_dir: Path to canonical bidless run.
        seed: Random seed for splitting and reproducibility.
        output_dir: Directory to write artifacts.
        split_type: "two_way" or "three_way" (three_way required for promotion).
        arm_mode: "both", "constrained", or "full".
        feature_budget: Per-contract max features for full arm (e.g., {"suit": 10}).
        freeze: Whether to freeze artifacts after writing.
        rung_id: Rung identifier (e.g., "r0").
        risk_lambda: Risk penalty coefficient (default 0.0 for R0).

    Returns:
        Dict with artifact paths and training summary.
    """
    bidless_path = os.path.join(run_dir, "datasets", "bidless.parquet")
    outcomes_path = os.path.join(run_dir, "datasets", "bidless_outcomes.parquet")

    if not os.path.exists(bidless_path):
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not os.path.exists(outcomes_path):
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    logger.info("Loading data from %s", run_dir)
    df = join_features_outcomes(bidless_path, outcomes_path)
    logger.info("Joined: %d rows", len(df))

    os.makedirs(output_dir, exist_ok=True)
    source_run_id = os.path.basename(run_dir)
    result = {"rung_id": rung_id, "artifacts": {}}

    # --- Constrained arm (OLSa with locked 3/1/1 features) ---
    if arm_mode in ("both", "constrained"):
        logger.info("Training constrained arm (OLSa)...")
        artifact, metrics, _ = _train_arm(
            df,
            CONTRACT_FEATURES,
            seed,
            source_run_id=source_run_id,
            source_parquet_path=bidless_path,
            split_type=split_type,
            output_dir=output_dir,
            arm_name="constrained",
            rung_id=rung_id,
            risk_lambda=risk_lambda,
            do_forward_select=False,
        )

        artifact_path = os.path.join(output_dir, f"hybrid_{rung_id}.json")
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2, sort_keys=True)

        if freeze:
            freeze_artifact(artifact_path)

        result["artifacts"]["constrained"] = artifact_path
        result["constrained_metrics"] = metrics

    # --- Full arm (OLSa_Full with forward selection) ---
    if arm_mode in ("both", "full"):
        logger.info("Training full arm (OLSa_Full) with forward selection...")
        artifact_full, metrics_full, fs_log = _train_arm(
            df,
            CONTRACT_FEATURES,
            seed,
            source_run_id=source_run_id,
            source_parquet_path=bidless_path,
            split_type=split_type,
            output_dir=output_dir,
            arm_name="full",
            rung_id=rung_id,
            risk_lambda=risk_lambda,
            feature_budget=feature_budget,
            do_forward_select=True,
        )

        artifact_full_path = os.path.join(output_dir, f"hybrid_{rung_id}_full.json")
        with open(artifact_full_path, "w") as f:
            json.dump(artifact_full, f, indent=2, sort_keys=True)

        if freeze:
            freeze_artifact(artifact_full_path)

        result["artifacts"]["full"] = artifact_full_path
        result["full_metrics"] = metrics_full

        # Save feature selection log
        if fs_log:
            fs_log_path = os.path.join(
                output_dir, f"feature_selection_log_{rung_id}_full.json"
            )
            with open(fs_log_path, "w") as f:
                json.dump(fs_log, f, indent=2)
            result["feature_selection_log"] = fs_log_path

    # --- Training report ---
    report = {
        "rung_id": rung_id,
        "training_seed": seed,
        "source_run_id": source_run_id,
        "split_type": split_type,
        "arm_mode": arm_mode,
        "git_sha": _git_sha(),
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if "constrained_metrics" in result:
        report["constrained"] = result["constrained_metrics"]
    if "full_metrics" in result:
        report["full"] = result["full_metrics"]

    report_path = os.path.join(output_dir, f"training_report_{rung_id}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    result["training_report"] = report_path

    # --- Rung bundle (when both arms are trained) ---
    if arm_mode == "both":
        # Extract per-arm metadata for bundle
        def _arm_block(artifact_path: str, fs_log_path: str | None = None) -> dict:
            with open(artifact_path) as af:
                art = json.load(af)
            selected = {
                cf: art["payoff_model"][cf]["feature_names"]
                for cf in art["payoff_model"]
            }
            block = {
                "artifact_path": artifact_path,
                "artifact_sha256": art.get("artifact_sha256"),
                "selected_features": selected,
                # Populated by evaluation PRs (PR-I2+)
                "eval_seed42": None,
                "eval_seed43": None,
                "eval_seed44": None,
                "semantic_gate_val": None,
                "semantic_gate_test": None,
            }
            if fs_log_path is not None:
                block["feature_selection_log"] = fs_log_path
            return block

        olsa_block = _arm_block(result["artifacts"]["constrained"])
        olsa_full_block = _arm_block(
            result["artifacts"]["full"],
            fs_log_path=result.get("feature_selection_log"),
        )

        bundle = {
            "bundle_schema": "arc_d_rung_bundle_v1",
            "rung_id": rung_id,
            "arc": "arc_d",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "olsa": olsa_block,
            "olsa_full": olsa_full_block,
            "split_manifest": os.path.join(
                output_dir, f"split_manifest_{rung_id}_suit.json"
            ),
            "training_report": report_path,
            "incumbent": None,
            "control": None,
        }

        bundle_path = os.path.join(output_dir, f"rung_bundle_{rung_id}.json")
        with open(bundle_path, "w") as f:
            json.dump(bundle, f, indent=2)
        result["rung_bundle"] = bundle_path

    logger.info("Training complete. Output: %s", output_dir)
    return result

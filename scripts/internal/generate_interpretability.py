#!/usr/bin/env python
"""Generate interpretability artifacts for Arc D v2 rung reports.

Produces SHAP analysis, feature selection paths, prediction diagnostics,
and cross-model decision comparison artifacts. Reads model artifacts and
eval predictions, outputs CSVs to chart_data/ and PNGs to charts/.

Usage:
    uv run python scripts/internal/generate_interpretability.py \
        --rung r0 --mode smoke --seed 42

    # Or with explicit directories:
    uv run python scripts/internal/generate_interpretability.py \
        --rung-dir data/runs/arc_d_v2/r0 \
        --report-dir docs/04_reports/arc_d_v2/r0

Outputs (chart_data/):
  - shap_values.csv          — per-prediction SHAP values for GBT
  - shap_dependence.csv      — binned dependence data for top features
  - shap_interactions.csv    — top interaction pairs
  - selection_paths.csv      — forward selection R² path per model
  - predictions.csv          — predicted vs actual per model × contract
  - residuals.csv            — residuals per model × contract
  - decision_comparison.csv  — agreement/disagreement rates
  - disagreement_outcomes.csv — outcome analysis for disagreements

Outputs (charts/):
  - shap_summary.png           — SHAP beeswarm per contract
  - shap_dependence_top5.png   — top-5 feature dependence curves
  - shap_interactions.png      — top-3 interaction effects (heatmap)
  - selection_path.png         — forward selection R² curves
  - pred_vs_actual.png         — scatter per model × contract
  - residual_distribution.png  — residual histograms
  - decision_agreement.png     — agreement rates by contract
  - disagreement_outcomes.png  — who wins when models disagree?

Outputs (tables/):
  - selected_features.csv      — final feature sets from forward selection
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  SHAP value shape normalization
# ──────────────────────────────────────────────


def normalize_shap_values(shap_values: object) -> np.ndarray:
    """Normalize SHAP values to 2D (n_samples, n_features).

    shap.TreeExplainer.shap_values() can return variable shapes:
    - list of arrays for multi-class models (take last/positive class)
    - 1D array for single feature
    - 3D array for multi-output models

    This function normalizes all cases to a 2D (n_samples, n_features) array.
    """
    # Multi-class: list of arrays, take positive class (last)
    if isinstance(shap_values, list):
        shap_values = np.array(shap_values[-1])

    shap_values = np.asarray(shap_values)

    # Single feature: reshape 1D to (n_samples, 1)
    if shap_values.ndim == 1:
        shap_values = shap_values.reshape(-1, 1)
    # Multi-output: take first output
    elif shap_values.ndim == 3:
        shap_values = shap_values[:, :, 0]

    return shap_values


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────


def _save_chart(fig: plt.Figure, output_dir: Path, name: str, dpi: int = 150) -> None:
    """Save a chart and close the figure."""
    path = output_dir / name
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", path)


def _read_csv_safe(path: Path) -> pd.DataFrame | None:
    """Read CSV, returning None if missing or empty."""
    if not path.exists():
        logger.warning("CSV not found: %s", path)
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) > 0 else None
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def _load_model_artifact(artifact_path: Path) -> dict | None:
    """Load a model artifact JSON, returning None if not found."""
    if not artifact_path.exists():
        logger.warning("Artifact not found: %s", artifact_path)
        return None
    try:
        with open(artifact_path) as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load artifact %s: %s", artifact_path, e)
        return None


def _resolve_rung_dirs(
    args: argparse.Namespace,
) -> tuple[Path, Path]:
    """Resolve rung-dir and report-dir from CLI args."""
    if args.rung_dir and args.report_dir:
        return Path(args.rung_dir), Path(args.report_dir)

    if args.rung:
        rung_dir = Path("data/runs/arc_d_v2") / args.rung
        report_dir = Path("docs/04_reports/arc_d_v2") / args.rung
        return rung_dir, report_dir

    raise ValueError("Must specify either --rung or both --rung-dir and --report-dir")


# ──────────────────────────────────────────────
#  SHAP analysis (GBT models only)
# ──────────────────────────────────────────────


def generate_shap_artifacts(
    rung_dir: Path,
    chart_data_dir: Path,
    charts_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate SHAP analysis artifacts for GBT models.

    Returns list of generated file names.
    """
    generated: list[str] = []

    try:
        import shap
    except ImportError:
        logger.warning("shap not installed; skipping SHAP analysis")
        return generated

    # Find GBT model artifacts
    models_dir = rung_dir / "models"
    if not models_dir.exists():
        logger.warning("Models directory not found: %s", models_dir)
        return generated

    # Look for GBT artifacts
    gbt_artifacts = sorted(models_dir.glob("*gbt*.json"))
    if not gbt_artifacts:
        logger.info("No GBT model artifacts found; skipping SHAP analysis")
        return generated

    # Load eval dataset for SHAP computation
    datasets_dir = rung_dir / "datasets"
    dataset_path = datasets_dir / "action_value.parquet"
    if not dataset_path.exists():
        logger.warning("Action value dataset not found: %s", dataset_path)
        return generated

    df = pd.read_parquet(dataset_path)

    all_shap_values = []
    all_shap_dependence = []
    all_shap_interactions = []

    for artifact_path in gbt_artifacts:
        artifact = _load_model_artifact(artifact_path)
        if artifact is None:
            continue

        contract_type = artifact.get("contract_type", "unknown")
        feature_names = artifact.get("feature_names", [])

        if not feature_names:
            logger.warning("No feature names in %s", artifact_path)
            continue

        # Filter data for this contract type
        contract_df = df[
            df.get("contract_family", df.get("action_type", "")) == contract_type
        ]
        if len(contract_df) == 0:
            # Try action_type column name
            if "action_type" in df.columns:
                contract_df = df[df["action_type"] == contract_type]
            if len(contract_df) == 0:
                logger.warning("No data for contract_type=%s", contract_type)
                continue

        # Build feature matrix
        available_features = [f for f in feature_names if f in contract_df.columns]
        if not available_features:
            logger.warning("No features available in dataset for %s", contract_type)
            continue

        X = contract_df[available_features].values

        # Load the sklearn model
        try:
            import pickle

            model_file = artifact_path.with_suffix(".pkl")
            if not model_file.exists():
                # Try joblib format
                model_file = artifact_path.with_suffix(".joblib")
            if not model_file.exists():
                logger.warning("No model file found for %s", artifact_path)
                continue

            with open(model_file, "rb") as f:
                model = pickle.load(f)  # noqa: S301
        except Exception as e:
            logger.warning("Failed to load model for %s: %s", artifact_path, e)
            continue

        # Compute SHAP values
        try:
            # Use a subsample for large datasets
            n_samples = min(len(X), 1000)
            X_sample = X[:n_samples]

            explainer = shap.TreeExplainer(model)
            raw_shap = explainer.shap_values(X_sample)

            # Normalize SHAP values to 2D (n_samples, n_features)
            shap_vals = normalize_shap_values(raw_shap)

            # Validate shape
            if shap_vals.shape[1] != len(available_features):
                logger.warning(
                    "SHAP shape mismatch: got %d features, expected %d for %s",
                    shap_vals.shape[1],
                    len(available_features),
                    contract_type,
                )
                continue

            # SHAP values CSV
            for i, feat_name in enumerate(available_features):
                for j in range(shap_vals.shape[0]):
                    all_shap_values.append(
                        {
                            "contract_type": contract_type,
                            "feature": feat_name,
                            "feature_value": float(X_sample[j, i]),
                            "shap_value": float(shap_vals[j, i]),
                        }
                    )

            # SHAP dependence (top 5 features by mean |SHAP|)
            mean_abs_shap = np.mean(np.abs(shap_vals), axis=0)
            top_indices = np.argsort(mean_abs_shap)[-5:][::-1]

            for idx in top_indices:
                feat_name = available_features[idx]
                feat_vals = X_sample[:, idx]
                shap_col = shap_vals[:, idx]

                # Bin into 20 bins
                n_bins = min(20, len(np.unique(feat_vals)))
                if n_bins < 2:
                    continue

                bins = np.linspace(feat_vals.min(), feat_vals.max(), n_bins + 1)
                for b in range(n_bins):
                    mask = (feat_vals >= bins[b]) & (feat_vals < bins[b + 1])
                    if b == n_bins - 1:
                        mask = (feat_vals >= bins[b]) & (feat_vals <= bins[b + 1])
                    if mask.sum() == 0:
                        continue
                    all_shap_dependence.append(
                        {
                            "contract_type": contract_type,
                            "feature": feat_name,
                            "bin_center": (bins[b] + bins[b + 1]) / 2,
                            "mean_shap": float(np.mean(shap_col[mask])),
                            "std_shap": float(np.std(shap_col[mask])),
                            "n": int(mask.sum()),
                        }
                    )

            # SHAP interactions (top 3 pairs)
            for rank, idx_i in enumerate(top_indices[:3]):
                for idx_j in top_indices[rank + 1 : 6]:
                    if idx_j >= len(available_features):
                        continue
                    # Approximate interaction as correlation of SHAP values
                    corr = np.corrcoef(shap_vals[:, idx_i], shap_vals[:, idx_j])[0, 1]
                    all_shap_interactions.append(
                        {
                            "contract_type": contract_type,
                            "feature_1": available_features[idx_i],
                            "feature_2": available_features[idx_j],
                            "interaction_strength": float(abs(corr)),
                            "correlation": float(corr),
                        }
                    )

        except Exception as e:
            logger.warning("SHAP computation failed for %s: %s", contract_type, e)
            continue

    # Write CSVs
    if all_shap_values:
        pd.DataFrame(all_shap_values).to_csv(
            chart_data_dir / "shap_values.csv", index=False
        )
        generated.append("shap_values.csv")
        logger.info("Wrote shap_values.csv (%d rows)", len(all_shap_values))

    if all_shap_dependence:
        pd.DataFrame(all_shap_dependence).to_csv(
            chart_data_dir / "shap_dependence.csv", index=False
        )
        generated.append("shap_dependence.csv")

    if all_shap_interactions:
        pd.DataFrame(all_shap_interactions).to_csv(
            chart_data_dir / "shap_interactions.csv", index=False
        )
        generated.append("shap_interactions.csv")

    # Generate charts from the CSVs
    chart_names = _generate_shap_charts(chart_data_dir, charts_dir, dpi)
    generated.extend(chart_names)

    return generated


def _generate_shap_charts(
    chart_data_dir: Path,
    charts_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate SHAP charts from CSVs."""
    generated: list[str] = []

    # SHAP summary (beeswarm approximation — scatter of SHAP values per feature)
    df = _read_csv_safe(chart_data_dir / "shap_values.csv")
    if df is not None:
        contracts = sorted(df["contract_type"].unique())
        n_contracts = len(contracts)
        if n_contracts > 0:
            fig, axes = plt.subplots(
                1, n_contracts, figsize=(6 * n_contracts, 8), squeeze=False
            )
            for i, ct in enumerate(contracts):
                ax = axes[0, i]
                ct_df = df[df["contract_type"] == ct]
                # Top 10 features by mean |SHAP|
                importance = (
                    ct_df.groupby("feature")["shap_value"]
                    .apply(lambda x: np.mean(np.abs(x)))
                    .sort_values(ascending=True)
                    .tail(10)
                )
                features = importance.index.tolist()
                for feat in features:
                    feat_data = ct_df[ct_df["feature"] == feat]
                    ax.scatter(
                        feat_data["shap_value"],
                        [feat] * len(feat_data),
                        c=feat_data["feature_value"],
                        cmap="coolwarm",
                        alpha=0.4,
                        s=5,
                    )
                ax.set_title(f"SHAP Summary — {ct}")
                ax.set_xlabel("SHAP value")
            fig.suptitle("SHAP Feature Importance", y=1.02)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "shap_summary.png", dpi)
            generated.append("shap_summary.png")

    # SHAP dependence (top 5)
    df = _read_csv_safe(chart_data_dir / "shap_dependence.csv")
    if df is not None:
        contracts = sorted(df["contract_type"].unique())
        features = (
            df.groupby("feature")["mean_shap"]
            .apply(lambda x: np.mean(np.abs(x)))
            .sort_values(ascending=False)
            .head(5)
            .index.tolist()
        )

        if features:
            fig, axes = plt.subplots(
                len(features),
                len(contracts),
                figsize=(5 * len(contracts), 3 * len(features)),
                squeeze=False,
            )
            for i, feat in enumerate(features):
                for j, ct in enumerate(contracts):
                    ax = axes[i, j]
                    sub = df[(df["feature"] == feat) & (df["contract_type"] == ct)]
                    if len(sub) > 0:
                        ax.errorbar(
                            sub["bin_center"],
                            sub["mean_shap"],
                            yerr=sub["std_shap"],
                            fmt="o-",
                            capsize=3,
                            markersize=4,
                        )
                    ax.set_xlabel(feat if i == len(features) - 1 else "")
                    ax.set_ylabel("Mean SHAP" if j == 0 else "")
                    if i == 0:
                        ax.set_title(ct)
            fig.suptitle("SHAP Dependence — Top 5 Features", y=1.02)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "shap_dependence_top5.png", dpi)
            generated.append("shap_dependence_top5.png")

    # SHAP interactions heatmap
    chart_name = generate_shap_interactions_chart(chart_data_dir, charts_dir, dpi)
    if chart_name:
        generated.append(chart_name)

    return generated


def generate_shap_interactions_chart(
    chart_data_dir: Path,
    charts_dir: Path,
    dpi: int = 150,
) -> str | None:
    """Generate SHAP interactions heatmap from shap_interactions.csv.

    Creates a heatmap showing interaction strengths between top feature pairs,
    faceted by contract type.
    """
    df = _read_csv_safe(chart_data_dir / "shap_interactions.csv")
    if df is None:
        return None

    contracts = sorted(df["contract_type"].unique())
    n_contracts = len(contracts)
    if n_contracts == 0:
        return None

    fig, axes = plt.subplots(
        1, n_contracts, figsize=(6 * n_contracts, 5), squeeze=False
    )

    for i, ct in enumerate(contracts):
        ax = axes[0, i]
        ct_df = df[df["contract_type"] == ct]

        if len(ct_df) == 0:
            ax.set_title(f"{ct} — no data")
            ax.axis("off")
            continue

        # Build interaction matrix
        all_features = sorted(
            set(ct_df["feature_1"].tolist() + ct_df["feature_2"].tolist())
        )
        n_feat = len(all_features)
        feat_to_idx = {f: j for j, f in enumerate(all_features)}

        matrix = np.zeros((n_feat, n_feat))
        for _, row in ct_df.iterrows():
            i1 = feat_to_idx[row["feature_1"]]
            i2 = feat_to_idx[row["feature_2"]]
            matrix[i1, i2] = row["interaction_strength"]
            matrix[i2, i1] = row["interaction_strength"]

        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto", vmin=0, vmax=1)
        ax.set_xticks(range(n_feat))
        ax.set_yticks(range(n_feat))
        # Truncate long feature names
        labels = [f[:12] for f in all_features]
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels(labels, fontsize=8)
        ax.set_title(f"{ct}")
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Interaction Strength")

    fig.suptitle("SHAP Feature Interactions by Contract", y=1.02)
    fig.tight_layout()
    _save_chart(fig, charts_dir, "shap_interactions.png", dpi)
    return "shap_interactions.png"


# ──────────────────────────────────────────────
#  Selection path analysis
# ──────────────────────────────────────────────


def generate_selection_path_artifacts(
    rung_dir: Path,
    chart_data_dir: Path,
    charts_dir: Path,
    tables_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate feature selection path artifacts.

    Returns list of generated file names.
    """
    generated: list[str] = []

    # Look for selection path data in model artifacts
    models_dir = rung_dir / "models"
    if not models_dir.exists():
        return generated

    # Find artifacts with selection_path data
    all_paths = []
    all_selected = []

    for artifact_path in sorted(models_dir.glob("*.json")):
        artifact = _load_model_artifact(artifact_path)
        if artifact is None:
            continue

        model_name = artifact.get("strategy_id", artifact_path.stem)
        contract_type = artifact.get("contract_type", "unknown")

        # Check for selection path data
        selection_path = artifact.get("selection_path", [])
        if selection_path:
            for step in selection_path:
                all_paths.append(
                    {
                        "model": model_name,
                        "contract_type": contract_type,
                        "n_features": step.get("n_features", 0),
                        "r2_oof": step.get("r2_oof", 0.0),
                        "feature_added": step.get("feature_added", ""),
                    }
                )

        # Collect selected features
        feature_names = artifact.get("feature_names", [])
        if feature_names:
            for feat in feature_names:
                all_selected.append(
                    {
                        "model": model_name,
                        "contract_type": contract_type,
                        "feature": feat,
                    }
                )

    if all_paths:
        pd.DataFrame(all_paths).to_csv(
            chart_data_dir / "selection_paths.csv", index=False
        )
        generated.append("selection_paths.csv")

        # Generate selection path chart
        df = pd.DataFrame(all_paths)
        contracts = sorted(df["contract_type"].unique())
        models = sorted(df["model"].unique())

        fig, axes = plt.subplots(
            1, len(contracts), figsize=(6 * len(contracts), 4), squeeze=False
        )
        for i, ct in enumerate(contracts):
            ax = axes[0, i]
            for model in models:
                sub = df[(df["contract_type"] == ct) & (df["model"] == model)]
                if len(sub) > 0:
                    sub = sub.sort_values("n_features")
                    ax.plot(
                        sub["n_features"],
                        sub["r2_oof"],
                        "o-",
                        label=model,
                        markersize=4,
                    )
            ax.set_xlabel("Number of Features")
            ax.set_ylabel("OOF R²")
            ax.set_title(ct)
            ax.legend(fontsize=8)
        fig.suptitle("Forward Selection R² Path", y=1.02)
        fig.tight_layout()
        _save_chart(fig, charts_dir, "selection_path.png", dpi)
        generated.append("selection_path.png")

    if all_selected:
        pd.DataFrame(all_selected).to_csv(
            tables_dir / "selected_features.csv", index=False
        )
        generated.append("selected_features.csv")

    return generated


# ──────────────────────────────────────────────
#  Prediction diagnostics
# ──────────────────────────────────────────────


def generate_prediction_diagnostics(
    rung_dir: Path,
    chart_data_dir: Path,
    charts_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate prediction vs actual and residual charts.

    Returns list of generated file names.
    """
    generated: list[str] = []

    # Look for predictions data
    predictions_csv = chart_data_dir / "predictions.csv"
    if predictions_csv.exists():
        df = _read_csv_safe(predictions_csv)
        if df is not None and "predicted" in df.columns and "actual" in df.columns:
            # Pred vs actual scatter
            contracts = (
                sorted(df["contract_type"].unique())
                if "contract_type" in df.columns
                else ["all"]
            )
            n = len(contracts)
            fig, axes = plt.subplots(1, n, figsize=(5 * n, 4), squeeze=False)
            for i, ct in enumerate(contracts):
                ax = axes[0, i]
                sub = (
                    df[df["contract_type"] == ct]
                    if "contract_type" in df.columns
                    else df
                )
                ax.scatter(sub["actual"], sub["predicted"], alpha=0.3, s=5)
                lims = [
                    min(sub["actual"].min(), sub["predicted"].min()),
                    max(sub["actual"].max(), sub["predicted"].max()),
                ]
                ax.plot(lims, lims, "r--", alpha=0.5)
                ax.set_xlabel("Actual")
                ax.set_ylabel("Predicted")
                ax.set_title(ct)
            fig.suptitle("Predicted vs Actual", y=1.02)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "pred_vs_actual.png", dpi)
            generated.append("pred_vs_actual.png")

    # Residuals
    residuals_csv = chart_data_dir / "residuals.csv"
    if residuals_csv.exists():
        df = _read_csv_safe(residuals_csv)
        if df is not None and "residual" in df.columns:
            contracts = (
                sorted(df["contract_type"].unique())
                if "contract_type" in df.columns
                else ["all"]
            )
            n = len(contracts)
            fig, axes = plt.subplots(1, n, figsize=(5 * n, 4), squeeze=False)
            for i, ct in enumerate(contracts):
                ax = axes[0, i]
                sub = (
                    df[df["contract_type"] == ct]
                    if "contract_type" in df.columns
                    else df
                )
                ax.hist(sub["residual"], bins=50, alpha=0.7, edgecolor="black")
                ax.axvline(0, color="red", linestyle="--", alpha=0.5)
                ax.set_xlabel("Residual")
                ax.set_ylabel("Count")
                ax.set_title(ct)
            fig.suptitle("Residual Distribution", y=1.02)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "residual_distribution.png", dpi)
            generated.append("residual_distribution.png")

    return generated


# ──────────────────────────────────────────────
#  Cross-model decision comparison
# ──────────────────────────────────────────────


def generate_decision_comparison(
    chart_data_dir: Path,
    charts_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate cross-model decision comparison artifacts.

    Returns list of generated file names.
    """
    generated: list[str] = []

    # Decision comparison
    comparison_csv = chart_data_dir / "decision_comparison.csv"
    if comparison_csv.exists():
        df = _read_csv_safe(comparison_csv)
        if df is not None and "agreement_rate" in df.columns:
            fig, ax = plt.subplots(figsize=(8, 5))
            if "contract_type" in df.columns:
                contracts = sorted(df["contract_type"].unique())
                x = np.arange(len(contracts))
                model_pairs = df.groupby(["model_1", "model_2"]).ngroups
                width = 0.8 / max(model_pairs, 1)
                for j, (pair, grp) in enumerate(df.groupby(["model_1", "model_2"])):
                    label = f"{pair[0]} vs {pair[1]}"
                    vals = []
                    for ct in contracts:
                        ct_data = grp[grp["contract_type"] == ct]
                        vals.append(
                            ct_data["agreement_rate"].mean() if len(ct_data) > 0 else 0
                        )
                    ax.bar(x + j * width, vals, width, label=label)
                ax.set_xticks(x + width * (model_pairs - 1) / 2)
                ax.set_xticklabels(contracts)
            ax.set_ylabel("Agreement Rate")
            ax.set_title("Decision Agreement by Contract")
            ax.legend(fontsize=8)
            ax.set_ylim(0, 1)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "decision_agreement.png", dpi)
            generated.append("decision_agreement.png")

    # Disagreement outcomes
    disagreement_csv = chart_data_dir / "disagreement_outcomes.csv"
    if disagreement_csv.exists():
        df = _read_csv_safe(disagreement_csv)
        if df is not None:
            fig, ax = plt.subplots(figsize=(8, 5))
            if "model_better" in df.columns and "contract_type" in df.columns:
                summary = (
                    df.groupby(["model_better", "contract_type"])
                    .size()
                    .unstack(fill_value=0)
                )
                summary.plot(kind="bar", ax=ax)
                ax.set_xlabel("Model with Better Outcome")
                ax.set_ylabel("Count")
            ax.set_title("Disagreement Outcomes — Who Wins?")
            ax.legend(title="Contract", fontsize=8)
            fig.tight_layout()
            _save_chart(fig, charts_dir, "disagreement_outcomes.png", dpi)
            generated.append("disagreement_outcomes.png")

    return generated


# ──────────────────────────────────────────────
#  Main orchestrator
# ──────────────────────────────────────────────


def generate_all(
    rung_dir: Path,
    report_dir: Path,
    dpi: int = 150,
) -> list[str]:
    """Generate all interpretability artifacts.

    Returns list of generated file names.
    """
    chart_data_dir = report_dir / "chart_data"
    charts_dir = report_dir / "charts"
    tables_dir = report_dir / "tables"

    # Create output directories
    for d in [chart_data_dir, charts_dir, tables_dir]:
        d.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []

    # 1. SHAP analysis
    try:
        shap_files = generate_shap_artifacts(rung_dir, chart_data_dir, charts_dir, dpi)
        generated.extend(shap_files)
    except Exception as e:
        logger.warning("SHAP analysis failed: %s", e)

    # 2. Selection paths
    try:
        selection_files = generate_selection_path_artifacts(
            rung_dir, chart_data_dir, charts_dir, tables_dir, dpi
        )
        generated.extend(selection_files)
    except Exception as e:
        logger.warning("Selection path analysis failed: %s", e)

    # 3. Prediction diagnostics
    try:
        pred_files = generate_prediction_diagnostics(
            rung_dir, chart_data_dir, charts_dir, dpi
        )
        generated.extend(pred_files)
    except Exception as e:
        logger.warning("Prediction diagnostics failed: %s", e)

    # 4. Decision comparison
    try:
        decision_files = generate_decision_comparison(chart_data_dir, charts_dir, dpi)
        generated.extend(decision_files)
    except Exception as e:
        logger.warning("Decision comparison failed: %s", e)

    return generated


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate interpretability artifacts for Arc D v2 rung reports."
    )
    parser.add_argument(
        "--rung",
        default=None,
        help="Rung ID (e.g., r0, r1). Auto-resolves rung-dir and report-dir.",
    )
    parser.add_argument(
        "--rung-dir",
        default=None,
        type=Path,
        help="Path to rung data directory",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        type=Path,
        help="Path to report output directory",
    )
    parser.add_argument(
        "--mode",
        default="smoke",
        choices=["smoke", "quick", "full"],
        help="Execution mode (default: smoke)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="DPI for saved figures (default: 150)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    rung_dir, report_dir = _resolve_rung_dirs(args)
    logger.info("Rung dir: %s", rung_dir)
    logger.info("Report dir: %s", report_dir)

    generated = generate_all(rung_dir, report_dir, args.dpi)
    logger.info("Generated %d artifacts: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()

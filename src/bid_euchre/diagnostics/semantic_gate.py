"""Semantic gate evaluation engine for model-rung HITL workflow.

Computes 12 health/quality checks in two tiers and emits a
machine-readable ``semantic_gate.json`` artifact.

**Tier 1 — Framework Health** (model-agnostic, fixed thresholds):
  val_split_integrity, feature_count, no_nan_features, tricks_range,
  min_sample_size

**Tier 2 — Model Quality Floor** (framework defaults, overridable per rung):
  seat_balance, contract_type_balance, trump_suit_invariance,
  team_balance, prediction_correlation, r_squared_floor, mae_ceiling

Usage::

    gate = compute_semantic_gate(
        df=val_df,
        mode="FULL",
        active_split="val",
        seed=42,
        manifest=manifest,
        predictions=pred_array,
        model_coefficients=coef_dict,
    )
    emit_semantic_gate(gate, output_dir)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Schema constants
# ──────────────────────────────────────────────

SEMANTIC_GATE_SCHEMA_VERSION = 1

SEMANTIC_GATE_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "gate_status",
        "created_at_utc",
        "active_split",
        "mode",
        "seed",
        "total_hands",
        "total_checks",
        "passed_checks",
        "failed_checks",
        "checks",
    }
)

SEMANTIC_CHECK_REQUIRED_FIELDS = frozenset(
    {
        "check_id",
        "category",
        "status",
        "threshold",
        "observed",
        "detail",
    }
)

# ──────────────────────────────────────────────
#  Default thresholds
# ──────────────────────────────────────────────

# Tier 1 (fixed, never relaxed)
MIN_SAMPLE_SIZES = {"SMOKE": 10, "QUICK": 100, "FULL": 2000}

# Tier 2 (framework defaults — catch catastrophic failures only)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "seat_balance_alpha": 0.01,
    "contract_balance_alpha": 0.01,
    "trump_invariance_spread": 0.02,
    "team_balance_delta": 0.25,
    "min_correlation": 0.10,
    "min_r_squared": 0.05,
    "max_mae": 2.5,
}

# Minimum per-cell N for statistical tests
_MIN_STAT_N = 200

# Feature names for sign checks (established in Phase 0)
_SIGN_CHECK_FEATURES = {
    "suit": "trump_count",
    "high": "offsuit_aces",
    "low": "offsuit_tens_count",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_check(
    check_id: str,
    category: str,
    status: str,
    threshold: str,
    observed: str,
    detail: str,
    *,
    contract_type: str | None = None,
    n_samples: int | None = None,
) -> dict[str, Any]:
    """Build a check entry dict."""
    entry: dict[str, Any] = {
        "check_id": check_id,
        "category": category,
        "status": status,
        "threshold": threshold,
        "observed": observed,
        "detail": detail,
    }
    if contract_type is not None:
        entry["contract_type"] = contract_type
    if n_samples is not None:
        entry["n_samples"] = n_samples
    return entry


# ──────────────────────────────────────────────
#  Tier 1 — Framework Health Checks
# ──────────────────────────────────────────────


def check_feature_count(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, Any]:
    """Verify feature column count matches expected set."""
    from bid_euchre.core.cards import Card
    from bid_euchre.features.hand_eval import get_hand_features

    # Get expected count by calling the feature extractor
    # Card(suit, rank) — 10 aces of hearts with hearts as trump
    dummy_hand = [Card("H", "A")] * 10
    expected = len(get_hand_features(dummy_hand, "suit", "H"))

    actual = len(feature_cols)
    if actual == expected:
        return _make_check(
            "feature_count",
            "health",
            "PASS",
            threshold=f"exactly {expected}",
            observed=str(actual),
            detail=f"Feature count matches: {actual}",
        )
    return _make_check(
        "feature_count",
        "health",
        "FAIL",
        threshold=f"exactly {expected}",
        observed=str(actual),
        detail=f"Feature count mismatch: got {actual}, expected {expected}",
    )


def check_no_nan_features(
    df: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, Any]:
    """Verify zero NaN values in feature columns."""
    nan_count = df[feature_cols].isna().sum().sum()
    if nan_count == 0:
        return _make_check(
            "no_nan_features",
            "health",
            "PASS",
            threshold="0 NaN",
            observed="0",
            detail="No NaN values in feature columns",
        )
    return _make_check(
        "no_nan_features",
        "health",
        "FAIL",
        threshold="0 NaN",
        observed=str(int(nan_count)),
        detail=f"Found {int(nan_count)} NaN values in feature columns",
    )


def check_tricks_range(df: pd.DataFrame) -> dict[str, Any]:
    """Verify all tricks_won values are in [0, 10]."""
    if "tricks_won" not in df.columns:
        return _make_check(
            "tricks_range",
            "health",
            "FAIL",
            threshold="all in [0, 10]",
            observed="column missing",
            detail="tricks_won column not found",
        )
    in_range = df["tricks_won"].between(0, 10).all()
    lo = df["tricks_won"].min()
    hi = df["tricks_won"].max()
    if in_range:
        return _make_check(
            "tricks_range",
            "health",
            "PASS",
            threshold="all in [0, 10]",
            observed=f"[{lo}, {hi}]",
            detail=f"All tricks_won in [0, 10] (range: {lo}–{hi})",
        )
    return _make_check(
        "tricks_range",
        "health",
        "FAIL",
        threshold="all in [0, 10]",
        observed=f"[{lo}, {hi}]",
        detail=f"tricks_won out of range: min={lo}, max={hi}",
    )


def check_min_sample_size(
    df: pd.DataFrame,
    mode: str,
) -> dict[str, Any]:
    """Verify val split meets minimum N for the declared mode."""
    n_hands = df["hand_id"].nunique() if "hand_id" in df.columns else len(df)
    threshold = MIN_SAMPLE_SIZES.get(mode, MIN_SAMPLE_SIZES["FULL"])
    if n_hands >= threshold:
        return _make_check(
            "min_sample_size",
            "health",
            "PASS",
            threshold=f"N >= {threshold} ({mode})",
            observed=str(n_hands),
            detail=f"Sample size {n_hands} meets {mode} minimum of {threshold}",
            n_samples=n_hands,
        )
    return _make_check(
        "min_sample_size",
        "health",
        "FAIL",
        threshold=f"N >= {threshold} ({mode})",
        observed=str(n_hands),
        detail=f"Sample size {n_hands} below {mode} minimum of {threshold}",
        n_samples=n_hands,
    )


def check_val_split_integrity(
    df: pd.DataFrame,
    manifest: Any,
    seed: int,
) -> dict[str, Any]:
    """Verify partition hash matches split manifest."""
    from bid_euchre.models.splits import verify_split_manifest

    if manifest is None:
        return _make_check(
            "val_split_integrity",
            "health",
            "PASS",
            threshold="hash match",
            observed="no manifest provided",
            detail="No manifest provided; integrity check skipped",
        )

    matches = verify_split_manifest(manifest, df, seed)
    if matches:
        return _make_check(
            "val_split_integrity",
            "health",
            "PASS",
            threshold="hash match",
            observed="match",
            detail="Partition hashes match manifest",
        )
    return _make_check(
        "val_split_integrity",
        "health",
        "FAIL",
        threshold="hash match",
        observed="mismatch",
        detail="Partition hashes do NOT match manifest. Data may be corrupted.",
    )


# ──────────────────────────────────────────────
#  Tier 2 — Model Quality Floor Checks
# ──────────────────────────────────────────────


def check_seat_balance(
    df: pd.DataFrame,
    mode: str,
    *,
    alpha: float = DEFAULT_THRESHOLDS["seat_balance_alpha"],
) -> list[dict[str, Any]]:
    """ANOVA F-test on hand_value by seat, per contract_type."""
    results = []

    if "contract_type" not in df.columns or "seat" not in df.columns:
        results.append(
            _make_check(
                "seat_balance",
                "fairness",
                "SKIP",
                threshold=f"ANOVA p > {alpha}",
                observed="missing columns",
                detail="Required columns (contract_type, seat) not found",
            )
        )
        return results

    if "hand_value" not in df.columns:
        results.append(
            _make_check(
                "seat_balance",
                "fairness",
                "SKIP",
                threshold=f"ANOVA p > {alpha}",
                observed="missing hand_value",
                detail="hand_value column not found",
            )
        )
        return results

    for ct in sorted(df["contract_type"].unique()):
        ct_df = df[df["contract_type"] == ct]
        groups = [
            g["hand_value"].values for _, g in ct_df.groupby("seat") if len(g) > 0
        ]
        n_per_cell = min(len(g) for g in groups) if groups else 0

        if len(groups) < 2 or n_per_cell < _MIN_STAT_N:
            results.append(
                _make_check(
                    "seat_balance",
                    "fairness",
                    "SKIP",
                    threshold=f"ANOVA p > {alpha}",
                    observed=f"N/cell={n_per_cell}",
                    detail=f"Insufficient data for {ct} (N/cell={n_per_cell}, need {_MIN_STAT_N})",
                    contract_type=ct,
                    n_samples=len(ct_df),
                )
            )
            continue

        f_stat, p_value = stats.f_oneway(*groups)
        status = "PASS" if p_value > alpha else "FAIL"
        results.append(
            _make_check(
                "seat_balance",
                "fairness",
                status,
                threshold=f"ANOVA p > {alpha}",
                observed=f"F={f_stat:.2f}, p={p_value:.4f}",
                detail=f"Seat balance for {ct}: F={f_stat:.2f}, p={p_value:.4f}",
                contract_type=ct,
                n_samples=len(ct_df),
            )
        )

    if not results:
        results.append(
            _make_check(
                "seat_balance",
                "fairness",
                "SKIP",
                threshold=f"ANOVA p > {alpha}",
                observed="no contract types",
                detail="No contract types found in data",
            )
        )

    return results


def check_contract_type_balance(
    df: pd.DataFrame,
    mode: str,
    *,
    expected_ratios: Optional[dict[str, float]] = None,
    alpha: float = DEFAULT_THRESHOLDS["contract_balance_alpha"],
) -> dict[str, Any]:
    """Chi-square goodness-of-fit on contract_type distribution."""
    if "contract_type" not in df.columns:
        return _make_check(
            "contract_type_balance",
            "fairness",
            "SKIP",
            threshold=f"chi2 p > {alpha}",
            observed="missing column",
            detail="contract_type column not found",
        )

    counts = df["contract_type"].value_counts()

    if len(counts) < 2:
        return _make_check(
            "contract_type_balance",
            "fairness",
            "SKIP",
            threshold=f"chi2 p > {alpha}",
            observed=f"{len(counts)} types",
            detail=f"Only {len(counts)} contract type(s) — need at least 2",
        )

    # Default 4:1:1 if not specified
    if expected_ratios is None:
        expected_ratios = {"suit": 4.0, "high": 1.0, "low": 1.0}

    # Build expected frequencies from ratios
    total = counts.sum()
    ratio_sum = sum(expected_ratios.get(ct, 1.0) for ct in counts.index)
    expected_freq = np.array(
        [total * expected_ratios.get(ct, 1.0) / ratio_sum for ct in counts.index]
    )
    observed_freq = counts.values.astype(float)

    if mode == "SMOKE" or total < _MIN_STAT_N:
        return _make_check(
            "contract_type_balance",
            "fairness",
            "SKIP",
            threshold=f"chi2 p > {alpha}",
            observed=f"N={total}",
            detail=f"Sample too small for chi-square test (N={total})",
            n_samples=int(total),
        )

    chi2, p_value = stats.chisquare(observed_freq, expected_freq)
    status = "PASS" if p_value > alpha else "FAIL"
    return _make_check(
        "contract_type_balance",
        "fairness",
        status,
        threshold=f"chi2 p > {alpha}",
        observed=f"chi2={chi2:.2f}, p={p_value:.4f}",
        detail=f"Contract type balance: chi2={chi2:.2f}, p={p_value:.4f}",
        n_samples=int(total),
    )


def check_trump_suit_invariance(
    df: pd.DataFrame,
    mode: str,
    *,
    max_spread: float = DEFAULT_THRESHOLDS["trump_invariance_spread"],
) -> dict[str, Any]:
    """Mean hand_value variance across trump suits (suit contracts only)."""
    if mode == "SMOKE":
        return _make_check(
            "trump_suit_invariance",
            "fairness",
            "SKIP",
            threshold=f"spread < {max_spread:.1%}",
            observed="SMOKE mode",
            detail="Skipped in SMOKE mode",
        )

    suit_df = df[df["contract_type"] == "suit"] if "contract_type" in df.columns else df

    if "trump_suit" not in suit_df.columns or "hand_value" not in suit_df.columns:
        return _make_check(
            "trump_suit_invariance",
            "fairness",
            "SKIP",
            threshold=f"spread < {max_spread:.1%}",
            observed="missing columns",
            detail="Required columns (trump_suit, hand_value) not found",
        )

    means = suit_df.groupby("trump_suit")["hand_value"].mean()
    if len(means) < 2:
        return _make_check(
            "trump_suit_invariance",
            "fairness",
            "SKIP",
            threshold=f"spread < {max_spread:.1%}",
            observed=f"{len(means)} suits",
            detail=f"Only {len(means)} trump suit(s) — need at least 2",
        )

    mean_val = means.mean()
    if mean_val == 0:
        spread = 0.0
    else:
        spread = (means.max() - means.min()) / mean_val

    status = "PASS" if spread < max_spread else "FAIL"
    return _make_check(
        "trump_suit_invariance",
        "fairness",
        status,
        threshold=f"spread < {max_spread:.1%}",
        observed=f"{spread:.4f} ({spread:.2%})",
        detail=f"Trump suit invariance: relative spread = {spread:.4f}",
        n_samples=len(suit_df),
    )


def check_team_balance(
    df: pd.DataFrame,
    mode: str,
    *,
    max_delta: float = DEFAULT_THRESHOLDS["team_balance_delta"],
) -> dict[str, Any]:
    """Mean trick delta from 5.0 in self-play."""
    if mode == "SMOKE":
        return _make_check(
            "team_balance",
            "fairness",
            "SKIP",
            threshold=f"|delta| < {max_delta}",
            observed="SMOKE mode",
            detail="Skipped in SMOKE mode",
        )

    if "tricks_won" not in df.columns:
        return _make_check(
            "team_balance",
            "fairness",
            "SKIP",
            threshold=f"|delta| < {max_delta}",
            observed="missing column",
            detail="tricks_won column not found",
        )

    mean_tricks = df["tricks_won"].mean()
    delta = abs(mean_tricks - 5.0)
    status = "PASS" if delta < max_delta else "FAIL"
    return _make_check(
        "team_balance",
        "fairness",
        status,
        threshold=f"|delta| < {max_delta}",
        observed=f"mean={mean_tricks:.3f}, delta={delta:.3f}",
        detail=f"Team balance: mean tricks = {mean_tricks:.3f}, |delta from 5.0| = {delta:.3f}",
        n_samples=len(df),
    )


def check_prediction_correlation(
    df: pd.DataFrame,
    predictions: np.ndarray | None,
    mode: str,
    *,
    min_r: float = DEFAULT_THRESHOLDS["min_correlation"],
) -> list[dict[str, Any]]:
    """Pearson r between predictions and actual tricks_won, per contract_type."""
    results = []

    if predictions is None or mode == "SMOKE":
        results.append(
            _make_check(
                "prediction_correlation",
                "directional_sanity",
                "SKIP" if mode == "SMOKE" else "SKIP",
                threshold=f"r > {min_r}",
                observed="no predictions" if predictions is None else "SMOKE mode",
                detail="Skipped: "
                + ("no predictions provided" if predictions is None else "SMOKE mode"),
            )
        )
        return results

    if "tricks_won" not in df.columns or "contract_type" not in df.columns:
        results.append(
            _make_check(
                "prediction_correlation",
                "directional_sanity",
                "SKIP",
                threshold=f"r > {min_r}",
                observed="missing columns",
                detail="Required columns not found",
            )
        )
        return results

    df = df.copy()
    df["_pred"] = predictions

    for ct in sorted(df["contract_type"].unique()):
        ct_df = df[df["contract_type"] == ct]
        if len(ct_df) < _MIN_STAT_N:
            results.append(
                _make_check(
                    "prediction_correlation",
                    "directional_sanity",
                    "SKIP",
                    threshold=f"r > {min_r}",
                    observed=f"N={len(ct_df)}",
                    detail=f"Too few samples for {ct} (N={len(ct_df)})",
                    contract_type=ct,
                    n_samples=len(ct_df),
                )
            )
            continue

        r, _ = stats.pearsonr(ct_df["_pred"], ct_df["tricks_won"])
        status = "PASS" if r > min_r else "FAIL"
        results.append(
            _make_check(
                "prediction_correlation",
                "directional_sanity",
                status,
                threshold=f"r > {min_r}",
                observed=f"r={r:.4f}",
                detail=f"Prediction correlation for {ct}: r={r:.4f}",
                contract_type=ct,
                n_samples=len(ct_df),
            )
        )

    if not results:
        results.append(
            _make_check(
                "prediction_correlation",
                "directional_sanity",
                "SKIP",
                threshold=f"r > {min_r}",
                observed="no data",
                detail="No contract types found",
            )
        )

    return results


def check_r_squared_floor(
    df: pd.DataFrame,
    predictions: np.ndarray | None,
    mode: str,
    *,
    min_r2: float = DEFAULT_THRESHOLDS["min_r_squared"],
) -> list[dict[str, Any]]:
    """Per-contract R-squared on val split."""
    results = []

    if predictions is None or mode == "SMOKE":
        results.append(
            _make_check(
                "r_squared_floor",
                "directional_sanity",
                "SKIP",
                threshold=f"R2 > {min_r2}",
                observed="no predictions" if predictions is None else "SMOKE mode",
                detail="Skipped: "
                + ("no predictions" if predictions is None else "SMOKE mode"),
            )
        )
        return results

    if "tricks_won" not in df.columns or "contract_type" not in df.columns:
        results.append(
            _make_check(
                "r_squared_floor",
                "directional_sanity",
                "SKIP",
                threshold=f"R2 > {min_r2}",
                observed="missing columns",
                detail="Required columns not found",
            )
        )
        return results

    df = df.copy()
    df["_pred"] = predictions

    for ct in sorted(df["contract_type"].unique()):
        ct_df = df[df["contract_type"] == ct]
        if len(ct_df) < _MIN_STAT_N:
            results.append(
                _make_check(
                    "r_squared_floor",
                    "directional_sanity",
                    "SKIP",
                    threshold=f"R2 > {min_r2}",
                    observed=f"N={len(ct_df)}",
                    detail=f"Too few samples for {ct}",
                    contract_type=ct,
                    n_samples=len(ct_df),
                )
            )
            continue

        ss_res = ((ct_df["tricks_won"] - ct_df["_pred"]) ** 2).sum()
        ss_tot = ((ct_df["tricks_won"] - ct_df["tricks_won"].mean()) ** 2).sum()
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        status = "PASS" if r2 > min_r2 else "FAIL"
        results.append(
            _make_check(
                "r_squared_floor",
                "directional_sanity",
                status,
                threshold=f"R2 > {min_r2}",
                observed=f"R2={r2:.4f}",
                detail=f"R-squared for {ct}: {r2:.4f}",
                contract_type=ct,
                n_samples=len(ct_df),
            )
        )

    if not results:
        results.append(
            _make_check(
                "r_squared_floor",
                "directional_sanity",
                "SKIP",
                threshold=f"R2 > {min_r2}",
                observed="no data",
                detail="No contract types found",
            )
        )

    return results


def check_mae_ceiling(
    df: pd.DataFrame,
    predictions: np.ndarray | None,
    mode: str,
    *,
    max_mae: float = DEFAULT_THRESHOLDS["max_mae"],
) -> list[dict[str, Any]]:
    """Per-contract MAE on val split."""
    results = []

    if predictions is None or mode == "SMOKE":
        results.append(
            _make_check(
                "mae_ceiling",
                "directional_sanity",
                "SKIP",
                threshold=f"MAE < {max_mae}",
                observed="no predictions" if predictions is None else "SMOKE mode",
                detail="Skipped: "
                + ("no predictions" if predictions is None else "SMOKE mode"),
            )
        )
        return results

    if "tricks_won" not in df.columns or "contract_type" not in df.columns:
        results.append(
            _make_check(
                "mae_ceiling",
                "directional_sanity",
                "SKIP",
                threshold=f"MAE < {max_mae}",
                observed="missing columns",
                detail="Required columns not found",
            )
        )
        return results

    df = df.copy()
    df["_pred"] = predictions

    for ct in sorted(df["contract_type"].unique()):
        ct_df = df[df["contract_type"] == ct]
        if len(ct_df) < _MIN_STAT_N:
            results.append(
                _make_check(
                    "mae_ceiling",
                    "directional_sanity",
                    "SKIP",
                    threshold=f"MAE < {max_mae}",
                    observed=f"N={len(ct_df)}",
                    detail=f"Too few samples for {ct}",
                    contract_type=ct,
                    n_samples=len(ct_df),
                )
            )
            continue

        mae = np.abs(ct_df["tricks_won"] - ct_df["_pred"]).mean()
        status = "PASS" if mae < max_mae else "FAIL"
        results.append(
            _make_check(
                "mae_ceiling",
                "directional_sanity",
                status,
                threshold=f"MAE < {max_mae}",
                observed=f"MAE={mae:.4f}",
                detail=f"MAE for {ct}: {mae:.4f}",
                contract_type=ct,
                n_samples=len(ct_df),
            )
        )

    if not results:
        results.append(
            _make_check(
                "mae_ceiling",
                "directional_sanity",
                "SKIP",
                threshold=f"MAE < {max_mae}",
                observed="no data",
                detail="No contract types found",
            )
        )

    return results


# ──────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────


def compute_semantic_gate(
    df: pd.DataFrame,
    mode: str,
    active_split: str,
    seed: int,
    *,
    feature_cols: Optional[list[str]] = None,
    manifest: Any = None,
    predictions: Optional[np.ndarray] = None,
    model_artifact_path: Optional[str] = None,
    model_artifact_sha256: Optional[str] = None,
    custom_thresholds: Optional[dict[str, float]] = None,
    contract_type_ratios: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """Run all semantic gate checks and return the gate artifact dict.

    Parameters
    ----------
    df : pd.DataFrame
        Evaluation data (val or test split).
    mode : str
        One of ``"SMOKE"``, ``"QUICK"``, ``"FULL"``.
    active_split : str
        Which split this evaluation is running on (``"val"`` or ``"test"``).
    seed : int
        RNG seed for reproducibility.
    feature_cols : list[str], optional
        Feature column names in *df*.  Required for feature_count and
        no_nan_features checks.
    manifest : SplitManifest, optional
        Split manifest for integrity verification.
    predictions : np.ndarray, optional
        Model predictions aligned with *df*.  Required for directional
        sanity checks.
    model_artifact_path : str, optional
        Path to the model artifact (for metadata).
    model_artifact_sha256 : str, optional
        SHA-256 of the model artifact (for metadata).
    custom_thresholds : dict[str, float], optional
        Per-rung threshold overrides.  Keys match ``DEFAULT_THRESHOLDS``.
    contract_type_ratios : dict[str, float], optional
        Expected contract_type ratios for the balance check.
        Defaults to ``{"suit": 4, "high": 1, "low": 1}`` (standard
        6-scenario config).  Override when using non-standard configs.

    Returns
    -------
    dict
        Semantic gate artifact conforming to schema v1.
    """
    thresholds = {**DEFAULT_THRESHOLDS}
    if custom_thresholds:
        thresholds.update(custom_thresholds)

    checks: list[dict[str, Any]] = []

    # ── Tier 1: Framework Health ──

    if feature_cols is not None:
        checks.append(check_feature_count(df, feature_cols))
        checks.append(check_no_nan_features(df, feature_cols))

    checks.append(check_tricks_range(df))
    checks.append(check_min_sample_size(df, mode))
    checks.append(check_val_split_integrity(df, manifest, seed))

    # ── Tier 2: Model Quality Floor ──

    checks.extend(
        check_seat_balance(
            df,
            mode,
            alpha=thresholds["seat_balance_alpha"],
        )
    )

    checks.append(
        check_contract_type_balance(
            df,
            mode,
            expected_ratios=contract_type_ratios,
            alpha=thresholds["contract_balance_alpha"],
        )
    )

    checks.append(
        check_trump_suit_invariance(
            df,
            mode,
            max_spread=thresholds["trump_invariance_spread"],
        )
    )

    checks.append(
        check_team_balance(
            df,
            mode,
            max_delta=thresholds["team_balance_delta"],
        )
    )

    checks.extend(
        check_prediction_correlation(
            df,
            predictions,
            mode,
            min_r=thresholds["min_correlation"],
        )
    )

    checks.extend(
        check_r_squared_floor(
            df,
            predictions,
            mode,
            min_r2=thresholds["min_r_squared"],
        )
    )

    checks.extend(
        check_mae_ceiling(
            df,
            predictions,
            mode,
            max_mae=thresholds["max_mae"],
        )
    )

    # ── Aggregate ──

    passed = sum(1 for c in checks if c["status"] == "PASS")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    warned = sum(1 for c in checks if c["status"] == "WARN")

    gate_status = "PASS" if failed == 0 else "FAIL"
    n_hands = df["hand_id"].nunique() if "hand_id" in df.columns else len(df)

    gate: dict[str, Any] = {
        "schema_version": SEMANTIC_GATE_SCHEMA_VERSION,
        "gate_status": gate_status,
        "created_at_utc": _utc_now_iso(),
        "active_split": active_split,
        "mode": mode,
        "seed": seed,
        "total_hands": n_hands,
        "total_checks": len(checks),
        "passed_checks": passed,
        "failed_checks": failed,
        "warned_checks": warned,
        "checks": checks,
    }

    if model_artifact_path is not None:
        gate["model_artifact_path"] = model_artifact_path
    if model_artifact_sha256 is not None:
        gate["model_artifact_sha256"] = model_artifact_sha256
    if manifest is not None:
        gate["split_manifest_sha256"] = manifest.partition_hashes.get(
            active_split, "unknown"
        )

    return gate


def emit_semantic_gate(
    gate: dict[str, Any],
    output_dir: str | Path,
    *,
    active_split: Optional[str] = None,
) -> Path:
    """Write semantic gate artifact to disk.

    File naming convention:
    - ``semantic_gate_val.json`` for val split
    - ``semantic_gate_test.json`` for test split

    Parameters
    ----------
    gate : dict
        Gate artifact from ``compute_semantic_gate()``.
    output_dir : str or Path
        Directory to write the artifact.
    active_split : str, optional
        Override the split suffix.  Defaults to ``gate["active_split"]``.

    Returns
    -------
    Path
        Path to the written file.
    """
    split = active_split or gate.get("active_split", "val")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"semantic_gate_{split}.json"
    file_path.write_text(json.dumps(gate, indent=2))
    logger.info("Wrote semantic gate: %s (status=%s)", file_path, gate["gate_status"])
    return file_path

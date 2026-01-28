"""Statistical utilities for bidless diagnostics.

Provides statistical tests and computations for analyzing
bidless simulation datasets, with a focus on CI-friendly
bounded checks rather than p-value based tests.
"""

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class BatchComparisonResult:
    """Result of comparing first vs last batch."""

    first_mean: float
    last_mean: float
    difference: float
    percent_change: float
    mannwhitney_stat: Optional[float]
    mannwhitney_pvalue: Optional[float]
    is_significant: bool  # p < 0.05
    interpretation: str


def compare_first_last_batch(
    df: pd.DataFrame,
    column: str = "feat_hand_value",
    batch_fraction: float = 0.1,
) -> BatchComparisonResult:
    """Compare first and last batch of data for drift detection.

    Uses Mann-Whitney U test to compare distributions. Note that
    this test can be flaky in CI; use bounded tolerance checks
    for hard gates.

    Args:
        df: DataFrame sorted by hand_id (or row order)
        column: Column to compare
        batch_fraction: Fraction of data for each batch (default 10%)

    Returns:
        BatchComparisonResult with statistics and interpretation
    """
    if column not in df.columns:
        return BatchComparisonResult(
            first_mean=0, last_mean=0, difference=0, percent_change=0,
            mannwhitney_stat=None, mannwhitney_pvalue=None,
            is_significant=False,
            interpretation=f"Column '{column}' not found",
        )

    n = len(df)
    batch_size = max(1, int(n * batch_fraction))

    first_batch = df[column].iloc[:batch_size].values
    last_batch = df[column].iloc[-batch_size:].values

    first_mean = float(np.mean(first_batch))
    last_mean = float(np.mean(last_batch))
    difference = last_mean - first_mean
    percent_change = (difference / first_mean * 100) if first_mean != 0 else 0

    # Mann-Whitney U test
    try:
        stat, pvalue = stats.mannwhitneyu(first_batch, last_batch, alternative="two-sided")
        is_significant = pvalue < 0.05
    except ValueError:
        stat, pvalue = None, None
        is_significant = False

    # Interpretation
    if abs(percent_change) < 1:
        interpretation = "No meaningful drift detected"
    elif is_significant:
        direction = "increased" if difference > 0 else "decreased"
        interpretation = f"Significant drift: {column} {direction} by {abs(percent_change):.1f}%"
    else:
        interpretation = f"Small drift ({percent_change:.1f}%) but not statistically significant"

    return BatchComparisonResult(
        first_mean=first_mean,
        last_mean=last_mean,
        difference=difference,
        percent_change=percent_change,
        mannwhitney_stat=stat,
        mannwhitney_pvalue=pvalue,
        is_significant=is_significant,
        interpretation=interpretation,
    )


@dataclass
class SeatBalanceResult:
    """Result of seat balance analysis."""

    seat_means: Dict[int, float]
    global_mean: float
    max_deviation: float
    max_deviation_seat: int
    is_balanced: bool  # Within tolerance
    tolerance_used: float
    interpretation: str


def compute_seat_balance(
    df: pd.DataFrame,
    column: str = "feat_hand_value",
    tolerance_fraction: float = 0.05,
) -> SeatBalanceResult:
    """Compute seat balance statistics.

    Uses bounded tolerance check (not statistical test) for CI stability.

    Args:
        df: DataFrame with 'seat' column
        column: Column to check balance for
        tolerance_fraction: Max allowed deviation as fraction of mean

    Returns:
        SeatBalanceResult with balance statistics
    """
    if column not in df.columns or "seat" not in df.columns:
        return SeatBalanceResult(
            seat_means={}, global_mean=0, max_deviation=0, max_deviation_seat=0,
            is_balanced=False, tolerance_used=0,
            interpretation="Required columns not found",
        )

    seat_means = df.groupby("seat")[column].mean().to_dict()
    global_mean = df[column].mean()

    # Compute deviations
    deviations = {seat: abs(mean - global_mean) for seat, mean in seat_means.items()}
    max_seat = max(deviations, key=deviations.get)
    max_deviation = deviations[max_seat]

    # Compute tolerance
    tolerance = tolerance_fraction * abs(global_mean) if global_mean != 0 else 0.1
    is_balanced = max_deviation <= tolerance

    if is_balanced:
        interpretation = f"All seats balanced within {tolerance_fraction*100:.0f}% tolerance"
    else:
        interpretation = (
            f"Seat {max_seat} deviates by {max_deviation:.3f} from global mean "
            f"(tolerance: {tolerance:.3f})"
        )

    return SeatBalanceResult(
        seat_means=seat_means,
        global_mean=global_mean,
        max_deviation=max_deviation,
        max_deviation_seat=max_seat,
        is_balanced=is_balanced,
        tolerance_used=tolerance,
        interpretation=interpretation,
    )


def compute_feature_stats(
    df: pd.DataFrame,
    features: Optional[list] = None,
) -> pd.DataFrame:
    """Compute summary statistics for feature columns.

    Args:
        df: DataFrame with feat_* columns
        features: List of features to include (without feat_ prefix).
                  If None, includes all feat_* columns.

    Returns:
        DataFrame with columns: feature, count, mean, std, min, max, median
    """
    feat_cols = [c for c in df.columns if c.startswith("feat_")]

    if features:
        feat_cols = [f"feat_{f}" for f in features if f"feat_{f}" in feat_cols]

    if not feat_cols:
        return pd.DataFrame()

    stats_rows = []
    for col in feat_cols:
        if df[col].dtype not in [np.float64, np.int64, np.float32, np.int32]:
            continue

        values = df[col].dropna()
        stats_rows.append({
            "feature": col.replace("feat_", ""),
            "count": len(values),
            "mean": values.mean(),
            "std": values.std(),
            "min": values.min(),
            "max": values.max(),
            "median": values.median(),
        })

    return pd.DataFrame(stats_rows)


def compute_correlation_with_label(
    df: pd.DataFrame,
    label: str = "feat_hand_value",
) -> pd.DataFrame:
    """Compute Pearson correlation of all features with label.

    Args:
        df: DataFrame with feat_* columns
        label: Label column name

    Returns:
        DataFrame sorted by absolute correlation, columns: feature, correlation
    """
    if label not in df.columns:
        return pd.DataFrame()

    feat_cols = [c for c in df.columns if c.startswith("feat_") and c != label]
    numeric_cols = [c for c in feat_cols if df[c].dtype in [np.float64, np.int64]]

    if not numeric_cols:
        return pd.DataFrame()

    correlations = []
    for col in numeric_cols:
        corr = df[col].corr(df[label])
        correlations.append({
            "feature": col.replace("feat_", ""),
            "correlation": corr,
            "abs_correlation": abs(corr),
        })

    result = pd.DataFrame(correlations)
    return result.sort_values("abs_correlation", ascending=False).drop("abs_correlation", axis=1)

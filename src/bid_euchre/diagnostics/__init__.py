"""Diagnostic utilities for bidless simulation analysis.

This package provides importable helpers for:
- Loading bidless datasets (Parquet/JSONL)
- Computing health scorecards
- Generating diagnostic charts
- Running statistical tests

The design philosophy is: logic lives here, notebooks are thin orchestration.
"""

from .charts import (
    plot_feature_correlation,
    plot_feature_distributions,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat,
    plot_rolling_mean,
)
from .health_checks import compute_health_scorecard, display_scorecard
from .loaders import load_bidless_dataset, load_meta
from .stats import compare_first_last_batch, compute_seat_balance

__all__ = [
    # Loaders
    "load_bidless_dataset",
    "load_meta",
    # Health checks
    "compute_health_scorecard",
    "display_scorecard",
    # Charts
    "plot_hand_value_by_seat",
    "plot_hand_value_by_contract",
    "plot_feature_distributions",
    "plot_feature_correlation",
    "plot_rolling_mean",
    # Stats
    "compare_first_last_batch",
    "compute_seat_balance",
]

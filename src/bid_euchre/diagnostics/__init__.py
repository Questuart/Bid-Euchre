"""Diagnostic utilities for bidless simulation analysis.

This package provides importable helpers for:
- Loading bidless datasets (Parquet/JSONL)
- Computing health scorecards
- Generating diagnostic charts
- Running statistical tests
- Strategy comparison visualizations

The design philosophy is: logic lives here, notebooks are thin orchestration.
"""

from .charts import (
    plot_ccdf,
    plot_cdf,
    plot_feature_correlation,
    plot_feature_distributions,
    plot_feature_heatmap_by_suit,
    plot_feature_outcome_correlation,
    plot_feature_vs_outcome,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat,
    plot_hand_value_by_trump_suit,
    plot_outcome_by_trump_suit,
    plot_outcome_distributions,
    plot_rolling_mean,
    plot_suit_variance_summary,
)
from .health_checks import compute_health_scorecard, display_issues, display_scorecard
from .loaders import load_bidless_dataset, load_meta
from .notebook_data import load_or_generate_features, load_or_generate_outcomes
from .stats import compare_first_last_batch, compute_seat_balance
from .strategy_charts import (
    ARCHETYPE_COLORS,
    plot_matchup_summary,
    plot_roster_calibration,
    plot_roster_conversion,
    plot_roster_efficiency,
    plot_self_play_control,
    plot_strategy_delta_bars,
    plot_tricks_distribution_comparison,
    plot_win_rate_heatmap,
)
from .validators import SampleSizeValidator, SampleSizeWarning

__all__ = [
    # Loaders
    "load_bidless_dataset",
    "load_meta",
    # Notebook data generation
    "load_or_generate_outcomes",
    "load_or_generate_features",
    # Health checks
    "compute_health_scorecard",
    "display_scorecard",
    "display_issues",
    # Charts - Feature Analysis
    "plot_hand_value_by_seat",
    "plot_hand_value_by_contract",
    "plot_feature_distributions",
    "plot_feature_correlation",
    "plot_rolling_mean",
    # Charts - Distribution Analysis
    "plot_cdf",
    "plot_ccdf",
    # Charts - Outcome Evaluation
    "plot_feature_vs_outcome",
    "plot_outcome_distributions",
    "plot_feature_outcome_correlation",
    # Charts - Trump Suit Analysis
    "plot_hand_value_by_trump_suit",
    "plot_outcome_by_trump_suit",
    "plot_feature_heatmap_by_suit",
    "plot_suit_variance_summary",
    # Charts - Strategy Comparison
    "plot_win_rate_heatmap",
    "plot_tricks_distribution_comparison",
    "plot_strategy_delta_bars",
    "plot_self_play_control",
    "plot_matchup_summary",
    # Charts - Roster Meta-Analysis
    "ARCHETYPE_COLORS",
    "plot_roster_calibration",
    "plot_roster_efficiency",
    "plot_roster_conversion",
    # Stats
    "compare_first_last_batch",
    "compute_seat_balance",
    # Validators
    "SampleSizeValidator",
    "SampleSizeWarning",
]

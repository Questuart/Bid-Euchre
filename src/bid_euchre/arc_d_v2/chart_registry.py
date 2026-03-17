"""Chart registry for Arc D v2 rung reports.

Defines the canonical 22-chart numbered registry. Chart numbers are stable
identifiers — they never change based on availability. Used by report.py
for numbered headings and by manifest.py for chart inventory.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChartEntry:
    """A single chart in the registry."""

    number: int
    filename: str
    title: str
    required: bool
    source: str


CHART_REGISTRY: tuple[ChartEntry, ...] = (
    ChartEntry(
        1,
        "dashboard_competitive.png",
        "Competitive Dashboard",
        True,
        "canonical tables",
    ),
    ChartEntry(
        2,
        "dashboard_health.png",
        "Health Dashboard",
        True,
        "canonical tables + chart_data",
    ),
    ChartEntry(
        3,
        "dashboard_model_eval.png",
        "Model Evaluation Dashboard",
        True,
        "canonical tables + chart_data",
    ),
    ChartEntry(
        4,
        "comparator_ranking_bars.png",
        "Comparator Ranking Bars",
        True,
        "tables/comparator_rankings.csv",
    ),
    ChartEntry(
        5,
        "tail_risk_panel.png",
        "Tail Risk Panel",
        True,
        "tables/comparator_rankings.csv",
    ),
    ChartEntry(
        6,
        "delta_bars_by_contract.png",
        "H2H Delta by Contract",
        True,
        "tables/h2h_delta_matrix.csv",
    ),
    ChartEntry(
        7, "h2h_heatmap.png", "H2H Heatmap", True, "tables/h2h_delta_matrix.csv"
    ),
    ChartEntry(
        8,
        "h2h_ranking_scatter.png",
        "H2H Ranking Scatter",
        False,
        "tables/comparator_rankings.csv + h2h_tier_summary.csv",
    ),
    ChartEntry(
        9,
        "outcome_distributions.png",
        "Outcome Distributions",
        False,
        "chart_data/outcome_distributions.csv",
    ),
    ChartEntry(
        10, "seat_balance.png", "Seat Balance", False, "chart_data/seat_balance.csv"
    ),
    ChartEntry(
        11, "contract_mix_bars.png", "Contract Mix", True, "chart_data/contract_mix.csv"
    ),
    ChartEntry(
        12,
        "bid_behavior_panel.png",
        "Bid and Make Rates",
        True,
        "tables/behavior_summary.csv",
    ),
    ChartEntry(
        13,
        "bid_level_distribution.png",
        "Bid Level Distribution",
        False,
        "chart_data/bid_levels.csv",
    ),
    ChartEntry(
        14,
        "r2_by_contract.png",
        "R-squared by Contract",
        True,
        "tables/model_performance.csv",
    ),
    ChartEntry(
        15,
        "mae_by_contract.png",
        "MAE by Contract",
        True,
        "tables/model_performance.csv",
    ),
    ChartEntry(
        16,
        "pred_vs_actual.png",
        "Predicted vs Actual",
        False,
        "chart_data/predictions.csv",
    ),
    ChartEntry(
        17,
        "residual_distribution.png",
        "Residual Distribution",
        False,
        "chart_data/residuals.csv",
    ),
    ChartEntry(
        18,
        "calibration_curve.png",
        "Calibration Curve",
        False,
        "chart_data/calibration_bins.csv",
    ),
    ChartEntry(
        19,
        "selection_path.png",
        "Selection Path",
        False,
        "chart_data/selection_paths.csv",
    ),
    ChartEntry(
        20,
        "feature_importance.png",
        "Feature Importance",
        False,
        "chart_data/selection_paths.csv",
    ),
    ChartEntry(
        21,
        "decision_agreement.png",
        "Decision Agreement",
        False,
        "chart_data/decision_comparison.csv",
    ),
    ChartEntry(
        22,
        "disagreement_outcomes.png",
        "Disagreement Outcomes",
        False,
        "chart_data/disagreement_outcomes.csv",
    ),
)


def get_chart_by_number(n: int) -> ChartEntry | None:
    """Look up a chart entry by its stable number."""
    for entry in CHART_REGISTRY:
        if entry.number == n:
            return entry
    return None


def get_chart_by_filename(filename: str) -> ChartEntry | None:
    """Look up a chart entry by its PNG filename."""
    for entry in CHART_REGISTRY:
        if entry.filename == filename:
            return entry
    return None

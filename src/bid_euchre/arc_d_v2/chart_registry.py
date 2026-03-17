"""Chart registry for Arc D v2 rung reports.

Defines the canonical 23-chart numbered registry. Chart numbers are stable
identifiers — they never change based on availability. Used by report.py
for numbered headings and by manifest.py for chart inventory.

Layout: Charts 1-3 (dashboards) are at the top level of charts/.
Charts 4-23 (standalone) live under charts/full_chart_suite/.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shorthand for the standalone chart subdirectory.
_FCS = "full_chart_suite"


@dataclass(frozen=True)
class ChartEntry:
    """A single chart in the registry."""

    number: int
    filename: str  # Bare name (stable identifier, no directory prefix)
    title: str
    required: bool
    source: str
    subdir: str = ""  # "" for dashboards, "full_chart_suite" for standalone

    @property
    def path(self) -> str:
        """Full relative path including subdirectory prefix."""
        return f"{self.subdir}/{self.filename}" if self.subdir else self.filename


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
        subdir=_FCS,
    ),
    ChartEntry(
        5,
        "tail_risk_panel.png",
        "Tail Risk Panel",
        True,
        "tables/comparator_rankings.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        6,
        "delta_bars_by_contract.png",
        "H2H Delta by Contract",
        True,
        "tables/h2h_delta_matrix.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        7,
        "h2h_heatmap.png",
        "H2H Heatmap",
        True,
        "tables/h2h_delta_matrix.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        8,
        "h2h_ranking_scatter.png",
        "H2H Ranking Scatter",
        False,
        "tables/comparator_rankings.csv + h2h_tier_summary.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        9,
        "outcome_distributions.png",
        "Outcome Distributions",
        False,
        "chart_data/outcome_distributions.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        10,
        "seat_balance.png",
        "Seat Balance",
        False,
        "chart_data/seat_balance.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        11,
        "contract_mix_bars.png",
        "Contract Mix",
        True,
        "chart_data/contract_mix.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        12,
        "bid_behavior_panel.png",
        "Bid and Make Rates",
        True,
        "tables/behavior_summary.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        13,
        "bid_level_distribution.png",
        "Bid Level Distribution",
        False,
        "chart_data/bid_levels.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        14,
        "r2_by_contract.png",
        "R-squared by Contract",
        True,
        "tables/model_performance.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        15,
        "mae_by_contract.png",
        "MAE by Contract",
        True,
        "tables/model_performance.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        16,
        "pred_vs_actual.png",
        "Predicted vs Actual",
        False,
        "chart_data/predictions.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        17,
        "residual_distribution.png",
        "Residual Distribution",
        False,
        "chart_data/residuals.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        18,
        "calibration_curve.png",
        "Calibration Curve",
        False,
        "chart_data/calibration_bins.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        19,
        "selection_path.png",
        "Selection Path",
        False,
        "chart_data/selection_paths.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        20,
        "feature_importance.png",
        "Feature Importance",
        False,
        "chart_data/selection_paths.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        21,
        "decision_agreement.png",
        "Decision Agreement",
        False,
        "chart_data/decision_comparison.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        22,
        "disagreement_outcomes.png",
        "Disagreement Outcomes",
        False,
        "chart_data/disagreement_outcomes.csv",
        subdir=_FCS,
    ),
    ChartEntry(
        23,
        "h2h_intelligence_faceted.png",
        "Intelligence-Faceted H2H",
        False,
        "tables/h2h_tier_summary.csv",
        subdir=_FCS,
    ),
)


def get_chart_by_number(n: int) -> ChartEntry | None:
    """Look up a chart entry by its stable number."""
    for entry in CHART_REGISTRY:
        if entry.number == n:
            return entry
    return None


def get_chart_by_filename(filename: str) -> ChartEntry | None:
    """Look up a chart entry by its bare PNG filename."""
    for entry in CHART_REGISTRY:
        if entry.filename == filename:
            return entry
    return None

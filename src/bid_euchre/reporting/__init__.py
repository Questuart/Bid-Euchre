"""
Bid Euchre Reporting Framework

Provides shared utilities for generating consistent, high-quality reports:
- style: Visual styling constants (colors, labels, fonts)
- paths: Report path management (archive + latest pattern)
- metrics: Core metric calculations (Win/Push/Loss rates with CI)
"""

from .metrics import (
    OutcomeStats,
    compute_outcome_stats,
    outcome_rates_with_ci,
)
from .paths import (
    ReportPaths,
    copy_to_latest,
    dashboard_paths,
    ensure_dir,
    get_report_paths,
    write_latest_pointer,
)
from .style import (
    CONTRACT_COLORS,
    CONTRACT_LABELS,
    OUTCOME_COLORS,
    OUTCOME_LABELS,
    STRATEGY_COLORS,
    STRATEGY_NAMES,
    apply_report_style,
    format_ci,
    format_pct,
)

__all__ = [
    # Style
    "CONTRACT_LABELS",
    "CONTRACT_COLORS",
    "STRATEGY_NAMES",
    "STRATEGY_COLORS",
    "OUTCOME_COLORS",
    "OUTCOME_LABELS",
    "apply_report_style",
    "format_pct",
    "format_ci",
    # Paths
    "ReportPaths",
    "get_report_paths",
    "write_latest_pointer",
    "copy_to_latest",
    "dashboard_paths",
    "ensure_dir",
    # Metrics
    "OutcomeStats",
    "compute_outcome_stats",
    "outcome_rates_with_ci",
]

"""
Statistical analysis utilities for Bid Euchre experiments.
"""

from .stats import (
    wilson_ci,
    paired_t_ci,
    compute_effect_size,
    bootstrap_ci,
    mean_with_ci,
)
from .paired import (
    load_paired_data,
    compute_paired_deltas,
    paired_comparison_summary,
)

__all__ = [
    "wilson_ci",
    "paired_t_ci",
    "compute_effect_size",
    "bootstrap_ci",
    "mean_with_ci",
    "load_paired_data",
    "compute_paired_deltas",
    "paired_comparison_summary",
]


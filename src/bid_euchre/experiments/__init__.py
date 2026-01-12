"""
Bid Euchre Experiment Framework

This package provides tools for configuring and running experiments.
"""

from .config import (
    BiddingPolicyConfig,
    ExperimentConfig,
    create_experiment,
    load_config,
)
from .meta import get_git_sha, sha256_file, utc_now_iso

__all__ = [
    "BiddingPolicyConfig",
    "ExperimentConfig",
    "load_config",
    "create_experiment",
    "utc_now_iso",
    "sha256_file",
    "get_git_sha",
]

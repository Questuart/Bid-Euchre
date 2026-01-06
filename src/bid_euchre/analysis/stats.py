"""
Statistical utility functions for analysis and reporting.
"""

from typing import List, Tuple

import numpy as np
from scipy import stats as scipy_stats


def wilson_ci(successes: int, trials: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Wilson score interval for binomial proportions.

    Better than normal approximation for proportions, especially with small p or small n.

    Args:
        successes: Number of successes
        trials: Number of trials
        confidence: Confidence level (default: 0.95)

    Returns:
        (proportion, lower_bound, upper_bound)

    Reference:
        Wilson, E. B. (1927). "Probable inference, the law of succession,
        and statistical inference". Journal of the American Statistical Association.
    """
    if trials == 0:
        return (0.0, 0.0, 0.0)

    p = successes / trials
    z = scipy_stats.norm.ppf((1 + confidence) / 2)

    denominator = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2)) / denominator

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return (p, lower, upper)


def paired_t_ci(differences: List[float], confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Paired t-test confidence interval for mean difference.

    Args:
        differences: List of paired differences (strategy - baseline)
        confidence: Confidence level (default: 0.95)

    Returns:
        (mean_diff, lower_bound, upper_bound)
    """
    if len(differences) == 0:
        return (0.0, 0.0, 0.0)

    differences = np.array(differences)
    mean_diff = np.mean(differences)

    if len(differences) < 2:
        return (mean_diff, mean_diff, mean_diff)

    stderr = scipy_stats.sem(differences)
    df = len(differences) - 1
    t_crit = scipy_stats.t.ppf((1 + confidence) / 2, df)
    margin = t_crit * stderr

    return (mean_diff, mean_diff - margin, mean_diff + margin)


def compute_effect_size(group1: List[float], group2: List[float]) -> float:
    """
    Compute Cohen's d effect size.

    Args:
        group1: First group values
        group2: Second group values

    Returns:
        Cohen's d (standardized mean difference)
    """
    if len(group1) < 2 or len(group2) < 2:
        return 0.0

    mean1 = np.mean(group1)
    mean2 = np.mean(group2)
    std1 = np.std(group1, ddof=1)
    std2 = np.std(group2, ddof=1)

    n1 = len(group1)
    n2 = len(group2)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))

    if pooled_std == 0:
        return 0.0

    return (mean1 - mean2) / pooled_std


def bootstrap_ci(
    data: List[float],
    statistic=np.mean,
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42
) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval for any statistic.

    Args:
        data: Data to bootstrap from
        statistic: Function to compute statistic (default: np.mean)
        confidence: Confidence level (default: 0.95)
        n_bootstrap: Number of bootstrap samples (default: 10000)
        seed: Random seed for reproducibility

    Returns:
        (statistic_value, lower_bound, upper_bound)
    """
    if len(data) < 2:
        val = statistic(data) if len(data) == 1 else 0.0
        return (val, val, val)

    data = np.array(data)
    rng = np.random.RandomState(seed)

    # Compute observed statistic
    observed = statistic(data)

    # Bootstrap resampling
    bootstrap_stats = []
    for _ in range(n_bootstrap):
        sample = rng.choice(data, size=len(data), replace=True)
        bootstrap_stats.append(statistic(sample))

    # Compute percentile interval
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_stats, alpha / 2 * 100)
    upper = np.percentile(bootstrap_stats, (1 - alpha / 2) * 100)

    return (observed, lower, upper)


def mean_with_ci(data: List[float], confidence: float = 0.95) -> Tuple[float, float, float]:
    """
    Compute mean with confidence interval using t-distribution.

    Args:
        data: Sample data
        confidence: Confidence level (default: 0.95)

    Returns:
        (mean, lower_bound, upper_bound)
    """
    if len(data) == 0:
        return (0.0, 0.0, 0.0)

    data = np.array(data)
    mean = np.mean(data)

    if len(data) < 2:
        return (mean, mean, mean)

    stderr = scipy_stats.sem(data)
    df = len(data) - 1
    t_crit = scipy_stats.t.ppf((1 + confidence) / 2, df)
    margin = t_crit * stderr

    return (mean, mean - margin, mean + margin)

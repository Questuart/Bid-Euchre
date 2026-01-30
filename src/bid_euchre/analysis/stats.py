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


def bootstrap_correlation_ci(
    x: List[float],
    y: List[float],
    method: str = 'pearson',
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42
) -> Tuple[float, float, float]:
    """
    Bootstrap confidence interval for correlation coefficient.

    Args:
        x: First variable
        y: Second variable
        method: 'pearson' or 'spearman' (default: 'pearson')
        confidence: Confidence level (default: 0.95)
        n_bootstrap: Number of bootstrap samples (default: 10000)
        seed: Random seed for reproducibility

    Returns:
        (correlation, lower_bound, upper_bound)
    """
    if len(x) != len(y) or len(x) < 2:
        return (0.0, 0.0, 0.0)

    x = np.array(x)
    y = np.array(y)
    rng = np.random.RandomState(seed)

    # Compute observed correlation
    if method == 'pearson':
        observed = scipy_stats.pearsonr(x, y)[0]
    elif method == 'spearman':
        observed = scipy_stats.spearmanr(x, y)[0]
    else:
        raise ValueError(f"Unknown method: {method}. Use 'pearson' or 'spearman'")

    # Bootstrap resampling
    bootstrap_corrs = []
    n = len(x)
    for _ in range(n_bootstrap):
        indices = rng.choice(n, size=n, replace=True)
        x_boot = x[indices]
        y_boot = y[indices]

        if method == 'pearson':
            corr = scipy_stats.pearsonr(x_boot, y_boot)[0]
        else:
            corr = scipy_stats.spearmanr(x_boot, y_boot)[0]

        if not np.isnan(corr):
            bootstrap_corrs.append(corr)

    # Compute percentile interval
    alpha = 1 - confidence
    lower = np.percentile(bootstrap_corrs, alpha / 2 * 100)
    upper = np.percentile(bootstrap_corrs, (1 - alpha / 2) * 100)

    return (observed, lower, upper)


def bootstrap_regression_ci(
    x: List[float],
    y: List[float],
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42
) -> dict:
    """
    Bootstrap confidence intervals for linear regression parameters.

    Args:
        x: Independent variable
        y: Dependent variable
        confidence: Confidence level (default: 0.95)
        n_bootstrap: Number of bootstrap samples (default: 10000)
        seed: Random seed for reproducibility

    Returns:
        Dictionary with keys 'slope', 'intercept', 'r_squared', each containing
        (estimate, lower_bound, upper_bound)
    """
    if len(x) != len(y) or len(x) < 2:
        return {
            'slope': (0.0, 0.0, 0.0),
            'intercept': (0.0, 0.0, 0.0),
            'r_squared': (0.0, 0.0, 0.0)
        }

    x = np.array(x)
    y = np.array(y)
    rng = np.random.RandomState(seed)

    # Compute observed statistics
    slope_obs, intercept_obs, r_obs, _, _ = scipy_stats.linregress(x, y)
    r_squared_obs = r_obs ** 2

    # Bootstrap resampling
    slopes = []
    intercepts = []
    r_squareds = []

    n = len(x)
    for _ in range(n_bootstrap):
        indices = rng.choice(n, size=n, replace=True)
        x_boot = x[indices]
        y_boot = y[indices]

        slope, intercept, r, _, _ = scipy_stats.linregress(x_boot, y_boot)
        slopes.append(slope)
        intercepts.append(intercept)
        r_squareds.append(r ** 2)

    # Compute percentile intervals
    alpha = 1 - confidence

    slope_lower = np.percentile(slopes, alpha / 2 * 100)
    slope_upper = np.percentile(slopes, (1 - alpha / 2) * 100)

    intercept_lower = np.percentile(intercepts, alpha / 2 * 100)
    intercept_upper = np.percentile(intercepts, (1 - alpha / 2) * 100)

    r2_lower = np.percentile(r_squareds, alpha / 2 * 100)
    r2_upper = np.percentile(r_squareds, (1 - alpha / 2) * 100)

    return {
        'slope': (slope_obs, slope_lower, slope_upper),
        'intercept': (intercept_obs, intercept_lower, intercept_upper),
        'r_squared': (r_squared_obs, r2_lower, r2_upper)
    }


def bootstrap_group_means_ci(
    groups: List[List[float]],
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42
) -> List[Tuple[float, float, float]]:
    """
    Bootstrap confidence intervals for means of multiple groups.

    Args:
        groups: List of groups (each group is a list of values)
        confidence: Confidence level (default: 0.95)
        n_bootstrap: Number of bootstrap samples (default: 10000)
        seed: Random seed for reproducibility

    Returns:
        List of (mean, lower_bound, upper_bound) for each group
    """
    results = []
    for group in groups:
        if len(group) < 1:
            results.append((0.0, 0.0, 0.0))
            continue

        mean, lower, upper = bootstrap_ci(
            group,
            statistic=np.mean,
            confidence=confidence,
            n_bootstrap=n_bootstrap,
            seed=seed
        )
        results.append((mean, lower, upper))

    return results


def effect_size_with_ci(
    group1: List[float],
    group2: List[float],
    confidence: float = 0.95,
    n_bootstrap: int = 10000,
    seed: int = 42
) -> Tuple[float, float, float]:
    """
    Cohen's d effect size with bootstrap confidence interval.

    Args:
        group1: First group values
        group2: Second group values
        confidence: Confidence level (default: 0.95)
        n_bootstrap: Number of bootstrap samples (default: 10000)
        seed: Random seed for reproducibility

    Returns:
        (cohen_d, lower_bound, upper_bound)
    """
    if len(group1) < 2 or len(group2) < 2:
        return (0.0, 0.0, 0.0)

    group1 = np.array(group1)
    group2 = np.array(group2)
    rng = np.random.RandomState(seed)

    # Observed effect size
    observed = compute_effect_size(group1, group2)

    # Bootstrap resampling
    effect_sizes = []
    n1 = len(group1)
    n2 = len(group2)

    for _ in range(n_bootstrap):
        g1_boot = rng.choice(group1, size=n1, replace=True)
        g2_boot = rng.choice(group2, size=n2, replace=True)

        d = compute_effect_size(g1_boot, g2_boot)
        effect_sizes.append(d)

    # Compute percentile interval
    alpha = 1 - confidence
    lower = np.percentile(effect_sizes, alpha / 2 * 100)
    upper = np.percentile(effect_sizes, (1 - alpha / 2) * 100)

    return (observed, lower, upper)


def check_sample_size_adequacy(
    n: int,
    analysis_type: str = 'regression',
    features: int = None,
    confidence: float = 0.95
) -> dict:
    """
    Check if sample size is adequate for statistical analysis.

    Args:
        n: Sample size
        analysis_type: Type of analysis ('regression', 'correlation',
                      'group_comparison', 'bootstrap')
        features: Number of features (for regression)
        confidence: Confidence level (affects required n)

    Returns:
        Dictionary with keys:
        - 'adequate': bool, whether sample size is adequate
        - 'warnings': list of warning strings
        - 'min_recommended': int, minimum recommended sample size
        - 'n': int, actual sample size
    """
    warnings = []
    min_n = 30  # Default minimum

    if analysis_type == 'regression':
        # Rule of thumb: n >= 10-20 per predictor
        min_n = (features or 1) * 15
        if n < min_n:
            warnings.append(
                f"Small sample for regression (n={n}, recommended >= {min_n})"
            )

    elif analysis_type == 'correlation':
        # n >= 30 for stable correlation estimates
        min_n = 30
        if n < min_n:
            warnings.append(
                f"Small sample for correlation (n={n}, recommended >= {min_n})"
            )

    elif analysis_type == 'group_comparison':
        # n >= 30 per group for t-test/effect size
        min_n = 30
        if n < min_n:
            warnings.append(
                f"Small sample per group (n={n}, recommended >= {min_n})"
            )

    elif analysis_type == 'bootstrap':
        # n >= 20 for bootstrap to be reliable
        min_n = 20
        if n < min_n:
            warnings.append(
                f"Sample too small for bootstrap (n={n}, recommended >= {min_n})"
            )

    # Critical threshold
    if n < 10:
        warnings.append("CRITICAL: Sample size too small for ANY reliable inference")

    return {
        'adequate': len(warnings) == 0,
        'warnings': warnings,
        'min_recommended': min_n,
        'n': n
    }

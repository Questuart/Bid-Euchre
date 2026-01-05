"""
Core metric calculations for strategy evaluation.

Primary metrics:
- Win rate: Team earned ≥6 tricks (won the hand)
- Push rate: Team earned exactly 5 tricks (tied)
- Loss rate: Team earned ≤4 tricks (lost the hand)

All rates include Wilson score confidence intervals for robustness.
"""

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class OutcomeStats:
    """
    Statistics for Win/Push/Loss outcomes.
    
    All rates are proportions (0.0 to 1.0).
    """
    n_total: int
    
    # Counts
    n_wins: int
    n_pushes: int
    n_losses: int
    
    # Rates
    win_rate: float
    push_rate: float
    loss_rate: float
    
    # Confidence intervals (95% by default)
    win_ci: Tuple[float, float]
    push_ci: Tuple[float, float]
    loss_ci: Tuple[float, float]
    
    # Mean tricks (for context)
    mean_tricks: float
    std_tricks: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "n_total": self.n_total,
            "n_wins": self.n_wins,
            "n_pushes": self.n_pushes,
            "n_losses": self.n_losses,
            "win_rate": self.win_rate,
            "push_rate": self.push_rate,
            "loss_rate": self.loss_rate,
            "win_ci": self.win_ci,
            "push_ci": self.push_ci,
            "loss_ci": self.loss_ci,
            "mean_tricks": self.mean_tricks,
            "std_tricks": self.std_tricks,
        }


def wilson_score_interval(
    n_successes: int,
    n_total: int,
    confidence: float = 0.95
) -> Tuple[float, float]:
    """
    Compute Wilson score confidence interval for a proportion.
    
    More accurate than normal approximation for small samples or extreme proportions.
    
    Args:
        n_successes: Number of successes
        n_total: Total number of trials
        confidence: Confidence level (default 0.95 for 95% CI)
    
    Returns:
        (lower_bound, upper_bound) as proportions
    """
    if n_total == 0:
        return (0.0, 0.0)
    
    p_hat = n_successes / n_total
    
    # Z-score for confidence level
    if confidence == 0.95:
        z = 1.96
    elif confidence == 0.99:
        z = 2.576
    else:
        # General case (slower)
        from scipy import stats
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
    
    denominator = 1 + z**2 / n_total
    center = p_hat + z**2 / (2 * n_total)
    spread = z * np.sqrt(p_hat * (1 - p_hat) / n_total + z**2 / (4 * n_total**2))
    
    lower = (center - spread) / denominator
    upper = (center + spread) / denominator
    
    return (max(0.0, lower), min(1.0, upper))


def compute_outcome_stats(
    trick_counts: List[int],
    confidence: float = 0.95
) -> OutcomeStats:
    """
    Compute Win/Push/Loss statistics from trick counts.
    
    Args:
        trick_counts: List of trick counts for a team (0-10)
        confidence: Confidence level for CI (default 0.95)
    
    Returns:
        OutcomeStats with all metrics
    """
    trick_counts = np.array(trick_counts)
    n_total = len(trick_counts)
    
    if n_total == 0:
        return OutcomeStats(
            n_total=0,
            n_wins=0, n_pushes=0, n_losses=0,
            win_rate=0.0, push_rate=0.0, loss_rate=0.0,
            win_ci=(0.0, 0.0), push_ci=(0.0, 0.0), loss_ci=(0.0, 0.0),
            mean_tricks=0.0, std_tricks=0.0,
        )
    
    # Classify outcomes
    n_wins = int(np.sum(trick_counts >= 6))
    n_pushes = int(np.sum(trick_counts == 5))
    n_losses = int(np.sum(trick_counts <= 4))
    
    # Compute rates
    win_rate = n_wins / n_total
    push_rate = n_pushes / n_total
    loss_rate = n_losses / n_total
    
    # Compute confidence intervals
    win_ci = wilson_score_interval(n_wins, n_total, confidence)
    push_ci = wilson_score_interval(n_pushes, n_total, confidence)
    loss_ci = wilson_score_interval(n_losses, n_total, confidence)
    
    # Basic stats
    mean_tricks = float(np.mean(trick_counts))
    std_tricks = float(np.std(trick_counts, ddof=1) if n_total > 1 else 0.0)
    
    return OutcomeStats(
        n_total=n_total,
        n_wins=n_wins,
        n_pushes=n_pushes,
        n_losses=n_losses,
        win_rate=win_rate,
        push_rate=push_rate,
        loss_rate=loss_rate,
        win_ci=win_ci,
        push_ci=push_ci,
        loss_ci=loss_ci,
        mean_tricks=mean_tricks,
        std_tricks=std_tricks,
    )


def outcome_rates_with_ci(
    trick_counts: List[int],
    confidence: float = 0.95
) -> dict:
    """
    Convenience function to get outcome rates as a dictionary.
    
    Returns dict with keys:
        - win_rate, push_rate, loss_rate
        - win_ci_lower, win_ci_upper, etc.
        - n_total, mean_tricks, std_tricks
    """
    stats = compute_outcome_stats(trick_counts, confidence)
    
    return {
        "n_total": stats.n_total,
        "win_rate": stats.win_rate,
        "push_rate": stats.push_rate,
        "loss_rate": stats.loss_rate,
        "win_ci_lower": stats.win_ci[0],
        "win_ci_upper": stats.win_ci[1],
        "push_ci_lower": stats.push_ci[0],
        "push_ci_upper": stats.push_ci[1],
        "loss_ci_lower": stats.loss_ci[0],
        "loss_ci_upper": stats.loss_ci[1],
        "mean_tricks": stats.mean_tricks,
        "std_tricks": stats.std_tricks,
    }


def paired_delta_stats(
    baseline_tricks: List[int],
    strategy_tricks: List[int],
    confidence: float = 0.95
) -> dict:
    """
    Compute paired delta statistics (strategy - baseline).
    
    Args:
        baseline_tricks: Trick counts for baseline strategy
        strategy_tricks: Trick counts for comparison strategy
        confidence: Confidence level for CI
    
    Returns:
        Dictionary with mean_delta, ci_lower, ci_upper, n_matched
    """
    baseline = np.array(baseline_tricks)
    strategy = np.array(strategy_tricks)
    
    if len(baseline) != len(strategy):
        raise ValueError("Baseline and strategy must have same number of samples")
    
    n = len(baseline)
    if n == 0:
        return {
            "mean_delta": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "n_matched": 0,
        }
    
    deltas = strategy - baseline
    mean_delta = float(np.mean(deltas))
    
    if n == 1:
        return {
            "mean_delta": mean_delta,
            "ci_lower": mean_delta,
            "ci_upper": mean_delta,
            "n_matched": n,
        }
    
    # Paired t-test confidence interval
    std_delta = np.std(deltas, ddof=1)
    se_delta = std_delta / np.sqrt(n)
    
    # t-critical value
    from scipy import stats
    alpha = 1 - confidence
    t_crit = stats.t.ppf(1 - alpha / 2, df=n - 1)
    
    margin = t_crit * se_delta
    ci_lower = mean_delta - margin
    ci_upper = mean_delta + margin
    
    return {
        "mean_delta": mean_delta,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n_matched": n,
    }


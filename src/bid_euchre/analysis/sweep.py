"""Reusable sweep and evaluation primitives for hyperparameter tuning.

Extracted from notebooks 56 (pass-threshold) and 58 (lambda tuning) to
provide a shared foundation for train/val split, grid search, guardrail
checks, and bootstrap validation.

Consumers import directly::

    from bid_euchre.analysis.sweep import deal_partition, compute_ev_vectorized

Do NOT re-export from analysis/__init__.py (circular import risk).
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

# ---------------------------------------------------------------------------
# Deal partitioning
# ---------------------------------------------------------------------------


def deal_partition(deal_id: str, seed: int = 42) -> str:
    """Deterministic 60/40 train/val split via SHA-256 hash.

    Buckets 0-2 (60%) -> "train", 3-4 (40%) -> "val".
    Grouped by deal_id to prevent leakage when a deal has multiple rows.

    Args:
        deal_id: Unique deal identifier (converted to str internally).
        seed: Hash salt for reproducibility. Different seeds yield
              different partitions.

    Returns:
        "train" or "val"
    """
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"


# ---------------------------------------------------------------------------
# Vectorized EV and bid-level search
# ---------------------------------------------------------------------------

_Z_CAP = 6.0


def compute_ev_vectorized(
    mu: np.ndarray, sigma: float, bid_n: np.ndarray
) -> np.ndarray:
    """Vectorized Gaussian expected net-differential.

    Mirrors ``_compute_ev_static`` in ``bidding.py`` exactly, but operates
    on numpy arrays for batch evaluation.

    Args:
        mu: Predicted tricks (array of floats).
        sigma: Residual standard deviation (scalar, per contract family).
        bid_n: Bid level for each hand (array of ints).

    Returns:
        Expected net-differential array of same shape as *mu*.
    """
    if sigma == 0.0:
        return np.where(mu >= bid_n, 2.0 * mu - 10.0, mu - bid_n - 10.0)

    threshold = bid_n - 0.5
    z = (threshold - mu) / sigma
    z = np.clip(z, -_Z_CAP, _Z_CAP)

    p_make = 1.0 - norm.cdf(z)
    p_set = 1.0 - p_make
    pdf_z = norm.pdf(z)

    e_tricks_make = np.where(p_make > 1e-12, mu + sigma * pdf_z / p_make, mu)
    e_tricks_set = np.where(p_set > 1e-12, mu - sigma * pdf_z / p_set, mu)

    make_ev = 2.0 * e_tricks_make - 10.0
    set_ev = e_tricks_set - bid_n - 10.0

    return p_make * make_ev + p_set * set_ev


def bid_level_search_vectorized(
    mu_vals: np.ndarray,
    sigma: float,
    risk_lambda: float = 0.0,
    pass_threshold: float = 0.0,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized bid-level search across all legal levels (1-10).

    For each hand, evaluates utility at every bid level and selects the
    level with highest utility. Tie-break: prefer higher bid level (matches
    ``compute_best_bid()`` in ``bidding.py``).

    For non-zero ``risk_lambda``, falls back to a scalar loop calling
    production ``compute_best_bid()`` (vectorized CVaR deferred to R1).

    Args:
        mu_vals: Predicted tricks array.
        sigma: Residual standard deviation (scalar).
        risk_lambda: Risk penalty weight. Non-zero triggers scalar fallback.
        pass_threshold: Minimum utility for non-pass bid (default 0.0).
        seed: RNG seed for CVaR Monte Carlo (only used when risk_lambda > 0).

    Returns:
        ``(best_bid_n, best_utility)`` arrays of shape ``(n_hands,)``.
        ``best_bid_n[i] = 0`` means the model passes that hand.
    """
    n = len(mu_vals)
    best_bid_n = np.ones(n, dtype=int)
    best_utility = np.full(n, -np.inf)

    if risk_lambda != 0.0:
        # Scalar fallback: production compute_best_bid() for non-zero lambda.
        # Vectorized CVaR deferred to R1.
        from bid_euchre.strategy.bidding import compute_best_bid

        for i in range(n):
            result = compute_best_bid(
                mu=float(mu_vals[i]),
                sigma=sigma,
                current_high_bid=0,
                pass_threshold=pass_threshold,
                bid_level_search=True,
                risk_lambda=risk_lambda,
                seed=seed,
            )
            if result is not None:
                best_bid_n[i] = result[0]
                best_utility[i] = result[1]
            else:
                best_bid_n[i] = 0
                best_utility[i] = -np.inf
        return best_bid_n, best_utility

    # Original vectorized path for lambda=0 (unchanged).
    # Iterate ascending; use >= so last (highest n) with max utility wins.
    # This matches compute_best_bid() tie-break: prefer higher n on equal utility.
    for bid_n in range(1, 11):
        ev = compute_ev_vectorized(mu_vals, sigma, np.full(n, bid_n))
        utility = ev  # At lambda=0, utility = EV (no CVaR penalty)
        better_or_tie = utility >= best_utility
        best_utility = np.where(better_or_tie, utility, best_utility)
        best_bid_n = np.where(better_or_tie, bid_n, best_bid_n)

    return best_bid_n, best_utility


# ---------------------------------------------------------------------------
# Guardrail checks
# ---------------------------------------------------------------------------


def check_guardrails(
    metrics: dict[str, float],
    bid_rate_floor: float = 0.05,
    bid_rate_cap: float = 0.95,
    make_rate_floor: float = 0.45,
    bid_rate_key: str = "bid_rate",
) -> tuple[bool, list[str]]:
    """Check bid_rate and make_rate against guardrail bounds.

    Args:
        metrics: Dict containing bid rate and/or ``"make_rate"`` keys.
        bid_rate_floor: Minimum acceptable bid rate.
        bid_rate_cap: Maximum acceptable bid rate.
        make_rate_floor: Minimum acceptable make rate.
        bid_rate_key: Key to use for bid rate (default ``"bid_rate"``). Use
            ``"seat_bid_propensity"`` for self-play contexts where deal-level
            bid_rate inflates.

    Returns:
        ``(all_pass, violation_messages)`` where *all_pass* is True when
        every checked guardrail is satisfied.
    """
    violations: list[str] = []
    bid_rate = metrics.get(bid_rate_key)
    make_rate = metrics.get("make_rate")
    if bid_rate is not None and bid_rate < bid_rate_floor:
        violations.append(f"bid_rate {bid_rate:.4f} < floor {bid_rate_floor}")
    if bid_rate is not None and bid_rate > bid_rate_cap:
        violations.append(f"bid_rate {bid_rate:.4f} > cap {bid_rate_cap}")
    if make_rate is not None and make_rate < make_rate_floor:
        violations.append(f"make_rate {make_rate:.4f} < floor {make_rate_floor}")
    return (len(violations) == 0, violations)


# ---------------------------------------------------------------------------
# Paired bootstrap
# ---------------------------------------------------------------------------


def bootstrap_paired_delta(
    baseline: dict[int, float],
    candidate: dict[int, float],
    n_bootstrap: int = 10_000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Paired bootstrap CI for mean(candidate - baseline).

    Keys must match exactly (same deal/hand ids in both dicts).

    Args:
        baseline: Mapping from id -> metric value (baseline policy).
        candidate: Mapping from id -> metric value (candidate policy).
        n_bootstrap: Number of bootstrap resamples.
        ci: Confidence level (e.g. 0.95 for 95% CI).
        seed: RNG seed for reproducibility.

    Returns:
        ``(observed_delta, ci_low, ci_high)``

    Raises:
        ValueError: If keys don't match between baseline and candidate.
    """
    if set(baseline.keys()) != set(candidate.keys()):
        raise ValueError(
            "Keys must match between baseline and candidate. "
            f"baseline has {len(baseline)} keys, candidate has {len(candidate)} keys."
        )

    if not baseline:
        raise ValueError("No paired observations")

    # Align by key to compute paired deltas
    keys = sorted(baseline.keys())
    deltas = np.array([candidate[k] - baseline[k] for k in keys])

    observed = float(np.mean(deltas))

    rng = np.random.RandomState(seed)
    boot_means = np.array(
        [
            rng.choice(deltas, size=len(deltas), replace=True).mean()
            for _ in range(n_bootstrap)
        ]
    )

    alpha = 1.0 - ci
    ci_low = float(np.percentile(boot_means, alpha / 2 * 100))
    ci_high = float(np.percentile(boot_means, (1 - alpha / 2) * 100))

    return (observed, ci_low, ci_high)


# ---------------------------------------------------------------------------
# Generalized sweep infrastructure
# ---------------------------------------------------------------------------


class ParameterSweep:
    """Grid search over a single hyperparameter with train/val split.

    Subclasses must implement :meth:`evaluate_candidate` to provide
    domain-specific evaluation logic.
    """

    def __init__(
        self,
        name: str,
        grid: list[float],
        split_seed: int = 42,
        bootstrap_seed: int = 42,
        n_bootstrap: int = 10_000,
    ):
        self.name = name
        self.grid = grid
        self.split_seed = split_seed
        self.bootstrap_seed = bootstrap_seed
        self.n_bootstrap = n_bootstrap

    def evaluate_candidate(
        self, df: pd.DataFrame, param_value: float
    ) -> dict[str, Any]:
        """Evaluate a single parameter value. Override in subclass."""
        raise NotImplementedError

    def run_train_selection(self, df: pd.DataFrame) -> tuple[float, dict[float, dict]]:
        """Run sweep on train split, return (best_param, results_dict).

        Selects the parameter value with the highest primary metric
        (``net_eppd`` or ``net_diff_mean``) among all grid candidates.
        """
        train_df = df[df["_partition"] == "train"]
        results: dict[float, dict] = {}
        for val in self.grid:
            results[val] = self.evaluate_candidate(train_df, val)
        best = max(
            results,
            key=lambda v: results[v].get(
                "net_eppd", results[v].get("net_diff_mean", 0)
            ),
        )
        return best, results

    def run_validation(self, df: pd.DataFrame, selected: float) -> dict[str, Any]:
        """Validate selected param on val split."""
        val_df = df[df["_partition"] == "val"]
        return self.evaluate_candidate(val_df, selected)

    def add_partition_column(
        self, df: pd.DataFrame, deal_id_col: str = "deal_id"
    ) -> pd.DataFrame:
        """Add ``_partition`` column using :func:`deal_partition`."""
        df = df.copy()
        df["_partition"] = df[deal_id_col].apply(
            lambda d: deal_partition(str(d), self.split_seed)
        )
        return df


class ThresholdSweep(ParameterSweep):
    """Sweep over ``pass_threshold`` values."""

    def __init__(self, grid: list[float], **kwargs: Any):
        super().__init__(name="threshold", grid=grid, **kwargs)


class LambdaSweep(ParameterSweep):
    """Sweep over ``risk_lambda`` values."""

    def __init__(self, grid: list[float], pass_threshold: float = 0.0, **kwargs: Any):
        super().__init__(name="lambda", grid=grid, **kwargs)
        self.pass_threshold = pass_threshold

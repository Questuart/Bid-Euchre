import os
from typing import Optional, List, Tuple
import numpy as np
import matplotlib.pyplot as plt

from .simulation import simulate_many_hands

MIN_BUCKET_COUNT = 5  # ignore buckets with fewer hands than this


def get_scenarios(n_per: int) -> List[Tuple[str, Optional[str], str, int]]:
    """
    Return list of scenarios:
    (contract_type, trump_suit, label, n_hands)
    """
    scenarios: List[Tuple[str, Optional[str], str, int]] = []

    # High and Low no-trump (no trump_suit)
    scenarios.append(("high", None, "High no-trump", n_per))
    scenarios.append(("low", None, "Low no-trump", n_per))

    # Suit contracts for each trump suit
    for suit in ["C", "D", "H", "S"]:
        label = f"Suit contract (trump={suit})"
        scenarios.append(("suit", suit, label, n_per))

    return scenarios


def compute_line_and_metrics(x: np.ndarray, y: np.ndarray):
    """Return (slope, intercept, corr, r2)."""
    corr = np.corrcoef(x, y)[0, 1]
    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs
    y_pred = slope * x + intercept
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return slope, intercept, corr, r2


def plot_scalar_score(results, label: str, output_dir: str, suffix: str):
    """Plot scalar hand score vs avg tricks."""
    buckets = results["score_buckets_player0"]
    if not buckets:
        print(f"No scalar score buckets for scenario: {label}")
        return

    # Filter by MIN_BUCKET_COUNT
    filtered_scores = []
    filtered_avgs = []
    for s, stats in buckets.items():
        if stats["count"] >= MIN_BUCKET_COUNT:
            filtered_scores.append(s)
            filtered_avgs.append(stats["avg_tricks"])

    if len(filtered_scores) < 2:
        print(f"Not enough scalar buckets for scenario: {label}")
        return

    scores = np.array(sorted(filtered_scores), dtype=float)
    avg_tricks = np.array(
        [buckets[s]["avg_tricks"] for s in sorted(filtered_scores)],
        dtype=float,
    )

    slope, intercept, corr, r2 = compute_line_and_metrics(scores, avg_tricks)

    plt.figure()
    plt.title(
        f"Score vs Avg Tricks\n{label} (n={results['hands']}, R²={r2:.3f}, ρ={corr:.3f})"
    )
    plt.xlabel("Player 0 hand score (scalar)")
    plt.ylabel("Avg tricks for Team 0")

    # Scatter
    plt.scatter(scores, avg_tricks, alpha=0.7)

    # Trendline
    x_line = np.linspace(scores.min(), scores.max(), 100)
    y_line = slope * x_line + intercept
    plt.plot(x_line, y_line, linewidth=2, alpha=0.8)

    # Diagonal reference (across data range)
    y_min, y_max = avg_tricks.min(), avg_tricks.max()
    x_min, x_max = scores.min(), scores.max()
    diag_x = np.array([x_min, x_max])
    diag_y = np.array([y_min, y_max])
    plt.plot(diag_x, diag_y, linestyle="--", alpha=0.5)

    # Annotate min & max score buckets
    for idx in [0, -1]:
        s = scores[idx]
        stats = buckets[s]
        plt.annotate(
            f"s={int(s)}\n n={stats['count']}",
            (s, stats["avg_tricks"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"score_vs_tricks_{suffix}.png")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    print(
        f"Saved scalar plot for {label} to {filename} "
        f"(buckets used: {len(scores)}, R²={r2:.3f}, ρ={corr:.3f})"
    )


def plot_feature(
    results,
    feature_name: str,
    label: str,
    output_dir: str,
    suffix: str,
):
    """Plot a single feature vs avg tricks."""
    feature_buckets = results.get("feature_buckets_player0", {})
    fb = feature_buckets.get(feature_name)
    if not fb:
        print(f"No feature buckets for {feature_name} in scenario: {label}")
        return

    filtered_vals = []
    filtered_avgs = []

    for v, stats in fb.items():
        if stats["count"] >= MIN_BUCKET_COUNT:
            filtered_vals.append(v)
            filtered_avgs.append(stats["avg_tricks"])

    if len(filtered_vals) < 2:
        print(f"Not enough buckets for feature {feature_name} in {label}")
        return

    vals = np.array(sorted(filtered_vals), dtype=float)
    avg_tricks = np.array(
        [fb[v]["avg_tricks"] for v in sorted(filtered_vals)],
        dtype=float,
    )

    slope, intercept, corr, r2 = compute_line_and_metrics(vals, avg_tricks)

    plt.figure()
    plt.title(
        f"{feature_name} vs Avg Tricks\n{label} (R²={r2:.3f}, ρ={corr:.3f})"
    )
    plt.xlabel(f"Player 0 {feature_name}")
    plt.ylabel("Avg tricks for Team 0")

    plt.scatter(vals, avg_tricks, alpha=0.7)

    x_line = np.linspace(vals.min(), vals.max(), 100)
    y_line = slope * x_line + intercept
    plt.plot(x_line, y_line, linewidth=2, alpha=0.8)

    # Diagonal reference across data range
    y_min, y_max = avg_tricks.min(), avg_tricks.max()
    x_min, x_max = vals.min(), vals.max()
    diag_x = np.array([x_min, x_max])
    diag_y = np.array([y_min, y_max])
    plt.plot(diag_x, diag_y, linestyle="--", alpha=0.5)

    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(
        output_dir, f"feature_{feature_name}_{suffix}.png"
    )
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    print(
        f"Saved feature plot ({feature_name}) for {label} to {filename} "
        f"(buckets used: {len(vals)}, R²={r2:.3f}, ρ={corr:.3f})"
    )


def main():
    n_per = 5000  # hands per scenario
    scenarios = get_scenarios(n_per)

    print(f"Running {len(scenarios)} scenarios, {n_per} hands each...")
    for contract_type, trump_suit, label, n_hands in scenarios:
        print(f"\n=== Scenario: {label} ===")
        # Run simulation once per scenario
        results = simulate_many_hands(
            n=n_hands,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )

        # Build suffix used in filenames
        suffix = (
            f"{contract_type}"
            if contract_type != "suit"
            else f"{contract_type}_{trump_suit}"
        )

        # 1) Scalar score plot
        plot_scalar_score(results, label, output_dir="plots", suffix=suffix)

        # 2) Feature plots
        if contract_type == "suit":
            feature_list = ["bowers", "trump_count", "rank_sum"]
        else:  # high / low no-trump
            feature_list = ["offsuit_aces", "rank_sum"]

        for feat in feature_list:
            plot_feature(
                results,
                feature_name=feat,
                label=label,
                output_dir="plots",
                suffix=f"{suffix}_{feat}",
            )


if __name__ == "__main__":
    main()

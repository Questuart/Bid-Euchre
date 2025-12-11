import os
from typing import Optional, List, Tuple
import numpy as np
import matplotlib.pyplot as plt

from .simulation import simulate_many_hands


MIN_BUCKET_COUNT = 5  # ignore score buckets with fewer than this many hands


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


def plot_score_vs_tricks_for_scenario(
    contract_type: str,
    trump_suit: Optional[str],
    label: str,
    n_hands: int,
    output_dir: str = "plots",
) -> None:
    """
    Run simulations for a single scenario and produce a scatter plot
    of Player 0 hand score vs Team 0 average tricks for that score bucket,
    with a linear trendline and a diagonal reference line.
    """
    os.makedirs(output_dir, exist_ok=True)

    results = simulate_many_hands(
        n=n_hands,
        contract_type=contract_type,
        trump_suit=trump_suit,
    )

    buckets = results["score_buckets_player0"]

    if not buckets:
        print(f"No score buckets for scenario: {label}")
        return

    # Filter out buckets with too few samples
    filtered_scores = []
    filtered_avg_tricks = []
    filtered_counts = []

    for s, stats in buckets.items():
        if stats["count"] >= MIN_BUCKET_COUNT:
            filtered_scores.append(s)
            filtered_avg_tricks.append(stats["avg_tricks"])
            filtered_counts.append(stats["count"])

    if len(filtered_scores) < 2:
        print(f"Not enough populated buckets for scenario: {label}")
        return

    scores = np.array(sorted(filtered_scores), dtype=float)
    avg_tricks = np.array(
        [buckets[s]["avg_tricks"] for s in sorted(filtered_scores)],
        dtype=float,
    )

    # Basic stats: correlation and R^2
    corr = np.corrcoef(scores, avg_tricks)[0, 1]
    coeffs = np.polyfit(scores, avg_tricks, 1)
    slope, intercept = coeffs
    y_pred = slope * scores + intercept
    ss_res = np.sum((avg_tricks - y_pred) ** 2)
    ss_tot = np.sum((avg_tricks - np.mean(avg_tricks)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    # Scatter
    plt.figure()
    plt.title(
        f"Score vs Avg Tricks\n{label} (n={n_hands}, R²={r2:.3f}, ρ={corr:.3f})"
    )
    plt.xlabel("Player 0 hand score (scalar)")
    plt.ylabel("Avg tricks for Team 0")

    plt.scatter(scores, avg_tricks, alpha=0.7)

    # Linear trendline
    x_line = np.linspace(scores.min(), scores.max(), 100)
    y_line = slope * x_line + intercept
    plt.plot(x_line, y_line, linewidth=2, alpha=0.8)

    # Diagonal reference line across the data range
    # (purely visual; not y=x in score/tricks units)
    y_min, y_max = avg_tricks.min(), avg_tricks.max()
    x_min, x_max = scores.min(), scores.max()
    diag_x = np.array([x_min, x_max])
    diag_y = np.array([y_min, y_max])
    plt.plot(diag_x, diag_y, linestyle="--", alpha=0.5)

    # Annotate a couple of extreme buckets (min and max scores)
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

    # Save to file
    suffix = (
        f"{contract_type}"
        if contract_type != "suit"
        else f"{contract_type}_{trump_suit}"
    )
    filename = os.path.join(output_dir, f"score_vs_tricks_{suffix}.png")
    plt.tight_layout()
    plt.savefig(filename)
    plt.close()

    print(
        f"Saved plot for {label} to {filename} "
        f"(buckets used: {len(scores)}, R²={r2:.3f}, ρ={corr:.3f})"
    )


def main():
    n_per = 5000  # hands per scenario
    scenarios = get_scenarios(n_per)

    print(f"Running {len(scenarios)} scenarios, {n_per} hands each...")
    for contract_type, trump_suit, label, n_hands in scenarios:
        print(f"\n=== Scenario: {label} ===")
        plot_score_vs_tricks_for_scenario(
            contract_type=contract_type,
            trump_suit=trump_suit,
            label=label,
            n_hands=n_hands,
            output_dir="plots",
        )


if __name__ == "__main__":
    main()

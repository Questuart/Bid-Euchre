import os
from typing import Optional, List, Tuple
import numpy as np
import matplotlib.pyplot as plt

from .simulation import simulate_many_hands


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
    with a linear trendline overlaid.
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

    # Sort by score
    scores = sorted(buckets.keys())
    avg_tricks = [buckets[s]["avg_tricks"] for s in scores]
    counts = [buckets[s]["count"] for s in scores]

    x = np.array(scores, dtype=float)
    y = np.array(avg_tricks, dtype=float)

    plt.figure()
    plt.title(f"Score vs Avg Tricks\n{label} (n={n_hands})")
    plt.xlabel("Player 0 hand score (scalar)")
    plt.ylabel("Avg tricks for Team 0")

    # Scatter only (no connecting lines between points)
    plt.scatter(x, y, alpha=0.7)

    # Linear trendline, if we have enough distinct points
    if len(np.unique(x)) > 1:
        coeffs = np.polyfit(x, y, 1)  # degree-1 polynomial (line)
        slope, intercept = coeffs
        x_line = np.linspace(x.min(), x.max(), 100)
        y_line = slope * x_line + intercept
        plt.plot(x_line, y_line, linewidth=2, alpha=0.8)

    # Annotate a couple of extreme buckets for sanity: min and max score
    if len(scores) >= 2:
        for idx in [0, -1]:
            s = scores[idx]
            b = buckets[s]
            plt.annotate(
                f"s={s}\n n={b['count']}",
                (s, b["avg_tricks"]),
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
        f"(score buckets: {len(scores)})"
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

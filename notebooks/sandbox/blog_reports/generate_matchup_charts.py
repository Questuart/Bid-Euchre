"""Generate strategy matchup charts for blog reports.

Produces all available matchup charts from the 5x5 outcomes_matrix_shallow run:
- win_rate_heatmap.png          — Team 0 win rate (RdYlGn, centered at 0.5)
- trick_advantage_heatmap.png   — Trick delta (team0 - team1, centered at 0)
- tricks_distribution.png       — Violin/box plots across all 25 matchups
- matchup_summary.png           — 3-panel summary (heatmap + bars + self-play)
- strategy_delta_bars.png       — Horizontal bar, delta vs auto-detected baseline
- self_play_control.png         — Self-play balance check (~5.0 mean)
- self_play_by_contract.png     — Grouped bar, self-play by contract/scenario

Usage:
    PYTHONPATH=src uv run python notebooks/sandbox/blog_reports/generate_matchup_charts.py
"""

import sys
from pathlib import Path

# Ensure src/ is on the import path when run standalone
_src = Path(__file__).resolve().parents[3] / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import matplotlib

matplotlib.use("Agg")

from bid_euchre.diagnostics.strategy_charts import (
    plot_matchup_summary,
    plot_self_play_by_contract,
    plot_self_play_control,
    plot_strategy_delta_bars,
    plot_tricks_distribution_comparison,
    plot_win_rate_heatmap,
)
from bid_euchre.reporting.chart_runner import _load_matchup_results

# --- Configuration ---
RUN_DIR = Path(__file__).resolve().parents[3] / (
    "data/runs/canonical_bidless_outcomes_matrix_shallow_42_20260206_171634"
)
OUTPUT_DIR = Path(__file__).resolve().parent
DPI = 200


def _save(fig, name: str) -> str:
    path = OUTPUT_DIR / f"{name}.png"
    fig.savefig(str(path), dpi=DPI, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    print(f"  Saved: {path.name}")
    return str(path)


def main() -> None:
    print(f"Loading matchup data from {RUN_DIR.name} ...")
    matchup_results = _load_matchup_results(RUN_DIR)
    if not matchup_results:
        print("ERROR: No matchup data found.")
        sys.exit(1)
    print(f"  Loaded {len(matchup_results)} matchups")

    # --- 1. Win rate heatmap ---
    fig = plot_win_rate_heatmap(matchup_results)
    _save(fig, "win_rate_heatmap")

    # --- 2. Trick advantage heatmap ---
    # Compute trick_advantage = mean_tricks_team0 - mean_tricks_team1
    advantage_results = {}
    for key, result in matchup_results.items():
        t0 = result.get("mean_tricks_team0", 5.0)
        t1 = result.get("mean_tricks_team1", 5.0)
        advantage_results[key] = {**result, "trick_advantage": t0 - t1}

    # Find symmetric limits for diverging colormap
    advantages = [r["trick_advantage"] for r in advantage_results.values()]
    abs_max = max(abs(v) for v in advantages) if advantages else 1.0

    fig = plot_win_rate_heatmap(
        advantage_results,
        metric="trick_advantage",
        title="Trick Advantage Heatmap (Team 0 - Team 1)",
        fmt="+.2f",
        center_override=0.0,
        vmin_override=-abs_max,
        vmax_override=abs_max,
        cbar_label_override="Trick Advantage (Team 0)",
    )
    _save(fig, "trick_advantage_heatmap")

    # --- 3. Tricks distribution ---
    fig = plot_tricks_distribution_comparison(matchup_results)
    _save(fig, "tricks_distribution")

    # --- 4. Matchup summary ---
    fig = plot_matchup_summary(matchup_results)
    _save(fig, "matchup_summary")

    # --- 5. Strategy delta bars ---
    self_play = {
        team0: result
        for (team0, team1), result in matchup_results.items()
        if team0 == team1
    }
    # Auto-detect baseline: prefer random_legal if available
    baseline_name = (
        "random_legal" if "random_legal" in self_play else next(iter(self_play), None)
    )

    if baseline_name and baseline_name in self_play:
        baseline_results = self_play[baseline_name]
        comparison_results = {
            team0: result
            for (team0, team1), result in matchup_results.items()
            if team1 == baseline_name and team0 != baseline_name
        }
        if comparison_results:
            fig = plot_strategy_delta_bars(
                baseline_results,
                comparison_results,
                baseline_name=baseline_name,
            )
            _save(fig, "strategy_delta_bars")

    # --- 6. Self-play control ---
    if self_play:
        fig = plot_self_play_control(self_play)
        _save(fig, "self_play_control")

    # --- 7. Self-play by contract ---
    fig = plot_self_play_by_contract(matchup_results)
    if fig is not None:
        _save(fig, "self_play_by_contract")

    print("\nDone. All charts saved to notebooks/sandbox/blog_reports/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Run bidless dataset diagnostics from the command line.

Usage:
    PYTHONPATH=src python scripts/run_bidless_diagnostics.py --dataset /path/to/datasets
    PYTHONPATH=src python scripts/run_bidless_diagnostics.py --dataset /path/to/datasets --charts /tmp/charts
"""

import argparse
import sys
from pathlib import Path

from bid_euchre.diagnostics import (
    compare_first_last_batch,
    compute_health_scorecard,
    compute_seat_balance,
    display_issues,
    display_scorecard,
    load_bidless_dataset,
)


def main():
    parser = argparse.ArgumentParser(description="Run bidless diagnostics")
    parser.add_argument("--dataset", required=True, help="Path to dataset directory")
    parser.add_argument("--charts", help="Output dir for charts (optional)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Load dataset
    df = load_bidless_dataset(args.dataset)
    print(f"Loaded {len(df):,} rows from {args.dataset}")

    # Run health scorecard
    scorecard = compute_health_scorecard(df)
    if args.verbose:
        print("\n" + display_scorecard(scorecard))

    # Additional stats
    balance = compute_seat_balance(df)
    drift = compare_first_last_batch(df)
    print(f"\nSeat balance: {balance.interpretation}")
    print(f"Drift check: {drift.interpretation}")

    # Optional charts
    if args.charts:
        _save_charts(df, args.charts)

    # Exit code
    summary = scorecard.summary()
    if summary["FAIL"] > 0:
        print(f"\n❌ {summary['FAIL']} check(s) FAILED")
        if not args.verbose:
            issues = display_issues(scorecard)
            if issues:
                print("\n" + issues)
        return 1
    elif summary["WARN"] > 0:
        print(f"\n⚠️ {summary['WARN']} warning(s), {summary['PASS']} passed")
        if not args.verbose:
            issues = display_issues(scorecard)
            if issues:
                print("\n" + issues)
        return 0
    else:
        print(f"\n✅ All {summary['PASS']} checks passed")
        return 0


def _save_charts(df, output_dir):
    """Save diagnostic charts to output directory."""
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt

    from bid_euchre.diagnostics import (
        plot_feature_distributions,
        plot_hand_value_by_contract,
        plot_hand_value_by_seat,
        plot_rolling_mean,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    charts = [
        ("hand_value_by_seat.png", plot_hand_value_by_seat),
        ("hand_value_by_contract.png", plot_hand_value_by_contract),
        ("feature_distributions.png", plot_feature_distributions),
        ("rolling_mean.png", lambda d: plot_rolling_mean(d, "feat_hand_value")),
    ]

    print("\nSaving charts:")
    for filename, plot_fn in charts:
        fig = plot_fn(df)
        fig.savefig(output_dir / filename, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {filename}")


if __name__ == "__main__":
    sys.exit(main())

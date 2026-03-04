#!/usr/bin/env python
"""
Generate auction-context dataset with partner bidding features.

Runs an auction-mode experiment (all 4 seats bidding with the same artifact),
then post-processes JSONL logs to produce a bidless-format parquet dataset
augmented with 4 partner auction features per row.

Output: standard run directory with datasets/bidless.parquet (43-feature
hand_features struct) and datasets/bidless_outcomes.parquet.

Usage:
    uv run python scripts/internal/generate_auction_context_dataset.py \
        --bidder-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
        --seed 42 --n-deals 50000 \
        --output-dir data/runs/canonical_auction_r1_42
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from bid_euchre.core.cards import Card
from bid_euchre.features.auction_context import (
    PARTNER_FEATURE_NAMES,
    extract_partner_features,
)
from bid_euchre.features.hand_eval import get_hand_features


def _find_jsonl_log(run_dir):
    """Find the JSONL log file in a run directory."""
    logs_dir = Path(run_dir) / "logs"
    if not logs_dir.is_dir():
        return None
    jsonl_files = list(logs_dir.glob("*.jsonl"))
    if len(jsonl_files) == 1:
        return str(jsonl_files[0])
    # Multiple files: pick the largest (most likely the main log)
    if jsonl_files:
        return str(max(jsonl_files, key=lambda p: p.stat().st_size))
    return None


def _parse_contract(contract_str, trump_str):
    """Map JSONL contract/trump fields to (contract_type, trump_suit)."""
    if contract_str in ("HIGH", "high"):
        return "high", None
    elif contract_str in ("LOW", "low"):
        return "low", None
    else:
        # Suit contract: trump field has the suit letter
        return "suit", trump_str


def _parse_hand(hand_data):
    """Parse JSONL hand data ([suit, rank] pairs) into Card objects."""
    return [Card(c[0], c[1]) for c in hand_data]


def build_dataset_from_jsonl(jsonl_path):
    """Build bidless-format DataFrames from JSONL auction logs.

    Parses hand_end records, recomputes hand features from cards,
    and adds partner auction context features.

    Returns (bidless_rows, outcomes_rows).
    """
    bidless_rows = []
    outcomes_rows = []

    hand_id = 0
    with open(jsonl_path) as f:
        for line in f:
            record = json.loads(line)
            if record.get("event") != "hand_end":
                continue

            # Skip redeals (all-pass hands with no contract)
            if record.get("redeal_flag"):
                continue

            contract_type, trump_suit = _parse_contract(
                record["contract"], record.get("trump")
            )
            t0 = record["t0"]
            t1 = record["t1"]
            dealer = record.get("dealer_position", 0)
            deal_id = record.get("deal_id", hand_id)
            hands_data = record.get("hands")
            auction_transcript = record.get("auction_transcript") or []

            if not hands_data or len(hands_data) != 4:
                print(
                    f"  WARNING: Skipping hand {hand_id} — no hands data logged",
                    file=sys.stderr,
                )
                continue

            # Outcomes row (one per hand)
            outcomes_rows.append(
                {
                    "hand_id": hand_id,
                    "deal_id": deal_id,
                    "dealer_seat": dealer,
                    "contract_type": contract_type,
                    "trump_suit": trump_suit,
                    "strategy_id": "auction",
                    "matchup_id": "auction",
                    "team0_strategy": "auction",
                    "team1_strategy": "auction",
                    "tricks_team0": t0,
                    "tricks_team1": t1,
                    "team0_win": t0 > t1,
                }
            )

            # Bidless rows (one per seat)
            for seat in range(4):
                hand_cards = _parse_hand(hands_data[seat])

                # 39 hand features
                features = get_hand_features(hand_cards, contract_type, trump_suit)

                # 4 partner features
                partner_feats = extract_partner_features(
                    seat, auction_transcript, observer_best_contract=contract_type
                )

                # Merge into single dict (43 features)
                merged_features = {**features, **partner_feats}

                bidless_rows.append(
                    {
                        "hand_id": hand_id,
                        "seat": seat,
                        "dealer_seat": dealer,
                        "deal_id": deal_id,
                        "hand_cards": [str(c) for c in hand_cards],
                        "hand_features": merged_features,
                        "hand_feature_schema_version": 1,
                        "contract_type": contract_type,
                        "trump_suit": trump_suit,
                    }
                )

            hand_id += 1

    return bidless_rows, outcomes_rows


def validate_dataset(bidless_df, outcomes_df):
    """Run gate X1 validation on the generated dataset.

    Raises AssertionError on any validation failure.
    """
    # Assert 4 rows per hand
    rows_per_hand = bidless_df.groupby("hand_id").size()
    assert (
        rows_per_hand == 4
    ).all(), f"Expected 4 rows per hand, got: {rows_per_hand.value_counts().to_dict()}"

    # Assert partner features present and non-null
    sample_features = bidless_df["hand_features"].iloc[0]
    for fname in PARTNER_FEATURE_NAMES:
        assert fname in sample_features, f"Missing partner feature: {fname}"
        assert sample_features[fname] is not None, f"Null partner feature: {fname}"

    # Assert feature dict has 43 keys (39 hand + 4 partner)
    n_features = len(sample_features)
    assert n_features == 43, f"Expected 43 features, got {n_features}"

    # Assert outcomes match hands
    n_hands_bidless = bidless_df["hand_id"].nunique()
    n_hands_outcomes = len(outcomes_df)
    assert (
        n_hands_bidless == n_hands_outcomes
    ), f"Hand count mismatch: bidless={n_hands_bidless}, outcomes={n_hands_outcomes}"

    print(f"  Gate X1 PASS: {n_hands_bidless} hands, 43 features, 4 rows/hand")


def print_partner_feature_stats(bidless_df):
    """Print summary statistics for partner features."""
    # Flatten hand_features to get partner columns
    features_flat = pd.json_normalize(bidless_df["hand_features"])
    print("\n  Partner feature summary:")
    for fname in PARTNER_FEATURE_NAMES:
        col = features_flat[fname]
        print(
            f"    {fname}: mean={col.mean():.3f}, "
            f"std={col.std():.3f}, "
            f"min={col.min():.1f}, max={col.max():.1f}"
        )


def run_auction_experiment(
    bidder_artifact,
    seed,
    n_deals,
    bidder_class="HybridOLSaBidder",
    play_strategy="glutton",
):
    """Run an auction-mode experiment and return the run directory path."""
    # Create temporary config
    config = {
        "experiment_name": "auction_context_gen",
        "bidding_policies": [
            {
                "name": "target_bidder",
                "class_name": bidder_class,
                "params": {"artifact_path": bidder_artifact},
            }
        ],
        "strategies": [{"name": play_strategy, "class_name": "GluttonStrategy"}],
        "scenarios": [{"contract_type": None}],
        "parameters": {
            "n_per": n_deals,
            "play_strategy": play_strategy,
            "mode": "auction",
        },
    }

    config_path = f"/tmp/auction_context_gen_{seed}.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    print(f"  Config: {config_path}")
    print(f"  Running {n_deals} deals with seed={seed}...")

    # Snapshot data/runs before
    runs_path = Path("data/runs")
    runs_path.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in runs_path.iterdir() if p.is_dir()}

    # Run experiment
    cmd = [
        sys.executable,
        "experiments/run_experiment.py",
        "--config",
        config_path,
        "--seed",
        str(seed),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"  ERROR: Experiment failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Find new run directory
    after = {p.name for p in runs_path.iterdir() if p.is_dir()}
    new_dirs = after - before
    if len(new_dirs) != 1:
        print(
            f"  ERROR: Expected 1 new run directory, found {len(new_dirs)}",
            file=sys.stderr,
        )
        sys.exit(1)

    run_dir = str(runs_path / new_dirs.pop())
    print(f"  Run directory: {run_dir}")
    return run_dir


def main():
    parser = argparse.ArgumentParser(
        description="Generate auction-context dataset with partner features"
    )
    parser.add_argument(
        "--bidder-artifact",
        required=True,
        help="Path to bidder artifact JSON (all seats use this)",
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--n-deals", type=int, default=50000)
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for datasets (standard run directory structure)",
    )
    parser.add_argument(
        "--bidder-class",
        default="HybridOLSaBidder",
        help="Bidder class name (default: HybridOLSaBidder)",
    )
    parser.add_argument(
        "--play-strategy",
        default="glutton",
        help="Play strategy name (default: glutton)",
    )
    parser.add_argument(
        "--skip-run",
        default=None,
        help="Skip experiment run, use existing run directory for JSONL parsing",
    )
    args = parser.parse_args()

    print("=== Auction Context Dataset Generator ===")

    # Step 1: Run experiment (or use existing)
    if args.skip_run:
        run_dir = args.skip_run
        print(f"  Using existing run: {run_dir}")
    else:
        run_dir = run_auction_experiment(
            args.bidder_artifact,
            args.seed,
            args.n_deals,
            args.bidder_class,
            args.play_strategy,
        )

    # Step 2: Find JSONL log
    jsonl_path = _find_jsonl_log(run_dir)
    if not jsonl_path:
        print(f"  ERROR: No JSONL log found in {run_dir}/logs/", file=sys.stderr)
        sys.exit(1)
    print(f"  JSONL log: {jsonl_path}")

    # Step 3: Build dataset
    print("  Building dataset from JSONL...")
    bidless_rows, outcomes_rows = build_dataset_from_jsonl(jsonl_path)

    if not bidless_rows:
        print("  ERROR: No valid hand records found in JSONL", file=sys.stderr)
        sys.exit(1)

    bidless_df = pd.DataFrame(bidless_rows)
    outcomes_df = pd.DataFrame(outcomes_rows)

    print(f"  Rows: {len(bidless_df)} bidless, {len(outcomes_df)} outcomes")

    # Step 4: Validate (gate X1)
    validate_dataset(bidless_df, outcomes_df)
    print_partner_feature_stats(bidless_df)

    # Step 5: Write to output directory
    output_dir = Path(args.output_dir)
    datasets_dir = output_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    bidless_path = datasets_dir / "bidless.parquet"
    outcomes_path = datasets_dir / "bidless_outcomes.parquet"

    bidless_df.to_parquet(bidless_path)
    outcomes_df.to_parquet(outcomes_path)

    print(f"\n  Output: {bidless_path}")
    print(f"  Output: {outcomes_path}")
    print(f"  Hands: {outcomes_df.shape[0]}")
    print("  Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Convert JSONL splits to CSV format for model training.

Takes train/val/test JSONL splits (created by split_train_val_test.py) and
converts them to CSV format with one row per player-hand. Each row includes:
- All 40+ hand features
- is_bidder (boolean: 1 if this player won the auction, 0 otherwise)
- contract_type, trump_suit
- actual_tricks (team tricks won)
- deal_id (for tracking)

The resulting CSVs are ready for training bidder-aware regression models.

Usage:
    python experiments/convert_splits_to_csv.py <run_dir>

Example:
    python experiments/convert_splits_to_csv.py \\
        data/runs/bidder_training_data_42_20250103_170000

Output:
    data/training/bidder_aware_train.csv  (~84k rows for 30k hands)
    data/training/bidder_aware_val.csv    (~18k rows)
    data/training/bidder_aware_test.csv   (~18k rows)
"""

import os
import sys
import json
import csv
from typing import List, Dict


def parse_jsonl_to_records(jsonl_path: str) -> List[Dict]:
    """Parse JSONL file and extract player-hand records."""
    records = []

    with open(jsonl_path, 'r') as f:
        for line in f:
            record = json.loads(line)

            # Only process hand_end events
            if record.get('event') != 'hand_end':
                continue

            # Skip misdeals (no bidder)
            if record.get('leader') == -1:
                continue

            # Extract metadata
            deal_id = record['deal_id']
            contract_type = record['contract']
            trump_suit = record.get('trump')
            t0 = record['t0']
            t1 = record['t1']
            bidder_position = record.get('bidder_position')
            dealer_position = record.get('dealer_position')

            # Skip if missing position data (old schema)
            if bidder_position is None or dealer_position is None:
                continue

            # Process all 4 players
            for player_idx in range(4):
                features = record['features'][player_idx]

                # Determine team tricks
                team_tricks = t0 if player_idx in (0, 2) else t1

                # Create player-hand record
                player_record = {
                    'deal_id': deal_id,
                    'player_idx': player_idx,
                    'contract_type': contract_type,
                    'trump_suit': trump_suit if trump_suit else 'none',
                    'is_bidder': 1 if player_idx == bidder_position else 0,
                    'dealer_position': dealer_position,
                    'bidder_position': bidder_position,
                    'actual_tricks': team_tricks,
                }

                # Add all hand features
                player_record.update(features)

                records.append(player_record)

    return records


def convert_split(run_dir: str, split_name: str, output_dir: str) -> Dict:
    """Convert a single split (train/val/test) to CSV."""
    splits_dir = os.path.join(run_dir, "splits")

    # Find JSONL file for this split
    split_files = [
        f for f in os.listdir(splits_dir)
        if f.endswith(f".{split_name}.jsonl")
    ]

    if not split_files:
        raise FileNotFoundError(f"No .{split_name}.jsonl files found in {splits_dir}")

    # We expect only one JSONL file per split for this experiment
    jsonl_path = os.path.join(splits_dir, split_files[0])

    print(f"  Reading: {jsonl_path}")
    records = parse_jsonl_to_records(jsonl_path)
    print(f"  Extracted {len(records):,} player-hand records")

    if len(records) == 0:
        print(f"  ⚠️  No records found in {split_name} split (this is expected if split is empty)")
        return None

    # Determine column order
    first_cols = [
        'deal_id', 'player_idx', 'contract_type', 'trump_suit',
        'is_bidder', 'actual_tricks', 'dealer_position', 'bidder_position'
    ]
    all_keys = set()
    for record in records:
        all_keys.update(record.keys())
    other_cols = sorted(all_keys - set(first_cols))
    column_order = first_cols + other_cols

    # Write CSV
    output_path = os.path.join(output_dir, f"bidder_aware_{split_name}.csv")
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=column_order)
        writer.writeheader()
        writer.writerows(records)

    # Calculate statistics
    bidders = sum(1 for r in records if r['is_bidder'] == 1)
    defenders = len(records) - bidders
    suit_hands = sum(1 for r in records if r['contract_type'] == 'suit')
    high_hands = sum(1 for r in records if r['contract_type'] == 'high')
    low_hands = sum(1 for r in records if r['contract_type'] == 'low')

    stats = {
        'rows': len(records),
        'bidders': bidders,
        'defenders': defenders,
        'suit_hands': suit_hands,
        'high_hands': high_hands,
        'low_hands': low_hands,
        'output_path': output_path
    }

    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python experiments/convert_splits_to_csv.py <run_dir>")
        print("\nExample:")
        print("  python experiments/convert_splits_to_csv.py \\")
        print("      data/runs/bidder_training_data_42_20250103_170000")
        sys.exit(1)

    run_dir = sys.argv[1]

    # Validate run directory
    splits_dir = os.path.join(run_dir, "splits")
    if not os.path.exists(splits_dir):
        print(f"Error: {splits_dir} does not exist.")
        print("Please run split_train_val_test.py first:")
        print(f"  python experiments/split_train_val_test.py {run_dir}")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("📊 Converting JSONL Splits to CSV")
    print("=" * 80)
    print(f"Run directory: {run_dir}\n")

    # Create output directory
    output_dir = "data/training"
    os.makedirs(output_dir, exist_ok=True)

    # Convert each split
    split_stats = {}

    for split_name in ['train', 'val', 'test']:
        print(f"\n{split_name.upper()} Split:")
        print("-" * 80)

        try:
            stats = convert_split(run_dir, split_name, output_dir)

            if stats is None:
                continue

            split_stats[split_name] = stats

            print(f"  ✅ Saved to: {stats['output_path']}")
            print(f"  Rows: {stats['rows']:,}")
            print(f"  Bidders: {stats['bidders']:,} ({stats['bidders']/stats['rows']*100:.1f}%)")
            print(f"  Defenders: {stats['defenders']:,} ({stats['defenders']/stats['rows']*100:.1f}%)")

        except Exception as e:
            print(f"  ❌ Error converting {split_name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Print summary
    print("\n" + "=" * 80)
    print("📈 Summary")
    print("=" * 80)

    total_rows = sum(stats['rows'] for stats in split_stats.values())
    total_bidders = sum(stats['bidders'] for stats in split_stats.values())
    total_defenders = sum(stats['defenders'] for stats in split_stats.values())

    print(f"\nTotal records: {total_rows:,}")
    print(f"  Train: {split_stats.get('train', {}).get('rows', 0):,} ({split_stats.get('train', {}).get('rows', 0)/total_rows*100:.1f}%)")
    print(f"  Val:   {split_stats.get('val', {}).get('rows', 0):,} ({split_stats.get('val', {}).get('rows', 0)/total_rows*100:.1f}%)")
    print(f"  Test:  {split_stats.get('test', {}).get('rows', 0):,} ({split_stats.get('test', {}).get('rows', 0)/total_rows*100:.1f}%)")

    print("\nBidder/Defender split:")
    print(f"  Bidders:   {total_bidders:,} ({total_bidders/total_rows*100:.1f}%)")
    print(f"  Defenders: {total_defenders:,} ({total_defenders/total_rows*100:.1f}%)")

    print("\nContract distribution (train):")
    if 'train' in split_stats:
        train_total = split_stats['train']['rows']
        print(f"  Suit: {split_stats['train']['suit_hands']:,} ({split_stats['train']['suit_hands']/train_total*100:.1f}%)")
        print(f"  High: {split_stats['train']['high_hands']:,} ({split_stats['train']['high_hands']/train_total*100:.1f}%)")
        print(f"  Low:  {split_stats['train']['low_hands']:,} ({split_stats['train']['low_hands']/train_total*100:.1f}%)")

    print("\n" + "=" * 80)
    print("✅ Conversion complete!")
    print("=" * 80)
    print("\nOutput files:")
    print(f"  {output_dir}/bidder_aware_train.csv")
    print(f"  {output_dir}/bidder_aware_val.csv")
    print(f"  {output_dir}/bidder_aware_test.csv")

    print("\n🎯 Next step: Train bidder-aware models")
    print("  PYTHONPATH=src python experiments/train_bidder_models.py")
    print("=" * 80)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Split JSONL hand logs into train/val/test sets.

Usage:
    python experiments/split_train_val_test.py <run_dir>

Splits by deal_id:
- train: 0-34999 (70%)
- val: 35000-42499 (15%)
- test: 42500-49999 (15%)
"""

import json
import os
import sys
import glob


def split_name(deal_id: int, n_per: int = 50000) -> str:
    """Determine split name based on deal_id."""
    train_cutoff = int(n_per * 0.70)
    val_cutoff = int(n_per * 0.85)
    
    if deal_id < train_cutoff:
        return "train"
    if deal_id < val_cutoff:
        return "val"
    return "test"


def split_jsonl_logs(run_dir: str):
    """Split all JSONL logs in run_dir/logs/ into train/val/test."""
    logs_dir = os.path.join(run_dir, "logs")
    out_dir = os.path.join(run_dir, "splits")
    
    if not os.path.exists(logs_dir):
        print(f"Error: {logs_dir} does not exist")
        return
    
    os.makedirs(out_dir, exist_ok=True)
    
    for path in glob.glob(os.path.join(logs_dir, "*.jsonl")):
        base = os.path.splitext(os.path.basename(path))[0]
        print(f"\nProcessing: {base}")
        
        # Open output files
        outs = {
            k: open(os.path.join(out_dir, f"{base}.{k}.jsonl"), "w")
            for k in ("train", "val", "test")
        }
        counts = {k: 0 for k in outs}
        
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                
                rec = json.loads(line)
                
                # Keep run_start/run_end in all splits
                if rec.get("event") in ("run_start", "run_end"):
                    for k in outs:
                        outs[k].write(line)
                    continue
                
                # Skip non-hand_end events
                if rec.get("event") != "hand_end":
                    continue
                
                deal_id = rec.get("deal_id")
                if deal_id is None:
                    continue
                
                k = split_name(int(deal_id))
                outs[k].write(line)
                counts[k] += 1
        
        # Close files
        for fh in outs.values():
            fh.close()
        
        print(f"  train: {counts['train']:,} hands")
        print(f"  val:   {counts['val']:,} hands")
        print(f"  test:  {counts['test']:,} hands")
        print(f"  total: {sum(counts.values()):,} hands")
    
    print(f"\n✅ Split logs written to: {out_dir}/")
    return out_dir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python experiments/split_train_val_test.py <run_dir>")
        sys.exit(1)
    
    run_dir = sys.argv[1]
    split_jsonl_logs(run_dir)

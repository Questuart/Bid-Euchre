#!/usr/bin/env python3
"""
Generate reports from a specific data split (train/val/test).

Creates a temporary directory structure with only the specified split's logs,
generates reports, then moves them to a split-specific subdirectory.

Usage:
    python experiments/generate_reports_from_split.py <run_dir> <split_name>
    
Example:
    python experiments/generate_reports_from_split.py \\
        data/runs/hand_eval_test_random_42_20251217_195516 train
"""

import os
import sys
import shutil
import tempfile
import subprocess


def generate_reports_from_split(run_dir: str, split_name: str):
    """Generate reports using only the specified split (train/val/test)."""
    splits_dir = os.path.join(run_dir, "splits")
    
    if not os.path.exists(splits_dir):
        print(f"Error: {splits_dir} does not exist. Run split_train_val_test.py first.")
        sys.exit(1)
    
    # Create temporary run directory with split logs
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_run_dir = os.path.join(temp_dir, "temp_run")
        temp_logs_dir = os.path.join(temp_run_dir, "logs")
        os.makedirs(temp_logs_dir, exist_ok=True)
        
        # Copy split logs to temp logs directory
        print(f"Setting up temporary directory with {split_name} split...")
        for split_file in os.listdir(splits_dir):
            if split_file.endswith(f".{split_name}.jsonl"):
                src = os.path.join(splits_dir, split_file)
                # Remove split suffix for the temp file
                dst_name = split_file.replace(f".{split_name}.jsonl", ".jsonl")
                dst = os.path.join(temp_logs_dir, dst_name)
                shutil.copy2(src, dst)
                print(f"  Copied: {split_file} -> {dst_name}")
        
        # Copy meta.json if it exists
        meta_src = os.path.join(run_dir, "meta.json")
        if os.path.exists(meta_src):
            shutil.copy2(meta_src, os.path.join(temp_run_dir, "meta.json"))
        
        # Generate hand eval dashboard
        print(f"\nGenerating hand evaluation dashboard from {split_name} split...")
        cmd = [
            "python", "experiments/generate_hand_eval_dashboard.py",
            "--run-dir", temp_run_dir
        ]
        
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode != 0:
            print("Error generating dashboard:")
            print(result.stderr)
            sys.exit(1)
        
        print(result.stdout)
        
        # Move generated reports to split-specific directory in original run
        temp_reports = os.path.join(temp_run_dir, "reports")
        if os.path.exists(temp_reports):
            split_reports_dir = os.path.join(run_dir, "reports", f"{split_name}_only")
            os.makedirs(split_reports_dir, exist_ok=True)
            
            # Copy bidding_strategy reports
            temp_bidding = os.path.join(temp_reports, "bidding_strategy")
            if os.path.exists(temp_bidding):
                dst_bidding = os.path.join(split_reports_dir, "bidding_strategy")
                if os.path.exists(dst_bidding):
                    shutil.rmtree(dst_bidding)
                shutil.copytree(temp_bidding, dst_bidding)
                print(f"\n✅ Reports saved to: {dst_bidding}/")
                print(f"   Dashboard: {os.path.join(dst_bidding, 'hand_eval_dashboard.png')}")
                print(f"   Summary: {os.path.join(dst_bidding, 'summary.md')}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python experiments/generate_reports_from_split.py <run_dir> <split_name>")
        print("  split_name: train, val, or test")
        sys.exit(1)
    
    run_dir = sys.argv[1]
    split_name = sys.argv[2]
    
    if split_name not in ("train", "val", "test"):
        print(f"Error: split_name must be 'train', 'val', or 'test' (got '{split_name}')")
        sys.exit(1)
    
    generate_reports_from_split(run_dir, split_name)

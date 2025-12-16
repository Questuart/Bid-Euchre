#!/usr/bin/env python3
"""
Unified Experiment Runner for Bid Euchre Simulations.

This script runs experiments defined in YAML configuration files.
It handles multiple strategies × scenarios with standardized output structure.

Usage:
    PYTHONPATH=src python experiments/run_experiment.py \\
        --config experiments/configs/baseline_greedy.yaml

    PYTHONPATH=src python experiments/run_experiment.py \\
        --config experiments/configs/strategy_comparison.yaml \\
        --n_per 50000 --seed 42

Features:
- Loads experiment configuration from YAML
- Runs all strategies × scenarios with common deals
- Records runtime and throughput metrics
- Saves standardized output to data/runs/<run_id>/
- Generates meta.json with complete metadata

Output Structure:
    data/runs/<experiment_name>_<seed>_<timestamp>/
    ├── meta.json                   # Experiment metadata + performance
    ├── results/
    │   └── <strategy>/
    │       ├── suit_C.json
    │       ├── suit_D.json
    │       ├── high.json
    │       └── low.json
    └── logs/
        └── <run_id>_<strategy>.jsonl
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import Dict, Any, List

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim import simulation
from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.experiments import load_config


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run Bid Euchre experiments from YAML config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--n_per", "-n",
        type=int,
        help="Override: number of hands per scenario"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        help="Override: random seed for reproducible results"
    )
    parser.add_argument(
        "--log-level",
        choices=["none", "hand", "trick"],
        help="Override: JSONL logging level"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default="data/runs",
        help="Base directory for run outputs (default: data/runs)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration and exit without running"
    )
    return parser.parse_args()


def scenario_filename(contract_type: str, trump_suit: str | None) -> str:
    """Generate standardized filename for scenario results."""
    if contract_type == "suit":
        return f"suit_{trump_suit}.json"
    return f"{contract_type}.json"


def save_results(results: Dict[str, Any], out_path: str) -> str:
    """Save scenario results to JSON file."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    return out_path


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def main():
    args = parse_args()
    
    # Load configuration
    print(f"📄 Loading configuration: {args.config}")
    config = load_config(args.config)
    
    # Apply command-line overrides
    n_per = args.n_per if args.n_per is not None else config.parameters.get("n_per", 50000)
    seed = args.seed if args.seed is not None else config.parameters.get("seed")
    log_level_str = args.log_level if args.log_level else config.parameters.get("log_level", "none")
    
    # Get strategies and scenarios
    strategies = config.get_strategies()
    scenarios = config.get_scenario_configs()
    
    # Print experiment summary
    print("\n" + "=" * 70)
    print(f"🚀 Experiment: {config.experiment_name}")
    print("=" * 70)
    print(f"Strategies: {', '.join(s.name for s in strategies)}")
    print(f"Scenarios: {len(scenarios)} ({', '.join(s.contract_type + ('-' + s.trump_suit if s.trump_suit else '') for s in scenarios[:3])}{'...' if len(scenarios) > 3 else ''})")
    print(f"Hands per scenario: {n_per:,}")
    print(f"Random seed: {seed if seed is not None else 'None (random)'}")
    print(f"Log level: {log_level_str}")
    print(f"Total hands to simulate: {len(strategies) * len(scenarios) * n_per:,}")
    print(f"Common deals: {'Yes' if seed is not None else 'No (random deals)'}")
    print("=" * 70)
    
    if args.dry_run:
        print("\n✅ Dry run complete. Configuration valid.")
        return
    
    # Create run directory structure
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_str = str(seed) if seed is not None else "random"
    run_id = f"{config.experiment_name}_{seed_str}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    results_dir = os.path.join(run_dir, "results")
    logs_dir = os.path.join(run_dir, "logs")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    print(f"\n📁 Run directory: {run_dir}\n")
    
    # Track performance metrics
    start_time = time.time()
    scenario_metrics = []
    
    # Run all strategies × scenarios
    for strategy in strategies:
        print("-" * 70)
        print(f"Strategy: {strategy.name}")
        print("-" * 70)
        
        # Set up logging
        logger = None
        if log_level_str != "none":
            log_level = LogLevel(log_level_str)
            logger = GameLogger(
                run_id=f"{run_id}_{strategy.name}",
                strategy_id=strategy.name,
                level=log_level,
                output_dir=logs_dir,
            )
            logger.open()
            print(f"📝 Logging to: {logs_dir}/{logger.run_id}.jsonl")
        
        try:
            for i, scenario in enumerate(scenarios, 1):
                # Generate deterministic seed per scenario
                scenario_seed = seed + (i - 1) if seed is not None else None
                
                label = scenario.contract_type
                if scenario.trump_suit:
                    label += f" ({scenario.trump_suit})"
                
                print(f"\n[{i}/{len(scenarios)}] {label} - {n_per:,} hands", end="")
                if scenario_seed is not None:
                    print(f" (deal_seed={scenario_seed})")
                else:
                    print()
                
                # Time the scenario
                scenario_start = time.time()
                
                # Run simulation
                results = simulation.simulate_many_hands(
                    n=n_per,
                    contract_type=scenario.contract_type,
                    trump_suit=scenario.trump_suit,
                    seed=None,  # Don't touch global RNG
                    deal_seed=scenario_seed,  # Use for deterministic deals
                    strategy=strategy,
                    logger=logger,
                )
                
                scenario_duration = time.time() - scenario_start
                hands_per_sec = n_per / scenario_duration if scenario_duration > 0 else 0
                
                # Save results
                out_path = os.path.join(
                    results_dir,
                    strategy.name,
                    scenario_filename(scenario.contract_type, scenario.trump_suit)
                )
                save_results(results, out_path)
                
                # Print summary
                team0_avg = results["avg_team0"]
                team1_avg = results["avg_team1"]
                win_hands = sum(
                    count
                    for tricks, count in results["distribution_team0"].items()
                    if int(tricks) >= 6
                )
                win_rate = win_hands / results["hands"] * 100
                
                print(f"  Team0: {team0_avg:.2f}  Team1: {team1_avg:.2f}  Win: {win_rate:.1f}%")
                print(f"  Performance: {format_duration(scenario_duration)}, {hands_per_sec:.0f} hands/sec")
                
                # Record metrics
                scenario_metrics.append({
                    "strategy": strategy.name,
                    "scenario": label,
                    "duration_sec": round(scenario_duration, 2),
                    "hands_per_sec": round(hands_per_sec, 1),
                    "total_hands": n_per,
                })
        
        finally:
            if logger:
                logger.close()
    
    # Calculate total metrics
    total_duration = time.time() - start_time
    total_hands = len(strategies) * len(scenarios) * n_per
    overall_throughput = total_hands / total_duration if total_duration > 0 else 0
    
    # Write metadata (experiment config + results summary)
    meta = {
        "run_id": run_id,
        "experiment_name": config.experiment_name,
        "timestamp": timestamp,
        "seed": seed,
        "n_per": n_per,
        "log_level": log_level_str,
        "scenarios": [
            {"contract_type": s.contract_type, "trump_suit": s.trump_suit}
            for s in scenarios
        ],
        "strategies": [s.name for s in strategies],
        "leader_randomized": True,  # Always true with new deal generator
        "common_deals": seed is not None,  # Only true if seed provided
        "total_hands": total_hands,
    }
    
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    
    # Write performance metrics to separate file
    perf = {
        "run_id": run_id,
        "total_duration_sec": round(total_duration, 2),
        "total_duration_human": format_duration(total_duration),
        "overall_throughput_hands_per_sec": round(overall_throughput, 1),
        "total_hands": total_hands,
        "by_scenario": scenario_metrics,
    }
    
    with open(os.path.join(run_dir, "perf.json"), "w") as f:
        json.dump(perf, f, indent=2)
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ Experiment completed!")
    print("=" * 70)
    print(f"📁 Results: {run_dir}/")
    print(f"⏱️  Duration: {format_duration(total_duration)}")
    print(f"🚀 Throughput: {overall_throughput:.0f} hands/sec")
    print(f"📊 Generated {len(strategies) * len(scenarios)} result files")
    
    print("\n🎯 Next steps:")
    print(f"   # Generate all reports:")
    print(f"   PYTHONPATH=src python experiments/generate_all_reports.py \\")
    print(f"       --run-dir {run_dir}")
    print()
    
    # Auto-generate reports if logs were created
    if log_level_str != "none":
        print("📊 Auto-generating reports...")
        try:
            import subprocess
            result = subprocess.run(
                ["python", "experiments/generate_all_reports.py", "--run-dir", run_dir],
                env={**os.environ, "PYTHONPATH": "src"},
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Reports generated automatically!")
            else:
                print("⚠️  Report generation encountered issues (run manually)")
        except Exception as e:
            print(f"⚠️  Could not auto-generate reports: {e}")
            print(f"   Run manually: PYTHONPATH=src python experiments/generate_all_reports.py --run-dir {run_dir}")
        print()


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Head-to-Head Matchup Runner for Bid Euchre.

Runs head-to-head matchups between strategies on common deals.
Designed for testing "does strategy X beat strategy Y?"

Usage:
    PYTHONPATH=src python experiments/run_head_to_head.py \\
        --config experiments/configs/head_to_head_vs_random.yaml

Output Structure:
    data/runs/<experiment_name>_<seed>_<timestamp>/
    ├── meta.json                    # Experiment metadata
    ├── perf.json                    # Performance metrics
    ├── results/
    │   ├── greedy_vs_random/        # One folder per matchup
    │   │   ├── suit_C.json
    │   │   └── ...
    │   └── random_vs_greedy/
    │       └── ...
    ├── logs/
    │   ├── <run_id>_greedy_vs_random.jsonl
    │   └── ...
    └── reports/
        ├── summary.md               # Key findings
        ├── comparison_matrix.png    # Win rate matrix
        └── matchups/
            ├── greedy_vs_random.png
            └── ...
"""

import os
import sys
import json
import time
import yaml
import argparse
from datetime import datetime
from typing import Dict, Any, List, Tuple

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim import simulation
from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.experiments import load_config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run head-to-head matchups from YAML config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        required=True,
        help="Path to YAML configuration file with matchups"
    )
    parser.add_argument(
        "--n_per", "-n",
        type=int,
        help="Override: number of hands per scenario"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        help="Override: random seed"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default="data/runs",
        help="Base directory for outputs (default: data/runs)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configuration and exit"
    )
    return parser.parse_args()


def scenario_filename(contract_type: str, trump_suit: str | None) -> str:
    """Generate standardized filename for scenario results."""
    if contract_type == "suit":
        return f"suit_{trump_suit}.json"
    return f"{contract_type}.json"


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
    
    # Load config
    print(f"📄 Loading configuration: {args.config}")
    config = load_config(args.config)
    
    # Load full YAML to get matchups (not in ExperimentConfig yet)
    with open(args.config, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    matchups = raw_config.get("matchups", [])
    if not matchups:
        raise ValueError("No matchups defined in config. Add 'matchups:' section.")
    
    # Apply overrides
    n_per = args.n_per if args.n_per is not None else config.parameters.get("n_per", 50000)
    seed = args.seed if args.seed is not None else config.parameters.get("seed", 42)
    log_level_str = config.parameters.get("log_level", "hand")
    
    # Get strategies and scenarios
    strategy_cfgs = {sc.name: sc for sc in config.strategies}
    scenarios = config.get_scenario_configs()
    
    # Print experiment summary
    print("\n" + "=" * 70)
    print(f"🥊 Head-to-Head Matchups: {config.experiment_name}")
    print("=" * 70)
    print(f"Matchups: {len(matchups)}")
    for m in matchups:
        print(f"  • {m['team0']} vs {m['team1']}")
    print(f"Scenarios: {len(scenarios)}")
    print(f"Hands per scenario: {n_per:,}")
    print(f"Random seed: {seed}")
    print(f"Total hands: {len(matchups) * len(scenarios) * n_per:,}")
    print("=" * 70)
    
    if args.dry_run:
        print("\n✅ Dry run complete.")
        return
    
    # Create run directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{config.experiment_name}_{seed}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    results_dir = os.path.join(run_dir, "results")
    logs_dir = os.path.join(run_dir, "logs")
    reports_dir = os.path.join(run_dir, "reports")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    
    print(f"\n📁 Run directory: {run_dir}\n")
    
    # Track performance
    start_time = time.time()
    scenario_metrics = []
    matchup_results = []
    
    # Run each matchup
    for matchup_idx, matchup in enumerate(matchups, 1):
        team0_name = matchup["team0"]
        team1_name = matchup["team1"]
        matchup_name = f"{team0_name}_vs_{team1_name}"
        
        print("-" * 70)
        print(f"Matchup {matchup_idx}/{len(matchups)}: {team0_name} vs {team1_name}")
        print("-" * 70)
        
        # Get strategy configs
        team0_cfg = strategy_cfgs[team0_name]
        team1_cfg = strategy_cfgs[team1_name]
        
        # Create seat strategies (team0 on seats 0&2, team1 on seats 1&3)
        def _clone(cfg, seat_idx: int):
            cfg_params = dict(cfg.params or {})
            if cfg.class_name == "RandomLegalStrategy":
                cfg_params["seed"] = (seed + seat_idx) if seed is not None else None
            from bid_euchre.experiments.config import StrategyConfig
            return StrategyConfig(name=cfg.name, class_name=cfg.class_name, params=cfg_params).create_strategy()
        
        seat_strategies = [
            _clone(team0_cfg, 0),  # Seat 0: Team 0
            _clone(team1_cfg, 1),  # Seat 1: Team 1
            _clone(team0_cfg, 2),  # Seat 2: Team 0
            _clone(team1_cfg, 3),  # Seat 3: Team 1
        ]
        
        # Set up logging
        logger = None
        if log_level_str != "none":
            log_level = LogLevel(log_level_str)
            logger = GameLogger(
                run_id=f"{run_id}_{matchup_name}",
                strategy_id=matchup_name,
                level=log_level,
                output_dir=logs_dir,
            )
            logger.open()
        
        try:
            matchup_start = time.time()
            
            for i, scenario in enumerate(scenarios, 1):
                scenario_seed = seed + (i - 1) if seed is not None else None
                
                label = scenario.contract_type
                if scenario.trump_suit:
                    label += f" ({scenario.trump_suit})"
                
                print(f"\n[{i}/{len(scenarios)}] {label} - {n_per:,} hands", end="")
                if scenario_seed is not None:
                    print(f" (seed={scenario_seed})")
                else:
                    print()
                
                scenario_start = time.time()
                
                # Run simulation
                results = simulation.simulate_many_hands(
                    n=n_per,
                    contract_type=scenario.contract_type,
                    trump_suit=scenario.trump_suit,
                    seed=None,
                    deal_seed=scenario_seed,
                    strategy=None,
                    strategies=seat_strategies,
                    logger=logger,
                )
                
                scenario_duration = time.time() - scenario_start
                hands_per_sec = n_per / scenario_duration if scenario_duration > 0 else 0
                
                # Save results
                out_path = os.path.join(
                    results_dir,
                    matchup_name,
                    scenario_filename(scenario.contract_type, scenario.trump_suit)
                )
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                with open(out_path, "w") as f:
                    json.dump(results, f, indent=2)
                
                # Print summary
                team0_avg = results["avg_team0"]
                team1_avg = results["avg_team1"]
                win_hands = sum(
                    count for tricks, count in results["distribution_team0"].items()
                    if int(tricks) >= 6
                )
                win_rate = win_hands / results["hands"] * 100
                
                print(f"  {team0_name}: {team0_avg:.2f}  {team1_name}: {team1_avg:.2f}  Team0 Win: {win_rate:.1f}%")
                print(f"  Performance: {format_duration(scenario_duration)}, {hands_per_sec:.0f} hands/sec")
                
                scenario_metrics.append({
                    "matchup": matchup_name,
                    "scenario": label,
                    "duration_sec": round(scenario_duration, 2),
                    "hands_per_sec": round(hands_per_sec, 1),
                })
            
            matchup_duration = time.time() - matchup_start
            matchup_results.append({
                "matchup": matchup_name,
                "team0": team0_name,
                "team1": team1_name,
                "duration_sec": round(matchup_duration, 2),
            })
        
        finally:
            if logger:
                logger.close()
    
    # Calculate total metrics
    total_duration = time.time() - start_time
    total_hands = len(matchups) * len(scenarios) * n_per
    overall_throughput = total_hands / total_duration if total_duration > 0 else 0
    
    # Write metadata
    meta = {
        "run_id": run_id,
        "experiment_name": config.experiment_name,
        "timestamp": timestamp,
        "mode": "head_to_head_matrix",
        "seed": seed,
        "n_per": n_per,
        "log_level": log_level_str,
        "matchups": matchup_results,
        "scenarios": [
            {"contract_type": s.contract_type, "trump_suit": s.trump_suit}
            for s in scenarios
        ],
        "common_deals": True,
        "leader_randomized": True,
        "total_hands": total_hands,
    }
    
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    
    # Write performance metrics
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
    print("✅ Head-to-Head Experiment Completed!")
    print("=" * 70)
    print(f"📁 Results: {run_dir}/")
    print(f"⏱️  Duration: {format_duration(total_duration)}")
    print(f"🚀 Throughput: {overall_throughput:.0f} hands/sec")
    print(f"📊 Matchups: {len(matchups)}")
    
    print("\n🎯 Next steps:")
    print(f"   # Generate head-to-head reports:")
    print(f"   PYTHONPATH=src python experiments/generate_head_to_head_report.py \\")
    print(f"       --run-dir {run_dir}")
    print()


if __name__ == "__main__":
    main()


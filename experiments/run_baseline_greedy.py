import json
import os
import argparse
from datetime import datetime
from typing import Dict, Any

from bid_euchre.sim import simulation
from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.strategy import BasicStrategy, GreedyStrategy
try:
    from bid_euchre.experiments import load_config, create_experiment
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run baseline greedy simulations for all contract types")
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to YAML configuration file"
    )
    parser.add_argument(
        "--n_per", "-n",
        type=int,
        default=50000,
        help="Number of hands per scenario (default: 50000)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducible results (default: None)"
    )
    parser.add_argument(
        "--output_dir", "-o",
        type=str,
        default=None,
        help="(Deprecated) Output directory for results. Prefer per-run layout under data/runs/."
    )
    parser.add_argument(
        "--log-level",
        choices=["none", "hand", "trick"],
        default="none",
        help="JSONL logging level: none (default), hand (per-hand), trick (per-trick)"
    )
    parser.add_argument(
        "--log-dir",
        default="logs",
        help="Directory for JSONL log files (default: logs)"
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default="data/runs",
        help="Base directory for run outputs (default: data/runs)"
    )
    return parser.parse_args()

def run_scenario(contract_type, trump_suit, n_hands=50_000, base_seed=None, scenario_index=0, strategy=None, logger=None):
    """Run simulation for a specific scenario and return results."""
    print(f"Running {contract_type} {'('+trump_suit+')' if trump_suit else ''} - {n_hands:,} hands...")

    # Use base_seed + scenario_index for reproducible per-scenario seeds
    scenario_seed = base_seed + scenario_index if base_seed is not None else None
    if scenario_seed is not None:
        print(f"  Using random seed: {scenario_seed}")

    results = simulation.simulate_many_hands(
        n=n_hands,
        contract_type=contract_type,
        trump_suit=trump_suit,
        seed=scenario_seed,
        strategy=strategy,
        logger=logger,
    )

    return results

def scenario_filename(contract_type: str, trump_suit: str | None) -> str:
    if contract_type == "suit":
        return f"suit_{trump_suit}.json"
    return f"{contract_type}.json"


def save_results(results: Dict[str, Any], out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"  → Saved to: {out_path}")
    return out_path

def main():
    args = parse_args()

    # Load configuration or create default
    if HAS_CONFIG and args.config:
        config = load_config(args.config)
        print(f"Loaded configuration: {args.config}")
    elif HAS_CONFIG:
        # Create default configuration
        config = create_experiment(
            name="baseline_greedy",
            strategy_names=["greedy"],
            contract_types=["suit", "high", "low"],
            trump_suits=["C", "D", "H", "S"],
            n_per=args.n_per,
            seed=args.seed
        )
        print("Using default baseline greedy configuration")
    else:
        # Fallback to simple config when YAML not available
        print("Using fallback configuration (YAML not available)")
        from bid_euchre.strategy import GreedyStrategy

        class FallbackConfig:
            def __init__(self):
                self.experiment_name = 'baseline_greedy_fallback'
                self.strategies = [GreedyStrategy()]
                self.parameters = {'n_per': args.n_per, 'seed': args.seed}

            def get_strategies(self):
                return self.strategies

            def get_scenario_configs(self):
                # Return scenario configs as objects with contract_type and trump_suit
                class Scenario:
                    def __init__(self, contract_type, trump_suit):
                        self.contract_type = contract_type
                        self.trump_suit = trump_suit

                scenarios = []
                scenarios.append(Scenario("high", None))
                scenarios.append(Scenario("low", None))
                for suit in ["C", "D", "H", "S"]:
                    scenarios.append(Scenario("suit", suit))
                return scenarios

        config = FallbackConfig()

    # Create run_id and directory layout:
    # data/runs/<run_id>/{meta.json,results/<strategy>/<scenario>.json,logs/<strategy>.jsonl}
    seed = args.seed if args.seed is not None else config.parameters.get("seed")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"{config.experiment_name}_{seed if seed is not None else 'random'}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    results_dir = os.path.join(run_dir, "results")
    logs_dir = os.path.join(run_dir, "logs")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)

    # Get scenarios from config
    scenarios = []
    for scenario_config in config.get_scenario_configs():
        scenarios.append((scenario_config.contract_type, scenario_config.trump_suit))

    # Override config parameters with command line args if provided
    n_per = args.n_per if args.n_per != 50000 else config.parameters.get("n_per", 50000)

    print("🚀 Starting comprehensive baseline greedy simulation")
    print("=" * 60)
    print(f"Experiment: {config.experiment_name}")
    print(f"Strategies: {', '.join(s.name for s in config.strategies)}")
    print(f"Parameters:")
    print(f"  Hands per scenario: {n_per:,}")
    print(f"  Random seed: {seed if seed is not None else 'None (random)'}")
    print(f"  Run directory: {run_dir}")
    print(f"  Log level: {args.log_level}")
    print(f"  Scenarios to run: {len(scenarios)}")
    print(f"  Total hands to simulate: {len(scenarios) * n_per:,}")
    print("=" * 60)

    # Get strategies from config (support multiple strategies)
    strategies = config.get_strategies() if config.strategies else [GreedyStrategy()]

    # Write meta.json
    meta = {
        "run_id": run_id,
        "experiment_name": config.experiment_name,
        "seed": seed,
        "n_per": n_per,
        "log_level": args.log_level,
        "timestamp": timestamp,
        "scenarios": [{"contract_type": c, "trump_suit": t} for (c, t) in scenarios],
        "strategies": [s.name for s in strategies],
        "leader_randomized": True,
        "common_deals": True,
    }
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    try:
        # Run all scenarios for all strategies (common deals via deal_seed)
        saved_files = []
        for strat in strategies:
            print("\n" + "-" * 60)
            print(f"Strategy: {strat.name}")
            print("-" * 60)

            # Set up logging per strategy if requested (write into run_dir/logs)
            logger = None
            if args.log_level != "none":
                log_level = LogLevel(args.log_level)
                logger = GameLogger(
                    run_id=f"{run_id}_{strat.name}",
                    strategy_id=strat.name,
                    level=log_level,
                    output_dir=logs_dir,
                )
                logger.open()
                print(f"📝 Logging to: {logs_dir}/{logger.run_id}.jsonl")

            try:
                for i, (contract_type, trump_suit) in enumerate(scenarios, 1):
                    print(f"\n[{i}/{len(scenarios)}] ", end="")
                    scenario_seed = seed + (i - 1) if seed is not None else None
                    if scenario_seed is not None:
                        print(f"Running {contract_type} {'('+trump_suit+')' if trump_suit else ''} - {n_per:,} hands...  (deal_seed={scenario_seed})")
                    else:
                        print(f"Running {contract_type} {'('+trump_suit+')' if trump_suit else ''} - {n_per:,} hands...")

                    results = simulation.simulate_many_hands(
                        n=n_per,
                        contract_type=contract_type,
                        trump_suit=trump_suit,
                        seed=None,  # do not touch global RNG; use deal_seed for reproducibility
                        deal_seed=scenario_seed,
                        strategy=strat,
                        logger=logger,
                    )

                    out_path = os.path.join(results_dir, strat.name, scenario_filename(contract_type, trump_suit))
                    saved_path = save_results(results, out_path)

                    team0_avg = results["avg_team0"]
                    team1_avg = results["avg_team1"]
                    print(f"  Team0: {team0_avg:.1f}  Team1: {team1_avg:.1f}")
                    win_hands = sum(count for tricks, count in results["distribution_team0"].items() if int(tricks) >= 6)
                    win_rate = win_hands / results["hands"] * 100
                    print(f"  Win rate: {win_rate:.1f}%")
                    saved_files.append(saved_path)
            finally:
                if logger:
                    logger.close()

        print("\n" + "=" * 60)
        print("✅ All simulations completed!")
        print(f"📁 Run saved to: {run_dir}/")
        print(f"📊 Generated {len(saved_files)} result files:")
        for file in saved_files:
            print(f"   • {os.path.basename(file)}")
        print("\n🎯 Next: Run dashboard:")
        print(f"   PYTHONPATH=src python experiments/generate_dashboard.py --run-dir {run_dir} --strategy greedy --seed {seed if seed is not None else ''}".rstrip())
    finally:
        pass

if __name__ == "__main__":
    main()

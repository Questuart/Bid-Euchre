import json
import os
import sys
import argparse

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim import simulation
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
        default="data/raw",
        help="Output directory for results (default: data/raw)"
    )
    return parser.parse_args()

def run_scenario(contract_type, trump_suit, n_hands=50_000, base_seed=None, scenario_index=0, strategy=None):
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
    )

    return results

def save_results(results, contract_type, trump_suit, out_dir):
    """Save results to appropriate JSON file."""
    if contract_type == "suit":
        filename = f"baseline_greedy_suit_{trump_suit}.json"
    else:
        filename = f"baseline_greedy_{contract_type}.json"

    out_path = os.path.join(out_dir, filename)
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

    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)

    # Get scenarios from config
    scenarios = []
    for scenario_config in config.get_scenario_configs():
        scenarios.append((scenario_config.contract_type, scenario_config.trump_suit))

    # Override config parameters with command line args if provided
    n_per = args.n_per if args.n_per != 50000 else config.parameters.get("n_per", 50000)
    seed = args.seed if args.seed is not None else config.parameters.get("seed")

    print("🚀 Starting comprehensive baseline greedy simulation")
    print("=" * 60)
    print(f"Experiment: {config.experiment_name}")
    print(f"Strategies: {', '.join(s.name for s in config.strategies)}")
    print(f"Parameters:")
    print(f"  Hands per scenario: {n_per:,}")
    print(f"  Random seed: {seed if seed is not None else 'None (random)'}")
    print(f"  Output directory: {out_dir}")
    print(f"  Scenarios to run: {len(scenarios)}")
    print(f"  Total hands to simulate: {len(scenarios) * n_per:,}")
    print("=" * 60)

    # Get the strategy from config (assuming single strategy for now)
    strategy = config.get_strategies()[0] if config.strategies else None

    # Run all scenarios
    saved_files = []
    for i, (contract_type, trump_suit) in enumerate(scenarios, 1):
        print(f"\n[{i}/{len(scenarios)}] ", end="")

        # Run the simulation
        results = run_scenario(contract_type, trump_suit, n_per, seed, i-1, strategy)

        # Save results
        saved_path = save_results(results, contract_type, trump_suit, out_dir)

        # Print summary stats
        team0_avg = results['avg_team0']
        team1_avg = results['avg_team1']
        print(f"{team0_avg:.1f} {team1_avg:.1f}")

        # Calculate win rate (6+ tricks)
        win_hands = sum(count for tricks, count in results['distribution_team0'].items() if int(tricks) >= 6)
        win_rate = win_hands / results['hands'] * 100
        print(f"{win_rate:.1f}")

        saved_files.append(saved_path)

    print("\n" + "=" * 60)
    print("✅ All simulations completed!")
    print(f"📁 Results saved to: {out_dir}/")
    print(f"📊 Generated {len(saved_files)} data files:")
    for file in saved_files:
        print(f"   • {os.path.basename(file)}")
    print("\n🎯 Next: Run analysis with make_phase1.5_report.py to visualize all results")

if __name__ == "__main__":
    main()

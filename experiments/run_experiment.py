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

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.datasets.bidding import emit_bidding_dataset
from bid_euchre.datasets.bidless import BidlessDatasetCollector, emit_bidless_dataset
from bid_euchre.experiments import load_config
from bid_euchre.experiments.meta import get_git_sha, sha256_file, utc_now_iso
from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.sim import simulation
from bid_euchre.sim.hooks import HandEndEvent, SimulationHooks

# Metadata schema version
META_JSON_SCHEMA_VERSION = 2  # v2: add created_at_utc, git_sha, config_path, config_sha256

# Maximum total hands by config
# Note: total_hands = plan_count * len(scenarios) * n_per
# where plan_count accounts for mode (matrix vs head_to_head, bidding policies, etc.)
TOTAL_HANDS_BUDGETS = {
    "quick_test": 1_000,
    "baseline_tiny": 50_000,
    "baseline_full": 5_000_000,
}


def check_total_hands_budget(config_name: str, total_hands: int, force: bool = False):
    """Enforce total hands budget to prevent accidental expensive runs.

    Args:
        config_name: Config name (e.g., "quick_test")
        total_hands: Total hands computed by runner (plan_count × scenarios × n_per)
        force: If True, skip budget check

    Raises:
        ValueError: If budget exceeded and not forced
    """
    if force:
        return

    budget = TOTAL_HANDS_BUDGETS.get(config_name)
    if budget and total_hands > budget:
        raise ValueError(
            f"Total hands budget exceeded for config '{config_name}': "
            f"{total_hands:,} > {budget:,} total hands\n"
            f"Use --force to override or reduce --n_per."
        )


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
        help="Random seed for reproducible results (required unless --allow-nondeterministic)"
    )
    parser.add_argument(
        "--allow-nondeterministic",
        action="store_true",
        help="Allow nondeterministic runs without a seed (for exploration only)"
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
    parser.add_argument(
        "--mode",
        choices=["self_play", "head_to_head", "head_to_head_matrix"],
        help="Override: evaluation mode. self_play = same strategy all seats; head_to_head = team0 strategy vs fixed team1 strategy."
    )
    parser.add_argument(
        "--emit-bidding-dataset",
        action="store_true",
        help="Emit bidding dataset to data/runs/<run_id>/datasets/ (auction mode only)"
    )
    parser.add_argument(
        "--bidding-dataset-format",
        choices=["parquet", "jsonl"],
        default="parquet",
        help="Format for bidding dataset emission (default: parquet)"
    )
    parser.add_argument(
        "--emit-bidless-dataset",
        action="store_true",
        help="Emit bidless dataset to data/runs/<run_id>/datasets/ (declared contract mode only)"
    )
    parser.add_argument(
        "--bidless-dataset-format",
        choices=["parquet", "jsonl"],
        default="parquet",
        help="Format for bidless dataset emission (default: parquet)"
    )
    parser.add_argument(
        "--team1-strategy",
        type=str,
        help="For head_to_head: name of strategy to use for Team 1 (players 1 & 3). Must be one of the strategies in the config."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Override work budget limits (use with caution)"
    )
    return parser.parse_args()


def scenario_filename(contract_type: str | None, trump_suit: str | None) -> str:
    """Generate standardized filename for scenario results."""
    if contract_type == "suit":
        return f"suit_{trump_suit}.json"
    if contract_type is None:
        return "auction.json"
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
    
    # Enforce determinism by default: seed required unless --allow-nondeterministic
    if seed is None and not args.allow_nondeterministic:
        raise SystemExit(
            "Error: --seed is required for deterministic runs. "
            "Use --seed <int> or --allow-nondeterministic for exploration."
        )
    
    log_level_str = args.log_level if args.log_level else config.parameters.get("log_level", "none")
    mode = args.mode if args.mode else (getattr(config, "mode", None) or config.parameters.get("mode", "self_play"))
    team1_strategy_name = args.team1_strategy if args.team1_strategy else config.parameters.get("team1_strategy")
    pair_deals = config.parameters.get("pair_deals", False)
    
    # Get strategies and bidding policies
    strategy_cfgs = config.strategies
    bidding_policy_cfgs = getattr(config, 'bidding_policies', [])
    strategies = config.get_strategies()
    bidding_policies = config.get_bidding_policies() if hasattr(config, 'get_bidding_policies') else []
    scenarios = config.get_scenario_configs()

    # Must have either strategies or bidding policies
    if not strategy_cfgs and not bidding_policy_cfgs:
        raise ValueError(
            f"No strategies or bidding_policies configured in {args.config}. Please add at least one."
        )

    if n_per is not None and n_per <= 0:
        raise ValueError(
            f"`n_per` must be greater than 0 (config: {args.config}, value: {n_per})."
        )

    # Validate scenarios are not empty
    if not scenarios:
        raise ValueError(
            f"No scenarios configured in {args.config}. Please specify at least one scenario."
        )

    # Resolve team1 strategy config for head-to-head mode (must exist in config)
    team1_cfg = None
    if mode == "head_to_head":
        if not team1_strategy_name:
            raise ValueError("head_to_head mode requires --team1-strategy (or parameters.team1_strategy in YAML)")
        for sc in strategy_cfgs:
            if sc.name == team1_strategy_name:
                team1_cfg = sc
                break
        if team1_cfg is None:
            raise ValueError(
                f"Unknown team1 strategy '{team1_strategy_name}'. "
                f"Must be one of: {', '.join(sc.name for sc in strategy_cfgs)}"
            )

    def _make_seat_strategies(team0_cfg):
        """
        Create per-seat strategy instances.
        - self_play: [team0, team0, team0, team0] (distinct instances)
        - head_to_head: team0 on seats 0&2, team1 on seats 1&3

        Note: RandomLegal gets a per-seat seed offset to avoid identical RNG streams.
        """
        def _clone(cfg, seat_idx: int):
            cfg_params = dict(cfg.params or {})
            if cfg.class_name == "RandomLegalStrategy":
                base_seed = cfg_params.get("seed", seed)
                cfg_params["seed"] = (base_seed + seat_idx) if base_seed is not None else None
            return cfg.__class__(name=cfg.name, class_name=cfg.class_name, params=cfg_params).create_strategy()

        if mode == "self_play":
            return [_clone(team0_cfg, i) for i in range(4)]

        # head_to_head
        return [
            _clone(team0_cfg, 0),
            _clone(team1_cfg, 1),
            _clone(team0_cfg, 2),
            _clone(team1_cfg, 3),
        ]
    
    # Determine what we're running
    has_auction_scenarios = any(s.contract_type is None for s in scenarios)

    if has_auction_scenarios and bidding_policies:
        # Use bidding policies for auction scenarios
        policies_to_run = bidding_policies
        policy_type = "Bidding Policies"
    else:
        # Use strategies for non-auction scenarios
        policies_to_run = strategies
        policy_type = "Strategies"

    plan_count = len(policies_to_run)
    if mode == "head_to_head_matrix":
        matchups = getattr(config, "matchups", None) or config.parameters.get("matchups") or []
        plan_count = len(matchups)

    print("\n" + "=" * 70)
    print(f"🚀 Experiment: {config.experiment_name}")
    print("=" * 70)
    print(f"{policy_type}: {', '.join(p.name for p in policies_to_run)}")
    print(f"Scenarios: {len(scenarios)} ({', '.join((s.contract_type or 'auction') + ('-' + s.trump_suit if s.trump_suit else '') for s in scenarios[:3])}{'...' if len(scenarios) > 3 else ''})")
    print(f"Hands per scenario: {n_per:,}")
    print(f"Random seed: {seed if seed is not None else 'None (random)'}")
    print(f"Log level: {log_level_str}")
    print(f"Total hands to simulate: {plan_count * len(scenarios) * n_per:,}")
    print(f"Common deals: {'Yes' if seed is not None else 'No (random deals)'}")
    print(f"Paired deals: {'Yes (same deals across scenarios)' if pair_deals else 'No'}")
    print(f"Mode: {mode}")
    if mode == "head_to_head":
        print(f"Team1 strategy: {team1_strategy_name}")
    print("=" * 70)

    # Enforce work budget before starting simulation
    total_hands_estimate = plan_count * len(scenarios) * n_per
    check_total_hands_budget(config.experiment_name, total_hands_estimate, force=args.force)
    
    if args.dry_run:
        print("\n✅ Dry run complete. Configuration valid.")
        return
    
    # Create run directory structure (full skeleton - always create all required dirs)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed_str = str(seed) if seed is not None else "random"
    run_id = f"{config.experiment_name}_{seed_str}_{timestamp}"
    run_dir = os.path.join(args.run_dir, run_id)
    
    # Create required subdirectories (even if empty)
    results_dir = os.path.join(run_dir, "results")
    logs_dir = os.path.join(run_dir, "logs")
    reports_dir = os.path.join(run_dir, "reports")
    splits_dir = os.path.join(run_dir, "splits")
    artifacts_dir = os.path.join(run_dir, "artifacts")
    
    for dir_path in [results_dir, logs_dir, reports_dir, splits_dir, artifacts_dir]:
        os.makedirs(dir_path, exist_ok=True)
    
    # Write effective config snapshot (after all CLI overrides applied)
    effective_config = {
        "experiment_name": config.experiment_name,
        "parameters": {
            "n_per": n_per,
            "seed": seed,
            "log_level": log_level_str,
            "pair_deals": pair_deals,
        },
        "mode": mode,
        "strategies": [{"name": s.name, "class_name": getattr(s, "class_name", s.__class__.__name__)} for s in strategy_cfgs],
        "bidding_policies": [{"name": p.name, "class_name": getattr(p, "class_name", p.__class__.__name__)} for p in bidding_policy_cfgs],
        "scenarios": [
            {"contract_type": s.contract_type, "trump_suit": s.trump_suit}
            for s in scenarios
        ],
    }
    
    # Add mode-specific parameters
    if mode == "head_to_head":
        effective_config["parameters"]["team1_strategy"] = team1_strategy_name
    
    # Write as YAML with stable sorting
    with open(os.path.join(run_dir, "config_effective.yaml"), "w") as f:
        yaml.dump(effective_config, f, default_flow_style=False, sort_keys=True)
    
    print(f"\n📁 Run directory: {run_dir}\n")
    
    # Track performance metrics
    start_time = time.time()
    scenario_metrics = []
    all_bidding_collectors: List[Any] = []
    all_bidless_collectors: List[BidlessDatasetCollector] = []

    # Create hooks for bidless dataset collection if requested
    def create_bidless_hooks() -> SimulationHooks | None:
        """Create hooks for bidless dataset collection."""
        if not args.emit_bidless_dataset:
            return None

        # Collector indexed by (deal_id, contract_type, trump_suit) to avoid collisions
        # when the same deal is played under different scenarios (e.g., pair_deals=True)
        hand_collectors: Dict[Tuple[int, str, Optional[str]], BidlessDatasetCollector] = {}

        def on_hand_end(event: HandEndEvent) -> None:
            """Record hand data when each hand completes."""
            # Skip auction mode hands (contract_type is None during auction)
            # Bidless dataset is only for pre-declared contracts
            if event.contract_type is None:
                return

            # Key by (deal_id, contract_type, trump_suit) to handle paired deals
            collector_key = (event.deal_id, event.contract_type, event.trump_suit)

            # Create collector for this hand if needed
            if collector_key not in hand_collectors:
                hand_collectors[collector_key] = BidlessDatasetCollector(run_id, event.deal_id)

            collector = hand_collectors[collector_key]

            # Record all 4 seats
            for seat in range(4):
                # Use dealer_seat=0 as default for bidless (not meaningful)
                dealer_seat = event.dealer_seat if event.dealer_seat is not None else 0
                collector.record_hand_value(
                    hand=event.hands[seat],
                    seat=seat,
                    dealer_seat=dealer_seat,
                    contract_type=event.contract_type,
                    trump_suit=event.trump_suit,
                    deal_id=event.deal_id,
                )

            # Add to list for later emission
            if collector not in all_bidless_collectors:
                all_bidless_collectors.append(collector)

        return SimulationHooks(on_hand_end=on_hand_end)

    bidless_hooks = create_bidless_hooks()

    # Run all strategies × scenarios
    # Run experiments
    if mode == "head_to_head_matrix":
        matchups = getattr(config, "matchups", None) or config.parameters.get("matchups")
        if not matchups:
            raise ValueError("head_to_head_matrix mode requires config.matchups in YAML")

        # Map strategy name -> StrategyConfig
        cfg_by_name = {sc.name: sc for sc in strategy_cfgs}
        policy_cfg_by_name = {pc.name: pc for pc in bidding_policy_cfgs}

        # Each matchup: results/<team0>_vs_<team1>/..., logs/<run_id>_<matchup>.jsonl
        for m in matchups:
            team0_name = m.get("team0")
            team1_name = m.get("team1")
            seat_strategy_names = m.get("seat_strategies")
            seat_bidding_policy_names = m.get("seat_bidding_policies")
            if team0_name and team1_name:
                if team0_name not in cfg_by_name or team1_name not in cfg_by_name:
                    raise ValueError(
                        f"Unknown matchup strategy in {m}. Must be among: {', '.join(cfg_by_name.keys())}"
                    )
                matchup_id = f"{team0_name}_vs_{team1_name}"
            elif seat_strategy_names:
                if len(seat_strategy_names) != 4:
                    raise ValueError(
                        f"seat_strategies must have length 4 (got {len(seat_strategy_names)}): {m}"
                    )
                unknown = [name for name in seat_strategy_names if name not in cfg_by_name]
                if unknown:
                    raise ValueError(
                        f"Unknown seat_strategies {unknown} in {m}. "
                        f"Must be among: {', '.join(cfg_by_name.keys())}"
                    )
                matchup_id = "seatmap__" + "__".join(seat_strategy_names)
            else:
                raise ValueError(
                    "head_to_head_matrix matchups require team0/team1 or seat_strategies."
                )

            if seat_bidding_policy_names:
                if len(seat_bidding_policy_names) != 4:
                    raise ValueError(
                        f"seat_bidding_policies must have length 4 (got {len(seat_bidding_policy_names)}): {m}"
                    )
                unknown = [name for name in seat_bidding_policy_names if name not in policy_cfg_by_name]
                if unknown:
                    raise ValueError(
                        f"Unknown seat_bidding_policies {unknown} in {m}. "
                        f"Must be among: {', '.join(policy_cfg_by_name.keys())}"
                    )
            print("-" * 70)
            print(f"Matchup: {matchup_id}")
            print("-" * 70)

            # Set up logging
            logger = None
            if log_level_str != "none":
                log_level = LogLevel(log_level_str)
                logger = GameLogger(
                    run_id=f"{run_id}_{matchup_id}",
                    strategy_id=matchup_id,
                    level=log_level,
                    output_dir=logs_dir,
                )
                logger.open()
                print(f"📝 Logging to: {logs_dir}/{logger.run_id}.jsonl")

            try:
                # Create per-seat strategies
                # Reuse cloning logic from _make_seat_strategies
                def _clone(cfg, seat_idx: int):
                    cfg_params = dict(cfg.params or {})
                    if cfg.class_name == "RandomLegalStrategy":
                        base_seed = cfg_params.get("seed", seed)
                        cfg_params["seed"] = (base_seed + seat_idx) if base_seed is not None else None
                    return cfg.__class__(name=cfg.name, class_name=cfg.class_name, params=cfg_params).create_strategy()

                if team0_name and team1_name:
                    team0_cfg = cfg_by_name[team0_name]
                    team1_cfg_local = cfg_by_name[team1_name]
                    seat_strategies = [
                        _clone(team0_cfg, 0),
                        _clone(team1_cfg_local, 1),
                        _clone(team0_cfg, 2),
                        _clone(team1_cfg_local, 3),
                    ]
                else:
                    seat_strategies = [
                        _clone(cfg_by_name[name], seat_idx)
                        for seat_idx, name in enumerate(seat_strategy_names)
                    ]

                seat_bidding_policies = None
                if seat_bidding_policy_names:
                    seat_bidding_policies = [
                        policy_cfg_by_name[name].create_bidding_policy()
                        for name in seat_bidding_policy_names
                    ]

                for i, scenario in enumerate(scenarios, 1):
                    # When pair_deals=True, use the same seed for all scenarios
                    # so the same physical deals are played under different contracts
                    if pair_deals and seed is not None:
                        scenario_seed = seed  # Same seed = same physical deals
                    else:
                        scenario_seed = seed + (i - 1) if seed is not None else None

                    label = scenario.contract_type or "auction"
                    if scenario.trump_suit:
                        label += f" ({scenario.trump_suit})"

                    print(f"\n[{i}/{len(scenarios)}] {label} - {n_per:,} hands", end="")
                    if scenario_seed is not None:
                        print(f" (deal_seed={scenario_seed})")
                    else:
                        print()

                    scenario_start = time.time()

                    results = simulation.simulate_many_hands(
                        n=n_per,
                        contract_type=scenario.contract_type,
                        trump_suit=scenario.trump_suit,
                        seed=None,
                        deal_seed=scenario_seed,
                        strategy=None,
                        strategies=seat_strategies,
                        bidding_policy=None,  # Use Strategy.decide_bid for backward compatibility
                        bidding_policies=seat_bidding_policies,
                        logger=logger,
                        bidding_dataset_run_id=run_id if args.emit_bidding_dataset else None,
                        hooks=bidless_hooks,
                    )
                    bidding_collectors = results.pop("bidding_collectors", [])
                    all_bidding_collectors.extend(bidding_collectors)

                    scenario_duration = time.time() - scenario_start
                    hands_per_sec = n_per / scenario_duration if scenario_duration > 0 else 0

                    out_path = os.path.join(
                        results_dir,
                        matchup_id,
                        scenario_filename(scenario.contract_type, scenario.trump_suit),
                    )
                    save_results(results, out_path)

                    team0_avg = results["avg_team0"]
                    team1_avg = results["avg_team1"]
                    full_wins = sum(
                        count
                        for tricks, count in results["distribution_team0"].items()
                        if int(tricks) >= 6
                    )
                    ties = results["distribution_team0"].get(5, 0)
                    # Weighted win rate: full wins + 0.5 × ties (ties contribute half to each team)
                    win_rate = (full_wins + 0.5 * ties) / results["hands"] * 100

                    print(f"  Team0: {team0_avg:.2f}  Team1: {team1_avg:.2f}  WinRate: {win_rate:.1f}%")
                    print(f"  Performance: {format_duration(scenario_duration)}, {hands_per_sec:.0f} hands/sec")

                    scenario_metrics.append({
                        "strategy": matchup_id,
                        "scenario": label,
                        "duration_sec": round(scenario_duration, 2),
                        "hands_per_sec": round(hands_per_sec, 1),
                        "total_hands": n_per,
                    })

            finally:
                if logger:
                    logger.close()

    else:
        # Determine what to iterate over: strategies or bidding policies
        has_auction_scenarios = any(s.contract_type is None for s in scenarios)

        if has_auction_scenarios and bidding_policies:
            # Use bidding policies for auction scenarios
            policies_to_run = bidding_policies
            policy_type = "bidding_policy"
        else:
            # Use strategies for non-auction scenarios
            policies_to_run = strategies
            policy_type = "strategy"

        for policy in policies_to_run:
            print("-" * 70)
            print(f"{policy_type.title()}: {policy.name}")
            print("-" * 70)

            # Set up logging
            logger = None
            if log_level_str != "none":
                log_level = LogLevel(log_level_str)
                logger = GameLogger(
                    run_id=f"{run_id}_{policy.name}",
                    strategy_id=policy.name,
                    level=log_level,
                    output_dir=logs_dir,
                )
                logger.open()
                print(f"📝 Logging to: {logs_dir}/{logger.run_id}.jsonl")

            try:
                for i, scenario in enumerate(scenarios, 1):
                    # When pair_deals=True, use the same seed for all scenarios
                    # so the same physical deals are played under different contracts
                    if pair_deals and seed is not None:
                        scenario_seed = seed  # Same seed = same physical deals
                    else:
                        scenario_seed = seed + (i - 1) if seed is not None else None

                    label = scenario.contract_type or "auction"
                    if scenario.trump_suit:
                        label += f" ({scenario.trump_suit})"

                    print(f"\n[{i}/{len(scenarios)}] {label} - {n_per:,} hands", end="")
                    if scenario_seed is not None:
                        print(f" (deal_seed={scenario_seed})")
                    else:
                        print()

                    scenario_start = time.time()

                    if policy_type == "bidding_policy":
                        # For bidding policies, use the policy directly in auction mode
                        results = simulation.simulate_many_hands(
                            n=n_per,
                            contract_type=scenario.contract_type,
                            trump_suit=scenario.trump_suit,
                            seed=None,
                            deal_seed=scenario_seed,
                            strategy=None,
                            strategies=None,  # No strategies for auction mode
                            bidding_policy=policy,
                            logger=logger,
                            bidding_dataset_run_id=run_id if args.emit_bidding_dataset else None,
                            hooks=bidless_hooks,
                        )
                    else:
                        # For strategies, use the existing logic
                        policy_cfg = next(sc for sc in strategy_cfgs if sc.name == policy.name)
                        seat_strategies = _make_seat_strategies(policy_cfg)
                        results = simulation.simulate_many_hands(
                            n=n_per,
                            contract_type=scenario.contract_type,
                            trump_suit=scenario.trump_suit,
                            seed=None,
                            deal_seed=scenario_seed,
                            strategy=None,
                            strategies=seat_strategies,
                            bidding_policy=None,
                            logger=logger,
                            bidding_dataset_run_id=run_id if args.emit_bidding_dataset else None,
                            hooks=bidless_hooks,
                        )
                    bidding_collectors = results.pop("bidding_collectors", [])
                    all_bidding_collectors.extend(bidding_collectors)

                    scenario_duration = time.time() - scenario_start
                    hands_per_sec = n_per / scenario_duration if scenario_duration > 0 else 0

                    out_path = os.path.join(
                        results_dir,
                        policy.name,
                        scenario_filename(scenario.contract_type, scenario.trump_suit)
                    )
                    save_results(results, out_path)

                    team0_avg = results["avg_team0"]
                    team1_avg = results["avg_team1"]
                    full_wins = sum(
                        count
                        for tricks, count in results["distribution_team0"].items()
                        if int(tricks) >= 6
                    )
                    ties = results["distribution_team0"].get(5, 0)
                    # Weighted win rate: full wins + 0.5 × ties (ties contribute half to each team)
                    win_rate = (full_wins + 0.5 * ties) / results["hands"] * 100

                    print(f"  Team0: {team0_avg:.2f}  Team1: {team1_avg:.2f}  WinRate: {win_rate:.1f}%")
                    print(f"  Performance: {format_duration(scenario_duration)}, {hands_per_sec:.0f} hands/sec")

                    scenario_metrics.append({
                        "strategy": policy.name,
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
    total_hands = plan_count * len(scenarios) * n_per
    overall_throughput = total_hands / total_duration if total_duration > 0 else 0
    
    # Write metadata (experiment config + results summary)
    meta = {
        "schema_version": META_JSON_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at_utc": utc_now_iso(),
        "git_sha": get_git_sha(),
        "config_path": args.config,
        "config_sha256": sha256_file(args.config),
        "experiment_name": config.experiment_name,
        "timestamp": timestamp,  # legacy/human-readable; keep for compatibility
        "seed": seed,
        "is_deterministic": seed is not None,  # True if seed provided (backward compatible field)
        "n_per": n_per,
        "log_level": log_level_str,
        "mode": mode,
        "team1_strategy": team1_strategy_name if mode == "head_to_head" else None,
        "scenarios": [
            {"contract_type": s.contract_type, "trump_suit": s.trump_suit}
            for s in scenarios
        ],
        "strategies": [s.name for s in strategies],
        "bidding_policies": [p.name for p in bidding_policies],
        "leader_randomized": True,  # Always true with new deal generator
        "common_deals": seed is not None,  # Only true if seed provided
        "pair_deals": pair_deals,  # True = same physical deals across all scenarios
        "total_hands": total_hands,
    }
    
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
    
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
    
    if args.emit_bidding_dataset and all_bidding_collectors:
        dataset_path = emit_bidding_dataset(all_bidding_collectors, run_dir, format=args.bidding_dataset_format)
        print(f"\n📊 Emitted bidding dataset: {dataset_path}")

    if args.emit_bidless_dataset and all_bidless_collectors:
        dataset_path = emit_bidless_dataset(all_bidless_collectors, run_dir, format=args.bidless_dataset_format)
        print(f"\n📊 Emitted bidless dataset: {dataset_path}")

    # Final summary
    print("\n" + "=" * 70)
    print("✅ Experiment completed!")
    print("=" * 70)
    print(f"📁 Results: {run_dir}/")
    print(f"⏱️  Duration: {format_duration(total_duration)}")
    print(f"🚀 Throughput: {overall_throughput:.0f} hands/sec")
    print(f"📊 Generated {plan_count * len(scenarios)} result files")
    
    print("\n🎯 Next steps:")
    print("   # Generate reports:")
    print("   PYTHONPATH=src python scripts/generate_report.py \\")
    print(f"       --run-dir {run_dir}")
    print()
    
    # Auto-generate reports if logs were created
    if log_level_str != "none":
        print("📊 Auto-generating reports...")
        try:
            import subprocess
            result = subprocess.run(
                ["python", "scripts/generate_report.py", "--run-dir", run_dir],
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
            print(f"   Run manually: PYTHONPATH=src python scripts/generate_report.py --run-dir {run_dir}")
        print()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)


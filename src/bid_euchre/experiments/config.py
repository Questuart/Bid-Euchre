"""
Experiment Configuration System

This module provides classes and functions for configuring and managing experiments.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml

from ..strategy import (
    ActionValueBidder,
    AlwaysHighestLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysPassBidder,
    ArtifactBidder,
    BasicStrategy,
    BiddingPolicy,
    FixedBidder,
    GluttonIsolatedStrategy,
    GluttonStrategy,
    GreedyStrategy,
    HybridOLSaBidder,
    ModeloEspecifico,
    OLSaBidder,
    RandomLegalStrategy,
    RanktheTank,
    Strategy,
    StrictHellRaiser,
)
from ..strategy.artifact_strategy import ArtifactGreedyStrategy
from .teacher_roster import load_teacher_roster

# Strategy registries for discoverability
# Maps class_name → class for play strategies and bidding policies
PLAY_STRATEGY_REGISTRY: dict[str, type] = {
    "BasicStrategy": BasicStrategy,
    "GreedyStrategy": GreedyStrategy,
    "GluttonStrategy": GluttonStrategy,
    "GluttonIsolatedStrategy": GluttonIsolatedStrategy,
    "RandomLegalStrategy": RandomLegalStrategy,
    "AlwaysLowestLegalStrategy": AlwaysLowestLegalStrategy,
    "AlwaysHighestLegalStrategy": AlwaysHighestLegalStrategy,
    "ArtifactGreedyStrategy": ArtifactGreedyStrategy,
}

BIDDING_POLICY_REGISTRY: dict[str, type] = {
    "AlwaysPassBidder": AlwaysPassBidder,
    "ArtifactBidder": ArtifactBidder,
    "RanktheTank": RanktheTank,
    "StrictHellRaiser": StrictHellRaiser,
    "StrictRaiserBidder": StrictHellRaiser,  # backward-compat alias
    "ModeloEspecifico": ModeloEspecifico,
    "FixedBidder": FixedBidder,
    "OLSaBidder": OLSaBidder,
    "HybridOLSaBidder": HybridOLSaBidder,
    "ActionValueBidder": ActionValueBidder,
}

STRATEGY_REQUIRED_PARAMS: dict[str, list[str]] = {
    "ArtifactGreedyStrategy": ["artifact_path"],
}

BIDDING_REQUIRED_PARAMS: dict[str, list[str]] = {
    "ArtifactBidder": ["artifact_path"],
    "FixedBidder": ["n", "contract"],
    "OLSaBidder": ["artifact_path"],
    "HybridOLSaBidder": ["artifact_path"],
    "ActionValueBidder": ["artifact_path"],
}


@dataclass
class StrategyConfig:
    """Configuration for a single strategy."""

    name: str
    class_name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def create_strategy(self) -> Strategy:
        """Create a strategy instance from this configuration."""
        cls = PLAY_STRATEGY_REGISTRY.get(self.class_name)
        if cls is None:
            raise ValueError(
                f"Unknown strategy class: {self.class_name}. "
                f"Available: {sorted(PLAY_STRATEGY_REGISTRY)}"
            )
        for param in STRATEGY_REQUIRED_PARAMS.get(self.class_name, []):
            if not self.params.get(param):
                raise ValueError(f"{self.class_name} requires '{param}' parameter")
        return cls(name=self.name, **self.params)


@dataclass
class BiddingPolicyConfig:
    """Configuration for a single bidding policy."""

    name: str
    class_name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def create_bidding_policy(self) -> BiddingPolicy:
        """Create a bidding policy instance from this configuration."""
        cls = BIDDING_POLICY_REGISTRY.get(self.class_name)
        if cls is None:
            raise ValueError(
                f"Unknown bidding policy class: {self.class_name}. "
                f"Available: {sorted(BIDDING_POLICY_REGISTRY)}"
            )
        for param in BIDDING_REQUIRED_PARAMS.get(self.class_name, []):
            if not self.params.get(param):
                raise ValueError(f"{self.class_name} requires '{param}' parameter")
        return cls(name=self.name, **self.params)


@dataclass
class ScenarioConfig:
    """Configuration for a simulation scenario."""

    contract_type: Optional[str]
    trump_suit: Optional[str] = None

    def __post_init__(self):
        """Validate scenario configuration."""
        if self.contract_type == "suit" and self.trump_suit is None:
            raise ValueError("trump_suit must be provided for 'suit' contracts")
        if self.contract_type in ["high", "low"] and self.trump_suit is not None:
            raise ValueError("trump_suit must be None for 'high'/'low' contracts")
        if self.contract_type is None and self.trump_suit is not None:
            raise ValueError(
                "trump_suit must be None for auction contracts (contract_type: null)"
            )
        # Validate known contract types
        if self.contract_type is not None and self.contract_type not in [
            "suit",
            "high",
            "low",
        ]:
            raise ValueError(
                f"Unknown contract_type: {self.contract_type}. Must be 'suit', 'high', 'low', or null for auction."
            )


@dataclass
class ExperimentConfig:
    """Configuration for a complete experiment."""

    experiment_name: str
    scenarios: List[Dict[str, Any]]  # Will be converted to ScenarioConfig objects
    parameters: Dict[str, Any]
    strategies: List[StrategyConfig] = field(default_factory=list)
    bidding_policies: List[BiddingPolicyConfig] = field(default_factory=list)
    mode: str = "self_play"
    matchups: Optional[List[Dict[str, str]]] = None
    strategy_roster_path: Optional[str] = None
    include_baselines: List[str] = field(default_factory=list)
    seat_bidding_policies: Optional[List[str]] = (
        None  # Per-seat policy names (list of 4)
    )

    def __post_init__(self):
        """Process scenarios into ScenarioConfig objects."""
        processed_scenarios = []
        for scenario_dict in self.scenarios:
            if isinstance(scenario_dict, dict):
                # Handle trump suit expansion (e.g., "C,D,H,S" -> ["C", "D", "H", "S"])
                trump_suits = scenario_dict.get("trump_suit", [])
                if isinstance(trump_suits, str):
                    trump_suits = [s.strip() for s in trump_suits.split(",")]

                if trump_suits:
                    # Create separate scenarios for each trump suit
                    for trump in trump_suits:
                        processed_scenarios.append(
                            ScenarioConfig(
                                contract_type=scenario_dict["contract_type"],
                                trump_suit=trump,
                            )
                        )
                else:
                    processed_scenarios.append(
                        ScenarioConfig(
                            contract_type=scenario_dict["contract_type"],
                            trump_suit=None,
                        )
                    )
            else:
                processed_scenarios.append(scenario_dict)

        self.scenarios = processed_scenarios

    def get_strategies(self) -> List[Strategy]:
        """Get all strategy instances."""
        return [
            strategy_config.create_strategy() for strategy_config in self.strategies
        ]

    def get_bidding_policies(self) -> List[BiddingPolicy]:
        """Get all bidding policy instances."""
        return [
            policy_config.create_bidding_policy()
            for policy_config in self.bidding_policies
        ]

    def get_scenario_configs(self) -> List[ScenarioConfig]:
        """Get all scenario configurations."""
        return self.scenarios


def load_config(config_path: str) -> ExperimentConfig:
    """
    Load experiment configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        ExperimentConfig instance
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)

    # Handle roster-based loading
    strategy_roster_path = config_dict.get("strategy_roster_path")
    include_baselines = config_dict.get("include_baselines", [])

    # Always load explicit strategies and bidding_policies from config
    strategies = []
    for strategy_dict in config_dict.get("strategies", []):
        strategies.append(StrategyConfig(**strategy_dict))

    bidding_policies = []
    for policy_dict in config_dict.get("bidding_policies", []):
        bidding_policies.append(BiddingPolicyConfig(**policy_dict))

    # Merge roster-based bidding policies if specified
    if strategy_roster_path and include_baselines:
        # Load roster and create configs from baselines
        roster = load_teacher_roster(strategy_roster_path)

        # Create lookup map of baseline id -> baseline config
        baseline_map = {b["id"]: b for b in roster["baselines"]}

        # Validate all requested baselines exist
        missing_baselines = set(include_baselines) - set(baseline_map.keys())
        if missing_baselines:
            raise ValueError(
                f"Requested baselines not found in roster: {missing_baselines}"
            )

        # Convert baselines to bidding policies and append to existing list
        for baseline_id in include_baselines:
            baseline = baseline_map[baseline_id]

            if baseline["kind"] == "policy":
                bidding_policies.append(
                    BiddingPolicyConfig(
                        name=baseline["display_name"],
                        class_name=baseline["import_path"].split(".")[-1],
                        params=baseline.get("params", {}),
                    )
                )
            elif baseline["kind"] == "artifact_policy":
                # For artifact policies, use ArtifactBidder for bidding
                bidding_policies.append(
                    BiddingPolicyConfig(
                        name=baseline["display_name"],
                        class_name="ArtifactBidder",
                        params=baseline.get("params", {}),
                    )
                )
            else:
                raise ValueError(f"Unsupported baseline kind: {baseline['kind']}")

    # Parse seat_bidding_policies if present
    seat_bidding_policies = config_dict.get("seat_bidding_policies")

    return ExperimentConfig(
        experiment_name=config_dict["experiment_name"],
        mode=config_dict.get(
            "mode", config_dict.get("parameters", {}).get("mode", "self_play")
        ),
        strategies=strategies,
        bidding_policies=bidding_policies,
        scenarios=config_dict["scenarios"],
        parameters=config_dict.get("parameters", {}),
        matchups=config_dict.get("matchups"),
        strategy_roster_path=strategy_roster_path,
        include_baselines=include_baselines,
        seat_bidding_policies=seat_bidding_policies,
    )


def create_experiment(
    name: str,
    strategy_names: List[str] = None,
    contract_types: List[str] = None,
    trump_suits: List[str] = None,
    n_per: int = 50000,
    seed: int = None,
) -> ExperimentConfig:
    """
    Create a simple experiment configuration programmatically.

    Args:
        name: Experiment name
        strategy_names: List of strategy names ("basic", "greedy")
        contract_types: List of contract types ("suit", "high", "low")
        trump_suits: List of trump suits (only used for "suit" contracts)
        n_per: Number of hands per scenario
        seed: Random seed

    Returns:
        ExperimentConfig instance
    """
    if strategy_names is None:
        strategy_names = ["greedy"]

    if contract_types is None:
        contract_types = ["suit", "high", "low"]

    # Create strategy configs
    strategies = []
    for strategy_name in strategy_names:
        if strategy_name == "basic":
            strategies.append(StrategyConfig(name="basic", class_name="BasicStrategy"))
        elif strategy_name == "greedy":
            strategies.append(
                StrategyConfig(name="greedy", class_name="GreedyStrategy")
            )
        elif strategy_name == "glutton":
            strategies.append(
                StrategyConfig(
                    name="glutton",
                    class_name="GluttonStrategy",
                    params={"debug": False},
                )
            )
        elif strategy_name == "random_legal":
            strategies.append(
                StrategyConfig(
                    name="random_legal",
                    class_name="RandomLegalStrategy",
                    params={"seed": seed},
                )
            )
        elif strategy_name == "always_lowest":
            strategies.append(
                StrategyConfig(
                    name="always_lowest", class_name="AlwaysLowestLegalStrategy"
                )
            )
        elif strategy_name == "always_highest":
            strategies.append(
                StrategyConfig(
                    name="always_highest", class_name="AlwaysHighestLegalStrategy"
                )
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    # Create scenario configs
    scenarios = []
    for contract_type in contract_types:
        if contract_type == "suit":
            if trump_suits is None:
                trump_suits = ["C", "D", "H", "S"]
            scenarios.append({"contract_type": "suit", "trump_suit": trump_suits})
        else:
            scenarios.append({"contract_type": contract_type})

    return ExperimentConfig(
        experiment_name=name,
        strategies=strategies,
        scenarios=scenarios,
        parameters={"n_per": n_per, "seed": seed},
    )


def save_config(config: ExperimentConfig, output_path: str):
    """
    Save experiment configuration to YAML file.

    Args:
        config: ExperimentConfig instance
        output_path: Path to save YAML file
    """
    # Convert back to dictionary format for YAML serialization
    config_dict = {
        "experiment_name": config.experiment_name,
        "strategies": [
            {"name": s.name, "class_name": s.class_name, "params": s.params}
            for s in config.strategies
        ],
        "scenarios": [
            {"contract_type": s.contract_type, "trump_suit": s.trump_suit}
            for s in config.scenarios
        ],
        "parameters": config.parameters,
    }
    # Include seat_bidding_policies if set
    if config.seat_bidding_policies is not None:
        config_dict["seat_bidding_policies"] = config.seat_bidding_policies

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

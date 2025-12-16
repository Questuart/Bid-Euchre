"""
Experiment Configuration System

This module provides classes and functions for configuring and managing experiments.
"""

import yaml
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from ..strategy import Strategy, BasicStrategy, GreedyStrategy


@dataclass
class StrategyConfig:
    """Configuration for a single strategy."""
    name: str
    class_name: str
    params: Dict[str, Any] = field(default_factory=dict)

    def create_strategy(self) -> Strategy:
        """Create a strategy instance from this configuration."""
        if self.class_name == "BasicStrategy":
            return BasicStrategy(name=self.name)
        elif self.class_name == "GreedyStrategy":
            return GreedyStrategy(name=self.name)
        else:
            raise ValueError(f"Unknown strategy class: {self.class_name}")


@dataclass
class ScenarioConfig:
    """Configuration for a simulation scenario."""
    contract_type: str
    trump_suit: Optional[str] = None

    def __post_init__(self):
        """Validate scenario configuration."""
        if self.contract_type == "suit" and self.trump_suit is None:
            raise ValueError("trump_suit must be provided for 'suit' contracts")
        if self.contract_type in ["high", "low"] and self.trump_suit is not None:
            raise ValueError("trump_suit must be None for 'high'/'low' contracts")


@dataclass
class ExperimentConfig:
    """Configuration for a complete experiment."""
    experiment_name: str
    strategies: List[StrategyConfig]
    scenarios: List[Dict[str, Any]]  # Will be converted to ScenarioConfig objects
    parameters: Dict[str, Any]

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
                        processed_scenarios.append(ScenarioConfig(
                            contract_type=scenario_dict["contract_type"],
                            trump_suit=trump
                        ))
                else:
                    processed_scenarios.append(ScenarioConfig(
                        contract_type=scenario_dict["contract_type"],
                        trump_suit=None
                    ))
            else:
                processed_scenarios.append(scenario_dict)

        self.scenarios = processed_scenarios

    def get_strategies(self) -> List[Strategy]:
        """Get all strategy instances."""
        return [strategy_config.create_strategy() for strategy_config in self.strategies]

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

    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)

    # Convert strategy configs
    strategies = []
    for strategy_dict in config_dict.get("strategies", []):
        strategies.append(StrategyConfig(**strategy_dict))

    return ExperimentConfig(
        experiment_name=config_dict["experiment_name"],
        strategies=strategies,
        scenarios=config_dict["scenarios"],
        parameters=config_dict.get("parameters", {})
    )


def create_experiment(
    name: str,
    strategy_names: List[str] = None,
    contract_types: List[str] = None,
    trump_suits: List[str] = None,
    n_per: int = 50000,
    seed: int = None
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
            strategies.append(StrategyConfig(
                name="basic",
                class_name="BasicStrategy"
            ))
        elif strategy_name == "greedy":
            strategies.append(StrategyConfig(
                name="greedy",
                class_name="GreedyStrategy"
            ))
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    # Create scenario configs
    scenarios = []
    for contract_type in contract_types:
        if contract_type == "suit":
            if trump_suits is None:
                trump_suits = ["C", "D", "H", "S"]
            scenarios.append({
                "contract_type": "suit",
                "trump_suit": trump_suits
            })
        else:
            scenarios.append({
                "contract_type": contract_type
            })

    return ExperimentConfig(
        experiment_name=name,
        strategies=strategies,
        scenarios=scenarios,
        parameters={
            "n_per": n_per,
            "seed": seed
        }
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
            {
                "name": s.name,
                "class_name": s.class_name,
                "params": s.params
            }
            for s in config.strategies
        ],
        "scenarios": [
            {
                "contract_type": s.contract_type,
                "trump_suit": s.trump_suit
            }
            for s in config.scenarios
        ],
        "parameters": config.parameters
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)

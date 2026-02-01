"""Data loading and generation utilities for notebook analysis.

Provides on-the-fly data generation for notebooks with automatic caching,
supporting both feature and outcome datasets for bidless euchre analysis.

Usage:
    # Generate or load cached outcomes
    df = load_or_generate_outcomes(mode="QUICK", seed=42)

    # Generate or load cached features with outcomes
    df = load_or_generate_features(mode="QUICK", seed=42)
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from bid_euchre.diagnostics.loaders import load_bidless_dataset


def load_or_generate_outcomes(
    mode: str = "QUICK",
    seed: int = 42,
    contracts: Optional[List[str]] = None,
    trumps: Optional[List[str]] = None,
    seats: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Load or generate outcome dataset (tricks_won by seat).

    Checks cache first, generates new data if not found.

    Args:
        mode: "QUICK" (~2k deals) or "FULL" (~50k deals)
        seed: Random seed for reproducibility
        contracts: Contract types to include (default: ['suit', 'high', 'low'])
        trumps: Trump suits for suit contracts (default: ['C', 'D', 'H', 'S'])
        seats: Seats to include (default: [0, 1, 2, 3])

    Returns:
        DataFrame with columns:
            - deal_id: int
            - seat: int (0-3)
            - contract_type: str ("suit", "high", "low")
            - trump: str or None
            - tricks_won: int (0-10)
            - strategy_id: str

    Raises:
        ValueError: If mode not recognized or parameters invalid
    """
    # Defaults
    if contracts is None:
        contracts = ['suit', 'high', 'low']
    if trumps is None:
        trumps = ['C', 'D', 'H', 'S']
    if seats is None:
        seats = [0, 1, 2, 3]

    # Validate
    if mode not in ["QUICK", "FULL"]:
        raise ValueError(f"mode must be 'QUICK' or 'FULL', got '{mode}'")

    # Check cache
    cache_key = _compute_cache_key("outcomes", mode, seed, contracts, trumps, seats)
    cache_path = _get_cache_path(cache_key)

    if cache_path.exists():
        print(f"Loading cached outcomes from {cache_path.name}...")
        return pd.read_parquet(cache_path)

    # Generate new data
    print(f"Generating new outcome dataset (mode={mode}, seed={seed})...")
    run_dir = _generate_experiment_data(mode, seed, contracts, trumps, seats)

    # Extract outcomes from logs
    outcome_df = _load_outcomes_from_run(run_dir)

    # Cache for reuse
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    outcome_df.to_parquet(cache_path, index=False)
    print(f"Cached outcomes to {cache_path.name}")

    return outcome_df


def load_or_generate_features(
    mode: str = "QUICK",
    seed: int = 42,
    contracts: Optional[List[str]] = None,
    trumps: Optional[List[str]] = None,
    seats: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Load or generate feature dataset (features + outcomes).

    Checks cache first, generates new data if not found.

    Args:
        mode: "QUICK" (~2k deals) or "FULL" (~50k deals)
        seed: Random seed for reproducibility
        contracts: Contract types to include (default: ['suit', 'high', 'low'])
        trumps: Trump suits for suit contracts (default: ['C', 'D', 'H', 'S'])
        seats: Seats to include (default: [0, 1, 2, 3])

    Returns:
        DataFrame with columns:
            - deal_id: int
            - seat: int (0-3)
            - contract_type: str ("suit", "high", "low")
            - trump: str or None
            - tricks_won: int (0-10)
            - strategy_id: str
            - feat_*: feature columns (trump_count, offsuit_aces, etc.)
            - hand_cards: list of str

    Raises:
        ValueError: If mode not recognized or parameters invalid
    """
    # Defaults
    if contracts is None:
        contracts = ['suit', 'high', 'low']
    if trumps is None:
        trumps = ['C', 'D', 'H', 'S']
    if seats is None:
        seats = [0, 1, 2, 3]

    # Validate
    if mode not in ["QUICK", "FULL"]:
        raise ValueError(f"mode must be 'QUICK' or 'FULL', got '{mode}'")

    # Check cache
    cache_key = _compute_cache_key("features", mode, seed, contracts, trumps, seats)
    cache_path = _get_cache_path(cache_key)

    if cache_path.exists():
        print(f"Loading cached features from {cache_path.name}...")
        return pd.read_parquet(cache_path)

    # Generate new data
    print(f"Generating new feature dataset (mode={mode}, seed={seed})...")
    run_dir = _generate_experiment_data(mode, seed, contracts, trumps, seats)

    # Load features from bidless dataset
    dataset_dir = run_dir / "datasets"
    features_df = load_bidless_dataset(dataset_dir)

    # Extract outcomes from logs and join
    outcome_df = _load_outcomes_from_run(run_dir)

    # Join on deal_id + seat
    merged_df = features_df.merge(
        outcome_df,
        on=['deal_id', 'seat'],
        how='inner',
        suffixes=('', '_outcome')
    )

    # Reconcile contract_type and trump columns if duplicated
    if 'contract_type_outcome' in merged_df.columns:
        # Verify they match
        assert (merged_df['contract_type'] == merged_df['contract_type_outcome']).all(), \
            "contract_type mismatch between features and outcomes"
        merged_df = merged_df.drop(columns=['contract_type_outcome'])

    if 'trump_outcome' in merged_df.columns:
        # Handle None vs NaN comparison carefully
        features_trump = merged_df['trump'].fillna('None')
        outcome_trump = merged_df['trump_outcome'].fillna('None')
        assert (features_trump == outcome_trump).all(), \
            "trump mismatch between features and outcomes"
        merged_df = merged_df.drop(columns=['trump_outcome'])

    # Cache for reuse
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_parquet(cache_path, index=False)
    print(f"Cached features to {cache_path.name}")

    return merged_df


# ============================================================================
# Internal Helpers
# ============================================================================

def _compute_cache_key(
    data_type: str,
    mode: str,
    seed: int,
    contracts: List[str],
    trumps: List[str],
    seats: List[int],
) -> str:
    """Compute cache key from parameters."""
    key_parts = [
        data_type,
        mode,
        str(seed),
        "_".join(sorted(contracts)),
        "_".join(sorted(trumps)),
        "_".join(map(str, sorted(seats))),
    ]
    key_str = "|".join(key_parts)
    hash_hex = hashlib.sha256(key_str.encode()).hexdigest()[:16]
    return f"{data_type}_{mode}_{seed}_{hash_hex}"


def _get_cache_path(cache_key: str) -> Path:
    """Get cache file path in scratchpad directory."""
    # Use scratchpad for session-specific caching
    scratchpad = Path(
        "/private/tmp/claude-503/-Users-claude-runner-Projects-Bid-Euchre-meta-Bid-Euchre/"
        "f5763644-2c9b-43b5-b1cd-43f153e65728/scratchpad"
    )
    cache_dir = scratchpad / "notebook_cache"
    return cache_dir / f"{cache_key}.parquet"


def _generate_experiment_data(
    mode: str,
    seed: int,
    contracts: List[str],
    trumps: List[str],
    seats: List[int],
) -> Path:
    """Generate experiment data by running experiment runner.

    Returns:
        Path to run directory containing logs/ and datasets/
    """
    # Create temporary config
    config = _generate_temp_config(mode, seed, contracts, trumps, seats)

    # Write config to temp file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.yaml',
        delete=False,
        dir=tempfile.gettempdir()
    ) as f:
        import yaml
        yaml.dump(config, f)
        config_path = f.name

    try:
        # Run experiment
        repo_root = Path(__file__).parent.parent.parent.parent
        cmd = [
            sys.executable,
            str(repo_root / "experiments" / "run_experiment.py"),
            "--config", config_path,
            "--seed", str(seed),
        ]

        print(f"Running experiment: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "PYTHONPATH": str(repo_root / "src")},
        )

        if result.returncode != 0:
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            raise RuntimeError(
                f"Experiment failed with code {result.returncode}\n"
                f"stderr: {result.stderr}"
            )

        # Parse output to find run_dir
        run_dir = None
        for line in result.stdout.split('\n'):
            if 'Run directory:' in line:
                # Extract path after "Run directory:"
                dir_path = line.split('Run directory:')[1].strip()
                run_dir = repo_root / dir_path
                break

        if run_dir is None or not run_dir.exists():
            # Fallback: look for any directory matching the experiment name
            runs_dir = repo_root / "data" / "runs"
            matching_dirs = list(runs_dir.glob(f"{config['experiment_name']}*"))
            if matching_dirs:
                # Get the most recent one
                run_dir = max(matching_dirs, key=lambda p: p.stat().st_mtime)
            else:
                raise RuntimeError(
                    f"Run directory not found for {config['experiment_name']}\n"
                    f"stdout: {result.stdout}\n"
                    f"stderr: {result.stderr}"
                )

        print(f"Experiment completed: {run_dir}")
        return run_dir

    finally:
        # Clean up temp config
        Path(config_path).unlink(missing_ok=True)


def _generate_temp_config(
    mode: str,
    seed: int,
    contracts: List[str],
    trumps: List[str],
    seats: List[int],
) -> Dict[str, Any]:
    """Generate temporary experiment config."""
    # Sample sizes by mode
    if mode == "QUICK":
        n_per = 50  # ~50 deals per scenario = ~2k total
    elif mode == "FULL":
        n_per = 2500  # ~2500 deals per scenario = ~50k total
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Build scenarios
    scenarios = []
    for contract in contracts:
        if contract == 'suit':
            # One scenario per trump
            for trump in trumps:
                scenarios.append({
                    'contract_type': 'suit',
                    'trump_suit': trump,
                })
        elif contract in ['high', 'low']:
            # Single scenario, no trump
            scenarios.append({
                'contract_type': contract,
            })
        else:
            raise ValueError(f"Unknown contract type: {contract}")

    # Build config
    config = {
        'experiment_name': f'notebook_temp_{mode}_{seed}',
        'strategies': [
            {
                'name': 'greedy',
                'class_name': 'GreedyStrategy',
            }
        ],
        'scenarios': scenarios,
        'parameters': {
            'n_per': n_per,
            'log_level': 'hand',  # Need hand_end logs for outcomes
            'generate_bidless_dataset': True,
        },
    }

    return config


def _load_outcomes_from_run(run_dir: Union[str, Path]) -> pd.DataFrame:
    """Load outcome data from experiment logs.

    Parses hand_end events from JSONL logs to extract tricks_won per seat.

    Args:
        run_dir: Path to run directory containing logs/*.jsonl

    Returns:
        DataFrame with columns: deal_id, seat, contract_type, trump, tricks_won, strategy_id
    """
    run_dir = Path(run_dir)
    logs_dir = run_dir / "logs"

    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")

    # Find all JSONL log files
    log_files = list(logs_dir.glob("*.jsonl"))
    if not log_files:
        raise FileNotFoundError(f"No JSONL logs found in {logs_dir}")

    # Parse all hand_end events
    hand_records = []
    for log_file in log_files:
        with open(log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                record = json.loads(line)
                if record.get('event') == 'hand_end':
                    hand_records.append(record)

    if not hand_records:
        raise ValueError(f"No hand_end events found in {logs_dir}")

    # Convert to per-seat outcome records
    outcome_records = []
    for hand in hand_records:
        deal_id = hand['deal_id']
        contract_type = hand['contract']
        trump = hand.get('trump')  # None for high/low
        strategy_id = hand['strategy_id']
        t0 = hand['t0']  # Team 0 tricks (seats 0 & 2)
        t1 = hand['t1']  # Team 1 tricks (seats 1 & 3)

        # Create one record per seat
        for seat in range(4):
            tricks_won = t0 if seat in [0, 2] else t1
            outcome_records.append({
                'deal_id': deal_id,
                'seat': seat,
                'contract_type': contract_type,
                'trump': trump,
                'tricks_won': tricks_won,
                'strategy_id': strategy_id,
            })

    # Convert to DataFrame
    outcome_df = pd.DataFrame(outcome_records)

    # Sort for consistency
    outcome_df = outcome_df.sort_values(['deal_id', 'seat']).reset_index(drop=True)

    return outcome_df

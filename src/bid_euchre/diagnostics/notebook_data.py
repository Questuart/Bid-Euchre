"""Data loading and generation utilities for notebook analysis.

Provides on-the-fly data generation for notebooks with automatic caching,
supporting both feature and outcome datasets for bidless euchre analysis.

Usage:
    # Generate or load cached outcomes
    df = load_or_generate_outcomes(mode="QUICK", seed=42)

    # Generate or load cached features with outcomes
    df = load_or_generate_features(mode="QUICK", seed=42)

    # Fast smoke test (CI validation)
    df = load_or_generate_outcomes(mode="SMOKE", seed=42)

Modes:
    SMOKE: ~100 total deals (~5 per scenario), fast CI validation
    QUICK: ~2k total deals (~50 per scenario), statistical checks
    FULL: ~50k total deals (~2500 per scenario), production rigor
"""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from bid_euchre.diagnostics.loaders import load_bidless_dataset


def load_or_generate_outcomes(
    mode: str = "QUICK",
    seed: int = 42,
    contracts: Optional[List[str]] = None,
    trumps: Optional[List[str]] = None,
    seats: Optional[List[int]] = None,
    strategies: Optional[List[Dict[str, str]]] = None,
    matchups: Optional[List[Dict[str, str]]] = None,
) -> pd.DataFrame:
    """Load or generate outcome dataset (tricks_won by seat).

    Checks cache first, generates new data if not found.

    Args:
        mode: "SMOKE" (~100 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
        seed: Random seed for reproducibility
        contracts: Contract types to include (default: ['suit', 'high', 'low'])
        trumps: Trump suits for suit contracts (default: ['C', 'D', 'H', 'S'])
        seats: Seats to include (default: [0, 1, 2, 3])
        strategies: List of strategy configs, e.g.:
            [{"name": "greedy", "class_name": "GreedyStrategy"},
             {"name": "random_legal", "class_name": "RandomLegalStrategy"}]
            Default: [{"name": "greedy", "class_name": "GreedyStrategy"}]
        matchups: List of matchups for head-to-head mode, e.g.:
            Team-based: [{"team0": "greedy", "team1": "random_legal"}]
            Seat-based: [{"seat_strategies": ["greedy", "random_legal", "greedy", "random_legal"]}]
            Default: None (self-play mode)

    Returns:
        DataFrame with columns:
            - deal_id: int
            - seat: int (0-3)
            - contract_type: str ("suit", "high", "low")
            - trump: str or None
            - tricks_won: int (0-10)
            - strategy_id: str

        strategy_id reflects mode:
        - Self-play: strategy_id = strategy name
        - Head-to-head: strategy_id = "team0_vs_team1"

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
    if mode not in ["SMOKE", "QUICK", "FULL"]:
        raise ValueError(f"mode must be 'SMOKE', 'QUICK', or 'FULL', got '{mode}'")

    # Check cache
    cache_key = _compute_cache_key("outcomes", mode, seed, contracts, trumps, seats, strategies, matchups)
    cache_path = _get_cache_path(cache_key)

    if cache_path.exists():
        print(f"Loading cached outcomes from {cache_path.name}...")
        return pd.read_parquet(cache_path)

    # Generate new data
    print(f"Generating new outcome dataset (mode={mode}, seed={seed})...")
    run_dir = _generate_experiment_data(mode, seed, contracts, trumps, seats, strategies, matchups)

    # Extract outcomes from logs (for on-the-fly generation, logs are always present)
    outcome_df = _load_outcomes_from_logs(run_dir)

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
    strategies: Optional[List[Dict[str, str]]] = None,
    matchups: Optional[List[Dict[str, str]]] = None,
) -> pd.DataFrame:
    """Load or generate feature dataset (features + outcomes).

    Checks cache first, generates new data if not found.

    Args:
        mode: "SMOKE" (~100 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
        seed: Random seed for reproducibility
        contracts: Contract types to include (default: ['suit', 'high', 'low'])
        trumps: Trump suits for suit contracts (default: ['C', 'D', 'H', 'S'])
        seats: Seats to include (default: [0, 1, 2, 3])
        strategies: List of strategy configs, e.g.:
            [{"name": "greedy", "class_name": "GreedyStrategy"},
             {"name": "random_legal", "class_name": "RandomLegalStrategy"}]
            Default: [{"name": "greedy", "class_name": "GreedyStrategy"}]
        matchups: List of matchups for head-to-head mode, e.g.:
            Team-based: [{"team0": "greedy", "team1": "random_legal"}]
            Seat-based: [{"seat_strategies": ["greedy", "random_legal", "greedy", "random_legal"]}]
            Default: None (self-play mode)

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
    if mode not in ["SMOKE", "QUICK", "FULL"]:
        raise ValueError(f"mode must be 'SMOKE', 'QUICK', or 'FULL', got '{mode}'")

    # Check cache
    cache_key = _compute_cache_key("features", mode, seed, contracts, trumps, seats, strategies, matchups)
    cache_path = _get_cache_path(cache_key)

    if cache_path.exists():
        print(f"Loading cached features from {cache_path.name}...")
        return pd.read_parquet(cache_path)

    # Generate new data
    print(f"Generating new feature dataset (mode={mode}, seed={seed})...")
    run_dir = _generate_experiment_data(mode, seed, contracts, trumps, seats, strategies, matchups)

    # Load features from bidless dataset
    dataset_dir = run_dir / "datasets"
    features_df = load_bidless_dataset(dataset_dir)

    # Normalize column names: rename trump_suit -> trump for consistency
    if 'trump_suit' in features_df.columns:
        features_df = features_df.rename(columns={'trump_suit': 'trump'})

    # Extract outcomes from logs and join (for on-the-fly generation, logs are always present)
    outcome_df = _load_outcomes_from_logs(run_dir)

    # Join on deal_id + seat + contract_type + trump
    # This ensures proper alignment even when features and outcomes have different data
    merge_keys = ['deal_id', 'seat', 'contract_type', 'trump']
    merged_df = features_df.merge(
        outcome_df[merge_keys + ['tricks_won', 'strategy_id']],
        on=merge_keys,
        how='inner'
    )

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
    strategies: Optional[List[Dict[str, str]]] = None,
    matchups: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Compute cache key from parameters.

    Uses deterministic serialization to ensure cache key stability:
    - Full strategy configs (name + class_name + params)
    - Sorted JSON for consistent ordering
    """
    key_parts = [
        data_type,
        mode,
        str(seed),
        "_".join(sorted(contracts)),
        "_".join(sorted(trumps)),
        "_".join(map(str, sorted(seats))),
    ]

    # Include full strategy configs in cache key (not just names)
    # Use deterministic JSON serialization for stability
    if strategies:
        strat_json = json.dumps(strategies, sort_keys=True)
        key_parts.append(strat_json)

    # Include matchups in cache key (deterministic order)
    if matchups:
        matchup_json = json.dumps(matchups, sort_keys=True)
        key_parts.append(matchup_json)

    key_str = "|".join(key_parts)
    hash_hex = hashlib.sha256(key_str.encode()).hexdigest()[:16]
    return f"{data_type}_{mode}_{seed}_{hash_hex}"


def _get_cache_path(cache_key: str) -> Path:
    """Get cache file path in system temp directory."""
    # Use system temp directory for caching
    cache_dir = Path(tempfile.gettempdir()) / "bid_euchre_notebook_cache"
    return cache_dir / f"{cache_key}.parquet"


def _generate_experiment_data(
    mode: str,
    seed: int,
    contracts: List[str],
    trumps: List[str],
    seats: List[int],
    strategies: Optional[List[Dict[str, str]]] = None,
    matchups: Optional[List[Dict[str, str]]] = None,
) -> Path:
    """Generate experiment data by running experiment runner.

    Returns:
        Path to run directory containing logs/ and datasets/
    """
    # Create temporary config
    config = _generate_temp_config(mode, seed, contracts, trumps, seats, strategies, matchups)

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
            "--emit-bidless-dataset",  # Required for features
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
    strategies: Optional[List[Dict[str, str]]] = None,
    matchups: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Generate temporary experiment config.

    Supports both self-play and head-to-head modes.

    Args:
        matchups: None = self-play for all strategies
                  List = head-to-head matchups (team-based or seat-based)

    Note: MATCHUPS=None runs self-play for EACH strategy in STRATEGIES.
          For single-strategy self-play, pass strategies=[{...}].
    """
    # Sample sizes by mode
    if mode == "SMOKE":
        n_per = 5  # ~5 deals per scenario (~30 total for 6 scenarios)
    elif mode == "QUICK":
        n_per = 50  # ~50 deals per scenario
    elif mode == "FULL":
        n_per = 2500
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Default strategies
    if strategies is None:
        strategies = [{"name": "greedy", "class_name": "GreedyStrategy"}]

    # Validate strategies
    if not strategies:
        raise ValueError("At least one strategy required")

    # Validate matchups
    if matchups is not None:
        if not matchups:
            raise ValueError(
                "MATCHUPS cannot be empty list. Use None for self-play mode, "
                "or provide at least one matchup for head-to-head mode."
            )

        # Validate matchup references
        strategy_names = {s["name"] for s in strategies}
        for matchup in matchups:
            team0 = matchup.get("team0")
            team1 = matchup.get("team1")
            seat_strategies = matchup.get("seat_strategies")

            if team0 and team1:
                if team0 not in strategy_names:
                    raise ValueError(
                        f"Matchup references unknown strategy: {team0}. "
                        f"Available: {sorted(strategy_names)}"
                    )
                if team1 not in strategy_names:
                    raise ValueError(
                        f"Matchup references unknown strategy: {team1}. "
                        f"Available: {sorted(strategy_names)}"
                    )
            elif seat_strategies:
                if len(seat_strategies) != 4:
                    raise ValueError(
                        f"seat_strategies must have length 4 (got {len(seat_strategies)}): {matchup}"
                    )
                unknown = [name for name in seat_strategies if name not in strategy_names]
                if unknown:
                    raise ValueError(
                        f"Matchup references unknown strategies: {unknown}. "
                        f"Available: {sorted(strategy_names)}"
                    )
            else:
                raise ValueError(
                    "Matchups must include team0/team1 or seat_strategies."
                )

    # Build scenarios (same as before)
    scenarios = []
    for contract in contracts:
        if contract == 'suit':
            for trump in trumps:
                scenarios.append({
                    'contract_type': 'suit',
                    'trump_suit': trump,
                })
        elif contract in ['high', 'low']:
            scenarios.append({'contract_type': contract})
        else:
            raise ValueError(f"Unknown contract type: {contract}")

    # Build config based on mode
    config = {
        'experiment_name': f'notebook_temp_{mode}_{seed}',
        'strategies': strategies,
        'scenarios': scenarios,
        'parameters': {
            'n_per': n_per,
            'log_level': 'hand',
        },
    }

    # Add matchups if specified (head-to-head mode)
    if matchups is not None:
        config['parameters']['mode'] = 'head_to_head_matrix'
        config['matchups'] = matchups

    return config


# ============================================================================
# Public RUN_DIR API (for loading from existing experiment runs)
# ============================================================================


def validate_run_dir(run_dir: str, require_logs: bool = False) -> Path:
    """Verify run directory exists and has required structure.

    Args:
        run_dir: Path to run directory (as string)
        require_logs: If True, require logs/ directory to exist.
                     If False (default), logs are optional if outcomes parquet exists.

    Returns:
        Validated Path object to the run directory

    Raises:
        FileNotFoundError: If run_dir doesn't exist
        ValueError: If run_dir is not a directory
    """
    run_path = Path(run_dir)

    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    if not run_path.is_dir():
        raise ValueError(f"Path is not a directory: {run_dir}")

    if require_logs:
        logs_dir = run_path / "logs"
        if not logs_dir.exists():
            raise FileNotFoundError(
                f"Logs directory not found: {logs_dir}. "
                "Expected run_dir/logs/ to contain JSONL log files."
            )

    return run_path


def load_outcomes_from_run_dir(run_dir: str, prefer_parquet: bool = True) -> pd.DataFrame:
    """Load outcome data from an existing experiment run directory.

    Prefers outcomes parquet when present (from --emit-bidless-outcomes-dataset),
    falls back to parsing JSONL logs when parquet is not available.

    Args:
        run_dir: Path to run directory
        prefer_parquet: If True (default), prefer bidless_outcomes.parquet when present.
                       Set to False to force log parsing even when parquet exists.

    Returns:
        DataFrame with columns:
            - deal_id: int
            - seat: int (0-3)
            - contract_type: str ("suit", "high", "low")
            - trump: str or None
            - tricks_won: int (0-10)
            - strategy_id: str
            Additional columns when loaded from parquet:
            - hand_id: int (globally unique)
            - matchup_id: str
            - team0_strategy, team1_strategy: str
            - team0_win: float (1.0=win, 0.5=tie, 0.0=loss)

    Raises:
        FileNotFoundError: If run_dir doesn't exist or no data source found
        ValueError: If no outcome data found
    """
    run_path = Path(run_dir)

    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    if not run_path.is_dir():
        raise ValueError(f"Path is not a directory: {run_dir}")

    # Try outcomes parquet first (preferred source when available)
    outcomes_parquet = run_path / "datasets" / "bidless_outcomes.parquet"
    if prefer_parquet and outcomes_parquet.exists():
        return _load_outcomes_from_parquet(outcomes_parquet)

    # Fall back to log parsing
    return _load_outcomes_from_logs(run_path)


def _load_outcomes_from_parquet(parquet_path: Path) -> pd.DataFrame:
    """Load outcomes from bidless_outcomes.parquet.

    The parquet file has per-hand granularity. This function expands
    to per-seat granularity for compatibility with existing code.

    Args:
        parquet_path: Path to bidless_outcomes.parquet

    Returns:
        DataFrame with per-seat outcomes
    """
    df = pd.read_parquet(parquet_path)

    # bidless_outcomes.parquet is per-hand; expand to per-seat for compatibility
    # Each hand has one row; we need 4 rows (one per seat)
    seat_records = []
    for _, row in df.iterrows():
        for seat in range(4):
            # Team 0 = seats 0, 2; Team 1 = seats 1, 3
            tricks_won = row["tricks_team0"] if seat in [0, 2] else row["tricks_team1"]
            seat_records.append({
                "hand_id": row["hand_id"],
                "deal_id": row["deal_id"],
                "seat": seat,
                "contract_type": row["contract_type"],
                "trump": row["trump_suit"],  # Normalize to 'trump' for consistency
                "tricks_won": tricks_won,
                "strategy_id": row["strategy_id"],
                "matchup_id": row["matchup_id"],
                "team0_strategy": row["team0_strategy"],
                "team1_strategy": row["team1_strategy"],
                "team0_win": row["team0_win"],
            })

    outcome_df = pd.DataFrame(seat_records)
    outcome_df = outcome_df.sort_values(["hand_id", "seat"]).reset_index(drop=True)
    return outcome_df


def _load_outcomes_from_logs(run_path: Path) -> pd.DataFrame:
    """Load outcomes from JSONL logs (legacy fallback).

    Args:
        run_path: Path to run directory containing logs/*.jsonl

    Returns:
        DataFrame with per-seat outcomes

    Raises:
        FileNotFoundError: If logs directory not found
        ValueError: If no hand_end events found
    """
    logs_dir = run_path / "logs"

    if not logs_dir.exists():
        raise FileNotFoundError(
            f"Logs directory not found: {logs_dir}. "
            "Run experiment with log_level != 'none' or use --emit-bidless-outcomes-dataset."
        )

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


def load_features_and_outcomes_from_run_dir(
    run_dir: str,
    prefer_parquet: bool = True,
) -> pd.DataFrame:
    """Load features from datasets/ and outcomes, joined by deal_id + seat.

    Prefers outcomes parquet when present (from --emit-bidless-outcomes-dataset),
    falls back to parsing JSONL logs when parquet is not available.

    This function:
    1. Validates the run directory structure
    2. Loads feature data from run_dir/datasets/bidless.parquet
    3. Loads outcome data (prefers parquet, falls back to logs)
    4. Joins on deal_id + seat + contract_type + trump

    Args:
        run_dir: Path to run directory containing datasets/ (and optionally logs/)
        prefer_parquet: If True (default), prefer bidless_outcomes.parquet when present.
                       Set to False to force log parsing even when parquet exists.

    Returns:
        DataFrame with columns:
            - deal_id: int
            - seat: int (0-3)
            - contract_type: str ("suit", "high", "low")
            - trump: str or None (normalized from trump_suit)
            - tricks_won: int (0-10)
            - strategy_id: str
            - feat_*: feature columns (trump_count, offsuit_aces, etc.)
            - hand_cards: list of str (if available)
            Additional columns when outcomes loaded from parquet:
            - hand_id: int (globally unique)
            - matchup_id: str
            - team0_strategy, team1_strategy: str
            - team0_win: float (1.0=win, 0.5=tie, 0.0=loss)

    Raises:
        FileNotFoundError: If run_dir or datasets/ doesn't exist
        ValueError: If no data found or join fails

    Note:
        The join is on [deal_id, seat, contract_type, trump] to ensure proper
        alignment even when features and outcomes have different data coverage.
    """
    run_path = Path(run_dir)

    if not run_path.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    if not run_path.is_dir():
        raise ValueError(f"Path is not a directory: {run_dir}")

    # Verify datasets/ exists
    dataset_dir = run_path / "datasets"
    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"Datasets directory not found: {dataset_dir}. "
            "Expected run_dir/datasets/ to contain Parquet files."
        )

    # Load features from bidless dataset
    features_df = load_bidless_dataset(dataset_dir)

    # Normalize column names: rename trump_suit -> trump for consistency
    if 'trump_suit' in features_df.columns:
        features_df = features_df.rename(columns={'trump_suit': 'trump'})

    # Load outcomes (prefers parquet, falls back to logs)
    outcomes_parquet = run_path / "datasets" / "bidless_outcomes.parquet"
    if prefer_parquet and outcomes_parquet.exists():
        outcome_df = _load_outcomes_from_parquet(outcomes_parquet)
    else:
        outcome_df = _load_outcomes_from_logs(run_path)

    # Determine columns to include from outcomes (depends on source)
    outcome_cols = ['deal_id', 'seat', 'contract_type', 'trump', 'tricks_won', 'strategy_id']
    # Add extra columns from parquet if available
    for col in ['hand_id', 'matchup_id', 'team0_strategy', 'team1_strategy', 'team0_win']:
        if col in outcome_df.columns:
            outcome_cols.append(col)

    # Join on deal_id + seat + contract_type + trump
    merge_keys = ['deal_id', 'seat', 'contract_type', 'trump']

    # Check that merge keys exist in both dataframes
    for key in merge_keys:
        if key not in features_df.columns:
            raise ValueError(f"Missing merge key '{key}' in features DataFrame")
        if key not in outcome_df.columns:
            raise ValueError(f"Missing merge key '{key}' in outcomes DataFrame")

    # Select outcome columns that exist
    outcome_cols_present = [c for c in outcome_cols if c in outcome_df.columns]
    merged_df = features_df.merge(
        outcome_df[outcome_cols_present],
        on=merge_keys,
        how='inner'
    )

    if len(merged_df) == 0:
        raise ValueError(
            "Join produced empty DataFrame. Check that features and outcomes "
            "have matching deal_id + seat + contract_type + trump values."
        )

    return merged_df

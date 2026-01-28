"""Data loading utilities for bidless diagnostics.

Handles loading bidless datasets from Parquet or JSONL format,
with proper metadata extraction and DataFrame construction.
"""

import json
from pathlib import Path
from typing import Any, Dict, Union

import pandas as pd


def load_meta(dataset_dir: Union[str, Path]) -> Dict[str, Any]:
    """Load bidless dataset metadata.

    Args:
        dataset_dir: Directory containing bidless_meta.json

    Returns:
        Metadata dict with run_id, schema versions, paths

    Raises:
        FileNotFoundError: If meta file doesn't exist
    """
    meta_path = Path(dataset_dir) / "bidless_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {meta_path}")

    with open(meta_path, "r") as f:
        return json.load(f)


def load_bidless_dataset(
    dataset_dir: Union[str, Path],
    format: str = "auto",
) -> pd.DataFrame:
    """Load bidless dataset as a pandas DataFrame.

    Args:
        dataset_dir: Directory containing bidless.parquet or bidless.jsonl
        format: "parquet", "jsonl", or "auto" (detect from meta)

    Returns:
        DataFrame with columns:
            - hand_id: int
            - seat: int (0-3)
            - dealer_seat: int (0-3)
            - deal_id: int or None
            - hand_cards: list of str (e.g., ["AS", "KH", ...])
            - hand_features: dict of features
            - hand_feature_schema_version: int
            - contract_type: str ("suit", "high", "low")
            - trump_suit: str or None

    Raises:
        FileNotFoundError: If dataset file doesn't exist
    """
    dataset_dir = Path(dataset_dir)

    # Auto-detect format
    if format == "auto":
        if (dataset_dir / "bidless.parquet").exists():
            format = "parquet"
        elif (dataset_dir / "bidless.jsonl").exists():
            format = "jsonl"
        else:
            raise FileNotFoundError(
                f"No bidless dataset found in {dataset_dir}. "
                "Expected bidless.parquet or bidless.jsonl"
            )

    if format == "parquet":
        df = _load_parquet(dataset_dir / "bidless.parquet")
    else:
        df = _load_jsonl(dataset_dir / "bidless.jsonl")

    # Flatten hand_features into separate columns for easier analysis
    df = _flatten_features(df)

    return df


def _load_parquet(path: Path) -> pd.DataFrame:
    """Load from Parquet format."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    return table.to_pandas()


def _load_jsonl(path: Path) -> pd.DataFrame:
    """Load from JSONL format."""
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return pd.DataFrame(records)


def _flatten_features(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten hand_features dict into separate columns.

    Creates columns like feat_trump_count, feat_offsuit_aces, etc.
    Keeps original hand_features column for reference.
    """
    if "hand_features" not in df.columns:
        return df

    # Extract feature columns
    feature_rows = df["hand_features"].tolist()
    if not feature_rows or feature_rows[0] is None:
        return df

    # Get all feature keys from first non-None row
    feature_keys = set()
    for row in feature_rows:
        if row is not None:
            feature_keys.update(row.keys())
            break

    # Create feature columns
    for key in sorted(feature_keys):
        col_name = f"feat_{key}"
        df[col_name] = df["hand_features"].apply(
            lambda x: x.get(key) if x else None
        )

    return df


def get_dataset_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute summary statistics for a loaded dataset.

    Args:
        df: DataFrame from load_bidless_dataset

    Returns:
        Dict with summary statistics
    """
    n_rows = len(df)
    n_hands = df["hand_id"].nunique() if "hand_id" in df.columns else 0
    n_seats = df["seat"].nunique() if "seat" in df.columns else 0

    # Contract distribution
    contract_counts = {}
    if "contract_type" in df.columns:
        contract_counts = df["contract_type"].value_counts().to_dict()

    # Trump distribution (for suit contracts)
    trump_counts = {}
    if "trump_suit" in df.columns:
        trump_counts = df["trump_suit"].dropna().value_counts().to_dict()

    # Feature columns
    feat_cols = [c for c in df.columns if c.startswith("feat_")]

    return {
        "n_rows": n_rows,
        "n_hands": n_hands,
        "rows_per_hand": n_rows / n_hands if n_hands > 0 else 0,
        "n_seats_observed": n_seats,
        "contract_distribution": contract_counts,
        "trump_distribution": trump_counts,
        "feature_columns": feat_cols,
    }

"""
Deterministic split manifests for reproducible train/val/test partitioning.

Split policy:
- Promotion-track: mandatory 3-way (train/val/test)
- Exploratory: 2-way (train/test) allowed

All splits are grouped by hand_id to prevent data leakage.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..experiments.meta import sha256_file, utc_now_iso


@dataclass(frozen=True)
class SplitManifest:
    """Manifest recording deterministic dataset split parameters and hashes."""

    schema_version: int
    split_seed: int
    split_type: str  # "two_way" | "three_way"
    train_fraction: float
    val_fraction: Optional[float]
    test_fraction: float
    total_hand_ids: int
    train_hand_ids: int
    val_hand_ids: Optional[int]
    test_hand_ids: int
    source_run_id: str
    source_parquet_sha256: str
    partition_hashes: dict  # {"train": sha256, "val": sha256, "test": sha256}
    created_at_utc: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SplitManifest:
        return cls(**d)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> SplitManifest:
        with open(path) as f:
            return cls.from_dict(json.load(f))


def _hash_hand_ids(hand_ids: np.ndarray) -> str:
    """SHA256 of sorted hand_id array for partition identity."""
    sorted_ids = np.sort(hand_ids)
    return hashlib.sha256(sorted_ids.tobytes()).hexdigest()


def create_split(
    df: pd.DataFrame,
    seed: int,
    source_run_id: str,
    source_parquet_path: str,
    split_type: str = "two_way",
    train_frac: float = 0.8,
    val_frac: float = 0.1,
    test_frac: float = 0.1,
) -> tuple[pd.DataFrame, Optional[pd.DataFrame], pd.DataFrame, SplitManifest]:
    """Split dataframe by hand_id and return partitions with manifest.

    Args:
        df: DataFrame with 'hand_id' column.
        seed: Random seed for reproducibility.
        source_run_id: Run ID for provenance.
        source_parquet_path: Path to source parquet for SHA256.
        split_type: "two_way" or "three_way".
        train_frac: Training fraction.
        val_frac: Validation fraction (three_way only).
        test_frac: Test fraction.

    Returns:
        (train_df, val_df_or_None, test_df, manifest)
    """
    if split_type not in ("two_way", "three_way"):
        raise ValueError(f"split_type must be 'two_way' or 'three_way', got {split_type!r}")

    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    if split_type == "two_way":
        split_idx = int(len(unique_ids) * train_frac)
        train_ids = unique_ids[:split_idx]
        test_ids = unique_ids[split_idx:]

        train_mask = df["hand_id"].isin(set(train_ids))
        train_df = df[train_mask].copy()
        test_df = df[~train_mask].copy()
        val_df = None

        partition_hashes = {
            "train": _hash_hand_ids(train_ids),
            "test": _hash_hand_ids(test_ids),
        }

        manifest = SplitManifest(
            schema_version=1,
            split_seed=seed,
            split_type="two_way",
            train_fraction=train_frac,
            val_fraction=None,
            test_fraction=round(1.0 - train_frac, 4),
            total_hand_ids=len(unique_ids),
            train_hand_ids=len(train_ids),
            val_hand_ids=None,
            test_hand_ids=len(test_ids),
            source_run_id=source_run_id,
            source_parquet_sha256=sha256_file(source_parquet_path),
            partition_hashes=partition_hashes,
            created_at_utc=utc_now_iso(),
        )

    else:  # three_way
        n = len(unique_ids)
        train_end = int(n * train_frac)
        val_end = train_end + int(n * val_frac)

        train_ids = unique_ids[:train_end]
        val_ids = unique_ids[train_end:val_end]
        test_ids = unique_ids[val_end:]

        train_set = set(train_ids)
        val_set = set(val_ids)

        train_df = df[df["hand_id"].isin(train_set)].copy()
        val_df = df[df["hand_id"].isin(val_set)].copy()
        test_df = df[~df["hand_id"].isin(train_set | val_set)].copy()

        partition_hashes = {
            "train": _hash_hand_ids(train_ids),
            "val": _hash_hand_ids(val_ids),
            "test": _hash_hand_ids(test_ids),
        }

        manifest = SplitManifest(
            schema_version=1,
            split_seed=seed,
            split_type="three_way",
            train_fraction=train_frac,
            val_fraction=val_frac,
            test_fraction=round(1.0 - train_frac - val_frac, 4),
            total_hand_ids=len(unique_ids),
            train_hand_ids=len(train_ids),
            val_hand_ids=len(val_ids),
            test_hand_ids=len(test_ids),
            source_run_id=source_run_id,
            source_parquet_sha256=sha256_file(source_parquet_path),
            partition_hashes=partition_hashes,
            created_at_utc=utc_now_iso(),
        )

    return train_df, val_df, test_df, manifest


def verify_split_manifest(manifest_path: str | Path, df: pd.DataFrame, seed: int) -> bool:
    """Verify a saved manifest matches the current data and seed.

    Returns True if partition hashes match, False otherwise.
    """
    manifest = SplitManifest.load(manifest_path)

    if manifest.split_seed != seed:
        return False

    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    if manifest.split_type == "two_way":
        split_idx = int(len(unique_ids) * manifest.train_fraction)
        train_ids = unique_ids[:split_idx]
        test_ids = unique_ids[split_idx:]
        return (
            _hash_hand_ids(train_ids) == manifest.partition_hashes["train"]
            and _hash_hand_ids(test_ids) == manifest.partition_hashes["test"]
        )
    else:
        n = len(unique_ids)
        train_end = int(n * manifest.train_fraction)
        val_end = train_end + int(n * manifest.val_fraction)
        train_ids = unique_ids[:train_end]
        val_ids = unique_ids[train_end:val_end]
        test_ids = unique_ids[val_end:]
        return (
            _hash_hand_ids(train_ids) == manifest.partition_hashes["train"]
            and _hash_hand_ids(val_ids) == manifest.partition_hashes["val"]
            and _hash_hand_ids(test_ids) == manifest.partition_hashes["test"]
        )

"""
Deterministic split manifests for train/val/test partitioning.

Provides grouped-by-hand_id splitting with persistent manifests that
record partition hashes for reproducibility and corruption detection.

Split policy:
  - Promotion-track: 3-way (train/val/test) required
  - Exploratory: 2-way (train/test) allowed
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _utc_now_iso() -> str:
    """UTC time in ISO8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: str) -> str:
    """SHA256 of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclasses.dataclass(frozen=True)
class SplitManifest:
    """Persistent record of a train/val/test split.

    Attributes:
        schema_version: Always 1.
        split_seed: Random seed used for partitioning.
        split_type: "two_way" or "three_way".
        train_fraction: Fraction of hand_ids in train set.
        val_fraction: Fraction of hand_ids in val set (None for two_way).
        test_fraction: Fraction of hand_ids in test set.
        total_hand_ids: Number of unique hand_ids before split.
        train_hand_ids: Number of unique hand_ids in train set.
        val_hand_ids: Number of unique hand_ids in val set (None for two_way).
        test_hand_ids: Number of unique hand_ids in test set.
        source_run_id: Run identifier the data came from.
        source_parquet_sha256: SHA256 of the source parquet file.
        partition_hashes: SHA256 of sorted hand_id lists per partition.
        created_at_utc: ISO8601 timestamp.
    """

    schema_version: int
    split_seed: int
    split_type: str
    train_fraction: float
    val_fraction: float | None
    test_fraction: float
    total_hand_ids: int
    train_hand_ids: int
    val_hand_ids: int | None
    test_hand_ids: int
    source_run_id: str
    source_parquet_sha256: str
    partition_hashes: dict[str, str]
    created_at_utc: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> SplitManifest:
        return cls(**{k: v for k, v in d.items() if k in {f.name for f in dataclasses.fields(cls)}})

    def save(self, path: str | Path) -> None:
        """Write manifest to JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> SplitManifest:
        """Load manifest from JSON file."""
        d = json.loads(Path(path).read_text())
        return cls.from_dict(d)


def _hash_hand_ids(hand_ids: np.ndarray) -> str:
    """SHA256 of sorted hand_id values as a stable fingerprint."""
    sorted_ids = np.sort(hand_ids)
    h = hashlib.sha256()
    for hid in sorted_ids:
        h.update(str(int(hid)).encode())
    return h.hexdigest()


def create_grouped_split(
    df: pd.DataFrame,
    seed: int,
    source_run_id: str,
    source_parquet_path: str,
    split_type: str = "two_way",
    train_frac: float = 0.8,
    val_frac: float = 0.1,
    test_frac: float = 0.1,
) -> tuple[pd.DataFrame, pd.DataFrame | None, pd.DataFrame, SplitManifest]:
    """Split DataFrame by hand_id groups and return partitions + manifest.

    Args:
        df: DataFrame with 'hand_id' column.
        seed: Random seed for reproducible partitioning.
        source_run_id: Run identifier for provenance.
        source_parquet_path: Path to source parquet (for SHA256).
        split_type: "two_way" or "three_way".
        train_frac: Fraction for training (used in both modes).
        val_frac: Fraction for validation (three_way only).
        test_frac: Fraction for test.

    Returns:
        (train_df, val_df_or_None, test_df, manifest)
    """
    if split_type not in ("two_way", "three_way"):
        raise ValueError(f"split_type must be 'two_way' or 'three_way', got {split_type!r}")

    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    n_total = len(unique_ids)

    if split_type == "two_way":
        split_idx = int(n_total * train_frac)
        train_ids = unique_ids[:split_idx]
        test_ids = unique_ids[split_idx:]
        val_ids = None

        train_df = df[df["hand_id"].isin(set(train_ids))]
        test_df = df[df["hand_id"].isin(set(test_ids))]
        val_df = None

        partition_hashes = {
            "train": _hash_hand_ids(train_ids),
            "test": _hash_hand_ids(test_ids),
        }

        manifest = SplitManifest(
            schema_version=1,
            split_seed=seed,
            split_type="two_way",
            train_fraction=round(len(train_ids) / n_total, 4),
            val_fraction=None,
            test_fraction=round(len(test_ids) / n_total, 4),
            total_hand_ids=n_total,
            train_hand_ids=len(train_ids),
            val_hand_ids=None,
            test_hand_ids=len(test_ids),
            source_run_id=source_run_id,
            source_parquet_sha256=_sha256_file(source_parquet_path),
            partition_hashes=partition_hashes,
            created_at_utc=_utc_now_iso(),
        )

    else:  # three_way
        # Validate fractions sum to ~1.0
        total_frac = train_frac + val_frac + test_frac
        if abs(total_frac - 1.0) > 0.01:
            raise ValueError(
                f"Fractions must sum to ~1.0 for three_way split, "
                f"got {train_frac}+{val_frac}+{test_frac}={total_frac}"
            )

        train_end = int(n_total * train_frac)
        val_end = train_end + int(n_total * val_frac)
        train_ids = unique_ids[:train_end]
        val_ids = unique_ids[train_end:val_end]
        test_ids = unique_ids[val_end:]

        train_df = df[df["hand_id"].isin(set(train_ids))]
        val_df = df[df["hand_id"].isin(set(val_ids))]
        test_df = df[df["hand_id"].isin(set(test_ids))]

        partition_hashes = {
            "train": _hash_hand_ids(train_ids),
            "val": _hash_hand_ids(val_ids),
            "test": _hash_hand_ids(test_ids),
        }

        manifest = SplitManifest(
            schema_version=1,
            split_seed=seed,
            split_type="three_way",
            train_fraction=round(len(train_ids) / n_total, 4),
            val_fraction=round(len(val_ids) / n_total, 4),
            test_fraction=round(len(test_ids) / n_total, 4),
            total_hand_ids=n_total,
            train_hand_ids=len(train_ids),
            val_hand_ids=len(val_ids),
            test_hand_ids=len(test_ids),
            source_run_id=source_run_id,
            source_parquet_sha256=_sha256_file(source_parquet_path),
            partition_hashes=partition_hashes,
            created_at_utc=_utc_now_iso(),
        )

    return train_df, val_df, test_df, manifest


def verify_split_manifest(manifest: SplitManifest, df: pd.DataFrame, seed: int) -> bool:
    """Verify a manifest matches a DataFrame by re-computing partition hashes.

    Re-runs the split with the same seed and checks that partition hashes match.

    Returns:
        True if manifest is consistent with the data.
    """
    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    n_total = len(unique_ids)

    if manifest.split_type == "two_way":
        split_idx = int(n_total * manifest.train_fraction)
        train_ids = unique_ids[:split_idx]
        test_ids = unique_ids[split_idx:]

        return (
            _hash_hand_ids(train_ids) == manifest.partition_hashes.get("train")
            and _hash_hand_ids(test_ids) == manifest.partition_hashes.get("test")
        )
    else:
        train_end = int(n_total * manifest.train_fraction)
        val_end = train_end + int(n_total * (manifest.val_fraction or 0))
        train_ids = unique_ids[:train_end]
        val_ids = unique_ids[train_end:val_end]
        test_ids = unique_ids[val_end:]

        return (
            _hash_hand_ids(train_ids) == manifest.partition_hashes.get("train")
            and _hash_hand_ids(val_ids) == manifest.partition_hashes.get("val")
            and _hash_hand_ids(test_ids) == manifest.partition_hashes.get("test")
        )

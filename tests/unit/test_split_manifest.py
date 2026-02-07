"""
Unit tests for deterministic split manifests.

Tests:
- Determinism (same seed = same partition hashes)
- Two-way vs three-way modes
- Manifest round-trip (save/load)
- Verification of manifest against data
- Corruption detection
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bid_euchre.models.splits import (
    SplitManifest,
    _hash_hand_ids,
    create_grouped_split,
    verify_split_manifest,
)


@pytest.fixture
def sample_parquet(tmp_path: Path) -> Path:
    """Create a small parquet file for testing."""
    n_hands = 100
    rows = []
    for hand_id in range(n_hands):
        for seat in range(4):
            rows.append({"hand_id": hand_id, "seat": seat, "tricks_won": 5.0})

    df = pd.DataFrame(rows)
    parquet_path = tmp_path / "bidless.parquet"
    df.to_parquet(parquet_path)
    return parquet_path


@pytest.fixture
def sample_df(sample_parquet: Path) -> pd.DataFrame:
    return pd.read_parquet(sample_parquet)


class TestCreateGroupedSplit:
    """Test create_grouped_split function."""

    def test_two_way_basic(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        train, val, test, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="test_run",
            source_parquet_path=str(sample_parquet),
            split_type="two_way",
        )
        assert val is None
        assert len(train) > 0
        assert len(test) > 0
        assert len(train) + len(test) == len(sample_df)
        assert manifest.split_type == "two_way"
        assert manifest.val_hand_ids is None
        assert manifest.val_fraction is None

    def test_three_way_basic(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        train, val, test, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="test_run",
            source_parquet_path=str(sample_parquet),
            split_type="three_way",
        )
        assert val is not None
        assert len(train) > 0
        assert len(val) > 0
        assert len(test) > 0
        assert len(train) + len(val) + len(test) == len(sample_df)
        assert manifest.split_type == "three_way"
        assert manifest.val_hand_ids is not None
        assert manifest.val_fraction is not None

    def test_determinism(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        """Same seed produces identical partition hashes."""
        _, _, _, m1 = create_grouped_split(
            sample_df, seed=42,
            source_run_id="test_run",
            source_parquet_path=str(sample_parquet),
        )
        _, _, _, m2 = create_grouped_split(
            sample_df, seed=42,
            source_run_id="test_run",
            source_parquet_path=str(sample_parquet),
        )
        assert m1.partition_hashes == m2.partition_hashes

    def test_different_seed_different_hashes(
        self, sample_df: pd.DataFrame, sample_parquet: Path
    ) -> None:
        _, _, _, m1 = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        _, _, _, m2 = create_grouped_split(
            sample_df, seed=99,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        assert m1.partition_hashes != m2.partition_hashes

    def test_no_hand_id_overlap(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        train, val, test, _ = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
            split_type="three_way",
        )
        train_ids = set(train["hand_id"].unique())
        val_ids = set(val["hand_id"].unique())
        test_ids = set(test["hand_id"].unique())

        assert train_ids.isdisjoint(val_ids)
        assert train_ids.isdisjoint(test_ids)
        assert val_ids.isdisjoint(test_ids)

    def test_invalid_split_type(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        with pytest.raises(ValueError, match="split_type must be"):
            create_grouped_split(
                sample_df, seed=42,
                source_run_id="run",
                source_parquet_path=str(sample_parquet),
                split_type="four_way",
            )

    def test_bad_fractions_rejected(
        self, sample_df: pd.DataFrame, sample_parquet: Path
    ) -> None:
        with pytest.raises(ValueError, match="Fractions must sum"):
            create_grouped_split(
                sample_df, seed=42,
                source_run_id="run",
                source_parquet_path=str(sample_parquet),
                split_type="three_way",
                train_frac=0.5,
                val_frac=0.5,
                test_frac=0.5,
            )

    def test_manifest_metadata(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        _, _, _, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="my_run",
            source_parquet_path=str(sample_parquet),
        )
        assert manifest.schema_version == 1
        assert manifest.split_seed == 42
        assert manifest.source_run_id == "my_run"
        assert manifest.source_parquet_sha256  # non-empty
        assert manifest.created_at_utc  # non-empty
        assert manifest.total_hand_ids == 100


class TestSplitManifestSerialization:
    """Test SplitManifest save/load round-trip."""

    def test_round_trip(self, sample_df: pd.DataFrame, sample_parquet: Path, tmp_path: Path) -> None:
        _, _, _, original = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        manifest_path = tmp_path / "manifest.json"
        original.save(manifest_path)
        loaded = SplitManifest.load(manifest_path)
        assert loaded == original

    def test_to_dict_json_serializable(
        self, sample_df: pd.DataFrame, sample_parquet: Path
    ) -> None:
        _, _, _, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        # Should not raise
        json.dumps(manifest.to_dict())


class TestVerifySplitManifest:
    """Test manifest verification."""

    def test_valid_manifest(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        _, _, _, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        assert verify_split_manifest(manifest, sample_df, seed=42) is True

    def test_wrong_seed_fails(self, sample_df: pd.DataFrame, sample_parquet: Path) -> None:
        _, _, _, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
        )
        assert verify_split_manifest(manifest, sample_df, seed=99) is False

    def test_three_way_verification(
        self, sample_df: pd.DataFrame, sample_parquet: Path
    ) -> None:
        _, _, _, manifest = create_grouped_split(
            sample_df, seed=42,
            source_run_id="run",
            source_parquet_path=str(sample_parquet),
            split_type="three_way",
        )
        assert verify_split_manifest(manifest, sample_df, seed=42) is True
        assert verify_split_manifest(manifest, sample_df, seed=99) is False


class TestHashHandIds:
    """Test _hash_hand_ids determinism."""

    def test_deterministic(self) -> None:
        ids = np.array([3, 1, 2])
        assert _hash_hand_ids(ids) == _hash_hand_ids(ids)

    def test_order_independent(self) -> None:
        """Hash of [3,1,2] equals hash of [2,1,3] (sorted internally)."""
        assert _hash_hand_ids(np.array([3, 1, 2])) == _hash_hand_ids(np.array([2, 1, 3]))

    def test_different_ids_different_hash(self) -> None:
        assert _hash_hand_ids(np.array([1, 2, 3])) != _hash_hand_ids(np.array([4, 5, 6]))

"""Tests for deterministic split manifests."""

import numpy as np
import pandas as pd
import pytest

from bid_euchre.models.splits import SplitManifest, create_split, verify_split_manifest


@pytest.fixture
def sample_df():
    """Create a sample DataFrame with hand_id for testing splits."""
    # 100 unique hand_ids, 4 rows per hand (simulating seat-level data)
    hand_ids = np.repeat(np.arange(100), 4)
    return pd.DataFrame(
        {
            "hand_id": hand_ids,
            "tricks_won": np.random.RandomState(0).randint(0, 11, len(hand_ids)),
            "feature_a": np.random.RandomState(1).randn(len(hand_ids)),
        }
    )


@pytest.fixture
def parquet_path(tmp_path, sample_df):
    """Save sample data as parquet and return path."""
    path = tmp_path / "test.parquet"
    sample_df.to_parquet(path)
    return str(path)


def test_two_way_split_determinism(sample_df, parquet_path):
    """Same seed produces identical partition hashes."""
    train1, _, test1, m1 = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    train2, _, test2, m2 = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    assert m1.partition_hashes["train"] == m2.partition_hashes["train"]
    assert m1.partition_hashes["test"] == m2.partition_hashes["test"]


def test_three_way_split_determinism(sample_df, parquet_path):
    """Same seed produces identical partition hashes for 3-way."""
    _, val1, _, m1 = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="three_way",
    )
    _, val2, _, m2 = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="three_way",
    )
    assert m1.partition_hashes == m2.partition_hashes


def test_two_way_split_sizes(sample_df, parquet_path):
    """Two-way split has correct approximate sizes."""
    train, val, test, manifest = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    assert val is None
    assert manifest.val_hand_ids is None
    assert manifest.split_type == "two_way"
    assert manifest.train_hand_ids + manifest.test_hand_ids == manifest.total_hand_ids
    assert manifest.train_hand_ids == 80  # 80% of 100
    assert manifest.test_hand_ids == 20


def test_three_way_split_sizes(sample_df, parquet_path):
    """Three-way split has correct approximate sizes."""
    train, val, test, manifest = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="three_way",
    )
    assert val is not None
    assert manifest.val_hand_ids is not None
    assert manifest.split_type == "three_way"
    total = manifest.train_hand_ids + manifest.val_hand_ids + manifest.test_hand_ids
    assert total == manifest.total_hand_ids


def test_manifest_roundtrip(tmp_path, sample_df, parquet_path):
    """Save and load manifest preserves all fields."""
    _, _, _, manifest = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="three_way",
    )
    path = tmp_path / "manifest.json"
    manifest.save(path)
    loaded = SplitManifest.load(path)
    assert loaded == manifest


def test_verify_manifest_correct(tmp_path, sample_df, parquet_path):
    """Verify returns True for matching data and seed."""
    _, _, _, manifest = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    path = tmp_path / "manifest.json"
    manifest.save(path)
    assert verify_split_manifest(path, sample_df, seed=42) is True


def test_verify_manifest_wrong_seed(tmp_path, sample_df, parquet_path):
    """Verify returns False for different seed."""
    _, _, _, manifest = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    path = tmp_path / "manifest.json"
    manifest.save(path)
    assert verify_split_manifest(path, sample_df, seed=99) is False


def test_invalid_split_type(sample_df, parquet_path):
    """Invalid split_type raises ValueError."""
    with pytest.raises(ValueError, match="split_type"):
        create_split(
            sample_df,
            seed=42,
            source_run_id="run1",
            source_parquet_path=parquet_path,
            split_type="invalid",
        )


def test_no_hand_id_leakage(sample_df, parquet_path):
    """Train and test hand_ids are completely disjoint."""
    train, _, test, _ = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="two_way",
    )
    train_ids = set(train["hand_id"].unique())
    test_ids = set(test["hand_id"].unique())
    assert train_ids.isdisjoint(test_ids)


def test_three_way_no_leakage(sample_df, parquet_path):
    """All three partitions have disjoint hand_ids."""
    train, val, test, _ = create_split(
        sample_df,
        seed=42,
        source_run_id="run1",
        source_parquet_path=parquet_path,
        split_type="three_way",
    )
    train_ids = set(train["hand_id"].unique())
    val_ids = set(val["hand_id"].unique())
    test_ids = set(test["hand_id"].unique())
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)

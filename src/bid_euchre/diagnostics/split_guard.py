"""Runtime split-access enforcement for HITL notebook workflow.

Provides ``require_split()`` which filters a DataFrame to a requested
partition while enforcing visibility rules:

- During HITL review (``active_split="val"``), test-split access is blocked.
- During blind test (``active_split="test"``), test-split access is allowed.
- Partition hashes are re-derived and verified against the manifest.

This module is the *runtime* complement to the *static* split manifest
validation in ``models.splits.verify_split_manifest``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bid_euchre.models.splits import SplitManifest, _hash_hand_ids

# Valid split names by manifest type
_VALID_SPLITS_THREE_WAY = frozenset({"train", "val", "test"})
_VALID_SPLITS_TWO_WAY = frozenset({"train", "test"})


def _partition_hand_ids(
    df: pd.DataFrame,
    manifest: SplitManifest,
    seed: int,
) -> dict[str, np.ndarray]:
    """Re-derive partition boundaries from manifest metadata.

    Returns a dict mapping split name -> array of hand_ids.
    """
    unique_ids = df["hand_id"].unique()
    rng = np.random.RandomState(seed)
    rng.shuffle(unique_ids)

    n_total = len(unique_ids)

    if manifest.split_type == "two_way":
        split_idx = int(n_total * manifest.train_fraction)
        return {
            "train": unique_ids[:split_idx],
            "test": unique_ids[split_idx:],
        }
    else:  # three_way
        train_end = int(n_total * manifest.train_fraction)
        val_end = train_end + int(n_total * (manifest.val_fraction or 0))
        return {
            "train": unique_ids[:train_end],
            "val": unique_ids[train_end:val_end],
            "test": unique_ids[val_end:],
        }


def require_split(
    df: pd.DataFrame,
    manifest: SplitManifest,
    allowed_split: str,
    seed: int,
    *,
    active_split: str = "val",
) -> pd.DataFrame:
    """Filter *df* to the requested split with access-control enforcement.

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset with ``hand_id`` column.
    manifest : SplitManifest
        Split manifest defining partition boundaries and hashes.
    allowed_split : str
        Which partition to return: ``"train"``, ``"val"``, or ``"test"``.
    seed : int
        The split seed (must match ``manifest.split_seed``).
    active_split : str, default ``"val"``
        Current notebook context. When ``"val"`` (HITL mode), requesting
        ``"test"`` raises ``ValueError``.

    Returns
    -------
    pd.DataFrame
        Rows belonging to the requested partition.

    Raises
    ------
    ValueError
        If *allowed_split* is invalid, test access is blocked, or
        partition hashes don't match the manifest.
    """
    # Determine valid splits for this manifest type
    if manifest.split_type == "three_way":
        valid_splits = _VALID_SPLITS_THREE_WAY
    else:
        valid_splits = _VALID_SPLITS_TWO_WAY

    # Validate split name
    if allowed_split not in valid_splits:
        if allowed_split == "val" and manifest.split_type == "two_way":
            raise ValueError(
                f"Split 'val' is not available in a two_way manifest. "
                f"Valid splits: {sorted(valid_splits)}"
            )
        raise ValueError(
            f"Unknown split name {allowed_split!r}. "
            f"Valid splits for {manifest.split_type}: {sorted(valid_splits)}"
        )

    # Enforce test-split access control
    if allowed_split == "test" and active_split == "val":
        raise ValueError(
            "Test split access blocked during HITL review. "
            "Set active_split='test' for blind test evaluation."
        )

    # Re-derive partitions
    partitions = _partition_hand_ids(df, manifest, seed)

    # Verify partition hash matches manifest
    requested_ids = partitions[allowed_split]
    computed_hash = _hash_hand_ids(requested_ids)
    expected_hash = manifest.partition_hashes.get(allowed_split)

    if computed_hash != expected_hash:
        raise ValueError(
            f"Partition hash mismatch for split {allowed_split!r}. "
            f"Computed: {computed_hash[:16]}..., "
            f"Expected: {(expected_hash or 'None')[:16]}... "
            f"Data may have changed since the manifest was created."
        )

    # Filter and return
    id_set = set(requested_ids)
    return df[df["hand_id"].isin(id_set)].copy()

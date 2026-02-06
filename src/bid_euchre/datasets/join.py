"""
Join bidless features and outcomes for analysis.

Provides the canonical join between per-seat feature rows (bidless.parquet)
and per-hand outcome rows (bidless_outcomes.parquet).
"""

import pandas as pd


def join_features_outcomes(
    bidless_path: str,
    outcomes_path: str,
) -> pd.DataFrame:
    """
    Join bidless feature data with outcome data.

    Bidless has per-seat rows (hand_id, seat, hand_features struct).
    Outcomes has per-hand rows (hand_id, tricks_team0, tricks_team1).

    The join assigns each seat its team's tricks_won:
      - Seats 0, 2 → team 0 → tricks_team0
      - Seats 1, 3 → team 1 → tricks_team1

    Args:
        bidless_path: Path to bidless.parquet
        outcomes_path: Path to bidless_outcomes.parquet

    Returns:
        DataFrame with columns: hand_id, seat, contract_type, trump_suit,
        <41 feature columns>, tricks_won
    """
    features_df = pd.read_parquet(bidless_path)
    outcomes_df = pd.read_parquet(outcomes_path)

    # Flatten the hand_features struct into individual columns
    if "hand_features" in features_df.columns:
        hf = pd.json_normalize(features_df["hand_features"])
        features_df = pd.concat(
            [features_df.drop(columns=["hand_features"]), hf], axis=1
        )

    # Keep only the columns we need from outcomes
    outcomes_subset = outcomes_df[
        ["hand_id", "contract_type", "trump_suit", "tricks_team0", "tricks_team1"]
    ].copy()

    # Join on hand_id + contract_type + trump_suit (outcomes may have
    # multiple strategy matchups; deduplicate by taking the first)
    outcomes_dedup = outcomes_subset.drop_duplicates(
        subset=["hand_id", "contract_type", "trump_suit"], keep="first"
    )

    merged = features_df.merge(
        outcomes_dedup,
        on=["hand_id", "contract_type", "trump_suit"],
        how="inner",
    )

    # Assign tricks_won based on team membership
    import numpy as np

    merged["tricks_won"] = np.where(
        merged["seat"].isin([0, 2]),
        merged["tricks_team0"],
        merged["tricks_team1"],
    )

    # Drop intermediate columns
    merged = merged.drop(columns=["tricks_team0", "tricks_team1"])

    return merged

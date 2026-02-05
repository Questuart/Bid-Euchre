"""
Unit tests for join_features_outcomes utility.
"""

import pandas as pd

from bid_euchre.datasets.join import join_features_outcomes


def _make_bidless_parquet(path, hand_ids, contract_types, trump_suits):
    """Create a minimal bidless.parquet for testing."""
    rows = []
    for hand_id in hand_ids:
        for ct, ts in zip(contract_types, trump_suits):
            for seat in range(4):
                rows.append(
                    {
                        "hand_id": hand_id,
                        "seat": seat,
                        "dealer_seat": 0,
                        "deal_id": hand_id,
                        "hand_cards": ["SA", "HA"],
                        "hand_features": {
                            "bowers": seat % 2,
                            "trump_count": 3 + seat,
                            "offsuit_aces": 1,
                            "offsuit_tens_count": 2,
                        },
                        "hand_feature_schema_version": 1,
                        "contract_type": ct,
                        "trump_suit": ts,
                    }
                )
    df = pd.DataFrame(rows)
    df.to_parquet(path)


def _make_outcomes_parquet(path, hand_ids, contract_types, trump_suits):
    """Create a minimal bidless_outcomes.parquet for testing."""
    rows = []
    for hand_id in hand_ids:
        for ct, ts in zip(contract_types, trump_suits):
            rows.append(
                {
                    "hand_id": hand_id,
                    "deal_id": hand_id,
                    "dealer_seat": 0,
                    "contract_type": ct,
                    "trump_suit": ts,
                    "strategy_id": "test",
                    "matchup_id": "test",
                    "team0_strategy": "greedy",
                    "team1_strategy": "greedy",
                    "tricks_team0": 6,
                    "tricks_team1": 4,
                    "team0_win": True,
                }
            )
    df = pd.DataFrame(rows)
    df.to_parquet(path)


class TestJoinFeaturesOutcomes:
    """Test the join utility."""

    def test_basic_join(self, tmp_path):
        """Test basic join produces correct shape and columns."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        hand_ids = [1, 2, 3]
        cts = ["suit"]
        tss = ["H"]

        _make_bidless_parquet(bidless_path, hand_ids, cts, tss)
        _make_outcomes_parquet(outcomes_path, hand_ids, cts, tss)

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        # 3 hands × 4 seats × 1 contract = 12 rows
        assert len(result) == 12
        assert "tricks_won" in result.columns
        assert "hand_id" in result.columns
        assert "seat" in result.columns
        # Struct features should be flattened
        assert "bowers" in result.columns
        assert "trump_count" in result.columns

    def test_team_assignment(self, tmp_path):
        """Test that tricks_won is correctly assigned by team."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        _make_bidless_parquet(bidless_path, [1], ["suit"], ["H"])
        _make_outcomes_parquet(outcomes_path, [1], ["suit"], ["H"])

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        # Seats 0, 2 → team 0 → tricks_team0 = 6
        team0_rows = result[result["seat"].isin([0, 2])]
        assert (team0_rows["tricks_won"] == 6).all()

        # Seats 1, 3 → team 1 → tricks_team1 = 4
        team1_rows = result[result["seat"].isin([1, 3])]
        assert (team1_rows["tricks_won"] == 4).all()

    def test_struct_flattening(self, tmp_path):
        """Test that hand_features struct is properly flattened."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        _make_bidless_parquet(bidless_path, [1], ["suit"], ["H"])
        _make_outcomes_parquet(outcomes_path, [1], ["suit"], ["H"])

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        # hand_features struct should be gone
        assert "hand_features" not in result.columns
        # Individual features should be present
        assert "bowers" in result.columns
        assert "offsuit_aces" in result.columns
        assert "offsuit_tens_count" in result.columns

    def test_no_intermediate_columns(self, tmp_path):
        """Test that tricks_team0/tricks_team1 are dropped."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        _make_bidless_parquet(bidless_path, [1], ["suit"], ["H"])
        _make_outcomes_parquet(outcomes_path, [1], ["suit"], ["H"])

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        assert "tricks_team0" not in result.columns
        assert "tricks_team1" not in result.columns

    def test_multiple_contracts(self, tmp_path):
        """Test join with multiple contract types."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        hand_ids = [1, 2]
        cts = ["suit", "high"]
        tss = ["H", None]

        _make_bidless_parquet(bidless_path, hand_ids, cts, tss)
        _make_outcomes_parquet(outcomes_path, hand_ids, cts, tss)

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        # 2 hands × 4 seats × 2 contracts = 16 rows
        assert len(result) == 16

    def test_hand_id_grouping_preserved(self, tmp_path):
        """Test that all 4 seats per hand are present after join."""
        bidless_path = tmp_path / "bidless.parquet"
        outcomes_path = tmp_path / "outcomes.parquet"

        _make_bidless_parquet(bidless_path, [10, 20, 30], ["suit"], ["S"])
        _make_outcomes_parquet(outcomes_path, [10, 20, 30], ["suit"], ["S"])

        result = join_features_outcomes(str(bidless_path), str(outcomes_path))

        # Each hand_id should have exactly 4 rows (one per seat)
        for hid in [10, 20, 30]:
            hand_rows = result[result["hand_id"] == hid]
            assert len(hand_rows) == 4
            assert set(hand_rows["seat"]) == {0, 1, 2, 3}

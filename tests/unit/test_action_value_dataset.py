"""Unit tests for the R1.5 counterfactual action-value dataset generator."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add scripts to path so we can import the generator
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from generate_action_value_dataset import (
    _bidding_order,
    _deterministic_dealer,
    _load_completed_chunks,
    _play_tricks,
    _play_tricks_loner,
    generate_dataset,
    run_partial_auction,
    sample_opponent_hands,
    simulate_counterfactual,
    simulate_loner_counterfactual,
    simulate_moon_counterfactual,
    validate_gate_x1,
)

from bid_euchre.sim.deals import generate_deal
from bid_euchre.strategy.bidding import (
    STATE_FEATURE_NAMES,
    AlwaysPassBidder,
    BidAction,
    StrictHellRaiser,
)

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def seed():
    return 42


@pytest.fixture
def hands(seed):
    return generate_deal(seed, 0)


@pytest.fixture
def dealer(seed):
    return _deterministic_dealer(seed, 0)


@pytest.fixture
def raiser():
    """A continuation policy that bids aggressively (ensures non-misdeal)."""
    return StrictHellRaiser(name="test_raiser")


@pytest.fixture
def passer():
    """A continuation policy that always passes."""
    return AlwaysPassBidder(name="test_passer")


# ── Helpers ───────────────────────────────────────────────────


class TestBiddingOrder:
    def test_dealer_last(self):
        assert _bidding_order(0) == [1, 2, 3, 0]
        assert _bidding_order(2) == [3, 0, 1, 2]

    def test_four_seats(self):
        for dealer in range(4):
            order = _bidding_order(dealer)
            assert len(order) == 4
            assert set(order) == {0, 1, 2, 3}


class TestDeterministicDealer:
    def test_reproducible(self, seed):
        d1 = _deterministic_dealer(seed, 0)
        d2 = _deterministic_dealer(seed, 0)
        assert d1 == d2

    def test_range(self, seed):
        for deal_id in range(100):
            d = _deterministic_dealer(seed, deal_id)
            assert 0 <= d <= 3

    def test_matches_engine_formula(self, seed):
        """Verify dealer derivation matches play_single_hand's auction-mode formula.

        The engine uses: random.Random(deal_seed + deal_id).randrange(4)
        NOT the _deal_rng formula (seed * 1_000_003 + deal_id).
        """
        import random

        for deal_id in range(20):
            expected = random.Random(seed + deal_id).randrange(4)
            actual = _deterministic_dealer(seed, deal_id)
            assert actual == expected, (
                f"Dealer mismatch at deal_id={deal_id}: "
                f"engine={expected}, generator={actual}"
            )


# ── Partial Auction ───────────────────────────────────────────


class TestRunPartialAuction:
    def test_first_seat_empty_transcript(self, hands, dealer, raiser):
        """First seat to bid should have empty transcript and high_bid=0."""
        first_seat = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, first_seat, raiser)
        assert high_bid == 0
        assert len(transcript) == 0

    def test_later_seat_sees_prior_bids(self, hands, dealer, raiser):
        """A later seat should see prior bids in transcript."""
        order = _bidding_order(dealer)
        # Third seat should see 2 prior actions
        third_seat = order[2]
        high_bid, transcript = run_partial_auction(hands, dealer, third_seat, raiser)
        assert len(transcript) == 2
        # StrictHellRaiser always bids, so high_bid > 0
        assert high_bid > 0

    def test_all_pass_continuation(self, hands, dealer, passer):
        """With AlwaysPassBidder, all prior seats pass."""
        order = _bidding_order(dealer)
        last_seat = order[3]
        high_bid, transcript = run_partial_auction(hands, dealer, last_seat, passer)
        assert high_bid == 0
        assert len(transcript) == 3
        assert all(e["action"] == "PASS" for e in transcript)


# ── Counterfactual Simulation ─────────────────────────────────


class TestSimulateCounterfactual:
    def test_returns_tuple(self, hands, dealer, raiser):
        """simulate_counterfactual returns a 3-tuple (net_points, tricks_won, focal_declared)."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        result = simulate_counterfactual(
            hands,
            dealer,
            focal,
            BidAction.pass_bid(),
            high_bid,
            transcript,
            raiser,
        )
        assert isinstance(result, tuple)
        assert len(result) == 3
        net_points, tricks_won, focal_declared = result
        assert isinstance(net_points, float)
        assert isinstance(tricks_won, float)
        assert isinstance(focal_declared, bool)

    def test_pass_returns_float(self, hands, dealer, raiser):
        """Pass action produces a float net_points."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            BidAction.pass_bid(),
            high_bid,
            transcript,
            raiser,
        )
        assert isinstance(net_points, float)

    def test_bid_returns_float(self, hands, dealer, raiser):
        """Bid action produces a float net_points."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        action = BidAction.bid(3, "S")
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            raiser,
        )
        assert isinstance(net_points, float)

    def test_misdeal_returns_zero(self, hands, dealer, passer):
        """When all pass (including forced pass), net_points=0, tricks_won=0, focal_declared=False."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, passer)
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            BidAction.pass_bid(),
            high_bid,
            transcript,
            passer,
        )
        assert net_points == 0.0
        assert tricks_won == 0.0
        assert focal_declared is False

    def test_tricks_won_range(self, hands, dealer, raiser):
        """tricks_won should be in [0, 10]."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        action = BidAction.bid(3, "S")
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            raiser,
        )
        assert 0 <= tricks_won <= 10

    def test_net_points_range(self, hands, dealer, raiser):
        """net_points should be in a plausible range."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
        action = BidAction.bid(3, "S")
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            raiser,
        )
        assert -20 <= net_points <= 20

    def test_focal_declared_true_when_focal_bids_highest(self, hands, dealer, passer):
        """When focal is the only bidder (others pass), focal_declared=True."""
        focal = _bidding_order(dealer)[0]
        high_bid, transcript = run_partial_auction(hands, dealer, focal, passer)
        # Focal bids, all others pass → focal's team declares
        action = BidAction.bid(4, "S")
        net_points, tricks_won, focal_declared = simulate_counterfactual(
            hands,
            dealer,
            focal,
            action,
            high_bid,
            transcript,
            passer,
        )
        assert focal_declared is True

    def test_focal_declared_false_when_opponent_outbids(self, raiser):
        """When opponent outbids focal, focal_declared=False."""
        # Use raiser as continuation — later seats will outbid a low bid
        # Test across multiple deals to find at least one where opponent outbids
        found_opponent_declared = False
        for deal_id in range(20):
            hands = generate_deal(42, deal_id)
            dealer = _deterministic_dealer(42, deal_id)
            focal = _bidding_order(dealer)[0]
            high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)
            # Focal passes, raiser continuation will bid
            net_points, tricks_won, focal_declared = simulate_counterfactual(
                hands,
                dealer,
                focal,
                BidAction.pass_bid(),
                high_bid,
                transcript,
                raiser,
            )
            if not focal_declared and net_points != 0.0:
                found_opponent_declared = True
                break
        assert (
            found_opponent_declared
        ), "Expected at least one deal where opponent declares"

    def test_different_actions_different_outcomes(self, raiser):
        """Across multiple deals, pass vs bid produce different net_points."""
        # Use multiple deals to avoid single-deal flukes where continuation
        # policy overwhelms the forced action
        results_pass = []
        results_bid = []
        for deal_id in range(10):
            hands = generate_deal(42, deal_id)
            dealer = _deterministic_dealer(42, deal_id)
            focal = _bidding_order(dealer)[0]
            high_bid, transcript = run_partial_auction(hands, dealer, focal, raiser)

            r_pass, _, _ = simulate_counterfactual(
                hands,
                dealer,
                focal,
                BidAction.pass_bid(),
                high_bid,
                transcript,
                raiser,
            )
            r_bid, _, _ = simulate_counterfactual(
                hands,
                dealer,
                focal,
                BidAction.bid(5, "S"),
                high_bid,
                transcript,
                raiser,
            )
            results_pass.append(r_pass)
            results_bid.append(r_bid)

        # Across 10 deals, pass and bid=5S should differ on at least one
        assert (
            results_pass != results_bid
        ), "Pass and bid always identical across 10 deals"


# ── Play Tricks ───────────────────────────────────────────────


class TestPlayTricks:
    def test_tricks_sum_to_ten(self, hands):
        t0, t1 = _play_tricks(
            hands, initial_leader=0, contract_type="suit", trump_suit="S"
        )
        assert t0 + t1 == 10

    def test_all_contract_types(self, hands):
        for ctype, trump in [
            ("suit", "C"),
            ("suit", "D"),
            ("high", None),
            ("low", None),
        ]:
            t0, t1 = _play_tricks(
                hands, initial_leader=0, contract_type=ctype, trump_suit=trump
            )
            assert t0 + t1 == 10
            assert 0 <= t0 <= 10


# ── Full Dataset Generation ──────────────────────────────────


class TestGenerateDataset:
    @pytest.fixture
    def small_df(self, raiser):
        """Generate a tiny dataset for testing (5 deals)."""
        return generate_dataset(
            seed=42, n_deals=5, continuation_policy=raiser, progress=False
        )

    def test_has_required_columns(self, small_df):
        required = {
            "hand_id",
            "deal_id",
            "focal_seat",
            "action_type",
            "contract_family",
            "bid_n",
            "trump_suit",
            "net_points",
            "tricks_won",
            "focal_declared",
        }
        assert required.issubset(set(small_df.columns))

    def test_has_state_features(self, small_df):
        for fname in STATE_FEATURE_NAMES:
            assert fname in small_df.columns, f"Missing: {fname}"

    def test_pass_coverage(self, small_df):
        """Exactly 1 pass per (deal_id, focal_seat)."""
        pass_df = small_df[small_df["action_type"] == "pass"]
        counts = pass_df.groupby(["deal_id", "focal_seat"]).size()
        assert (counts == 1).all()
        assert len(counts) == 5 * 4  # 5 deals × 4 seats

    def test_tricks_won_range(self, small_df):
        """tricks_won should be in [0, 10] for all rows."""
        assert small_df["tricks_won"].between(0, 10).all()

    def test_focal_declared_is_boolean(self, small_df):
        """focal_declared should contain only boolean-like values."""
        vals = set(small_df["focal_declared"].unique())
        assert vals.issubset({True, False, 0, 1})

    def test_focal_declared_has_both_values(self, small_df):
        """With 5 deals, we expect both True and False focal_declared values."""
        vals = set(small_df["focal_declared"].unique())
        assert True in vals or 1 in vals, "Expected at least one focal_declared=True"
        assert False in vals or 0 in vals, "Expected at least one focal_declared=False"

    def test_no_nan(self, small_df):
        feature_cols = STATE_FEATURE_NAMES + ["net_points", "tricks_won"]
        assert small_df[feature_cols].isna().sum().sum() == 0

    def test_action_types(self, small_df):
        assert set(small_df["action_type"].unique()) == {"pass", "bid"}

    def test_contract_families(self, small_df):
        families = set(small_df["contract_family"].unique())
        # Must have at least pass (none) and some bid families
        assert "none" in families
        assert len(families) >= 2

    def test_row_count_plausible(self, small_df):
        """5 deals × 4 seats × ~40 avg actions ≈ 800 rows."""
        assert 200 <= len(small_df) <= 2000


# ── Determinism ───────────────────────────────────────────────


class TestDeterminism:
    def test_same_seed_same_output(self, raiser):
        df1 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        df2 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seed_different_output(self, raiser):
        df1 = generate_dataset(
            seed=99, n_deals=3, continuation_policy=raiser, progress=False
        )
        df2 = generate_dataset(
            seed=100, n_deals=3, continuation_policy=raiser, progress=False
        )
        # Different seeds should produce different net_points
        assert not np.allclose(df1["net_points"].values, df2["net_points"].values)


# ── Gate X1 ───────────────────────────────────────────────────


class TestGateX1:
    def test_passes_on_valid_data(self, raiser):
        df = generate_dataset(
            seed=42, n_deals=10, continuation_policy=raiser, progress=False
        )
        # Should not raise
        validate_gate_x1(df, n_deals=10)

    def test_fails_on_missing_pass(self, raiser):
        df = generate_dataset(
            seed=42, n_deals=5, continuation_policy=raiser, progress=False
        )
        # Remove all pass rows
        df_no_pass = df[df["action_type"] != "pass"].copy()
        with pytest.raises(AssertionError, match="pass"):
            validate_gate_x1(df_no_pass, n_deals=5)


# ── Opponent Hand Resampling ─────────────────────────────────


class TestSampleOpponentHands:
    def test_focal_and_partner_preserved(self, hands):
        """Focal and partner hands must be identical across all samples."""
        import random as rng_mod

        for focal_seat in range(4):
            partner_seat = (focal_seat + 2) % 4
            configs = sample_opponent_hands(
                focal_seat, hands, n_samples=5, rng=rng_mod.Random(42)
            )
            for config in configs:
                assert config[focal_seat] == hands[focal_seat]
                assert config[partner_seat] == hands[partner_seat]

    def test_opponent_hands_vary(self, hands):
        """Opponent hands should differ across samples (with high probability)."""
        import random as rng_mod

        configs = sample_opponent_hands(
            focal_seat=0, hands=hands, n_samples=10, rng=rng_mod.Random(42)
        )
        opp_seat = 1
        # Collect all opponent hand configurations as sorted tuples for comparison
        opp_hands = [tuple(sorted(str(c) for c in cfg[opp_seat])) for cfg in configs]
        # At least 2 distinct configurations out of 10
        assert len(set(opp_hands)) >= 2, "Opponent hands did not vary across samples"

    def test_card_count_preserved(self, hands):
        """Each config should have 4 hands of 10 cards = 40 total."""
        import random as rng_mod

        configs = sample_opponent_hands(
            focal_seat=0, hands=hands, n_samples=5, rng=rng_mod.Random(42)
        )
        for config in configs:
            assert len(config) == 4
            for h in config:
                assert len(h) == 10

    def test_determinism(self, hands):
        """Same seed produces same samples."""
        import random as rng_mod

        configs1 = sample_opponent_hands(
            focal_seat=0, hands=hands, n_samples=3, rng=rng_mod.Random(99)
        )
        configs2 = sample_opponent_hands(
            focal_seat=0, hands=hands, n_samples=3, rng=rng_mod.Random(99)
        )
        for c1, c2 in zip(configs1, configs2):
            for seat in range(4):
                assert c1[seat] == c2[seat]

    def test_all_cards_from_original_pool(self, hands):
        """Resampled opponent cards must come from the original opponent pool."""
        import random as rng_mod

        focal_seat = 0
        opp_seats = [1, 3]
        original_pool = sorted(
            str(c) for c in hands[opp_seats[0]] + hands[opp_seats[1]]
        )

        configs = sample_opponent_hands(
            focal_seat, hands, n_samples=5, rng=rng_mod.Random(42)
        )
        for config in configs:
            resampled_pool = sorted(
                str(c) for c in config[opp_seats[0]] + config[opp_seats[1]]
            )
            assert resampled_pool == original_pool


# ── Multi-Rollout Dataset Generation ─────────────────────────


class TestMultiRolloutDataset:
    @pytest.fixture
    def single_df(self, raiser):
        """N=1 dataset (existing behavior)."""
        return generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=1,
        )

    @pytest.fixture
    def multi_df(self, raiser):
        """N=5 dataset (multi-rollout)."""
        return generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=5,
        )

    def test_n1_matches_original(self, raiser):
        """N=1 with explicit parameter matches default behavior exactly."""
        df_default = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
        )
        df_n1 = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=1,
        )
        pd.testing.assert_frame_equal(df_default, df_n1)

    def test_multi_has_metadata_columns(self, multi_df):
        """Multi-sample dataset includes std_net_points and n_samples."""
        assert "std_net_points" in multi_df.columns
        assert "n_samples" in multi_df.columns
        assert (multi_df["n_samples"] == 5).all()

    def test_single_lacks_metadata_columns(self, single_df):
        """Single-sample dataset does NOT include metadata columns."""
        assert "std_net_points" not in single_df.columns
        assert "n_samples" not in single_df.columns

    def test_same_row_count(self, single_df, multi_df):
        """Single and multi datasets should have the same number of rows."""
        assert len(single_df) == len(multi_df)

    def test_same_features(self, single_df, multi_df):
        """Features should be identical (extracted from original hands)."""
        for fname in STATE_FEATURE_NAMES:
            np.testing.assert_array_equal(
                single_df[fname].values,
                multi_df[fname].values,
                err_msg=f"Feature {fname} differs between N=1 and N=5",
            )

    def test_suit_labels_differ(self, single_df, multi_df):
        """Multi-sample suit labels should differ from single-sample."""
        suit_mask = single_df["contract_family"] == "suit"
        if suit_mask.sum() == 0:
            pytest.skip("No suit actions in test dataset")

        single_suit = single_df.loc[suit_mask, "net_points"].values
        multi_suit = multi_df.loc[suit_mask, "net_points"].values
        # With 3 deals and 5 samples, at least some suit labels should differ
        assert not np.allclose(
            single_suit, multi_suit
        ), "Multi-sample suit labels are identical to single-sample"

    def test_std_net_points_positive_for_some_suits(self, multi_df):
        """At least some suit actions should have std_net_points > 0."""
        suit_mask = multi_df["contract_family"] == "suit"
        if suit_mask.sum() == 0:
            pytest.skip("No suit actions in test dataset")
        suit_stds = multi_df.loc[suit_mask, "std_net_points"]
        assert (suit_stds > 0).any(), "No suit actions have label variance"

    def test_multi_determinism(self, raiser):
        """Same seed + n_opponent_samples produces identical results."""
        df1 = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=5,
        )
        df2 = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=5,
        )
        pd.testing.assert_frame_equal(df1, df2)

    def test_gate_x1_passes_multi(self, raiser):
        """Gate X1 should pass on multi-sample dataset."""
        df = generate_dataset(
            seed=42,
            n_deals=10,
            continuation_policy=raiser,
            progress=False,
            n_opponent_samples=5,
        )
        validate_gate_x1(df, n_deals=10)


# ── Moon / Loner Counterfactuals ─────────────────────────


class TestPlayTricksLoner:
    def test_tricks_sum_to_ten(self, hands):
        """3-player trick play should still produce 10 tricks total."""
        t0, t1 = _play_tricks_loner(
            hands,
            initial_leader=0,
            sitting_out_seat=2,
            contract_type="suit",
            trump_suit="S",
        )
        assert t0 + t1 == 10

    def test_all_contract_types(self, hands):
        for ctype, trump in [
            ("suit", "C"),
            ("suit", "D"),
            ("high", None),
            ("low", None),
        ]:
            t0, t1 = _play_tricks_loner(
                hands,
                initial_leader=0,
                sitting_out_seat=2,
                contract_type=ctype,
                trump_suit=trump,
            )
            assert t0 + t1 == 10
            assert 0 <= t0 <= 10

    def test_sitting_out_seat_skipped(self, hands):
        """The sitting-out seat should not play cards."""
        # Before: partner at seat 2 has 10 cards
        hands_copy = [list(h) for h in hands]
        original_partner_len = len(hands_copy[2])
        assert original_partner_len == 10

        # After loner play, the hands are mutated by _play_tricks_loner
        # but we pass copies so original is unchanged
        _play_tricks_loner(
            hands_copy,
            initial_leader=0,
            sitting_out_seat=2,
            contract_type="suit",
            trump_suit="S",
        )
        # Seat 2 should still have 10 cards (not played)
        assert len(hands_copy[2]) == 10


class TestSimulateMoonCounterfactual:
    def test_returns_tuple(self, hands):
        net_points, tricks_won = simulate_moon_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="S"
        )
        assert isinstance(net_points, float)
        assert isinstance(tricks_won, float)

    def test_moon_scoring_range(self, hands):
        """Moon net_points should be in [-30, 30] (max: +20 - 0 or -20 - 10)."""
        net_points, tricks_won = simulate_moon_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="S"
        )
        assert -30 <= net_points <= 30
        assert 0 <= tricks_won <= 10

    def test_moon_high_contract(self, hands):
        """Moon with high contract should work."""
        net_points, tricks_won = simulate_moon_counterfactual(
            hands, focal_seat=1, contract_type="high", trump_suit=None
        )
        assert isinstance(net_points, float)

    def test_moon_exchange_changes_hands(self, hands):
        """Moon simulation should use exchanged hands (different from regular)."""
        # Run moon for multiple deals and check at least some differ from
        # regular 4-player trick play
        moon_results = []
        regular_results = []
        for deal_id in range(10):
            deal_hands = generate_deal(42, deal_id)
            mn, _ = simulate_moon_counterfactual(
                deal_hands,
                focal_seat=0,
                contract_type="suit",
                trump_suit="S",
            )
            moon_results.append(mn)
            # Regular 4-player (no exchange) for comparison
            t0, t1 = _play_tricks(
                deal_hands,
                initial_leader=0,
                contract_type="suit",
                trump_suit="S",
            )
            regular_results.append(t0)
        # At least some should differ (exchange changes hands)
        assert (
            moon_results != regular_results
        ), "Moon results identical to regular — exchange may not be working"

    def test_moon_uses_3_player_trick_play(self, hands):
        """Moon counterfactual must route through _play_tricks_loner (3-player).

        Regression test for PR #2114 — previously called _play_tricks (4-player).
        """
        from unittest.mock import patch

        with patch(
            "generate_action_value_dataset._play_tricks_loner",
            wraps=_play_tricks_loner,
        ) as spy:
            simulate_moon_counterfactual(
                hands, focal_seat=0, contract_type="suit", trump_suit="S"
            )
            spy.assert_called_once()

    def test_moon_partner_sits_out(self, hands):
        """Moon: the focal player's partner must be the sitting-out seat.

        For focal_seat=0, partner is seat 2.
        For focal_seat=1, partner is seat 3.
        """
        from unittest.mock import patch

        for focal_seat, expected_partner in [(0, 2), (1, 3), (2, 0), (3, 1)]:
            with patch(
                "generate_action_value_dataset._play_tricks_loner",
                wraps=_play_tricks_loner,
            ) as spy:
                simulate_moon_counterfactual(
                    hands,
                    focal_seat=focal_seat,
                    contract_type="suit",
                    trump_suit="S",
                )
                call_kwargs = spy.call_args
                # sitting_out_seat is passed as a positional or keyword arg
                # _play_tricks_loner(hands, focal_seat, partner_seat, ...)
                # In simulate_moon_counterfactual, call is:
                #   _play_tricks_loner(exchanged_hands, focal_seat, partner_seat, ...)
                actual_sitting_out = call_kwargs[0][2]  # 3rd positional arg
                assert actual_sitting_out == expected_partner, (
                    f"focal_seat={focal_seat}: expected partner {expected_partner} "
                    f"to sit out, got {actual_sitting_out}"
                )

    def test_moon_3_player_tricks_exclude_partner(self):
        """Each trick in moon play has exactly 3 players; partner never plays.

        Instruments trick_winner to observe plays per trick, verifying:
        - Every trick has exactly 3 plays (not 4)
        - The sitting-out partner seat never appears in any trick
        """
        from unittest.mock import patch

        from bid_euchre.core.rules import trick_winner as real_trick_winner

        for focal_seat in range(4):
            partner_seat = (focal_seat + 2) % 4
            deal_hands = generate_deal(42, 0)
            recorded_tricks = []

            def recording_trick_winner(plays, **kwargs):
                recorded_tricks.append(list(plays))
                return real_trick_winner(plays, **kwargs)

            with patch(
                "bid_euchre.core.rules.trick_winner",
                side_effect=recording_trick_winner,
            ):
                t0, t1 = _play_tricks_loner(
                    deal_hands,
                    initial_leader=focal_seat,
                    sitting_out_seat=partner_seat,
                    contract_type="suit",
                    trump_suit="S",
                )

            assert t0 + t1 == 10
            assert (
                len(recorded_tricks) == 10
            ), f"Expected 10 tricks, got {len(recorded_tricks)}"

            for trick_idx, plays in enumerate(recorded_tricks):
                # Each trick must have exactly 3 plays
                assert len(plays) == 3, (
                    f"focal={focal_seat}, trick {trick_idx}: "
                    f"expected 3 plays, got {len(plays)}"
                )
                # Partner seat must not appear
                seats_in_trick = {seat for seat, _card in plays}
                assert partner_seat not in seats_in_trick, (
                    f"focal={focal_seat}, trick {trick_idx}: "
                    f"partner seat {partner_seat} played but should sit out"
                )

    def test_moon_counterfactual_3_player_all_contract_types(self):
        """Moon counterfactual uses 3-player play for all contract types."""
        from unittest.mock import patch

        from bid_euchre.core.rules import trick_winner as real_trick_winner

        for ctype, trump in [
            ("suit", "S"),
            ("suit", "H"),
            ("high", None),
            ("low", None),
        ]:
            deal_hands = generate_deal(42, 0)
            recorded_tricks = []

            def recording_trick_winner(plays, **kwargs):
                recorded_tricks.append(list(plays))
                return real_trick_winner(plays, **kwargs)

            with patch(
                "bid_euchre.core.rules.trick_winner",
                side_effect=recording_trick_winner,
            ):
                simulate_moon_counterfactual(
                    deal_hands,
                    focal_seat=0,
                    contract_type=ctype,
                    trump_suit=trump,
                )

            # All 10 tricks should have exactly 3 plays
            assert len(recorded_tricks) == 10
            for trick_idx, plays in enumerate(recorded_tricks):
                assert len(plays) == 3, (
                    f"contract={ctype}/{trump}, trick {trick_idx}: "
                    f"expected 3 plays, got {len(plays)}"
                )


class TestSimulateLoner:
    def test_returns_tuple(self, hands):
        net_points, tricks_won = simulate_loner_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="S"
        )
        assert isinstance(net_points, float)
        assert isinstance(tricks_won, float)

    def test_loner_scoring_range(self, hands):
        """Loner net_points should be in [-50, 50] (max: +40 - 0 or -40 - 10)."""
        net_points, tricks_won = simulate_loner_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="S"
        )
        assert -50 <= net_points <= 50
        assert 0 <= tricks_won <= 10

    def test_loner_high_contract(self, hands):
        """Loner with high contract should work."""
        net_points, tricks_won = simulate_loner_counterfactual(
            hands, focal_seat=1, contract_type="high", trump_suit=None
        )
        assert isinstance(net_points, float)

    def test_loner_uses_3_player(self, hands):
        """Loner should produce different results from 4-player play."""
        loner_results = []
        regular_results = []
        for deal_id in range(10):
            deal_hands = generate_deal(42, deal_id)
            ln, _ = simulate_loner_counterfactual(
                deal_hands,
                focal_seat=0,
                contract_type="suit",
                trump_suit="S",
            )
            loner_results.append(ln)
            t0, t1 = _play_tricks(
                deal_hands,
                initial_leader=0,
                contract_type="suit",
                trump_suit="S",
            )
            regular_results.append(t0)
        assert (
            loner_results != regular_results
        ), "Loner results identical to regular — 3-player may not be working"


# ── Moon/Loner Dataset Generation ───────────────────────


class TestMoonLonerDataset:
    @pytest.fixture
    def ml_df(self, raiser):
        """Generate a tiny dataset with moon/loner counterfactuals."""
        return generate_dataset(
            seed=42,
            n_deals=5,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=True,
        )

    @pytest.fixture
    def regular_df(self, raiser):
        """Generate a tiny dataset WITHOUT moon/loner for comparison."""
        return generate_dataset(
            seed=42,
            n_deals=5,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=False,
        )

    def test_has_is_moon_is_loner_columns(self, ml_df):
        assert "is_moon" in ml_df.columns
        assert "is_loner" in ml_df.columns

    def test_regular_also_has_columns(self, regular_df):
        """Even without moon/loner, is_moon and is_loner columns exist."""
        assert "is_moon" in regular_df.columns
        assert "is_loner" in regular_df.columns
        assert (regular_df["is_moon"] == 0).all()
        assert (regular_df["is_loner"] == 0).all()

    def test_moon_rows_present(self, ml_df):
        moon_rows = ml_df[ml_df["is_moon"] == 1]
        assert len(moon_rows) > 0

    def test_loner_rows_present(self, ml_df):
        loner_rows = ml_df[ml_df["is_loner"] == 1]
        assert len(loner_rows) > 0

    def test_moon_loner_count_per_hand(self, ml_df):
        """Each (deal, seat) should have exactly 6 moon + 6 loner rows."""
        moon_df = ml_df[ml_df["is_moon"] == 1]
        loner_df = ml_df[ml_df["is_loner"] == 1]
        moon_counts = moon_df.groupby(["deal_id", "focal_seat"]).size()
        loner_counts = loner_df.groupby(["deal_id", "focal_seat"]).size()
        assert (moon_counts == 6).all()
        assert (loner_counts == 6).all()

    def test_moon_bid_n_is_10(self, ml_df):
        moon_df = ml_df[ml_df["is_moon"] == 1]
        assert (moon_df["bid_n"] == 10).all()

    def test_loner_bid_n_is_10(self, ml_df):
        loner_df = ml_df[ml_df["is_loner"] == 1]
        assert (loner_df["bid_n"] == 10).all()

    def test_moon_loner_focal_declared(self, ml_df):
        """Moon/loner rows should have focal_declared=True."""
        special = ml_df[(ml_df["is_moon"] == 1) | (ml_df["is_loner"] == 1)]
        assert special["focal_declared"].all()

    def test_regular_rows_unchanged(self, ml_df, regular_df):
        """Regular action rows should be identical with/without moon/loner."""
        regular_from_ml = ml_df[
            (ml_df["is_moon"] == 0) & (ml_df["is_loner"] == 0)
        ].reset_index(drop=True)
        regular_only = regular_df.reset_index(drop=True)
        # Same number of regular rows
        assert len(regular_from_ml) == len(regular_only)
        # Same state features
        for fname in STATE_FEATURE_NAMES:
            np.testing.assert_array_equal(
                regular_from_ml[fname].values,
                regular_only[fname].values,
                err_msg=f"Feature {fname} differs",
            )

    def test_more_rows_with_moon_loner(self, ml_df, regular_df):
        """Moon/loner dataset should have more rows (12 extra per hand)."""
        extra = 5 * 4 * 12  # 5 deals × 4 seats × 12 (6 moon + 6 loner)
        assert len(ml_df) == len(regular_df) + extra

    def test_no_nan_in_moon_loner(self, ml_df):
        special = ml_df[(ml_df["is_moon"] == 1) | (ml_df["is_loner"] == 1)]
        feature_cols = STATE_FEATURE_NAMES + ["net_points", "tricks_won"]
        assert special[feature_cols].isna().sum().sum() == 0

    def test_gate_x1_passes_with_moon_loner(self, raiser):
        df = generate_dataset(
            seed=42,
            n_deals=10,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=True,
        )
        validate_gate_x1(df, n_deals=10, include_moon_loner=True)

    def test_backward_compat_without_flag(self, raiser):
        """Default (include_moon_loner=False) matches existing behavior."""
        df_default = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
        )
        df_explicit = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=False,
        )
        pd.testing.assert_frame_equal(df_default, df_explicit)

    def test_determinism_with_moon_loner(self, raiser):
        """Same seed + include_moon_loner produces identical results."""
        df1 = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=True,
        )
        df2 = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=True,
        )
        pd.testing.assert_frame_equal(df1, df2)

    def test_all_contracts_in_moon_loner(self, ml_df):
        """Moon and loner should cover all 3 contract families."""
        moon_df = ml_df[ml_df["is_moon"] == 1]
        loner_df = ml_df[ml_df["is_loner"] == 1]
        moon_families = set(moon_df["contract_family"].unique())
        loner_families = set(loner_df["contract_family"].unique())
        assert {"suit", "high", "low"} == moon_families
        assert {"suit", "high", "low"} == loner_families


# ── Chunked Dataset Generation ───────────────────────────


class TestChunkedGeneration:
    """Tests for chunked parquet output mode."""

    @pytest.fixture
    def chunked_dir(self, tmp_path, raiser):
        """Generate a 20-deal dataset in 5-deal chunks."""
        output_dir = tmp_path / "action_value"
        generate_dataset(
            seed=42,
            n_deals=20,
            continuation_policy=raiser,
            progress=False,
            chunk_size=5,
            output_dir=output_dir,
        )
        return output_dir

    @pytest.fixture
    def single_df(self, raiser):
        """Generate the same dataset as a single DataFrame."""
        return generate_dataset(
            seed=42,
            n_deals=20,
            continuation_policy=raiser,
            progress=False,
        )

    def test_part_files_exist(self, chunked_dir):
        """Chunked output creates the expected part files."""
        parts = sorted(chunked_dir.glob("part_*.parquet"))
        assert len(parts) == 4
        expected_names = [
            "part_000000_000004.parquet",
            "part_000005_000009.parquet",
            "part_000010_000014.parquet",
            "part_000015_000019.parquet",
        ]
        actual_names = [p.name for p in parts]
        assert actual_names == expected_names

    def test_manifest_exists(self, chunked_dir):
        """Manifest file is written with correct entries."""
        manifest_path = chunked_dir / "manifest.jsonl"
        assert manifest_path.exists()
        entries = []
        with open(manifest_path) as f:
            for line in f:
                entries.append(json.loads(line.strip()))
        assert len(entries) == 4
        for entry in entries:
            assert entry["status"] == "complete"
            assert entry["seed"] == 42
            assert entry["n_deals"] == 5
            assert entry["rows"] > 0

    def test_manifest_deal_ranges(self, chunked_dir):
        """Manifest entries cover all deal ranges without gaps."""
        manifest_path = chunked_dir / "manifest.jsonl"
        entries = []
        with open(manifest_path) as f:
            for line in f:
                entries.append(json.loads(line.strip()))
        ranges = [(e["deal_start"], e["deal_end"]) for e in entries]
        assert ranges == [(0, 4), (5, 9), (10, 14), (15, 19)]

    def test_concatenated_equals_single(self, chunked_dir, single_df):
        """Concatenated chunks must equal single-file output."""
        parts = sorted(chunked_dir.glob("part_*.parquet"))
        chunked_df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        single_reset = single_df.reset_index(drop=True)
        # Compare column by column for better diagnostics
        assert set(chunked_df.columns) == set(single_reset.columns)
        assert len(chunked_df) == len(single_reset)
        pd.testing.assert_frame_equal(chunked_df[single_reset.columns], single_reset)

    def test_hand_id_globally_unique(self, chunked_dir):
        """hand_id must be globally unique across all chunks."""
        parts = sorted(chunked_dir.glob("part_*.parquet"))
        all_hand_ids = []
        for p in parts:
            df = pd.read_parquet(p, columns=["hand_id"])
            all_hand_ids.extend(df["hand_id"].unique().tolist())
        assert len(all_hand_ids) == len(set(all_hand_ids))

    def test_hand_id_deterministic(self, chunked_dir):
        """hand_id = deal_id * 4 + focal_seat."""
        parts = sorted(chunked_dir.glob("part_*.parquet"))
        for p in parts:
            df = pd.read_parquet(p, columns=["hand_id", "deal_id", "focal_seat"])
            expected = df["deal_id"] * 4 + df["focal_seat"]
            np.testing.assert_array_equal(df["hand_id"].values, expected.values)

    def test_gate_x1_passes_on_concatenated(self, chunked_dir):
        """Gate X1 validation passes on concatenated chunks."""
        parts = sorted(chunked_dir.glob("part_*.parquet"))
        df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        validate_gate_x1(df, n_deals=20)

    def test_returns_none_in_chunked_mode(self, tmp_path, raiser):
        """generate_dataset returns None when chunked."""
        output_dir = tmp_path / "av_none_test"
        result = generate_dataset(
            seed=42,
            n_deals=10,
            continuation_policy=raiser,
            progress=False,
            chunk_size=5,
            output_dir=output_dir,
        )
        assert result is None

    def test_unchunked_returns_dataframe(self, raiser):
        """generate_dataset returns DataFrame without chunk_size."""
        result = generate_dataset(
            seed=42,
            n_deals=5,
            continuation_policy=raiser,
            progress=False,
        )
        assert isinstance(result, pd.DataFrame)


class TestChunkedResumability:
    """Tests for chunk resumption from manifest."""

    def test_load_completed_chunks_empty(self, tmp_path):
        """No manifest means no completed chunks."""
        manifest = tmp_path / "manifest.jsonl"
        assert _load_completed_chunks(manifest) == set()

    def test_load_completed_chunks(self, tmp_path):
        """Completed chunks are read from manifest."""
        manifest = tmp_path / "manifest.jsonl"
        entries = [
            {"deal_start": 0, "deal_end": 4, "status": "complete"},
            {"deal_start": 5, "deal_end": 9, "status": "complete"},
        ]
        with open(manifest, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        completed = _load_completed_chunks(manifest)
        assert completed == {(0, 4), (5, 9)}

    def test_resume_skips_completed(self, tmp_path, raiser):
        """Resuming generation skips already-completed chunks."""
        output_dir = tmp_path / "av_resume"

        # First run: generate all 10 deals in 5-deal chunks
        generate_dataset(
            seed=42,
            n_deals=10,
            continuation_policy=raiser,
            progress=False,
            chunk_size=5,
            output_dir=output_dir,
        )

        # Read manifest — should have 2 entries
        manifest_path = output_dir / "manifest.jsonl"
        with open(manifest_path) as f:
            entries_before = f.readlines()
        assert len(entries_before) == 2

        # Run again — should skip both chunks (no new manifest entries)
        generate_dataset(
            seed=42,
            n_deals=10,
            continuation_policy=raiser,
            progress=False,
            chunk_size=5,
            output_dir=output_dir,
        )

        with open(manifest_path) as f:
            entries_after = f.readlines()
        # Still 2 entries (no new writes)
        assert len(entries_after) == 2


class TestChunkedNonDivisible:
    """Test chunked output when n_deals is not divisible by chunk_size."""

    def test_partial_final_chunk(self, tmp_path, raiser):
        """7 deals with chunk_size=5 produces 2 chunks (5 + 2)."""
        output_dir = tmp_path / "av_partial"
        generate_dataset(
            seed=42,
            n_deals=7,
            continuation_policy=raiser,
            progress=False,
            chunk_size=5,
            output_dir=output_dir,
        )
        parts = sorted(output_dir.glob("part_*.parquet"))
        assert len(parts) == 2
        # First chunk: deals 0-4, second chunk: deals 5-6
        assert parts[0].name == "part_000000_000004.parquet"
        assert parts[1].name == "part_000005_000006.parquet"

        # Verify all 7 deals are covered
        df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        assert set(df["deal_id"].unique()) == set(range(7))


# ── Global UIDs (v2 repair LA-5 §4.6) ────────────────────────


class TestGlobalUIDs:
    """Test dataset_seed, deal_uid, hand_uid columns."""

    @pytest.fixture
    def uid_df(self, raiser):
        """Generate a small dataset with default dataset_seed."""
        return generate_dataset(
            seed=42, n_deals=3, continuation_policy=raiser, progress=False
        )

    def test_has_uid_columns(self, uid_df):
        """Generated rows include dataset_seed, deal_uid, hand_uid."""
        assert "dataset_seed" in uid_df.columns
        assert "deal_uid" in uid_df.columns
        assert "hand_uid" in uid_df.columns

    def test_dataset_seed_defaults_to_seed(self, uid_df):
        """When dataset_seed is not specified, it defaults to the main seed."""
        assert (uid_df["dataset_seed"] == 42).all()

    def test_deal_uid_format(self, uid_df):
        """deal_uid = f'{dataset_seed}:{deal_id}'."""
        for _, row in uid_df.iterrows():
            expected = f"{int(row['dataset_seed'])}:{int(row['deal_id'])}"
            assert row["deal_uid"] == expected

    def test_hand_uid_format(self, uid_df):
        """hand_uid = f'{dataset_seed}:{hand_id}'."""
        for _, row in uid_df.iterrows():
            expected = f"{int(row['dataset_seed'])}:{int(row['hand_id'])}"
            assert row["hand_uid"] == expected

    def test_explicit_dataset_seed(self, raiser):
        """Explicit dataset_seed overrides the default."""
        df = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            dataset_seed=999,
        )
        assert (df["dataset_seed"] == 999).all()
        # deal_uid uses 999, not 42
        for _, row in df.iterrows():
            assert row["deal_uid"].startswith("999:")

    def test_moon_loner_rows_have_uids(self, raiser):
        """Moon and loner rows also get dataset_seed, deal_uid, hand_uid."""
        df = generate_dataset(
            seed=42,
            n_deals=3,
            continuation_policy=raiser,
            progress=False,
            include_moon_loner=True,
        )
        moon_df = df[df["is_moon"] == 1]
        loner_df = df[df["is_loner"] == 1]

        assert (moon_df["dataset_seed"] == 42).all()
        assert (loner_df["dataset_seed"] == 42).all()

        for _, row in moon_df.iterrows():
            expected_deal_uid = f"{int(row['dataset_seed'])}:{int(row['deal_id'])}"
            assert row["deal_uid"] == expected_deal_uid

        for _, row in loner_df.iterrows():
            expected_hand_uid = f"{int(row['dataset_seed'])}:{int(row['hand_id'])}"
            assert row["hand_uid"] == expected_hand_uid

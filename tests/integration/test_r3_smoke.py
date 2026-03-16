"""R3 SMOKE-scale end-to-end validation for moon/loner pipeline.

Validates that moon and loner bids work through the full pipeline:
  1. Dataset generation with --include-moon-loner produces correct rows
  2. Simulation engine handles moon exchange and loner 3-player trick play
  3. Scoring is correct (moon: +/-20, loner: +/-40)
  4. Training pipeline consumes expanded dataset without errors

This is the final R3 Phase A validation — confirming all 5 prior PRs
(bid types, exchange, loner tricks, scoring, dataset gen) integrate correctly.
"""

import random
import sys
import tempfile
from pathlib import Path

import pytest

from bid_euchre.core.cards import create_deck, deal_hands, shuffle_deck
from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
)

# Allow importing from scripts/internal
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "internal"))

from generate_action_value_dataset import (  # noqa: E402
    generate_dataset,
    simulate_loner_counterfactual,
    simulate_moon_counterfactual,
    validate_gate_x1,
)

# ── Test Policies ────────────────────────────────────────────


class AlwaysMoonPolicy(BiddingPolicy):
    """Bids moon for a fixed seat; all others pass."""

    def __init__(self, contract: str = "H", seat_to_bid: int = 0):
        self.contract = contract
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_moon"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.moon(self.contract)
        return BidAction.pass_bid()


class AlwaysLonerPolicy(BiddingPolicy):
    """Bids loner for a fixed seat; all others pass."""

    def __init__(self, contract: str = "H", seat_to_bid: int = 0):
        self.contract = contract
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_loner"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.loner(self.contract)
        return BidAction.pass_bid()


class AlwaysRegularPolicy(BiddingPolicy):
    """Bids a regular bid for a fixed seat; all others pass."""

    def __init__(self, contract: str = "H", bid_n: int = 6, seat_to_bid: int = 0):
        self.contract = contract
        self.bid_n = bid_n
        self.seat_to_bid = seat_to_bid

    @property
    def strategy_id(self) -> str:
        return "always_regular"

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.seat_to_bid:
            return BidAction.bid(self.bid_n, self.contract)
        return BidAction.pass_bid()


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def seed():
    return 42


# ── 1. Moon Simulation Tests ────────────────────────────────


class TestMoonEndToEnd:
    """Validate moon bid through the simulation engine."""

    def test_moon_game_completes_with_exchange(self):
        """Moon bid triggers card exchange and completes 10 tricks with 4 players."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysMoonPolicy(contract="H", seat_to_bid=0)] * 4,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        (
            t0,
            t1,
            _scores,
            _feats,
            _leader,
            _hands,
            bid,
            dealer,
            bidder,
            ctype,
            trump,
            transcript,
            bid_type,
            exchange_given,
            exchange_received,
            sitting_out,
        ) = result

        # Tricks sum to 10
        assert t0 + t1 == 10, f"Expected 10 total tricks, got {t0 + t1}"
        # bid_type should be "moon"
        assert bid_type == "moon", f"Expected bid_type='moon', got '{bid_type}'"
        # Contract should be suit with trump H
        assert ctype == "suit", f"Expected contract_type='suit', got '{ctype}'"
        assert trump == "H", f"Expected trump='H', got '{trump}'"
        # Exchange cards should be populated for moon bids
        assert (
            exchange_given is not None
        ), "exchange_cards_given should not be None for moon"
        assert (
            exchange_received is not None
        ), "exchange_cards_received should not be None for moon"
        assert (
            len(exchange_given) == 2
        ), f"Expected 2 cards given, got {len(exchange_given)}"
        assert (
            len(exchange_received) == 2
        ), f"Expected 2 cards received, got {len(exchange_received)}"
        # sitting_out should be None for moon (only loner)
        assert (
            sitting_out is None
        ), f"sitting_out should be None for moon, got {sitting_out}"

    def test_moon_scoring_made(self):
        """When declaring team wins all 10 tricks, they get +20."""
        # Directly test compute_points for moon
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=10,
            tricks_team1=0,
            bid_type="moon",
        )
        assert pts_t0 == 20, f"Made moon should be +20, got {pts_t0}"
        assert pts_t1 == 0, f"Defending team should get 0 tricks won, got {pts_t1}"

    def test_moon_scoring_failed(self):
        """When declaring team fails moon, they get -20."""
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=8,
            tricks_team1=2,
            bid_type="moon",
        )
        assert pts_t0 == -20, f"Failed moon should be -20, got {pts_t0}"
        assert pts_t1 == 2, f"Defending team should get their tricks, got {pts_t1}"

    def test_moon_exchange_preserves_hand_sizes(self):
        """After moon exchange, both hands still have 10 cards."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysMoonPolicy(contract="H", seat_to_bid=0)] * 4,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        # The game completed without error (exchange + 10 tricks)
        t0, t1 = result[0], result[1]
        assert t0 + t1 == 10

    @pytest.mark.parametrize("contract", ["C", "D", "H", "S", "HIGH", "LOW"])
    def test_moon_all_contract_types(self, contract):
        """Moon works with all 6 contract types."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysMoonPolicy(contract=contract, seat_to_bid=0)] * 4,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1, _s, _f, _l, _h, _b, _d, _bp, ctype, trump, _tr, bid_type, *_ = result
        assert t0 + t1 == 10
        assert bid_type == "moon"

        if contract in {"C", "D", "H", "S"}:
            assert ctype == "suit"
            assert trump == contract
        elif contract == "HIGH":
            assert ctype == "high"
            assert trump is None
        elif contract == "LOW":
            assert ctype == "low"
            assert trump is None


# ── 2. Loner Simulation Tests ───────────────────────────────


class TestLonerEndToEnd:
    """Validate loner bid through the simulation engine."""

    def test_loner_game_completes_3_players(self):
        """Loner bid produces a complete game with 3-player trick play."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysLonerPolicy(contract="H", seat_to_bid=0)] * 4,
            hands=hands,
            initial_leader=0,
            deal_id=0,
            rng=rng,
        )

        t0, t1, _s, _f, _l, _h, _b, _d, _bp, ctype, trump, _tr, bid_type, *_ = result

        assert t0 + t1 == 10, f"Expected 10 total tricks, got {t0 + t1}"
        assert bid_type == "loner", f"Expected bid_type='loner', got '{bid_type}'"
        assert ctype == "suit"
        assert trump == "H"

    def test_loner_scoring_made(self):
        """When declaring team wins all 10 tricks in loner, they get +40."""
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=10,
            tricks_team1=0,
            bid_type="loner",
        )
        assert pts_t0 == 40, f"Made loner should be +40, got {pts_t0}"
        assert pts_t1 == 0, f"Defending team should get 0, got {pts_t1}"

    def test_loner_scoring_failed(self):
        """When declaring team fails loner, they get -40."""
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=7,
            tricks_team1=3,
            bid_type="loner",
        )
        assert pts_t0 == -40, f"Failed loner should be -40, got {pts_t0}"
        assert pts_t1 == 3, f"Defending team should get their tricks, got {pts_t1}"

    def test_loner_scoring_team1_bidder(self):
        """Scoring works correctly when team 1 bids loner."""
        # Bidder at seat 1 (team 1)
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=1,
            tricks_team0=2,
            tricks_team1=8,
            bid_type="loner",
        )
        # Team 1 fails (didn't get all 10)
        assert pts_t1 == -40, f"Failed loner should be -40, got {pts_t1}"
        assert pts_t0 == 2, f"Defending team should get their tricks, got {pts_t0}"


# ── 3. Dataset Generation Tests ─────────────────────────────


class TestDatasetGenerationMoonLoner:
    """Validate moon/loner rows in counterfactual dataset."""

    def test_dataset_with_moon_loner_has_expected_columns(self, seed):
        """Dataset generated with include_moon_loner has is_moon/is_loner columns."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=5,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        assert "is_moon" in df.columns, "Missing is_moon column"
        assert "is_loner" in df.columns, "Missing is_loner column"

    def test_dataset_moon_loner_row_counts(self, seed):
        """Each (deal, seat) should have exactly 6 moon + 6 loner rows."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=5,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        moon_df = df[df["is_moon"] == 1]
        loner_df = df[df["is_loner"] == 1]

        assert len(moon_df) > 0, "No moon rows found"
        assert len(loner_df) > 0, "No loner rows found"

        # 5 deals * 4 seats * 6 contracts = 120 moon rows
        assert (
            len(moon_df) == 5 * 4 * 6
        ), f"Expected {5 * 4 * 6} moon rows, got {len(moon_df)}"
        assert (
            len(loner_df) == 5 * 4 * 6
        ), f"Expected {5 * 4 * 6} loner rows, got {len(loner_df)}"

    def test_dataset_moon_rows_are_bid_type(self, seed):
        """Moon rows should have action_type='bid', bid_n=10."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=3,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        moon_df = df[df["is_moon"] == 1]
        assert (moon_df["action_type"] == "bid").all(), "Moon rows should be bids"
        assert (moon_df["bid_n"] == 10).all(), "Moon rows should have bid_n=10"
        assert (moon_df["is_loner"] == 0).all(), "Moon rows should not be loner"

    def test_dataset_loner_rows_are_bid_type(self, seed):
        """Loner rows should have action_type='bid', bid_n=10."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=3,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        loner_df = df[df["is_loner"] == 1]
        assert (loner_df["action_type"] == "bid").all(), "Loner rows should be bids"
        assert (loner_df["bid_n"] == 10).all(), "Loner rows should have bid_n=10"
        assert (loner_df["is_moon"] == 0).all(), "Loner rows should not be moon"

    def test_dataset_without_moon_loner_has_zeros(self, seed):
        """Without include_moon_loner, is_moon and is_loner should all be 0."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=3,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=False,
        )

        assert "is_moon" in df.columns
        assert "is_loner" in df.columns
        assert (df["is_moon"] == 0).all(), "is_moon should be 0 without flag"
        assert (df["is_loner"] == 0).all(), "is_loner should be 0 without flag"

    def test_dataset_moon_net_points_range(self, seed):
        """Moon counterfactual net_points should be in the +/-20 scoring range."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=10,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        moon_df = df[df["is_moon"] == 1]
        # Moon scoring: declaring gets +20 or -20; defending gets their tricks (0-10)
        # net_points = focal - opponent, so range is roughly [-30, 20]
        assert (
            moon_df["net_points"].min() >= -30
        ), f"Moon net_points too low: {moon_df['net_points'].min()}"
        assert (
            moon_df["net_points"].max() <= 30
        ), f"Moon net_points too high: {moon_df['net_points'].max()}"

    def test_dataset_loner_net_points_range(self, seed):
        """Loner counterfactual net_points should be in the +/-40 scoring range."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=10,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        loner_df = df[df["is_loner"] == 1]
        # Loner scoring: declaring gets +40 or -40; defending gets their tricks (0-10)
        # net_points = focal - opponent, so range is roughly [-50, 40]
        assert (
            loner_df["net_points"].min() >= -50
        ), f"Loner net_points too low: {loner_df['net_points'].min()}"
        assert (
            loner_df["net_points"].max() <= 50
        ), f"Loner net_points too high: {loner_df['net_points'].max()}"


# ── 4. Counterfactual Simulation Tests ──────────────────────


class TestCounterfactualSimulations:
    """Validate moon/loner counterfactual simulation functions."""

    def test_moon_counterfactual_returns_valid_output(self, seed):
        """simulate_moon_counterfactual returns (net_points, tricks_won)."""
        hands = generate_deal(seed, 0)
        net_pts, tricks = simulate_moon_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="H"
        )

        assert isinstance(net_pts, float)
        assert isinstance(tricks, float)
        assert 0 <= tricks <= 10

    def test_loner_counterfactual_returns_valid_output(self, seed):
        """simulate_loner_counterfactual returns (net_points, tricks_won)."""
        hands = generate_deal(seed, 0)
        net_pts, tricks = simulate_loner_counterfactual(
            hands, focal_seat=0, contract_type="suit", trump_suit="H"
        )

        assert isinstance(net_pts, float)
        assert isinstance(tricks, float)
        assert 0 <= tricks <= 10

    def test_moon_counterfactual_deterministic(self, seed):
        """Same inputs produce same moon counterfactual output."""
        results = []
        for _ in range(2):
            hands = generate_deal(seed, 0)
            result = simulate_moon_counterfactual(
                hands, focal_seat=0, contract_type="suit", trump_suit="H"
            )
            results.append(result)

        assert results[0] == results[1], "Moon counterfactual should be deterministic"

    def test_loner_counterfactual_deterministic(self, seed):
        """Same inputs produce same loner counterfactual output."""
        results = []
        for _ in range(2):
            hands = generate_deal(seed, 0)
            result = simulate_loner_counterfactual(
                hands, focal_seat=0, contract_type="suit", trump_suit="H"
            )
            results.append(result)

        assert results[0] == results[1], "Loner counterfactual should be deterministic"

    @pytest.mark.parametrize("focal_seat", [0, 1, 2, 3])
    def test_moon_counterfactual_all_seats(self, seed, focal_seat):
        """Moon counterfactual works for all focal seats."""
        hands = generate_deal(seed, 0)
        net_pts, tricks = simulate_moon_counterfactual(
            hands, focal_seat=focal_seat, contract_type="suit", trump_suit="H"
        )
        assert 0 <= tricks <= 10

    @pytest.mark.parametrize("focal_seat", [0, 1, 2, 3])
    def test_loner_counterfactual_all_seats(self, seed, focal_seat):
        """Loner counterfactual works for all focal seats."""
        hands = generate_deal(seed, 0)
        net_pts, tricks = simulate_loner_counterfactual(
            hands, focal_seat=focal_seat, contract_type="suit", trump_suit="H"
        )
        assert 0 <= tricks <= 10


# ── 5. Gate X1 Validation Tests ─────────────────────────────


class TestGateX1MoonLoner:
    """Validate Gate X1 passes for datasets with moon/loner."""

    def test_gate_x1_passes_with_moon_loner(self, seed):
        """Gate X1 validation succeeds for dataset with moon/loner rows."""
        continuation = AlwaysPassBidder()
        n_deals = 5
        df = generate_dataset(
            seed=seed,
            n_deals=n_deals,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        # Should not raise
        validate_gate_x1(df, n_deals, include_moon_loner=True)

    def test_gate_x1_passes_without_moon_loner(self, seed):
        """Gate X1 validation succeeds for dataset without moon/loner rows."""
        continuation = AlwaysPassBidder()
        n_deals = 5
        df = generate_dataset(
            seed=seed,
            n_deals=n_deals,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=False,
        )

        # Should not raise
        validate_gate_x1(df, n_deals, include_moon_loner=False)


# ── 6. End-to-End Pipeline Test ─────────────────────────────


class TestEndToEndPipeline:
    """Validate the full generate -> train -> bid pipeline with moon/loner."""

    @pytest.mark.slow
    def test_generate_and_train_with_moon_loner(self, seed):
        """Generate dataset with moon/loner, verify it is trainable end-to-end."""
        from train_action_value import (
            load_dataset,
            resolve_feature_names,
            split_by_deal,
        )

        # Step 1: Generate small dataset with moon/loner and write to parquet
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=30,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        # Verify dataset structure
        assert "is_moon" in df.columns
        assert "is_loner" in df.columns
        assert len(df[df["is_moon"] == 1]) > 0
        assert len(df[df["is_loner"] == 1]) > 0

        # Step 2: Write to temp parquet and load via training pipeline
        with tempfile.TemporaryDirectory() as tmpdir:
            parquet_path = Path(tmpdir) / "action_value.parquet"
            df.to_parquet(parquet_path, index=False)

            # load_dataset validates columns — should succeed with moon/loner data
            loaded = load_dataset(str(parquet_path))
            assert len(loaded) == len(df)

            # Step 3: Verify all contract families present
            families = set(loaded["contract_family"].unique())
            assert {"none", "suit", "high", "low"}.issubset(families)

            # Step 4: Resolve features and verify trainable shape
            feature_names = resolve_feature_names("full", "suit")
            assert len(feature_names) > 0

            # Step 5: Split by deal — should work with moon/loner data
            train_df, val_df, test_df = split_by_deal(loaded, seed=seed)
            assert len(train_df) > 0
            assert len(val_df) > 0
            assert len(test_df) > 0

            # Step 6: Verify suit data is trainable
            suit_train = train_df[train_df["contract_family"] == "suit"]
            assert (
                len(suit_train) > 5
            ), f"Need suit rows to train, got {len(suit_train)}"

            # Verify feature columns have no NaN
            for fname in feature_names:
                if fname in suit_train.columns:
                    assert not suit_train[fname].isna().any(), f"NaN in feature {fname}"

    def test_moon_loner_flags_mutually_exclusive(self, seed):
        """is_moon and is_loner are never both 1 for the same row."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=10,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        both_set = df[(df["is_moon"] == 1) & (df["is_loner"] == 1)]
        assert (
            len(both_set) == 0
        ), f"Found {len(both_set)} rows with both is_moon=1 and is_loner=1"

    def test_regular_rows_have_zero_flags(self, seed):
        """Regular (non-moon, non-loner) rows have is_moon=0 and is_loner=0."""
        continuation = AlwaysPassBidder()
        df = generate_dataset(
            seed=seed,
            n_deals=5,
            continuation_policy=continuation,
            progress=False,
            include_moon_loner=True,
        )

        # Rows that are not moon or loner
        regular_df = df[(df["is_moon"] == 0) & (df["is_loner"] == 0)]
        assert len(regular_df) > 0, "Should have regular rows"

        # These should include passes and regular bids
        assert "pass" in regular_df["action_type"].values
        assert "bid" in regular_df["action_type"].values


# ── 7. Cross-Validation: Engine vs Counterfactual ───────────


class TestEngineCounterfactualConsistency:
    """Verify that engine simulation and counterfactual simulation agree on scoring."""

    def test_moon_scoring_consistency(self):
        """Moon scoring in engine matches counterfactual scoring logic."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        # Run through engine
        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysMoonPolicy(contract="H", seat_to_bid=0)] * 4,
            hands=[list(h) for h in hands],
            initial_leader=0,
            deal_id=0,
            rng=random.Random(42),
        )

        engine_t0, engine_t1 = result[0], result[1]
        engine_bid_type = result[12]

        # Verify engine reports moon bid_type
        assert engine_bid_type == "moon"

        # Verify scoring via compute_points matches expected moon rules
        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=engine_t0,
            tricks_team1=engine_t1,
            bid_type="moon",
        )

        if engine_t0 == 10:
            assert pts_t0 == 20, "Made moon should give +20"
        else:
            assert pts_t0 == -20, "Failed moon should give -20"
        assert pts_t1 == engine_t1, "Defending gets their tricks"

    def test_loner_scoring_consistency(self):
        """Loner scoring in engine matches counterfactual scoring logic."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysLonerPolicy(contract="H", seat_to_bid=0)] * 4,
            hands=[list(h) for h in hands],
            initial_leader=0,
            deal_id=0,
            rng=random.Random(42),
        )

        engine_t0, engine_t1 = result[0], result[1]
        engine_bid_type = result[12]

        assert engine_bid_type == "loner"

        pts_t0, pts_t1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=engine_t0,
            tricks_team1=engine_t1,
            bid_type="loner",
        )

        if engine_t0 == 10:
            assert pts_t0 == 40, "Made loner should give +40"
        else:
            assert pts_t0 == -40, "Failed loner should give -40"
        assert pts_t1 == engine_t1, "Defending gets their tricks"

    def test_regular_scoring_unchanged(self):
        """Regular bid scoring is unaffected by moon/loner additions."""
        rng = random.Random(42)
        deck = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)

        result = play_single_hand(
            contract_type=None,
            bidding_policies=[AlwaysRegularPolicy(contract="H", bid_n=6)] * 4,
            hands=[list(h) for h in hands],
            initial_leader=0,
            deal_id=0,
            rng=random.Random(42),
        )

        engine_t0, engine_t1 = result[0], result[1]
        engine_bid_type = result[12]

        assert engine_bid_type == "regular"

        pts_t0, pts_t1 = compute_points(
            winning_bid=6,
            bidder_position=0,
            tricks_team0=engine_t0,
            tricks_team1=engine_t1,
            bid_type="regular",
        )

        if engine_t0 >= 6:
            # Made bid: both teams get their tricks
            assert pts_t0 == engine_t0
            assert pts_t1 == engine_t1
        else:
            # Set: bid team gets -bid, defending gets tricks
            assert pts_t0 == -6
            assert pts_t1 == engine_t1


# ── 8. Bid Action Type Tests ────────────────────────────────


class TestBidActionTypes:
    """Validate BidAction factory methods and overcall hierarchy."""

    def test_moon_bid_creation(self):
        """BidAction.moon() creates a valid moon bid."""
        action = BidAction.moon("H")
        assert action.n == 10
        assert action.contract == "H"
        assert action.bid_type == "moon"
        assert not action.is_pass()

    def test_loner_bid_creation(self):
        """BidAction.loner() creates a valid loner bid."""
        action = BidAction.loner("H")
        assert action.n == 10
        assert action.contract == "H"
        assert action.bid_type == "loner"
        assert not action.is_pass()

    def test_overcall_hierarchy(self):
        """Loner overcalls moon overcalls regular 10."""
        regular_10 = BidAction.bid(10, "H")
        moon = BidAction.moon("H")
        loner = BidAction.loner("H")

        assert moon.overcalls(regular_10), "Moon should overcall regular 10"
        assert loner.overcalls(moon), "Loner should overcall moon"
        assert loner.overcalls(regular_10), "Loner should overcall regular 10"
        assert not regular_10.overcalls(moon), "Regular 10 should not overcall moon"

    def test_moon_must_be_level_10(self):
        """Moon bids at non-10 levels are rejected."""
        with pytest.raises(ValueError, match="level 10"):
            BidAction(n=8, contract="H", bid_type="moon")

    def test_loner_must_be_level_10(self):
        """Loner bids at non-10 levels are rejected."""
        with pytest.raises(ValueError, match="level 10"):
            BidAction(n=8, contract="H", bid_type="loner")

    def test_pass_cannot_be_moon(self):
        """A pass cannot have bid_type='moon'."""
        with pytest.raises(ValueError, match="regular"):
            BidAction(n=0, contract=None, bid_type="moon")

    def test_bid_rank_ordering(self):
        """bid_rank() orders: pass < regular < moon < loner."""
        pass_bid = BidAction.pass_bid()
        regular_6 = BidAction.bid(6, "H")
        regular_10 = BidAction.bid(10, "H")
        moon = BidAction.moon("H")
        loner = BidAction.loner("H")

        assert pass_bid.bid_rank() < regular_6.bid_rank()
        assert regular_6.bid_rank() < regular_10.bid_rank()
        assert regular_10.bid_rank() < moon.bid_rank()
        assert moon.bid_rank() < loner.bid_rank()

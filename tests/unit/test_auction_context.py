"""Tests for partner bidding context feature extraction."""

from bid_euchre.core.cards import Card
from bid_euchre.features.auction_context import (
    PARTNER_FEATURE_NAMES,
    PARTNER_FEATURE_NAMES_V2,
    extract_partner_features,
    extract_partner_features_v2,
)
from bid_euchre.strategy.bidding import (
    _POSITION_FEATURE_NAMES,
    BiddingObservation,
    extract_state_features,
)


def _bid_entry(seat: int, tricks: int, contract_type: str, trump: str | None = None):
    return {
        "seat": seat,
        "action": "BID",
        "tricks_bid": tricks,
        "contract_type": contract_type,
        "trump": trump,
    }


def _pass_entry(seat: int):
    return {
        "seat": seat,
        "action": "PASS",
        "tricks_bid": 0,
        "contract_type": None,
        "trump": None,
    }


class TestExtractPartnerFeatures:
    def test_partner_bid_extracts_level(self):
        # Seat 0's partner is seat 2; seat 2 bids 5 suit
        transcript = [_bid_entry(2, 5, "suit", "H")]
        result = extract_partner_features(0, transcript)
        assert result["partner_bid_level"] == 5

    def test_partner_passed_flag(self):
        transcript = [_pass_entry(2)]
        result = extract_partner_features(0, transcript)
        assert result["partner_passed"] == 1
        assert result["partner_bid_level"] == 0

    def test_empty_transcript_all_zeros(self):
        result = extract_partner_features(0, ())
        assert result["partner_bid_level"] == 0
        assert result["partner_passed"] == 0
        assert result["partner_suit_match"] == 0

    def test_partner_suit_match(self):
        transcript = [_bid_entry(2, 4, "suit", "S")]
        result = extract_partner_features(0, transcript, observer_best_contract="suit")
        assert result["partner_suit_match"] == 1

    def test_partner_suit_mismatch(self):
        transcript = [_bid_entry(2, 3, "high")]
        result = extract_partner_features(0, transcript, observer_best_contract="suit")
        assert result["partner_suit_match"] == 0

    def test_multiple_entries_takes_highest(self):
        transcript = [
            _bid_entry(2, 3, "suit", "H"),
            _bid_entry(2, 5, "suit", "S"),
        ]
        result = extract_partner_features(0, transcript)
        assert result["partner_bid_level"] == 5

    def test_ignores_non_partner_seats(self):
        # Seat 0's partner is seat 2; bids from seat 1 and 3 should be ignored
        transcript = [
            _bid_entry(1, 6, "suit", "H"),
            _bid_entry(3, 8, "high"),
        ]
        result = extract_partner_features(0, transcript)
        assert result["partner_bid_level"] == 0
        assert result["partner_passed"] == 0

    def test_no_observer_contract_defaults_suit_match_zero(self):
        transcript = [_bid_entry(2, 4, "suit", "D")]
        result = extract_partner_features(0, transcript, observer_best_contract=None)
        assert result["partner_suit_match"] == 0

    def test_partner_seat_wraps_correctly(self):
        # Seat 1's partner is seat 3
        transcript = [_bid_entry(3, 4, "low")]
        result = extract_partner_features(1, transcript)
        assert result["partner_bid_level"] == 4

        # Seat 3's partner is seat 1
        transcript = [_bid_entry(1, 6, "high")]
        result = extract_partner_features(3, transcript)
        assert result["partner_bid_level"] == 6

    def test_pass_then_bid_captures_both(self):
        transcript = [
            _pass_entry(2),
            _bid_entry(2, 4, "suit", "H"),
        ]
        result = extract_partner_features(0, transcript)
        assert result["partner_passed"] == 1
        assert result["partner_bid_level"] == 4

    def test_feature_names_constant_matches_output(self):
        result = extract_partner_features(0, ())
        assert set(result.keys()) == set(PARTNER_FEATURE_NAMES)

    def test_accepts_list_transcript(self):
        """Transcript can be list (from JSONL) or tuple (from BiddingObservation)."""
        transcript = [_bid_entry(2, 3, "suit", "H")]
        result = extract_partner_features(0, transcript)
        assert result["partner_bid_level"] == 3


class TestExtractPartnerFeaturesV2:
    """Tests for v2 suit-relative partner feature extraction (R1)."""

    def test_suit_contract_same_suit(self):
        """Partner bids same suit as observer -> same_suit channel."""
        transcript = [_bid_entry(2, 5, "suit", "H")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_level_same_suit"] == 5
        assert result["partner_level_same_color"] == 0
        assert result["partner_level_off_color"] == 0

    def test_suit_contract_same_color(self):
        """Partner bids same-color suit (H/D are same color)."""
        transcript = [_bid_entry(2, 4, "suit", "D")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_level_same_suit"] == 0
        assert result["partner_level_same_color"] == 4
        assert result["partner_level_off_color"] == 0

    def test_suit_contract_off_color(self):
        """Partner bids off-color suit (H observer, S partner = off-color)."""
        transcript = [_bid_entry(2, 3, "suit", "S")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_level_same_suit"] == 0
        assert result["partner_level_same_color"] == 0
        assert result["partner_level_off_color"] == 3

    def test_high_contract_suit_channels_zero(self):
        """For high contracts, suit channels are always 0."""
        transcript = [_bid_entry(2, 5, "suit", "H")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="high",
            observer_trump_suit=None,
        )
        assert result["partner_level_same_suit"] == 0
        assert result["partner_level_same_color"] == 0
        assert result["partner_level_off_color"] == 0

    def test_low_contract_suit_channels_zero(self):
        """For low contracts, suit channels are always 0."""
        transcript = [_bid_entry(2, 6, "suit", "C")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="low",
            observer_trump_suit=None,
        )
        assert result["partner_level_same_suit"] == 0
        assert result["partner_level_same_color"] == 0
        assert result["partner_level_off_color"] == 0

    def test_high_low_channels(self):
        """Partner bids high and low -> those channels populated."""
        transcript = [
            _bid_entry(2, 4, "high"),
            _bid_entry(2, 3, "low"),
        ]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_level_high"] == 4
        assert result["partner_level_low"] == 3

    def test_partner_passed(self):
        """partner_passed flag works in v2."""
        transcript = [_pass_entry(2)]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_passed"] == 1
        assert result["partner_level_same_suit"] == 0

    def test_empty_transcript_all_zeros(self):
        """First bidder: empty transcript -> all zeros."""
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=(),
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        for key in PARTNER_FEATURE_NAMES_V2:
            assert result[key] == 0, f"{key} should be 0"

    def test_feature_names_constant_matches_output(self):
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=(),
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert set(result.keys()) == set(PARTNER_FEATURE_NAMES_V2)

    def test_multiple_suit_bids_takes_highest(self):
        """Multiple bids in same-suit channel -> takes highest level."""
        transcript = [
            _bid_entry(2, 3, "suit", "H"),
            _bid_entry(2, 6, "suit", "H"),
        ]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        assert result["partner_level_same_suit"] == 6

    def test_ignores_non_partner_seats(self):
        """Only partner seat (seat+2)%4 bids are considered."""
        transcript = [
            _bid_entry(1, 7, "suit", "H"),
            _bid_entry(3, 8, "high"),
        ]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="H",
        )
        for key in PARTNER_FEATURE_NAMES_V2:
            assert result[key] == 0

    def test_clubs_spades_same_color(self):
        """C and S are same color."""
        transcript = [_bid_entry(2, 4, "suit", "C")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type="suit",
            observer_trump_suit="S",
        )
        assert result["partner_level_same_color"] == 4
        assert result["partner_level_same_suit"] == 0

    def test_none_contract_type_suit_channels_zero(self):
        """observer_contract_type=None (pass) -> suit channels zero."""
        transcript = [_bid_entry(2, 5, "suit", "H")]
        result = extract_partner_features_v2(
            seat=0,
            auction_transcript=transcript,
            observer_contract_type=None,
            observer_trump_suit=None,
        )
        assert result["partner_level_same_suit"] == 0
        assert result["partner_level_same_color"] == 0
        assert result["partner_level_off_color"] == 0


def _make_obs(seat, dealer_seat, transcript=(), current_high_bid=0):
    """Create a minimal BiddingObservation for testing."""
    hand = [
        Card("C", "T"),
        Card("D", "T"),
        Card("H", "T"),
        Card("S", "T"),
        Card("C", "J"),
        Card("D", "Q"),
        Card("H", "Q"),
        Card("S", "Q"),
        Card("C", "K"),
        Card("S", "A"),
    ]
    return BiddingObservation(
        hand=hand,
        seat=seat,
        dealer_seat=dealer_seat,
        current_high_bid=current_high_bid,
        auction_transcript=tuple(transcript),
    )


class TestPositionFeatures:
    """Tests for auction_position and is_dealer features."""

    def test_auction_position_formula(self):
        """auction_position = (seat - dealer_seat - 1) % 4."""
        # Dealer=0, seat=1 -> position = (1-0-1)%4 = 0 (first to bid)
        obs = _make_obs(seat=1, dealer_seat=0)
        state = extract_state_features(obs, "suit", "H")
        pos_start = 39 + 6  # hand(39) + partner_v2(6)
        assert state[pos_start] == 0.0  # auction_position
        assert state[pos_start + 1] == 0.0  # is_dealer (seat 1 != dealer 0)

    def test_is_dealer_flag(self):
        """is_dealer = 1 when seat == dealer_seat."""
        obs = _make_obs(seat=2, dealer_seat=2)
        state = extract_state_features(obs, "suit", "H")
        pos_start = 39 + 6
        # auction_position = (2-2-1)%4 = 3 (dealer bids last)
        assert state[pos_start] == 3.0
        assert state[pos_start + 1] == 1.0  # is_dealer

    def test_all_four_positions(self):
        """Verify auction_position for all 4 seats with dealer=0."""
        expected_positions = {
            1: 0,  # first to bid
            2: 1,  # second
            3: 2,  # third
            0: 3,  # dealer (last)
        }
        for seat, expected_pos in expected_positions.items():
            obs = _make_obs(seat=seat, dealer_seat=0)
            state = extract_state_features(obs, "suit", "H")
            pos_start = 39 + 6
            assert state[pos_start] == float(
                expected_pos
            ), f"seat={seat}: expected position {expected_pos}, got {state[pos_start]}"

    def test_state_vector_length_57(self):
        """R1 state vector is 39 hand + 6 partner + 2 position + 10 positional = 57."""
        obs = _make_obs(seat=0, dealer_seat=3)
        state = extract_state_features(obs, "suit", "H")
        assert len(state) == 57

    def test_position_feature_names(self):
        """Position feature name list is correct."""
        assert _POSITION_FEATURE_NAMES == ["auction_position", "is_dealer"]

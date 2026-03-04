"""Tests for partner bidding context feature extraction."""

import pytest

from bid_euchre.features.auction_context import (
    PARTNER_FEATURE_NAMES,
    extract_partner_features,
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
        assert result["partner_bid_confidence"] == 0.0

    def test_partner_suit_match(self):
        transcript = [_bid_entry(2, 4, "suit", "S")]
        result = extract_partner_features(0, transcript, observer_best_contract="suit")
        assert result["partner_suit_match"] == 1

    def test_partner_suit_mismatch(self):
        transcript = [_bid_entry(2, 3, "high")]
        result = extract_partner_features(0, transcript, observer_best_contract="suit")
        assert result["partner_suit_match"] == 0

    def test_partner_bid_confidence_normalized(self):
        transcript = [_bid_entry(2, 7, "suit", "D")]
        result = extract_partner_features(0, transcript)
        assert result["partner_bid_confidence"] == pytest.approx(0.7)

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

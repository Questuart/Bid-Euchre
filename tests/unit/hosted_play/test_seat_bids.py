"""Unit tests for _build_seat_bids() in web/routes.py.

Covers every rendering branch: pass, moon, loner, suit contracts (with symbol),
HIGH, LOW, missing seat entries, and last-bid-wins semantics.

Follow-up from PR #2040 review finding (issue #2053).
"""

from __future__ import annotations

from web.routes import _build_seat_bids


class TestBuildSeatBidsPass:
    """Pass action renders as 'Pass'."""

    def test_single_pass(self):
        auction = [{"seat": 0, "action": "pass"}]
        assert _build_seat_bids(auction) == {0: "Pass"}

    def test_all_pass(self):
        auction = [{"seat": s, "action": "pass"} for s in range(4)]
        assert _build_seat_bids(auction) == {0: "Pass", 1: "Pass", 2: "Pass", 3: "Pass"}


class TestBuildSeatBidsMoon:
    """Moon bids render as 'Moon'."""

    def test_moon_bid(self):
        auction = [
            {"seat": 0, "action": "bid", "bid_type": "moon", "n": 10, "contract": "S"},
        ]
        assert _build_seat_bids(auction) == {0: "Moon"}

    def test_moon_overrides_earlier_regular(self):
        auction = [
            {
                "seat": 0,
                "action": "bid",
                "bid_type": "regular",
                "n": 6,
                "contract": "S",
            },
            {"seat": 0, "action": "bid", "bid_type": "moon", "n": 10, "contract": "S"},
        ]
        assert _build_seat_bids(auction) == {0: "Moon"}


class TestBuildSeatBidsLoner:
    """Loner bids render as 'Loner'."""

    def test_loner_bid(self):
        auction = [
            {"seat": 1, "action": "bid", "bid_type": "loner", "n": 10, "contract": "H"},
        ]
        assert _build_seat_bids(auction) == {1: "Loner"}


class TestBuildSeatBidsSuitContract:
    """Suit-contract regular bids render with suit symbol."""

    def test_spades(self):
        auction = [{"seat": 0, "action": "bid", "n": 6, "contract": "S"}]
        result = _build_seat_bids(auction)
        assert result == {0: "6\u2660"}  # 6♠

    def test_hearts(self):
        auction = [{"seat": 1, "action": "bid", "n": 7, "contract": "H"}]
        result = _build_seat_bids(auction)
        assert result == {1: "7\u2665"}  # 7♥

    def test_diamonds(self):
        auction = [{"seat": 2, "action": "bid", "n": 8, "contract": "D"}]
        result = _build_seat_bids(auction)
        assert result == {2: "8\u2666"}  # 8♦

    def test_clubs(self):
        auction = [{"seat": 3, "action": "bid", "n": 9, "contract": "C"}]
        result = _build_seat_bids(auction)
        assert result == {3: "9\u2663"}  # 9♣


class TestBuildSeatBidsHighLow:
    """HIGH and LOW contracts render as 'Hi' and 'Lo'."""

    def test_high_contract(self):
        auction = [{"seat": 0, "action": "bid", "n": 6, "contract": "HIGH"}]
        assert _build_seat_bids(auction) == {0: "6 Hi"}

    def test_low_contract(self):
        auction = [{"seat": 0, "action": "bid", "n": 6, "contract": "LOW"}]
        assert _build_seat_bids(auction) == {0: "6 Lo"}


class TestBuildSeatBidsEdgeCases:
    """Edge cases: empty auction, missing seat, last-bid-wins."""

    def test_empty_auction(self):
        assert _build_seat_bids([]) == {}

    def test_entry_without_seat_is_skipped(self):
        auction = [{"action": "pass"}]
        assert _build_seat_bids(auction) == {}

    def test_seat_none_is_skipped(self):
        auction = [{"seat": None, "action": "pass"}]
        assert _build_seat_bids(auction) == {}

    def test_last_bid_wins_for_same_seat(self):
        """When a seat bids multiple times, the most recent entry wins."""
        auction = [
            {"seat": 0, "action": "bid", "n": 6, "contract": "S"},
            {"seat": 0, "action": "bid", "n": 7, "contract": "H"},
        ]
        result = _build_seat_bids(auction)
        assert result == {0: "7\u2665"}  # last bid: 7♥

    def test_pass_overwrites_earlier_bid(self):
        """A later pass overwrites an earlier bid for the same seat."""
        auction = [
            {"seat": 0, "action": "bid", "n": 6, "contract": "S"},
            {"seat": 0, "action": "pass"},
        ]
        assert _build_seat_bids(auction) == {0: "Pass"}


class TestBuildSeatBidsMultiSeat:
    """Multi-seat auction with mixed bid types."""

    def test_mixed_auction(self):
        auction = [
            {"seat": 0, "action": "bid", "n": 6, "contract": "S"},
            {"seat": 1, "action": "pass"},
            {"seat": 2, "action": "bid", "n": 7, "contract": "HIGH"},
            {"seat": 3, "action": "bid", "bid_type": "moon", "n": 10, "contract": "H"},
        ]
        result = _build_seat_bids(auction)
        assert result == {
            0: "6\u2660",  # 6♠
            1: "Pass",
            2: "7 Hi",
            3: "Moon",
        }

    def test_bid_type_defaults_to_regular(self):
        """Missing bid_type key defaults to 'regular' behavior."""
        auction = [{"seat": 0, "action": "bid", "n": 6, "contract": "D"}]
        result = _build_seat_bids(auction)
        assert result == {0: "6\u2666"}  # 6♦

    def test_unknown_contract_passes_through(self):
        """Unknown contract string is used as-is (no symbol mapping)."""
        auction = [{"seat": 0, "action": "bid", "n": 6, "contract": "WEIRD"}]
        result = _build_seat_bids(auction)
        assert result == {0: "6WEIRD"}

    def test_seat_as_string_is_coerced(self):
        """Seat values that come as strings are coerced to int keys."""
        auction = [{"seat": "2", "action": "pass"}]
        result = _build_seat_bids(auction)
        assert result == {2: "Pass"}

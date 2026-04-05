"""Unit tests for _format_auction_event() in web/routes.py.

Verifies that auction log entries use Unicode suit symbols (♠, ♥, ♦, ♣)
instead of letter abbreviations (S, H, D, C).

Fix for issue #2417.
"""

from __future__ import annotations

from web.routes import _format_auction_event


class TestFormatAuctionEventPass:
    """Pass actions render as '<Name> passed'."""

    def test_pass(self):
        assert _format_auction_event(1, {"action": "pass"}) == "Slim passed"


class TestFormatAuctionEventMoonLoner:
    """Moon and loner bids render without suit."""

    def test_moon(self):
        result = _format_auction_event(
            0, {"bid_type": "moon", "n": 10, "contract": "S"}
        )
        assert result == "You bid Moon"

    def test_loner(self):
        result = _format_auction_event(
            3, {"bid_type": "loner", "n": 10, "contract": "H"}
        )
        assert result == "Deuce bid Loner"


class TestFormatAuctionEventHighLow:
    """HIGH and LOW contracts render as words."""

    def test_high(self):
        result = _format_auction_event(2, {"n": 6, "contract": "HIGH"})
        assert result == "Ace bid 6 High"

    def test_low(self):
        result = _format_auction_event(1, {"n": 5, "contract": "LOW"})
        assert result == "Slim bid 5 Low"


class TestFormatAuctionEventSuitSymbols:
    """Suit contracts use Unicode symbols, not letter abbreviations (#2417)."""

    def test_spades(self):
        result = _format_auction_event(1, {"n": 5, "contract": "S"})
        assert result == "Slim bid 5 ♠"
        assert "S" not in result.split("bid")[1]  # no raw letter after "bid"

    def test_hearts(self):
        result = _format_auction_event(0, {"n": 6, "contract": "H"})
        assert result == "You bid 6 ♥"

    def test_diamonds(self):
        result = _format_auction_event(2, {"n": 8, "contract": "D"})
        assert result == "Ace bid 8 ♦"

    def test_clubs(self):
        result = _format_auction_event(3, {"n": 7, "contract": "C"})
        assert result == "Deuce bid 7 ♣"

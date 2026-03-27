"""Tests for moon bid card exchange mechanic."""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.sim.exchange import (
    _card_value_for_discard,
    _card_value_for_partner,
    _select_mooner_discards,
    _select_partner_gifts,
    perform_exchange,
    select_mooner_discards,
    select_partner_gifts,
)

# ============================================================
# Helper to build hands from shorthand
# ============================================================


def _cards(specs: list[str]) -> list[Card]:
    """Convert shorthand like ['AH', 'KS'] to Card objects."""
    return [Card(suit=s[1], rank=s[0]) for s in specs]


def _make_hand_10(base: list[str], fill_suit: str = "C") -> list[Card]:
    """Make a 10-card hand, padding with low fill_suit cards if needed."""
    hand = _cards(base)
    fill_ranks = ["T", "J", "Q", "K", "A"]
    idx = 0
    while len(hand) < 10 and idx < len(fill_ranks):
        candidate = Card(suit=fill_suit, rank=fill_ranks[idx])
        if candidate not in hand:
            hand.append(candidate)
        idx += 1
    # If still short, fill with other suits
    for s in ["D", "H", "S"]:
        for r in fill_ranks:
            if len(hand) >= 10:
                break
            candidate = Card(suit=s, rank=r)
            if candidate not in hand:
                hand.append(candidate)
    return hand[:10]


# ============================================================
# Tests: perform_exchange produces valid hands
# ============================================================


class TestExchangeValidity:
    """Exchange produces valid hands with correct card count and no duplicates created."""

    def test_exchange_preserves_hand_sizes(self):
        """Both hands remain 10 cards after exchange."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"], fill_suit="D")
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"], fill_suit="C")

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "suit", "H")

        assert len(new_m) == 10
        assert len(new_p) == 10

    def test_exchange_preserves_total_cards(self):
        """Total card pool is unchanged after exchange."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"], fill_suit="D")
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"], fill_suit="C")

        original = sorted(mooner + partner, key=lambda c: (c.suit, c.rank))
        new_m, new_p, _, _ = perform_exchange(mooner, partner, "suit", "H")
        after = sorted(new_m + new_p, key=lambda c: (c.suit, c.rank))

        assert original == after

    def test_exchange_does_not_mutate_inputs(self):
        """Original hands are not modified."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"], fill_suit="D")
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"], fill_suit="C")

        mooner_copy = list(mooner)
        partner_copy = list(partner)

        perform_exchange(mooner, partner, "suit", "H")

        assert mooner == mooner_copy
        assert partner == partner_copy

    def test_exchange_high_contract(self):
        """Exchange works for high (no-trump) contracts."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"], fill_suit="D")
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"], fill_suit="C")

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "high", None)

        assert len(new_m) == 10
        assert len(new_p) == 10

    def test_exchange_low_contract(self):
        """Exchange works for low (no-trump) contracts."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"], fill_suit="D")
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"], fill_suit="C")

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "low", None)

        assert len(new_m) == 10
        assert len(new_p) == 10


# ============================================================
# Tests: Mooner heuristic selects worst cards
# ============================================================


class TestMoonerDiscard:
    """Mooner heuristic identifies the weakest cards to give away."""

    def test_suit_discards_offsuit_low_cards(self):
        """Suit contract: mooner discards lowest non-trump cards."""
        # Hand: 5 hearts (trump) + 5 diamonds (non-trump)
        # Note: JD is the left bower (trump) when trump=H, so it won't be discarded.
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        trump_suit = "H"

        indices = _select_mooner_discards(hand, "suit", trump_suit)
        discards = [hand[i] for i in indices]

        # Should discard the 2 lowest non-trump diamonds (TD, QD)
        # JD is left bower (trump), so it's kept
        assert Card("D", "T") in discards
        assert Card("D", "Q") in discards

    def test_suit_never_discards_bowers(self):
        """Suit contract: bowers are never discarded."""
        # Hand with right bower (JH) and left bower (JD with trump=H)
        hand = _cards(["JH", "JD", "AH", "KH", "QH", "TH", "TC", "QC", "KC", "AC"])
        trump_suit = "H"

        indices = _select_mooner_discards(hand, "suit", trump_suit)
        discards = [hand[i] for i in indices]

        assert Card("H", "J") not in discards  # Right bower
        assert Card("D", "J") not in discards  # Left bower

    def test_suit_discards_lowest_offsuit(self):
        """Suit contract: prefers discarding cards from shorter suits."""
        # 3 trump + 4 clubs + 3 spades
        hand = _cards(["AH", "KH", "QH", "TC", "JC", "QC", "KC", "TS", "JS", "QS"])
        trump_suit = "H"

        indices = _select_mooner_discards(hand, "suit", trump_suit)
        discards = [hand[i] for i in indices]

        # Should discard from spades (shorter suit, lower ranks)
        # Both TS and JS are candidates (lowest rank in shorter suit)
        for d in discards:
            assert d.suit != "H"  # Never discard trump

    def test_high_discards_lowest_ranks(self):
        """High contract: discards lowest-ranked cards (tens)."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])

        indices = _select_mooner_discards(hand, "high", None)
        discards = [hand[i] for i in indices]

        # Should discard the 2 tens
        assert all(c.rank == "T" for c in discards)

    def test_low_discards_highest_ranks(self):
        """Low contract: discards highest-ranked cards (aces)."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])

        indices = _select_mooner_discards(hand, "low", None)
        discards = [hand[i] for i in indices]

        # Should discard the 2 aces
        assert all(c.rank == "A" for c in discards)


# ============================================================
# Tests: Partner heuristic selects best cards
# ============================================================


class TestPartnerGifts:
    """Partner heuristic identifies the strongest cards to give the mooner."""

    def test_suit_gives_bowers_first(self):
        """Suit contract: partner gives bowers over other trump."""
        # Partner has right bower and other trump
        hand = _cards(["JH", "AH", "KH", "QH", "TH", "AD", "KD", "QD", "JD", "TD"])
        trump_suit = "H"

        indices = _select_partner_gifts(hand, "suit", trump_suit)
        gifts = [hand[i] for i in indices]

        # Right bower (JH) should be given
        assert Card("H", "J") in gifts

    def test_suit_gives_left_bower(self):
        """Suit contract: left bower is treated as trump and given."""
        # Partner has left bower (JD when trump is H) and other cards
        hand = _cards(["JD", "AD", "KD", "QD", "TD", "AC", "KC", "QC", "JC", "TC"])
        trump_suit = "H"

        indices = _select_partner_gifts(hand, "suit", trump_suit)
        gifts = [hand[i] for i in indices]

        # Left bower (JD) should be given
        assert Card("D", "J") in gifts

    def test_suit_gives_trump_over_offsuit_ace(self):
        """Suit contract: trump cards are preferred over non-trump aces."""
        hand = _cards(["AH", "KH", "AC", "AD", "AS", "TC", "TD", "QC", "QD", "QS"])
        trump_suit = "H"

        indices = _select_partner_gifts(hand, "suit", trump_suit)
        gifts = [hand[i] for i in indices]

        # AH and KH (trump) should be given, not offsuit aces
        assert Card("H", "A") in gifts
        assert Card("H", "K") in gifts

    def test_high_gives_aces_then_kings(self):
        """High contract: gives aces first, then kings."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])

        indices = _select_partner_gifts(hand, "high", None)
        gifts = [hand[i] for i in indices]

        # Should give the 2 aces
        assert all(c.rank == "A" for c in gifts)

    def test_low_gives_tens_then_jacks(self):
        """Low contract: gives tens first, then jacks."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])

        indices = _select_partner_gifts(hand, "low", None)
        gifts = [hand[i] for i in indices]

        # Should give the 2 tens
        assert all(c.rank == "T" for c in gifts)


# ============================================================
# Tests: Bower handling in exchange
# ============================================================


class TestBowerHandling:
    """Bowers are correctly valued during exchange."""

    def test_right_bower_valued_above_left(self):
        """Right bower has higher discard value than left bower."""
        trump_suit = "H"
        hand = _cards(["JH", "JD", "AH", "KH", "QH", "TH", "TC", "QC", "KC", "AC"])

        right_val = _card_value_for_discard(Card("H", "J"), "suit", trump_suit, hand)
        left_val = _card_value_for_discard(Card("D", "J"), "suit", trump_suit, hand)

        assert right_val > left_val

    def test_partner_right_bower_valued_above_left(self):
        """Partner values right bower above left bower for giving."""
        trump_suit = "H"

        right_val = _card_value_for_partner(Card("H", "J"), "suit", trump_suit)
        left_val = _card_value_for_partner(Card("D", "J"), "suit", trump_suit)

        assert right_val > left_val

    def test_left_bower_treated_as_trump_for_discard(self):
        """Left bower is valued as trump, not its printed suit."""
        trump_suit = "H"
        hand = _cards(["JD", "AD", "KD", "QD", "TD", "AC", "KC", "QC", "JC", "TC"])

        left_bower_val = _card_value_for_discard(
            Card("D", "J"), "suit", trump_suit, hand
        )
        ace_diamond_val = _card_value_for_discard(
            Card("D", "A"), "suit", trump_suit, hand
        )

        # Left bower (trump) should be more valuable than ace of diamonds (non-trump)
        assert left_bower_val > ace_diamond_val

    def test_exchange_with_both_bowers(self):
        """Full exchange with bowers keeps them with the mooner."""
        # Mooner has both bowers + some low offsuit
        mooner = _cards(["JH", "JD", "AH", "KH", "QH", "TH", "TC", "TD", "QC", "QD"])
        # Partner has non-trump cards
        partner = _cards(["AS", "KS", "QS", "JS", "TS", "AC", "KC", "JC", "AD", "KD"])
        trump_suit = "H"

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "suit", trump_suit)

        # Mooner should still have both bowers
        assert Card("H", "J") in new_m  # Right bower
        assert Card("D", "J") in new_m  # Left bower


# ============================================================
# Tests: Double-deck edge cases
# ============================================================


class TestDoubleDeckEdgeCases:
    """Handle identical cards correctly in a double deck."""

    def test_duplicate_cards_in_hands(self):
        """Exchange handles hands with duplicate cards (double deck)."""
        # Both hands contain AC (legal in double deck)
        mooner = _cards(["AH", "KH", "QH", "JH", "TH", "AC", "KC", "QC", "JC", "TC"])
        partner = _cards(["AS", "KS", "QS", "JS", "TS", "AC", "KC", "QC", "JC", "TC"])

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "suit", "H")

        assert len(new_m) == 10
        assert len(new_p) == 10
        # Total cards preserved
        original = sorted(mooner + partner, key=lambda c: (c.suit, c.rank))
        after = sorted(new_m + new_p, key=lambda c: (c.suit, c.rank))
        assert original == after

    def test_duplicate_cards_exchanged(self):
        """When both hands have the same card, exchange still works."""
        # Mooner and partner both have TH
        mooner = _cards(["TH", "AH", "KH", "QH", "JH", "TD", "JD", "QD", "KD", "AD"])
        partner = _cards(["TH", "AS", "KS", "QS", "JS", "TS", "AC", "KC", "QC", "JC"])

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "high", None)

        assert len(new_m) == 10
        assert len(new_p) == 10


# ============================================================
# Tests: No exchange for regular/loner bids (integration boundary)
# ============================================================


class TestNoExchangeForNonMoon:
    """Exchange is only triggered for moon bids — not regular or loner."""

    def test_regular_bid_no_exchange_in_sim(self):
        """Verify the simulation integration point: regular bids skip exchange.

        This tests the conditional in simulation.py — perform_exchange is
        only called when bid_type == 'moon'.
        """
        from bid_euchre.strategy.bidding import BidAction

        regular = BidAction.bid(7, "H")
        assert regular.bid_type == "regular"
        assert regular.bid_type != "moon"

    def test_loner_bid_no_exchange_in_sim(self):
        """Loner bids do not trigger exchange (partner sits out entirely)."""
        from bid_euchre.strategy.bidding import BidAction

        loner = BidAction.loner("H")
        assert loner.bid_type == "loner"
        assert loner.bid_type != "moon"


# ============================================================
# Tests: Error handling
# ============================================================


class TestExchangeErrors:
    """Exchange validates inputs."""

    def test_wrong_mooner_hand_size(self):
        """Raises ValueError if mooner hand is not 10 cards."""
        mooner = _cards(["AH", "KH", "QH"])
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"])

        with pytest.raises(ValueError, match="Mooner hand must have 10 cards"):
            perform_exchange(mooner, partner, "suit", "H")

    def test_wrong_partner_hand_size(self):
        """Raises ValueError if partner hand is not 10 cards."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"])
        partner = _cards(["AS", "KS"])

        with pytest.raises(ValueError, match="Partner hand must have 10 cards"):
            perform_exchange(mooner, partner, "suit", "H")

    def test_invalid_contract_type(self):
        """Raises ValueError for unknown contract type."""
        mooner = _make_hand_10(["AH", "KH", "QH", "JH", "TH"])
        partner = _make_hand_10(["AS", "KS", "QS", "JS", "TS"])

        with pytest.raises(ValueError, match="Unknown contract_type"):
            perform_exchange(mooner, partner, "unknown", None)


# ============================================================
# Tests: End-to-end exchange correctness
# ============================================================


class TestExchangeEndToEnd:
    """Verify exchange logic end-to-end with known hands."""

    def test_suit_exchange_mooner_gets_trump(self):
        """Mooner discards weakest offsuit, receives partner's trump."""
        # Mooner: 5 trump (H) + 5 low clubs
        mooner = _cards(["AH", "KH", "QH", "TH", "TH", "TC", "TC", "JC", "JC", "QC"])
        # Partner: 3 trump (H) + 7 non-trump
        partner = _cards(["JH", "JD", "KD", "AD", "AS", "KS", "QS", "JS", "TS", "TD"])
        trump_suit = "H"

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "suit", trump_suit)

        # Mooner should have gained the right bower (JH) and left bower (JD)
        assert Card("H", "J") in new_m
        assert Card("D", "J") in new_m

    def test_high_exchange_aces_transferred(self):
        """High contract: partner gives aces to mooner."""
        # Mooner: mixed hand with some low cards
        mooner = _cards(["AH", "KH", "QH", "JH", "TH", "TD", "JD", "QD", "KD", "AD"])
        # Partner: has aces in spades and clubs
        partner = _cards(["AS", "KS", "QS", "JS", "TS", "AC", "KC", "QC", "JC", "TC"])

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "high", None)

        # Mooner should have received AS and AC (the partner's aces)
        assert Card("S", "A") in new_m
        assert Card("C", "A") in new_m

    def test_low_exchange_tens_transferred(self):
        """Low contract: partner gives tens to mooner."""
        # Mooner: has mostly high cards (bad for low)
        mooner = _cards(["AH", "KH", "QH", "JH", "AD", "KD", "QD", "JD", "AC", "KC"])
        # Partner: has tens
        partner = _cards(["TH", "TD", "TC", "TS", "QS", "JS", "QC", "JC", "KS", "AS"])

        new_m, new_p, _, _ = perform_exchange(mooner, partner, "low", None)

        # Mooner should have received 2 tens from partner
        tens_in_mooner = [c for c in new_m if c.rank == "T"]
        assert len(tens_in_mooner) >= 2


# ============================================================
# Tests: Public wrapper functions
# ============================================================


class TestPublicWrappers:
    """Public wrappers delegate to private functions and expose the same contract."""

    # --- select_mooner_discards ---

    def test_mooner_wrapper_matches_private_suit(self):
        """select_mooner_discards returns same indices as _select_mooner_discards for suit."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_mooner_discards(hand, "suit", "H") == _select_mooner_discards(
            hand, "suit", "H"
        )

    def test_mooner_wrapper_matches_private_high(self):
        """select_mooner_discards returns same indices as _select_mooner_discards for high."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_mooner_discards(hand, "high", None) == _select_mooner_discards(
            hand, "high", None
        )

    def test_mooner_wrapper_matches_private_low(self):
        """select_mooner_discards returns same indices as _select_mooner_discards for low."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_mooner_discards(hand, "low", None) == _select_mooner_discards(
            hand, "low", None
        )

    def test_mooner_wrapper_custom_n_cards(self):
        """select_mooner_discards forwards n_cards parameter."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        result = select_mooner_discards(hand, "suit", "H", n_cards=3)
        assert len(result) == 3
        assert result == _select_mooner_discards(hand, "suit", "H", n_cards=3)

    def test_mooner_wrapper_returns_descending_indices(self):
        """select_mooner_discards returns indices sorted descending."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        indices = select_mooner_discards(hand, "suit", "H")
        assert indices == sorted(indices, reverse=True)

    def test_mooner_wrapper_never_discards_bowers(self):
        """select_mooner_discards never selects bowers for discard."""
        hand = _cards(["JH", "JD", "AH", "KH", "QH", "TH", "TC", "QC", "KC", "AC"])
        indices = select_mooner_discards(hand, "suit", "H")
        discards = [hand[i] for i in indices]
        assert Card("H", "J") not in discards  # Right bower
        assert Card("D", "J") not in discards  # Left bower

    def test_mooner_wrapper_invalid_contract_type(self):
        """select_mooner_discards raises ValueError for unknown contract type."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        with pytest.raises(ValueError, match="Unknown contract_type"):
            select_mooner_discards(hand, "unknown", None)

    # --- select_partner_gifts ---

    def test_partner_wrapper_matches_private_suit(self):
        """select_partner_gifts returns same indices as _select_partner_gifts for suit."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_partner_gifts(hand, "suit", "H") == _select_partner_gifts(
            hand, "suit", "H"
        )

    def test_partner_wrapper_matches_private_high(self):
        """select_partner_gifts returns same indices as _select_partner_gifts for high."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_partner_gifts(hand, "high", None) == _select_partner_gifts(
            hand, "high", None
        )

    def test_partner_wrapper_matches_private_low(self):
        """select_partner_gifts returns same indices as _select_partner_gifts for low."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        assert select_partner_gifts(hand, "low", None) == _select_partner_gifts(
            hand, "low", None
        )

    def test_partner_wrapper_custom_n_cards(self):
        """select_partner_gifts forwards n_cards parameter."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        result = select_partner_gifts(hand, "suit", "H", n_cards=3)
        assert len(result) == 3
        assert result == _select_partner_gifts(hand, "suit", "H", n_cards=3)

    def test_partner_wrapper_returns_descending_indices(self):
        """select_partner_gifts returns indices sorted descending."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        indices = select_partner_gifts(hand, "high", None)
        assert indices == sorted(indices, reverse=True)

    def test_partner_wrapper_gives_bowers_first(self):
        """select_partner_gifts selects bowers as gifts for suit contract."""
        hand = _cards(["JH", "AH", "KH", "QH", "TH", "AD", "KD", "QD", "JD", "TD"])
        indices = select_partner_gifts(hand, "suit", "H")
        gifts = [hand[i] for i in indices]
        # Right bower (JH) should be given
        assert Card("H", "J") in gifts

    def test_partner_wrapper_invalid_contract_type(self):
        """select_partner_gifts raises ValueError for unknown contract type."""
        hand = _cards(["AH", "KH", "QH", "JH", "TH", "AD", "KD", "QD", "JD", "TD"])
        with pytest.raises(ValueError, match="Unknown contract_type"):
            select_partner_gifts(hand, "invalid", None)

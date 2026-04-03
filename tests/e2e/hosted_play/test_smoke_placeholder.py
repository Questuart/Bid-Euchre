"""E2E tests for hosted-play UI features: lead indicator, trick winner,
hand sorting, and seat labels.

These tests exercise the full pipeline from MatchEngine through
get_visible_state to Jinja2 template rendering.  They validate that
game state features are correctly surfaced in the rendered HTML without
requiring a running server or browser.

Tested features:
1. Lead indicator — lead-suit badge and seat-marker--leader in trick.html
2. Trick winner display — .trick-winner text and winning card
3. Hand sorting — sort_hand_for_display produces correct card order
4. Seat labels — seat labels render correctly across templates

See ``plans/browser_game_expansion/governing_plan.md`` for context.
"""

from __future__ import annotations

import jinja2
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.hosted_play.engine import (
    HUMAN_SEAT,
    MatchEngine,
    sort_hand_for_display,
)

from .conftest import (
    SEED,
    advance_to_trick_play,
    build_visible_context,
    play_full_hand,
    play_one_trick,
)

# ---------------------------------------------------------------------------
# Test 1: Lead indicator
# ---------------------------------------------------------------------------


class TestLeadIndicator:
    """Verify the lead suit badge and leader seat marker render correctly."""

    @pytest.mark.e2e
    def test_lead_suit_badge_present_during_trick(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Lead suit symbol renders in the trick heading when cards have been played."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play (all-pass redeal)")

        # Play at least one card to establish lead. If it's the human's turn
        # and the trick is empty, the human leads — so play a card.
        if hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_plays(state)
            state = engine.submit_human_card(state, legal[0])
            hand = state.current_hand

        ctx = build_visible_context(engine, state)

        # After playing, we need a trick with plays.  If the trick completed
        # instantly (all 4 played), check completed_tricks.
        trick = ctx.get("current_trick")
        if trick is not None and len(trick.get("plays", [])) == 0:
            trick = None
        if trick is None and ctx.get("completed_tricks"):
            trick = ctx["completed_tricks"][-1]

        assert trick is not None, "Expected a trick with plays after playing a card"
        assert len(trick["plays"]) > 0, "Expected at least one play in trick"

        # Render trick partial with the trick that has plays visible
        tmpl = jinja_env.get_template("partials/trick.html")
        render_ctx = dict(ctx)
        if (
            ctx.get("current_trick") is None
            or len(ctx["current_trick"].get("plays", [])) == 0
        ):
            # Show the completed trick
            render_ctx["current_trick"] = None
        html = tmpl.render(**render_ctx)

        # Lead suit badge should be present
        assert "lead-suit" in html, "Expected lead-suit CSS class in trick HTML"
        assert "lead-suit--" in html, "Expected suit-specific lead class"

    @pytest.mark.e2e
    def test_leader_seat_marker_present(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """The 'Leader' marker renders next to the trick leader's seat."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/trick.html")
        html = tmpl.render(**ctx)

        assert "seat-marker--leader" in html, "Expected leader marker in trick HTML"
        assert 'title="Leader"' in html, "Expected 'Leader' title attribute on marker"

    @pytest.mark.e2e
    def test_lead_suit_matches_first_card_suit(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """The lead suit badge shows the suit of the first card played."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        # Play one card if it's human's turn
        if hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_plays(state)
            state = engine.submit_human_card(state, legal[0])

        ctx = build_visible_context(engine, state)
        trick = ctx.get("current_trick")
        if trick is not None and len(trick.get("plays", [])) == 0:
            trick = None
        if trick is None and ctx.get("completed_tricks"):
            trick = ctx["completed_tricks"][-1]

        assert (
            trick is not None and len(trick["plays"]) > 0
        ), "Need a trick with at least one play"
        lead_suit = trick["plays"][0][1][0]  # First play's suit

        suit_symbols = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
        suit_classes = {"S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
        expected_symbol = suit_symbols[lead_suit]
        expected_class = f"lead-suit--{suit_classes[lead_suit]}"

        tmpl = jinja_env.get_template("partials/trick.html")
        render_ctx = dict(ctx)
        if (
            ctx.get("current_trick") is None
            or len(ctx["current_trick"].get("plays", [])) == 0
        ):
            render_ctx["current_trick"] = None
        html = tmpl.render(**render_ctx)

        assert (
            expected_symbol in html
        ), f"Expected lead suit symbol '{expected_symbol}' for suit {lead_suit}"
        assert expected_class in html, f"Expected lead suit class '{expected_class}'"


# ---------------------------------------------------------------------------
# Test 2: Trick winner display
# ---------------------------------------------------------------------------


class TestTrickWinnerDisplay:
    """Verify trick winner text and winning card render after trick completion."""

    @pytest.mark.e2e
    def test_trick_winner_text_after_completion(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """After a trick completes, the winner text is rendered."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        # Play one full trick
        state = play_one_trick(engine, state)

        ctx = build_visible_context(engine, state)
        assert (
            len(ctx["completed_tricks"]) >= 1
        ), "Expected at least one completed trick"

        # Render with current_trick=None to show the completed trick
        last_trick = ctx["completed_tricks"][-1]
        winner_seat = last_trick["winner"]

        tmpl = jinja_env.get_template("partials/trick.html")
        # Render showing the last completed trick (as happens between tricks)
        render_ctx = dict(ctx)
        render_ctx["current_trick"] = None
        html = tmpl.render(**render_ctx)

        assert "trick-winner" in html, "Expected .trick-winner element"
        assert "won" in html, "Expected 'won' text in trick winner display"

        # Verify the correct seat label appears
        seat_labels = {0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"}
        expected_label = seat_labels[winner_seat]
        assert (
            expected_label in html
        ), f"Expected winner label '{expected_label}' for seat {winner_seat}"

    @pytest.mark.e2e
    def test_winning_card_displayed(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """The winning card (suit symbol + rank) renders in trick winner text."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        state = play_one_trick(engine, state)

        ctx = build_visible_context(engine, state)
        assert len(ctx["completed_tricks"]) >= 1

        last_trick = ctx["completed_tricks"][-1]
        winning_card = last_trick.get("winning_card")

        if winning_card is None:
            pytest.skip("No winning_card data in completed trick")

        tmpl = jinja_env.get_template("partials/trick.html")
        render_ctx = dict(ctx)
        render_ctx["current_trick"] = None
        html = tmpl.render(**render_ctx)

        suit_symbols = {"S": "\u2660", "H": "\u2665", "D": "\u2666", "C": "\u2663"}
        expected_suit_sym = suit_symbols[winning_card[0]]
        expected_rank = winning_card[1]

        assert (
            expected_suit_sym in html
        ), f"Expected winning card suit symbol '{expected_suit_sym}'"
        assert expected_rank in html, f"Expected winning card rank '{expected_rank}'"

    @pytest.mark.e2e
    def test_trick_winner_in_history(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Trick history table shows the winner column for completed tricks."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        state = play_one_trick(engine, state)
        ctx = build_visible_context(engine, state)

        assert len(ctx["completed_tricks"]) >= 1

        tmpl = jinja_env.get_template("partials/trick_history.html")
        html = tmpl.render(**ctx)

        assert "trick-history" in html, "Expected trick history to render"
        assert (
            "trick-history__cell--winner" in html
        ), "Expected winner cell styling in trick history"

        # The "Won" column header should be present
        assert "Won" in html, "Expected 'Won' column header in trick history"


# ---------------------------------------------------------------------------
# Test 3: Hand sorting
# ---------------------------------------------------------------------------


class TestHandSorting:
    """Verify sort_hand_for_display produces correct card order."""

    @pytest.mark.e2e
    def test_suit_grouping_no_trump(self) -> None:
        """Cards group by suit in S > H > D > C order without trump."""
        hand = [
            Card("C", "A"),
            Card("H", "K"),
            Card("S", "Q"),
            Card("D", "J"),
        ]
        sort_hand_for_display(hand)

        suits = [c.suit for c in hand]
        assert suits == [
            "S",
            "H",
            "D",
            "C",
        ], f"Expected S > H > D > C order, got {suits}"

    @pytest.mark.e2e
    def test_suit_grouping_with_trump(self) -> None:
        """Trump suit cards appear first when contract_type is 'suit'."""
        hand = [
            Card("S", "A"),
            Card("H", "K"),
            Card("D", "Q"),
            Card("C", "T"),
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="D")

        # Diamonds (trump) should come first
        assert hand[0].suit == "D", f"Expected trump suit first, got {hand[0].suit}"

    @pytest.mark.e2e
    def test_rank_order_within_suit(self) -> None:
        """Within a suit, ranks order J > A > K > Q > T (non-trump)."""
        hand = [
            Card("S", "T"),
            Card("S", "Q"),
            Card("S", "K"),
            Card("S", "A"),
            Card("S", "J"),
        ]
        sort_hand_for_display(hand)

        ranks = [c.rank for c in hand]
        assert ranks == [
            "J",
            "A",
            "K",
            "Q",
            "T",
        ], f"Expected J > A > K > Q > T, got {ranks}"

    @pytest.mark.e2e
    def test_low_contract_rank_order(self) -> None:
        """Low contracts order T > J > Q > K > A."""
        hand = [
            Card("H", "A"),
            Card("H", "K"),
            Card("H", "Q"),
            Card("H", "J"),
            Card("H", "T"),
        ]
        sort_hand_for_display(hand, contract_type="low")

        ranks = [c.rank for c in hand]
        assert ranks == [
            "T",
            "J",
            "Q",
            "K",
            "A",
        ], f"Expected T > J > Q > K > A for low, got {ranks}"

    @pytest.mark.e2e
    def test_bowers_sort_to_top_of_trump(self) -> None:
        """Right bower then left bower sort to the very top of trump suit."""
        # Right bower = J of trump, Left bower = J of same color
        # Trump = Spades -> Right bower = J♠, Left bower = J♣
        hand = [
            Card("S", "A"),
            Card("S", "K"),
            Card("C", "J"),  # Left bower (same color as Spades)
            Card("S", "J"),  # Right bower
            Card("S", "Q"),
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="S")

        # Right bower first, then left bower, then A > K > Q
        assert hand[0] == Card("S", "J"), f"Expected right bower first, got {hand[0]}"
        assert hand[1] == Card("C", "J"), f"Expected left bower second, got {hand[1]}"
        remaining_ranks = [c.rank for c in hand[2:]]
        assert remaining_ranks == [
            "A",
            "K",
            "Q",
        ], f"Expected A > K > Q after bowers, got {remaining_ranks}"

    @pytest.mark.e2e
    def test_sorted_hand_renders_in_order(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Engine-sorted hand renders cards in the sorted order in HTML.

        Each card in the hand template has a data-card-index attribute (for
        legal cards) or appears sequentially in the card-fan.  We verify the
        template emits cards in the order provided by the engine (sorted).
        """
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        human_hand = ctx["human_hand"]

        tmpl = jinja_env.get_template("partials/hand.html")
        html = tmpl.render(**ctx)

        # Extract data-card-index values from the rendered HTML.  These
        # correspond to the 0-based position in human_hand and should appear
        # in order 0, 1, 2, ... in the HTML.
        import re

        indices = [int(m) for m in re.findall(r'data-card-index="(\d+)"', html)]

        # Even if not all cards are legal (and thus have data-card-index),
        # verify the ones that do appear are in ascending order.
        if len(indices) >= 2:
            for i in range(1, len(indices)):
                assert indices[i] > indices[i - 1], (
                    f"data-card-index {indices[i]} appears before {indices[i - 1]} "
                    "— hand is not rendered in sorted order"
                )
        else:
            # Fallback: verify the card count matches
            suit_symbols = {
                "S": "\u2660",
                "H": "\u2665",
                "D": "\u2666",
                "C": "\u2663",
            }
            rendered_suits = sum(html.count(sym) for sym in suit_symbols.values())
            assert rendered_suits >= len(
                human_hand
            ), "Expected at least as many suit symbols as cards in hand"


# ---------------------------------------------------------------------------
# Test 4: Seat labels
# ---------------------------------------------------------------------------


class TestSeatLabels:
    """Verify seat labels render correctly across all templates."""

    EXPECTED_LABELS = {0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"}

    @pytest.mark.e2e
    def test_seat_labels_in_trick_area(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Seat labels render in empty card slots during trick play."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/trick.html")
        html = tmpl.render(**ctx)

        # At least some seat labels should appear in empty card slots
        found_labels = sum(
            1 for label in self.EXPECTED_LABELS.values() if label in html
        )
        assert (
            found_labels >= 2
        ), f"Expected at least 2 seat labels in trick area, found {found_labels}"

    @pytest.mark.e2e
    def test_seat_labels_in_score_bar(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Score bar renders 'You' and 'AI' labels and dealer seat label."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/score.html")
        html = tmpl.render(**ctx)

        assert "You:" in html, "Expected 'You:' label in score bar"
        assert "AI:" in html, "Expected 'AI:' label in score bar"

        # Dealer label should use the seat_labels mapping
        dealer_seat = ctx["dealer_seat"]
        expected_dealer = self.EXPECTED_LABELS[dealer_seat]
        assert (
            expected_dealer in html
        ), f"Expected dealer label '{expected_dealer}' for seat {dealer_seat}"

    @pytest.mark.e2e
    def test_seat_labels_in_game_board_ai_hands(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """AI hand blocks show correct seat labels in the game board."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/game_board.html")
        html = tmpl.render(**ctx)

        assert "Slim" in html, "Expected 'Slim' in game board"
        assert "Ace" in html, "Expected 'Ace' in game board"
        assert "Deuce" in html, "Expected 'Deuce' in game board"

    @pytest.mark.e2e
    def test_seat_labels_in_trick_history(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Trick history table uses seat labels in the 'Won' column."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        state = play_one_trick(engine, state)
        ctx = build_visible_context(engine, state)

        if not ctx["completed_tricks"]:
            pytest.skip("No completed tricks available")

        tmpl = jinja_env.get_template("partials/trick_history.html")
        html = tmpl.render(**ctx)

        winner = ctx["completed_tricks"][-1]["winner"]
        # Trick history now uses character names
        history_labels = {0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"}
        expected = history_labels[winner]
        assert expected in html, f"Expected winner label '{expected}' in trick history"

    @pytest.mark.e2e
    def test_score_bar_shows_game_score(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Score bar shows 'Current Game Score' label per #2200 cleanup."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)

        tmpl = jinja_env.get_template("partials/score.html")
        html = tmpl.render(**ctx)

        # Score bar shows game score label (declarer moved to contract bar per #2200)
        assert (
            "Current Game Score" in html
        ), "Expected 'Current Game Score' label in score bar"

    @pytest.mark.e2e
    def test_seat_labels_in_hand_result(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Hand result screen uses seat labels for the declarer."""
        state = engine.start_match(SEED, "test")
        state = play_full_hand(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "complete":
            pytest.skip("Hand did not complete")

        ctx = build_visible_context(engine, state)
        ctx["phase"] = "hand_result"

        tmpl = jinja_env.get_template("partials/hand_result.html")
        html = tmpl.render(**ctx)

        bidder_seat = ctx.get("bidder_seat")
        if bidder_seat is not None:
            expected = self.EXPECTED_LABELS[bidder_seat]
            assert (
                expected in html
            ), f"Expected declarer label '{expected}' in hand result"


# ---------------------------------------------------------------------------
# Test 5: Cross-feature integration
# ---------------------------------------------------------------------------


class TestCrossFeatureIntegration:
    """Verify features work together in the full game board render."""

    @pytest.mark.e2e
    def test_game_board_renders_all_features(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Full game board includes seat labels, trick area, and hand."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/game_board.html")
        html = tmpl.render(**ctx)

        # Trick area renders
        assert "trick-area" in html, "Expected trick area in game board"
        # Hand renders
        assert "human-hand" in html, "Expected human hand in game board"
        # Score bar renders
        assert "score-bar" in html, "Expected score bar in game board"
        # Compass-rose layout renders
        assert "compass-layout" in html, "Expected compass layout in game board"

    @pytest.mark.e2e
    def test_game_board_after_one_trick(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Game board renders correctly after completing one trick."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        state = play_one_trick(engine, state)
        ctx = build_visible_context(engine, state)
        tmpl = jinja_env.get_template("partials/game_board.html")
        html = tmpl.render(**ctx)

        # Should have trick count in score
        assert (
            "Tricks:" in html or "trick-count" in html
        ), "Expected trick count display after completing a trick"
        # Should have trick history
        assert (
            "trick-history" in html or "Cards Played" in html
        ), "Expected trick history after completing a trick"

    @pytest.mark.e2e
    def test_hand_result_renders_after_full_hand(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Hand result screen renders with scoring table after full hand."""
        state = engine.start_match(SEED, "test")
        state = play_full_hand(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "complete":
            pytest.skip("Hand did not complete normally")

        ctx = build_visible_context(engine, state)
        ctx["phase"] = "hand_result"

        tmpl = jinja_env.get_template("partials/game_board.html")
        html = tmpl.render(**ctx)

        assert "hand-result" in html, "Expected hand-result in rendered board"
        assert "result-title" in html, "Expected result title"
        assert "result-table" in html, "Expected scoring table"
        assert "result-match-score" in html, "Expected match score display"
        assert "Next Hand" in html, "Expected 'Next Hand' button"


# ---------------------------------------------------------------------------
# Test 6: Current high play indicator
# ---------------------------------------------------------------------------


class TestCurrentHighPlayIndicator:
    """Verify card--winning class and trick-current-winner text render mid-trick.

    The engine auto-advances AI after human plays, which may complete the
    trick.  To test mid-trick rendering we look for states where AIs have
    already played (AI-led trick) before the human's turn — giving us an
    active trick with plays but not yet complete.  If the human leads,
    we play the human card first to establish a lead, then check whether
    the trick still has plays (it may auto-complete via AI).
    """

    @staticmethod
    def _get_mid_trick_ctx(
        engine: MatchEngine,
    ) -> dict | None:
        """Try multiple tricks to find a mid-trick state with plays.

        Returns a (ctx, state) tuple or None if no mid-trick found.
        """
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        # Try up to 10 tricks to find a mid-trick state
        for _ in range(10):
            hand = state.current_hand
            if hand is None or hand.phase != "trick_play":
                return None

            trick = hand.current_trick
            if trick is not None and len(trick.plays) >= 1:
                # AI has already played — we have mid-trick state
                return build_visible_context(engine, state)

            # Human is the leader with 0 plays — play our card
            if hand.current_seat == HUMAN_SEAT:
                legal = engine.get_legal_plays(state)
                state = engine.submit_human_card(state, legal[0])

                hand = state.current_hand
                if hand is None:
                    return None

                # Check if we now have a mid-trick (human played but
                # AI hasn't finished the trick yet)
                trick = hand.current_trick
                if trick is not None and len(trick.plays) >= 1:
                    return build_visible_context(engine, state)

                # Trick completed — try next trick
                continue

        return None

    @pytest.mark.e2e
    def test_winning_card_highlight_mid_trick(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """card--winning class appears on the currently winning card during active trick."""
        ctx = self._get_mid_trick_ctx(engine)
        if ctx is None:
            pytest.skip("Could not reach mid-trick state with this seed")

        tmpl = jinja_env.get_template("partials/trick.html")
        html = tmpl.render(**ctx)

        assert (
            "card--winning" in html
        ), "Expected card--winning class on the currently winning card"

    @pytest.mark.e2e
    def test_winning_text_label_mid_trick(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """trick-current-winner text appears during active trick."""
        ctx = self._get_mid_trick_ctx(engine)
        if ctx is None:
            pytest.skip("Could not reach mid-trick state with this seed")

        tmpl = jinja_env.get_template("partials/trick.html")
        html = tmpl.render(**ctx)

        assert (
            "trick-current-winner" in html
        ), "Expected trick-current-winner element in trick HTML"
        assert (
            "currently winning the trick" in html
        ), "Expected 'currently winning the trick' text in high play indicator"

    @pytest.mark.e2e
    def test_no_winning_indicator_on_completed_trick(
        self, engine: MatchEngine, jinja_env: jinja2.Environment
    ) -> None:
        """Winning indicator does not appear on completed tricks."""
        state = engine.start_match(SEED, "test")
        state = advance_to_trick_play(engine, state)

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Seed produced no trick play")

        # Complete one trick
        state = play_one_trick(engine, state)

        ctx = build_visible_context(engine, state)

        # Render with current_trick=None (showing completed trick)
        render_ctx = dict(ctx)
        render_ctx["current_trick"] = None
        tmpl = jinja_env.get_template("partials/trick.html")
        html = tmpl.render(**render_ctx)

        assert (
            "trick-current-winner" not in html
        ), "trick-current-winner should not appear on completed tricks"

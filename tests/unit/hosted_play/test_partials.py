"""Unit tests for Jinja2 template partials in web/templates/partials/.

Validates that each partial renders correctly with representative context
data matching the visible state contract from MatchEngine.get_visible_state().
"""

from __future__ import annotations

import os

import jinja2
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "templates",
)


@pytest.fixture()
def env():
    """Jinja2 environment loading from web/templates/."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )


# ---------------------------------------------------------------------------
# nickname_form.html
# ---------------------------------------------------------------------------


class TestNicknameForm:
    def test_renders_form_with_link_uuid(self, env):
        tmpl = env.get_template("partials/nickname_form.html")
        html = tmpl.render(link_uuid="abc-123")
        assert 'action="/play/abc-123/nickname"' in html
        assert 'hx-post="/play/abc-123/nickname"' in html
        assert 'name="nickname"' in html
        assert "Set Nickname" in html

    def test_has_required_attribute(self, env):
        tmpl = env.get_template("partials/nickname_form.html")
        html = tmpl.render(link_uuid="test-uuid")
        assert "required" in html


# ---------------------------------------------------------------------------
# model_select.html
# ---------------------------------------------------------------------------


class ModelStub:
    """Minimal stand-in for ModelInfo."""

    def __init__(self, id: str, name: str, description: str):
        self.id = id
        self.name = name
        self.description = description


class TestModelSelect:
    def test_renders_models_dropdown(self, env):
        models = [
            ModelStub("heuristic", "Heuristic", "Rule-based"),
            ModelStub("hybrid", "Hybrid", "Statistical bidder"),
        ]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(link_uuid="abc-123", nickname="Alice", models=models)
        assert 'value="heuristic"' in html
        assert "Heuristic" in html
        assert 'value="hybrid"' in html
        assert "Alice" in html
        assert 'action="/play/abc-123/select-ai"' in html

    def test_renders_single_model(self, env):
        models = [ModelStub("heuristic", "Heuristic", "Rule-based")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(link_uuid="x", nickname="Bob", models=models)
        assert 'value="heuristic"' in html
        assert "Start Match" in html


# ---------------------------------------------------------------------------
# bid_panel.html
# ---------------------------------------------------------------------------


class TestBidPanel:
    def test_renders_pass_option(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=3,
        )
        assert 'value="0">Pass' in html
        assert 'name="turn_number"' in html
        assert 'value="0"' in html

    def test_shows_legal_bid_levels_above_current(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=4,
            auction=[
                {"seat": 1, "n": 0, "action": "pass"},
                {"seat": 2, "n": 5, "action": "bid", "contract": "H"},
            ],
            current_high_bid=5,
            dealer_seat=0,
        )
        # Extract only the bid_n select options for precise checking.
        # Bid levels 1-5 should NOT appear as bid_n options.
        # (value="4" also exists in the turn_number hidden input, so
        # we check within the select element specifically.)
        import re

        bid_select = re.search(
            r'<select id="bid-level"[^>]*>(.*?)</select>', html, re.DOTALL
        )
        assert bid_select is not None
        bid_options = bid_select.group(1)
        for n in range(1, 6):
            assert f'value="{n}">{n}' not in bid_options
        # Should have bid levels 6-10
        for n in range(6, 11):
            assert f'value="{n}">{n}' in bid_options
        # Pass is always available
        assert "Pass" in bid_options

    def test_shows_all_contract_types(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert "Spades" in html
        assert "Hearts" in html
        assert "Diamonds" in html
        assert "Clubs" in html
        assert "High (no trump)" in html
        assert "Low (no trump)" in html

    def test_moon_and_loner_labels_show_points(self, env):
        """Moon and loner labels should display the point values shown to players."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert "Moon (20)" in html
        assert "Loner (40)" in html
        assert "Moon (10)" not in html
        assert "Loner (10)" not in html

    def test_auction_transcript_shows_entries(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {"seat": 1, "n": 0, "action": "pass"},
                {"seat": 2, "n": 3, "action": "bid", "contract": "S"},
            ],
            current_high_bid=3,
            dealer_seat=0,
        )
        assert "Pass" in html
        # Spade symbol in transcript
        assert "\u2660" in html  # ♠

    def test_form_targets_correct_route(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=5,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert 'hx-post="/play/test-uuid/bid"' in html
        assert 'hx-target="#game-board"' in html

    def test_moon_bid_in_transcript_has_emphasis(self, env):
        """Moon bids in the auction transcript get CSS class and badge."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {
                    "seat": 1,
                    "n": 10,
                    "action": "bid",
                    "contract": "H",
                    "bid_type": "moon",
                },
            ],
            current_high_bid=10,
            dealer_seat=0,
        )
        assert "bid--moon" in html
        assert "bid-type-badge--moon" in html
        assert "Moon" in html

    def test_loner_bid_in_transcript_has_emphasis(self, env):
        """Loner bids in the auction transcript get CSS class and badge."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {
                    "seat": 0,
                    "n": 10,
                    "action": "bid",
                    "contract": "S",
                    "bid_type": "loner",
                },
            ],
            current_high_bid=10,
            dealer_seat=3,
        )
        assert "bid--loner" in html
        assert "bid-type-badge--loner" in html
        assert "Loner" in html

    def test_regular_bid_no_emphasis_class(self, env):
        """Regular bids do not get moon/loner CSS classes."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {"seat": 2, "n": 5, "action": "bid", "contract": "D"},
            ],
            current_high_bid=5,
            dealer_seat=0,
        )
        assert "bid--moon" not in html
        assert "bid--loner" not in html
        assert "bid-type-badge" not in html

    def test_current_high_bid_shows_moon_badge(self, env):
        """The current high bid info line shows a moon badge when bid_type is moon."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {
                    "seat": 1,
                    "n": 10,
                    "action": "bid",
                    "contract": "H",
                    "bid_type": "moon",
                },
            ],
            current_high_bid=10,
            dealer_seat=0,
            bid_type="moon",
        )
        assert "bid-type-badge--moon" in html

    def test_current_high_bid_shows_loner_badge(self, env):
        """The current high bid info line shows a loner badge when bid_type is loner."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=2,
            auction=[
                {
                    "seat": 1,
                    "n": 10,
                    "action": "bid",
                    "contract": "S",
                    "bid_type": "loner",
                },
            ],
            current_high_bid=10,
            dealer_seat=0,
            bid_type="loner",
        )
        assert "bid-type-badge--loner" in html


# ---------------------------------------------------------------------------
# hand.html
# ---------------------------------------------------------------------------


class TestHand:
    def test_renders_cards_during_auction(self, env):
        """During auction, cards are shown but not clickable."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=0,
            human_hand=[["S", "A"], ["H", "K"], ["D", "10"]],
            legal_plays=None,
            phase="auction",
        )
        assert "\u2660" in html  # ♠
        assert "\u2665" in html  # ♥
        assert "\u2666" in html  # ♦
        assert "A" in html
        assert "K" in html
        # No card--legal or card--illegal during auction (plain cards)
        assert "card--legal" not in html

    def test_legal_cards_are_form_buttons(self, env):
        """During trick play, legal cards are form buttons."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=8,
            human_hand=[["S", "A"], ["H", "K"], ["D", "10"]],
            legal_plays=[0, 2],  # First and third cards are legal
            phase="trick_play",
        )
        # Legal cards have form with hx-post
        assert 'hx-post="/play/abc-123/play-card"' in html
        assert 'name="card_index" value="0"' in html
        assert 'name="card_index" value="2"' in html
        assert "card--legal" in html

    def test_illegal_cards_are_divs(self, env):
        """During trick play, illegal cards are plain divs."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=8,
            human_hand=[["S", "A"], ["H", "K"], ["D", "10"]],
            legal_plays=[0],  # Only first card is legal
            phase="trick_play",
        )
        assert "card--illegal" in html
        # card_index=1 should NOT appear in a form
        assert 'name="card_index" value="1"' not in html

    def test_turn_number_in_forms(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=42,
            human_hand=[["C", "J"]],
            legal_plays=[0],
            phase="trick_play",
        )
        assert 'name="turn_number" value="42"' in html


# ---------------------------------------------------------------------------
# trick.html
# ---------------------------------------------------------------------------


class TestTrick:
    def test_renders_empty_trick(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "Trick 1 of 10" in html
        assert "0\u20131" not in html or "0\u20130" in html  # 0–0

    def test_renders_played_cards(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={
                "leader": 1,
                "plays": [
                    [1, ["H", "A"]],
                    [2, ["S", "K"]],
                ],
            },
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "A" in html  # Ace
        assert "\u2665" in html  # ♥
        assert "K" in html  # King
        assert "\u2660" in html  # ♠

    def test_trick_number_increments(self, env):
        tmpl = env.get_template("partials/trick.html")
        # After 3 completed tricks
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[{}, {}, {}],
            tricks_team0=2,
            tricks_team1=1,
        )
        assert "Trick 4 of 10" in html

    def test_no_current_trick(self, env):
        """When current_trick is None (e.g., hand complete)."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[{}, {}, {}, {}, {}],
            tricks_team0=3,
            tricks_team1=2,
        )
        assert "trick-area" in html


# ---------------------------------------------------------------------------
# score.html
# ---------------------------------------------------------------------------


class TestScore:
    def test_renders_scores(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=15,
            score_ai=-3,
            hands_played=4,
            contract_type="suit",
            trump="H",
            winning_bid=6,
            bidder_seat=0,
            tricks_team0=4,
            tricks_team1=2,
            dealer_seat=3,
            phase="trick_play",
        )
        assert "15" in html
        assert "-3" in html
        assert "Hand 5" in html
        assert "6" in html  # bid
        assert "\u2665" in html  # ♥
        assert "You" in html  # declarer

    def test_auction_in_progress(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=0,
            score_ai=0,
            hands_played=0,
            contract_type=None,
            trump=None,
            winning_bid=None,
            bidder_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            dealer_seat=0,
            phase="auction",
        )
        assert "Auction in progress" in html
        assert "Hand 1" in html

    def test_high_contract_display(self, env):
        """Engine produces lowercase 'high' for no-trump high contracts."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type="high",
            trump=None,
            winning_bid=7,
            bidder_seat=1,
            tricks_team0=0,
            tricks_team1=0,
            dealer_seat=2,
            phase="trick_play",
        )
        assert "7" in html
        assert "High" in html

    def test_low_contract_display(self, env):
        """Engine produces lowercase 'low' for no-trump low contracts."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type="low",
            trump=None,
            winning_bid=7,
            bidder_seat=1,
            tricks_team0=0,
            tricks_team1=0,
            dealer_seat=2,
            phase="trick_play",
        )
        assert "7" in html
        assert "Low" in html

    def test_moon_contract_display(self, env):
        """Moon contract shows moon badge instead of bid number."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type="suit",
            trump="H",
            winning_bid=10,
            bidder_seat=0,
            bid_type="moon",
            tricks_team0=3,
            tricks_team1=0,
            dealer_seat=2,
            phase="trick_play",
        )
        assert "contract-bid-type--moon" in html
        assert "Moon" in html

    def test_loner_contract_display(self, env):
        """Loner contract shows loner badge instead of bid number."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type="suit",
            trump="S",
            winning_bid=10,
            bidder_seat=1,
            bid_type="loner",
            tricks_team0=0,
            tricks_team1=3,
            dealer_seat=2,
            phase="trick_play",
        )
        assert "contract-bid-type--loner" in html
        assert "Loner" in html

    def test_regular_bid_shows_number(self, env):
        """Regular bid shows bid number, not moon/loner badges."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type="suit",
            trump="H",
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            tricks_team0=2,
            tricks_team1=1,
            dealer_seat=2,
            phase="trick_play",
        )
        assert "contract-bid-type--moon" not in html
        assert "contract-bid-type--loner" not in html
        assert "6" in html


# ---------------------------------------------------------------------------
# hand_result.html
# ---------------------------------------------------------------------------


class TestHandResult:
    def test_made_bid(self, env):
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert "Made it!" in html
        assert "7" in html  # tricks
        assert "\u2660" in html  # ♠

    def test_set_bid(self, env):
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=8,
            bidder_seat=0,
            contract_type="suit",
            trump="H",
            tricks_team0=5,
            tricks_team1=5,
            points_team0=-8,
            points_team1=5,
            score_human=-8,
            score_ai=5,
            hands_played=1,
        )
        assert "Set!" in html
        assert "-8" in html  # points

    def test_high_contract_result(self, env):
        """Engine produces lowercase 'high' for no-trump high contracts."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=0,
            contract_type="high",
            trump=None,
            tricks_team0=8,
            tricks_team1=2,
            points_team0=8,
            points_team1=2,
            score_human=8,
            score_ai=2,
            hands_played=1,
        )
        assert "Made it!" in html
        assert "High" in html

    def test_low_contract_result(self, env):
        """Engine produces lowercase 'low' for no-trump low contracts."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=1,
            contract_type="low",
            trump=None,
            tricks_team0=3,
            tricks_team1=7,
            points_team0=3,
            points_team1=7,
            score_human=3,
            score_ai=7,
            hands_played=1,
        )
        assert "Made it!" in html
        assert "Low" in html

    def test_moon_made_banner(self, env):
        """Moon made shows special banner with score delta."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=0,
            contract_type="suit",
            trump="H",
            bid_type="moon",
            tricks_team0=10,
            tricks_team1=0,
            points_team0=20,
            points_team1=0,
            score_human=20,
            score_ai=0,
            hands_played=1,
        )
        assert "Moon Made!" in html
        assert "result--moon-made" in html
        assert "+20" in html
        assert "MOON" in html
        assert "MADE" in html
        # Should NOT show regular "Made it!" text
        assert "Made it!" not in html

    def test_moon_set_banner(self, env):
        """Moon set shows special banner with negative score."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            bid_type="moon",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=-20,
            points_team1=3,
            score_human=-20,
            score_ai=3,
            hands_played=1,
        )
        assert "Moon Set!" in html
        assert "result--moon-set" in html
        assert "-20" in html
        assert "SET" in html
        # Should show moon-specific banner, not plain "Set!" alone
        assert ">Set!<" not in html

    def test_loner_made_banner(self, env):
        """Loner made shows special banner."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=0,
            contract_type="suit",
            trump="D",
            bid_type="loner",
            tricks_team0=10,
            tricks_team1=0,
            points_team0=20,
            points_team1=0,
            score_human=20,
            score_ai=0,
            hands_played=1,
        )
        assert "Loner Made!" in html
        assert "result--loner-made" in html
        assert "+20" in html
        assert "LONER" in html

    def test_loner_set_banner(self, env):
        """Loner set shows special banner."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=2,
            contract_type="suit",
            trump="C",
            bid_type="loner",
            tricks_team0=5,
            tricks_team1=5,
            points_team0=-20,
            points_team1=5,
            score_human=-20,
            score_ai=5,
            hands_played=1,
        )
        assert "Loner Set!" in html
        assert "result--loner-set" in html
        assert "-20" in html

    def test_regular_bid_no_moon_loner_class(self, env):
        """Regular bid result does not get moon/loner CSS classes."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            bid_type="regular",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert "result--moon" not in html
        assert "result--loner" not in html
        assert "Made it!" in html

    def test_moon_result_shows_exchange_summary(self, env):
        """Moon results include exchange card summary."""
        html = env.get_template("partials/hand_result.html").render(
            link_uuid="abc-123",
            winning_bid=10,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            bid_type="moon",
            tricks_team0=10,
            tricks_team1=0,
            points_team0=20,
            points_team1=0,
            score_human=20,
            score_ai=0,
            hands_played=1,
            exchange_given=[["S", "10"], ["D", "J"]],
            exchange_received=[["H", "Q"], ["C", "A"]],
        )
        assert "Moon exchange" in html
        assert "Given 2 to partner" in html
        assert "Received 2 from partner" in html
        assert "♠ 10" in html
        assert "♦ J" in html
        assert "♥ Q" in html
        assert "♣ A" in html

    def test_hand_result_shows_next_hand_button(self, env):
        """Hand results should include an action to advance to the next hand."""
        html = env.get_template("partials/hand_result.html").render(
            link_uuid="abc-123",
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert 'hx-post="/play/abc-123/next-hand"' in html
        assert 'hx-target="#game-board"' in html
        assert "Next Hand" in html

    def test_animated_class_present(self, env):
        """All hand results have the animated class for slide-in."""
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=1,
            contract_type="suit",
            trump="H",
            tricks_team0=3,
            tricks_team1=7,
            points_team0=3,
            points_team1=7,
            score_human=3,
            score_ai=7,
            hands_played=1,
        )
        assert "hand-result--animated" in html


# ---------------------------------------------------------------------------
# match_result.html
# ---------------------------------------------------------------------------


class TestMatchResult:
    def test_human_wins(self, env):
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="abc-123",
            winner="human",
            score_human=55,
            score_ai=30,
            hands_played=12,
        )
        assert "You Win!" in html
        assert "55" in html
        assert "30" in html
        assert "12" in html
        assert "Play Again" in html
        assert 'hx-post="/play/abc-123/new-match"' in html

    def test_ai_wins(self, env):
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="x",
            winner="ai",
            score_human=20,
            score_ai=54,
            hands_played=8,
        )
        assert "You Lose" in html
        assert "Play Again" in html

    def test_play_again_form(self, env):
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="test-id",
            winner="human",
            score_human=52,
            score_ai=10,
            hands_played=5,
        )
        assert 'action="/play/test-id/new-match"' in html
        assert 'hx-target="#game-board"' in html


# ---------------------------------------------------------------------------
# Accessibility — ARIA attributes
# ---------------------------------------------------------------------------


class TestAccessibilityHand:
    """Verify ARIA attributes on card elements in hand.html."""

    def test_legal_card_has_aria_label(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"]],
            legal_plays=[0],
            phase="trick_play",
        )
        assert 'aria-label="Play A of Spades"' in html

    def test_illegal_card_has_aria_label(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["H", "K"]],
            legal_plays=[],
            phase="trick_play",
        )
        assert 'aria-label="K of Hearts (cannot play)"' in html

    def test_auction_card_has_aria_label(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["D", "10"]],
            legal_plays=None,
            phase="auction",
        )
        assert 'aria-label="10 of Diamonds"' in html

    def test_hand_region_has_aria_label(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["C", "J"]],
            legal_plays=None,
            phase="auction",
        )
        assert 'aria-label="Your hand"' in html

    def test_card_fan_has_group_role(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"], ["H", "K"]],
            legal_plays=None,
            phase="auction",
        )
        assert 'role="group"' in html
        assert "Cards in your hand (2)" in html


class TestAccessibilityBidPanel:
    """Verify ARIA attributes on bid panel controls."""

    def test_bid_panel_has_region_role(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert 'role="region"' in html
        assert 'aria-label="Auction panel"' in html

    def test_bid_form_has_aria_label(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert 'aria-label="Submit your bid"' in html

    def test_submit_button_has_aria_label(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert 'aria-label="Submit bid"' in html

    def test_pass_button_has_aria_label(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert 'aria-label="Pass on this bid"' in html


class TestAccessibilityTrick:
    """Verify ARIA attributes on trick area."""

    def test_trick_area_has_region(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
        )
        assert 'role="region"' in html
        assert 'aria-label="Current trick"' in html

    def test_played_card_has_aria_label(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={
                "leader": 1,
                "plays": [[1, ["H", "A"]]],
            },
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "AI Left played A of Hearts" in html

    def test_empty_slot_has_waiting_label(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "waiting to play" in html


class TestAccessibilityScore:
    """Verify ARIA attributes on score bar."""

    def test_score_bar_has_status_role(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
            hands_played=2,
            contract_type=None,
            trump=None,
            winning_bid=None,
            bidder_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            dealer_seat=0,
            phase="auction",
        )
        assert 'role="status"' in html

    def test_score_section_has_aria_label(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=15,
            score_ai=-3,
            hands_played=4,
            contract_type=None,
            trump=None,
            winning_bid=None,
            bidder_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            dealer_seat=3,
            phase="auction",
        )
        assert "Match score: You 15, AI -3" in html


class TestAccessibilityResults:
    """Verify ARIA attributes on result screens."""

    def test_hand_result_has_alert_role(self, env):
        tmpl = env.get_template("partials/hand_result.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert 'role="alert"' in html

    def test_match_result_has_alert_role(self, env):
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="x",
            winner="human",
            score_human=55,
            score_ai=30,
            hands_played=12,
        )
        assert 'role="alert"' in html

    def test_play_again_has_aria_label(self, env):
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="x",
            winner="human",
            score_human=55,
            score_ai=30,
            hands_played=12,
        )
        assert 'aria-label="Start a new match"' in html


class TestAccessibilityForms:
    """Verify ARIA attributes on setup form partials."""

    def test_nickname_form_has_region(self, env):
        tmpl = env.get_template("partials/nickname_form.html")
        html = tmpl.render(link_uuid="x")
        assert 'role="region"' in html
        assert 'aria-label="Set your nickname"' in html

    def test_model_select_has_region(self, env):
        models = [ModelStub("heuristic", "Heuristic", "Rule-based")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(link_uuid="x", nickname="Bob", models=models)
        assert 'role="region"' in html
        assert 'aria-label="Choose AI opponent"' in html

    def test_invite_code_has_sr_only_label(self, env):
        tmpl = env.get_template("partials/invite_code_form.html")
        html = tmpl.render(error=None)
        assert 'class="sr-only"' in html
        assert 'for="invite-code-input"' in html

    def test_invite_error_has_alert_role(self, env):
        tmpl = env.get_template("partials/invite_code_form.html")
        html = tmpl.render(error="Invalid code")
        assert 'role="alert"' in html
        assert "Invalid code" in html


class TestAccessibilityBaseTemplate:
    """Verify accessibility features in base.html."""

    def test_skip_link_present(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert 'class="skip-link"' in html
        assert 'href="#main-content"' in html

    def test_main_has_id_for_skip(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert 'id="main-content"' in html
        assert 'role="main"' in html

    def test_header_has_banner_role(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert 'role="banner"' in html

    def test_accessibility_css_linked(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert "/static/css/accessibility.css" in html

    def test_viewport_has_viewport_fit(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert "viewport-fit=cover" in html

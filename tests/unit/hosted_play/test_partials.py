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
    def test_renders_radio_cards(self, env):
        models = [
            ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder"),
            ModelStub("olsa", "OLSa (Easy)", "Conservative action-value bidder"),
        ]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            nickname="Alice",
            models=models,
            default_model_id="bud_bot",
        )
        assert 'value="olsa"' in html
        assert "OLSa (Easy)" in html
        assert 'value="bud_bot"' in html
        assert "Bud Bot" in html
        assert "Alice" in html
        assert 'action="/play/abc-123/select-ai"' in html
        # Radio cards instead of select dropdown
        assert 'type="radio"' in html
        assert 'name="model_id"' in html
        assert "model-card" in html
        # Bud Bot should be pre-selected as default
        assert 'value="bud_bot"' in html
        # Check that checked attribute is on the default model's radio
        # (bud_bot checked, olsa not)
        assert 'id="model-bud_bot"' in html
        assert 'id="model-olsa"' in html

    def test_default_model_checked(self, env):
        models = [
            ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder"),
            ModelStub("olsa", "OLSa (Easy)", "Conservative action-value bidder"),
        ]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            nickname="Alice",
            models=models,
            default_model_id="bud_bot",
        )
        # The radio input spans multiple lines; extract each <input ...> block
        import re

        inputs = re.findall(r"<input[^>]+>", html, re.DOTALL)
        bud_bot_inputs = [i for i in inputs if 'value="bud_bot"' in i]
        olsa_inputs = [i for i in inputs if 'value="olsa"' in i]
        assert len(bud_bot_inputs) == 1
        assert "checked" in bud_bot_inputs[0]
        assert len(olsa_inputs) == 1
        assert "checked" not in olsa_inputs[0]

    def test_renders_single_model(self, env):
        models = [ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="x",
            nickname="Bob",
            models=models,
            default_model_id="bud_bot",
        )
        assert 'value="bud_bot"' in html
        assert "Start Match" in html
        assert 'type="radio"' in html

    def test_shows_match_info(self, env):
        models = [ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="x",
            nickname="Bob",
            models=models,
            default_model_id="bud_bot",
        )
        assert "6–12 hands" in html
        assert "match-info" in html

    def test_model_descriptions_shown(self, env):
        models = [
            ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder"),
            ModelStub("olsa", "OLSa (Easy)", "Conservative action-value bidder"),
        ]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            nickname="Alice",
            models=models,
            default_model_id="bud_bot",
        )
        assert "Gradient-boosted bidder" in html
        assert "Conservative action-value bidder" in html
        assert "model-card-desc" in html
        assert "model-card-name" in html


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

    def test_moon_bid_label_uses_20_points(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert "Moon (20)" in html

    def test_loner_bid_label_uses_40_points(self, env):
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
        )
        assert "Loner (40)" in html

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
        # Legal cards appear in the shared legal play flow
        assert 'id="card-play-form"' in html
        assert 'id="selected-card-index"' in html
        assert 'id="card-play-submit"' in html
        assert 'data-card-index="0"' in html
        assert 'data-card-index="2"' in html
        assert 'name="card_index" value=""' in html
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
        # card_index=1 should NOT be a selected legal-card payload in this phase
        assert 'data-card-index="1"' not in html

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

    def test_play_form_hidden_when_waiting_for_next(self, env):
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=8,
            human_hand=[["S", "A"], ["H", "K"]],
            legal_plays=None,
            phase="trick_play",
        )
        assert 'id="card-play-form"' not in html
        assert "Play card" not in html


# ---------------------------------------------------------------------------
# trick.html
# ---------------------------------------------------------------------------


class TestTrick:
    def test_renders_empty_trick(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            dealer_seat=0,
            bidder_seat=0,
            current_seat=0,
            sitting_out_seat=None,
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
            dealer_seat=1,
            bidder_seat=2,
            current_seat=3,
            sitting_out_seat=None,
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
            completed_tricks=[
                {"plays": [], "winner": 0},
                {"plays": [], "winner": 1},
                {"plays": [], "winner": 2},
            ],
            dealer_seat=2,
            bidder_seat=2,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=2,
            tricks_team1=1,
        )
        assert "Trick 4 of 10" in html

    def test_no_current_trick(self, env):
        """When current_trick is None (e.g., hand complete)."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {"plays": [], "winner": 0},
                {"plays": [], "winner": 1},
                {"plays": [], "winner": 2},
                {"plays": [], "winner": 3},
                {"plays": [], "winner": 0},
            ],
            dealer_seat=3,
            bidder_seat=3,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=3,
            tricks_team1=2,
        )
        assert "trick-area" in html

    def test_completed_trick_replaces_current_trick_when_paused(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {
                    "plays": [[1, ["D", "A"]], [2, ["S", "K"]], [3, ["H", "Q"]]],
                    "winner": 2,
                },
            ],
            dealer_seat=1,
            bidder_seat=2,
            current_seat=3,
            sitting_out_seat=None,
            tricks_team0=4,
            tricks_team1=1,
        )
        assert "Trick 1 of 10 complete" in html
        assert "AI Left" in html
        assert "AI Partner" in html
        assert "AI Right" in html
        assert "\u2666" in html  # ♦
        assert "\u2660" in html  # ♠
        assert "AI Partner" in html
        assert "won" in html
        assert "Last Trick" not in html

    def test_markers_for_dealer_turn_declarer_and_sitout(self, env):
        """Markers render for dealer/turn/declarer/sitting out states."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 3, "plays": [[3, ["C", "10"]]]},
            completed_tricks=[],
            dealer_seat=1,
            bidder_seat=2,
            current_seat=1,
            sitting_out_seat=0,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "seat-marker--dealer" in html
        assert "seat-marker--turn" in html
        assert "seat-marker--declarer" in html
        assert "seat-marker--sitting-out" in html
        assert 'title="Dealer"' in html
        assert 'title="Current turn"' in html
        assert 'title="Declarer"' in html
        assert 'title="Sitting out"' in html

    def test_leader_marker_shown_for_trick_leader(self, env):
        """Leader seat gets an 'L' marker during the current trick."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 1, "plays": [[1, ["H", "A"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=2,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "seat-marker--leader" in html
        assert 'title="Lead"' in html

    def test_leader_marker_shown_for_completed_trick(self, env):
        """Leader marker renders when showing a completed trick (no current)."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {"leader": 2, "plays": [[2, ["S", "K"]]], "winner": 2},
            ],
            dealer_seat=0,
            bidder_seat=1,
            current_seat=3,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=1,
        )
        assert "seat-marker--leader" in html
        assert 'title="Lead"' in html

    def test_lead_suit_displayed(self, env):
        """Lead suit symbol shown next to the trick heading."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": [[0, ["H", "A"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "lead-suit" in html
        assert "\u2665" in html  # ♥

    def test_lead_suit_not_shown_when_no_plays(self, env):
        """Lead suit indicator not present when trick has no plays yet."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "lead-suit" not in html


# ---------------------------------------------------------------------------
# game_controls.html
# ---------------------------------------------------------------------------


class TestGameControls:
    def test_game_controls_render_help(self, env):
        tmpl = env.get_template("partials/game_controls.html")
        html = tmpl.render()
        assert "Help: Bid Euchre Rules" in html
        assert "double deck" in html
        assert "40-card" in html
        assert "Bowers" in html
        assert "Moon and loner" in html
        assert "High/Low" in html
        assert "+52 or -52" in html

    def test_game_controls_legend_icons(self, env):
        """Help drawer includes an icon/indicator legend."""
        tmpl = env.get_template("partials/game_controls.html")
        html = tmpl.render()
        assert "Icons &amp; Indicators" in html
        # Each seat marker variant is present
        assert "seat-marker--dealer" in html
        assert "seat-marker--declarer" in html
        assert "seat-marker--leader" in html
        assert "seat-marker--turn" in html
        assert "seat-marker--sitting-out" in html
        # Green glow swatch
        assert "help-legend__swatch--legal" in html
        # Descriptions
        assert "Dealer" in html
        assert "Declarer" in html
        assert "Sitting out" in html
        assert "legal play" in html


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

    def test_next_hand_button_posts_to_next_hand(self, env):
        """Hand results include a Next Hand control that posts to the route."""
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
        assert 'action="/play/abc-123/next-hand"' in html
        assert 'hx-post="/play/abc-123/next-hand"' in html
        assert "Next Hand" in html

    def test_moon_exchange_summary_is_visible(self, env):
        """Moon hands render exchange-given/received card summary."""
        html = env.get_template("partials/hand_result.html").render(
            link_uuid="abc-123",
            winning_bid=10,
            bidder_seat=1,
            contract_type="suit",
            trump="H",
            bid_type="moon",
            tricks_team0=6,
            tricks_team1=4,
            points_team0=10,
            points_team1=0,
            score_human=10,
            score_ai=0,
            hands_played=1,
            exchange_given=[["S", "A"], ["H", "K"]],
            exchange_received=[["C", "J"], ["D", "9"]],
        )
        assert "Moon Exchange" in html
        assert "AI Left" in html
        assert "AI Right" in html
        assert "♠A" in html
        assert "♥K" in html
        assert "♣J" in html
        assert "♦9" in html

    @pytest.mark.parametrize(
        "seat_val,expected_label",
        [("0", "You"), ("1", "AI Left"), ("2", "AI Partner"), ("3", "AI Right")],
        ids=["str_seat0", "str_seat1", "str_seat2", "str_seat3"],
    )
    def test_string_bidder_seat_coerced_to_label(self, env, seat_val, expected_label):
        """String bidder_seat values are coerced to int for label lookup (#1928)."""
        html = env.get_template("partials/hand_result.html").render(
            winning_bid=6,
            bidder_seat=seat_val,
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
        assert expected_label in html
        assert f"Seat {seat_val}" not in html

    @pytest.mark.parametrize("seat", [0, 1, 2, 3])
    def test_int_bidder_seat_still_works(self, env, seat):
        """Int bidder_seat values continue to resolve to correct labels (#1928)."""
        expected = {0: "You", 1: "AI Left", 2: "AI Partner", 3: "AI Right"}
        html = env.get_template("partials/hand_result.html").render(
            winning_bid=6,
            bidder_seat=seat,
            contract_type="suit",
            trump="H",
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert expected[seat] in html
        assert f"Seat {seat}" not in html

    def test_trick_history_shown_with_completed_tricks(self, env):
        """Hand result includes a collapsible trick-by-trick game log (#2006)."""
        tricks = [
            {
                "leader": 0,
                "plays": [
                    [0, ["S", "A"]],
                    [1, ["S", "K"]],
                    [2, ["S", "Q"]],
                    [3, ["S", "J"]],
                ],
                "winner": 0,
            },
            {
                "leader": 0,
                "plays": [
                    [0, ["H", "A"]],
                    [1, ["H", "K"]],
                    [2, ["H", "Q"]],
                    [3, ["H", "J"]],
                ],
                "winner": 0,
            },
        ]
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
            completed_tricks=tricks,
        )
        # The trick history details element should be present
        assert "trick-history" in html
        assert "Cards Played" in html
        # Card values rendered
        assert "A" in html
        assert "K" in html

    def test_trick_history_absent_without_tricks(self, env):
        """Hand result omits trick history when no tricks available (#2006)."""
        html = env.get_template("partials/hand_result.html").render(
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            tricks_team0=0,
            tricks_team1=0,
            points_team0=0,
            points_team1=0,
            score_human=0,
            score_ai=0,
            hands_played=1,
            completed_tricks=[],
        )
        # With empty completed_tricks, the trick-history section is not rendered
        assert "trick-history" not in html

    def test_trick_history_defaults_gracefully(self, env):
        """Hand result renders without completed_tricks in context (#2006)."""
        html = env.get_template("partials/hand_result.html").render(
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
        # Should render without error even when completed_tricks is not provided
        assert "Made it!" in html
        assert "trick-history" not in html

    def test_trick_history_wrapper_has_class(self, env):
        """The trick log wrapper uses the hand-result__trick-log class (#2006)."""
        tricks = [
            {
                "leader": 1,
                "plays": [
                    [1, ["D", "10"]],
                    [2, ["D", "J"]],
                    [3, ["D", "Q"]],
                    [0, ["D", "K"]],
                ],
                "winner": 0,
            },
        ]
        html = env.get_template("partials/hand_result.html").render(
            link_uuid="abc-123",
            winning_bid=5,
            bidder_seat=1,
            contract_type="suit",
            trump="D",
            tricks_team0=6,
            tricks_team1=4,
            points_team0=6,
            points_team1=4,
            score_human=6,
            score_ai=4,
            hands_played=1,
            completed_tricks=tricks,
        )
        assert "hand-result__trick-log" in html


# ---------------------------------------------------------------------------
# moon_exchange.html
# ---------------------------------------------------------------------------


class TestMoonExchange:
    """Tests for the moon exchange interstitial template."""

    def test_renders_exchange_cards(self, env):
        """Exchange given/received cards are rendered."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            exchange_given=[["H", "10"], ["D", "J"]],
            exchange_received=[["S", "A"], ["C", "K"]],
            human_hand=[
                ["S", "A"],
                ["S", "K"],
                ["C", "K"],
                ["H", "Q"],
            ],
        )
        assert "Moon Exchange" in html
        assert "\u2665" in html  # hearts symbol for given card
        assert "\u2666" in html  # diamond symbol for given card
        assert "\u2660" in html  # spade for trump/received
        assert "\u2663" in html  # club for received
        assert "Start Trick Play" in html
        assert 'hx-post="/play/abc-123/next"' in html

    def test_shows_mooner_label(self, env):
        """Mooner seat label is displayed."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=1,
            contract_type="suit",
            trump="H",
            exchange_given=[["S", "10"], ["D", "J"]],
            exchange_received=[["H", "A"], ["C", "K"]],
            human_hand=[],
        )
        assert "AI Left" in html
        assert "AI Right" in html  # partner of seat 1

    def test_shows_contract_info(self, env):
        """Trump suit is displayed in subtitle."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="suit",
            trump="H",
            exchange_given=[["S", "10"]],
            exchange_received=[["H", "A"]],
            human_hand=[],
        )
        assert "\u2665" in html  # hearts symbol

    def test_high_contract_label(self, env):
        """High contract renders 'High' label."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="high",
            trump=None,
            exchange_given=[["S", "10"]],
            exchange_received=[["H", "A"]],
            human_hand=[],
        )
        assert "High" in html

    def test_empty_exchange_graceful(self, env):
        """Template handles empty exchange lists gracefully."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            exchange_given=[],
            exchange_received=[],
            human_hand=[],
        )
        assert "Moon Exchange" in html
        assert "Start Trick Play" in html


# ---------------------------------------------------------------------------
# moon_exchange_select.html — interactive card selection
# ---------------------------------------------------------------------------


class TestMoonExchangeSelect:
    """Tests for the interactive moon exchange card selection template."""

    def test_renders_selectable_cards(self, env):
        """Human hand rendered as selectable buttons."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            human_hand=[["S", "A"], ["H", "K"], ["D", "Q"]],
            exchange_prompt="Choose 2 cards to give to your partner",
            is_mooner=True,
        )
        assert "Moon Exchange" in html
        assert "Choose 2 cards" in html
        assert 'data-exchange-index="0"' in html
        assert 'data-exchange-index="1"' in html
        assert 'data-exchange-index="2"' in html
        assert "Confirm Exchange" in html
        assert 'action="/play/abc-123/exchange"' in html

    def test_partner_prompt(self, env):
        """Partner sees correct prompt text."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=2,
            contract_type="suit",
            trump="H",
            human_hand=[["H", "J"]],
            exchange_prompt="Choose 2 cards to give to the mooner",
            is_mooner=False,
        )
        assert "Choose 2 cards to give to the mooner" in html
        assert "AI Partner" in html  # mooner label for seat 2

    def test_submit_button_disabled_by_default(self, env):
        """Submit button starts disabled."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            human_hand=[["S", "A"]],
            exchange_prompt="Choose 2 cards",
            is_mooner=True,
        )
        assert "disabled" in html

    def test_form_targets_exchange_endpoint(self, env):
        """Form submits to /play/<uuid>/exchange."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            bidder_seat=0,
            contract_type="high",
            trump=None,
            human_hand=[["S", "A"], ["H", "K"]],
            exchange_prompt="Choose 2 cards",
            is_mooner=True,
        )
        assert 'hx-post="/play/test-uuid/exchange"' in html
        assert 'name="card_index_0"' in html
        assert 'name="card_index_1"' in html


# ---------------------------------------------------------------------------
# trick.html — winning card display
# ---------------------------------------------------------------------------


class TestTrickWinnerCard:
    """Verify the trick-winner paragraph shows the winning card."""

    def test_winning_card_shown(self, env):
        """Trick winner paragraph includes the winning card."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {
                    "plays": [
                        [1, ["D", "A"]],
                        [2, ["S", "K"]],
                        [3, ["H", "Q"]],
                    ],
                    "winner": 1,
                    "winning_card": ["D", "A"],
                },
            ],
            dealer_seat=0,
            bidder_seat=1,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=1,
        )
        assert "AI Left" in html
        assert "won" in html
        assert "with" in html
        assert "\u2666" in html  # diamond symbol
        assert "A" in html  # rank

    def test_no_winning_card_graceful(self, env):
        """Trick winner paragraph without winning_card is still valid."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {
                    "plays": [
                        [0, ["S", "A"]],
                        [1, ["S", "K"]],
                    ],
                    "winner": 0,
                    # No winning_card key — backward compat
                },
            ],
            dealer_seat=0,
            bidder_seat=0,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=1,
            tricks_team1=0,
        )
        assert "You" in html
        assert "won" in html
        # No "with" since winning_card is absent
        assert "with" not in html

    def test_human_winner_shows_card(self, env):
        """When human wins, 'You won with' is rendered."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick=None,
            completed_tricks=[
                {
                    "plays": [
                        [0, ["S", "A"]],
                        [1, ["S", "K"]],
                        [2, ["H", "Q"]],
                        [3, ["D", "J"]],
                    ],
                    "winner": 0,
                    "winning_card": ["S", "A"],
                },
            ],
            dealer_seat=1,
            bidder_seat=0,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=1,
            tricks_team1=0,
        )
        assert "You" in html
        assert "won" in html
        assert "with" in html
        assert "\u2660" in html  # spade symbol
        assert "A" in html


# ---------------------------------------------------------------------------
# game_board.html — seat-0 declarer regression (issue #1913)
# ---------------------------------------------------------------------------


class TestGameBoardSeatZeroRegression:
    """Regression: bidder_seat=0 must not be coerced to -1 by default filter.

    The old ``| default(-1, true)`` treated 0 as falsy, causing
    ``hand_result.html`` to assign the wrong declarer team when the human
    (seat 0) bid and was set.  See issue #1913.
    """

    def test_hand_result_via_game_board_seat0_set(self, env):
        """Human (seat 0) bid and got set — banner must say 'Set!'."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="hand_result",
            link_uuid="test-uuid",
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            bid_type="regular",
            dealer_seat=3,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=4,
            tricks_team1=6,
            points_team0=-6,
            points_team1=6,
            score_human=-6,
            score_ai=6,
            hands_played=1,
        )
        assert "Set!" in html
        # Verify human is identified as the bidder
        assert "You" in html
        # Should NOT say "Made it!"
        assert "Made it!" not in html

    def test_hand_result_via_game_board_seat0_made(self, env):
        """Human (seat 0) bid and made — banner must say 'Made it!'."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="hand_result",
            link_uuid="test-uuid",
            winning_bid=6,
            bidder_seat=0,
            contract_type="suit",
            trump="H",
            bid_type="regular",
            dealer_seat=3,
            current_seat=0,
            sitting_out_seat=None,
            tricks_team0=7,
            tricks_team1=3,
            points_team0=7,
            points_team1=3,
            score_human=7,
            score_ai=3,
            hands_played=1,
        )
        assert "Made it!" in html
        assert "You" in html

    def test_dealer_seat_zero_preserved(self, env):
        """dealer_seat=0 must not be coerced to -1."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="trick_play",
            link_uuid="test-uuid",
            dealer_seat=0,
            bidder_seat=1,
            current_seat=2,
            sitting_out_seat=None,
            current_trick={"leader": 1, "plays": [[1, ["H", "K"]]]},
            completed_tricks=[],
            human_hand=[["S", "A"], ["H", "Q"]],
            auction=[],
            contract_type="suit",
            trump="H",
            bid_type="regular",
            winning_bid=5,
            current_high_bid=5,
            tricks_team0=0,
            tricks_team1=0,
            score_human=0,
            score_ai=0,
            hands_played=0,
            legal_plays=None,
            opp_left_count=10,
            partner_count=10,
            opp_right_count=10,
            show_next=False,
            next_reason=None,
            show_bid_panel=False,
            action_rail=[],
        )
        # The human (seat 0) should show the dealer marker
        assert "seat-marker--dealer" in html

    def test_compact_ai_badges_rendered(self, env):
        """Compact mobile badge row renders with correct counts and markers."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="trick_play",
            link_uuid="test-uuid",
            dealer_seat=1,
            bidder_seat=2,
            current_seat=3,
            sitting_out_seat=None,
            current_trick={"leader": 1, "plays": [[1, ["H", "K"]]]},
            completed_tricks=[],
            human_hand=[["S", "A"], ["H", "Q"]],
            auction=[],
            contract_type="suit",
            trump="H",
            bid_type="regular",
            winning_bid=5,
            current_high_bid=5,
            tricks_team0=0,
            tricks_team1=0,
            score_human=0,
            score_ai=0,
            hands_played=0,
            legal_plays=None,
            opp_left_count=8,
            partner_count=7,
            opp_right_count=9,
            show_next=False,
            next_reason=None,
            show_bid_panel=False,
            action_rail=[],
        )
        # Compact badge container present
        assert 'class="ai-hands-compact"' in html
        # Badges with correct card counts
        assert "L:8" in html
        assert "P:7" in html
        assert "R:9" in html
        # Seat markers present inside compact badges
        # dealer at seat 1 → L badge; declarer at seat 2 → P badge; turn at seat 3 → R badge
        assert "ai-badge" in html

    def test_compact_badges_auction_phase(self, env):
        """Compact badges also render during auction phase."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="auction",
            link_uuid="test-uuid",
            dealer_seat=3,
            bidder_seat=-1,
            current_seat=0,
            sitting_out_seat=None,
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            human_hand=[["S", "A"]],
            auction=[],
            contract_type=None,
            trump=None,
            bid_type=None,
            winning_bid=0,
            current_high_bid=0,
            tricks_team0=0,
            tricks_team1=0,
            score_human=0,
            score_ai=0,
            hands_played=0,
            legal_plays=None,
            opp_left_count=10,
            partner_count=10,
            opp_right_count=10,
            show_next=False,
            next_reason=None,
            show_bid_panel=True,
            turn_number=0,
            action_rail=[],
        )
        assert 'class="ai-hands-compact"' in html
        assert "L:10" in html
        assert "P:10" in html
        assert "R:10" in html


# ---------------------------------------------------------------------------
# contract_bar.html — sticky contract info bar during trick play
# ---------------------------------------------------------------------------


class TestContractBar:
    """Verify the contract bar partial renders correctly for all contract types."""

    def test_suit_contract_shows_trump_symbol(self, env):
        """Suit contract shows bid level and trump suit symbol."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=1,
            bid_type="regular",
            contract_type="suit",
            trump="H",
        )
        assert "contract-bar" in html
        assert "6" in html
        assert "\u2665" in html  # Heart symbol
        assert "AI Left" in html

    def test_high_contract(self, env):
        """High (no-trump) contract displays 'High' label."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=0,
            bid_type="regular",
            contract_type="high",
            trump=None,
        )
        assert "7" in html
        assert "High" in html
        assert "You" in html

    def test_low_contract(self, env):
        """Low (no-trump) contract displays 'Low' label."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=2,
            bid_type="regular",
            contract_type="low",
            trump=None,
        )
        assert "7" in html
        assert "Low" in html
        assert "AI Partner" in html

    def test_moon_contract(self, env):
        """Moon bid shows moon emoji and label."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=3,
            bid_type="moon",
            contract_type="suit",
            trump="S",
        )
        assert "Moon" in html
        assert "contract-bar__type--moon" in html
        assert "\u2660" in html  # Spade symbol
        assert "AI Right" in html

    def test_loner_contract(self, env):
        """Loner bid shows loner emoji and label."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=0,
            bid_type="loner",
            contract_type="suit",
            trump="D",
        )
        assert "Loner" in html
        assert "contract-bar__type--loner" in html
        assert "\u2666" in html  # Diamond symbol
        assert "You" in html

    def test_hidden_when_no_bid(self, env):
        """No output when winning_bid is None (auction not resolved)."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=None,
            bidder_seat=None,
            bid_type="regular",
            contract_type=None,
            trump=None,
        )
        assert "contract-bar" not in html

    def test_bidder_seat_zero_not_coerced(self, env):
        """bidder_seat=0 (human) must not be treated as falsy."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="C",
        )
        assert "contract-bar" in html
        assert "You" in html
        assert "\u2663" in html  # Club symbol


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
            dealer_seat=0,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
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
            dealer_seat=0,
            bidder_seat=1,
            current_seat=2,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "AI Left played A of Hearts" in html

    def test_empty_slot_has_waiting_label(self, env):
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            dealer_seat=0,
            bidder_seat=0,
            current_seat=3,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "waiting to play" in html


# ---------------------------------------------------------------------------
# action_rail.html
# ---------------------------------------------------------------------------


class TestActionRail:
    def test_action_rail_renders_events(self, env):
        tmpl = env.get_template("partials/action_rail.html")
        html = tmpl.render(
            action_rail=[
                {"kind": "auction", "text": "AI Left passed"},
                {"kind": "trick", "text": "AI Left won trick #1"},
                {"kind": "system", "text": "Hand starts"},
            ],
            action_rail_label="Action Rail",
        )
        assert 'id="action-rail"' in html
        assert "Action Rail" in html
        assert "AI Left passed" in html
        assert "AI Left won trick #1" in html
        assert "Hand starts" in html
        assert "action-rail__item--auction" in html
        assert "action-rail__item--trick" in html
        assert "action-rail__item--system" in html


class TestNextControls:
    def test_next_controls_post_to_next_route(self, env):
        tmpl = env.get_template("partials/next_controls.html")
        html = tmpl.render(
            link_uuid="abc-123",
            next_reason="Reveal the next auction action.",
        )
        assert 'action="/play/abc-123/next"' in html
        assert 'hx-post="/play/abc-123/next"' in html
        assert "Reveal the next auction action." in html
        assert "Next" in html


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
        models = [ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="x",
            nickname="Bob",
            models=models,
            default_model_id="bud_bot",
        )
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

    def test_safe_area_css_present(self, env):
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert "safe-area-inset-top" in html
        assert "safe-area-inset-right" in html
        assert "safe-area-inset-bottom" in html
        assert "safe-area-inset-left" in html


class TestGameTemplateAccessibility:
    """Verify accessibility-sensitive behavior in the full-page game template."""

    def test_mobile_ai_counts_remain_in_accessibility_tree(self, env):
        tmpl = env.get_template("game.html")
        html = tmpl.render(
            phase="auction",
            link_uuid="abc-123",
            opp_left_count=10,
            partner_count=10,
            opp_right_count=10,
            current_trick=None,
            completed_tricks=[],
            tricks_team0=0,
            tricks_team1=0,
            human_hand=[["S", "A"]],
            legal_plays=None,
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=0,
            score_human=0,
            score_ai=0,
            hands_played=0,
            contract_type=None,
            trump=None,
            winning_bid=None,
            bidder_seat=None,
        )
        assert 'class="ai-card-count" aria-hidden="true"' not in html
        assert "AI Left (10)" in html
        assert "Partner (10)" in html
        assert "AI Right (10)" in html


# ---------------------------------------------------------------------------
# trick_history.html
# ---------------------------------------------------------------------------


class TestTrickHistory:
    """Tests for the collapsible trick history partial."""

    @pytest.fixture()
    def completed_tricks(self):
        """Two completed tricks for testing."""
        return [
            {
                "leader": 0,
                "plays": [
                    [0, ["S", "A"]],
                    [1, ["S", "K"]],
                    [2, ["S", "Q"]],
                    [3, ["S", "T"]],
                ],
                "winner": 0,
            },
            {
                "leader": 0,
                "plays": [
                    [0, ["H", "J"]],
                    [1, ["H", "A"]],
                    [2, ["H", "K"]],
                    [3, ["H", "Q"]],
                ],
                "winner": 1,
            },
        ]

    def test_renders_empty_when_no_tricks(self, env):
        """No output when completed_tricks is empty."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(completed_tricks=[], tricks_team0=0, tricks_team1=0)
        assert "trick-history" not in html

    def test_renders_details_element(self, env, completed_tricks):
        """Renders a <details> element with correct id."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert 'id="trick-history"' in html
        assert "Cards Played (2/10)" in html

    def test_shows_card_values(self, env, completed_tricks):
        """Card values appear in the history table."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        # Suit symbols and ranks should appear
        assert "\u2660" in html  # ♠
        assert "\u2665" in html  # ♥
        assert "A" in html
        assert "K" in html

    def test_shows_trick_numbers(self, env, completed_tricks):
        """Each trick row has its number."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        # Trick numbers appear in cells
        assert "trick-history__cell--num" in html

    def test_winner_cell_highlighted(self, env, completed_tricks):
        """Winner's card cell gets the winner class."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert "trick-history__cell--winner" in html

    def test_leader_cell_marked(self, env, completed_tricks):
        """Leader's card cell gets the leader class."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert "trick-history__cell--leader" in html

    def test_won_column_shows_seat_label(self, env, completed_tricks):
        """Won column shows human-readable seat labels."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert "You" in html  # Trick 1 won by seat 0
        assert "Left" in html  # Trick 2 won by seat 1

    def test_has_table_headers(self, env, completed_tricks):
        """Table has column headers for seat labels."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert "Partner" in html
        assert "Right" in html
        assert "Won" in html

    def test_sitting_out_seat_shows_dash(self, env):
        """When a seat is sitting out (loner), its cell shows a dash."""
        tricks = [
            {
                "leader": 0,
                "plays": [
                    [0, ["H", "A"]],
                    [1, ["H", "K"]],
                    [3, ["H", "Q"]],
                ],
                "winner": 0,
            },
        ]
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(completed_tricks=tricks, tricks_team0=1, tricks_team1=0)
        assert "trick-history__absent" in html

    def test_has_aria_attributes(self, env, completed_tricks):
        """Trick history has accessibility attributes."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert 'role="region"' in html
        assert 'aria-label="Cards played history"' in html

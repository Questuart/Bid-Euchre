"""Unit tests for Jinja2 template partials in web/templates/partials/.

Validates that each partial renders correctly with representative context
data matching the visible state contract from MatchEngine.get_visible_state().
"""

from __future__ import annotations

import os

import jinja2
import pytest

from web.template_filters import display_rank, effective_suit, is_bower

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
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    environment.filters["display_rank"] = display_rank
    environment.filters["effective_suit"] = effective_suit
    environment.filters["is_bower"] = is_bower
    return environment


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

    def test_quick_start_guide_shown(self, env):
        models = [ModelStub("bud_bot", "Bud Bot", "Gradient-boosted bidder")]
        tmpl = env.get_template("partials/model_select.html")
        html = tmpl.render(
            link_uuid="abc-123",
            nickname="Alice",
            models=models,
            default_model_id="bud_bot",
        )
        # Quick-start guide was removed (#2288.8) — model select shows
        # only the AI picker now; the Help / Guide tab serves this purpose.
        assert "quick-start-guide" not in html


# ---------------------------------------------------------------------------
# guide.html
# ---------------------------------------------------------------------------


class TestGuideTemplate:
    def test_renders_title(self, env):
        tmpl = env.get_template("guide.html")
        html = tmpl.render(
            link_uuid="abc-123",
            current_page="guide",
            nickname="Alice",
        )
        assert "How to Play" in html

    def test_contains_all_sections(self, env):
        tmpl = env.get_template("guide.html")
        html = tmpl.render(
            link_uuid="abc-123",
            current_page="guide",
            nickname="Alice",
        )
        assert "Quick Start" in html
        assert "The Basics" in html
        assert "Bidding" in html
        assert "Card Play" in html
        assert "Scoring" in html
        assert "Tips" in html
        assert "Basic Strategies" in html

    def test_icon_legend_removed(self, env):
        """Icons & Indicators section was removed (icons removed from gameplay)."""
        tmpl = env.get_template("guide.html")
        html = tmpl.render(
            link_uuid="abc-123",
            current_page="guide",
            nickname="Alice",
        )
        assert "Icons" not in html
        assert "icon-table" not in html

    def test_back_link_uses_link_uuid(self, env):
        tmpl = env.get_template("guide.html")
        html = tmpl.render(
            link_uuid="my-uuid",
            current_page="guide",
            nickname="Bob",
        )
        assert "/play/my-uuid" in html
        assert "Back to Game" in html

    def test_renders_without_link_uuid(self, env):
        """Guide renders without back link when link_uuid is not set."""
        tmpl = env.get_template("guide.html")
        html = tmpl.render(current_page="guide", nickname="Bob")
        assert "How to Play" in html
        assert "Back to Game" not in html


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
        # Should have bid levels 6-10 (first may have 'selected' attr)
        for n in range(6, 11):
            assert f'value="{n}"' in bid_options
        # Pass is always available
        assert "Pass" in bid_options

    def test_default_selection_is_next_bid(self, env):
        """Bid selector defaults to next possible bid, not pass (#2310)."""
        import re

        tmpl = env.get_template("partials/bid_panel.html")
        # current_high_bid=5 → first legal bid is 6, should be selected
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=5,
            dealer_seat=3,
        )
        bid_select = re.search(
            r'<select id="bid-level"[^>]*>(.*?)</select>', html, re.DOTALL
        )
        assert bid_select is not None
        bid_options = bid_select.group(1)
        assert 'value="6" selected' in bid_options
        assert 'value="7" selected' not in bid_options

    def test_default_selection_first_bid_when_no_bids(self, env):
        """When no bids yet (current_high_bid=0), bid 1 is selected."""
        import re

        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=3,
        )
        bid_select = re.search(
            r'<select id="bid-level"[^>]*>(.*?)</select>', html, re.DOTALL
        )
        assert bid_select is not None
        bid_options = bid_select.group(1)
        assert 'value="1" selected' in bid_options

    def test_default_selection_pass_when_all_bids_exhausted(self, env):
        """When current_high_bid=10, no numeric bids available; pass is default."""
        import re

        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            auction=[],
            current_high_bid=10,
            dealer_seat=3,
        )
        bid_select = re.search(
            r'<select id="bid-level"[^>]*>(.*?)</select>', html, re.DOTALL
        )
        assert bid_select is not None
        bid_options = bid_select.group(1)
        # No selected attribute on any option → browser defaults to first (Pass)
        assert "selected" not in bid_options

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

    def test_card_play_form_has_timeout(self, env):
        """Card play form has hx-timeout for retry on stalled requests."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="abc-123",
            turn_number=8,
            human_hand=[["S", "A"], ["H", "K"]],
            legal_plays=[0, 1],
            phase="trick_play",
        )
        assert 'hx-timeout="15000"' in html

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
        assert "Slim" in html
        assert "Ace" in html
        assert "Deuce" in html
        assert "\u2666" in html  # ♦
        assert "\u2660" in html  # ♠
        assert "Ace" in html
        assert "won" in html
        assert "Last Trick" not in html

    def test_markers_for_dealer_turn_declarer_and_sitout(self, env):
        """Phase-dependent markers: only Leader and Sitting Out in trick area.

        Dealer/turn/declarer markers removed from trick area per #2200 UI cleanup.
        Dealer shown on compass seats during auction only; declarer in contract bar.
        """
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 3, "plays": [[3, ["C", "10"]]]},
            completed_tricks=[],
            dealer_seat=1,
            bidder_seat=2,
            current_seat=1,
            sitting_out_seat=0,
            phase="trick_play",
            tricks_team0=0,
            tricks_team1=0,
        )
        # Leader and Sitting Out are shown
        assert "seat-marker--leader" in html
        assert 'title="Leader"' in html
        assert "seat-marker--sitting-out" in html
        assert 'title="Sitting out"' in html
        # Dealer, turn, and declarer markers removed from trick area
        assert "seat-marker--dealer" not in html
        assert "seat-marker--turn" not in html
        assert "seat-marker--declarer" not in html

    def test_leader_marker_shown_for_trick_leader(self, env):
        """Leader seat gets a 'Leader' word label during trick play."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 1, "plays": [[1, ["H", "A"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=2,
            sitting_out_seat=None,
            phase="trick_play",
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "seat-marker--leader" in html
        assert 'title="Leader"' in html
        assert "Leader" in html

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
            phase="trick_play",
            tricks_team0=0,
            tricks_team1=1,
        )
        assert "seat-marker--leader" in html
        assert 'title="Leader"' in html

    def test_dealer_marker_shown_during_auction(self, env):
        """Dealer marker appears in trick area during auction phase."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            dealer_seat=1,
            bidder_seat=None,
            current_seat=0,
            sitting_out_seat=None,
            phase="auction",
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "seat-marker--dealer" in html
        assert 'title="Dealer"' in html
        assert "Dealer" in html

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

    def test_left_bower_lead_shows_trump_suit(self, env):
        """Left bower lead displays trump suit, not printed suit (#2158).

        When the left bower (J of same-color off-suit) leads in a suit
        contract, the lead-suit indicator must show the trump suit.
        Example: clubs contract, J♠ (left bower) led → shows ♣ not ♠.
        """
        tmpl = env.get_template("partials/trick.html")
        # J♠ led in a clubs contract — left bower of clubs
        html = tmpl.render(
            current_trick={"leader": 0, "plays": [[0, ["S", "J"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        assert "lead-suit" in html
        # ♣ (clubs) should appear, not ♠ (spades)
        assert "\u2663" in html  # ♣
        assert "lead-suit--clubs" in html
        assert "lead-suit--spades" not in html

    def test_right_bower_lead_shows_trump_suit(self, env):
        """Right bower lead displays trump suit (trivial — printed suit matches)."""
        tmpl = env.get_template("partials/trick.html")
        # J♣ led in a clubs contract — right bower
        html = tmpl.render(
            current_trick={"leader": 0, "plays": [[0, ["C", "J"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        assert "lead-suit--clubs" in html

    def test_non_bower_jack_lead_shows_printed_suit(self, env):
        """Non-bower J lead shows its printed suit, not trump."""
        tmpl = env.get_template("partials/trick.html")
        # J♦ led in a clubs contract — not a bower (different color)
        html = tmpl.render(
            current_trick={"leader": 0, "plays": [[0, ["D", "J"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        assert "lead-suit--diamonds" in html

    def test_lead_suit_no_contract_falls_back_to_printed(self, env):
        """Without contract info, lead suit falls back to printed suit."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={"leader": 0, "plays": [[0, ["S", "J"]]]},
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert "lead-suit--spades" in html

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
# score.html
# ---------------------------------------------------------------------------


class TestScore:
    """Score bar shows only 'Current Game Score' per #2200 UI cleanup.

    Contract, declarer, tricks info removed (shown in contract bar and trick area).
    Hand details dropdown removed per #2509 (cluttered).
    """

    def test_renders_scores(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=15,
            score_ai=-3,
        )
        assert "15" in html
        assert "-3" in html
        assert "Current Game Score" in html
        assert "Your Team:" in html
        assert "Opponent:" in html

    def test_no_hand_details_dropdown(self, env):
        """Hand details dropdown removed per #2509."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=0,
            score_ai=0,
        )
        assert "hand-details" not in html
        assert "<details" not in html
        assert "<summary" not in html
        assert "Hand Details" not in html

    def test_no_contract_info_in_score_bar(self, env):
        """Contract info removed from score bar (shown in contract bar instead)."""
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=10,
            score_ai=5,
        )
        # Contract info should NOT appear in score bar
        assert "contract-info" not in html
        assert "contract-bid-type" not in html
        assert "Declarer:" not in html
        assert "Tricks:" not in html


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
        assert "Your Team Made It!" in html
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
        assert "Your Team was Set!" in html
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
        assert "Your Team Made It!" in html
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
        assert "Opponent Made It!" in html
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
        assert "Your Team Moon Made!" in html
        assert "result--moon-made" in html
        assert "+20" in html
        assert "MOON" in html
        assert "MADE" in html
        # Should NOT show regular "Made It!" text
        assert "Made It!" not in html

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
        assert "Your Team Moon Set!" in html
        assert "result--moon-set" in html
        assert "-20" in html
        assert "SET" in html
        # Should show moon-specific banner, not plain "was Set!" alone
        assert "was Set!" not in html

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
        assert "Your Team Loner Made!" in html
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
        assert "Your Team Loner Set!" in html
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
        assert "Your Team Made It!" in html

    def test_opponent_declared_made_shows_opponent_prefix(self, env):
        """When AI team declares and makes, banner says 'Opponent Made It!' (#2439)."""
        html = env.get_template("partials/hand_result.html").render(
            winning_bid=6,
            bidder_seat=1,
            contract_type="suit",
            trump="S",
            tricks_team0=3,
            tricks_team1=7,
            points_team0=3,
            points_team1=7,
            score_human=3,
            score_ai=7,
            hands_played=1,
        )
        assert "Opponent Made It!" in html
        assert "Your Team" not in html

    def test_opponent_declared_set_shows_opponent_prefix(self, env):
        """When AI team declares and is set, banner says 'Opponent was Set!' (#2439)."""
        html = env.get_template("partials/hand_result.html").render(
            winning_bid=8,
            bidder_seat=3,
            contract_type="suit",
            trump="H",
            tricks_team0=5,
            tricks_team1=5,
            points_team0=5,
            points_team1=-8,
            score_human=5,
            score_ai=-8,
            hands_played=1,
        )
        assert "Opponent was Set!" in html
        assert "Your Team" not in html

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
        # Rank and suit are in separate spans: <span class="suit-icon ...">♠</span> 10
        assert "♠" in html
        assert ">♠</span> 10" in html
        assert ">♦</span> J" in html
        assert ">♥</span> Q" in html
        assert ">♣</span> A" in html

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
        assert "Slim" in html
        assert "Deuce" in html
        assert "♠A" in html
        assert "♥K" in html
        assert "♣J" in html
        assert "♦9" in html

    @pytest.mark.parametrize(
        "seat_val,expected_label",
        [("0", "You"), ("1", "Slim"), ("2", "Ace"), ("3", "Deuce")],
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
        expected = {0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"}
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
        assert "Your Team Made It!" in html
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
        assert "Slim" in html
        assert "Deuce" in html  # partner of seat 1

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
        assert "Ace" in html  # mooner label for seat 2

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
        assert "Slim" in html
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
        """Human (seat 0) bid and got set — banner must say 'Your Team was Set!'."""
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
        assert "Your Team was Set!" in html
        # Verify human is identified as the bidder
        assert "You" in html
        # Should NOT say "Made It!"
        assert "Made It!" not in html

    def test_hand_result_via_game_board_seat0_made(self, env):
        """Human (seat 0) bid and made — banner must say 'Your Team Made It!'."""
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
        assert "Your Team Made It!" in html
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
        # During trick play, dealer is NOT shown (only during auction)
        assert "seat-marker--dealer" not in html

    def test_dealer_seat_zero_shown_during_auction(self, env):
        """dealer_seat=0 shows 'Dealer' on human seat during auction."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="auction",
            link_uuid="test-uuid",
            dealer_seat=0,
            bidder_seat=-1,
            current_seat=0,
            sitting_out_seat=None,
            current_trick={"leader": 0, "plays": []},
            completed_tricks=[],
            human_hand=[["S", "A"], ["H", "Q"]],
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
        # During auction, dealer marker shown
        assert "seat-marker--dealer" in html
        assert "Dealer" in html

    def test_compact_ai_badges_removed(self, env):
        """Compact mobile badge row removed per #2200 UI cleanup."""
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
        # Compact badge container removed
        assert 'class="ai-hands-compact"' not in html
        assert "ai-badge" not in html

    def test_icon_legend_removed(self, env):
        """Icon legend removed per #2200 UI cleanup."""
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
            opp_left_count=10,
            partner_count=10,
            opp_right_count=10,
            show_next=False,
            next_reason=None,
            show_bid_panel=False,
            action_rail=[],
        )
        assert "icon-legend" not in html

    def test_declarer_marker_hidden_during_auction(self, env):
        """Declarer ★ markers must not appear during auction phase (#2203).

        When a player has placed a bid during the auction, bidder_seat is set
        to their seat, but the ★ Declarer marker should only render after the
        auction is complete (during trick_play).
        """
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="auction",
            link_uuid="test-uuid",
            dealer_seat=0,
            bidder_seat=2,  # seat 2 has the current high bid during auction
            current_seat=3,
            sitting_out_seat=None,
            current_trick=None,
            completed_tricks=[],
            human_hand=[["S", "A"], ["H", "Q"]],
            auction=[[1, 5], [2, 6]],
            contract_type=None,
            trump=None,
            bid_type=None,
            winning_bid=6,
            current_high_bid=6,
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
        # Declarer marker removed from compass seats per #2200 UI cleanup.
        # Declarer info now shown in contract bar only.
        assert 'title="Declarer"' not in html
        # Dealer marker SHOULD appear during auction
        assert "seat-marker--dealer" in html

    def test_declarer_marker_removed_during_trick_play(self, env):
        """Declarer ★ markers removed from compass seats per #2200.

        Declarer info is now shown in the contract bar only.
        """
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="trick_play",
            link_uuid="test-uuid",
            dealer_seat=0,
            bidder_seat=2,
            current_seat=1,
            sitting_out_seat=None,
            current_trick={"leader": 1, "plays": [[1, ["H", "K"]]]},
            completed_tricks=[],
            human_hand=[["S", "A"], ["H", "Q"]],
            auction=[],
            contract_type="suit",
            trump="H",
            bid_type="regular",
            winning_bid=6,
            current_high_bid=6,
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
        # Declarer marker removed from compass seats
        assert "seat-marker--declarer" not in html
        assert 'title="Declarer"' not in html
        # Contract bar shows declarer info instead
        assert "contract-bar" in html

    def test_trick_heading_hidden_during_auction(self, env):
        """'Trick N of 10' heading must not appear during auction (#2206).

        The trick area partial should only render during trick play, not
        during the auction phase where it would misleadingly show
        'Trick 1 of 10'.
        """
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            phase="auction",
            link_uuid="test-uuid",
            dealer_seat=3,
            bidder_seat=-1,
            current_seat=0,
            sitting_out_seat=None,
            current_trick=None,
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
        # Trick heading must NOT appear during auction
        assert "Trick 1 of 10" not in html
        assert "trick-area" not in html

    def test_trick_heading_shown_during_trick_play(self, env):
        """'Trick N of 10' heading appears normally during trick play (#2206)."""
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
        # Trick heading SHOULD appear during trick play
        assert "Trick 1 of 10" in html
        assert "trick-area" in html


# ---------------------------------------------------------------------------
# game_board.html — auction log repositioning (#2331)
# ---------------------------------------------------------------------------


class TestAuctionLogRepositioning:
    """Auction log renders inside compass-center during auction, but moves
    below the score bar (hand details) during trick play.  Issue #2331."""

    @staticmethod
    def _board_ctx(phase, **overrides):
        ctx = dict(
            phase=phase,
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
            winning_bid=6,
            current_high_bid=6,
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
            action_rail=[{"kind": "auction", "text": "Slim bid 6"}],
        )
        ctx.update(overrides)
        return ctx

    def test_auction_log_inside_compass_center_during_auction(self, env):
        """During auction, the action-rail is inside .compass-center."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            **self._board_ctx("auction", show_bid_panel=True, turn_number=0)
        )
        center_pos = html.index("compass-center")
        rail_pos = html.index('id="action-rail"')
        score_pos = html.index("score-bar")
        assert center_pos < rail_pos < score_pos

    def test_auction_log_below_score_bar_during_trick_play(self, env):
        """During trick play, the action-rail is below .score-bar (#2331)."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(**self._board_ctx("trick_play"))
        score_pos = html.index("score-bar")
        rail_pos = html.index('id="action-rail"')
        assert rail_pos > score_pos

    def test_auction_log_below_score_bar_during_redeal(self, env):
        """During redeal phase, the action-rail is below .score-bar (#2331)."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(**self._board_ctx("redeal"))
        score_pos = html.index("score-bar")
        rail_pos = html.index('id="action-rail"')
        assert rail_pos > score_pos

    def test_auction_log_not_duplicated(self, env):
        """Auction log should appear exactly once in each phase."""
        tmpl = env.get_template("partials/game_board.html")
        for phase in ("auction", "trick_play", "redeal"):
            ctx = self._board_ctx(phase)
            if phase == "auction":
                ctx["show_bid_panel"] = True
                ctx["turn_number"] = 0
            html = tmpl.render(**ctx)
            count = html.count('id="action-rail"')
            assert count == 1, f"Expected 1 action-rail in {phase}, found {count}"


# ---------------------------------------------------------------------------
# contract_bar.html — sticky contract info bar during trick play
# ---------------------------------------------------------------------------


class TestContractBar:
    """Verify the contract bar partial renders correctly for all contract types."""

    def test_suit_contract_shows_trump_symbol(self, env):
        """Suit contract shows bid level, trump symbol, and 'by Name' label."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=1,
            bid_type="regular",
            contract_type="suit",
            trump="H",
            phase="trick_play",
        )
        assert "contract-bar" in html
        assert "contract-bar--opp-team" in html
        assert "Current Contract and Trump:" in html
        assert "6" in html
        assert "\u2665" in html  # Heart symbol
        # AI declarer name wrapped in .ai-name with team color (#2346)
        assert 'class="ai-name player-name--ai">Slim</span>' in html

    def test_high_contract(self, env):
        """High (no-trump) contract by human shows 'by You'."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=0,
            bid_type="regular",
            contract_type="high",
            trump=None,
            phase="trick_play",
        )
        assert "7" in html
        assert "High" in html
        assert 'player-name--human">You</span>' in html
        assert "contract-bar--my-team" in html
        # Human name should NOT be wrapped in ai-name
        assert "ai-name" not in html
        assert "Current Contract:" in html
        assert "and Trump" not in html

    def test_low_contract(self, env):
        """Low (no-trump) contract by partner shows 'by Ace'."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=2,
            bid_type="regular",
            contract_type="low",
            trump=None,
            phase="trick_play",
        )
        assert "7" in html
        assert "Low" in html
        # Partner declarer name wrapped in .ai-name with human team color (#2346)
        assert 'class="ai-name player-name--human">Ace</span>' in html
        assert "contract-bar--my-team" in html

    def test_moon_contract(self, env):
        """Moon bid by opponent shows Moon label and 'by Deuce'."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=3,
            bid_type="moon",
            contract_type="suit",
            trump="S",
            phase="trick_play",
        )
        assert "Moon" in html
        assert "contract-bar__type--moon" in html
        assert "\u2660" in html  # Spade symbol
        # AI declarer name wrapped in .ai-name with team color (#2346)
        assert 'class="ai-name player-name--ai">Deuce</span>' in html
        assert "contract-bar--opp-team" in html

    def test_loner_contract(self, env):
        """Loner bid by human shows Loner label, 'by You'."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=10,
            bidder_seat=0,
            bid_type="loner",
            contract_type="suit",
            trump="D",
            phase="trick_play",
        )
        assert "Loner" in html
        assert "contract-bar__type--loner" in html
        assert "\u2666" in html  # Diamond symbol
        assert 'player-name--human">You</span>' in html
        assert "contract-bar--my-team" in html
        # Human name should NOT be wrapped in ai-name
        assert "ai-name" not in html

    def test_auction_in_progress_display(self, env):
        """During auction with no bid, shows 'Auction in Progress'."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=None,
            bidder_seat=None,
            bid_type="regular",
            contract_type=None,
            trump=None,
            phase="auction",
        )
        assert "contract-bar" in html
        assert "Auction:" in html
        assert "Auction in Progress" in html

    def test_auction_shows_high_bid(self, env):
        """During auction with a current high bid, shows the bid amount."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=None,
            bidder_seat=None,
            bid_type="regular",
            contract_type=None,
            trump=None,
            phase="auction",
            current_high_bid=6,
        )
        assert "High Bid: 6" in html

    def test_hidden_when_no_bid_no_phase(self, env):
        """No output when winning_bid is None and phase is not auction."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=None,
            bidder_seat=None,
            bid_type="regular",
            contract_type=None,
            trump=None,
        )
        assert "contract-bar" not in html

    def test_auction_settle_hides_contract(self, env):
        """During auction settle pause, contract/trump is hidden (#2328).

        After all bids are revealed but before the user clicks "Continue",
        winning_bid and bidder_seat are set but phase is still "auction".
        The contract bar should show the auction status, not the contract.
        """
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=6,
            bidder_seat=1,
            bid_type="regular",
            contract_type="suit",
            trump="H",
            phase="auction",
            current_high_bid=6,
            high_bidder_seat=1,
        )
        # Must NOT show the "Current Contract" display
        assert "Current Contract" not in html
        # Must show auction status instead
        assert "Auction:" in html
        assert "High Bid: 6" in html

    def test_bidder_seat_zero_not_coerced(self, env):
        """bidder_seat=0 (human) must not be treated as falsy."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="C",
            phase="trick_play",
        )
        assert "contract-bar" in html
        assert 'player-name--human">You</span>' in html
        assert "\u2663" in html  # Club symbol
        assert "contract-bar--my-team" in html

    def test_partner_declarer_label(self, env):
        """Partner (seat 2) shows 'by Ace' with human team color."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=2,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            phase="trick_play",
        )
        assert 'class="ai-name player-name--human">Ace</span>' in html
        assert "contract-bar--my-team" in html

    def test_opponent_seat1_declarer_label(self, env):
        """Left opponent (seat 1) shows 'by Slim' with AI team color."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=1,
            bid_type="regular",
            contract_type="suit",
            trump="H",
            phase="trick_play",
        )
        assert 'class="ai-name player-name--ai">Slim</span>' in html
        assert "contract-bar--opp-team" in html

    def test_opponent_seat3_declarer_label(self, env):
        """Right opponent (seat 3) shows 'by Deuce' with AI team color."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=8,
            bidder_seat=3,
            bid_type="regular",
            contract_type="suit",
            trump="C",
            phase="trick_play",
        )
        assert 'class="ai-name player-name--ai">Deuce</span>' in html
        assert "contract-bar--opp-team" in html

    def test_header_label_suit(self, env):
        """Suit contract shows 'Current Contract and Trump:' header."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=5,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="H",
            phase="trick_play",
        )
        assert "contract-bar__header" in html
        assert "Current Contract and Trump:" in html

    def test_header_label_no_trump(self, env):
        """No-trump contract shows neutral 'Current Contract:' header."""
        tmpl = env.get_template("partials/contract_bar.html")
        html = tmpl.render(
            winning_bid=7,
            bidder_seat=0,
            bid_type="regular",
            contract_type="high",
            trump=None,
            phase="trick_play",
        )
        assert "contract-bar__header" in html
        assert "Current Contract:" in html
        assert "and Trump" not in html


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
        assert "2 cards in your hand" in html


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
        assert "Slim played A of Hearts" in html

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
                {"kind": "auction", "text": "Slim passed"},
                {"kind": "result", "text": "Ace wins auction: 7 \u2665"},
                {"kind": "system", "text": "All players passed; redeal starting."},
            ],
            action_rail_label="Auction Log",
        )
        assert 'id="action-rail"' in html
        assert "Auction Log" in html
        assert "Slim passed" in html
        assert "Ace wins auction" in html
        assert "redeal starting" in html
        assert "action-rail__item--auction" in html
        assert "action-rail__item--result" in html
        assert "action-rail__item--system" in html

    def test_action_rail_no_trick_results(self, env):
        """Auction log must not display trick results (#2477)."""
        tmpl = env.get_template("partials/action_rail.html")
        # Even if trick events were somehow passed, the template renders
        # whatever it receives — the fix is in the route, not the template.
        # This test documents that trick events are no longer part of the
        # auction log data contract.
        html = tmpl.render(
            action_rail=[
                {"kind": "auction", "text": "Slim bid 6 \u2660"},
                {"kind": "result", "text": "Slim wins auction: 6 \u2660"},
            ],
            action_rail_label="Auction Log",
        )
        assert "action-rail__item--trick" not in html
        assert "won Trick" not in html

    def test_auction_log_open_during_auction(self, env):
        """Auction log <details> should be open during auction phase (#2288)."""
        tmpl = env.get_template("partials/action_rail.html")
        html = tmpl.render(
            action_rail=[{"kind": "auction", "text": "Slim bid 6"}],
            phase="auction",
        )
        # <details> has open attribute during auction
        assert "<details" in html
        assert "open" in html
        assert 'data-phase="auction"' in html

    def test_auction_log_collapsed_during_trick_play(self, env):
        """Auction log should be collapsed (no open attr) during trick play (#2288)."""
        tmpl = env.get_template("partials/action_rail.html")
        html = tmpl.render(
            action_rail=[{"kind": "auction", "text": "Slim bid 6"}],
            phase="trick_play",
        )
        assert "<details" in html
        assert 'data-phase="trick_play"' in html
        # The open attribute should NOT be present
        # Parse carefully: "open" could appear in other contexts
        import re

        details_tag = re.search(r"<details[^>]*>", html).group(0)
        assert "open" not in details_tag.split("data-phase")[0]

    def test_auction_log_shows_event_count(self, env):
        """Summary line should show item count when events exist (#2288)."""
        tmpl = env.get_template("partials/action_rail.html")
        html = tmpl.render(
            action_rail=[
                {"kind": "auction", "text": "Slim passed"},
                {"kind": "auction", "text": "Ace bid 7"},
            ],
            phase="auction",
        )
        assert "(2)" in html

    def test_auction_log_collapsible_toggle(self, env):
        """Auction log uses <details>/<summary> for collapsibility (#2288)."""
        tmpl = env.get_template("partials/action_rail.html")
        html = tmpl.render(
            action_rail=[{"kind": "auction", "text": "Test"}],
            phase="trick_play",
        )
        assert "<summary" in html
        assert "action-rail__toggle" in html
        assert "action-rail__content" in html


STATIC_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "static",
)


class TestAuctionLogJsToggle:
    """Verify game.js auction log toggle logic (#2471, #2488)."""

    @pytest.fixture()
    def game_js(self):
        path = os.path.join(STATIC_DIR, "game.js")
        with open(path) as f:
            return f.read()

    def test_restore_function_exists(self, game_js):
        assert "function restoreAuctionLogState()" in game_js

    def test_save_function_exists(self, game_js):
        assert "function saveAuctionLogState()" in game_js

    def test_auction_phase_forces_open(self, game_js):
        """During auction phase, restoreAuctionLogState must always force
        the details element open, ignoring stale sessionStorage (#2488)."""
        fn_start = game_js.index("function restoreAuctionLogState()")
        fn_block = game_js[fn_start : fn_start + 1800]
        # Must force open during auction (not just conditionally clear)
        assert "details.open = true" in fn_block
        assert "sessionStorage.removeItem(AUCTION_LOG_KEY)" in fn_block

    def test_auto_collapse_on_phase_transition(self, game_js):
        """When transitioning from auction to non-auction, the log should
        auto-collapse and save the closed state."""
        fn_start = game_js.index("function restoreAuctionLogState()")
        fn_block = game_js[fn_start : fn_start + 1800]
        assert "previousPhase === 'auction'" in fn_block
        assert "details.open = false" in fn_block

    def test_auction_log_keys_defined(self, game_js):
        assert "AUCTION_LOG_KEY" in game_js
        assert "'auctionLogOpen'" in game_js
        assert "AUCTION_LOG_PHASE_KEY" in game_js
        assert "'auctionLogPhase'" in game_js


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
        )
        assert 'role="status"' in html

    def test_score_section_has_aria_label(self, env):
        tmpl = env.get_template("partials/score.html")
        html = tmpl.render(
            score_human=15,
            score_ai=-3,
        )
        assert "Current game score: Your Team 15, Opponent -3" in html


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


class TestOgImageAbsoluteUrl:
    """Verify og:image uses app_url for absolute URL (#2058)."""

    def test_og_image_relative_without_app_url(self, env):
        """Without app_url global, og:image falls back to relative path."""
        tmpl = env.get_template("base.html")
        html = tmpl.render()
        assert "og:image" in html
        assert "/static/icons/icon-512.png" in html

    def test_og_image_absolute_with_app_url(self, env):
        """With app_url global, og:image produces an absolute URL."""
        env.globals["app_url"] = "https://bideuchre.example.com"
        try:
            tmpl = env.get_template("base.html")
            html = tmpl.render()
            assert "https://bideuchre.example.com/static/icons/icon-512.png" in html
        finally:
            env.globals.pop("app_url", None)

    def test_og_image_strips_trailing_slash(self, env):
        """app_url with trailing slash does not produce double slash."""
        env.globals["app_url"] = "https://bideuchre.example.com"
        try:
            tmpl = env.get_template("base.html")
            html = tmpl.render()
            # Should NOT contain double slash in static path
            assert "https://bideuchre.example.com//static" not in html
        finally:
            env.globals.pop("app_url", None)


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
        # Duplicate card-count lines removed; names shown once with team colors (#2346)
        assert "ai-card-count" not in html
        # AI names with team-color classes (#2346)
        assert 'player-name--ai">Slim</span>' in html
        assert 'player-name--human">Ace</span>' in html
        assert 'player-name--ai">Deuce</span>' in html


# ---------------------------------------------------------------------------
# trick_history.html
# ---------------------------------------------------------------------------


class TestBidRecap:
    """Tests for partials/bid_recap.html — auction result summary bar.

    Follow-up from PR #2017 review finding (issue #2021).
    Covers: regular suit/high/low bids, moon, loner, sitting-out seat,
    no-output guard, and seat label rendering.
    """

    def _render(self, env, **ctx):
        """Render bid_recap.html with the given context variables."""
        tmpl = env.get_template("partials/bid_recap.html")
        return tmpl.render(**ctx)

    # --- Regular bids ---

    def test_regular_suit_bid(self, env):
        """Regular suit bid shows level + suit symbol."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert "bid-recap__level" in html
        assert ">6<" in html
        # Spade symbol (♠ = &#9824; or raw unicode)
        assert "\u2660" in html
        assert "bid-recap__suit--s" in html

    def test_regular_hearts_bid(self, env):
        html = self._render(
            env,
            winning_bid=7,
            bidder_seat=1,
            bid_type="regular",
            contract_type="suit",
            trump="H",
            sitting_out_seat=None,
        )
        assert ">7<" in html
        assert "\u2665" in html  # ♥
        assert "bid-recap__suit--h" in html

    def test_regular_diamonds_bid(self, env):
        html = self._render(
            env,
            winning_bid=8,
            bidder_seat=2,
            bid_type="regular",
            contract_type="suit",
            trump="D",
            sitting_out_seat=None,
        )
        assert "\u2666" in html  # ♦

    def test_regular_clubs_bid(self, env):
        html = self._render(
            env,
            winning_bid=9,
            bidder_seat=3,
            bid_type="regular",
            contract_type="suit",
            trump="C",
            sitting_out_seat=None,
        )
        assert "\u2663" in html  # ♣

    def test_high_contract_no_trump(self, env):
        """HIGH contract shows level + 'High' text."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            contract_type="high",
            trump=None,
            sitting_out_seat=None,
        )
        assert ">6<" in html
        assert "bid-recap__no-trump" in html
        assert "High" in html

    def test_low_contract_no_trump(self, env):
        """LOW contract shows level + 'Low' text."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            contract_type="low",
            trump=None,
            sitting_out_seat=None,
        )
        assert ">6<" in html
        assert "bid-recap__no-trump" in html
        assert "Low" in html

    # --- Moon bids ---

    def test_moon_bid_with_emoji(self, env):
        """Moon bid shows moon emoji + 'Moon' text."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="moon",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert "bid-recap__type--moon" in html
        assert "Moon" in html
        # Moon emoji (🌙 = &#127769;)
        assert "&#127769;" in html
        # Moon bids should NOT show the numeric level
        assert "bid-recap__level" not in html

    def test_moon_bid_with_suit_symbol(self, env):
        """Moon bid still shows the trump suit symbol."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="moon",
            contract_type="suit",
            trump="H",
            sitting_out_seat=None,
        )
        assert "\u2665" in html  # ♥

    # --- Loner bids ---

    def test_loner_bid(self, env):
        """Loner bid shows card emoji + 'Loner' text."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="loner",
            contract_type="suit",
            trump="S",
            sitting_out_seat=2,
        )
        assert "bid-recap__type--loner" in html
        assert "Loner" in html
        # Playing card emoji (🃏 = &#127183;)
        assert "&#127183;" in html

    def test_loner_shows_sitting_out(self, env):
        """Loner bid shows which seat is sitting out."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="loner",
            contract_type="suit",
            trump="S",
            sitting_out_seat=2,
        )
        assert "bid-recap__sitting-out" in html
        assert "Ace" in html
        assert "sits out" in html

    def test_loner_sitting_out_seat_labels(self, env):
        """Sitting-out uses correct seat labels for each seat."""
        for seat, label in [
            (0, "You"),
            (1, "Slim"),
            (2, "Ace"),
            (3, "Deuce"),
        ]:
            html = self._render(
                env,
                winning_bid=10,
                bidder_seat=1,
                bid_type="loner",
                contract_type="suit",
                trump="S",
                sitting_out_seat=seat,
            )
            assert label in html

    # --- No-output guards ---

    def test_no_output_without_winning_bid(self, env):
        """No bid-recap div when winning_bid is None."""
        html = self._render(
            env,
            winning_bid=None,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert "bid-recap" not in html

    def test_no_output_without_bidder_seat(self, env):
        """No bid-recap div when bidder_seat is None."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=None,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert "bid-recap" not in html

    def test_no_sitting_out_for_regular_bid(self, env):
        """Regular bids with sitting_out_seat=None show no sits-out text."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert "bid-recap__sitting-out" not in html
        assert "sits out" not in html

    # --- Seat labels ---

    def test_seat_labels_correct(self, env):
        """Declarer label matches the seat label mapping."""
        labels = {0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"}
        for seat, expected_label in labels.items():
            html = self._render(
                env,
                winning_bid=6,
                bidder_seat=seat,
                bid_type="regular",
                contract_type="suit",
                trump="S",
                sitting_out_seat=None,
            )
            assert expected_label in html

    # --- Accessibility ---

    def test_has_role_status(self, env):
        """Bid recap bar has role=status for screen readers."""
        html = self._render(
            env,
            winning_bid=6,
            bidder_seat=0,
            bid_type="regular",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert 'role="status"' in html
        assert 'aria-label="Auction result"' in html

    def test_moon_has_aria_label(self, env):
        """Moon type span has an aria-label."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="moon",
            contract_type="suit",
            trump="S",
            sitting_out_seat=None,
        )
        assert 'aria-label="Moon bid"' in html

    def test_loner_has_aria_label(self, env):
        """Loner type span has an aria-label."""
        html = self._render(
            env,
            winning_bid=10,
            bidder_seat=0,
            bid_type="loner",
            contract_type="suit",
            trump="S",
            sitting_out_seat=2,
        )
        assert 'aria-label="Loner bid"' in html


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
        assert "Slim" in html  # Trick 2 won by seat 1

    def test_has_table_headers(self, env, completed_tricks):
        """Table has column headers for seat labels."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks, tricks_team0=1, tricks_team1=1
        )
        assert "Ace" in html
        assert "Deuce" in html
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

    def test_bower_legend_shown_for_suit_contract(self, env, completed_tricks):
        """Bower abbreviation legend appears when contract_type is 'suit' (#2288)."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks,
            tricks_team0=1,
            tricks_team1=1,
            contract_type="suit",
            trump="H",
        )
        assert "trick-history__legend" in html
        assert "RB" in html
        assert "LB" in html
        assert "Right Bower" in html
        assert "Left Bower" in html

    def test_bower_legend_hidden_for_high_contract(self, env, completed_tricks):
        """No bower legend when contract_type is 'high' (no bowers) (#2288)."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks,
            tricks_team0=1,
            tricks_team1=1,
            contract_type="high",
        )
        assert "Right Bower" not in html
        assert "Left Bower" not in html
        # Visual indicator legend is always present (#2385)
        assert "trick-history__legend--visual" in html

    def test_bower_legend_hidden_for_low_contract(self, env, completed_tricks):
        """No bower legend when contract_type is 'low' (no bowers) (#2288)."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks,
            tricks_team0=1,
            tricks_team1=1,
            contract_type="low",
        )
        assert "Right Bower" not in html
        assert "Left Bower" not in html
        # Visual indicator legend is always present (#2385)
        assert "trick-history__legend--visual" in html

    def test_bower_legend_hidden_when_no_contract(self, env, completed_tricks):
        """No bower legend when contract_type is unset (#2288)."""
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(
            completed_tricks=completed_tricks,
            tricks_team0=1,
            tricks_team1=1,
        )
        assert "Right Bower" not in html
        assert "Left Bower" not in html
        # Visual indicator legend is always present (#2385)
        assert "trick-history__legend--visual" in html

    def test_visual_legend_always_shown(self, env, completed_tricks):
        """Visual indicator legend (led/won) always appears (#2385)."""
        tmpl = env.get_template("partials/trick_history.html")
        for ctype in ["suit", "high", "low", None]:
            ctx = dict(
                completed_tricks=completed_tricks,
                tricks_team0=1,
                tricks_team1=1,
            )
            if ctype is not None:
                ctx["contract_type"] = ctype
            html = tmpl.render(**ctx)
            assert (
                "trick-history__legend--visual" in html
            ), f"Visual legend missing for contract_type={ctype!r}"
            assert "led trick" in html
            assert "won trick" in html
            assert "legend-item--leader" in html
            assert "legend-item--winner" in html


# ---------------------------------------------------------------------------
# Bower suit display — show printed suit + RB/LB labels (#2261)
# ---------------------------------------------------------------------------


class TestBowerDisplay:
    """Verify bower cards show original printed suit + RB/LB badge.

    Bowers must display their printed (physical) suit with an RB (right bower)
    or LB (left bower) badge.  The effective suit should NOT be used for display.
    Refs: #2261, #2204, #2158, #2180.
    """

    # -- trick.html: played card in trick area --

    def test_left_bower_played_card_shows_printed_suit(self, env):
        """Left bower in trick card_slot shows printed suit, not trump suit (#2261)."""
        tmpl = env.get_template("partials/trick.html")
        # J♠ played in a clubs contract — left bower of clubs
        html = tmpl.render(
            current_trick={
                "leader": 1,
                "plays": [[1, ["H", "A"]], [0, ["S", "J"]]],
            },
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=2,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        # The played card should show spades (♠) — its printed suit
        assert "card--spades" in html
        assert "card--bower" in html
        assert ">LB<" in html  # left bower badge

    def test_right_bower_played_card_shows_printed_suit(self, env):
        """Right bower in trick card_slot shows printed suit (same as trump)."""
        tmpl = env.get_template("partials/trick.html")
        # J♣ played in a clubs contract — right bower
        html = tmpl.render(
            current_trick={
                "leader": 0,
                "plays": [[0, ["C", "J"]]],
            },
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        assert "card--clubs" in html
        assert "card--bower" in html
        assert ">RB<" in html  # right bower badge

    def test_non_bower_jack_no_badge(self, env):
        """Non-bower J does not get a bower badge."""
        tmpl = env.get_template("partials/trick.html")
        # J♦ played in a clubs contract — not a bower (different color)
        html = tmpl.render(
            current_trick={
                "leader": 0,
                "plays": [[0, ["D", "J"]]],
            },
            completed_tricks=[],
            dealer_seat=3,
            bidder_seat=0,
            current_seat=1,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        assert "card--diamonds" in html
        assert "card--bower" not in html

    # -- hand.html: card in player's hand --

    def test_left_bower_in_hand_shows_printed_suit(self, env):
        """Left bower in the hand shows printed suit and LB badge (#2261)."""
        tmpl = env.get_template("partials/hand.html")
        # J♦ in a hearts contract — left bower of hearts
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            human_hand=[["D", "J"], ["H", "A"]],
            legal_plays=None,
            phase="trick_play",
            contract_type="suit",
            trump="H",
        )
        # The J♦ card should show diamonds (♦) — its printed suit
        assert "card--diamonds" in html
        assert "card--bower" in html
        assert ">LB<" in html

    def test_left_bower_legal_card_shows_printed_suit(self, env):
        """Left bower as a legal play button shows printed suit + LB badge."""
        tmpl = env.get_template("partials/hand.html")
        # J♠ legal in a clubs contract — left bower
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=5,
            human_hand=[["S", "J"]],
            legal_plays=[0],
            phase="trick_play",
            contract_type="suit",
            trump="C",
        )
        # Should show spades suit (printed), with LB bower badge
        assert "card--spades" in html
        assert "card--bower" in html
        assert "(left bower)" in html
        assert ">LB<" in html

    def test_hand_no_bower_without_trump(self, env):
        """No bower badge when trump is not set (e.g. auction phase)."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            human_hand=[["S", "J"]],
            legal_plays=None,
            phase="auction",
        )
        assert "card--bower" not in html

    def test_hand_no_bower_during_auction_even_with_trump_set(self, env):
        """No bower badge during auction settle pause when trump leaks (#2473).

        During the auction settle interstitial, the engine may have already
        resolved the contract (setting trump/contract_type), but the template
        phase is still "auction".  Bower badges must not appear.
        """
        tmpl = env.get_template("partials/hand.html")
        # J♣ would be right bower of clubs — but phase is auction
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            human_hand=[["C", "J"], ["S", "J"], ["H", "A"]],
            legal_plays=None,
            phase="auction",
            contract_type="suit",
            trump="C",
        )
        assert "card--bower" not in html
        assert ">RB<" not in html
        assert ">LB<" not in html
        assert "bower" not in html.lower().replace("is_bower", "")

    # -- trick_history.html: card in history table --

    def test_left_bower_in_history_shows_printed_suit(self, env):
        """Left bower in trick history shows printed suit + LB badge (#2261)."""
        tmpl = env.get_template("partials/trick_history.html")
        # J♠ in a clubs contract — left bower
        html = tmpl.render(
            completed_tricks=[
                {
                    "leader": 0,
                    "plays": [
                        [0, ["S", "J"]],  # left bower of clubs
                        [1, ["C", "A"]],
                        [2, ["C", "K"]],
                        [3, ["C", "Q"]],
                    ],
                    "winner": 0,
                },
            ],
            tricks_team0=1,
            tricks_team1=0,
            contract_type="suit",
            trump="C",
        )
        # Should show ♠ for the left bower (printed suit), not ♣
        assert "\u2660" in html  # ♠
        assert "bower-sup" in html
        assert ">LB<" in html

    # -- moon_exchange.html: exchanged cards --

    def test_left_bower_in_exchange_shows_printed_suit(self, env):
        """Left bower in moon exchange given cards shows printed suit (#2261)."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            bidder_seat=0,
            exchange_given=[["S", "J"]],  # left bower of clubs
            exchange_received=[["C", "A"]],
            contract_type="suit",
            trump="C",
            link_uuid="test-uuid",
            human_hand=[["C", "K"], ["C", "Q"]],
        )
        # Should show spades (♠) — printed suit of J♠
        assert "card--spades" in html
        assert "card--bower" in html
        assert ">LB<" in html

    # -- moon_exchange_select.html: selectable cards --

    def test_left_bower_in_exchange_select_shows_printed_suit(self, env):
        """Left bower in moon exchange selection shows printed suit (#2261)."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            bidder_seat=0,
            contract_type="suit",
            trump="C",
            link_uuid="test-uuid",
            human_hand=[["S", "J"], ["C", "A"]],  # left bower + A♣
            exchange_prompt="Choose 2 cards",
            is_mooner=True,
        )
        # Should show spades (♠) — printed suit of J♠
        assert "card--spades" in html
        assert "card--bower" in html
        assert ">LB<" in html


class TestIsBowerFilter:
    """Unit tests for the is_bower template filter."""

    def test_left_bower(self):
        assert is_bower(["S", "J"], "C", "suit") == "left"

    def test_right_bower(self):
        assert is_bower(["C", "J"], "C", "suit") == "right"

    def test_non_bower_jack(self):
        assert is_bower(["D", "J"], "C", "suit") == ""

    def test_non_jack(self):
        assert is_bower(["C", "A"], "C", "suit") == ""

    def test_no_trump(self):
        assert is_bower(["S", "J"], None, "suit") == ""

    def test_high_contract(self):
        assert is_bower(["S", "J"], "C", "high") == ""

    def test_low_contract(self):
        assert is_bower(["S", "J"], "C", "low") == ""


# ---------------------------------------------------------------------------
# Moon exchange morph — bid panel uses innerHTML swap (#2214)
# ---------------------------------------------------------------------------


class TestBidPanelSwapMode:
    """Verify bid_panel uses innerHTML swap (not morph) to avoid TypeError (#2214)."""

    def test_bid_panel_uses_innerhtml_swap(self, env):
        """The bid panel form uses hx-swap='innerHTML' not 'morph:innerHTML'."""
        tmpl = env.get_template("partials/bid_panel.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            auction=[],
            current_high_bid=0,
            dealer_seat=3,
            bid_type="regular",
        )
        assert 'hx-swap="innerHTML"' in html
        assert "morph" not in html


# ---------------------------------------------------------------------------
# display_rank filter — ten cards show '10' instead of 'T'
# ---------------------------------------------------------------------------


class TestDisplayRankFilter:
    """Verify the display_rank Jinja filter converts 'T' → '10'."""

    def test_filter_converts_t_to_10(self):
        """The filter function converts 'T' to '10'."""
        assert display_rank("T") == "10"

    def test_filter_passes_other_ranks(self):
        """Non-ten ranks pass through unchanged."""
        for rank in ("J", "Q", "K", "A"):
            assert display_rank(rank) == rank

    def test_hand_renders_ten_as_10(self, env):
        """A ten of spades in hand.html shows '10' not 'T'."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            human_hand=[["S", "T"]],
            legal_plays=None,
            phase="auction",
        )
        # The card__rank span should contain '10', not 'T'
        assert ">10<" in html
        assert ">T<" not in html

    def test_hand_legal_card_ten_shows_10(self, env):
        """Legal ten card button shows '10' in title and aria-label."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=5,
            human_hand=[["H", "T"]],
            legal_plays=[0],
            phase="trick_play",
        )
        assert "10♥" in html
        assert "Play 10 of Hearts" in html

    def test_trick_renders_ten_as_10(self, env):
        """Played ten in trick.html shows '10'."""
        tmpl = env.get_template("partials/trick.html")
        html = tmpl.render(
            current_trick={
                "leader": 0,
                "plays": [[0, ["S", "T"]]],
            },
            completed_tricks=[],
            current_seat=1,
            dealer_seat=0,
            bidder_seat=0,
            sitting_out_seat=None,
            tricks_team0=0,
            tricks_team1=0,
        )
        assert ">10<" in html
        assert "played 10 of Spades" in html

    def test_trick_history_renders_ten_as_10(self, env):
        """Ten in trick_history.html shows '10'."""
        tricks = [
            {
                "leader": 0,
                "plays": [
                    [0, ["S", "T"]],
                    [1, ["S", "J"]],
                    [2, ["S", "Q"]],
                    [3, ["S", "K"]],
                ],
                "winner": 0,
            },
        ]
        tmpl = env.get_template("partials/trick_history.html")
        html = tmpl.render(completed_tricks=tricks, tricks_team0=1, tricks_team1=0)
        # Rank and suit are in separate spans (#2289)
        assert "10<span" in html
        assert ">♠</span>" in html

    def test_moon_exchange_renders_ten_as_10(self, env):
        """Ten cards in moon_exchange.html show '10'."""
        tmpl = env.get_template("partials/moon_exchange.html")
        html = tmpl.render(
            bidder_seat=0,
            exchange_given=[["S", "T"]],
            exchange_received=[["H", "T"]],
            contract_type="suit",
            trump="S",
            link_uuid="test-uuid",
            human_hand=[["S", "A"], ["H", "T"]],
        )
        assert ">10<" in html
        # Should not have a standalone 'T' rank display
        # (check within card__rank spans specifically)
        assert 'aria-hidden="true">T<' not in html

    def test_moon_exchange_select_renders_ten_as_10(self, env):
        """Ten cards in moon_exchange_select.html show '10'."""
        tmpl = env.get_template("partials/moon_exchange_select.html")
        html = tmpl.render(
            bidder_seat=0,
            contract_type="suit",
            trump="S",
            link_uuid="test-uuid",
            human_hand=[["S", "T"], ["H", "K"]],
            exchange_prompt="Choose 2 cards to exchange",
            is_mooner=True,
        )
        assert ">10<" in html
        assert "Select 10 of Spades" in html

    def test_non_ten_ranks_unchanged(self, env):
        """Non-ten ranks still render normally."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="test-uuid",
            turn_number=0,
            human_hand=[["S", "J"], ["H", "Q"], ["D", "K"], ["C", "A"]],
            legal_plays=None,
            phase="auction",
        )
        assert ">J<" in html
        assert ">Q<" in html
        assert ">K<" in html
        assert ">A<" in html


# ---------------------------------------------------------------------------
# Score display consistency (#2212)
# ---------------------------------------------------------------------------


class TestScoreDisplayConsistency:
    """Verify score-value spans appear on hand-result and match-result pages."""

    def test_hand_result_match_score_has_score_value_spans(self, env):
        """Hand result match score line uses structured score-value spans."""
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
        assert "score-value" in html
        assert "score--positive" in html

    def test_hand_result_negative_score_has_negative_class(self, env):
        """Negative match score renders with score--negative class."""
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
        assert "score--negative" in html

    def test_match_result_score_has_positive_class(self, env):
        """Match result final score uses score--positive for winning score."""
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="x",
            winner="human",
            score_human=55,
            score_ai=30,
            hands_played=12,
        )
        assert "score--positive" in html

    def test_match_result_negative_score_has_negative_class(self, env):
        """Match result renders score--negative for negative final score."""
        tmpl = env.get_template("partials/match_result.html")
        html = tmpl.render(
            link_uuid="x",
            winner="ai",
            score_human=-5,
            score_ai=52,
            hands_played=10,
        )
        assert "score--negative" in html


# ---------------------------------------------------------------------------
# #2205 — Singular card count grammar
# ---------------------------------------------------------------------------


class TestCardCountGrammar:
    """Card count labels use '1 card' (singular) and 'N cards' (plural)."""

    def test_hand_singular_card_label(self, env):
        """Human hand with 1 card uses singular 'card'."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"]],
            legal_plays=None,
            phase="trick_play",
        )
        assert "1 card in your hand" in html

    def test_hand_plural_card_label(self, env):
        """Human hand with multiple cards uses plural 'cards'."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"], ["H", "K"], ["D", "Q"]],
            legal_plays=None,
            phase="auction",
        )
        assert "3 cards in your hand" in html

    _BOARD_CTX = dict(
        phase="auction",
        link_uuid="x",
        human_hand=[["S", "A"]],
        legal_plays=None,
        turn_number=0,
        seat_labels={0: "You", 1: "Slim", 2: "Ace", 3: "Deuce"},
        score_human=0,
        score_ai=0,
        hands_played=0,
        dealer_seat=0,
        winning_bid=None,
        bidder_seat=None,
        tricks_team0=0,
        tricks_team1=0,
    )

    def test_game_board_singular_ai_hand(self, env):
        """AI hand aria-label with 1 card uses singular 'card'."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            **self._BOARD_CTX,
            opp_left_count=1,
            partner_count=1,
            opp_right_count=1,
        )
        assert "Slim has 1 card" in html
        assert "Ace has 1 card" in html
        assert "Deuce has 1 card" in html

    def test_game_board_plural_ai_hand(self, env):
        """AI hand aria-label with multiple cards uses plural 'cards'."""
        tmpl = env.get_template("partials/game_board.html")
        html = tmpl.render(
            **self._BOARD_CTX,
            opp_left_count=5,
            partner_count=5,
            opp_right_count=5,
        )
        assert "Slim has 5 cards" in html
        assert "Ace has 5 cards" in html
        assert "Deuce has 5 cards" in html


# ---------------------------------------------------------------------------
# #2215 — Duplicate card copy index in accessible names
# ---------------------------------------------------------------------------


class TestDuplicateCardCopyIndex:
    """Double-deck duplicate cards get copy index in aria-label."""

    def test_duplicate_cards_get_copy_suffix(self, env):
        """Two identical cards in hand get '(1)' and '(2)' suffixes."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"], ["S", "A"]],
            legal_plays=None,
            phase="auction",
        )
        assert "A of Spades (1)" in html
        assert "A of Spades (2)" in html

    def test_unique_cards_no_copy_suffix(self, env):
        """Unique cards do not get copy suffixes."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"], ["H", "K"]],
            legal_plays=None,
            phase="auction",
        )
        assert "A of Spades" in html
        assert "(1)" not in html
        assert "(2)" not in html

    def test_duplicate_legal_cards_get_copy_suffix(self, env):
        """Duplicate legal cards during trick play also get copy index."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["H", "K"], ["H", "K"]],
            legal_plays=[0, 1],
            phase="trick_play",
        )
        assert "Play K of Hearts (1)" in html
        assert "Play K of Hearts (2)" in html

    def test_mixed_duplicates_only_dups_get_suffix(self, env):
        """Only duplicated cards get copy suffixes; unique cards do not."""
        tmpl = env.get_template("partials/hand.html")
        html = tmpl.render(
            link_uuid="x",
            turn_number=0,
            human_hand=[["S", "A"], ["H", "K"], ["S", "A"]],
            legal_plays=None,
            phase="auction",
        )
        assert "A of Spades (1)" in html
        assert "A of Spades (2)" in html
        # K of Hearts should not have a copy suffix
        assert "K of Hearts" in html
        assert "K of Hearts (1)" not in html


# ---------------------------------------------------------------------------
# #2209 — data-match-status attribute on game board
# ---------------------------------------------------------------------------


class TestMatchStatusDataAttribute:
    """The #game-board div carries a data-match-status attribute (#2209)."""

    def test_active_match_status(self, env):
        """Active match renders data-match-status='active'."""
        tmpl = env.get_template("game.html")
        html = tmpl.render(
            match_status="active",
            phase="nickname",
            link_uuid="x",
        )
        assert 'data-match-status="active"' in html

    def test_complete_match_status(self, env):
        """Completed match renders data-match-status='complete'."""
        tmpl = env.get_template("game.html")
        html = tmpl.render(
            match_status="complete",
            phase="match_result",
            link_uuid="x",
            winner="human",
            score_human=52,
            score_ai=30,
            hands_played=10,
        )
        assert 'data-match-status="complete"' in html

    def test_missing_match_status_defaults_to_setup(self, env):
        """When match_status is not provided, defaults to 'setup'."""
        tmpl = env.get_template("game.html")
        html = tmpl.render(
            phase="nickname",
            link_uuid="x",
        )
        assert 'data-match-status="setup"' in html

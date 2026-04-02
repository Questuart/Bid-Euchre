"""Integration tests for web.routes — FastAPI route handlers.

Uses FastAPI TestClient with an in-memory SQLite database for isolation.
Tests cover the full match lifecycle: create → nickname → select-ai →
bid → play-card → match completion → decision logging.
"""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from bid_euchre.core.cards import Card
from bid_euchre.hosted_play import TrickResult, TrickState
from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.strategy.bidding import BidAction, BiddingObservation, BiddingPolicy
from tests.unit.hosted_play.conftest import (
    advance_pending_reveals,
    get_match_state,
    make_hosted_play_test_config,
)
from web.ai_manager import AIManager, ModelInfo
from web.app import create_app
from web.db import Decision, Hand, InviteCode, Match, Player

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path):
    """File-based SQLite config for test isolation.

    Uses a temp file rather than in-memory SQLite because in-memory
    databases aren't shared across different connections/threads.
    """
    return make_hosted_play_test_config(tmp_path)


@pytest.fixture()
def app(config):
    """FastAPI app configured with in-memory DB."""
    return create_app(config=config)


@pytest.fixture()
def client(app):
    """TestClient for the app."""
    with TestClient(app) as c:
        yield c


def _create_game(client: TestClient) -> str:
    """POST /new and return the link_uuid from the redirect URL."""
    resp = client.post("/new", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["location"]
    # Location is /play/{link_uuid}
    link_uuid = location.split("/play/")[1]
    return link_uuid


def _set_nickname(client: TestClient, link_uuid: str, nickname: str = "Tester"):
    """Set nickname and return the response."""
    return client.post(
        f"/play/{link_uuid}/nickname",
        data={"nickname": nickname},
    )


def _select_ai(client: TestClient, link_uuid: str, model_id: str = "olsa"):
    """Select AI model and return the response."""
    return client.post(
        f"/play/{link_uuid}/select-ai",
        data={"model_id": model_id},
    )


def _setup_game(client: TestClient) -> str:
    """Create game, set nickname, select AI, return link_uuid."""
    link_uuid = _create_game(client)
    _set_nickname(client, link_uuid)
    _select_ai(client, link_uuid)
    return link_uuid


# ---------------------------------------------------------------------------
# Test 1: Create game → 302 with UUID
# ---------------------------------------------------------------------------


class TestCreateGame:
    """POST /new creates a player and redirects."""

    def test_create_game_redirects(self, client):
        resp = client.post("/new", follow_redirects=False)
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "/play/" in location
        # UUID is in the path
        link_uuid = location.split("/play/")[1]
        assert len(link_uuid) == 36  # UUID format


# ---------------------------------------------------------------------------
# Test 2: Set nickname → stores in DB
# ---------------------------------------------------------------------------


class TestSetNickname:
    """POST /play/{uuid}/nickname stores the nickname."""

    def test_set_nickname_stores(self, client, app):
        link_uuid = _create_game(client)
        resp = _set_nickname(client, link_uuid, "Alice")
        assert resp.status_code == 200
        assert "Alice" in resp.text

        # Verify in DB
        session_factory = app.state.session_factory
        session = session_factory()
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        assert player.nickname == "Alice"
        session.close()


# ---------------------------------------------------------------------------
# Test 3: Select AI model → match created, first hand dealt
# ---------------------------------------------------------------------------


class TestSelectAI:
    """POST /play/{uuid}/select-ai creates match with first hand dealt."""

    def test_select_ai_creates_match(self, client, app):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        resp = _select_ai(client, link_uuid, "olsa")
        assert resp.status_code == 200

        # Verify match exists in DB
        session_factory = app.state.session_factory
        session = session_factory()
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        match_row = session.query(Match).filter_by(player_id=player.id).first()
        assert match_row is not None
        assert match_row.status == "active"
        assert match_row.ai_model == "olsa"

        # Verify match state has a current hand
        state_data = json.loads(match_row.match_state_json)
        assert state_data["current_hand"] is not None
        session.close()

    def test_select_invalid_model_rejected(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        resp = _select_ai(client, link_uuid, "nonexistent_model")
        assert resp.status_code == 400

    def test_test_seed_produces_deterministic_match(self, tmp_path):
        """When test_seed is set, select-ai uses it instead of random."""
        config = make_hosted_play_test_config(tmp_path, test_seed=42)
        app = create_app(config=config)

        seeds = []
        with TestClient(app) as c:
            for _ in range(2):
                link_uuid = _create_game(c)
                _set_nickname(c, link_uuid)
                resp = _select_ai(c, link_uuid, "olsa")
                assert resp.status_code == 200

                session = app.state.session_factory()
                player = session.query(Player).filter_by(link_uuid=link_uuid).first()
                match_row = session.query(Match).filter_by(player_id=player.id).first()
                seeds.append(match_row.seed)
                session.close()

        # Both matches should have the same seed
        assert seeds[0] == seeds[1] == 42


# ---------------------------------------------------------------------------
# Test 4: Submit bid → state advances
# ---------------------------------------------------------------------------


class TestSubmitBid:
    """POST /play/{uuid}/bid advances the auction state."""

    def test_submit_bid_advances_state(self, client, app):
        link_uuid = _setup_game(client)
        advance_pending_reveals(client, app, link_uuid)

        # Get the current state to find the turn number
        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result
        session.close()

        hand = state.current_hand
        assert hand is not None

        # The human might need to bid. If it's the human's turn in auction:
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            turn = hand.turn_number
            resp = client.post(
                f"/play/{link_uuid}/bid",
                data={
                    "turn_number": turn,
                    "bid_n": 0,  # pass
                    "bid_contract": "",
                },
            )
            assert resp.status_code == 200

            # State should have advanced
            result2 = get_match_state(app, link_uuid)
            assert result2 is not None
            state2, _, session2 = result2
            # Either the hand advanced past this turn or a new hand started
            if state2.current_hand is not None:
                assert (
                    state2.current_hand.turn_number > turn
                    or state2.hands_played > state.hands_played
                )
            session2.close()


# ---------------------------------------------------------------------------
# Test 4a: Unified next-step reveal flow
# ---------------------------------------------------------------------------


class TestNextRevealFlow:
    def test_next_reveals_hidden_auction_actions(self, client, app):
        """GET/POST next exposes hidden auction actions one step at a time."""
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None
        hand.phase = "auction"
        hand.current_seat = HUMAN_SEAT
        hand.turn_number = 2
        hand.auction = [
            {"seat": 1, "n": 0, "action": "pass"},
            {
                "seat": 2,
                "n": 5,
                "action": "bid",
                "contract": "S",
                "bid_type": "regular",
            },
        ]
        hand.revealed_auction_count = 1
        hand.current_high_bid = 5
        match_row.match_state_json = json.dumps(state.to_dict())
        session.commit()
        session.close()

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert f'hx-post="/play/{link_uuid}/next"' in resp.text
        assert "Reveal the next auction action." in resp.text
        assert "Submit Bid" not in resp.text

        resp = client.post(f"/play/{link_uuid}/next")
        assert resp.status_code == 200
        assert "Submit Bid" in resp.text

        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, _, session_after = result_after
        assert state_after.current_hand is not None
        assert state_after.current_hand.revealed_auction_count == 2
        session_after.close()

    def test_next_clears_trick_pause_and_restores_play_controls(self, client, app):
        """Paused trick state hides play controls until the user presses Next."""
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None
        hand.phase = "trick_play"
        hand.current_seat = HUMAN_SEAT
        hand.turn_number = 6
        hand.bidder_seat = 1
        hand.winning_bid = 6
        hand.bid_type = "regular"
        hand.contract_type = "suit"
        hand.trump = "S"
        hand.revealed_auction_count = len(hand.auction)
        hand.hands = [
            [Card("H", "K"), Card("S", "A")],
            [],
            [],
            [],
        ]
        hand.completed_tricks = [
            TrickResult(
                leader=1,
                plays=[
                    (1, Card("D", "A")),
                    (2, Card("D", "K")),
                    (3, Card("D", "Q")),
                    (0, Card("D", "10")),
                ],
                winner=1,
            )
        ]
        hand.current_trick = TrickState(leader=1, plays=[(1, Card("H", "A"))])
        hand.paused_after_trick = True
        match_row.match_state_json = json.dumps(state.to_dict())
        session.commit()
        session.close()

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "Continue to the next trick." in resp.text
        assert "Trick 1 of 10 complete" in resp.text
        assert 'id="card-play-form"' not in resp.text

        resp = client.post(f"/play/{link_uuid}/next")
        assert resp.status_code == 200
        assert "Play card" in resp.text

        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, _, session_after = result_after
        assert state_after.current_hand is not None
        assert state_after.current_hand.paused_after_trick is False
        session_after.close()

    def test_next_reveals_moon_exchange_and_transitions_to_trick_play(
        self, client, app
    ):
        """POST /next flips exchange_revealed and transitions from moon exchange to trick play.

        Verifies the route-level /next handler for the moon-exchange-pending
        state: before the POST the interstitial is shown; after it the game
        advances to trick play.  Closes #1930.
        """
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None
        # Simulate a completed moon exchange that is pending reveal:
        # phase is "trick_play" (engine sets this after exchange), but
        # exchange_revealed is still False so the route renders the
        # moon_exchange interstitial.
        hand.phase = "trick_play"
        hand.current_seat = HUMAN_SEAT
        hand.turn_number = 6
        hand.bidder_seat = 1
        hand.winning_bid = 10
        hand.bid_type = "moon"
        hand.contract_type = "suit"
        hand.trump = "H"
        hand.revealed_auction_count = len(hand.auction)
        hand.exchange_given = [["H", "10"], ["D", "10"]]
        hand.exchange_received = [["H", "A"], ["H", "K"]]
        hand.exchange_revealed = False
        hand.exchange_phase = None
        hand.hands = [
            [Card("H", "A"), Card("H", "K"), Card("S", "A"), Card("S", "K")],
            [Card("D", "A"), Card("D", "K")],
            [Card("C", "A"), Card("C", "K")],
            [Card("S", "Q"), Card("S", "J")],
        ]
        hand.current_trick = TrickState(leader=1)
        match_row.match_state_json = json.dumps(state.to_dict())
        session.commit()
        session.close()

        # Before /next: the moon exchange interstitial should be rendered
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "Moon Exchange" in resp.text
        assert "Start Trick Play" in resp.text
        # The moon_exchange partial has its own /next form button —
        # trick play controls should NOT be visible yet
        assert 'id="card-play-form"' not in resp.text

        # POST /next to reveal the exchange
        resp = client.post(f"/play/{link_uuid}/next")
        assert resp.status_code == 200
        # After reveal, the response should show trick play (not the exchange)
        assert "Moon Exchange" not in resp.text
        assert "Start Trick Play" not in resp.text

        # Verify exchange_revealed was persisted
        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, _, session_after = result_after
        hand_after = state_after.current_hand
        assert hand_after is not None
        assert hand_after.exchange_revealed is True
        assert hand_after.phase == "trick_play"
        session_after.close()

    def test_hidden_auction_hides_trick_play_state(self, client, app):
        """Trick data must not render while auction bids are still hidden.

        Regression test: when the engine auto-advances from auction into
        trick play (AI bids completing the auction + AI leading the first
        trick), the route-level game context must suppress trick-play state
        until all auction entries are revealed via /next.
        """
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None

        # Simulate: engine finished auction → trick_play, but only 1 of 4
        # auction bids has been revealed to the user.
        hand.phase = "trick_play"
        hand.dealer_seat = 3
        hand.current_seat = HUMAN_SEAT
        hand.turn_number = 5  # 4 bids + 1 AI card play
        hand.bidder_seat = 1
        hand.winning_bid = 5
        hand.bid_type = "regular"
        hand.contract_type = "suit"
        hand.trump = "S"
        hand.auction = [
            {
                "seat": 0,
                "n": 5,
                "action": "bid",
                "contract": "S",
                "bid_type": "regular",
            },
            {"seat": 1, "n": 0, "action": "pass"},
            {"seat": 2, "n": 0, "action": "pass"},
            {"seat": 3, "n": 0, "action": "pass"},
        ]
        hand.revealed_auction_count = 1  # Only human's bid revealed

        # AI already played a card into the trick (engine auto-advance)
        hand.current_trick = TrickState(
            leader=1,
            plays=[(1, Card("D", "A"))],
        )
        # AI hand now has 9 cards (one played)
        hand.hands[1] = hand.hands[1][:9]

        match_row.match_state_json = json.dumps(state.to_dict())
        session.commit()
        session.close()

        # Render the game page — should show auction reveal, NOT trick data
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200

        # The "Next" button should be visible (auction reveal in progress)
        assert f'hx-post="/play/{link_uuid}/next"' in resp.text

        # Trick area should NOT show the AI's played card
        # D♦ / A would appear as card rank+suit in the trick area
        assert "card--played" not in resp.text

        # AI Left hand count should show 10 (pre-play), not 9
        assert "AI Left (10)" in resp.text

        # No "Play card" button — still in auction reveal
        assert 'id="card-play-form"' not in resp.text


# ---------------------------------------------------------------------------
# Test 5: Submit card → state advances
# ---------------------------------------------------------------------------


class TestSubmitCard:
    """POST /play/{uuid}/play-card advances the trick play state."""

    def test_submit_card_advances_state(self, client, app):
        link_uuid = _setup_game(client)

        # We need to get to trick_play phase with the human's turn.
        # Keep bidding pass until the auction resolves.
        for _ in range(20):  # safety limit for redeals
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                # Pass in auction — the AI may place a bid
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                # Found a trick play turn — play a legal card
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                assert len(legal) > 0

                turn = hand.turn_number
                resp = client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": turn,
                        "card_index": legal[0],
                    },
                )
                assert resp.status_code == 200

                # State should have advanced
                result2 = get_match_state(app, link_uuid)
                assert result2 is not None
                state2, _, session2 = result2
                if state2.current_hand is not None:
                    assert (
                        state2.current_hand.turn_number > turn
                        or state2.hands_played > state.hands_played
                    )
                session2.close()
                return  # Test passed

        pytest.fail("Never reached human's trick play turn")


# ---------------------------------------------------------------------------
# Test 6: Idempotent resubmission → same response
# ---------------------------------------------------------------------------


class TestIdempotentResubmission:
    """Submitting the same turn_number twice returns current state."""

    def test_idempotent_bid(self, client, app):
        link_uuid = _setup_game(client)
        advance_pending_reveals(client, app, link_uuid)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None or hand.phase != "auction" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in auction position")

        turn = hand.turn_number
        # First submission
        resp1 = client.post(
            f"/play/{link_uuid}/bid",
            data={"turn_number": turn, "bid_n": 0, "bid_contract": ""},
        )
        assert resp1.status_code == 200

        # Same turn_number — idempotent
        resp2 = client.post(
            f"/play/{link_uuid}/bid",
            data={"turn_number": turn, "bid_n": 0, "bid_contract": ""},
        )
        assert resp2.status_code == 200
        # Both should return valid responses (second is idempotent)


# ---------------------------------------------------------------------------
# Test 7: Invalid move rejected → error response
# ---------------------------------------------------------------------------


class TestInvalidMove:
    """Invalid actions are rejected with an error response."""

    def test_invalid_card_rejected(self, client, app):
        link_uuid = _setup_game(client)

        # Navigate to trick play phase
        for _ in range(20):
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                # Try an invalid card index
                resp = client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": 99,  # invalid index
                    },
                )
                assert resp.status_code == 400
                return

        pytest.fail("Never reached human's trick play turn for invalid move test")


# ---------------------------------------------------------------------------
# Test 8: Match resume → shows correct state
# ---------------------------------------------------------------------------


class TestMatchResume:
    """GET /play/{uuid} after actions shows the correct game state."""

    def test_resume_after_bid(self, client, app):
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        hand = state.current_hand
        if (
            hand is not None
            and hand.phase == "auction"
            and hand.current_seat == HUMAN_SEAT
        ):
            client.post(
                f"/play/{link_uuid}/bid",
                data={
                    "turn_number": hand.turn_number,
                    "bid_n": 0,
                    "bid_contract": "",
                },
            )

        # Resume — GET the page
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # Should show game board with score bar from templates
        assert "game-board" in resp.text
        assert "score-bar" in resp.text


# ---------------------------------------------------------------------------
# Test 9: Match completion → status becomes complete
# ---------------------------------------------------------------------------


class TestMatchCompletion:
    """Play a full match to completion, verify status becomes complete."""

    def test_play_to_completion(self, client, app):
        link_uuid = _setup_game(client)

        # Play through the entire match
        # The AI will auto-advance. Human just needs to pass bids
        # and play legal cards. With enough turns the match should end.
        turns_played = 0
        max_turns = 2000  # safety limit

        while turns_played < max_turns:
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, match_row, session = result

            if state.status == "complete" or match_row.status == "complete":
                session.close()
                # Verify match status in DB
                session2 = app.state.session_factory()
                m = session2.query(Match).filter_by(id=match_row.id).first()
                assert m.status == "complete"
                session2.close()
                return  # Test passed

            hand = state.current_hand
            if hand is not None and hand.phase == "complete":
                session.close()
                client.post(f"/play/{link_uuid}/next-hand")
                turns_played += 1
                continue
            session.close()

            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                # Bid: alternate between passing and making small bids
                # to keep the game moving
                if turns_played % 3 == 0 and hand.current_high_bid < 5:
                    bid_n = hand.current_high_bid + 1
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": bid_n,
                            "bid_contract": "H",
                        },
                    )
                else:
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": 0,
                            "bid_contract": "",
                        },
                    )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
            elif hand.phase == "complete":
                client.post(f"/play/{link_uuid}/next-hand")
            else:
                # Not human's turn — something unexpected; break
                break

            turns_played += 1

        # If we get here, verify match eventually completed or we ran out of turns
        result = get_match_state(app, link_uuid)
        if result is not None:
            state, match_row, session = result
            session.close()
            if state.status == "complete":
                return  # late completion check
        pytest.fail(
            f"Match did not complete within {max_turns} turns (played {turns_played})"
        )


# ---------------------------------------------------------------------------
# Test 10: Decision logging → decisions rows exist
# ---------------------------------------------------------------------------


class TestDecisionLogging:
    """After playing, verify decision rows exist in the DB."""

    def test_decisions_logged(self, client, app):
        link_uuid = _setup_game(client)

        # Play a few turns to generate decisions
        for _ in range(20):
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
                break  # played at least one card
            else:
                break

        # Verify decisions rows exist
        session = app.state.session_factory()
        decisions = session.query(Decision).all()
        assert len(decisions) > 0, "Expected at least one decision row"

        # Verify at least one human decision
        human_decisions = [d for d in decisions if d.actor_type == "human"]
        assert len(human_decisions) > 0, "Expected at least one human decision"
        session.close()


# ---------------------------------------------------------------------------
# Landing page
# ---------------------------------------------------------------------------


class TestLandingPage:
    """GET / returns the landing page with invite code form."""

    def test_landing_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Bid Euchre" in resp.text
        assert "Enter Invite Code" in resp.text
        assert "invite-code-input" in resp.text


# ---------------------------------------------------------------------------
# New match
# ---------------------------------------------------------------------------


class TestNewMatch:
    """POST /play/{uuid}/new-match returns model selection."""

    def test_new_match_shows_model_selection(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)

        resp = client.post(f"/play/{link_uuid}/new-match")
        assert resp.status_code == 200
        assert "Start Match" in resp.text


# ---------------------------------------------------------------------------
# Redeal persistence
# ---------------------------------------------------------------------------


class _AlwaysPassBidder(BiddingPolicy):
    """Bidding policy that always passes — forces all-pass redeals."""

    def __init__(self) -> None:
        super().__init__(name="always_pass")

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


@pytest.fixture()
def allpass_client(config):
    """TestClient whose AI always passes — forces all-pass redeals.

    The AI manager is set during the lifespan (triggered by entering the
    TestClient context), so we swap the bidding policy after startup.
    """
    application = create_app(config=config)
    with TestClient(application) as c:
        ai_manager: AIManager = application.state.ai_manager
        info = ai_manager.available_models["olsa"]
        ai_manager.available_models["olsa"] = ModelInfo(
            id=info.id,
            name=info.name,
            description=info.description,
            bidding_policy=_AlwaysPassBidder(),
            play_strategy=info.play_strategy,
        )
        yield c, application


class _FixedRegularBidder(BiddingPolicy):
    """Bidding policy that bids up to 5♠ so we get deterministic non-moon flow."""

    def __init__(self) -> None:
        super().__init__(name="fixed_regular")

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.current_high_bid < 5:
            return BidAction.bid(5, "S")
        return BidAction.pass_bid()


@pytest.fixture()
def regular_ai_client(config):
    """TestClient whose AI bids a fixed regular contract to avoid loner/moon variance."""
    application = create_app(config=config)
    with TestClient(application) as c:
        ai_manager: AIManager = application.state.ai_manager
        info = ai_manager.available_models["olsa"]
        ai_manager.available_models["olsa"] = ModelInfo(
            id=info.id,
            name=info.name,
            description=info.description,
            bidding_policy=_FixedRegularBidder(),
            play_strategy=info.play_strategy,
        )
        yield c, application


class TestRedealPersistence:
    """All-pass redeal creates a Hand row marked 'redeal' with correct metadata."""

    def test_all_pass_hand_row_marked_redeal(self, allpass_client):
        """Force all-pass → assert Hand row persisted as 'redeal'."""
        client, app = allpass_client
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)
        advance_pending_reveals(client, app, link_uuid)

        # Load the current match state to get the turn number
        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "auction"
        assert hand.current_seat == HUMAN_SEAT

        original_deal_id = hand.deal_id
        original_dealer = hand.dealer_seat
        match_id = match_row.id
        session.close()

        # Human passes — all AI already passed → all-pass redeal
        resp = client.post(
            f"/play/{link_uuid}/bid",
            data={
                "turn_number": hand.turn_number,
                "bid_n": 0,
                "bid_contract": "",
            },
        )
        assert resp.status_code == 200

        # Verify the hand row for the redealt hand
        session = app.state.session_factory()
        try:
            redeal_hand = (
                session.query(Hand).filter_by(match_id=match_id, hand_number=0).first()
            )
            assert redeal_hand is not None, "Expected Hand row for the redealt hand"
            assert redeal_hand.status == "redeal"
            assert redeal_hand.deal_id == original_deal_id
            assert redeal_hand.dealer_seat == original_dealer

            # Verify a new hand row exists for the next deal
            next_hand = (
                session.query(Hand)
                .filter_by(match_id=match_id)
                .filter(Hand.deal_id > original_deal_id)
                .first()
            )
            assert next_hand is not None, "Expected Hand row for the post-redeal hand"
            assert next_hand.status == "in_progress"
            assert next_hand.deal_id == original_deal_id + 1
            assert next_hand.dealer_seat == (original_dealer + 1) % 4
        finally:
            session.close()

    def test_match_state_has_new_hand_after_redeal(self, allpass_client):
        """After redeal, serialized match state shows the new hand (not redeal)."""
        client, app = allpass_client
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        hand = state.current_hand
        assert hand is not None
        session.close()

        # Human passes → all-pass redeal
        client.post(
            f"/play/{link_uuid}/bid",
            data={
                "turn_number": hand.turn_number,
                "bid_n": 0,
                "bid_contract": "",
            },
        )

        # Load the match state after redeal
        result2 = get_match_state(app, link_uuid)
        assert result2 is not None
        state2, _, session2 = result2

        # Match state should show the new hand in auction phase
        new_hand = state2.current_hand
        assert new_hand is not None
        assert new_hand.phase == "auction"
        assert state2.hands_played == 0  # Redeals don't count
        session2.close()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case coverage."""

    def test_game_page_unknown_uuid(self, client):
        resp = client.get("/play/nonexistent-uuid")
        assert resp.status_code == 404

    def test_nickname_unknown_uuid(self, client):
        resp = client.post(
            "/play/nonexistent-uuid/nickname",
            data={"nickname": "Test"},
        )
        assert resp.status_code == 404

    def test_bid_no_active_match(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        # No match created yet
        resp = client.post(
            f"/play/{link_uuid}/bid",
            data={"turn_number": 0, "bid_n": 0, "bid_contract": ""},
        )
        assert resp.status_code == 404

    def test_play_card_no_active_match(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        resp = client.post(
            f"/play/{link_uuid}/play-card",
            data={"turn_number": 0, "card_index": 0},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# XSS prevention (issue #1438)
# ---------------------------------------------------------------------------


class TestXSSPrevention:
    """Verify user-supplied nicknames are HTML-escaped in responses."""

    def test_nickname_html_escaped_in_set_nickname(self, client):
        """set_nickname() must escape HTML in the nickname."""
        link_uuid = _create_game(client)
        xss_payload = '<script>alert("xss")</script>'
        resp = _set_nickname(client, link_uuid, xss_payload)
        assert resp.status_code == 200
        # Raw script tag must NOT appear in the response
        assert "<script>" not in resp.text
        # Escaped form should appear
        assert "&lt;script&gt;" in resp.text

    def test_nickname_html_escaped_in_game_page(self, client):
        """game_page() must escape HTML in the stored nickname."""
        link_uuid = _create_game(client)
        xss_payload = '<img src=x onerror="alert(1)">'
        _set_nickname(client, link_uuid, xss_payload)
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # Raw tag must NOT appear
        assert '<img src=x onerror="alert(1)">' not in resp.text
        assert "&lt;img" in resp.text

    def test_game_page_backfills_player_cookie(self, client):
        """Visiting /play/{link_uuid} directly should set the session cookie
        so reconnect works on subsequent landing-page visits."""
        from web.middleware import PLAYER_COOKIE_NAME

        link_uuid = _create_game(client)
        # Clear cookies to simulate a direct visit (bookmark/shared link)
        client.cookies.clear()
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # The response should set the player cookie
        assert PLAYER_COOKIE_NAME in resp.cookies

    def test_game_page_includes_ai_hand_counts_for_accessibility(self, client):
        """Initial GET render should expose AI hand-count labels to screen readers."""
        link_uuid = _setup_game(client)
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # Count labels should be present on first render.
        assert "AI Left" in resp.text
        assert "AI Partner" in resp.text
        assert "AI Right" in resp.text
        # Ensure accessibility-related count labels are not excluded.
        assert 'class="ai-card-count" aria-hidden="true"' not in resp.text

    def test_nickname_html_escaped_in_new_match(self, client):
        """new_match() must escape HTML in the stored nickname."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid, "<b>bold</b>")
        resp = client.post(f"/play/{link_uuid}/new-match")
        assert resp.status_code == 200
        assert "<b>bold</b>" not in resp.text
        assert "&lt;b&gt;" in resp.text

    def test_new_match_none_nickname_does_not_crash(self, client):
        """new_match() must not crash when player.nickname is None (#1464)."""
        link_uuid = _create_game(client)
        # Do NOT set a nickname — player.nickname remains None
        resp = client.post(f"/play/{link_uuid}/new-match")
        assert resp.status_code == 200
        # Template renders model selection with fallback nickname "Player"
        assert "Welcome, Player!" in resp.text
        assert "model-select" in resp.text


# ---------------------------------------------------------------------------
# hx-post URL interpolation (issue #1439)
# ---------------------------------------------------------------------------


class TestHxPostUrl:
    """Verify hx-post attribute contains the correct interpolated URL."""

    def test_hx_post_contains_link_uuid(self, client):
        """The nickname form hx-post must include the actual link_uuid."""
        link_uuid = _create_game(client)
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # The hx-post attribute should contain the real UUID, not the
        # literal placeholder "{link_uuid}"
        assert f'hx-post="/play/{link_uuid}/nickname"' in resp.text
        assert "{link_uuid}" not in resp.text


# ---------------------------------------------------------------------------
# Test: AI decision content quality
# ---------------------------------------------------------------------------


class TestAIDecisionContent:
    """Verify AI decision rows have non-empty legal_actions and chosen_action.

    Regression test for the P1 finding: AI decision rows must contain exact
    legal_actions, chosen_action, and game_state — not empty placeholders.
    """

    def test_ai_bid_decisions_have_content(self, client, app):
        """After a bid route, AI bid decision rows have non-empty fields."""
        link_uuid = _setup_game(client)

        # Play a few auction turns to generate AI bid decisions
        for _ in range(10):
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
                break  # One bid is enough to trigger AI auto-advance
            else:
                break

        # Query AI decision rows
        session = app.state.session_factory()
        ai_decisions = session.query(Decision).filter(Decision.actor_type == "ai").all()

        assert len(ai_decisions) > 0, "Expected at least one AI decision row"

        for d in ai_decisions:
            legal = json.loads(d.legal_actions_json)
            chosen = json.loads(d.chosen_action_json)
            game_st = json.loads(d.game_state_json)

            assert (
                legal != []
            ), f"AI decision turn={d.turn_number} has empty legal_actions"
            assert (
                chosen != {}
            ), f"AI decision turn={d.turn_number} has empty chosen_action"
            assert (
                game_st != {}
            ), f"AI decision turn={d.turn_number} has empty game_state"

            # Verify legal_actions structure for bid phase
            if d.phase == "bid":
                assert isinstance(legal, list)
                assert all("n" in b and "contract" in b for b in legal)
                assert "n" in chosen
                assert "contract" in chosen

            # Verify game_state has required context fields
            assert "phase" in game_st
            assert "seat" in game_st
            assert "turn_number" in game_st

        session.close()

    def test_ai_play_decisions_have_content(self, client, app):
        """After a play-card route, AI play decision rows have non-empty fields."""
        link_uuid = _setup_game(client)

        # Navigate to trick play and play one card
        for _ in range(20):
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
                break
            else:
                break

        # Query AI play decision rows
        session = app.state.session_factory()
        ai_play_decisions = (
            session.query(Decision)
            .filter(Decision.actor_type == "ai", Decision.phase == "play")
            .all()
        )

        if len(ai_play_decisions) == 0:
            session.close()
            pytest.skip("No AI play decisions generated in this game state")

        for d in ai_play_decisions:
            legal = json.loads(d.legal_actions_json)
            chosen = json.loads(d.chosen_action_json)
            game_st = json.loads(d.game_state_json)

            assert (
                legal != []
            ), f"AI play decision turn={d.turn_number} has empty legal_actions"
            assert isinstance(legal, list)
            assert all(isinstance(idx, int) for idx in legal)
            assert isinstance(
                chosen, int
            ), f"AI play chosen_action should be int, got {type(chosen)}"
            assert (
                game_st != {}
            ), f"AI play decision turn={d.turn_number} has empty game_state"
            assert game_st.get("phase") == "trick_play"

        session.close()


# ---------------------------------------------------------------------------
# Test: Refresh/Resume proof (SP-3-02 Step 5)
# ---------------------------------------------------------------------------


def _advance_to_trick_play(client: TestClient, app, link_uuid: str):
    """Helper: advance game to human's trick-play turn.

    Returns (state, hand) at the point where the human can play a card,
    or calls ``pytest.fail`` if not reachable within safety limit.
    """
    for _ in range(20):
        advance_pending_reveals(client, app, link_uuid)
        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None:
            break

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            client.post(
                f"/play/{link_uuid}/bid",
                data={
                    "turn_number": hand.turn_number,
                    "bid_n": 0,
                    "bid_contract": "",
                },
            )
        elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
            return state, hand
        else:
            break

    pytest.fail("Never reached human's trick play turn")


def _complete_one_hand(client: TestClient, app, link_uuid: str):
    """Drive to a completed hand and return that state."""
    for _ in range(220):
        advance_pending_reveals(client, app, link_uuid)
        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        if state.status == "complete":
            pytest.fail("Match completed before one hand completed")

        hand = state.current_hand
        if hand is None:
            pytest.fail("Match ended without a current hand")

        if hand.phase == "complete":
            return state

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if hand.current_high_bid < 3:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": hand.current_high_bid + 1,
                        "bid_contract": "H",
                    },
                )
            else:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
        elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
            ai_manager = app.state.ai_manager
            info = ai_manager.get_model_info(state.ai_model)
            engine = MatchEngine(
                bidding_policy=info.bidding_policy,
                play_strategy=info.play_strategy,
            )
            legal = engine.get_legal_plays(state)
            client.post(
                f"/play/{link_uuid}/play-card",
                data={
                    "turn_number": hand.turn_number,
                    "card_index": legal[0],
                },
            )
        else:
            # Human is not on-turn and not in a completed hand.  Poll again
            # to make progress or fail out after safety limit.
            pass

    pytest.fail("Could not complete a hand within safety limit")


class TestRefreshResumeSafety:
    """Proves that GET /play/{uuid} restores correct state after any action.

    Covers SP-3-02 Step 5 acceptance criteria:
    1. Refresh mid-auction → resumes at correct bid state
    2. Refresh mid-trick → resumes with correct cards played
    3. Refresh between hands → shows correct hand result or next hand
    4. Double-click bid/play → idempotent (no state corruption)
    5. Navigate away + return → full state restored from DB
    """

    # ---- 1. Refresh mid-auction ------------------------------------------

    def test_refresh_mid_auction_shows_correct_bid_state(self, client, app):
        """GET /play/{uuid} mid-auction renders correct turn_number and auction data."""
        link_uuid = _setup_game(client)
        advance_pending_reveals(client, app, link_uuid)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None or hand.phase != "auction" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in auction position after game start")

        # Submit one bid (pass) to create mid-auction state
        turn_before = hand.turn_number
        client.post(
            f"/play/{link_uuid}/bid",
            data={"turn_number": turn_before, "bid_n": 0, "bid_contract": ""},
        )

        # "Refresh" — GET the page
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200

        # Verify the response reflects the DB-persisted state, not stale data
        result2 = get_match_state(app, link_uuid)
        assert result2 is not None
        state2, match_row2, session2 = result2

        # The match_state_json was updated by the bid route
        persisted = json.loads(match_row2.match_state_json)
        assert persisted["current_hand"] is not None

        # State has advanced past the pre-bid turn
        hand2 = state2.current_hand
        if hand2 is not None:
            assert (
                hand2.turn_number > turn_before
                or state2.hands_played > state.hands_played
            )

        # The GET response contains game board data from persisted state
        assert "game-board" in resp.text and "score-bar" in resp.text
        session2.close()

    # ---- 2. Refresh mid-trick --------------------------------------------

    def test_refresh_mid_trick_shows_cards_played(self, client, app):
        """GET /play/{uuid} mid-trick shows correct trick and cards."""
        link_uuid = _setup_game(client)

        state, hand = _advance_to_trick_play(client, app, link_uuid)

        # Play one card to create mid-trick state
        ai_manager = app.state.ai_manager
        info = ai_manager.get_model_info(state.ai_model)
        engine = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        legal = engine.get_legal_plays(state)
        turn_before = hand.turn_number

        client.post(
            f"/play/{link_uuid}/play-card",
            data={"turn_number": turn_before, "card_index": legal[0]},
        )

        # "Refresh" — GET the page
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200

        # Verify persisted state is consistent with the GET response
        result2 = get_match_state(app, link_uuid)
        assert result2 is not None
        state2, match_row2, session2 = result2

        persisted = json.loads(match_row2.match_state_json)

        # State has advanced from the card play
        if state2.current_hand is not None:
            assert (
                state2.current_hand.turn_number > turn_before
                or state2.hands_played > state.hands_played
            )

        # The GET response shows the game board, not an error page
        assert "game-board" in resp.text and "score-bar" in resp.text

        # Match state is self-consistent: round-trip serialize/deserialize
        engine2 = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        round_tripped = engine2.deserialize(persisted)
        assert round_tripped.score_human == state2.score_human
        assert round_tripped.score_ai == state2.score_ai
        assert round_tripped.hands_played == state2.hands_played
        session2.close()

    # ---- 3. Refresh between hands ----------------------------------------

    def test_refresh_between_hands_shows_correct_state(self, client, app):
        """GET /play/{uuid} after a hand completes shows next hand or result."""
        link_uuid = _setup_game(client)

        initial_result = get_match_state(app, link_uuid)
        assert initial_result is not None
        _, _, session = initial_result
        session.close()

        # Play through an entire hand
        hands_before = 0
        for _ in range(200):  # safety limit for one hand
            advance_pending_reveals(client, app, link_uuid)
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            if state.hands_played > hands_before:
                # A hand just completed — this is the "between hands" moment
                break

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                # Bid aggressively to avoid all-pass redeals
                if hand.current_high_bid < 3:
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": hand.current_high_bid + 1,
                            "bid_contract": "H",
                        },
                    )
                else:
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": 0,
                            "bid_contract": "",
                        },
                    )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
            else:
                break
        else:
            pytest.fail("Could not complete a hand within safety limit")

        # "Refresh" at the between-hands moment
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200

        # Verify the refresh shows valid game state
        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, match_row_after, session_after = result_after

        # Either the match is paused on the hand-result screen or completed
        assert state_after.hands_played >= 1
        if state_after.status == "active":
            assert state_after.current_hand is not None
            # Hand result should be visible before auto-advancing next hand
            assert state_after.current_hand.phase == "complete"
            assert state_after.score_human != 0 or state_after.score_ai != 0
            assert "hand-result" in resp.text
            assert "Next Hand" in resp.text
        elif state_after.status == "complete":
            assert state_after.winner in ("human", "ai")
            assert "match-result" in resp.text

        # GET rendered the persisted state, not stale or error
        assert "game-board" in resp.text
        if (
            state_after.current_hand is not None
            and state_after.current_hand.phase == "complete"
        ):
            assert "Next Hand" in resp.text
            assert "hand-result" in resp.text
        elif state_after.status == "active":
            assert "score-bar" in resp.text
        else:
            assert "match-result" in resp.text
        session_after.close()
        session_after.close()

    # ---- Next-hand flow --------------------------------------------------

    def test_next_hand_after_completion_advances_state(self, client, app):
        """POST /next-hand advances from completed hand to next hand."""
        link_uuid = _setup_game(client)
        state = _complete_one_hand(client, app, link_uuid)

        assert state.current_hand is not None
        assert state.current_hand.phase == "complete"
        assert state.status == "active"

        resp = client.post(f"/play/{link_uuid}/next-hand")
        assert resp.status_code == 200
        assert "game-board" in resp.text

        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, _, session_after = result_after

        # Hand transition starts a fresh non-complete hand
        assert state_after.current_hand is not None
        assert state_after.current_hand.phase in ("auction", "trick_play")
        assert state_after.hands_played == state.hands_played
        assert state_after.deal_id == state.current_hand.deal_id + 1
        assert state_after.dealer_seat == (state.dealer_seat + 1) % 4
        session_after.close()

    def test_next_hand_on_non_completed_hand_is_noop(self, client, app):
        """POST /next-hand is idempotent unless hand.phase == complete."""
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state_before, match_row_before, session_before = result

        # Game starts in auction/trick_play with a non-complete hand.
        hand_before = state_before.current_hand
        assert hand_before is not None
        assert hand_before.phase != "complete"

        prior_state_json = match_row_before.match_state_json
        resp = client.post(f"/play/{link_uuid}/next-hand")
        assert resp.status_code == 200

        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, match_row_after, session_after = result_after

        # No hand transition should happen
        assert state_after.current_hand is not None
        assert state_after.current_hand.phase == hand_before.phase
        assert state_after.current_hand.deal_id == hand_before.deal_id
        assert state_after.dealer_seat == state_before.dealer_seat
        assert prior_state_json == match_row_after.match_state_json
        session_after.close()
        session_before.close()

    # ---- 4a. Double-click bid → idempotent -------------------------------

    def test_double_click_bid_no_state_corruption(self, client, app):
        """Submitting the same bid turn_number twice causes no state corruption."""
        link_uuid = _setup_game(client)
        advance_pending_reveals(client, app, link_uuid)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None or hand.phase != "auction" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in auction position")

        turn = hand.turn_number
        bid_data = {"turn_number": turn, "bid_n": 0, "bid_contract": ""}

        # First submission
        resp1 = client.post(f"/play/{link_uuid}/bid", data=bid_data)
        assert resp1.status_code == 200

        # Capture state after first submission
        result1 = get_match_state(app, link_uuid)
        assert result1 is not None
        state1, match_row1, session1 = result1
        state_json_1 = match_row1.match_state_json
        session1.close()

        # "Double-click" — same turn_number
        resp2 = client.post(f"/play/{link_uuid}/bid", data=bid_data)
        assert resp2.status_code == 200

        # State must not have changed from the second submission
        result2 = get_match_state(app, link_uuid)
        assert result2 is not None
        state2, match_row2, session2 = result2

        assert match_row2.match_state_json == state_json_1
        assert state2.score_human == state1.score_human
        assert state2.score_ai == state1.score_ai
        assert state2.hands_played == state1.hands_played

        # Decision table: only one row for that turn_number on this hand
        session3 = app.state.session_factory()
        hand_rows = session3.query(Hand).filter_by(match_id=match_row2.id).all()
        if hand_rows:
            for hr in hand_rows:
                turn_decisions = (
                    session3.query(Decision)
                    .filter_by(hand_id=hr.id, turn_number=turn)
                    .all()
                )
                assert len(turn_decisions) <= 1, (
                    f"Duplicate decision rows for turn {turn}: "
                    f"found {len(turn_decisions)}"
                )
        session3.close()
        session2.close()

    # ---- 4b. Double-click play-card → idempotent -------------------------

    def test_double_click_play_card_no_state_corruption(self, client, app):
        """Submitting the same play-card turn_number twice causes no state corruption."""
        link_uuid = _setup_game(client)

        state, hand = _advance_to_trick_play(client, app, link_uuid)

        ai_manager = app.state.ai_manager
        info = ai_manager.get_model_info(state.ai_model)
        engine = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        legal = engine.get_legal_plays(state)
        turn = hand.turn_number
        play_data = {"turn_number": turn, "card_index": legal[0]}

        # First submission
        resp1 = client.post(f"/play/{link_uuid}/play-card", data=play_data)
        assert resp1.status_code == 200

        # Capture state after first submission
        result1 = get_match_state(app, link_uuid)
        assert result1 is not None
        state1, match_row1, session1 = result1
        state_json_1 = match_row1.match_state_json
        session1.close()

        # "Double-click" — same turn_number
        resp2 = client.post(f"/play/{link_uuid}/play-card", data=play_data)
        assert resp2.status_code == 200

        # State must not have changed from the second submission
        result2 = get_match_state(app, link_uuid)
        assert result2 is not None
        state2, match_row2, session2 = result2

        assert match_row2.match_state_json == state_json_1
        assert state2.score_human == state1.score_human
        assert state2.score_ai == state1.score_ai
        assert state2.hands_played == state1.hands_played
        session2.close()

    # ---- 5. Navigate away + return → full state restored -----------------

    def test_navigate_away_return_restores_full_state(self, client, app):
        """After several actions, navigating away and returning restores state."""
        link_uuid = _setup_game(client)

        # Play several turns to build up state
        actions_taken = 0
        for _ in range(15):
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, _, session = result
            session.close()

            hand = state.current_hand
            if hand is None:
                break

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                client.post(
                    f"/play/{link_uuid}/bid",
                    data={
                        "turn_number": hand.turn_number,
                        "bid_n": 0,
                        "bid_contract": "",
                    },
                )
                actions_taken += 1
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
                actions_taken += 1
            else:
                break

        assert actions_taken > 0, "Expected at least one action before navigate-away"

        # Snapshot the DB state before "navigating away"
        result_before = get_match_state(app, link_uuid)
        assert result_before is not None
        state_before, match_row_before, session_before = result_before
        snapshot_json = match_row_before.match_state_json
        score_h = state_before.score_human
        score_ai = state_before.score_ai
        hands_played = state_before.hands_played
        session_before.close()

        # "Navigate away" — visit the landing page
        resp_away = client.get("/")
        assert resp_away.status_code == 200

        # "Return" — GET /play/{uuid} again
        resp_return = client.get(f"/play/{link_uuid}")
        assert resp_return.status_code == 200

        # Verify the full state is restored from the DB
        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, match_row_after, session_after = result_after

        assert match_row_after.match_state_json == snapshot_json
        assert state_after.score_human == score_h
        assert state_after.score_ai == score_ai
        assert state_after.hands_played == hands_played
        assert "game-board" in resp_return.text
        if state_after.status == "active" and state_after.current_hand is not None:
            if state_after.current_hand.phase == "complete":
                assert "Next Hand" in resp_return.text
                assert "hand-result" in resp_return.text
            else:
                assert "score-bar" in resp_return.text
        else:
            assert "match-result" in resp_return.text
        session_after.close()

    # ---- 5b. Completed match → return shows result -----------------------

    def test_completed_match_resume_shows_result(self, client, app):
        """GET /play/{uuid} after match completion still shows valid state."""
        link_uuid = _setup_game(client)

        # Play to completion
        for _ in range(4000):
            result = get_match_state(app, link_uuid)
            assert result is not None
            state, match_row, session = result

            if state.status == "complete" or match_row.status == "complete":
                session.close()
                break

            hand = state.current_hand
            session.close()

            if hand is None:
                break

            if hand.phase == "complete" and state.status == "active":
                session.close()
                client.post(f"/play/{link_uuid}/next-hand")
                continue

            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                if hand.current_high_bid < 5:
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": hand.current_high_bid + 1,
                            "bid_contract": "H",
                        },
                    )
                else:
                    client.post(
                        f"/play/{link_uuid}/bid",
                        data={
                            "turn_number": hand.turn_number,
                            "bid_n": 0,
                            "bid_contract": "",
                        },
                    )
            elif hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                ai_manager = app.state.ai_manager
                info = ai_manager.get_model_info(state.ai_model)
                engine = MatchEngine(
                    bidding_policy=info.bidding_policy,
                    play_strategy=info.play_strategy,
                )
                legal = engine.get_legal_plays(state)
                client.post(
                    f"/play/{link_uuid}/play-card",
                    data={
                        "turn_number": hand.turn_number,
                        "card_index": legal[0],
                    },
                )
            elif hand.phase == "complete":
                client.post(f"/play/{link_uuid}/next-hand")
            else:
                break
        else:
            pytest.skip("Match did not complete within safety limit")

        # "Resume" the completed match
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200

        assert "match-result" in resp.text
        assert "Play Again" in resp.text


# ---------------------------------------------------------------------------
# Health & Readiness endpoints
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """GET /health — liveness probe."""

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        # Enhanced health includes metrics (B8 hardening)
        assert "active_matches" in body
        assert "total_players" in body
        assert "db_size_bytes" in body
        assert "uptime_seconds" in body

    def test_health_content_type_json(self, client):
        resp = client.get("/health")
        assert "application/json" in resp.headers["content-type"]


class TestReadyEndpoint:
    """GET /ready — readiness probe (DB connectivity)."""

    def test_ready_returns_ready(self, client):
        """With a healthy DB, /ready returns 200."""
        resp = client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {"status": "ready"}

    def test_ready_content_type_json(self, client):
        resp = client.get("/ready")
        assert "application/json" in resp.headers["content-type"]

    def test_ready_returns_503_when_db_unavailable(self, client):
        """When the DB is unreachable, /ready returns 503."""
        from unittest.mock import MagicMock

        app = client.app

        # Replace session_factory with one that raises on execute
        original_factory = app.state.session_factory

        def broken_factory():
            session = MagicMock()
            session.execute.side_effect = Exception("DB connection failed")
            return session

        app.state.session_factory = broken_factory
        try:
            resp = client.get("/ready")
            assert resp.status_code == 503
            body = resp.json()
            assert body == {"status": "unavailable"}
        finally:
            app.state.session_factory = original_factory

    def test_ready_returns_503_when_write_fails(self, client):
        """When the DB is read-only, /ready returns 503."""
        from unittest.mock import MagicMock

        app = client.app
        original_factory = app.state.session_factory

        def read_only_factory():
            session = MagicMock()

            def execute_side_effect(stmt, *args, **kwargs):
                sql = str(stmt).upper()
                if sql.startswith("SELECT"):
                    return MagicMock()
                raise Exception("read-only filesystem")

            session.execute.side_effect = execute_side_effect
            return session

        app.state.session_factory = read_only_factory
        try:
            resp = client.get("/ready")
            assert resp.status_code == 503
            body = resp.json()
            assert body == {"status": "unavailable"}
        finally:
            app.state.session_factory = original_factory


# ---------------------------------------------------------------------------
# Invite code flow
# ---------------------------------------------------------------------------


def _seed_invite_code(
    app, code: str = "TESTCODE", status: str = "active", label: str | None = None
) -> InviteCode:
    """Insert an invite code directly into the DB for testing."""
    session = app.state.session_factory()
    try:
        invite = InviteCode(code=code, status=status, label=label)
        session.add(invite)
        session.commit()
        session.refresh(invite)
        return invite
    finally:
        session.close()


class TestInviteCodeFlow:
    """Tests for invite-code gated access: /enter-code route."""

    def test_landing_shows_invite_form(self, client):
        """Landing page contains the invite code input."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "invite-code-input" in resp.text
        assert "Enter Invite Code" in resp.text

    def test_invalid_code_rejected(self, client):
        """POST /enter-code with an unknown code shows an error."""
        resp = client.post(
            "/enter-code",
            data={"code": "BADCODE1"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "Invalid invite code" in resp.text

    def test_revoked_code_rejected(self, client, app):
        """POST /enter-code with a revoked code shows an error."""
        _seed_invite_code(app, code="REVOKED1", status="revoked")
        resp = client.post(
            "/enter-code",
            data={"code": "REVOKED1"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "revoked" in resp.text.lower()

    def test_valid_code_redirects_to_game(self, client, app):
        """POST /enter-code with a valid active code redirects to /play/{uuid}."""
        _seed_invite_code(app, code="VALID001")
        resp = client.post(
            "/enter-code",
            data={"code": "VALID001"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "/play/" in location

    def test_valid_code_creates_player(self, client, app):
        """Valid code creates a Player row and binds the invite code."""
        _seed_invite_code(app, code="PLAYER01")
        resp = client.post(
            "/enter-code",
            data={"code": "PLAYER01"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        link_uuid = resp.headers["location"].split("/play/")[1]

        session = app.state.session_factory()
        try:
            player = session.query(Player).filter_by(link_uuid=link_uuid).first()
            assert player is not None

            invite = session.query(InviteCode).filter_by(code="PLAYER01").first()
            assert invite.status == "redeemed"
            assert invite.player_id == player.id
            assert invite.redeemed_at is not None
        finally:
            session.close()

    def test_redeemed_code_returns_same_player(self, client, app):
        """Re-entering a redeemed code redirects to the same player."""
        _seed_invite_code(app, code="REPEAT01")

        # First entry
        resp1 = client.post(
            "/enter-code",
            data={"code": "REPEAT01"},
            follow_redirects=False,
        )
        assert resp1.status_code == 302
        link1 = resp1.headers["location"]

        # Second entry — same code
        resp2 = client.post(
            "/enter-code",
            data={"code": "REPEAT01"},
            follow_redirects=False,
        )
        assert resp2.status_code == 302
        link2 = resp2.headers["location"]

        assert link1 == link2  # Same player link

    def test_code_case_insensitive(self, client, app):
        """Invite codes are normalized to uppercase."""
        _seed_invite_code(app, code="UPPER123")
        resp = client.post(
            "/enter-code",
            data={"code": "upper123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/play/" in resp.headers["location"]

    def test_code_whitespace_stripped(self, client, app):
        """Leading/trailing whitespace is stripped from code input."""
        _seed_invite_code(app, code="STRIP001")
        resp = client.post(
            "/enter-code",
            data={"code": "  STRIP001  "},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/play/" in resp.headers["location"]

    def test_full_invite_to_nickname_to_game_flow(self, client, app):
        """End-to-end: invite code → nickname → select AI → game board."""
        _seed_invite_code(app, code="E2E00001")

        # Enter code → redirect
        resp = client.post(
            "/enter-code",
            data={"code": "E2E00001"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        link_uuid = resp.headers["location"].split("/play/")[1]

        # Game page shows nickname form
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "nickname" in resp.text.lower()

        # Set nickname
        resp = _set_nickname(client, link_uuid, "InvitedUser")
        assert resp.status_code == 200

        # Select AI → game board rendered
        resp = _select_ai(client, link_uuid, "olsa")
        assert resp.status_code == 200

    def test_htmx_enter_code_returns_hx_redirect(self, client, app):
        """HTMX POST /enter-code returns HX-Redirect header."""
        _seed_invite_code(app, code="HTMX0001")
        resp = client.post(
            "/enter-code",
            data={"code": "HTMX0001"},
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert "HX-Redirect" in resp.headers
        assert "/play/" in resp.headers["HX-Redirect"]

    def test_legacy_new_route_still_works(self, client):
        """POST /new still creates a player (backwards compat)."""
        resp = client.post("/new", follow_redirects=False)
        assert resp.status_code == 302
        assert "/play/" in resp.headers["location"]


# ---------------------------------------------------------------------------
# Test: Moon exchange route — AI leads after exchange (#1910)
# ---------------------------------------------------------------------------


class TestMoonExchangeRoute:
    """Route-level tests for moon exchange flow.

    Regression test for #1910: when an AI bids moon, the game was stuck
    after the exchange because ``submit_exchange_selection`` did not call
    ``_advance_ai``.  The human saw trick play but no AI had played,
    making it appear as if the partner was "sitting out".
    """

    def test_ai_mooner_exchange_then_trick_play(self, client, app):
        """After AI moon exchange + reveal, the game is in a playable state.

        Sets up a state where AI Partner (seat 2) bid moon and the human
        is the exchange partner.  After submitting the exchange and clicking
        "Start Trick Play", the board must show trick play with the human's
        turn (AI should have already played via _advance_ai).
        """
        link_uuid = _setup_game(client)

        result = get_match_state(app, link_uuid)
        assert result is not None
        state, match_row, session = result

        hand = state.current_hand
        assert hand is not None

        # Simulate: AI Partner (seat 2) bid moon, auction complete.
        # Human (seat 0) is the exchange partner — interactive exchange.
        hand.phase = "moon_exchange"
        hand.exchange_phase = "selecting"
        hand.current_seat = HUMAN_SEAT
        hand.turn_number = 6
        hand.bidder_seat = 2  # AI Partner is the mooner
        hand.winning_bid = 10
        hand.bid_type = "moon"
        hand.contract_type = "suit"
        hand.trump = "S"
        hand.sitting_out_seat = None  # Moon = no sit-out
        hand.revealed_auction_count = len(hand.auction)
        hand.exchange_given = None
        hand.exchange_received = None
        hand.exchange_revealed = False
        # Give everyone valid 10-card hands (ranks use "T" for 10)
        hand.hands = [
            [
                Card("S", "A"),
                Card("S", "K"),
                Card("S", "Q"),
                Card("S", "J"),
                Card("S", "T"),
                Card("H", "A"),
                Card("H", "K"),
                Card("H", "Q"),
                Card("H", "J"),
                Card("H", "T"),
            ],
            [
                Card("D", "A"),
                Card("D", "K"),
                Card("D", "Q"),
                Card("D", "J"),
                Card("D", "T"),
                Card("C", "A"),
                Card("C", "K"),
                Card("C", "Q"),
                Card("C", "J"),
                Card("C", "T"),
            ],
            [
                Card("S", "A"),
                Card("S", "K"),
                Card("S", "Q"),
                Card("S", "J"),
                Card("S", "T"),
                Card("H", "A"),
                Card("H", "K"),
                Card("H", "Q"),
                Card("H", "J"),
                Card("H", "T"),
            ],
            [
                Card("D", "A"),
                Card("D", "K"),
                Card("D", "Q"),
                Card("D", "J"),
                Card("D", "T"),
                Card("C", "A"),
                Card("C", "K"),
                Card("C", "Q"),
                Card("C", "J"),
                Card("C", "T"),
            ],
        ]

        match_row.match_state_json = json.dumps(state.to_dict())
        session.commit()
        session.close()

        # Step 1: GET shows moon exchange selection form
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "exchange" in resp.text.lower()

        # Step 2: Submit exchange — human gives 2 cards
        resp = client.post(
            f"/play/{link_uuid}/exchange",
            data={"card_index_0": 0, "card_index_1": 1},
        )
        assert resp.status_code == 200

        # Step 3: After exchange, we should see the exchange interstitial
        # (exchange_revealed is False at this point)
        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "Moon Exchange" in resp.text
        assert "Start Trick Play" in resp.text

        # Step 4: Click "Start Trick Play" to reveal the exchange.
        # Human is the partner (seat 0) and sits out for moon — after
        # the reveal, _advance_ai auto-plays all 10 tricks, completing
        # the hand.  The response shows the hand result.
        resp = client.post(f"/play/{link_uuid}/next")
        assert resp.status_code == 200

        # Step 5: Verify the hand completed (human sat out)
        result_after = get_match_state(app, link_uuid)
        assert result_after is not None
        state_after, _, session_after = result_after
        hand_after = state_after.current_hand
        assert hand_after is not None
        assert hand_after.exchange_revealed is True
        assert (
            hand_after.sitting_out_seat == HUMAN_SEAT
        ), "Moon partner (human) should sit out"
        # Human sat out → AI auto-played all tricks → hand complete
        assert (
            hand_after.phase == "complete"
        ), f"Expected 'complete' (human sits out), got '{hand_after.phase}'"
        session_after.close()


# ---------------------------------------------------------------------------
# Match History
# ---------------------------------------------------------------------------


class TestMatchHistory:
    """GET /history/{link_uuid} shows completed matches."""

    def test_history_unknown_uuid_404(self, client):
        resp = client.get("/history/nonexistent-uuid")
        assert resp.status_code == 404

    def test_history_empty_when_no_completed_matches(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        resp = client.get(f"/history/{link_uuid}")
        assert resp.status_code == 200
        assert "No completed matches yet" in resp.text

    def test_history_shows_completed_match(self, client, app):
        """Create a completed match row directly and verify it appears."""
        from datetime import datetime, timezone

        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid, "HistoryTester")

        # Directly insert a completed match for this player
        session_factory = app.state.session_factory
        session = session_factory()
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        assert player is not None

        import uuid as uuid_mod

        completed_match = Match(
            match_uuid=str(uuid_mod.uuid4()),
            player_id=player.id,
            ai_model="bud_bot",
            status="complete",
            seed=42,
            score_human=52,
            score_ai=38,
            hands_played=7,
            match_state_json="{}",
            completed_at=datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
        session.add(completed_match)
        session.commit()
        session.close()

        resp = client.get(f"/history/{link_uuid}")
        assert resp.status_code == 200
        assert "Match History" in resp.text
        # Should show the AI opponent name
        assert "Bud Bot" in resp.text
        # Should show scores
        assert "52" in resp.text
        assert "38" in resp.text
        # Should show win result
        assert "Win" in resp.text
        # Should show hands played
        assert "7" in resp.text
        # Should show formatted date
        assert "Mar 15, 2026" in resp.text

    def test_history_shows_loss(self, client, app):
        """A match where AI wins should show 'Loss'."""
        from datetime import datetime, timezone

        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid, "Loser")

        session_factory = app.state.session_factory
        session = session_factory()
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()

        import uuid as uuid_mod

        lost_match = Match(
            match_uuid=str(uuid_mod.uuid4()),
            player_id=player.id,
            ai_model="olsa",
            status="complete",
            seed=99,
            score_human=30,
            score_ai=54,
            hands_played=9,
            match_state_json="{}",
            completed_at=datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc),
        )
        session.add(lost_match)
        session.commit()
        session.close()

        resp = client.get(f"/history/{link_uuid}")
        assert resp.status_code == 200
        assert "Loss" in resp.text
        assert "OLSa" in resp.text

    def test_history_excludes_active_matches(self, client, app):
        """Active (in-progress) matches should NOT appear in history."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        # Select AI starts an active match
        _select_ai(client, link_uuid)

        resp = client.get(f"/history/{link_uuid}")
        assert resp.status_code == 200
        # Active match should not appear — show empty state
        assert "No completed matches yet" in resp.text

    def test_history_nav_link_present(self, client):
        """The header nav should include a History link when link_uuid is set."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert f"/history/{link_uuid}" in resp.text


class TestTabNavigation:
    """Header tab navigation — active state, accessibility, and placeholder."""

    def test_game_tab_active_on_game_page(self, client):
        """Game tab is active when viewing the game page."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        # The Game tab should have the active class
        assert "header-nav__tab--active" in resp.text
        # Game tab link should be the one marked active (contains Game and active)
        assert "header-nav__tab header-nav__tab--active" in resp.text

    def test_leaderboard_tab_active_on_leaderboard_page(self, client):
        """Leaderboard tab is active when viewing the leaderboard."""
        link_uuid = _create_game(client)
        resp = client.get(f"/leaderboard/{link_uuid}")
        assert resp.status_code == 200
        assert "header-nav__tab--active" in resp.text
        # Should contain aria-selected="true" for the leaderboard tab
        assert 'aria-selected="true"' in resp.text

    def test_history_tab_active_on_history_page(self, client):
        """History tab is active when viewing the history page."""
        link_uuid = _create_game(client)
        resp = client.get(f"/history/{link_uuid}")
        assert resp.status_code == 200
        assert "header-nav__tab--active" in resp.text

    def test_comments_tab_disabled(self, client):
        """Comments tab is present but disabled with 'Coming soon' tooltip."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert "header-nav__tab--disabled" in resp.text
        assert "Coming soon" in resp.text
        assert "Comments" in resp.text
        assert 'aria-disabled="true"' in resp.text

    def test_tab_bar_uses_tablist_role(self, client):
        """The nav element uses role=tablist for accessibility."""
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        _select_ai(client, link_uuid)

        resp = client.get(f"/play/{link_uuid}")
        assert resp.status_code == 200
        assert 'role="tablist"' in resp.text

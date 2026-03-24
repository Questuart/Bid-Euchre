"""Integration tests for web.routes — FastAPI route handlers.

Uses FastAPI TestClient with an in-memory SQLite database for isolation.
Tests cover the full match lifecycle: create → nickname → select-ai →
bid → play-card → match completion → decision logging.
"""

from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.strategy.bidding import BidAction, BiddingObservation, BiddingPolicy
from web.ai_manager import AIManager, ModelInfo
from web.app import create_app
from web.config import HostedPlayConfig
from web.db import Decision, Hand, Match, Player

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config(tmp_path):
    """File-based SQLite config for test isolation.

    Uses a temp file rather than in-memory SQLite because in-memory
    databases aren't shared across different connections/threads.
    """
    db_path = tmp_path / "test.db"
    return HostedPlayConfig(database_url=f"sqlite:///{db_path}")


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


def _select_ai(client: TestClient, link_uuid: str, model_id: str = "heuristic"):
    """Select AI model and return the response."""
    return client.post(
        f"/play/{link_uuid}/select-ai",
        data={"model_id": model_id},
    )


def _get_match_state(app, link_uuid: str):
    """Load the current match state from the DB for assertions."""
    session_factory = app.state.session_factory
    session = session_factory()
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            # Check for completed matches
            match_row = (
                session.query(Match)
                .filter_by(player_id=player.id)
                .order_by(Match.created_at.desc())
                .first()
            )
        if match_row is None:
            return None
        ai_manager = app.state.ai_manager
        info = ai_manager.get_model_info(match_row.ai_model)
        engine = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        state = engine.deserialize(json.loads(match_row.match_state_json))
        return state, match_row, session
    except Exception:
        session.close()
        raise


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
        resp = _select_ai(client, link_uuid, "heuristic")
        assert resp.status_code == 200

        # Verify match exists in DB
        session_factory = app.state.session_factory
        session = session_factory()
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        match_row = session.query(Match).filter_by(player_id=player.id).first()
        assert match_row is not None
        assert match_row.status == "active"
        assert match_row.ai_model == "heuristic"

        # Verify match state has a current hand
        state_data = json.loads(match_row.match_state_json)
        assert state_data["current_hand"] is not None
        session.close()

    def test_select_invalid_model_rejected(self, client):
        link_uuid = _create_game(client)
        _set_nickname(client, link_uuid)
        resp = _select_ai(client, link_uuid, "nonexistent_model")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Test 4: Submit bid → state advances
# ---------------------------------------------------------------------------


class TestSubmitBid:
    """POST /play/{uuid}/bid advances the auction state."""

    def test_submit_bid_advances_state(self, client, app):
        link_uuid = _setup_game(client)

        # Get the current state to find the turn number
        result = _get_match_state(app, link_uuid)
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
            result2 = _get_match_state(app, link_uuid)
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
# Test 5: Submit card → state advances
# ---------------------------------------------------------------------------


class TestSubmitCard:
    """POST /play/{uuid}/play-card advances the trick play state."""

    def test_submit_card_advances_state(self, client, app):
        link_uuid = _setup_game(client)

        # We need to get to trick_play phase with the human's turn.
        # Keep bidding pass until the auction resolves.
        for _ in range(20):  # safety limit for redeals
            result = _get_match_state(app, link_uuid)
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
                result2 = _get_match_state(app, link_uuid)
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

        result = _get_match_state(app, link_uuid)
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
            result = _get_match_state(app, link_uuid)
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

        result = _get_match_state(app, link_uuid)
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
        # Should show game board with state data
        assert "score_human" in resp.text or "Game Board" in resp.text


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
            result = _get_match_state(app, link_uuid)
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
            else:
                # Not human's turn — something unexpected; break
                break

            turns_played += 1

        # If we get here, verify match eventually completed or we ran out of turns
        result = _get_match_state(app, link_uuid)
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
            result = _get_match_state(app, link_uuid)
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
    """GET / returns the landing page."""

    def test_landing_page(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Bid Euchre" in resp.text
        assert "New Game" in resp.text


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
        info = ai_manager.available_models["heuristic"]
        ai_manager.available_models["heuristic"] = ModelInfo(
            id=info.id,
            name=info.name,
            description=info.description,
            bidding_policy=_AlwaysPassBidder(),
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

        # Load the current match state to get the turn number
        result = _get_match_state(app, link_uuid)
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

        result = _get_match_state(app, link_uuid)
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
        result2 = _get_match_state(app, link_uuid)
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

"""Route handlers for the Bid Euchre browser game.

All game-action POSTs include ``turn_number`` for idempotent submission.
If the submitted turn doesn't match the current expected turn the POST
returns the current visible state without modifying anything.

Delegates game logic to :class:`~bid_euchre.hosted_play.engine.MatchEngine`;
no rule/scoring logic lives here.
"""

from __future__ import annotations

import html
import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.strategy.bidding import BidAction

from .ai_manager import AIManager
from .db import Decision, Hand, Match, Player

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_ai_manager(request: Request) -> AIManager:
    """Retrieve the AIManager stashed on ``app.state`` during startup."""
    return request.app.state.ai_manager


def _get_session(request: Request):
    """Create a new DB session from the factory on ``app.state``."""
    return request.app.state.session_factory()


def _build_engine(ai_manager: AIManager, model_id: str) -> MatchEngine:
    """Instantiate a MatchEngine for the given *model_id*."""
    info = ai_manager.get_model_info(model_id)
    return MatchEngine(
        bidding_policy=info.bidding_policy,
        play_strategy=info.play_strategy,
    )


def _serialize_state(engine: MatchEngine, state) -> str:
    """Serialize match state to JSON string."""
    return json.dumps(engine.serialize(state))


def _deserialize_state(engine: MatchEngine, data: str):
    """Deserialize match state from JSON string."""
    return engine.deserialize(json.loads(data))


def _ensure_hand_row(
    session,
    match_row: Match,
    hand_state,
    hand_number: int,
) -> Hand:
    """Get or create the Hand row for the current hand.

    Returns the existing row if it already exists for this
    (match_id, hand_number) pair; creates a new one otherwise.
    """
    hand_row = (
        session.query(Hand)
        .filter_by(match_id=match_row.id, hand_number=hand_number)
        .first()
    )
    if hand_row is None:
        hand_row = Hand(
            match_id=match_row.id,
            hand_number=hand_number,
            deal_id=hand_state.deal_id,
            dealer_seat=hand_state.dealer_seat,
            status="in_progress",
            hand_state_json=json.dumps(hand_state.to_dict()),
        )
        session.add(hand_row)
        session.flush()
    return hand_row


def _update_hand_row(hand_row: Hand, hand_state) -> None:
    """Sync a Hand row with completed/redeal hand state."""
    hand_row.hand_state_json = json.dumps(hand_state.to_dict())
    if hand_state.phase == "complete":
        hand_row.status = "complete"
        hand_row.winning_bid_n = hand_state.winning_bid
        hand_row.bidder_seat = hand_state.bidder_seat
        hand_row.contract_type = hand_state.contract_type
        hand_row.trump_suit = hand_state.trump
        hand_row.winning_contract = _winning_contract_code(hand_state)
        hand_row.tricks_team0 = hand_state.tricks_team0
        hand_row.tricks_team1 = hand_state.tricks_team1
        hand_row.points_team0 = hand_state.points_team0
        hand_row.points_team1 = hand_state.points_team1
        hand_row.completed_at = datetime.now(timezone.utc)
    elif hand_state.phase == "redeal":
        hand_row.status = "redeal"


def _winning_contract_code(hand_state) -> str | None:
    """Derive the winning_contract column value from hand state."""
    ct = hand_state.contract_type
    if ct is None:
        return None
    if ct == "suit":
        return hand_state.trump  # 'C', 'D', 'H', or 'S'
    return ct.upper()  # 'HIGH' or 'LOW'


def _update_match_row(match_row: Match, state) -> None:
    """Sync the Match row with current match state."""
    match_row.match_state_json = json.dumps(state.to_dict())
    match_row.score_human = state.score_human
    match_row.score_ai = state.score_ai
    match_row.hands_played = state.hands_played
    if state.status == "complete":
        match_row.status = "complete"
        match_row.completed_at = datetime.now(timezone.utc)


def _log_decision(
    session,
    match_row: Match,
    hand_row: Hand,
    turn_number: int,
    seat: int,
    phase: str,
    actor_type: str,
    decision_source: str,
    legal_actions: Any,
    chosen_action: Any,
    game_state: Any,
    decision_time_ms: int | None = None,
) -> None:
    """Insert a decision row (idempotent — skips if turn already logged)."""
    exists = (
        session.query(Decision)
        .filter_by(hand_id=hand_row.id, turn_number=turn_number)
        .first()
    )
    if exists is not None:
        return
    decision = Decision(
        match_id=match_row.id,
        hand_id=hand_row.id,
        turn_number=turn_number,
        seat=seat,
        phase=phase,
        actor_type=actor_type,
        decision_source=decision_source,
        legal_actions_json=json.dumps(legal_actions),
        chosen_action_json=json.dumps(chosen_action),
        game_state_json=json.dumps(game_state),
        decision_time_ms=decision_time_ms,
    )
    session.add(decision)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page — create game form."""
    return HTMLResponse(
        "<html><body>"
        "<h1>Bid Euchre</h1>"
        '<form method="post" action="/new">'
        '<button type="submit">New Game</button>'
        "</form>"
        "</body></html>"
    )


@router.post("/new")
async def create_game(request: Request):
    """Create a new game link and redirect to the play page."""
    session = _get_session(request)
    try:
        link_uuid = str(uuid.uuid4())
        player = Player(link_uuid=link_uuid)
        session.add(player)
        session.commit()
        return RedirectResponse(url=f"/play/{link_uuid}", status_code=302)
    finally:
        session.close()


@router.get("/play/{link_uuid}", response_class=HTMLResponse)
async def game_page(request: Request, link_uuid: str):
    """Game page — shows nickname prompt or game board."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # No nickname yet — show nickname prompt
        if not player.nickname:
            return HTMLResponse(
                "<html><body>"
                "<h2>Enter your nickname</h2>"
                f'<form method="post" action="/play/{link_uuid}/nickname"'
                f' hx-post="/play/{link_uuid}/nickname" hx-target="#main">'
                '<input name="nickname" required>'
                '<button type="submit">Set Nickname</button>'
                "</form>"
                "</body></html>"
            )

        # Check for an active match
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )

        if match_row is None:
            # No active match — show model selection
            ai_manager = _get_ai_manager(request)
            models = ai_manager.list_available()
            options = "".join(
                f'<option value="{m.id}">{m.name} — {m.description}</option>'
                for m in models
            )
            return HTMLResponse(
                "<html><body>"
                f"<h2>Welcome, {html.escape(player.nickname)}!</h2>"
                f'<form method="post" action="/play/{link_uuid}/select-ai">'
                f'<select name="model_id">{options}</select>'
                '<button type="submit">Start Match</button>'
                "</form>"
                "</body></html>"
            )

        # Active match — show game board
        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        state = _deserialize_state(engine, match_row.match_state_json)
        visible = engine.get_visible_state(state)
        return HTMLResponse(
            "<html><body>"
            f"<h2>Game Board — {html.escape(player.nickname)}</h2>"
            f"<pre>{json.dumps(visible, indent=2)}</pre>"
            "</body></html>"
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/nickname", response_class=HTMLResponse)
async def set_nickname(
    request: Request,
    link_uuid: str,
    nickname: str = Form(...),
):
    """Set the player's nickname."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        player.nickname = nickname
        session.commit()

        # Return model selection form
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        options = "".join(
            f'<option value="{m.id}">{m.name} — {m.description}</option>'
            for m in models
        )
        return HTMLResponse(
            f"<h2>Welcome, {html.escape(nickname)}!</h2>"
            f'<form method="post" action="/play/{link_uuid}/select-ai">'
            f'<select name="model_id">{options}</select>'
            '<button type="submit">Start Match</button>'
            "</form>"
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/select-ai", response_class=HTMLResponse)
async def select_ai(
    request: Request,
    link_uuid: str,
    model_id: str = Form(...),
):
    """Select AI model, create match, deal first hand."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        ai_manager = _get_ai_manager(request)
        try:
            ai_manager.get_model_info(model_id)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")

        engine = _build_engine(ai_manager, model_id)
        seed = random.Random().randint(0, 2**31 - 1)
        state = engine.start_match(seed=seed, ai_model=model_id)

        match_uuid = str(uuid.uuid4())
        match_row = Match(
            match_uuid=match_uuid,
            player_id=player.id,
            ai_model=model_id,
            status="active",
            seed=seed,
            match_state_json=_serialize_state(engine, state),
        )
        session.add(match_row)
        session.flush()

        # Create the initial hand row
        if state.current_hand is not None:
            _ensure_hand_row(session, match_row, state.current_hand, state.hands_played)

        session.commit()

        visible = engine.get_visible_state(state)
        return HTMLResponse(
            f"<h2>Match started!</h2><pre>{json.dumps(visible, indent=2)}</pre>"
        )
    finally:
        session.close()


@router.post("/play/{link_uuid}/bid", response_class=HTMLResponse)
async def submit_bid(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    bid_n: int = Form(...),
    bid_contract: str = Form(None),
):
    """Submit a bid action."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        state = _deserialize_state(engine, match_row.match_state_json)

        # Idempotency check
        hand = state.current_hand
        if hand is None or turn_number < hand.turn_number:
            visible = engine.get_visible_state(state)
            return HTMLResponse(f"<pre>{json.dumps(visible, indent=2)}</pre>")

        # Validate phase
        if hand.phase != "auction":
            raise HTTPException(status_code=400, detail="Not in auction phase")
        if hand.current_seat != HUMAN_SEAT:
            raise HTTPException(status_code=400, detail="Not the human's turn")

        # Build bid action
        if bid_n == 0:
            bid = BidAction.pass_bid()
        else:
            if bid_contract is None:
                raise HTTPException(
                    status_code=400, detail="bid_contract required for non-pass bids"
                )
            bid = BidAction.bid(bid_n, bid_contract)

        # Validate legality
        legal_bids = engine.get_legal_bids(state)
        if not any(b.n == bid.n and b.contract == bid.contract for b in legal_bids):
            raise HTTPException(status_code=400, detail="Illegal bid")

        # Record pre-action state for decision logging
        pre_turn = hand.turn_number
        hand_number = state.hands_played

        # Ensure hand row exists
        hand_row = _ensure_hand_row(session, match_row, hand, hand_number)

        # Log human decision
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=pre_turn,
            seat=HUMAN_SEAT,
            phase="bid",
            actor_type="human",
            decision_source="human",
            legal_actions=[{"n": b.n, "contract": b.contract} for b in legal_bids],
            chosen_action={"n": bid.n, "contract": bid.contract},
            game_state=engine.get_visible_state(state),
        )

        # Apply action — engine auto-advances AI
        prev_turn = hand.turn_number
        state = engine.submit_human_bid(state, bid)

        # Log AI decisions that occurred during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            state,
            prev_turn,
            "bid",
        )

        # Update hand row if hand completed
        current_hand = state.current_hand
        if current_hand is not None and current_hand.phase in ("complete", "redeal"):
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        # If a new hand started, ensure its row exists
        if state.hands_played > hand_number and state.current_hand is not None:
            _ensure_hand_row(session, match_row, state.current_hand, state.hands_played)

        _update_match_row(match_row, state)
        session.commit()

        visible = engine.get_visible_state(state)
        return HTMLResponse(f"<pre>{json.dumps(visible, indent=2)}</pre>")
    finally:
        session.close()


@router.post("/play/{link_uuid}/play-card", response_class=HTMLResponse)
async def submit_card(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    card_index: int = Form(...),
):
    """Submit a card play action."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            raise HTTPException(status_code=404, detail="No active match")

        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        state = _deserialize_state(engine, match_row.match_state_json)

        # Idempotency check
        hand = state.current_hand
        if hand is None or turn_number < hand.turn_number:
            visible = engine.get_visible_state(state)
            return HTMLResponse(f"<pre>{json.dumps(visible, indent=2)}</pre>")

        # Validate phase
        if hand.phase != "trick_play":
            raise HTTPException(status_code=400, detail="Not in trick play phase")
        if hand.current_seat != HUMAN_SEAT:
            raise HTTPException(status_code=400, detail="Not the human's turn")

        # Validate legality
        legal_plays = engine.get_legal_plays(state)
        if card_index not in legal_plays:
            raise HTTPException(status_code=400, detail="Illegal card play")

        # Record pre-action state for decision logging
        pre_turn = hand.turn_number
        hand_number = state.hands_played

        # Ensure hand row exists
        hand_row = _ensure_hand_row(session, match_row, hand, hand_number)

        # Log human decision
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=pre_turn,
            seat=HUMAN_SEAT,
            phase="play",
            actor_type="human",
            decision_source="human",
            legal_actions=legal_plays,
            chosen_action=card_index,
            game_state=engine.get_visible_state(state),
        )

        # Apply action — engine auto-advances AI
        prev_turn = hand.turn_number
        state = engine.submit_human_card(state, card_index)

        # Log AI decisions that occurred during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            state,
            prev_turn,
            "play",
        )

        # Update hand row if hand completed
        current_hand = state.current_hand
        if current_hand is not None and current_hand.phase in ("complete", "redeal"):
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        # If a new hand started, ensure its row exists
        if state.hands_played > hand_number and state.current_hand is not None:
            _ensure_hand_row(session, match_row, state.current_hand, state.hands_played)

        _update_match_row(match_row, state)
        session.commit()

        visible = engine.get_visible_state(state)
        return HTMLResponse(f"<pre>{json.dumps(visible, indent=2)}</pre>")
    finally:
        session.close()


@router.post("/play/{link_uuid}/new-match", response_class=HTMLResponse)
async def new_match(
    request: Request,
    link_uuid: str,
):
    """Start a new match (after a previous one completed)."""
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Return model selection form
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        options = "".join(
            f'<option value="{m.id}">{m.name} — {m.description}</option>'
            for m in models
        )
        return HTMLResponse(
            f"<h2>New Match — {html.escape(player.nickname)}</h2>"
            f'<form method="post" action="/play/{link_uuid}/select-ai">'
            f'<select name="model_id">{options}</select>'
            '<button type="submit">Start Match</button>'
            "</form>"
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# AI decision logging helper
# ---------------------------------------------------------------------------


def _log_ai_decisions_after_advance(
    session,
    match_row: Match,
    hand_row: Hand,
    state,
    prev_turn: int,
    calling_phase: str,
) -> None:
    """Log AI decisions that occurred between prev_turn and current turn.

    After the engine auto-advances AI turns, we know AI acted for every
    turn_number between ``prev_turn + 1`` and the current turn_number.

    *calling_phase* is ``"bid"`` or ``"play"`` (matching the DB constraint)
    and is passed from the calling route handler.

    Note: The engine doesn't expose per-step callbacks, so legal actions
    and game states for intermediate AI turns are recorded as empty
    placeholders.  This is a known V1 limitation.
    """
    current_hand = state.current_hand
    if current_hand is None:
        return

    current_turn = current_hand.turn_number
    ai_model = state.ai_model

    for t in range(prev_turn + 1, current_turn):
        # Simplified seat calculation — approximation for V1
        seat = (HUMAN_SEAT + 1 + (t - prev_turn - 1)) % 4
        if seat == HUMAN_SEAT:
            continue  # Skip — human turns are logged separately

        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=t,
            seat=seat,
            phase=calling_phase,
            actor_type="ai",
            decision_source=ai_model,
            legal_actions=[],
            chosen_action={},
            game_state={},
        )

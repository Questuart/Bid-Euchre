"""Route handlers for the Bid Euchre browser game.

All game-action POSTs include ``turn_number`` for idempotent submission.
If the submitted turn doesn't match the current expected turn the POST
returns the current visible state without modifying anything.

Delegates game logic to :class:`~bid_euchre.hosted_play.engine.MatchEngine`;
no rule/scoring logic lives here.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text
from starlette.templating import Jinja2Templates

from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.strategy.bidding import BidAction

from .ai_manager import AIManager
from .db import Decision, Hand, InviteCode, Match, Player
from .middleware import check_match_limit

router = APIRouter()

_AI_MODEL_DISPLAY_NAMES = {
    "olsa": "OLSa",
    "bud_bot": "Bud Bot",
}
_PLAY_POLICY_DISPLAY_NAME = "Glutton"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_templates(request: Request) -> Jinja2Templates:
    """Retrieve the Jinja2Templates stashed on ``app.state`` during startup."""
    return request.app.state.templates


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
        hand_row.winning_bid_type = hand_state.bid_type
        hand_row.bidder_seat = hand_state.bidder_seat
        hand_row.sitting_out_seat = hand_state.sitting_out_seat
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


def _game_phase(state) -> str:
    """Map engine state to the template ``phase`` variable.

    The ``game.html`` template dispatches on this value to select which
    partials to include.
    """
    if state.status == "complete":
        return "match_result"
    hand = state.current_hand
    if hand is None:
        return "model_select"
    if hand.phase == "complete":
        return "hand_result"
    # "auction", "trick_play", or "redeal" pass through directly
    return hand.phase


def _has_hidden_auction(hand) -> bool:
    return hand.revealed_auction_count < len(hand.auction)


def _has_hidden_tricks(hand) -> bool:
    if hand.phase == "complete":
        return False
    return hand.revealed_trick_count < len(hand.completed_tricks)


def _reveal_initial_step(state) -> None:
    """Reveal the first pending hidden step so a new board is not blank."""
    hand = state.current_hand
    if hand is None:
        return
    if len(hand.auction) > 0 and hand.revealed_auction_count == 0:
        hand.revealed_auction_count = 1
    elif len(hand.completed_tricks) > 0 and hand.revealed_trick_count == 0:
        hand.revealed_trick_count = 1


def _reveal_after_human_action(
    state,
    *,
    prior_auction_count: int,
    prior_revealed_auction_count: int,
    prior_trick_count: int,
    prior_revealed_trick_count: int,
) -> None:
    """Reveal the human's own newly created action/trick immediately."""
    hand = state.current_hand
    if hand is None:
        return

    if len(hand.auction) > prior_auction_count:
        hand.revealed_auction_count = min(
            prior_revealed_auction_count + 1,
            len(hand.auction),
        )

    if len(hand.completed_tricks) > prior_trick_count:
        hand.revealed_trick_count = min(
            prior_revealed_trick_count + 1,
            len(hand.completed_tricks),
        )


def _reveal_next_step(state) -> bool:
    """Advance one hidden reveal step if any exist."""
    hand = state.current_hand
    if hand is None:
        return False
    if _has_hidden_auction(hand):
        hand.revealed_auction_count += 1
        return True
    if _has_hidden_tricks(hand):
        hand.revealed_trick_count += 1
        return True
    return False


def _display_phase(state) -> str:
    """Map engine state plus reveal cursors to the UI phase."""
    if state.status == "complete":
        return "match_result"

    hand = state.current_hand
    if hand is None:
        return "model_select"
    if hand.phase == "complete":
        return "hand_result"
    if hand.phase in {"moon_exchange", "moon_exchange_review"}:
        return hand.phase
    if _has_hidden_auction(hand) or hand.phase == "redeal":
        return "auction"
    if _has_hidden_tricks(hand):
        return "trick_play"
    return hand.phase


def _summarize_auction(entries: list[dict[str, Any]]) -> tuple[int, str]:
    """Return (current_high_bid, bid_type) for the revealed auction only."""
    current_high_bid = 0
    current_bid_type = "regular"

    for entry in entries:
        if entry.get("action") == "pass":
            continue
        bid_type = entry.get("bid_type", "regular")
        n = int(entry.get("n", 0))
        if bid_type == "regular":
            current_high_bid = max(current_high_bid, n)
            current_bid_type = "regular"
        elif bid_type == "moon":
            current_high_bid = 10
            current_bid_type = "moon"
        elif bid_type == "loner":
            current_high_bid = 10
            current_bid_type = "loner"

    return current_high_bid, current_bid_type


def _format_auction_event(seat: int | None, action: dict[str, Any]) -> str:
    """Format a single auction event for the action rail."""
    seat_labels = {0: "You", 1: "AI Left", 2: "AI Partner", 3: "AI Right"}
    seat_label = seat_labels.get(int(seat), f"Seat {seat}")

    if action.get("action") == "pass":
        return f"{seat_label} passed"

    bid_type = action.get("bid_type", "regular")
    if bid_type == "moon":
        return f"{seat_label} bid Moon"
    if bid_type == "loner":
        return f"{seat_label} bid Loner"

    # Regular bid
    n = action.get("n", 0)
    contract = action.get("contract", "")
    if contract == "HIGH":
        contract_label = "High"
    elif contract == "LOW":
        contract_label = "Low"
    else:
        contract_label = str(contract)
    return f"{seat_label} bid {n} {contract_label}"


def _build_action_rail(visible: dict[str, Any], state) -> list[dict[str, str]]:
    """Build an event feed from auction/trick/redeal transitions.

    The list is capped to the most recent 12 entries for compact rendering.
    """
    hand = state.current_hand
    if hand is None:
        return []

    seat_labels = {0: "You", 1: "AI Left", 2: "AI Partner", 3: "AI Right"}
    events: list[dict[str, str]] = []
    revealed_auction = visible.get("auction", [])[: hand.revealed_auction_count]
    revealed_trick_count = (
        len(visible.get("completed_tricks", []))
        if hand.phase == "complete"
        else hand.revealed_trick_count
    )
    revealed_tricks = visible.get("completed_tricks", [])[:revealed_trick_count]

    # Auction activity (in order).
    for entry in revealed_auction:
        events.append(
            {
                "kind": "auction",
                "text": _format_auction_event(entry.get("seat"), entry),
            }
        )

    # Completed tricks so the user can inspect a simple event log.
    for idx, trick in enumerate(revealed_tricks, start=1):
        winner = trick.get("winner")
        if winner is None:
            continue
        winner_label = seat_labels.get(int(winner), f"Seat {winner}")
        events.append(
            {
                "kind": "trick",
                "text": f"{winner_label} won trick #{idx}",
            }
        )

    # Redeal transition.
    if hand.phase == "redeal" and not _has_hidden_auction(hand):
        events.append(
            {"kind": "system", "text": "All players passed; redeal starting."}
        )

    # Hand-complete outcomes (compact summary).
    if hand.phase == "complete" and not _has_hidden_tricks(hand):
        bidder = seat_labels.get(hand.bidder_seat, f"Seat {hand.bidder_seat}")
        if hand.contract_type == "suit" and hand.trump is not None:
            contract = hand.trump
        elif hand.contract_type == "high":
            contract = "High"
        elif hand.contract_type == "low":
            contract = "Low"
        elif hand.winning_bid is None:
            contract = "No contract"
        else:
            contract = str(hand.winning_bid)

        bid_type = hand.bid_type
        if bid_type == "moon":
            contract_label = "Moon"
        elif bid_type == "loner":
            contract_label = "Loner"
        elif hand.winning_bid is None:
            contract_label = "No contract"
        else:
            contract_label = f"{hand.winning_bid} {contract}"

        events.append(
            {
                "kind": "system",
                "text": (
                    f"Hand complete: {bidder} made {contract_label}; "
                    f"scores {state.score_human} vs {state.score_ai}"
                ),
            }
        )

    return events[-12:]


def _build_game_context(
    engine: MatchEngine,
    state,
    link_uuid: str,
) -> dict[str, Any]:
    """Build the Jinja2 template context for the game board.

    Combines visible state (from ``engine.get_visible_state``) with additional
    fields needed by the partials (winning_bid, bidder_seat, current_high_bid,
    points, legal plays, AI hand counts).
    """
    visible = engine.get_visible_state(state)
    hand = state.current_hand

    ctx: dict[str, Any] = {
        "link_uuid": link_uuid,
        "match_status": state.status,
        "ai_model_name": _AI_MODEL_DISPLAY_NAMES.get(state.ai_model, state.ai_model),
        "play_policy_name": _PLAY_POLICY_DISPLAY_NAME,
        **visible,
    }
    ctx["phase"] = _display_phase(state)

    # Fields only available from hand state (not in visible dict)
    if hand is not None:
        revealed_auction = visible.get("auction", [])[: hand.revealed_auction_count]
        revealed_trick_count = (
            len(visible.get("completed_tricks", []))
            if hand.phase == "complete"
            else hand.revealed_trick_count
        )
        revealed_tricks = visible.get("completed_tricks", [])[:revealed_trick_count]
        has_hidden_auction = _has_hidden_auction(hand)
        has_hidden_tricks = _has_hidden_tricks(hand)
        current_high_bid, current_bid_type = _summarize_auction(revealed_auction)

        ctx["auction"] = revealed_auction
        ctx["completed_tricks"] = revealed_tricks
        if has_hidden_auction or has_hidden_tricks or ctx["phase"] == "auction":
            ctx["current_trick"] = None
        ctx["winning_bid"] = hand.winning_bid
        ctx["bidder_seat"] = hand.bidder_seat
        ctx["current_high_bid"] = (
            current_high_bid if has_hidden_auction else hand.current_high_bid
        )
        ctx["bid_type"] = current_bid_type if has_hidden_auction else hand.bid_type
        ctx["points_team0"] = hand.points_team0
        ctx["points_team1"] = hand.points_team1
        ctx["action_rail"] = _build_action_rail(visible, state)
        ctx["show_next"] = (
            has_hidden_auction or has_hidden_tricks or hand.phase == "redeal"
        )
        ctx["next_reason"] = (
            "auction"
            if has_hidden_auction
            else "trick"
            if has_hidden_tricks
            else "redeal"
            if hand.phase == "redeal"
            else None
        )
        ctx["show_turn_marker"] = not ctx["show_next"]
        ctx["can_submit_bid"] = (
            ctx["phase"] == "auction"
            and hand.phase == "auction"
            and hand.current_seat == HUMAN_SEAT
            and not has_hidden_auction
        )
        ctx["can_play_card"] = (
            ctx["phase"] == "trick_play"
            and hand.phase == "trick_play"
            and hand.current_seat == HUMAN_SEAT
            and not has_hidden_tricks
        )

        # Legal plays for the hand partial
        if ctx["can_play_card"]:
            ctx["legal_plays"] = engine.get_legal_plays(state)
        else:
            ctx["legal_plays"] = None

        # AI hand card counts (face-down display)
        ctx["opp_left_count"] = len(hand.hands[1]) if len(hand.hands) > 1 else 0
        ctx["partner_count"] = len(hand.hands[2]) if len(hand.hands) > 2 else 0
        ctx["opp_right_count"] = len(hand.hands[3]) if len(hand.hands) > 3 else 0
    else:
        ctx["winning_bid"] = None
        ctx["bidder_seat"] = None
        ctx["current_high_bid"] = 0
        ctx["points_team0"] = 0
        ctx["points_team1"] = 0
        ctx["legal_plays"] = None
        ctx["show_next"] = False
        ctx["next_reason"] = None
        ctx["show_turn_marker"] = True
        ctx["can_submit_bid"] = False
        ctx["can_play_card"] = False
        ctx["opp_left_count"] = 0
        ctx["partner_count"] = 0
        ctx["opp_right_count"] = 0
        ctx["action_rail"] = []

    return ctx


def _render_game_board(
    request: Request,
    engine: MatchEngine,
    state,
    link_uuid: str,
) -> str:
    """Render the game board composite partial as an HTML string.

    Returns the inner HTML for the ``#game-board`` div — used by HTMX
    partial POST responses.
    """
    templates = _get_templates(request)
    ctx = _build_game_context(engine, state, link_uuid)
    ctx["request"] = request
    return templates.get_template("partials/game_board.html").render(ctx)


# ---------------------------------------------------------------------------
# Health / Readiness
# ---------------------------------------------------------------------------


@router.get("/health")
async def health(request: Request):
    """Liveness probe with operational metrics.

    Always returns 200 OK.  Includes ``active_matches``,
    ``total_players``, ``db_size_bytes`` (SQLite only, -1 otherwise),
    and ``uptime_seconds`` for operational observability.
    """
    info: dict[str, Any] = {"status": "ok"}

    try:
        session = _get_session(request)
        try:
            info["active_matches"] = (
                session.query(Match).filter_by(status="active").count()
            )
            info["total_players"] = session.query(Player).count()

            # DB file size — only meaningful for SQLite file-based databases
            db_url = str(request.app.state.engine.url)
            if db_url.startswith("sqlite:///") and ":memory:" not in db_url:
                import os

                db_path = db_url.replace("sqlite:///", "")
                try:
                    info["db_size_bytes"] = os.path.getsize(db_path)
                except OSError:
                    info["db_size_bytes"] = -1
            else:
                info["db_size_bytes"] = -1
        finally:
            session.close()
    except Exception:
        info["active_matches"] = -1
        info["total_players"] = -1
        info["db_size_bytes"] = -1

    # Uptime
    started_at = getattr(request.app.state, "started_at", None)
    if started_at is not None:
        delta = datetime.now(timezone.utc) - started_at
        info["uptime_seconds"] = int(delta.total_seconds())
    else:
        info["uptime_seconds"] = -1

    return JSONResponse(info)


@router.get("/ready")
async def ready(request: Request):
    """Readiness probe — checks DB read and write capability.

    Returns 200 if the database supports both reads and writes, 503 otherwise.
    """
    try:
        session = _get_session(request)
        try:
            # Read check
            session.execute(text("SELECT 1"))
            # Write check — session-scoped temp table, cleaned up on close
            session.execute(
                text("CREATE TEMPORARY TABLE IF NOT EXISTS _ready_check (v INTEGER)")
            )
            session.execute(text("INSERT INTO _ready_check (v) VALUES (1)"))
            session.execute(text("DELETE FROM _ready_check"))
        finally:
            session.close()
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    """Landing page — invite code entry form."""
    templates = _get_templates(request)
    return templates.TemplateResponse("landing.html", {"request": request})


@router.post("/enter-code")
async def enter_code(
    request: Request,
    code: str = Form(...),
):
    """Validate an invite code and redirect to the game.

    If the code is valid and unused, creates a new Player and binds the
    code.  If the code was already redeemed, returns the existing player's
    link.  Invalid or revoked codes show an error on the landing page.

    HTMX-aware: when the request comes from HTMX, returns an HX-Redirect
    header so the client performs a full navigation to the game page.
    """
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        normalized = code.strip().upper()
        invite = session.query(InviteCode).filter_by(code=normalized).first()

        # --- Reject invalid / revoked codes ---
        if invite is None:
            ctx = {"request": request, "error": "Invalid invite code."}
            return HTMLResponse(
                templates.get_template("partials/invite_code_form.html").render(ctx),
                status_code=200,
            )

        if invite.status == "revoked":
            ctx = {
                "request": request,
                "error": "This invite code has been revoked.",
            }
            return HTMLResponse(
                templates.get_template("partials/invite_code_form.html").render(ctx),
                status_code=200,
            )

        # --- Already redeemed — return existing player link ---
        if invite.status == "redeemed" and invite.player_id is not None:
            player = session.query(Player).get(invite.player_id)
            if player is not None:
                redirect_url = f"/play/{player.link_uuid}"
                # HTMX-aware redirect
                if request.headers.get("HX-Request"):
                    return HTMLResponse(
                        "",
                        headers={"HX-Redirect": redirect_url},
                    )
                return RedirectResponse(url=redirect_url, status_code=302)

        # --- Active code — create player and redeem ---
        link_uuid = str(uuid.uuid4())
        player = Player(link_uuid=link_uuid)
        session.add(player)
        session.flush()

        invite.status = "redeemed"
        invite.player_id = player.id
        invite.redeemed_at = datetime.now(timezone.utc)
        session.commit()

        redirect_url = f"/play/{link_uuid}"
        # HTMX-aware redirect
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                "",
                headers={"HX-Redirect": redirect_url},
            )
        return RedirectResponse(url=redirect_url, status_code=302)
    finally:
        session.close()


@router.post("/new")
async def create_game(request: Request):
    """Create a new game link and redirect to the play page.

    Legacy route — kept for backwards compatibility.  New pilot access
    goes through ``/enter-code``.
    """
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
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # No nickname yet — show nickname prompt
        if not player.nickname:
            return templates.TemplateResponse(
                "game.html",
                {
                    "request": request,
                    "phase": "nickname",
                    "link_uuid": link_uuid,
                },
            )

        # Show the latest match for this player, including completed matches.
        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id)
            .order_by(Match.created_at.desc())
            .first()
        )

        if match_row is None:
            # No usable match — show model selection
            ai_manager = _get_ai_manager(request)
            models = ai_manager.list_available()
            return templates.TemplateResponse(
                "game.html",
                {
                    "request": request,
                    "phase": "model_select",
                    "link_uuid": link_uuid,
                    "nickname": player.nickname,
                    "models": models,
                },
            )

        # Active or completed match — restore current state
        ai_manager = _get_ai_manager(request)
        engine = _build_engine(ai_manager, match_row.ai_model)
        state = _deserialize_state(engine, match_row.match_state_json)
        ctx = _build_game_context(engine, state, link_uuid)
        ctx["request"] = request
        ctx["nickname"] = player.nickname
        return templates.TemplateResponse("game.html", ctx)
    finally:
        session.close()


@router.post("/play/{link_uuid}/nickname", response_class=HTMLResponse)
async def set_nickname(
    request: Request,
    link_uuid: str,
    nickname: str = Form(...),
):
    """Set the player's nickname."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        player.nickname = nickname
        session.commit()

        # Return model selection form (HTMX partial)
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        return HTMLResponse(
            templates.get_template("partials/model_select.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": nickname,
                    "models": models,
                }
            )
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

        # Rate limit — max active matches per player
        if not check_match_limit(session, player_id=player.id):
            raise HTTPException(
                status_code=429,
                detail="Match limit reached — complete or abandon an existing match first",
            )

        ai_manager = _get_ai_manager(request)
        try:
            ai_manager.get_model_info(model_id)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown model: {model_id}")

        engine = _build_engine(ai_manager, model_id)
        seed = random.Random().randint(0, 2**31 - 1)
        state = engine.start_match(seed=seed, ai_model=model_id)
        _reveal_initial_step(state)

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

        # Create the initial hand row (use deal_id as hand_number to stay
        # unique even when redeals occur before any hand completes)
        if state.current_hand is not None:
            _ensure_hand_row(
                session, match_row, state.current_hand, state.current_hand.deal_id
            )

        session.commit()

        # Return game board (HTMX partial)
        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/bid", response_class=HTMLResponse)
async def submit_bid(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    bid_n: int = Form(...),
    bid_contract: str = Form(None),
    bid_type: str = Form("regular"),
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
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

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
            if bid_type == "moon":
                bid = BidAction.moon(bid_contract)
            elif bid_type == "loner":
                bid = BidAction.loner(bid_contract)
            else:
                bid = BidAction.bid(bid_n, bid_contract)

        # Validate legality using overcall-aware comparison
        legal_bids = engine.get_legal_bids(state)
        if not any(
            b.n == bid.n and b.contract == bid.contract and b.bid_type == bid.bid_type
            for b in legal_bids
        ):
            raise HTTPException(status_code=400, detail="Illegal bid")

        # Record pre-action state for decision logging
        pre_turn = hand.turn_number
        prior_auction_count = len(hand.auction)
        prior_revealed_auction_count = hand.revealed_auction_count
        prior_trick_count = len(hand.completed_tricks)
        prior_revealed_trick_count = hand.revealed_trick_count

        # Ensure hand row exists (keyed by deal_id for redeal-safe uniqueness)
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

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
            legal_actions=[
                {"n": b.n, "contract": b.contract, "bid_type": b.bid_type}
                for b in legal_bids
            ],
            chosen_action={
                "n": bid.n,
                "contract": bid.contract,
                "bid_type": bid.bid_type,
            },
            game_state=engine.get_visible_state(state),
        )

        # Apply action — engine auto-advances AI
        state = engine.submit_human_bid(state, bid)

        # Log AI decisions captured during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        _reveal_after_human_action(
            state,
            prior_auction_count=prior_auction_count,
            prior_revealed_auction_count=prior_revealed_auction_count,
            prior_trick_count=prior_trick_count,
            prior_revealed_trick_count=prior_revealed_trick_count,
        )

        # Update hand row if hand completed or redealt
        current_hand = state.current_hand
        if current_hand is not None and current_hand.phase in ("complete", "redeal"):
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        _update_match_row(match_row, state)
        session.commit()

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
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
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

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
        prior_auction_count = len(hand.auction)
        prior_revealed_auction_count = hand.revealed_auction_count
        prior_trick_count = len(hand.completed_tricks)
        prior_revealed_trick_count = hand.revealed_trick_count

        # Ensure hand row exists (keyed by deal_id for redeal-safe uniqueness)
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

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
        state = engine.submit_human_card(state, card_index)

        # Log AI decisions captured during auto-advance
        _log_ai_decisions_after_advance(
            session,
            match_row,
            hand_row,
            engine,
            state,
        )

        _reveal_after_human_action(
            state,
            prior_auction_count=prior_auction_count,
            prior_revealed_auction_count=prior_revealed_auction_count,
            prior_trick_count=prior_trick_count,
            prior_revealed_trick_count=prior_revealed_trick_count,
        )

        # Update hand row if hand completed (redeals cannot occur during
        # card play, but keep the check consistent)
        current_hand = state.current_hand
        if current_hand is not None and current_hand.phase == "complete":
            _update_hand_row(hand_row, current_hand)
        elif current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        _update_match_row(match_row, state)
        session.commit()

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/moon-exchange", response_class=HTMLResponse)
async def submit_moon_exchange(
    request: Request,
    link_uuid: str,
    turn_number: int = Form(...),
    card_indices: list[int] = Form(...),
):
    """Submit the human side of a moon exchange."""
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

        hand = state.current_hand
        if hand is None or turn_number < hand.turn_number:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        if hand.phase != "moon_exchange":
            raise HTTPException(status_code=400, detail="Not in moon exchange phase")
        if hand.current_seat != HUMAN_SEAT:
            raise HTTPException(status_code=400, detail="Not the human's turn")

        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=hand.turn_number,
            seat=HUMAN_SEAT,
            phase="moon_exchange",
            actor_type="human",
            decision_source="human",
            legal_actions=list(range(len(hand.hands[HUMAN_SEAT]))),
            chosen_action=sorted(card_indices),
            game_state=engine.get_visible_state(state),
        )

        try:
            state = engine.submit_human_moon_exchange(state, card_indices)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        current_hand = state.current_hand
        if current_hand is not None:
            hand_row.hand_state_json = json.dumps(current_hand.to_dict())

        _update_match_row(match_row, state)
        session.commit()

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/next-hand", response_class=HTMLResponse)
async def next_hand(
    request: Request,
    link_uuid: str,
):
    """Advance from hand result to next hand."""
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

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        # Persist current hand before any hand transition
        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)
        if hand.phase == "complete":
            _update_hand_row(hand_row, hand)

        # Only start a new hand when we are paused on a completed hand
        state = engine.advance_to_next_hand(state)
        _reveal_initial_step(state)

        if state.current_hand is not None:
            next_hand_row = _ensure_hand_row(
                session,
                match_row,
                state.current_hand,
                state.current_hand.deal_id,
            )
            if state.current_hand.deal_id != hand.deal_id:
                _log_ai_decisions_after_advance(
                    session,
                    match_row,
                    next_hand_row,
                    engine,
                    state,
                )

        _update_match_row(match_row, state)
        session.commit()

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/next", response_class=HTMLResponse)
async def next_step(
    request: Request,
    link_uuid: str,
):
    """Advance one hidden reveal step or continue after a redeal pause."""
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

        hand = state.current_hand
        if hand is None:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        hand_row = _ensure_hand_row(session, match_row, hand, hand.deal_id)

        if _reveal_next_step(state):
            hand_row.hand_state_json = json.dumps(state.current_hand.to_dict())
        elif hand.phase == "moon_exchange_review":
            state = engine.advance_after_moon_review(state)
            _reveal_initial_step(state)
            _log_ai_decisions_after_advance(
                session,
                match_row,
                hand_row,
                engine,
                state,
            )
            if state.current_hand is not None:
                hand_row.hand_state_json = json.dumps(state.current_hand.to_dict())
        elif hand.phase == "redeal":
            _update_hand_row(hand_row, hand)
            state = engine.deal_after_redeal(state)
            _reveal_initial_step(state)
            if state.current_hand is not None:
                next_hand_row = _ensure_hand_row(
                    session,
                    match_row,
                    state.current_hand,
                    state.current_hand.deal_id,
                )
                _log_ai_decisions_after_advance(
                    session,
                    match_row,
                    next_hand_row,
                    engine,
                    state,
                )
        else:
            return HTMLResponse(_render_game_board(request, engine, state, link_uuid))

        _update_match_row(match_row, state)
        session.commit()

        return HTMLResponse(_render_game_board(request, engine, state, link_uuid))
    finally:
        session.close()


@router.post("/play/{link_uuid}/new-match", response_class=HTMLResponse)
async def new_match(
    request: Request,
    link_uuid: str,
):
    """Start a new match (after a previous one completed)."""
    templates = _get_templates(request)
    session = _get_session(request)
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            raise HTTPException(status_code=404, detail="Game not found")

        # Return model selection form (HTMX partial)
        ai_manager = _get_ai_manager(request)
        models = ai_manager.list_available()
        return HTMLResponse(
            templates.get_template("partials/model_select.html").render(
                {
                    "request": request,
                    "link_uuid": link_uuid,
                    "nickname": player.nickname or "Player",
                    "models": models,
                }
            )
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
    engine: MatchEngine,
    state,
) -> None:
    """Log AI decisions captured during the engine's last auto-advance.

    Uses the exact per-turn action events emitted by ``MatchEngine._advance_ai``
    (via ``engine.last_ai_events``) so that every AI decision row has the actual
    seat, legal_actions, chosen_action, and game_state snapshot.
    """
    ai_model = state.ai_model

    for event in engine.last_ai_events:
        _log_decision(
            session,
            match_row,
            hand_row,
            turn_number=event.turn_number,
            seat=event.seat,
            phase=event.phase,
            actor_type="ai",
            decision_source=ai_model,
            legal_actions=event.legal_actions,
            chosen_action=event.chosen_action,
            game_state=event.game_state,
        )

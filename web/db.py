"""SQLAlchemy models and session management for hosted play.

Models mirror the reference schema in ``web/schema.sql``.  V1 uses SQLite
for local development and Postgres for deployed environments; SQLAlchemy
abstracts the difference.

The ``match_state_json`` column stores a fully serialized ``MatchState``
for browser-refresh resume — no complex ORM mapping of nested game state.
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Invite code generation defaults
INVITE_CODE_LENGTH = 8
INVITE_CODE_ALPHABET = string.ascii_uppercase + string.digits

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    """Declarative base for all hosted-play models."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    link_uuid = Column(String, nullable=False, unique=True)
    nickname = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Player id={self.id} nickname={self.nickname!r}>"


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    match_uuid = Column(String, nullable=False, unique=True)
    player_id = Column(
        Integer,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_model = Column(String, nullable=False)
    status = Column(
        String,
        CheckConstraint("status IN ('active', 'complete', 'abandoned')"),
        nullable=False,
    )
    seed = Column(Integer, nullable=False)
    score_human = Column(Integer, nullable=False, default=0)
    score_ai = Column(Integer, nullable=False, default=0)
    hands_played = Column(Integer, nullable=False, default=0)
    current_hand_number = Column(Integer, nullable=False, default=0)
    match_state_json = Column(Text, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_matches_player_status", "player_id", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Match id={self.id} uuid={self.match_uuid!r} status={self.status!r}>"


class Hand(Base):
    __tablename__ = "hands"

    id = Column(Integer, primary_key=True)
    match_id = Column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    hand_number = Column(Integer, nullable=False)
    deal_id = Column(Integer, nullable=False)
    dealer_seat = Column(
        Integer,
        CheckConstraint("dealer_seat BETWEEN 0 AND 3"),
        nullable=False,
    )
    status = Column(
        String,
        CheckConstraint("status IN ('in_progress', 'redeal', 'complete')"),
        nullable=False,
    )
    winning_bid_n = Column(Integer, nullable=True)
    winning_bid_type = Column(
        String,
        CheckConstraint(
            "winning_bid_type IS NULL "
            "OR winning_bid_type IN ('regular', 'moon', 'loner')"
        ),
        nullable=True,
    )
    winning_contract = Column(
        String,
        CheckConstraint(
            "winning_contract IS NULL "
            "OR winning_contract IN ('C', 'D', 'H', 'S', 'HIGH', 'LOW')"
        ),
        nullable=True,
    )
    bidder_seat = Column(
        Integer,
        CheckConstraint("bidder_seat IS NULL OR bidder_seat BETWEEN 0 AND 3"),
        nullable=True,
    )
    sitting_out_seat = Column(
        Integer,
        CheckConstraint("sitting_out_seat IS NULL OR sitting_out_seat BETWEEN 0 AND 3"),
        nullable=True,
    )
    contract_type = Column(
        String,
        CheckConstraint(
            "contract_type IS NULL OR contract_type IN ('suit', 'high', 'low')"
        ),
        nullable=True,
    )
    trump_suit = Column(
        String,
        CheckConstraint("trump_suit IS NULL OR trump_suit IN ('C', 'D', 'H', 'S')"),
        nullable=True,
    )
    tricks_team0 = Column(Integer, nullable=False, default=0)
    tricks_team1 = Column(Integer, nullable=False, default=0)
    points_team0 = Column(Integer, nullable=False, default=0)
    points_team1 = Column(Integer, nullable=False, default=0)
    hand_state_json = Column(Text, nullable=False)
    started_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("match_id", "hand_number"),
        Index("idx_hands_match_number", "match_id", "hand_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<Hand id={self.id} match={self.match_id} "
            f"hand_number={self.hand_number} status={self.status!r}>"
        )


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True)
    match_id = Column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    hand_id = Column(
        Integer,
        ForeignKey("hands.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_number = Column(
        Integer,
        CheckConstraint("turn_number >= 0"),
        nullable=False,
    )
    seat = Column(
        Integer,
        CheckConstraint("seat BETWEEN 0 AND 3"),
        nullable=False,
    )
    phase = Column(
        String,
        CheckConstraint("phase IN ('bid', 'play')"),
        nullable=False,
    )
    actor_type = Column(
        String,
        CheckConstraint("actor_type IN ('human', 'ai')"),
        nullable=False,
    )
    decision_source = Column(String, nullable=False)
    legal_actions_json = Column(Text, nullable=False)
    chosen_action_json = Column(Text, nullable=False)
    game_state_json = Column(Text, nullable=False)
    decision_time_ms = Column(
        Integer,
        CheckConstraint("decision_time_ms IS NULL OR decision_time_ms >= 0"),
        nullable=True,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("hand_id", "turn_number"),
        Index("idx_decisions_match_turn", "match_id", "hand_id", "turn_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<Decision id={self.id} hand={self.hand_id} "
            f"turn={self.turn_number} seat={self.seat}>"
        )


class InviteCode(Base):
    """Invite code for pilot access control.

    Each code is a short alphanumeric string that grants access to the game.
    Codes are single-use: once redeemed, they are permanently bound to the
    player who redeemed them.  A redeemed code can be re-entered to look up
    the existing player (idempotent re-entry).

    Statuses:
      - ``active``   — available for redemption
      - ``redeemed`` — bound to a player
      - ``revoked``  — administratively disabled
    """

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String, nullable=False, unique=True)
    status = Column(
        String,
        CheckConstraint("status IN ('active', 'redeemed', 'revoked')"),
        nullable=False,
        default="active",
    )
    player_id = Column(
        Integer,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    )
    label = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    redeemed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_invite_codes_code", "code"),
        Index("idx_invite_codes_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<InviteCode id={self.id} code={self.code!r} status={self.status!r}>"


class Comment(Base):
    """Player comment on a game session.

    Simple text-only comments, displayed newest first.  No threading,
    editing, or deletion — a minimal community board for pilot users.
    """

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    player_id = Column(
        Integer,
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
    )
    match_id = Column(
        Integer,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=True,
    )
    content = Column(
        Text,
        CheckConstraint("length(content) > 0"),
        nullable=False,
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("idx_comments_created", "created_at"),
        Index("idx_comments_player", "player_id"),
    )

    def __repr__(self) -> str:
        return f"<Comment id={self.id} player={self.player_id}>"


def generate_invite_code(
    length: int = INVITE_CODE_LENGTH,
    alphabet: str = INVITE_CODE_ALPHABET,
) -> str:
    """Generate a cryptographically random invite code.

    Default: 8-character uppercase alphanumeric (36^8 ≈ 2.8 trillion
    combinations).  Easy to type on mobile keyboards.
    """
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Engine / session helpers
# ---------------------------------------------------------------------------


def _enable_sqlite_fks(dbapi_conn, connection_record):  # noqa: ARG001
    """Enable foreign key enforcement for SQLite connections."""
    dbapi_conn.execute("PRAGMA foreign_keys = ON")


def init_engine(database_url: str):
    """Create a SQLAlchemy engine with appropriate settings.

    For SQLite, enables foreign key enforcement via a connection event.
    """
    engine = create_engine(database_url, echo=False)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_fks)
    return engine


def create_tables(engine) -> None:
    """Create all tables (idempotent — safe to call on every startup)."""
    Base.metadata.create_all(engine)


def make_session_factory(engine) -> sessionmaker[Session]:
    """Return a configured session factory bound to *engine*."""
    return sessionmaker(bind=engine)

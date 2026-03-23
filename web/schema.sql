-- Hosted-play reference schema for the browser game V1.
--
-- This schema is SQLite-first for local/dev bootstrap. `web/db.py` will remain
-- the portable SQLAlchemy source for SQLite and Postgres.
--
-- V1 does not create a database `model_registry` table. The approved AI roster
-- is config-backed and preloaded at app startup.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY,
    link_uuid TEXT NOT NULL UNIQUE,
    nickname TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY,
    match_uuid TEXT NOT NULL UNIQUE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    ai_model TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'complete', 'abandoned')),
    seed INTEGER NOT NULL,
    score_human INTEGER NOT NULL DEFAULT 0,
    score_ai INTEGER NOT NULL DEFAULT 0,
    hands_played INTEGER NOT NULL DEFAULT 0,
    current_hand_number INTEGER NOT NULL DEFAULT 0,
    match_state_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS hands (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    hand_number INTEGER NOT NULL,
    deal_id INTEGER NOT NULL,
    dealer_seat INTEGER NOT NULL CHECK (dealer_seat BETWEEN 0 AND 3),
    status TEXT NOT NULL CHECK (status IN ('in_progress', 'redeal', 'complete')),
    winning_bid_n INTEGER,
    winning_contract TEXT CHECK (
        winning_contract IS NULL
        OR winning_contract IN ('C', 'D', 'H', 'S', 'HIGH', 'LOW')
    ),
    bidder_seat INTEGER CHECK (bidder_seat IS NULL OR bidder_seat BETWEEN 0 AND 3),
    contract_type TEXT CHECK (
        contract_type IS NULL OR contract_type IN ('suit', 'high', 'low')
    ),
    trump_suit TEXT CHECK (
        trump_suit IS NULL OR trump_suit IN ('C', 'D', 'H', 'S')
    ),
    tricks_team0 INTEGER NOT NULL DEFAULT 0,
    tricks_team1 INTEGER NOT NULL DEFAULT 0,
    points_team0 INTEGER NOT NULL DEFAULT 0,
    points_team1 INTEGER NOT NULL DEFAULT 0,
    hand_state_json TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    UNIQUE (match_id, hand_number)
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    hand_id INTEGER NOT NULL REFERENCES hands(id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL CHECK (turn_number >= 0),
    seat INTEGER NOT NULL CHECK (seat BETWEEN 0 AND 3),
    phase TEXT NOT NULL CHECK (phase IN ('bid', 'play')),
    actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'ai')),
    decision_source TEXT NOT NULL,
    legal_actions_json TEXT NOT NULL,
    chosen_action_json TEXT NOT NULL,
    game_state_json TEXT NOT NULL,
    decision_time_ms INTEGER CHECK (
        decision_time_ms IS NULL OR decision_time_ms >= 0
    ),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (hand_id, turn_number)
);

CREATE INDEX IF NOT EXISTS idx_matches_player_status
    ON matches(player_id, status, created_at);

CREATE INDEX IF NOT EXISTS idx_hands_match_number
    ON hands(match_id, hand_number);

CREATE INDEX IF NOT EXISTS idx_decisions_match_turn
    ON decisions(match_id, hand_id, turn_number);

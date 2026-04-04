#!/usr/bin/env bash
# create_invite_codes.sh — Batch-create invite codes for the browser game.
#
# Usage:
#   bash scripts/internal/create_invite_codes.sh [count] [label]
#
# Arguments:
#   count   Number of codes to create (default: 5)
#   label   Optional label for the batch (default: "playtest")
#
# Environment:
#   DATABASE_URL  Database URL (default: sqlite:///hosted_play.db)
#
# Examples:
#   # Create 5 playtest codes on local dev DB
#   bash scripts/internal/create_invite_codes.sh 5 playtest
#
#   # Create 10 codes on a remote Postgres DB
#   DATABASE_URL="postgresql://..." bash scripts/internal/create_invite_codes.sh 10 batch-2026-04
#
# Output:
#   Prints each generated code to stdout (one per line), suitable for
#   piping to a file or clipboard.

set -euo pipefail

COUNT="${1:-5}"
LABEL="${2:-playtest}"

# Use inline Python to leverage the existing web.db module
uv run python -c "
import sys
sys.path.insert(0, '.')
from web.db import (
    Base, InviteCode, generate_invite_code,
    init_engine, make_session_factory,
)
from web.config import get_config

config = get_config()
engine = init_engine(config.database_url)
Base.metadata.create_all(engine)
SessionFactory = make_session_factory(engine)
session = SessionFactory()

count = int('${COUNT}')
label = '${LABEL}'
codes = []

try:
    for _ in range(count):
        code = generate_invite_code()
        invite = InviteCode(code=code, status='active', label=label)
        session.add(invite)
        codes.append(code)
    session.commit()
    for c in codes:
        print(c)
    print(f'--- Created {count} invite codes (label={label}) ---', file=sys.stderr)
except Exception as e:
    session.rollback()
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
finally:
    session.close()
    engine.dispose()
"

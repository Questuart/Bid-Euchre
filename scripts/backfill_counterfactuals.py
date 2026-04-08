"""Backfill counterfactual columns for historical Render DB decisions.

Retroactively populates NULL rows in the ``decisions`` table:

* ``counterfactual_json`` — what GBT (Bud Bot) would have bid on human bid
  decisions.  Mirrors the live computation in
  :func:`web.routes._compute_bid_counterfactual`.
* ``glutton_action_json`` — what GluttonStrategy would have played on human
  card-play decisions.  Mirrors the live computation in
  :func:`web.routes._compute_glutton_counterfactual`.

Both columns were added in PRs #2618 and #2616 respectively.  Rows that predate
those PRs have NULL values and are the target of this script.

Usage
-----
::

    # Report NULL counts only (no writes)
    DATABASE_URL=<url> uv run python scripts/backfill_counterfactuals.py --dry-run

    # Backfill both types, default batch size 50
    DATABASE_URL=<url> uv run python scripts/backfill_counterfactuals.py

    # Bid counterfactuals only, custom batch
    DATABASE_URL=<url> uv run python scripts/backfill_counterfactuals.py \\
        --type bid --batch-size 100

    # Play counterfactuals only
    DATABASE_URL=<url> uv run python scripts/backfill_counterfactuals.py --type play

Environment
-----------
``DATABASE_URL`` — SQLAlchemy connection string (required).
``GBT_ARTIFACT``  — Path to the GBT action-value artifact file (required for
                    bid backfill; defaults to the config default path).
``MODELS_DIR``    — Directory prefix for relative artifact paths (optional).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("backfill_counterfactuals")

# Human player is always at seat 0 in browser game sessions.
_HUMAN_SEAT = 0


# ---------------------------------------------------------------------------
# State reconstruction helpers
# ---------------------------------------------------------------------------


def _cards_from_list(raw: list[list[str]]) -> list[Any]:
    """Reconstruct a list of Card objects from stored [[suit, rank], ...] pairs."""
    from bid_euchre.core.cards import Card

    return [Card(suit=pair[0], rank=pair[1]) for pair in raw]


def _trick_plays_from_list(
    raw: list[list[Any]],
) -> list[tuple[int, Any]]:
    """Reconstruct trick plays from stored [[seat, [suit, rank]], ...] pairs."""
    from bid_euchre.core.cards import Card

    return [(int(entry[0]), Card(suit=entry[1][0], rank=entry[1][1])) for entry in raw]


def _current_high_bid_from_auction(auction: list[dict[str, Any]]) -> int:
    """Compute the current high bid from an auction transcript list.

    Returns the highest ``n`` among all non-pass entries, or 0 if no bids.
    Mirrors ``hand.current_high_bid`` at the time the game state was captured.
    """
    high = 0
    for entry in auction:
        if entry.get("action") == "bid":
            high = max(high, int(entry.get("n", 0)))
    return high


# ---------------------------------------------------------------------------
# Counterfactual computation
# ---------------------------------------------------------------------------


def _compute_bid_counterfactual_from_state(
    gbt_bidder: Any,
    game_state: dict[str, Any],
) -> dict[str, Any] | None:
    """Re-run GBT bidder on the stored pre-decision game state.

    Returns the counterfactual dict or None if the state is insufficient.
    """
    from bid_euchre.strategy.bidding import BiddingObservation

    try:
        raw_hand = game_state.get("human_hand")
        if not raw_hand:
            logger.warning("bid counterfactual: missing human_hand in game_state")
            return None
        dealer_seat = game_state.get("dealer_seat")
        if dealer_seat is None:
            logger.warning("bid counterfactual: missing dealer_seat in game_state")
            return None
        auction = game_state.get("auction", [])

        hand_cards = _cards_from_list(raw_hand)
        current_high_bid = _current_high_bid_from_auction(auction)

        obs = BiddingObservation(
            hand=hand_cards,
            seat=_HUMAN_SEAT,
            dealer_seat=int(dealer_seat),
            current_high_bid=current_high_bid,
            auction_transcript=tuple(auction),
        )
        gbt_bid = gbt_bidder.choose_bid(obs)
        return {
            "source": "bud_bot",
            "n": gbt_bid.n,
            "contract": gbt_bid.contract,
            "bid_type": gbt_bid.bid_type,
        }
    except Exception:
        logger.warning("bid counterfactual: computation failed", exc_info=True)
        return None


def _compute_glutton_counterfactual_from_state(
    game_state: dict[str, Any],
) -> int | None:
    """Re-run GluttonStrategy on the stored pre-decision game state.

    Returns the chosen card index or None if the state is insufficient.
    """
    from bid_euchre.strategy.glutton import GluttonStrategy

    try:
        raw_hand = game_state.get("human_hand")
        if not raw_hand:
            logger.warning("play counterfactual: missing human_hand in game_state")
            return None
        contract_type = game_state.get("contract_type")
        if not contract_type:
            logger.warning("play counterfactual: missing contract_type in game_state")
            return None

        raw_trick = game_state.get("current_trick")
        if raw_trick is None:
            logger.warning("play counterfactual: missing current_trick in game_state")
            return None

        trump = game_state.get("trump")  # May be None for HIGH/LOW contracts
        hand_cards = _cards_from_list(raw_hand)
        plays_so_far = _trick_plays_from_list(raw_trick.get("plays", []))

        glutton = GluttonStrategy(cash_winners_on_lead=True)
        return glutton.choose_card(
            hand_cards,
            plays_so_far,
            contract_type,
            trump,
            _HUMAN_SEAT,
        )
    except Exception:
        logger.warning("play counterfactual: computation failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# GBT model loading
# ---------------------------------------------------------------------------


def _load_gbt_bidder(config: Any) -> Any:
    """Load and return the GBTActionValueBidder from the configured artifact.

    Raises RuntimeError if the artifact cannot be loaded.
    """
    import os

    from bid_euchre.strategy.bidding import GBTActionValueBidder

    # Resolve candidate paths (mirrors AIManager._resolve_candidate_paths)
    artifact_path = config.gbt_artifact
    if not artifact_path:
        raise RuntimeError(
            "GBT_ARTIFACT is not configured — set GBT_ARTIFACT env var "
            "or ensure the default artifact path exists"
        )

    candidates: list[str] = []
    if config.models_dir and not os.path.isabs(artifact_path):
        if os.path.isfile(artifact_path):
            candidates.append(artifact_path)
        candidates.append(os.path.join(config.models_dir, artifact_path))
    else:
        candidates.append(artifact_path)

    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            bidder = GBTActionValueBidder(
                artifact_path=path,
                name="bud_bot",
                skip_behavioral_check=True,
            )
            logger.info("Loaded GBT model from %s", path)
            return bidder
        except Exception:
            logger.warning("Failed to load GBT from %s", path, exc_info=True)

    raise RuntimeError(
        f"GBT artifact not found or failed to load. "
        f"Tried: {candidates}. "
        f"Set GBT_ARTIFACT and/or MODELS_DIR env vars."
    )


# ---------------------------------------------------------------------------
# Dry-run reporting
# ---------------------------------------------------------------------------


def _report_null_counts(session: Any) -> None:
    """Print NULL row counts for both counterfactual columns."""
    from web.db import Decision

    bid_null = (
        session.query(Decision)
        .filter(
            Decision.phase == "bid",
            Decision.actor_type == "human",
            Decision.counterfactual_json.is_(None),
        )
        .count()
    )
    play_null = (
        session.query(Decision)
        .filter(
            Decision.phase == "play",
            Decision.actor_type == "human",
            Decision.glutton_action_json.is_(None),
        )
        .count()
    )
    logger.info("DRY RUN — NULL row counts:")
    logger.info("  counterfactual_json (bid):   %d rows", bid_null)
    logger.info("  glutton_action_json (play):  %d rows", play_null)
    logger.info("  Total:                       %d rows", bid_null + play_null)


# ---------------------------------------------------------------------------
# Batch processors
# ---------------------------------------------------------------------------


def _backfill_bid_batch(
    session: Any,
    gbt_bidder: Any,
    batch_size: int,
) -> tuple[int, int, int]:
    """Process one batch of bid decisions missing counterfactual_json.

    Returns (processed, skipped, errors) counts for this batch.
    """
    from web.db import Decision

    rows = (
        session.query(Decision)
        .filter(
            Decision.phase == "bid",
            Decision.actor_type == "human",
            Decision.counterfactual_json.is_(None),
        )
        .limit(batch_size)
        .all()
    )

    processed = 0
    skipped = 0
    errors = 0

    for row in rows:
        try:
            game_state = json.loads(row.game_state_json)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Decision id=%d: invalid game_state_json: %s", row.id, exc)
            errors += 1
            continue

        result = _compute_bid_counterfactual_from_state(gbt_bidder, game_state)
        if result is None:
            logger.info("Decision id=%d (bid): insufficient context, skipping", row.id)
            skipped += 1
            continue

        row.counterfactual_json = json.dumps(result)
        processed += 1

    session.commit()
    return processed, skipped, errors


def _backfill_play_batch(
    session: Any,
    batch_size: int,
) -> tuple[int, int, int]:
    """Process one batch of play decisions missing glutton_action_json.

    Returns (processed, skipped, errors) counts for this batch.
    """
    from web.db import Decision

    rows = (
        session.query(Decision)
        .filter(
            Decision.phase == "play",
            Decision.actor_type == "human",
            Decision.glutton_action_json.is_(None),
        )
        .limit(batch_size)
        .all()
    )

    processed = 0
    skipped = 0
    errors = 0

    for row in rows:
        try:
            game_state = json.loads(row.game_state_json)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Decision id=%d: invalid game_state_json: %s", row.id, exc)
            errors += 1
            continue

        result = _compute_glutton_counterfactual_from_state(game_state)
        if result is None:
            logger.info("Decision id=%d (play): insufficient context, skipping", row.id)
            skipped += 1
            continue

        row.glutton_action_json = json.dumps(result)
        processed += 1

    session.commit()
    return processed, skipped, errors


# ---------------------------------------------------------------------------
# Main backfill loop
# ---------------------------------------------------------------------------


def _run_backfill(
    session_factory: Any,
    gbt_bidder: Any | None,
    backfill_type: str,
    batch_size: int,
) -> None:
    """Run the backfill loop until all NULL rows are filled."""
    total_processed = 0
    total_skipped = 0
    total_errors = 0

    if backfill_type in ("bid", "both"):
        if gbt_bidder is None:
            logger.error("GBT bidder is required for bid backfill but was not loaded")
            sys.exit(1)
        logger.info("Starting bid counterfactual backfill (batch_size=%d)", batch_size)
        bid_processed = bid_skipped = bid_errors = 0
        batch_num = 0
        while True:
            session = session_factory()
            try:
                processed, skipped, errors = _backfill_bid_batch(
                    session, gbt_bidder, batch_size
                )
            finally:
                session.close()

            bid_processed += processed
            bid_skipped += skipped
            bid_errors += errors
            batch_num += 1

            logger.info(
                "Bid batch %d: processed=%d skipped=%d errors=%d "
                "(cumulative: processed=%d skipped=%d errors=%d)",
                batch_num,
                processed,
                skipped,
                errors,
                bid_processed,
                bid_skipped,
                bid_errors,
            )

            # A batch that produced zero writes (all skipped or all errored,
            # or empty) means we are either done or stuck.  Stop in both cases
            # to avoid an infinite loop on permanently-unbackfillable rows.
            if processed == 0:
                break

        logger.info(
            "Bid backfill complete: processed=%d skipped=%d errors=%d",
            bid_processed,
            bid_skipped,
            bid_errors,
        )
        total_processed += bid_processed
        total_skipped += bid_skipped
        total_errors += bid_errors

    if backfill_type in ("play", "both"):
        logger.info("Starting play counterfactual backfill (batch_size=%d)", batch_size)
        play_processed = play_skipped = play_errors = 0
        batch_num = 0
        while True:
            session = session_factory()
            try:
                processed, skipped, errors = _backfill_play_batch(session, batch_size)
            finally:
                session.close()

            play_processed += processed
            play_skipped += skipped
            play_errors += errors
            batch_num += 1

            logger.info(
                "Play batch %d: processed=%d skipped=%d errors=%d "
                "(cumulative: processed=%d skipped=%d errors=%d)",
                batch_num,
                processed,
                skipped,
                errors,
                play_processed,
                play_skipped,
                play_errors,
            )

            if processed == 0:
                break

        logger.info(
            "Play backfill complete: processed=%d skipped=%d errors=%d",
            play_processed,
            play_skipped,
            play_errors,
        )
        total_processed += play_processed
        total_skipped += play_skipped
        total_errors += play_errors

    logger.info(
        "Backfill finished — total: processed=%d skipped=%d errors=%d",
        total_processed,
        total_skipped,
        total_errors,
    )
    if total_errors > 0:
        logger.warning("%d rows could not be processed due to errors", total_errors)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill counterfactual columns for historical DB decisions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report NULL row counts without writing any data.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        metavar="N",
        help="Number of rows to process per batch (default: 50).",
    )
    parser.add_argument(
        "--type",
        choices=["bid", "play", "both"],
        default="both",
        dest="backfill_type",
        help="Which counterfactual type to backfill (default: both).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    from web.config import HostedPlayConfig
    from web.db import create_tables, init_engine, make_session_factory

    config = HostedPlayConfig.from_env()
    logger.info("Connecting to database: %s", config.database_url)
    engine = init_engine(config.database_url)
    # Create tables if missing (idempotent — no-op on production DB with
    # existing schema; ensures the script works against a fresh test DB).
    create_tables(engine)
    session_factory = make_session_factory(engine)

    if args.dry_run:
        session = session_factory()
        try:
            _report_null_counts(session)
        finally:
            session.close()
        return

    # Load GBT bidder only when needed for bid backfill.
    gbt_bidder: Any | None = None
    if args.backfill_type in ("bid", "both"):
        try:
            gbt_bidder = _load_gbt_bidder(config)
        except RuntimeError as exc:
            logger.error("Cannot load GBT model: %s", exc)
            sys.exit(1)

    _run_backfill(
        session_factory=session_factory,
        gbt_bidder=gbt_bidder,
        backfill_type=args.backfill_type,
        batch_size=args.batch_size,
    )


if __name__ == "__main__":
    main()

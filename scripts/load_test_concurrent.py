"""Load test: simulate concurrent browser-game players.

Measures response times, SQLite contention, and error rates under
varying concurrency levels (5–20 simultaneous players).

Usage:
    uv run python scripts/load_test_concurrent.py [--levels 5,10,15,20] [--hands 3]

Output: JSON results to stdout, human-readable summary to stderr.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# App bootstrap (must happen before TestClient usage)
# ---------------------------------------------------------------------------


def _make_test_app(tmp_dir: Path):
    """Create a FastAPI app with file-based SQLite in tmp_dir."""
    from tests.unit.hosted_play.conftest import make_hosted_play_test_config
    from web.app import create_app

    config = make_hosted_play_test_config(
        tmp_dir,
        database_url=f"sqlite:///{tmp_dir / 'loadtest.db'}",
        test_seed=42,
    )
    return create_app(config=config)


# ---------------------------------------------------------------------------
# Timing helpers
# ---------------------------------------------------------------------------


@dataclass
class RequestTiming:
    """Record for a single HTTP request."""

    endpoint: str
    method: str
    status_code: int
    elapsed_ms: float
    error: str | None = None


@dataclass
class PlayerSession:
    """Results for one simulated player."""

    player_id: int
    timings: list[RequestTiming] = field(default_factory=list)
    hands_completed: int = 0
    errors: int = 0
    total_ms: float = 0.0


# ---------------------------------------------------------------------------
# Player simulation
# ---------------------------------------------------------------------------

# Maximum number of /next calls per action to advance reveals
_MAX_REVEAL_STEPS = 15
# Safety limit for total actions per hand (auction + play)
_MAX_ACTIONS_PER_HAND = 60


def _timed_request(
    session_data: PlayerSession, client, method: str, url: str, **kwargs
):
    """Execute a request and record timing."""
    start = time.perf_counter()
    try:
        if method == "GET":
            resp = client.get(url, **kwargs)
        else:
            resp = client.post(url, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000

        error_msg = None
        if resp.status_code >= 400:
            error_msg = f"HTTP {resp.status_code}"
            session_data.errors += 1
        if "database is locked" in resp.text.lower():
            error_msg = "database_locked"
            session_data.errors += 1

        session_data.timings.append(
            RequestTiming(
                endpoint=url,
                method=method,
                status_code=resp.status_code,
                elapsed_ms=elapsed,
                error=error_msg,
            )
        )
        return resp
    except Exception as exc:
        elapsed = (time.perf_counter() - start) * 1000
        session_data.errors += 1
        session_data.timings.append(
            RequestTiming(
                endpoint=url,
                method=method,
                status_code=0,
                elapsed_ms=elapsed,
                error=str(exc),
            )
        )
        return None


def _advance_reveals(session_data: PlayerSession, client, link_uuid: str):
    """Advance hidden auction/trick reveals until actionable."""
    for _ in range(_MAX_REVEAL_STEPS):
        resp = _timed_request(session_data, client, "POST", f"/play/{link_uuid}/next")
        if resp is None:
            break
        # If the response doesn't contain another "next" prompt, we're done
        if f'hx-post="/play/{link_uuid}/next"' not in resp.text:
            break


def _get_game_state(app, link_uuid: str):
    """Load current match state from DB for decision-making."""
    from tests.unit.hosted_play.conftest import get_match_state

    result = get_match_state(app, link_uuid)
    if result is None:
        return None, None
    state, _match_row, session = result
    session.close()
    return state, state.current_hand if state else None


def _simulate_player(
    app,
    client,
    player_id: int,
    max_hands: int,
) -> PlayerSession:
    """Simulate one player's game session through multiple hands.

    Uses a shared Starlette TestClient which routes requests through the
    app's ASGI interface — this tests real DB contention without network.
    The *client* is created once in the caller and shared across threads.
    """
    session_data = PlayerSession(player_id=player_id)
    start = time.perf_counter()

    # Step 1: Create game (POST /new)
    resp = _timed_request(session_data, client, "POST", "/new")
    if resp is None or resp.status_code not in (200, 302):
        session_data.total_ms = (time.perf_counter() - start) * 1000
        return session_data

    # Extract link_uuid from redirect
    if resp.status_code == 302:
        location = resp.headers.get("location", "")
    else:
        location = resp.url.path if hasattr(resp, "url") else ""

    if "/play/" not in location:
        session_data.errors += 1
        session_data.total_ms = (time.perf_counter() - start) * 1000
        return session_data

    link_uuid = location.split("/play/")[1].rstrip("/")

    # Step 2: Set nickname
    resp = _timed_request(
        session_data,
        client,
        "POST",
        f"/play/{link_uuid}/nickname",
        data={"nickname": f"LoadBot-{player_id}"},
    )
    if resp is None or resp.status_code >= 400:
        session_data.total_ms = (time.perf_counter() - start) * 1000
        return session_data

    # Step 3: Select AI model
    resp = _timed_request(
        session_data,
        client,
        "POST",
        f"/play/{link_uuid}/select-ai",
        data={"model_id": "bud_bot"},
    )
    if resp is None or resp.status_code >= 400:
        session_data.total_ms = (time.perf_counter() - start) * 1000
        return session_data

    # Step 4: Play through hands
    for _ in range(max_hands):
        hand_completed = _play_one_hand(app, client, session_data, link_uuid)
        if hand_completed:
            session_data.hands_completed += 1
        else:
            break

    session_data.total_ms = (time.perf_counter() - start) * 1000
    return session_data


def _play_one_hand(
    app,
    client,
    session_data: PlayerSession,
    link_uuid: str,
) -> bool:
    """Play through one hand (auction + trick play). Returns True if completed."""
    from bid_euchre.hosted_play.engine import HUMAN_SEAT

    actions = 0
    while actions < _MAX_ACTIONS_PER_HAND:
        actions += 1

        # Advance any pending reveals first
        _advance_reveals(session_data, client, link_uuid)

        # Get current game state
        state, hand = _get_game_state(app, link_uuid)
        if state is None or hand is None:
            return False

        # Match complete?
        if state.status == "complete":
            return True

        # Hand complete — advance to next
        if hand.phase == "complete":
            resp = _timed_request(
                session_data,
                client,
                "POST",
                f"/play/{link_uuid}/next-hand",
            )
            return resp is not None and resp.status_code == 200

        # Not our turn — advance reveals
        if hand.current_seat != HUMAN_SEAT:
            _advance_reveals(session_data, client, link_uuid)
            continue

        # Auction phase — submit a bid
        if hand.phase == "auction":
            resp = _timed_request(
                session_data,
                client,
                "POST",
                f"/play/{link_uuid}/bid",
                data={
                    "turn_number": hand.turn_number,
                    "bid_n": 0,  # always pass — simplest legal bid
                    "bid_contract": "",
                },
            )
            if resp is None or resp.status_code >= 400:
                return False
            continue

        # Trick play phase — play first legal card
        if hand.phase == "trick_play":
            from bid_euchre.hosted_play.engine import MatchEngine

            ai_manager = app.state.ai_manager
            match_state, _ = _get_game_state(app, link_uuid)
            if match_state is None:
                return False

            # Get legal plays from engine
            info = ai_manager.get_model_info("bud_bot")
            engine = MatchEngine(
                bidding_policy=info.bidding_policy,
                play_strategy=info.play_strategy,
            )
            legal_plays = engine.get_legal_plays(match_state)
            if not legal_plays:
                return False

            resp = _timed_request(
                session_data,
                client,
                "POST",
                f"/play/{link_uuid}/play-card",
                data={
                    "turn_number": hand.turn_number,
                    "card_index": legal_plays[0],
                },
            )
            if resp is None or resp.status_code >= 400:
                return False
            continue

        # Moon exchange phase
        if hand.phase == "moon_exchange":
            resp = _timed_request(
                session_data,
                client,
                "POST",
                f"/play/{link_uuid}/exchange",
                data={
                    "card_index_0": 0,
                    "card_index_1": 1,
                },
            )
            if resp is None or resp.status_code >= 400:
                return False
            continue

        # Unknown phase — skip
        break

    return False


# ---------------------------------------------------------------------------
# Load test runner
# ---------------------------------------------------------------------------


def run_load_test(
    concurrency: int,
    hands_per_player: int,
) -> dict[str, Any]:
    """Run a load test at the given concurrency level.

    Returns a dict with timing statistics.
    """
    import tempfile

    from starlette.testclient import TestClient

    tmp_dir = Path(tempfile.mkdtemp(prefix="loadtest_"))
    app = _make_test_app(tmp_dir)

    sessions: list[PlayerSession] = []
    wall_start = time.perf_counter()

    # One shared TestClient — lifespan runs once, all threads share
    # the same ASGI transport. This mirrors real production: one server
    # process handling concurrent requests to the same SQLite DB.
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(_simulate_player, app, client, i, hands_per_player): i
                for i in range(concurrency)
            }
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=300)
                    sessions.append(result)
                except Exception as exc:
                    pid = futures[future]
                    print(f"  Player {pid} crashed: {exc}", file=sys.stderr)
                    sessions.append(PlayerSession(player_id=pid, errors=1))

    wall_ms = (time.perf_counter() - wall_start) * 1000

    # Aggregate statistics
    all_timings: list[RequestTiming] = []
    for s in sessions:
        all_timings.extend(s.timings)

    total_requests = len(all_timings)
    total_errors = sum(1 for t in all_timings if t.error is not None)
    total_hands = sum(s.hands_completed for s in sessions)

    # Per-endpoint latency breakdown
    endpoint_stats: dict[str, dict[str, Any]] = {}
    for t in all_timings:
        # Normalize endpoint (strip UUIDs)
        parts = t.endpoint.split("/")
        normalized = []
        for p in parts:
            if len(p) == 36 and p.count("-") == 4:
                normalized.append("{uuid}")
            else:
                normalized.append(p)
        key = "/".join(normalized)

        if key not in endpoint_stats:
            endpoint_stats[key] = {"latencies": [], "errors": 0, "count": 0}
        endpoint_stats[key]["latencies"].append(t.elapsed_ms)
        endpoint_stats[key]["count"] += 1
        if t.error:
            endpoint_stats[key]["errors"] += 1

    # Compute percentiles
    summary_endpoints = {}
    for ep, data in sorted(endpoint_stats.items()):
        lats = sorted(data["latencies"])
        n = len(lats)
        summary_endpoints[ep] = {
            "count": n,
            "errors": data["errors"],
            "p50_ms": round(lats[n // 2], 1) if n else 0,
            "p95_ms": round(lats[int(n * 0.95)] if n else 0, 1),
            "p99_ms": round(lats[int(n * 0.99)] if n else 0, 1),
            "mean_ms": round(statistics.mean(lats), 1) if n else 0,
            "max_ms": round(max(lats), 1) if n else 0,
        }

    # Overall latency
    all_lats = sorted(t.elapsed_ms for t in all_timings) if all_timings else [0]
    n_all = len(all_lats)

    # Database locked errors specifically
    db_locked = sum(1 for t in all_timings if t.error == "database_locked")

    return {
        "concurrency": concurrency,
        "hands_per_player": hands_per_player,
        "wall_time_ms": round(wall_ms, 1),
        "total_requests": total_requests,
        "total_errors": total_errors,
        "db_locked_errors": db_locked,
        "error_rate_pct": round(total_errors / max(total_requests, 1) * 100, 2),
        "total_hands_completed": total_hands,
        "overall_latency": {
            "p50_ms": round(all_lats[n_all // 2], 1),
            "p95_ms": round(all_lats[int(n_all * 0.95)], 1),
            "p99_ms": round(all_lats[int(n_all * 0.99)], 1),
            "mean_ms": round(statistics.mean(all_lats), 1),
            "max_ms": round(max(all_lats), 1),
        },
        "endpoints": summary_endpoints,
        "per_player": [
            {
                "player_id": s.player_id,
                "hands_completed": s.hands_completed,
                "total_requests": len(s.timings),
                "errors": s.errors,
                "total_ms": round(s.total_ms, 1),
            }
            for s in sessions
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Load test concurrent players")
    parser.add_argument(
        "--levels",
        default="5,10,15,20",
        help="Comma-separated concurrency levels (default: 5,10,15,20)",
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=3,
        help="Hands per player to simulate (default: 3)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: stdout)",
    )
    args = parser.parse_args()

    levels = [int(x.strip()) for x in args.levels.split(",")]
    results = []

    for level in levels:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(
            f"Running load test: {level} concurrent players, {args.hands} hands each",
            file=sys.stderr,
        )
        print(f"{'=' * 60}", file=sys.stderr)

        result = run_load_test(level, args.hands)
        results.append(result)

        # Summary to stderr
        lat = result["overall_latency"]
        print(f"  Wall time:      {result['wall_time_ms']:.0f} ms", file=sys.stderr)
        print(f"  Requests:       {result['total_requests']}", file=sys.stderr)
        print(
            f"  Errors:         {result['total_errors']} ({result['error_rate_pct']}%)",
            file=sys.stderr,
        )
        print(f"  DB locked:      {result['db_locked_errors']}", file=sys.stderr)
        print(f"  Hands done:     {result['total_hands_completed']}", file=sys.stderr)
        print(f"  Latency p50:    {lat['p50_ms']:.1f} ms", file=sys.stderr)
        print(f"  Latency p95:    {lat['p95_ms']:.1f} ms", file=sys.stderr)
        print(f"  Latency p99:    {lat['p99_ms']:.1f} ms", file=sys.stderr)
        print(f"  Latency max:    {lat['max_ms']:.1f} ms", file=sys.stderr)

    output = json.dumps(results, indent=2)
    if args.output:
        Path(args.output).write_text(output)
        print(f"\nResults written to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

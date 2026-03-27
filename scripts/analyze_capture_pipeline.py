#!/usr/bin/env python
"""Analyze gameplay data from the capture pipeline and produce charts.

Reads a JSONL export file (produced by ``web.export.export_decisions``)
and generates three analysis charts:

1. **Bid distribution** — histogram of bid amounts by seat
2. **Score progression** — cumulative score over hands (inferred from
   trick counts and scoring)
3. **Trick count distribution** — histogram of tricks won per team per hand

Usage::

    uv run python scripts/analyze_capture_pipeline.py \\
        --input data/export.jsonl \\
        --output-dir data/analysis_charts

If ``--input`` is not provided, runs a self-contained demo that plays
AI-only games via the MatchEngine, exports to a temp file, and then
produces charts from that data.

Charts are saved as PNG files in the output directory.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

# Guard matplotlib import — falls back gracefully in CI if not available
try:
    import matplotlib

    matplotlib.use("Agg")  # Non-interactive backend for CI/headless
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def load_records(jsonl_path: Path) -> list[dict]:
    """Load all records from a JSONL file."""
    records = []
    with open(jsonl_path) as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                records.append(json.loads(raw))
    return records


def chart_bid_distribution(records: list[dict], output_path: Path) -> dict:
    """Produce a bid distribution chart and return summary stats.

    Chart: histogram of bid amounts grouped by seat.
    Returns: bid count per seat, pass count per seat, bid value distribution.
    """
    bid_records = [r for r in records if r["phase"] == "bid"]
    if not bid_records:
        return {"error": "No bid records found"}

    # Extract bid amounts by seat
    bids_by_seat: dict[int, list[int]] = defaultdict(list)
    pass_count_by_seat: Counter = Counter()

    for r in bid_records:
        seat = r["seat"]
        chosen = r["chosen_action"]
        if isinstance(chosen, dict):
            bid_n = chosen.get("n", 0)
            if bid_n == 0:
                pass_count_by_seat[seat] += 1
            else:
                bids_by_seat[seat].append(bid_n)
        elif isinstance(chosen, int):
            if chosen == 0:
                pass_count_by_seat[seat] += 1
            else:
                bids_by_seat[seat].append(chosen)

    # Summary stats
    all_bids = []
    for bids in bids_by_seat.values():
        all_bids.extend(bids)

    stats = {
        "total_bid_decisions": len(bid_records),
        "total_passes": sum(pass_count_by_seat.values()),
        "total_actual_bids": len(all_bids),
        "pass_count_by_seat": dict(pass_count_by_seat),
        "bid_count_by_seat": {s: len(b) for s, b in bids_by_seat.items()},
    }

    if all_bids:
        stats["bid_mean"] = round(sum(all_bids) / len(all_bids), 2)
        stats["bid_min"] = min(all_bids)
        stats["bid_max"] = max(all_bids)
        bid_dist = Counter(all_bids)
        stats["bid_value_distribution"] = dict(sorted(bid_dist.items()))

    # Chart
    if HAS_MATPLOTLIB and all_bids:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Left: bid amounts by seat
        seat_labels = [
            "Seat 0\n(Human)",
            "Seat 1\n(AI)",
            "Seat 2\n(AI)",
            "Seat 3\n(AI)",
        ]
        colors = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]

        for seat in range(4):
            bids = bids_by_seat.get(seat, [])
            if bids:
                axes[0].hist(
                    bids,
                    bins=range(1, 12),
                    alpha=0.6,
                    label=seat_labels[seat],
                    color=colors[seat],
                    edgecolor="black",
                    linewidth=0.5,
                )

        axes[0].set_xlabel("Bid Amount")
        axes[0].set_ylabel("Count")
        axes[0].set_title("Bid Amount Distribution by Seat")
        axes[0].legend()
        axes[0].set_xticks(range(1, 11))

        # Right: pass vs bid ratio by seat
        seat_ids = list(range(4))
        pass_vals = [pass_count_by_seat.get(s, 0) for s in seat_ids]
        bid_vals = [len(bids_by_seat.get(s, [])) for s in seat_ids]

        x_pos = range(4)
        width = 0.35
        axes[1].bar(
            [p - width / 2 for p in x_pos],
            pass_vals,
            width,
            label="Pass",
            color="#E0E0E0",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[1].bar(
            [p + width / 2 for p in x_pos],
            bid_vals,
            width,
            label="Bid",
            color="#2196F3",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[1].set_xlabel("Seat")
        axes[1].set_ylabel("Count")
        axes[1].set_title("Pass vs Bid Count by Seat")
        axes[1].set_xticks(x_pos)
        axes[1].set_xticklabels(seat_labels)
        axes[1].legend()

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close(fig)

    return stats


def chart_score_progression(records: list[dict], output_path: Path) -> dict:
    """Produce a score progression chart and return summary stats.

    Infers score changes from trick counts and auction data in game_state.
    Chart: cumulative score over hands for both teams.
    """
    # Group records by hand_number
    hands_data: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        hands_data[r["hand_number"]].append(r)

    if not hands_data:
        return {"error": "No records found"}

    # Extract scoring info from the last record of each hand
    team0_cumulative = []
    team1_cumulative = []
    cum_t0 = 0
    cum_t1 = 0

    hand_results = []
    for hn in sorted(hands_data.keys()):
        group = hands_data[hn]
        # Find a record with the most complete game_state (highest turn_number)
        group.sort(key=lambda r: r["turn_number"], reverse=True)
        last_gs = group[0].get("game_state", {})

        t0 = last_gs.get("tricks_team0", 0)
        t1 = last_gs.get("tricks_team1", 0)
        pts0 = last_gs.get("points_team0")
        pts1 = last_gs.get("points_team1")

        # If points aren't in game_state, use trick counts as proxy
        if pts0 is not None:
            cum_t0 += pts0
            cum_t1 += pts1 or 0
        else:
            cum_t0 += t0
            cum_t1 += t1

        team0_cumulative.append(cum_t0)
        team1_cumulative.append(cum_t1)
        hand_results.append(
            {
                "hand_number": hn,
                "tricks_team0": t0,
                "tricks_team1": t1,
                "points_team0": pts0,
                "points_team1": pts1,
            }
        )

    stats = {
        "total_hands": len(hands_data),
        "final_score_team0": cum_t0,
        "final_score_team1": cum_t1,
        "hand_results": hand_results,
    }

    # Chart
    if HAS_MATPLOTLIB and len(team0_cumulative) > 0:
        fig, ax = plt.subplots(figsize=(10, 5))
        x = list(range(1, len(team0_cumulative) + 1))

        ax.plot(
            x,
            team0_cumulative,
            marker="o",
            linewidth=2,
            markersize=5,
            label="Team 0 (Human+Partner)",
            color="#2196F3",
        )
        ax.plot(
            x,
            team1_cumulative,
            marker="s",
            linewidth=2,
            markersize=5,
            label="Team 1 (AI)",
            color="#FF5722",
        )
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        ax.fill_between(x, team0_cumulative, team1_cumulative, alpha=0.1)

        ax.set_xlabel("Hand Number")
        ax.set_ylabel("Cumulative Score")
        ax.set_title("Score Progression Over Hands")
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close(fig)

    return stats


def chart_trick_counts(records: list[dict], output_path: Path) -> dict:
    """Produce a trick count distribution chart and return summary stats.

    Chart: histogram of tricks won per team per hand.
    """
    # Group by hand, extract trick counts from last record per hand
    hands_data: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        hands_data[r["hand_number"]].append(r)

    team0_tricks = []
    team1_tricks = []

    for hn in sorted(hands_data.keys()):
        group = hands_data[hn]
        group.sort(key=lambda r: r["turn_number"], reverse=True)
        gs = group[0].get("game_state", {})
        t0 = gs.get("tricks_team0", 0)
        t1 = gs.get("tricks_team1", 0)

        # Only include hands where tricks were actually played
        if t0 + t1 > 0:
            team0_tricks.append(t0)
            team1_tricks.append(t1)

    if not team0_tricks:
        return {"error": "No trick data found"}

    stats = {
        "hands_with_tricks": len(team0_tricks),
        "team0_tricks_total": sum(team0_tricks),
        "team1_tricks_total": sum(team1_tricks),
        "team0_tricks_mean": round(sum(team0_tricks) / len(team0_tricks), 2),
        "team1_tricks_mean": round(sum(team1_tricks) / len(team1_tricks), 2),
        "team0_tricks_distribution": dict(Counter(team0_tricks)),
        "team1_tricks_distribution": dict(Counter(team1_tricks)),
    }

    # Chart
    if HAS_MATPLOTLIB:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Left: side-by-side histogram
        bins = range(0, 12)
        axes[0].hist(
            team0_tricks,
            bins=bins,
            alpha=0.6,
            label="Team 0 (Human+Partner)",
            color="#2196F3",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[0].hist(
            team1_tricks,
            bins=bins,
            alpha=0.6,
            label="Team 1 (AI)",
            color="#FF5722",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[0].set_xlabel("Tricks Won")
        axes[0].set_ylabel("Number of Hands")
        axes[0].set_title("Tricks Won Distribution by Team")
        axes[0].legend()
        axes[0].set_xticks(range(0, 11))

        # Right: per-hand stacked bar
        hand_indices = list(range(1, len(team0_tricks) + 1))
        axes[1].bar(
            hand_indices,
            team0_tricks,
            label="Team 0",
            color="#2196F3",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[1].bar(
            hand_indices,
            team1_tricks,
            bottom=team0_tricks,
            label="Team 1",
            color="#FF5722",
            edgecolor="black",
            linewidth=0.5,
        )
        axes[1].axhline(
            y=10, color="gray", linestyle="--", alpha=0.5, label="10 tricks total"
        )
        axes[1].set_xlabel("Hand Number")
        axes[1].set_ylabel("Tricks Won")
        axes[1].set_title("Tricks Won Per Hand (Stacked)")
        axes[1].legend(loc="lower right")

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close(fig)

    return stats


def run_demo_game() -> Path:
    """Run a self-contained AI-only game and export to a temp JSONL file.

    Uses the MatchEngine directly to play a complete match, persists
    decisions to an in-memory SQLite DB, and exports via export_decisions.
    """

    from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
    from tests.unit.hosted_play.conftest import (
        make_hosted_play_test_config,
    )
    from web.app import create_app
    from web.db import (
        Match,
        Player,
    )
    from web.export import export_decisions

    # Set up DB
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        config = make_hosted_play_test_config(
            tmp_path, database_url=f"sqlite:///{tmp_path / 'demo.db'}"
        )

        from starlette.testclient import TestClient

        app = create_app(config=config)

        with TestClient(app) as client:
            # Create a game
            resp = client.post("/new", follow_redirects=False)
            link_uuid = resp.headers["location"].split("/play/")[1]
            client.post(f"/play/{link_uuid}/nickname", data={"nickname": "Demo"})
            client.post(f"/play/{link_uuid}/select-ai", data={"model_id": "olsa"})

            # Play through multiple hands
            for _ in range(300):
                session = app.state.session_factory()
                try:
                    player = (
                        session.query(Player).filter_by(link_uuid=link_uuid).first()
                    )
                    if player is None:
                        break
                    match_row = (
                        session.query(Match).filter_by(player_id=player.id).first()
                    )
                    if match_row is None:
                        break

                    ai_manager = app.state.ai_manager
                    info = ai_manager.get_model_info(match_row.ai_model)
                    engine = MatchEngine(
                        bidding_policy=info.bidding_policy,
                        play_strategy=info.play_strategy,
                    )
                    state = engine.deserialize(json.loads(match_row.match_state_json))
                finally:
                    session.close()

                if state.status == "complete" or state.hands_played >= 5:
                    break

                hand = state.current_hand
                if hand is None:
                    break

                if hand.phase == "complete":
                    client.post(f"/play/{link_uuid}/next-hand")
                    continue

                if hand.phase == "redeal":
                    client.post(f"/play/{link_uuid}/next")
                    continue

                has_hidden = hand.revealed_auction_count < len(hand.auction)
                if has_hidden or hand.paused_after_trick:
                    client.post(f"/play/{link_uuid}/next")
                    continue

                if (
                    hand.phase == "trick_play"
                    and hand.bid_type == "moon"
                    and not hand.exchange_revealed
                ):
                    client.post(f"/play/{link_uuid}/next")
                    continue

                if hand.current_seat == HUMAN_SEAT:
                    if hand.phase == "auction":
                        client.post(
                            f"/play/{link_uuid}/bid",
                            data={
                                "turn_number": hand.turn_number,
                                "bid_n": 0,
                                "bid_contract": "",
                            },
                        )
                    elif hand.phase == "trick_play":
                        legal = engine.get_legal_plays(state)
                        if legal:
                            client.post(
                                f"/play/{link_uuid}/play-card",
                                data={
                                    "turn_number": hand.turn_number,
                                    "card_index": legal[0],
                                },
                            )
                else:
                    client.post(f"/play/{link_uuid}/next")

            # Export
            output_path = tmp_path / "demo_export.jsonl"
            session = app.state.session_factory()
            try:
                player = session.query(Player).filter_by(link_uuid=link_uuid).first()
                match_row = session.query(Match).filter_by(player_id=player.id).first()
                count = export_decisions(
                    session, output_path, match_uuid=match_row.match_uuid
                )
            finally:
                session.close()

            print(f"Exported {count} decisions to {output_path}")

            # Copy to a persistent location
            persistent_path = Path(tempfile.mktemp(suffix=".jsonl"))
            persistent_path.write_text(output_path.read_text())
            return persistent_path


def produce_data_quality_report(records: list[dict]) -> dict:
    """Produce a data quality report with pass/fail for each field check.

    Returns a dict with check names and results.
    """
    report: dict[str, dict] = {}
    total = len(records)

    # Check 1: All required fields present
    from web.export import REQUIRED_FIELDS

    missing_count = 0
    for r in records:
        if REQUIRED_FIELDS - set(r.keys()):
            missing_count += 1
    report["required_fields_present"] = {
        "status": "PASS" if missing_count == 0 else "FAIL",
        "detail": f"{total - missing_count}/{total} records have all fields",
    }

    # Check 2: Valid phase values
    bad_phases = sum(1 for r in records if r.get("phase") not in ("bid", "play"))
    report["valid_phase_values"] = {
        "status": "PASS" if bad_phases == 0 else "FAIL",
        "detail": f"{bad_phases} records with invalid phase",
    }

    # Check 3: Valid actor types
    bad_actors = sum(1 for r in records if r.get("actor_type") not in ("human", "ai"))
    report["valid_actor_types"] = {
        "status": "PASS" if bad_actors == 0 else "FAIL",
        "detail": f"{bad_actors} records with invalid actor_type",
    }

    # Check 4: Valid seat values
    bad_seats = sum(
        1
        for r in records
        if not isinstance(r.get("seat"), int) or r["seat"] not in range(4)
    )
    report["valid_seat_values"] = {
        "status": "PASS" if bad_seats == 0 else "FAIL",
        "detail": f"{bad_seats} records with invalid seat",
    }

    # Check 5: Schema version = 1
    bad_version = sum(1 for r in records if r.get("schema_version") != 1)
    report["schema_version_correct"] = {
        "status": "PASS" if bad_version == 0 else "FAIL",
        "detail": f"{bad_version} records with wrong schema_version",
    }

    # Check 6: Non-empty legal_actions
    empty_legal = sum(
        1
        for r in records
        if not r.get("legal_actions")
        or (isinstance(r["legal_actions"], list) and len(r["legal_actions"]) == 0)
    )
    report["non_empty_legal_actions"] = {
        "status": "PASS" if empty_legal == 0 else "FAIL",
        "detail": f"{empty_legal} records with empty legal_actions",
    }

    # Check 7: Non-null chosen_action
    null_chosen = sum(1 for r in records if r.get("chosen_action") is None)
    report["non_null_chosen_action"] = {
        "status": "PASS" if null_chosen == 0 else "FAIL",
        "detail": f"{null_chosen} records with null chosen_action",
    }

    # Check 8: Chosen action in legal actions (self-consistency)
    illegal_chosen = 0
    for r in records:
        legal = r.get("legal_actions")
        chosen = r.get("chosen_action")
        if isinstance(legal, list) and chosen is not None:
            if chosen not in legal:
                illegal_chosen += 1
    report["chosen_in_legal_actions"] = {
        "status": "PASS" if illegal_chosen == 0 else "FAIL",
        "detail": f"{illegal_chosen} records with illegal chosen_action",
    }

    # Check 9: Non-negative turn numbers
    bad_turns = sum(
        1
        for r in records
        if not isinstance(r.get("turn_number"), int) or r["turn_number"] < 0
    )
    report["non_negative_turn_numbers"] = {
        "status": "PASS" if bad_turns == 0 else "FAIL",
        "detail": f"{bad_turns} records with bad turn_number",
    }

    # Check 10: Bid values in valid range (1-10 or 0 for pass)
    bid_records = [r for r in records if r.get("phase") == "bid"]
    bad_bids = 0
    for r in bid_records:
        chosen = r.get("chosen_action")
        if isinstance(chosen, dict):
            n = chosen.get("n", -1)
            if n < 0 or n > 10:
                bad_bids += 1
    report["valid_bid_range"] = {
        "status": "PASS" if bad_bids == 0 else "FAIL",
        "detail": f"{bad_bids}/{len(bid_records)} bid records with invalid n",
    }

    # Overall summary
    all_pass = all(c["status"] == "PASS" for c in report.values())
    report["_overall"] = {
        "status": "PASS" if all_pass else "FAIL",
        "total_records": total,
        "checks_passed": sum(1 for c in report.values() if c.get("status") == "PASS"),
        "checks_total": len(report) - 1,  # exclude _overall
    }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Analyze gameplay data from the capture pipeline"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to JSONL export file (if omitted, runs demo game)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/analysis_charts"),
        help="Directory for output charts (default: data/analysis_charts)",
    )
    args = parser.parse_args()

    # Load or generate data
    if args.input is not None:
        jsonl_path = args.input
        if not jsonl_path.exists():
            print(f"Error: {jsonl_path} does not exist", file=sys.stderr)
            sys.exit(1)
    else:
        print("No input file specified — running demo game...")
        jsonl_path = run_demo_game()

    records = load_records(jsonl_path)
    print(f"Loaded {len(records)} records from {jsonl_path}")

    if not records:
        print("Error: No records found", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Data quality report
    print("\n=== Data Quality Report ===")
    report = produce_data_quality_report(records)
    for check_name, result in report.items():
        if check_name == "_overall":
            continue
        status = result["status"]
        detail = result["detail"]
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {check_name}: {detail}")

    overall = report["_overall"]
    print(
        f"\nOverall: {overall['status']} "
        f"({overall['checks_passed']}/{overall['checks_total']} checks passed, "
        f"{overall['total_records']} records)"
    )

    # Produce charts
    if not HAS_MATPLOTLIB:
        print("\nWarning: matplotlib not available — skipping chart generation")
        print("Install with: pip install matplotlib")
    else:
        print("\n=== Generating Charts ===")

    # Chart 1: Bid distribution
    bid_path = args.output_dir / "bid_distribution.png"
    bid_stats = chart_bid_distribution(records, bid_path)
    print("\n1. Bid Distribution:")
    print(f"   Total bid decisions: {bid_stats.get('total_bid_decisions', 0)}")
    print(f"   Passes: {bid_stats.get('total_passes', 0)}")
    print(f"   Actual bids: {bid_stats.get('total_actual_bids', 0)}")
    if "bid_mean" in bid_stats:
        print(f"   Mean bid: {bid_stats['bid_mean']}")
    if HAS_MATPLOTLIB:
        print(f"   Chart: {bid_path}")

    # Chart 2: Score progression
    score_path = args.output_dir / "score_progression.png"
    score_stats = chart_score_progression(records, score_path)
    print("\n2. Score Progression:")
    print(f"   Hands played: {score_stats.get('total_hands', 0)}")
    print(f"   Final team 0 score: {score_stats.get('final_score_team0', 0)}")
    print(f"   Final team 1 score: {score_stats.get('final_score_team1', 0)}")
    if HAS_MATPLOTLIB:
        print(f"   Chart: {score_path}")

    # Chart 3: Trick counts
    trick_path = args.output_dir / "trick_counts.png"
    trick_stats = chart_trick_counts(records, trick_path)
    print("\n3. Trick Count Distribution:")
    if "error" not in trick_stats:
        print(f"   Hands with tricks: {trick_stats['hands_with_tricks']}")
        print(f"   Team 0 mean tricks: {trick_stats['team0_tricks_mean']}")
        print(f"   Team 1 mean tricks: {trick_stats['team1_tricks_mean']}")
    if HAS_MATPLOTLIB:
        print(f"   Chart: {trick_path}")

    # Write JSON report
    report_path = args.output_dir / "data_quality_report.json"
    with open(report_path, "w") as f:
        json.dump(
            {
                "data_quality": report,
                "bid_stats": bid_stats,
                "score_stats": {
                    k: v for k, v in score_stats.items() if k != "hand_results"
                },
                "trick_stats": trick_stats,
            },
            f,
            indent=2,
        )
    print(f"\nFull report: {report_path}")

    # Clean up temp file if we generated it
    if args.input is None and jsonl_path.exists():
        jsonl_path.unlink()

    # Exit with failure if quality checks failed
    if overall["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()

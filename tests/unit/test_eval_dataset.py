"""Tests for the JSONL eval dataset parser.

Tests follow the plan spec: 13 cases covering parsing, feature extraction,
team assignment, bidder flags, auction summary, redeal handling, max_deals,
error cases, and malformed-JSON tolerance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.datasets.eval_dataset import (
    build_eval_dataset,
    resolve_eval_log_from_bundle,
)

# ---------------------------------------------------------------------------
# Fixtures: minimal hand_end records
# ---------------------------------------------------------------------------


def _make_hand_end(
    deal_id: int = 0,
    contract: str = "suit",
    trump: str | None = "H",
    t0: int = 6,
    t1: int = 4,
    winning_bid: int | None = 6,
    bidder_position: int | None = 0,
    dealer_position: int | None = 3,
    made_bid: bool | None = True,
    redeal_flag: bool | None = False,
    auction_transcript: list | None = None,
    features: list | None = None,
) -> dict:
    """Build a minimal schema-v7 hand_end record."""
    if features is None:
        features = [_make_features(seat) for seat in range(4)]
    if auction_transcript is None:
        auction_transcript = [
            {
                "seat": 0,
                "action": "BID",
                "tricks_bid": 6,
                "contract_type": "suit",
                "trump": "H",
            },
            {
                "seat": 1,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            },
            {
                "seat": 2,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            },
            {
                "seat": 3,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            },
        ]
    return {
        "schema_version": 7,
        "event": "hand_end",
        "run_id": "test_run",
        "strategy_id": "test_strategy",
        "deal_id": deal_id,
        "seed": 42,
        "contract": contract,
        "trump": trump,
        "leader": 0,
        "t0": t0,
        "t1": t1,
        "features": features,
        "scores": [0, 0, 0, 0],
        "hands": [[], [], [], []],
        "winning_bid": winning_bid,
        "dealer_position": dealer_position,
        "bidder_position": bidder_position,
        "redeal_flag": redeal_flag,
        "made_bid": made_bid,
        "auction_transcript": auction_transcript,
        "timestamp": "2026-01-01T00:00:00",
    }


def _make_features(seat: int) -> dict:
    """Create a plausible 39-feature dict for a seat."""
    return {
        "bowers": seat % 3,
        "trump_count": 2 + seat,
        "offsuit_aces": 1,
        "offsuit_non_ace_count": 5,
        "hand_value": 400.0 + seat * 100,
        "trump_rb_count": 1 if seat == 0 else 0,
        "trump_lb_count": 0,
        "trump_ace_count": 1,
        "trump_king_count": 0,
        "trump_queen_count": 1,
        "trump_ten_count": 0,
        "highest_trump_rank": 6 if seat == 0 else 4,
        "second_highest_trump_rank": 4 if seat == 0 else 2,
        "third_highest_trump_rank": 0,
        "trump_power_sum": 10 + seat,
        "trump_duplicate_pairs": 0,
        "offsuit_king_count_total": 2,
        "offsuit_queen_count_total": 1,
        "offsuit_suits_with_ace": 1,
        "offsuit_suits_with_double_ace": 0,
        "offsuit_suits_with_ace_and_king": 1,
        "void_count": 1,
        "max_suit_len": 4,
        "second_suit_len": 3,
        "third_suit_len": 2,
        "fourth_suit_len": 1,
        "num_singletons": 1,
        "num_doubletons": 1,
        "offsuit_tens_count": 1,
        "offsuit_length_3plus_count": 2,
        "offsuit_best_rank_sum": 10,
        "offsuit_secondbest_rank_sum": 7,
        "double_ten_jack_count": 0,
        "high_card_count": 3,
        "low_card_count": 4,
        "trump_count_x_void_count": 2,
        "trump_count_x_offsuit_ace": 2,
        "losing_tricks_count": 5.0,
        "quick_tricks": 1.5,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as JSONL."""
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBasicParsing:
    """Test 1: Single record → 4 rows, correct columns."""

    def test_basic_parsing(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, [_make_hand_end()])

        df = build_eval_dataset(log)

        assert len(df) == 4
        assert set(df["seat"]) == {0, 1, 2, 3}
        # Structural columns
        for col in [
            "deal_id",
            "seat",
            "team",
            "contract_type",
            "trump",
            "tricks_won",
            "winning_bid",
            "bidder_seat",
            "bidder_team",
            "dealer_seat",
            "made_bid",
            "redeal_flag",
            "is_bidder",
            "is_declaring_team",
            "n_bids",
            "n_passes",
            "auction_rounds",
            "hand_id",
        ]:
            assert col in df.columns, f"Missing column: {col}"


class TestFeatureExtraction:
    """Test 2: 39 features with feat_ prefix."""

    def test_feature_extraction_with_prefix(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, [_make_hand_end()])

        df = build_eval_dataset(log)

        feat_cols = [c for c in df.columns if c.startswith("feat_")]
        assert len(feat_cols) == 39

        # Spot-check specific features
        assert "feat_hand_value" in df.columns
        assert "feat_bowers" in df.columns
        assert "feat_losing_tricks_count" in df.columns
        assert "feat_quick_tricks" in df.columns

        # No bare feature names
        assert "hand_value" not in df.columns
        assert "bowers" not in df.columns


class TestTeamAssignment:
    """Test 3: Seats 0,2→team 0; 1,3→team 1."""

    def test_team_assignment(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, [_make_hand_end()])

        df = build_eval_dataset(log)

        for _, row in df.iterrows():
            expected_team = 0 if row["seat"] in (0, 2) else 1
            assert row["team"] == expected_team


class TestTricksWon:
    """Test 4: Team 0 gets t0, team 1 gets t1."""

    def test_tricks_won_by_team(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, [_make_hand_end(t0=7, t1=3)])

        df = build_eval_dataset(log)

        for _, row in df.iterrows():
            if row["seat"] in (0, 2):
                assert row["tricks_won"] == 7
            else:
                assert row["tricks_won"] == 3


class TestBidderFlags:
    """Test 5: is_bidder and is_declaring_team correct."""

    def test_bidder_flags(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        # Seat 1 is the bidder → team 1
        _write_jsonl(log, [_make_hand_end(bidder_position=1)])

        df = build_eval_dataset(log)

        for _, row in df.iterrows():
            if row["seat"] == 1:
                assert row["is_bidder"] is True
            else:
                assert row["is_bidder"] is False

            # Declaring team: bidder is seat 1 → team 1
            if row["team"] == 1:
                assert row["is_declaring_team"] is True
            else:
                assert row["is_declaring_team"] is False


class TestAuctionSummary:
    """Test 6: n_bids, n_passes, auction_rounds."""

    def test_auction_summary(self, tmp_path: Path) -> None:
        transcript = [
            {
                "seat": 0,
                "action": "BID",
                "tricks_bid": 6,
                "contract_type": "suit",
                "trump": "H",
            },
            {
                "seat": 1,
                "action": "BID",
                "tricks_bid": 7,
                "contract_type": "suit",
                "trump": "S",
            },
            {
                "seat": 2,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            },
            {
                "seat": 3,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            },
        ]
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, [_make_hand_end(auction_transcript=transcript)])

        df = build_eval_dataset(log)

        # All 4 rows have same auction summary
        assert (df["n_bids"] == 2).all()
        assert (df["n_passes"] == 2).all()
        assert (df["auction_rounds"] == 4).all()


class TestRedealHandling:
    """Tests 7-8: Redeal filtering."""

    def test_skip_redeals(self, tmp_path: Path) -> None:
        records = [
            _make_hand_end(deal_id=0, redeal_flag=False),
            _make_hand_end(deal_id=1, redeal_flag=True),
            _make_hand_end(deal_id=2, redeal_flag=False),
        ]
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, records)

        df = build_eval_dataset(log, skip_redeals=True)

        assert set(df["deal_id"]) == {0, 2}
        assert len(df) == 8  # 2 deals × 4 seats

    def test_include_redeals(self, tmp_path: Path) -> None:
        records = [
            _make_hand_end(deal_id=0, redeal_flag=False),
            _make_hand_end(deal_id=1, redeal_flag=True),
        ]
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, records)

        df = build_eval_dataset(log, skip_redeals=False)

        assert set(df["deal_id"]) == {0, 1}
        assert len(df) == 8  # 2 deals × 4 seats


class TestMaxDeals:
    """Test 9: Only first N deals returned."""

    def test_max_deals(self, tmp_path: Path) -> None:
        records = [_make_hand_end(deal_id=i) for i in range(10)]
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, records)

        df = build_eval_dataset(log, max_deals=3)

        assert set(df["deal_id"]) == {0, 1, 2}
        assert len(df) == 12  # 3 deals × 4 seats


class TestErrorCases:
    """Tests 10-11: Missing file and empty log."""

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            build_eval_dataset(tmp_path / "nonexistent.jsonl")

    def test_empty_log(self, tmp_path: Path) -> None:
        log = tmp_path / "empty.jsonl"
        log.write_text("")

        with pytest.raises(ValueError, match="No hand_end records"):
            build_eval_dataset(log)


class TestEventFiltering:
    """Test 12: run_start, run_end, trick_end ignored."""

    def test_skip_non_hand_end_events(self, tmp_path: Path) -> None:
        records = [
            {"event": "run_start", "run_id": "test", "schema_version": 7},
            _make_hand_end(deal_id=0),
            {"event": "trick_end", "deal_id": 0, "trick_number": 1},
            {"event": "run_end", "run_id": "test", "schema_version": 7},
        ]
        log = tmp_path / "test.jsonl"
        _write_jsonl(log, records)

        df = build_eval_dataset(log)

        assert len(df) == 4  # Only 1 hand_end → 4 rows
        assert set(df["deal_id"]) == {0}


class TestMalformedJson:
    """Test 13: Bad JSON tolerated (evaluator pattern)."""

    def test_malformed_json_lines_skipped(self, tmp_path: Path) -> None:
        log = tmp_path / "test.jsonl"
        with log.open("w") as f:
            f.write("NOT VALID JSON\n")
            f.write(json.dumps(_make_hand_end(deal_id=0)) + "\n")
            f.write("{truncated\n")
            f.write(json.dumps(_make_hand_end(deal_id=1)) + "\n")

        df = build_eval_dataset(log)

        assert len(df) == 8  # 2 valid hand_end records × 4 seats
        assert set(df["deal_id"]) == {0, 1}


class TestPointsWon:
    """Tests for points_won column derived from compute_points."""

    def test_made_bid_declaring_team(self, tmp_path: Path) -> None:
        """Declaring team (team 0) made the bid → gets tricks won."""
        log = tmp_path / "test.jsonl"
        # Team 0 bids 6, wins 7 tricks
        _write_jsonl(
            log,
            [_make_hand_end(winning_bid=6, bidder_position=0, t0=7, t1=3)],
        )

        df = build_eval_dataset(log)

        # Seats 0,2 (team 0, declaring) → 7 points (made bid, get tricks)
        for seat in (0, 2):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == 7

    def test_made_bid_defending_team(self, tmp_path: Path) -> None:
        """Defending team (team 1) when bid is made → gets their tricks."""
        log = tmp_path / "test.jsonl"
        _write_jsonl(
            log,
            [_make_hand_end(winning_bid=6, bidder_position=0, t0=7, t1=3)],
        )

        df = build_eval_dataset(log)

        # Seats 1,3 (team 1, defending) → 3 points (their tricks)
        for seat in (1, 3):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == 3

    def test_set_bid_declaring_team(self, tmp_path: Path) -> None:
        """Declaring team set → gets -bid."""
        log = tmp_path / "test.jsonl"
        # Team 0 bids 8, only wins 5 tricks → set
        _write_jsonl(
            log,
            [_make_hand_end(winning_bid=8, bidder_position=0, t0=5, t1=5)],
        )

        df = build_eval_dataset(log)

        # Seats 0,2 (team 0, declaring, set) → -8 points
        for seat in (0, 2):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == -8
        # Seats 1,3 (team 1, defending) → 5 points
        for seat in (1, 3):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == 5

    def test_no_bidder(self, tmp_path: Path) -> None:
        """No bidder → both teams get their tricks as points."""
        log = tmp_path / "test.jsonl"
        _write_jsonl(
            log,
            [_make_hand_end(winning_bid=None, bidder_position=None, t0=6, t1=4)],
        )

        df = build_eval_dataset(log)

        for seat in (0, 2):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == 6
        for seat in (1, 3):
            assert df.loc[df["seat"] == seat, "points_won"].iloc[0] == 4


# ---------------------------------------------------------------------------
# Tests: resolve_eval_log_from_bundle
# ---------------------------------------------------------------------------


def _setup_bundle_tree(tmp_path: Path) -> dict:
    """Create a synthetic bundle/eval/log file tree for testing.

    Returns a dict with paths: bundle_path, eval_json_path, log_path.
    """
    # Create fake .git dir so repo root detection works
    (tmp_path / ".git").mkdir()

    # Create run directory with a JSONL log file
    run_id = "test_run_abc"
    log_name = "game_log.jsonl"
    run_dir = tmp_path / "data" / "runs" / run_id
    run_dir.mkdir(parents=True)
    log_path = run_dir / log_name
    log_path.write_text('{"event": "hand_end"}\n')

    # Create eval JSON
    eval_dir = tmp_path / "data" / "artifacts" / "arc_d" / "r0" / "eval"
    eval_dir.mkdir(parents=True)
    eval_json_path = eval_dir / "eval_olsa_42.json"
    eval_json_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "source_logs": [log_name],
                "seed": 42,
            }
        )
    )

    # Create bundle JSON
    bundle_dir = tmp_path / "data" / "artifacts" / "arc_d" / "r0"
    bundle_path = bundle_dir / "rung_bundle_r0.json"
    # Eval path is relative to repo root
    eval_rel = str(eval_json_path.relative_to(tmp_path))
    bundle_path.write_text(
        json.dumps(
            {
                "olsa": {
                    "eval_seed42": eval_rel,
                    "eval_seed43": eval_rel,
                },
                "olsa_full": {
                    "eval_seed42": eval_rel,
                },
            }
        )
    )

    return {
        "bundle_path": bundle_path,
        "eval_json_path": eval_json_path,
        "log_path": log_path,
    }


class TestResolveEvalLogFromBundle:
    """Tests for resolve_eval_log_from_bundle."""

    def test_happy_path(self, tmp_path: Path) -> None:
        """Resolves the correct JSONL log path."""
        paths = _setup_bundle_tree(tmp_path)
        result = resolve_eval_log_from_bundle(paths["bundle_path"], arm="olsa", seed=42)
        assert result == paths["log_path"]

    def test_missing_bundle(self, tmp_path: Path) -> None:
        """FileNotFoundError when bundle does not exist."""
        with pytest.raises(FileNotFoundError, match="Bundle not found"):
            resolve_eval_log_from_bundle(
                tmp_path / "nonexistent.json", arm="olsa", seed=42
            )

    def test_invalid_arm(self, tmp_path: Path) -> None:
        """KeyError when arm not in bundle."""
        paths = _setup_bundle_tree(tmp_path)
        with pytest.raises(KeyError, match="Arm 'bogus' not found"):
            resolve_eval_log_from_bundle(paths["bundle_path"], arm="bogus", seed=42)

    def test_invalid_seed(self, tmp_path: Path) -> None:
        """KeyError when seed not in bundle arm."""
        paths = _setup_bundle_tree(tmp_path)
        with pytest.raises(KeyError, match="eval_seed99"):
            resolve_eval_log_from_bundle(paths["bundle_path"], arm="olsa", seed=99)

    def test_missing_eval_json(self, tmp_path: Path) -> None:
        """FileNotFoundError when eval JSON file does not exist."""
        paths = _setup_bundle_tree(tmp_path)
        # Remove the eval JSON
        paths["eval_json_path"].unlink()
        with pytest.raises(FileNotFoundError, match="Eval JSON not found"):
            resolve_eval_log_from_bundle(paths["bundle_path"], arm="olsa", seed=42)

    def test_missing_log_file(self, tmp_path: Path) -> None:
        """FileNotFoundError with regeneration hint when JSONL log missing."""
        paths = _setup_bundle_tree(tmp_path)
        # Remove the log file
        paths["log_path"].unlink()
        with pytest.raises(FileNotFoundError, match="JSONL game log not found"):
            resolve_eval_log_from_bundle(paths["bundle_path"], arm="olsa", seed=42)

    def test_missing_log_regeneration_hint(self, tmp_path: Path) -> None:
        """Error message includes regeneration command."""
        paths = _setup_bundle_tree(tmp_path)
        paths["log_path"].unlink()
        with pytest.raises(FileNotFoundError, match="Regenerate with"):
            resolve_eval_log_from_bundle(paths["bundle_path"], arm="olsa", seed=42)

    def test_olsa_full_arm(self, tmp_path: Path) -> None:
        """Works with olsa_full arm."""
        paths = _setup_bundle_tree(tmp_path)
        result = resolve_eval_log_from_bundle(
            paths["bundle_path"], arm="olsa_full", seed=42
        )
        assert result == paths["log_path"]

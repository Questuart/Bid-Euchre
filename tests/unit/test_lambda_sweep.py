"""Tests for scripts/internal/run_lambda_sweep.py — lambda sweep tooling."""

# run_lambda_sweep is a script, not a library module. Import via path manipulation.
# The canonical approach in this repo is PYTHONPATH=src, so we add scripts/internal
# to get the module.
import json
import sys
from pathlib import Path

import pytest

# Insert scripts/internal onto sys.path so we can import run_lambda_sweep
_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts" / "internal")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import run_lambda_sweep  # noqa: E402

# ---------------------------------------------------------------------------
# extract_seat_bid_propensity
# ---------------------------------------------------------------------------


class TestExtractSeatBidPropensity:
    def _write_jsonl(self, logs_dir, records):
        """Helper to write JSONL records to a log file."""
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "test_run.jsonl"
        with open(log_file, "w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def test_basic_counting(self, tmp_path):
        """Counts BID and PASS actions correctly across seats."""
        run_dir = tmp_path / "test_run"
        logs_dir = run_dir / "logs"
        records = [
            {"event": "run_start"},
            {
                "event": "hand_end",
                "deal_id": 0,
                "auction_transcript": [
                    {"seat": 0, "action": "BID"},
                    {"seat": 1, "action": "PASS"},
                    {"seat": 2, "action": "BID"},
                    {"seat": 3, "action": "PASS"},
                ],
            },
            {
                "event": "hand_end",
                "deal_id": 1,
                "auction_transcript": [
                    {"seat": 0, "action": "BID"},
                    {"seat": 1, "action": "BID"},
                    {"seat": 2, "action": "BID"},
                    {"seat": 3, "action": "BID"},
                ],
            },
        ]
        self._write_jsonl(logs_dir, records)

        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        # 6 BIDs out of 8 total opportunities
        assert result == pytest.approx(6 / 8)

    def test_all_pass(self, tmp_path):
        """All-pass deals yield propensity 0."""
        run_dir = tmp_path / "test_run"
        logs_dir = run_dir / "logs"
        records = [
            {
                "event": "hand_end",
                "deal_id": 0,
                "auction_transcript": [
                    {"seat": 0, "action": "PASS"},
                    {"seat": 1, "action": "PASS"},
                    {"seat": 2, "action": "PASS"},
                    {"seat": 3, "action": "PASS"},
                ],
            },
        ]
        self._write_jsonl(logs_dir, records)
        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        assert result == 0.0

    def test_all_bid(self, tmp_path):
        """All-bid deals yield propensity 1."""
        run_dir = tmp_path / "test_run"
        logs_dir = run_dir / "logs"
        records = [
            {
                "event": "hand_end",
                "deal_id": 0,
                "auction_transcript": [
                    {"seat": 0, "action": "BID"},
                    {"seat": 1, "action": "BID"},
                    {"seat": 2, "action": "BID"},
                    {"seat": 3, "action": "BID"},
                ],
            },
        ]
        self._write_jsonl(logs_dir, records)
        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        assert result == 1.0

    def test_no_logs_dir(self, tmp_path):
        """Returns None when logs directory does not exist."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        assert result is None

    def test_no_auction_transcripts(self, tmp_path):
        """Returns None when no hand_end records have auction_transcript."""
        run_dir = tmp_path / "test_run"
        logs_dir = run_dir / "logs"
        records = [
            {"event": "run_start"},
            {"event": "hand_end", "deal_id": 0},
        ]
        self._write_jsonl(logs_dir, records)
        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        assert result is None

    def test_skips_non_hand_end_events(self, tmp_path):
        """Only counts auction_transcript from hand_end events."""
        run_dir = tmp_path / "test_run"
        logs_dir = run_dir / "logs"
        records = [
            {"event": "run_start"},
            {
                "event": "hand_end",
                "deal_id": 0,
                "auction_transcript": [
                    {"seat": 0, "action": "BID"},
                    {"seat": 1, "action": "PASS"},
                    {"seat": 2, "action": "PASS"},
                    {"seat": 3, "action": "PASS"},
                ],
            },
        ]
        self._write_jsonl(logs_dir, records)
        result = run_lambda_sweep.extract_seat_bid_propensity(str(run_dir))
        assert result == pytest.approx(1 / 4)


# ---------------------------------------------------------------------------
# apply_guardrails with bid_rate_key
# ---------------------------------------------------------------------------


class TestApplyGuardrailsBidRateKey:
    def test_default_uses_bid_rate(self):
        """Default bid_rate_key='bid_rate' uses deal-level bid_rate."""
        metrics = {"bid_rate": 0.5, "make_rate": 0.7}
        result = run_lambda_sweep.apply_guardrails(metrics)
        assert result["all_pass"] is True

    def test_custom_key_seat_propensity(self):
        """Using seat_bid_propensity key reads from that field."""
        metrics = {
            "bid_rate": 0.99,  # deal-level (would fail cap)
            "seat_bid_propensity": 0.5,  # seat-level (passes)
            "make_rate": 0.7,
        }
        result = run_lambda_sweep.apply_guardrails(
            metrics, bid_rate_key="seat_bid_propensity"
        )
        assert result["all_pass"] is True
        assert result["pass_bid_rate_cap"] is True

    def test_seat_propensity_below_floor(self):
        """Seat propensity below floor triggers guardrail failure."""
        metrics = {
            "bid_rate": 0.13,  # deal-level (would pass floor)
            "seat_bid_propensity": 0.034,  # seat-level (below 0.05 floor)
            "make_rate": 1.0,
        }
        result = run_lambda_sweep.apply_guardrails(
            metrics, bid_rate_key="seat_bid_propensity"
        )
        assert result["all_pass"] is False
        assert result["pass_bid_rate_floor"] is False

    def test_missing_key_defaults_to_pass(self):
        """If the specified key is missing, guardrail passes (None treated as ok)."""
        metrics = {"make_rate": 0.7}
        result = run_lambda_sweep.apply_guardrails(
            metrics, bid_rate_key="seat_bid_propensity"
        )
        assert result["pass_bid_rate_floor"] is True
        assert result["pass_bid_rate_cap"] is True

    def test_raw_value_avoids_rounding_boundary_flip(self):
        """Using raw (unrounded) value prevents rounding from flipping boundary decisions.

        Example: raw 0.04996 rounds to 0.0500, which is >= 0.05 floor.
        But the raw value 0.04996 is < 0.05 and should FAIL.
        """
        raw_val = 0.04996
        rounded_val = round(raw_val, 4)  # 0.0500
        # Rounded value would pass (0.0500 >= 0.05)
        metrics_rounded = {"seat_bid_propensity": rounded_val, "make_rate": 1.0}
        result_rounded = run_lambda_sweep.apply_guardrails(
            metrics_rounded, bid_rate_key="seat_bid_propensity"
        )
        assert (
            result_rounded["pass_bid_rate_floor"] is True
        )  # Wrong! Rounding hides failure

        # Raw value correctly fails (0.04996 < 0.05)
        metrics_raw = {"seat_bid_propensity_raw": raw_val, "make_rate": 1.0}
        result_raw = run_lambda_sweep.apply_guardrails(
            metrics_raw, bid_rate_key="seat_bid_propensity_raw"
        )
        assert result_raw["pass_bid_rate_floor"] is False  # Correct


# ---------------------------------------------------------------------------
# select_lambda_star with seat-level guardrails
# ---------------------------------------------------------------------------


class TestSelectLambdaStarSeatLevel:
    def test_selects_lambda_0_5_with_seat_propensity(self):
        """With seat-level propensity, lambda=0.5 is selected (best net_eppd that passes).

        This mirrors the corrected real-world scenario:
        - lambda=0.0 through 0.5 pass (seat propensity in [0.05, 0.95])
        - lambda=0.5 has best net_eppd
        - lambda=2.0 fails (seat propensity < 0.05)
        """
        sweep_results = [
            {
                "risk_lambda": 0.0,
                "net_eppd": 2.238,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 0.05,
                "net_eppd": 2.270,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 0.1,
                "net_eppd": 2.685,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 0.2,
                "net_eppd": 2.905,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 0.5,
                "net_eppd": 3.122,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 1.0,
                "net_eppd": 2.216,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 2.0,
                "net_eppd": 0.696,
                "guardrails": {"all_pass": False},
            },
        ]
        result = run_lambda_sweep.select_lambda_star(sweep_results, epsilon=0.02)
        assert result == 0.5

    def test_old_behavior_would_select_lambda_1(self):
        """Demonstrates the old (incorrect) behavior: only lambda=1.0 and 2.0 pass
        because deal-level bid_rate was used for cap (all others > 0.95).
        """
        # This is the old behavior: deal-level bid_rate > 0.95 for lambda 0-0.5
        sweep_results = [
            {
                "risk_lambda": 0.0,
                "net_eppd": 2.238,
                "guardrails": {"all_pass": False},
            },
            {
                "risk_lambda": 0.05,
                "net_eppd": 2.270,
                "guardrails": {"all_pass": False},
            },
            {
                "risk_lambda": 0.1,
                "net_eppd": 2.685,
                "guardrails": {"all_pass": False},
            },
            {
                "risk_lambda": 0.2,
                "net_eppd": 2.905,
                "guardrails": {"all_pass": False},
            },
            {
                "risk_lambda": 0.5,
                "net_eppd": 3.122,
                "guardrails": {"all_pass": False},
            },
            {
                "risk_lambda": 1.0,
                "net_eppd": 2.216,
                "guardrails": {"all_pass": True},
            },
            {
                "risk_lambda": 2.0,
                "net_eppd": 0.696,
                "guardrails": {"all_pass": True},
            },
        ]
        result = run_lambda_sweep.select_lambda_star(sweep_results, epsilon=0.02)
        # Old behavior: selects 1.0 (best net_eppd among 1.0 and 2.0)
        assert result == 1.0


# ---------------------------------------------------------------------------
# format_sweep_summary includes seat_bid_propensity
# ---------------------------------------------------------------------------


class TestFormatSweepSummaryPropensity:
    def test_includes_seat_bid_propensity(self):
        """format_sweep_summary includes seat_bid_propensity when present."""
        sweep_results = [
            {
                "risk_lambda": 0.0,
                "net_eppd": 2.0,
                "bid_rate": 1.0,
                "make_rate": 0.97,
                "seat_bid_propensity": 0.468,
                "guardrails": {"all_pass": True},
            },
        ]
        summary = run_lambda_sweep.format_sweep_summary(
            grid=[0.0],
            sweep_results=sweep_results,
            lambda_star=0.0,
            seed=42,
            n_per=100,
            pass_threshold=0.0,
            artifact_path="test.json",
            epsilon=0.02,
        )
        assert "seat_bid_propensity" in summary["results"][0]
        assert summary["results"][0]["seat_bid_propensity"] == 0.468

    def test_omits_seat_bid_propensity_when_absent(self):
        """format_sweep_summary omits seat_bid_propensity when not present."""
        sweep_results = [
            {
                "risk_lambda": 0.0,
                "net_eppd": 2.0,
                "bid_rate": 0.5,
                "make_rate": 0.7,
                "guardrails": {"all_pass": True},
            },
        ]
        summary = run_lambda_sweep.format_sweep_summary(
            grid=[0.0],
            sweep_results=sweep_results,
            lambda_star=0.0,
            seed=42,
            n_per=100,
            pass_threshold=0.0,
            artifact_path="test.json",
            epsilon=0.02,
        )
        assert "seat_bid_propensity" not in summary["results"][0]

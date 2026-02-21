"""
Unit tests for net-differential expected points per deal (net_eppd).

Tests the _net_differential_points function and verifies net metrics
appear correctly in evaluator output.
"""

import json
from pathlib import Path

from bid_euchre.reporting.evaluator import (
    _net_differential_points,
    compute_cvar,
    compute_downside_variance,
    generate_bidder_evaluation,
)


def _make_hand_end_record(
    winning_bid: int,
    bidder_position: int,
    t0: int,
    t1: int,
    deal_id: int = 1,
    strategy_id: str = "test_strategy",
) -> dict:
    """Create a minimal hand_end record for testing."""
    return {
        "event": "hand_end",
        "deal_id": deal_id,
        "strategy_id": strategy_id,
        "winning_bid": winning_bid,
        "bidder_position": bidder_position,
        "t0": t0,
        "t1": t1,
        "timestamp": f"2026-01-01T00:00:{deal_id:02d}Z",
    }


def test_net_differential_make():
    """bid_n=5, tricks=7 (team0 bidder) → net = 2*7 - 10 = 4."""
    record = _make_hand_end_record(winning_bid=5, bidder_position=0, t0=7, t1=3)
    assert _net_differential_points(record) == 4


def test_net_differential_set():
    """bid_n=6, tricks=3 (team0 bidder) → net = 3 - 6 - 10 = -13."""
    # Set: bidder gets -6 (= -bid), opponent gets 7 (their tricks = t1)
    # net = -6 - 7 = -13
    record = _make_hand_end_record(winning_bid=6, bidder_position=0, t0=3, t1=7)
    assert _net_differential_points(record) == -13


def test_net_differential_team1_bidder_make():
    """Bidder on team1 (seat 1), makes bid: bid_n=4, t0=3, t1=7 → net = 2*7 - 10 = 4."""
    record = _make_hand_end_record(winning_bid=4, bidder_position=1, t0=3, t1=7)
    assert _net_differential_points(record) == 4


def test_net_differential_team1_bidder_set():
    """Bidder on team1 (seat 3), set: bid_n=6, t0=7, t1=3 → net = 3 - 6 - 10 = -13."""
    record = _make_hand_end_record(winning_bid=6, bidder_position=3, t0=7, t1=3)
    assert _net_differential_points(record) == -13


def test_net_differential_no_bid():
    """Returns None for all-pass (no winning_bid)."""
    record = {
        "event": "hand_end",
        "deal_id": 1,
        "strategy_id": "test",
        "winning_bid": None,
        "bidder_position": None,
        "t0": 5,
        "t1": 5,
    }
    assert _net_differential_points(record) is None


def test_net_differential_exact_make():
    """bid_n=5, tricks=5 (exactly make) → net = 2*5 - 10 = 0."""
    record = _make_hand_end_record(winning_bid=5, bidder_position=0, t0=5, t1=5)
    assert _net_differential_points(record) == 0


def test_net_differential_slam():
    """bid_n=10, tricks=10 (all tricks) → net = 2*10 - 10 = 10."""
    record = _make_hand_end_record(winning_bid=10, bidder_position=0, t0=10, t1=0)
    assert _net_differential_points(record) == 10


def test_net_eppd_in_eval_output(tmp_path: Path):
    """Verify net_expected_points and related keys appear in evaluator output."""
    # Create a minimal JSONL log directory
    run_dir = tmp_path / "test_run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    datasets_dir = run_dir / "datasets"
    datasets_dir.mkdir()
    meta_path = run_dir / "meta.json"
    meta_path.write_text(
        json.dumps({"data_dir": str(datasets_dir), "logs_dir": str(logs_dir)})
    )

    # Write some hand_end records
    log_file = logs_dir / "game_001.jsonl"
    records = [
        _make_hand_end_record(winning_bid=5, bidder_position=0, t0=7, t1=3, deal_id=1),
        _make_hand_end_record(winning_bid=6, bidder_position=0, t0=3, t1=7, deal_id=2),
        _make_hand_end_record(winning_bid=4, bidder_position=2, t0=6, t1=4, deal_id=3),
    ]
    log_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    result = generate_bidder_evaluation(run_dir)
    assert result is not None

    with result.open() as f:
        data = json.load(f)

    assert data["primary_series"] == "net_bidder_team_points"
    assert len(data["strategies"]) == 1

    strategy = data["strategies"][0]
    assert "net_expected_points" in strategy
    assert "net_expected_points_per_deal" in strategy
    assert "net_cvar_5" in strategy
    assert "net_downside_variance" in strategy
    assert "net_bidder_team_points" in strategy
    assert isinstance(strategy["net_bidder_team_points"], list)
    assert len(strategy["net_bidder_team_points"]) == 3


def test_eppd_still_present(tmp_path: Path):
    """Old expected_points (eppd) keys must still be present for backward compat."""
    run_dir = tmp_path / "test_run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    datasets_dir = run_dir / "datasets"
    datasets_dir.mkdir()
    meta_path = run_dir / "meta.json"
    meta_path.write_text(
        json.dumps({"data_dir": str(datasets_dir), "logs_dir": str(logs_dir)})
    )

    log_file = logs_dir / "game_001.jsonl"
    records = [
        _make_hand_end_record(winning_bid=5, bidder_position=0, t0=7, t1=3, deal_id=1),
    ]
    log_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    result = generate_bidder_evaluation(run_dir)
    assert result is not None

    with result.open() as f:
        data = json.load(f)

    strategy = data["strategies"][0]
    # Old keys still present
    assert "expected_points" in strategy
    assert "expected_points_per_deal" in strategy
    assert "cvar_5" in strategy
    assert "downside_variance" in strategy
    assert "bidder_team_points" in strategy


def test_net_cvar_computed_on_net_series():
    """CVaR should be computed on net differential values, not bidder-only values."""
    # Make case: bid=5, tricks=7 → bidder_pts=7, net=4
    # Set case: bid=6, tricks=3 → bidder_pts=-6, net=-13
    # CVaR on net series uses net values, not bidder team values
    net_values = [4, -13, 0, 2, -8]
    bidder_values = [7, -6, 5, 6, -5]

    net_cvar = compute_cvar(net_values)
    bidder_cvar = compute_cvar(bidder_values)

    # These must differ since the series are different
    assert net_cvar != bidder_cvar
    # Net CVaR should be based on worst net values
    assert net_cvar == -13.0  # worst 5% of 5 values = 1 value = -13


def test_net_downside_variance_computed_on_net_series():
    """Downside variance should be computed on net differential values."""
    net_values = [4, -13, 0, 2, -8]
    bidder_values = [7, -6, 5, 6, -5]

    net_dv = compute_downside_variance(net_values)
    bidder_dv = compute_downside_variance(bidder_values)

    assert net_dv != bidder_dv
    assert net_dv is not None
    assert bidder_dv is not None


def test_metric_definitions_include_net_keys(tmp_path: Path):
    """Metric definitions should document net-differential metrics."""
    run_dir = tmp_path / "test_run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True)
    datasets_dir = run_dir / "datasets"
    datasets_dir.mkdir()
    meta_path = run_dir / "meta.json"
    meta_path.write_text(
        json.dumps({"data_dir": str(datasets_dir), "logs_dir": str(logs_dir)})
    )

    log_file = logs_dir / "game_001.jsonl"
    records = [
        _make_hand_end_record(winning_bid=5, bidder_position=0, t0=7, t1=3, deal_id=1),
    ]
    log_file.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    result = generate_bidder_evaluation(run_dir)
    with result.open() as f:
        data = json.load(f)

    defs = data["metric_definitions"]
    assert "net_expected_points" in defs
    assert "net_expected_points_per_deal" in defs
    assert "net_cvar_5" in defs
    assert "net_downside_variance" in defs
    # Old definitions still present
    assert "expected_points" in defs
    assert "cvar_5" in defs

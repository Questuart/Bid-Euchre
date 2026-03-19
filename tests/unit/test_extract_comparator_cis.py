"""
Unit tests for extract_comparator_cis.py: JSONL parsing, metrics, bootstrap,
batch coherence validation, and manifest loading.

Import via importlib.util (same pattern as test_h2h_battery.py) since
scripts/internal/ has no __init__.py.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Import script module via importlib.util
# ---------------------------------------------------------------------------

_EXTRACTOR_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "extract_comparator_cis.py"
)
_spec = importlib.util.spec_from_file_location(
    "extract_comparator_cis", _EXTRACTOR_SCRIPT
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_parse_jsonl_points = _mod._parse_jsonl_points
_cvar_5 = _mod._cvar_5
_compute_bidder_metrics = _mod._compute_bidder_metrics
_bootstrap_pairwise_pvalue = _mod._bootstrap_pairwise_pvalue
_make_per_deal_net_array = _mod._make_per_deal_net_array
_extract_timestamp = _mod._extract_timestamp
_load_manifest_runs = _mod._load_manifest_runs
_validate_batch_coherence = _mod._validate_batch_coherence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path, records):
    """Write records as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _make_hand_end(
    t0=5,
    t1=5,
    winning_bid=6,
    bidder_position=0,
    redeal_flag=False,
    contract="suit",
    trump="S",
):
    """Create a synthetic hand_end JSONL record."""
    rec = {
        "event": "hand_end",
        "t0": t0,
        "t1": t1,
        "contract": contract,
        "trump": trump,
        "winning_bid": winning_bid,
        "bidder_position": bidder_position,
        "redeal_flag": redeal_flag,
    }
    if redeal_flag:
        rec["winning_bid"] = None
        rec["bidder_position"] = None
        rec["t0"] = 0
        rec["t1"] = 0
    return rec


def _make_meta_json(run_dir, seed=42, n_per=100, config_sha256=None):
    """Create a synthetic meta.json in run_dir."""
    meta = {
        "seed": seed,
        "config": {
            "parameters": {"n_per": n_per},
        },
    }
    if config_sha256 is not None:
        meta["config_sha256"] = config_sha256
    meta_path = Path(run_dir) / "meta.json"
    meta_path.write_text(json.dumps(meta))


def _make_evaluation_json(run_dir, deals_total=100, bid_rate=0.5, net_eppd=1.0):
    """Create a synthetic evaluation.json in run_dir."""
    eval_dir = Path(run_dir) / "reports" / "bidding_strategy"
    eval_dir.mkdir(parents=True, exist_ok=True)
    evaluation = {
        "strategies": [
            {
                "deals_total": deals_total,
                "hands_with_bids": int(deals_total * bid_rate),
                "expected_points_per_deal": net_eppd + 0.5,
                "net_expected_points_per_deal": net_eppd,
                "make_rate": 0.7,
                "bid_rate": bid_rate,
            }
        ]
    }
    (eval_dir / "evaluation.json").write_text(json.dumps(evaluation))


def _make_manifest(
    runs_dir, members, seed=42, n_per=100, policies=None, experiment_name="test"
):
    """Create a synthetic batch manifest."""
    if policies is None:
        policies = sorted(set(k.rsplit("_seat", 1)[0] for k in members.keys()))
    manifest = {
        "schema": "batch_manifest_v1",
        "batch_id": f"{experiment_name}_{seed}_20260302_120000",
        "created_at_utc": "2026-03-02T12:00:00Z",
        "experiment_name": experiment_name,
        "seed": seed,
        "n_per": n_per,
        "mode": "single_seat",
        "expected_policies": policies,
        "expected_seats": 4,
        "members": members,
    }
    manifest_path = Path(runs_dir) / f"batch_manifest_{experiment_name}_{seed}.json"
    manifest_path.write_text(json.dumps(manifest))
    return str(manifest_path)


# ---------------------------------------------------------------------------
# Tests: _parse_jsonl_points
# ---------------------------------------------------------------------------


class TestParseJsonlPoints:
    def test_basic_bid_hand(self, tmp_path):
        """Parses a single bid hand correctly."""
        records = [_make_hand_end(t0=7, t1=3, winning_bid=6, bidder_position=0)]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        assert data["deals_total"] == 1
        assert len(data["bidder_team_points"]) == 1
        assert len(data["net_bidder_team_points"]) == 1

    def test_all_pass_redeal(self, tmp_path):
        """All-pass redeals count toward deals_total but not bid arrays."""
        records = [
            _make_hand_end(redeal_flag=True),
            _make_hand_end(t0=6, t1=4, winning_bid=5, bidder_position=0),
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        assert data["deals_total"] == 2
        assert len(data["bidder_team_points"]) == 1

    def test_empty_file(self, tmp_path):
        """Empty JSONL file returns zeros."""
        log = tmp_path / "empty.jsonl"
        log.write_text("")
        data = _parse_jsonl_points(log)
        assert data["deals_total"] == 0
        assert data["bidder_team_points"] == []
        assert data["net_bidder_team_points"] == []

    def test_team1_bidder(self, tmp_path):
        """Bidder at seat 1 (team 1) gets t1 as bidder points."""
        records = [_make_hand_end(t0=3, t1=7, winning_bid=6, bidder_position=1)]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        # bidder_position=1 is team1, so net = pts_t1 - pts_t0
        assert len(data["net_bidder_team_points"]) == 1
        assert data["net_bidder_team_points"][0] > 0  # t1=7 > t0=3

    def test_ignores_non_hand_end_events(self, tmp_path):
        """Non-hand_end events are ignored."""
        records = [
            {"event": "game_start", "t0": 0, "t1": 0},
            _make_hand_end(t0=5, t1=5, winning_bid=5, bidder_position=0),
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        assert data["deals_total"] == 1

    def test_multiple_hands(self, tmp_path):
        """Multiple hands accumulate correctly."""
        records = [
            _make_hand_end(t0=6, t1=4, winning_bid=5, bidder_position=0),
            _make_hand_end(t0=8, t1=2, winning_bid=7, bidder_position=0),
            _make_hand_end(redeal_flag=True),
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        assert data["deals_total"] == 3
        assert len(data["bidder_team_points"]) == 2

    def test_by_contract_basic(self, tmp_path):
        """Per-contract tracking counts deals correctly."""
        records = [
            _make_hand_end(
                t0=7, t1=3, winning_bid=6, bidder_position=0, contract="suit"
            ),
            _make_hand_end(
                t0=6,
                t1=4,
                winning_bid=5,
                bidder_position=0,
                contract="high",
                trump=None,
            ),
            _make_hand_end(
                t0=4, t1=6, winning_bid=5, bidder_position=1, contract="low", trump=None
            ),
            _make_hand_end(
                t0=8, t1=2, winning_bid=7, bidder_position=0, contract="suit"
            ),
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        bc = data["by_contract"]
        assert bc["suit"]["deals_total"] == 2
        assert bc["high"]["deals_total"] == 1
        assert bc["low"]["deals_total"] == 1
        assert len(bc["suit"]["bidder_team_points"]) == 2
        assert len(bc["high"]["bidder_team_points"]) == 1
        assert len(bc["low"]["bidder_team_points"]) == 1

    def test_all_pass_does_not_poison_high(self, tmp_path):
        """All-pass redeals (contract='high' from dummy_ctype) must NOT inflate
        by_contract['high']['deals_total']. This is the regression test for F1:
        simulation.py:426 uses dummy_ctype='high' for all-pass, which would
        poison the 'high' contract metrics if counted."""
        records = [
            # Real "high" contract bid
            _make_hand_end(
                t0=6,
                t1=4,
                winning_bid=5,
                bidder_position=0,
                contract="high",
                trump=None,
            ),
            # All-pass redeal — simulation.py logs contract="high" (dummy_ctype)
            _make_hand_end(redeal_flag=True, contract="high"),
            # Another all-pass with contract="high"
            _make_hand_end(redeal_flag=True, contract="high"),
            # Real suit bid
            _make_hand_end(
                t0=7, t1=3, winning_bid=6, bidder_position=0, contract="suit"
            ),
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)

        # Pooled deals_total includes all-pass
        assert data["deals_total"] == 4

        # Per-contract "high" must only count the 1 real bid, NOT the 2 all-pass
        bc = data["by_contract"]
        assert bc["high"]["deals_total"] == 1, (
            f"All-pass redeals with dummy contract='high' must not inflate "
            f"by_contract['high']['deals_total']; got {bc['high']['deals_total']}"
        )
        assert len(bc["high"]["bidder_team_points"]) == 1

        # Suit should be unaffected
        assert bc["suit"]["deals_total"] == 1
        assert len(bc["suit"]["bidder_team_points"]) == 1

        # Low should have no deals
        assert bc["low"]["deals_total"] == 0

    def test_per_contract_bid_rate_is_one(self, tmp_path):
        """Per-contract bid_rate is always 1.0 by construction (every deal
        in a contract bucket had a bid)."""
        records = [
            _make_hand_end(
                t0=7, t1=3, winning_bid=6, bidder_position=0, contract="suit"
            ),
            _make_hand_end(
                t0=6,
                t1=4,
                winning_bid=5,
                bidder_position=0,
                contract="high",
                trump=None,
            ),
            _make_hand_end(redeal_flag=True, contract="high"),  # all-pass, excluded
        ]
        log = tmp_path / "game.jsonl"
        _write_jsonl(log, records)
        data = _parse_jsonl_points(log)
        for ct in ("suit", "high"):
            ct_data = data["by_contract"][ct]
            if ct_data["deals_total"] > 0:
                metrics = _compute_bidder_metrics(ct_data)
                assert (
                    metrics["bid_rate"] == pytest.approx(1.0)
                ), f"Per-contract bid_rate for '{ct}' should be 1.0, got {metrics['bid_rate']}"


# ---------------------------------------------------------------------------
# Tests: _cvar_5
# ---------------------------------------------------------------------------


class TestCvar5:
    def test_uniform_values(self):
        """CVaR-5% of uniform values is mean of worst 5%."""
        arr = np.arange(100, dtype=float)
        cvar = _cvar_5(arr)
        # Worst 5% = [0, 1, 2, 3, 4], mean = 2.0
        assert cvar == pytest.approx(2.0)

    def test_single_value(self):
        """Single value: CVaR-5% is that value."""
        arr = np.array([42.0])
        assert _cvar_5(arr) == pytest.approx(42.0)

    def test_worst_5_percent(self):
        """Verify CVaR picks the correct tail."""
        arr = np.array([-100.0] + [10.0] * 19)  # 20 values, worst 5% = 1 value
        cvar = _cvar_5(arr)
        assert cvar == pytest.approx(-100.0)

    def test_all_same(self):
        """All same values → CVaR equals that value."""
        arr = np.array([5.0] * 50)
        assert _cvar_5(arr) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Tests: _make_per_deal_net_array
# ---------------------------------------------------------------------------


class TestMakePerDealNetArray:
    def test_array_length_equals_deals_total(self):
        """Output array length = deals_total."""
        data = {
            "net_bidder_team_points": [1.0, 2.0, 3.0],
            "deals_total": 10,
        }
        arr = _make_per_deal_net_array(data)
        assert len(arr) == 10

    def test_mean_equals_net_eppd(self):
        """Mean of array should approximate net_eppd."""
        data = {
            "net_bidder_team_points": [2.0, 4.0],
            "deals_total": 4,
        }
        arr = _make_per_deal_net_array(data)
        # sum = 6.0, deals = 4, net_eppd = 1.5
        assert arr.mean() == pytest.approx(1.5)

    def test_pass_hands_are_zeros(self):
        """Pass hands contribute zeros."""
        data = {
            "net_bidder_team_points": [5.0],
            "deals_total": 5,
        }
        arr = _make_per_deal_net_array(data)
        assert (arr == 0).sum() == 4
        assert arr[0] == 5.0


# ---------------------------------------------------------------------------
# Tests: _bootstrap_pairwise_pvalue
# ---------------------------------------------------------------------------


class TestBootstrapPairwisePvalue:
    def test_identical_arrays_high_pvalue(self):
        """Identical arrays should produce high p-value."""
        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        p = _bootstrap_pairwise_pvalue(a, b, n_bootstrap=200, seed=42)
        assert p > 0.5

    def test_separated_arrays_low_pvalue(self):
        """Well-separated arrays should produce low p-value."""
        a = np.array([100.0] * 50)
        b = np.array([0.0] * 50)
        p = _bootstrap_pairwise_pvalue(a, b, n_bootstrap=500, seed=42)
        assert p < 0.05

    def test_seed_determinism(self):
        """Same seed produces same p-value."""
        a = np.random.RandomState(1).randn(30)
        b = np.random.RandomState(2).randn(30)
        p1 = _bootstrap_pairwise_pvalue(a, b, n_bootstrap=100, seed=99)
        p2 = _bootstrap_pairwise_pvalue(a, b, n_bootstrap=100, seed=99)
        assert p1 == p2


# ---------------------------------------------------------------------------
# Tests: _compute_bidder_metrics
# ---------------------------------------------------------------------------


class TestComputeBidderMetrics:
    def test_basic_metrics(self):
        """Basic metrics computation from parsed data."""
        data = {
            "bidder_team_points": [6.0, 4.0, 8.0],
            "net_bidder_team_points": [2.0, -2.0, 4.0],
            "deals_total": 5,
        }
        m = _compute_bidder_metrics(data)
        assert m["deals_total"] == 5
        assert m["hands_with_bids"] == 3
        assert m["bid_rate"] == pytest.approx(0.6)
        assert m["eppd"] == pytest.approx(18.0 / 5)
        assert m["net_eppd"] == pytest.approx(4.0 / 5)

    def test_zero_deals(self):
        """Zero deals returns zero metrics."""
        data = {
            "bidder_team_points": [],
            "net_bidder_team_points": [],
            "deals_total": 0,
        }
        m = _compute_bidder_metrics(data)
        assert m["eppd"] == 0.0
        assert m["net_eppd"] == 0.0
        assert m["bid_rate"] == 0.0

    def test_no_bids(self):
        """All passes: bid_rate=0, make_rate=0."""
        data = {
            "bidder_team_points": [],
            "net_bidder_team_points": [],
            "deals_total": 10,
        }
        m = _compute_bidder_metrics(data)
        assert m["bid_rate"] == 0.0
        assert m["make_rate"] == 0.0
        assert m["hands_with_bids"] == 0


# ---------------------------------------------------------------------------
# Tests: _validate_batch_coherence
# ---------------------------------------------------------------------------


class TestBatchCoherenceValidation:
    def test_same_seed_passes(self, tmp_path):
        """Consistent metadata across seats passes validation."""
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42, n_per=100)
            dirs.append((seat, d))
        # Should not raise
        _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_mismatched_seed_fails_strict(self, tmp_path):
        """Mismatched seeds cause sys.exit in strict mode."""
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42 if seat < 3 else 99, n_per=100)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_mismatched_seed_warns_nonstrict(self, tmp_path, capsys):
        """Mismatched seeds warn in non-strict mode but don't exit."""
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42 if seat < 3 else 99, n_per=100)
            dirs.append((seat, d))
        _validate_batch_coherence(dirs, "test_bidder", strict=False)
        captured = capsys.readouterr()
        assert "mixed seeds" in captured.err

    def test_mismatched_n_per_fails_strict(self, tmp_path):
        """Mismatched n_per causes sys.exit in strict mode."""
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42, n_per=100 if seat < 3 else 200)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_missing_meta_json_fails_strict(self, tmp_path):
        """Missing meta.json causes sys.exit in strict mode."""
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            if seat < 3:
                _make_meta_json(d, seed=42, n_per=100)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_mismatched_config_sha256_fails_strict(self, tmp_path):
        """Mismatched config_sha256 causes sys.exit in strict mode."""
        sha_a = "a" * 64
        sha_b = "b" * 64
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            sha = sha_a if seat < 3 else sha_b
            _make_meta_json(d, seed=42, n_per=100, config_sha256=sha)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_same_config_sha256_passes(self, tmp_path):
        """Matching config_sha256 across seats passes validation."""
        sha = "c" * 64
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42, n_per=100, config_sha256=sha)
            dirs.append((seat, d))
        _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_partial_missing_config_sha256_fails_strict(self, tmp_path):
        """3 seats with hash + 1 seat missing hash fails strict mode."""
        sha = "d" * 64
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            # Seat 3 has no config_sha256 (simulates older meta.json)
            cfg_sha = sha if seat < 3 else None
            _make_meta_json(d, seed=42, n_per=100, config_sha256=cfg_sha)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_partial_missing_config_sha256_warns_nonstrict(self, tmp_path):
        """3 seats with hash + 1 missing does NOT exit in non-strict mode."""
        sha = "d" * 64
        dirs = []
        for seat in range(4):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            cfg_sha = sha if seat < 3 else None
            _make_meta_json(d, seed=42, n_per=100, config_sha256=cfg_sha)
            dirs.append((seat, d))
        # Non-strict: should warn but not exit
        _validate_batch_coherence(dirs, "test_bidder", strict=False)

    def test_n_per_off_by_one_passes(self, tmp_path):
        """n_per varying by ±1 (uneven seat split) passes validation."""
        dirs = []
        # Simulates n_per=101 split across 4 seats: 26, 25, 25, 25
        for seat, n in enumerate([26, 25, 25, 25]):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42, n_per=n)
            dirs.append((seat, d))
        _validate_batch_coherence(dirs, "test_bidder", strict=True)

    def test_n_per_spread_too_large_fails(self, tmp_path):
        """n_per spread > 1 causes sys.exit in strict mode."""
        dirs = []
        for seat, n in enumerate([100, 100, 100, 102]):
            d = tmp_path / f"run_seat{seat}"
            d.mkdir()
            _make_meta_json(d, seed=42, n_per=n)
            dirs.append((seat, d))
        with pytest.raises(SystemExit):
            _validate_batch_coherence(dirs, "test_bidder", strict=True)


# ---------------------------------------------------------------------------
# Tests: _load_manifest_runs
# ---------------------------------------------------------------------------


class TestManifestLoading:
    def test_valid_manifest(self, tmp_path):
        """Valid manifest loads and resolves all directories."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        members = {}
        for seat in range(4):
            dirname = f"run_alpha_seat{seat}"
            (runs_dir / dirname).mkdir()
            members[f"alpha_seat{seat}"] = dirname

        manifest_path = _make_manifest(runs_dir, members, policies=["alpha"])
        result = _load_manifest_runs(manifest_path, ["alpha"], str(runs_dir))
        assert "alpha" in result
        assert len(result["alpha"]) == 4

    def test_missing_dir_fails(self, tmp_path):
        """Manifest referencing non-existent directory causes sys.exit."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        members = {}
        for seat in range(4):
            members[f"alpha_seat{seat}"] = f"run_alpha_seat{seat}"
            if seat < 3:  # seat 3 dir is missing
                (runs_dir / f"run_alpha_seat{seat}").mkdir()

        manifest_path = _make_manifest(runs_dir, members, policies=["alpha"])
        with pytest.raises(SystemExit):
            _load_manifest_runs(manifest_path, ["alpha"], str(runs_dir))

    def test_bidder_not_in_manifest_fails(self, tmp_path):
        """Bidder in battery but not in manifest causes sys.exit."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        members = {}
        for seat in range(4):
            dirname = f"run_alpha_seat{seat}"
            (runs_dir / dirname).mkdir()
            members[f"alpha_seat{seat}"] = dirname

        manifest_path = _make_manifest(runs_dir, members, policies=["alpha"])
        with pytest.raises(SystemExit):
            _load_manifest_runs(manifest_path, ["alpha", "beta"], str(runs_dir))

    def test_wrong_schema_fails(self, tmp_path):
        """Wrong schema version causes sys.exit."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        manifest_path = runs_dir / "bad_manifest.json"
        manifest_path.write_text(json.dumps({"schema": "wrong_v99"}))
        with pytest.raises(SystemExit):
            _load_manifest_runs(str(manifest_path), ["alpha"], str(runs_dir))


# ---------------------------------------------------------------------------
# Tests: CLI --skip-run contract (subprocess-level)
# ---------------------------------------------------------------------------


class TestCLISkipRunContract:
    """Test CLI-level behavior of --skip-run with manifest requirements."""

    def _run_extractor(self, args, env_extra=None):
        """Run extract_comparator_cis.py as subprocess."""
        env = {**__import__("os").environ, "PYTHONPATH": "src"}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(_EXTRACTOR_SCRIPT)] + args,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_single_seat_no_manifest_hard_fails(self, tmp_path):
        """--single-seat without --manifest or --allow-legacy-seat-discovery fails."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        battery = {"bidders": {"alpha": {"net_eppd": 0, "eppd": 0}}}
        (artifacts / "battery.json").write_text(json.dumps(battery))

        result = self._run_extractor(
            [
                "--artifacts-dir",
                str(artifacts),
                "--runs-dir",
                str(tmp_path / "runs"),
                "--seed",
                "42",
                "--battery-file",
                "battery.json",
                "--single-seat",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert result.returncode != 0
        assert "requires --manifest" in result.stderr

    def test_manifest_flag_validates(self, tmp_path):
        """--manifest with non-existent file fails with clear error."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        battery = {"bidders": {"alpha": {"net_eppd": 0, "eppd": 0}}}
        (artifacts / "battery.json").write_text(json.dumps(battery))

        result = self._run_extractor(
            [
                "--artifacts-dir",
                str(artifacts),
                "--runs-dir",
                str(tmp_path / "runs"),
                "--seed",
                "42",
                "--battery-file",
                "battery.json",
                "--single-seat",
                "--manifest",
                "/nonexistent/manifest.json",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert result.returncode != 0
        assert "Manifest not found" in result.stderr

    def test_allow_legacy_no_runs_fails(self, tmp_path):
        """--allow-legacy-seat-discovery with no matching runs fails at JSONL stage."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        runs = tmp_path / "runs"
        runs.mkdir()
        battery = {"bidders": {"alpha": {"net_eppd": 0, "eppd": 0}}}
        (artifacts / "battery.json").write_text(json.dumps(battery))

        result = self._run_extractor(
            [
                "--artifacts-dir",
                str(artifacts),
                "--runs-dir",
                str(runs),
                "--seed",
                "42",
                "--battery-file",
                "battery.json",
                "--single-seat",
                "--allow-legacy-seat-discovery",
                "--output",
                str(tmp_path / "out.json"),
            ]
        )
        assert result.returncode != 0
        # Should fail trying to find run dirs
        assert "No run dir" in result.stderr

    def test_help_includes_manifest_flags(self):
        """--help output includes the new flags."""
        result = self._run_extractor(["--help"])
        assert result.returncode == 0
        assert "--manifest" in result.stdout
        assert "--allow-legacy-seat-discovery" in result.stdout


# ---------------------------------------------------------------------------
# Tests: _extract_timestamp
# ---------------------------------------------------------------------------


class TestExtractTimestamp:
    def test_standard_run_dir_name(self):
        """Extracts timestamp from standard run directory name."""
        p = Path("auction_comparator_olsa_seat0_42_20260302_091500")
        assert _extract_timestamp(p) == "20260302_091500"

    def test_short_name(self):
        """Short names return empty string."""
        p = Path("short")
        assert _extract_timestamp(p) == ""

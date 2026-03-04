"""
Unit tests for dual-seat comparator mode.

Tests cover: config generation, merge logic, manifest schema, format_json mode.
"""

import importlib.util
import json
from pathlib import Path

# Import via importlib to avoid sys.path.insert anti-pattern.
_COMPARATOR_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "run_auction_comparator.py"
)
_spec = importlib.util.spec_from_file_location(
    "run_auction_comparator", _COMPARATOR_SCRIPT
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
format_json = _mod.format_json
_merge_dual_seat_evaluations = _mod._merge_dual_seat_evaluations
_write_dual_seat_manifest = _mod._write_dual_seat_manifest


def _make_fake_eval(deals_total, hands_with_bids, eppd, net_eppd, make_rate):
    """Create a minimal evaluation.json-like dict for test injection."""
    return {
        "strategies": [
            {
                "deals_total": deals_total,
                "hands_with_bids": hands_with_bids,
                "expected_points_per_deal": eppd,
                "net_expected_points_per_deal": net_eppd,
                "make_rate": make_rate,
                "bid_rate": hands_with_bids / deals_total if deals_total > 0 else 0,
            }
        ]
    }


class TestMergeDualSeatEvaluations:
    """Test dual-seat evaluation merging across 2 teams."""

    def test_two_teams_merge_correctly(self):
        """Merge 2 team evaluations into a single bidder metric."""
        policies = [{"name": "test_bidder"}]
        run_dirs = {
            "test_bidder_team0": "/fake/team0",
            "test_bidder_team1": "/fake/team1",
        }

        # Team 0: 100 deals, 50 bids, eppd=2.0, net_eppd=1.0, make_rate=0.8
        # Team 1: 100 deals, 60 bids, eppd=3.0, net_eppd=1.5, make_rate=0.6
        fake_evals = {
            "/fake/team0": _make_fake_eval(100, 50, 2.0, 1.0, 0.8),
            "/fake/team1": _make_fake_eval(100, 60, 3.0, 1.5, 0.6),
        }

        metrics, missing = _merge_dual_seat_evaluations(
            run_dirs, policies, load_fn=lambda d: fake_evals[d]
        )

        assert len(missing) == 0
        assert "test_bidder" in metrics
        m = metrics["test_bidder"]

        # Merged: 200 deals, 110 bid hands
        assert m["deals_total"] == 200
        assert m["hands_with_bids"] == 110

        # eppd = (2.0*100 + 3.0*100) / 200 = 2.5
        assert abs(m["expected_points_per_deal"] - 2.5) < 1e-9

        # net_eppd = (1.0*100 + 1.5*100) / 200 = 1.25
        assert abs(m["net_expected_points_per_deal"] - 1.25) < 1e-9

        # bid_rate = 110 / 200 = 0.55
        assert abs(m["bid_rate"] - 0.55) < 1e-9

        # make_count = round(0.8*50) + round(0.6*60) = 40 + 36 = 76
        # make_rate = 76 / 110
        assert abs(m["make_rate"] - 76 / 110) < 1e-9

    def test_missing_team_reports_missing(self):
        """Missing team sub-run reports the bidder as missing."""
        policies = [{"name": "bidder_x"}]
        run_dirs = {
            "bidder_x_team0": "/fake/team0",
            # team1 missing
        }

        fake_evals = {
            "/fake/team0": _make_fake_eval(100, 50, 2.0, 1.0, 0.8),
        }

        metrics, missing = _merge_dual_seat_evaluations(
            run_dirs, policies, load_fn=lambda d: fake_evals.get(d)
        )

        assert "bidder_x" in missing
        assert "bidder_x" not in metrics

    def test_multiple_bidders_merge_independently(self):
        """Each bidder's teams are merged independently."""
        policies = [{"name": "alpha"}, {"name": "beta"}]
        run_dirs = {
            "alpha_team0": "/fake/a0",
            "alpha_team1": "/fake/a1",
            "beta_team0": "/fake/b0",
            "beta_team1": "/fake/b1",
        }

        fake_evals = {
            "/fake/a0": _make_fake_eval(100, 40, 1.0, 0.5, 0.7),
            "/fake/a1": _make_fake_eval(100, 40, 1.0, 0.5, 0.7),
            "/fake/b0": _make_fake_eval(200, 80, 3.0, 2.0, 0.9),
            "/fake/b1": _make_fake_eval(200, 80, 3.0, 2.0, 0.9),
        }

        metrics, missing = _merge_dual_seat_evaluations(
            run_dirs, policies, load_fn=lambda d: fake_evals[d]
        )

        assert len(missing) == 0
        assert len(metrics) == 2

        # Alpha: identical teams → same metrics
        assert abs(metrics["alpha"]["expected_points_per_deal"] - 1.0) < 1e-9
        assert metrics["alpha"]["deals_total"] == 200

        # Beta: identical teams → same metrics
        assert abs(metrics["beta"]["expected_points_per_deal"] - 3.0) < 1e-9
        assert metrics["beta"]["deals_total"] == 400


class TestWriteDualSeatManifest:
    """Test dual-seat batch manifest writing."""

    def test_writes_valid_manifest(self, tmp_path):
        """Manifest is written with correct schema fields."""
        # Create fake run dirs with evaluation.json
        for suffix in ["team0", "team1"]:
            run_dir = tmp_path / f"test_bidder_{suffix}"
            eval_dir = run_dir / "reports" / "bidding_strategy"
            eval_dir.mkdir(parents=True)
            (eval_dir / "evaluation.json").write_text("{}")

        run_dirs = {
            "test_bidder_team0": str(tmp_path / "test_bidder_team0"),
            "test_bidder_team1": str(tmp_path / "test_bidder_team1"),
        }
        policies = [{"name": "test_bidder"}]

        manifest_path, batch_id = _write_dual_seat_manifest(
            str(tmp_path), "test_exp", 42, 1000, policies, run_dirs
        )

        assert manifest_path is not None
        assert batch_id is not None

        manifest = json.loads(Path(manifest_path).read_text())
        assert manifest["schema"] == "batch_manifest_v1"
        assert manifest["mode"] == "dual_seat"
        assert manifest["expected_teams"] == 2
        assert manifest["seed"] == 42
        assert manifest["n_per"] == 1000
        assert "test_bidder_team0" in manifest["members"]
        assert "test_bidder_team1" in manifest["members"]

    def test_incomplete_batch_returns_none(self, tmp_path):
        """Missing team sub-run → no manifest written."""
        # Only team0
        run_dir = tmp_path / "test_bidder_team0"
        eval_dir = run_dir / "reports" / "bidding_strategy"
        eval_dir.mkdir(parents=True)
        (eval_dir / "evaluation.json").write_text("{}")

        run_dirs = {"test_bidder_team0": str(run_dir)}
        policies = [{"name": "test_bidder"}]

        manifest_path, batch_id = _write_dual_seat_manifest(
            str(tmp_path), "test_exp", 42, 1000, policies, run_dirs
        )

        assert manifest_path is None
        assert batch_id is None


class TestFormatJsonDualSeat:
    """Test format_json includes dual_seat mode."""

    def test_dual_seat_mode_in_output(self):
        """format_json with dual_seat=True includes mode field."""
        metrics = {"bidder": {"net_expected_points_per_deal": 1.0, "bid_rate": 0.5}}
        result = format_json(metrics, [], 42, 1000, dual_seat=True)
        assert result["mode"] == "dual_seat"

    def test_single_seat_mode_unchanged(self):
        """format_json with single_seat=True still works."""
        metrics = {"bidder": {"net_expected_points_per_deal": 1.0, "bid_rate": 0.5}}
        result = format_json(metrics, [], 42, 1000, single_seat=True)
        assert result["mode"] == "single_seat"

    def test_no_mode_by_default(self):
        """format_json with neither flag omits mode field."""
        metrics = {"bidder": {"net_expected_points_per_deal": 1.0, "bid_rate": 0.5}}
        result = format_json(metrics, [], 42, 1000)
        assert "mode" not in result

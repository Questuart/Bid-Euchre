"""Unit tests for H2H battery runner matchup generation and config logic.

Tests import the script functions via importlib.util (same pattern as
test_arc_d_gate.py) since scripts/internal/ has no __init__.py.
"""

import importlib.util
import json
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Import script module via importlib.util
# ---------------------------------------------------------------------------

_BATTERY_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "run_arc_d_h2h_battery.py"
)
_spec = importlib.util.spec_from_file_location("run_arc_d_h2h_battery", _BATTERY_SCRIPT)
_battery_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_battery_mod)

generate_matchups = _battery_mod.generate_matchups
generate_h2h_config = _battery_mod.generate_h2h_config
select_full_subset = _battery_mod.select_full_subset
generate_summary = _battery_mod.generate_summary
parse_run_results = _battery_mod.parse_run_results
_compute_team_points = _battery_mod._compute_team_points
_bootstrap_ci = _battery_mod._bootstrap_ci
DEFAULT_ROSTER = _battery_mod.DEFAULT_ROSTER
KEY_BIDDERS = _battery_mod.KEY_BIDDERS
PLAY_STRATEGY_MAP = _battery_mod.PLAY_STRATEGY_MAP


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SMALL_ROSTER = [
    {"name": "alpha", "class_name": "AlphaBot"},
    {"name": "beta", "class_name": "BetaBot"},
    {"name": "gamma", "class_name": "GammaBot"},
]


# ---------------------------------------------------------------------------
# Tests: generate_matchups
# ---------------------------------------------------------------------------


class TestGenerateMatchups:
    def test_generate_matchups_count(self):
        """8 bidders -> 8^2 = 64 matchups."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        assert len(matchups) == 64

    def test_generate_matchups_small_roster(self):
        """3 bidders -> 3^2 = 9 matchups."""
        matchups = generate_matchups(_SMALL_ROSTER)
        assert len(matchups) == 9

    def test_generate_matchups_self_play(self):
        """Each bidder gets exactly one self-play matchup."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        self_plays = [m for m in matchups if m["bidder_a"] == m["bidder_b"]]
        assert len(self_plays) == 8

        # Each bidder name appears exactly once in self-play
        self_play_names = {m["bidder_a"] for m in self_plays}
        roster_names = {r["name"] for r in DEFAULT_ROSTER}
        assert self_play_names == roster_names

    def test_generate_matchups_both_rotations(self):
        """Each non-self pair has both seat rotations."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        cross_matchups = [m for m in matchups if m["bidder_a"] != m["bidder_b"]]

        # Build set of (a, b) pairs from cross matchups
        pairs = {(m["bidder_a"], m["bidder_b"]) for m in cross_matchups}

        # For every (a, b), the reverse (b, a) should also exist
        for a, b in list(pairs):
            assert (b, a) in pairs, f"Missing reverse rotation for ({a}, {b})"

        # 8 bidders: C(8,2) = 28 pairs, 2 rotations each = 56 cross matchups
        assert len(cross_matchups) == 56

    def test_generate_matchups_deterministic(self):
        """Same roster -> same matchups every time."""
        m1 = generate_matchups(DEFAULT_ROSTER)
        m2 = generate_matchups(DEFAULT_ROSTER)

        ids1 = [m["matchup_id"] for m in m1]
        ids2 = [m["matchup_id"] for m in m2]
        assert ids1 == ids2

    def test_matchup_id_uniqueness(self):
        """All 64 matchup_ids are unique."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        ids = [m["matchup_id"] for m in matchups]
        assert len(ids) == len(
            set(ids)
        ), f"Duplicate IDs found: {len(ids)} != {len(set(ids))}"

    def test_seat_bidding_policies_format(self):
        """Each matchup has a 4-element seat_bidding_policies list."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        for m in matchups:
            sbp = m["seat_bidding_policies"]
            assert isinstance(sbp, list), f"Not a list: {sbp}"
            assert len(sbp) == 4, f"Wrong length: {len(sbp)}"

            if m["bidder_a"] == m["bidder_b"]:
                # Self-play: all 4 seats same bidder
                assert len(set(sbp)) == 1
            else:
                # Cross-matchup: alternating a,b,a,b pattern
                assert sbp[0] == sbp[2], f"Seats 0,2 should match: {sbp}"
                assert sbp[1] == sbp[3], f"Seats 1,3 should match: {sbp}"
                assert sbp[0] != sbp[1], f"Opposing seats should differ: {sbp}"

    def test_self_play_matchup_id_format(self):
        """Self-play matchup IDs follow '{name}_self_play' pattern."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        self_plays = [m for m in matchups if m["bidder_a"] == m["bidder_b"]]
        for m in self_plays:
            expected_id = f"{m['bidder_a']}_self_play"
            assert m["matchup_id"] == expected_id

    def test_cross_matchup_id_format(self):
        """Cross-matchup IDs follow '{a}_vs_{b}' where a occupies seats 0,2."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        cross = [m for m in matchups if m["bidder_a"] != m["bidder_b"]]
        for m in cross:
            expected_id = f"{m['bidder_a']}_vs_{m['bidder_b']}"
            assert m["matchup_id"] == expected_id
            # bidder_a should be in seats 0,2
            assert m["seat_bidding_policies"][0] == m["bidder_a"]
            assert m["seat_bidding_policies"][2] == m["bidder_a"]

    def test_single_bidder_roster(self):
        """Single bidder -> 1 self-play matchup."""
        roster = [{"name": "solo", "class_name": "SoloBot"}]
        matchups = generate_matchups(roster)
        assert len(matchups) == 1
        assert matchups[0]["matchup_id"] == "solo_self_play"


# ---------------------------------------------------------------------------
# Tests: generate_h2h_config
# ---------------------------------------------------------------------------


class TestGenerateH2HConfig:
    def test_generate_h2h_config_structure(self):
        """Config has all required top-level keys."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)

        assert config["experiment_name"] == "arc_d_r0_h2h_battery"
        assert config["parameters"]["seed"] == 42
        assert config["parameters"]["n_per"] == 2000
        assert config["parameters"]["log_level"] == "hand"
        assert config["parameters"]["mode"] == "head_to_head_matrix"
        assert config["parameters"]["pair_deals"] is True

        assert len(config["strategies"]) == 1
        assert config["strategies"][0]["class_name"] == "GluttonStrategy"

        assert len(config["bidding_policies"]) == 8
        assert len(config["matchups"]) == 64

        assert config["scenarios"] == [{"contract_type": None}]

    def test_config_yaml_serializable(self):
        """Config can be round-tripped through YAML."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)

        yaml_str = yaml.dump(config, default_flow_style=False)
        reloaded = yaml.safe_load(yaml_str)

        assert reloaded["experiment_name"] == config["experiment_name"]
        assert len(reloaded["matchups"]) == len(config["matchups"])
        assert reloaded["parameters"] == config["parameters"]

    def test_config_matchups_no_internal_keys(self):
        """YAML matchups should not include internal keys like bidder_a/bidder_b."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)

        for m in config["matchups"]:
            assert "bidder_a" not in m
            assert "bidder_b" not in m
            assert "matchup_id" in m
            assert "seat_bidding_policies" in m
            assert "team0" in m
            assert "team1" in m

    def test_config_bidding_policies_preserve_params(self):
        """Bidding policies with params should preserve them."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)

        by_name = {p["name"]: p for p in config["bidding_policies"]}

        # hybrid_olsa has artifact_path param
        assert "params" in by_name["hybrid_olsa"]
        assert "artifact_path" in by_name["hybrid_olsa"]["params"]

        # fiveheadfred has n and contract params
        assert by_name["fiveheadfred"]["params"]["n"] == 5
        assert by_name["fiveheadfred"]["params"]["contract"] == "S"

        # stricthellraiser has no params
        assert "params" not in by_name["stricthellraiser"]


# ---------------------------------------------------------------------------
# Tests: select_full_subset
# ---------------------------------------------------------------------------


class TestFullSubsetSelection:
    def _make_quick_summary(self, cells):
        """Build a minimal QUICK summary with given cells."""
        return {
            "schema": "h2h_battery_v1",
            "mode": "QUICK",
            "cells": cells,
        }

    def test_full_subset_includes_key_bidders(self):
        """Cells involving key bidders are always selected."""
        cells = {
            "hybrid_olsa_vs_rankthetank": {
                "bidder_a": "hybrid_olsa",
                "bidder_b": "rankthetank",
                "ci_low": 0.1,
                "ci_high": 0.5,  # Does not cross zero
            },
            "rankthetank_vs_stricthellraiser": {
                "bidder_a": "rankthetank",
                "bidder_b": "stricthellraiser",
                "ci_low": 0.1,
                "ci_high": 0.5,  # Does not cross zero
            },
        }
        summary = self._make_quick_summary(cells)
        selected = select_full_subset(summary, DEFAULT_ROSTER)

        assert "hybrid_olsa_vs_rankthetank" in selected
        assert "rankthetank_vs_stricthellraiser" not in selected

    def test_full_subset_includes_ci_crosses_zero(self):
        """Non-key cells where CI crosses zero are selected."""
        cells = {
            "rankthetank_vs_stricthellraiser": {
                "bidder_a": "rankthetank",
                "bidder_b": "stricthellraiser",
                "ci_low": -0.1,
                "ci_high": 0.2,  # Crosses zero
            },
            "fiveheadfred_vs_modeloespecifico": {
                "bidder_a": "fiveheadfred",
                "bidder_b": "modeloespecifico",
                "ci_low": 0.05,
                "ci_high": 0.3,  # Does not cross zero
            },
        }
        summary = self._make_quick_summary(cells)
        selected = select_full_subset(summary, DEFAULT_ROSTER)

        assert "rankthetank_vs_stricthellraiser" in selected
        assert "fiveheadfred_vs_modeloespecifico" not in selected

    def test_full_subset_mixed_criteria(self):
        """Mixed selection: key bidders + CI-crosses-zero."""
        cells = {
            "olsa_vs_modeloespecifico": {
                "bidder_a": "olsa",
                "bidder_b": "modeloespecifico",
                "ci_low": 0.2,
                "ci_high": 0.5,
            },
            "rankthetank_vs_fiveheadfred": {
                "bidder_a": "rankthetank",
                "bidder_b": "fiveheadfred",
                "ci_low": -0.05,
                "ci_high": 0.01,  # Crosses zero
            },
            "modeloespecifico_vs_stricthellraiser": {
                "bidder_a": "modeloespecifico",
                "bidder_b": "stricthellraiser",
                "ci_low": 0.1,
                "ci_high": 0.3,  # Clear positive, no key bidder
            },
        }
        summary = self._make_quick_summary(cells)
        selected = select_full_subset(summary, DEFAULT_ROSTER)

        assert "olsa_vs_modeloespecifico" in selected  # Key bidder
        assert "rankthetank_vs_fiveheadfred" in selected  # CI crosses zero
        assert "modeloespecifico_vs_stricthellraiser" not in selected  # Neither

    def test_full_subset_null_ci_excluded(self):
        """Cells with null CI values are not selected by CI criterion."""
        cells = {
            "rankthetank_vs_stricthellraiser": {
                "bidder_a": "rankthetank",
                "bidder_b": "stricthellraiser",
                "ci_low": None,
                "ci_high": None,
            },
        }
        summary = self._make_quick_summary(cells)
        selected = select_full_subset(summary, DEFAULT_ROSTER)
        assert len(selected) == 0


# ---------------------------------------------------------------------------
# Tests: generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_summary_schema(self):
        """Summary has all required top-level fields."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=2000,
            roster=DEFAULT_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        assert summary["schema"] == "h2h_battery_v2"
        assert summary["mode"] == "QUICK"
        assert summary["seed"] == 42
        assert summary["n_per"] == 2000
        assert len(summary["roster"]) == 8
        assert len(summary["cells"]) == 64
        assert summary["quick_source"] is None
        assert "script" in summary["provenance"]
        assert "git_sha" in summary["provenance"]

    def test_summary_json_serializable(self):
        """Summary can be serialized to JSON."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        config = generate_h2h_config(DEFAULT_ROSTER, matchups, seed=42, n_per=2000)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=2000,
            roster=DEFAULT_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        json_str = json.dumps(summary)
        reloaded = json.loads(json_str)
        assert reloaded["schema"] == "h2h_battery_v2"
        assert len(reloaded["cells"]) == 64


# ---------------------------------------------------------------------------
# Tests: _compute_team_points
# ---------------------------------------------------------------------------


class TestComputeTeamPoints:
    def test_team0_declares_and_makes(self):
        """Team 0 declares, makes bid -> gets tricks won."""
        record = {
            "t0": 7,
            "t1": 3,
            "winning_bid": 6,
            "bidder_position": 0,
            "made_bid": True,
        }
        t0_pts, t1_pts = _compute_team_points(record)
        assert t0_pts == 7
        assert t1_pts == 3

    def test_team0_declares_and_set(self):
        """Team 0 declares, set -> gets -bid."""
        record = {
            "t0": 4,
            "t1": 6,
            "winning_bid": 6,
            "bidder_position": 2,
            "made_bid": False,
        }
        t0_pts, t1_pts = _compute_team_points(record)
        assert t0_pts == -6
        assert t1_pts == 6

    def test_team1_declares_and_makes(self):
        """Team 1 declares, makes bid -> gets tricks won."""
        record = {
            "t0": 3,
            "t1": 7,
            "winning_bid": 6,
            "bidder_position": 1,
            "made_bid": True,
        }
        t0_pts, t1_pts = _compute_team_points(record)
        assert t0_pts == 3
        assert t1_pts == 7

    def test_team1_declares_and_set(self):
        """Team 1 declares, set -> gets -bid."""
        record = {
            "t0": 6,
            "t1": 4,
            "winning_bid": 7,
            "bidder_position": 3,
            "made_bid": False,
        }
        t0_pts, t1_pts = _compute_team_points(record)
        assert t0_pts == 6
        assert t1_pts == -7


# ---------------------------------------------------------------------------
# Tests: _bootstrap_ci
# ---------------------------------------------------------------------------


class TestBootstrapCI:
    def test_bootstrap_ci_deterministic(self):
        """Same input + seed -> same CI."""
        deltas = [0.1, 0.2, 0.3, -0.1, 0.05] * 20
        ci1 = _bootstrap_ci(deltas, seed=42)
        ci2 = _bootstrap_ci(deltas, seed=42)
        assert ci1 == ci2

    def test_bootstrap_ci_ordering(self):
        """ci_low <= mean <= ci_high."""
        import numpy as np

        deltas = [0.1, 0.2, 0.3, -0.1, 0.05] * 20
        ci_low, ci_high = _bootstrap_ci(deltas, seed=42)
        mean_val = float(np.mean(deltas))
        assert ci_low <= mean_val <= ci_high

    def test_bootstrap_ci_single_value(self):
        """Single value -> CI collapses to that value."""
        ci_low, ci_high = _bootstrap_ci([0.5], seed=42)
        assert ci_low == 0.5
        assert ci_high == 0.5

    def test_bootstrap_ci_positive_data(self):
        """All positive deltas -> positive CI."""
        deltas = [0.5, 0.6, 0.7, 0.8, 0.9] * 20
        ci_low, ci_high = _bootstrap_ci(deltas, seed=42)
        assert ci_low > 0


# ---------------------------------------------------------------------------
# Tests: parse_run_results
# ---------------------------------------------------------------------------


class TestParseRunResults:
    def _make_hand_end_record(
        self, matchup_id, t0, t1, winning_bid, bidder_position, made_bid
    ):
        """Create a synthetic hand_end JSONL record."""
        return {
            "event": "hand_end",
            "matchup_id": matchup_id,
            "deal_id": f"deal_{matchup_id}_{t0}_{t1}",
            "t0": t0,
            "t1": t1,
            "winning_bid": winning_bid,
            "bidder_position": bidder_position,
            "made_bid": made_bid,
        }

    def _write_jsonl(self, path, records):
        """Write records as JSONL."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")

    def test_parse_populates_cells(self, tmp_path):
        """Parse fills in None-valued cells from JSONL data."""
        # Create a skeleton summary with one matchup
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=10)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=10,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        # Verify cells start with None metrics
        first_cell = next(iter(summary["cells"].values()))
        assert first_cell["net_eppd_delta"] is None

        # Create synthetic JSONL data for one matchup
        mid = "alpha_self_play"
        records = []
        for _ in range(20):
            # Team 0 declares, makes bid of 6, gets 7 tricks (team 1 gets 3)
            records.append(self._make_hand_end_record(mid, 7, 3, 6, 0, True))
            # Team 1 declares, makes bid of 5, gets 6 tricks (team 0 gets 4)
            records.append(self._make_hand_end_record(mid, 4, 6, 5, 1, True))

        run_dir = tmp_path / "test_run"
        self._write_jsonl(run_dir / "game_log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)

        cell = result["cells"][mid]
        assert cell["net_eppd_delta"] is not None
        assert cell["deals_total"] == 40
        assert cell["run_id"] == "test_run"

    def test_parse_no_jsonl_returns_unchanged(self, tmp_path):
        """Empty run dir returns summary unchanged."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=10)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=10,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        run_dir = tmp_path / "empty_run"
        run_dir.mkdir()

        result = parse_run_results(str(run_dir), summary, seed=42)
        first_cell = next(iter(result["cells"].values()))
        assert first_cell["net_eppd_delta"] is None

    def test_parse_self_play_near_zero(self, tmp_path):
        """Self-play with symmetric data -> net_eppd_delta near zero."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=100)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=100,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        mid = "alpha_self_play"
        records = []
        for i in range(100):
            # Alternate who declares, symmetric outcomes
            if i % 2 == 0:
                records.append(self._make_hand_end_record(mid, 6, 4, 5, 0, True))
            else:
                records.append(self._make_hand_end_record(mid, 4, 6, 5, 1, True))

        run_dir = tmp_path / "self_play_run"
        self._write_jsonl(run_dir / "log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)
        cell = result["cells"][mid]
        # Symmetric self-play: net_eppd_delta should be 0
        assert cell["net_eppd_delta"] == 0.0
        assert cell["win_rate_a"] == 0.5

    def test_parse_all_pass_hands_counted_but_unbid(self, tmp_path):
        """All-pass hands count in deals_total but not in bid/make stats."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=10)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=10,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        mid = "alpha_self_play"
        records = []
        # 10 normal hands (team 0 declares)
        for _ in range(10):
            records.append(self._make_hand_end_record(mid, 7, 3, 6, 0, True))
        # 5 all-pass hands (bidder_position=None, equal tricks)
        for _ in range(5):
            records.append(
                {
                    "event": "hand_end",
                    "matchup_id": mid,
                    "deal_id": "deal_allpass",
                    "t0": 5,
                    "t1": 5,
                    "winning_bid": 0,
                    "bidder_position": None,
                    "made_bid": False,
                }
            )
        # 5 all-pass hands (bidder_position missing entirely)
        for _ in range(5):
            records.append(
                {
                    "event": "hand_end",
                    "matchup_id": mid,
                    "deal_id": "deal_allpass_missing",
                    "t0": 5,
                    "t1": 5,
                    "winning_bid": 0,
                    "made_bid": False,
                }
            )

        run_dir = tmp_path / "allpass_run"
        self._write_jsonl(run_dir / "game_log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)
        cell = result["cells"][mid]

        # All 20 hands count in deals_total (per-deal contract)
        assert cell["deals_total"] == 20
        # bid_rate = bids / total_deals; 10 bids out of 20 deals
        assert cell["bid_rate_a"] == 0.5
        assert cell["bid_rate_b"] == 0.0

    def test_parse_populates_cvar_5(self, tmp_path):
        """Parsed cells contain a numeric cvar_5 field."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=10)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=10,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        mid = "alpha_self_play"
        records = []
        for _ in range(20):
            records.append(self._make_hand_end_record(mid, 7, 3, 6, 0, True))
            records.append(self._make_hand_end_record(mid, 4, 6, 5, 1, True))

        run_dir = tmp_path / "cvar_run"
        self._write_jsonl(run_dir / "game_log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)
        cell = result["cells"][mid]

        assert "cvar_5" in cell
        assert isinstance(cell["cvar_5"], float)

    def test_cvar_5_uniform_zeros(self, tmp_path):
        """CVaR-5 of all-zero deltas is 0.0."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=20)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=20,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        mid = "alpha_self_play"
        records = []
        # 20 hands where both teams score equally -> delta = 0
        for _ in range(20):
            records.append(self._make_hand_end_record(mid, 5, 5, 5, 0, True))

        run_dir = tmp_path / "cvar_zeros_run"
        self._write_jsonl(run_dir / "game_log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)
        cell = result["cells"][mid]
        assert cell["cvar_5"] == 0.0

    def test_cvar_5_single_outlier(self, tmp_path):
        """CVaR-5 with one extreme outlier in 20 deals picks up only that value."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=20)
        summary = generate_summary(
            mode="QUICK",
            seed=42,
            n_per=20,
            roster=_SMALL_ROSTER,
            matchups=matchups,
            config_dict=config,
        )

        mid = "alpha_self_play"
        records = []
        # 19 hands where team0 wins 5-5 (delta=0 after scoring: 5-5=0)
        for _ in range(19):
            records.append(self._make_hand_end_record(mid, 5, 5, 5, 0, True))
        # 1 hand where team0 gets set badly: t0=-10, t1=10 -> delta = -10 - 10 = -20
        # Team 0 declares bid 10, gets 0 tricks -> set: t0_pts = -10, t1_pts = 10
        records.append(self._make_hand_end_record(mid, 0, 10, 10, 0, False))

        run_dir = tmp_path / "cvar_outlier_run"
        self._write_jsonl(run_dir / "game_log.jsonl", records)

        result = parse_run_results(str(run_dir), summary, seed=42)
        cell = result["cells"][mid]

        # 5% of 20 = 1 value, ceil(1.0)=1. Bottom 1 delta is -20.
        # delta for the set hand: t0_pts=-10, t1_pts=10, delta=-10-10=-20
        assert cell["cvar_5"] == -20.0


# ---------------------------------------------------------------------------
# Tests: play_strategy parameterization
# ---------------------------------------------------------------------------


class TestPlayStrategyParam:
    """Tests for --play-strategy and --roster-names CLI features."""

    def test_play_strategy_map_contains_defaults(self):
        """PLAY_STRATEGY_MAP has glutton and greedy."""
        assert "glutton" in PLAY_STRATEGY_MAP
        assert "greedy" in PLAY_STRATEGY_MAP
        assert PLAY_STRATEGY_MAP["glutton"] == "GluttonStrategy"
        assert PLAY_STRATEGY_MAP["greedy"] == "GreedyStrategy"

    def test_generate_matchups_default_glutton(self):
        """Default play_strategy_name is glutton (backward compat)."""
        matchups = generate_matchups(_SMALL_ROSTER)
        for m in matchups:
            assert m["team0"] == "glutton"
            assert m["team1"] == "glutton"

    def test_generate_matchups_greedy(self):
        """play_strategy_name='greedy' propagates to team0/team1."""
        matchups = generate_matchups(_SMALL_ROSTER, play_strategy_name="greedy")
        for m in matchups:
            assert m["team0"] == "greedy"
            assert m["team1"] == "greedy"

    def test_generate_matchups_count_unchanged_by_strategy(self):
        """Matchup count is independent of play strategy."""
        m_glutton = generate_matchups(_SMALL_ROSTER, play_strategy_name="glutton")
        m_greedy = generate_matchups(_SMALL_ROSTER, play_strategy_name="greedy")
        assert len(m_glutton) == len(m_greedy) == 9

    def test_generate_h2h_config_greedy_strategy(self):
        """Config strategies section uses greedy when requested."""
        matchups = generate_matchups(_SMALL_ROSTER, play_strategy_name="greedy")
        config = generate_h2h_config(
            _SMALL_ROSTER, matchups, seed=42, n_per=100, play_strategy_name="greedy"
        )
        assert len(config["strategies"]) == 1
        assert config["strategies"][0]["name"] == "greedy"
        assert config["strategies"][0]["class_name"] == "GreedyStrategy"

    def test_generate_h2h_config_default_glutton(self):
        """Config defaults to GluttonStrategy (backward compat)."""
        matchups = generate_matchups(_SMALL_ROSTER)
        config = generate_h2h_config(_SMALL_ROSTER, matchups, seed=42, n_per=100)
        assert config["strategies"][0]["name"] == "glutton"
        assert config["strategies"][0]["class_name"] == "GluttonStrategy"

    def test_config_matchups_use_play_strategy(self):
        """Matchup team0/team1 in config reflect the play strategy."""
        matchups = generate_matchups(_SMALL_ROSTER, play_strategy_name="greedy")
        config = generate_h2h_config(
            _SMALL_ROSTER, matchups, seed=42, n_per=100, play_strategy_name="greedy"
        )
        for m in config["matchups"]:
            assert m["team0"] == "greedy"
            assert m["team1"] == "greedy"

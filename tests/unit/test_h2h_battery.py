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
DEFAULT_ROSTER = _battery_mod.DEFAULT_ROSTER
KEY_BIDDERS = _battery_mod.KEY_BIDDERS


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
        """7 bidders -> 7^2 = 49 matchups."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        assert len(matchups) == 49

    def test_generate_matchups_small_roster(self):
        """3 bidders -> 3^2 = 9 matchups."""
        matchups = generate_matchups(_SMALL_ROSTER)
        assert len(matchups) == 9

    def test_generate_matchups_self_play(self):
        """Each bidder gets exactly one self-play matchup."""
        matchups = generate_matchups(DEFAULT_ROSTER)
        self_plays = [m for m in matchups if m["bidder_a"] == m["bidder_b"]]
        assert len(self_plays) == 7

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

        # 7 bidders: C(7,2) = 21 pairs, 2 rotations each = 42 cross matchups
        assert len(cross_matchups) == 42

    def test_generate_matchups_deterministic(self):
        """Same roster -> same matchups every time."""
        m1 = generate_matchups(DEFAULT_ROSTER)
        m2 = generate_matchups(DEFAULT_ROSTER)

        ids1 = [m["matchup_id"] for m in m1]
        ids2 = [m["matchup_id"] for m in m2]
        assert ids1 == ids2

    def test_matchup_id_uniqueness(self):
        """All 49 matchup_ids are unique."""
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

        assert len(config["bidding_policies"]) == 7
        assert len(config["matchups"]) == 49

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

        assert summary["schema"] == "h2h_battery_v1"
        assert summary["mode"] == "QUICK"
        assert summary["seed"] == 42
        assert summary["n_per"] == 2000
        assert len(summary["roster"]) == 7
        assert len(summary["cells"]) == 49
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
        assert reloaded["schema"] == "h2h_battery_v1"
        assert len(reloaded["cells"]) == 49

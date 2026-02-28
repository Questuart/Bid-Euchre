"""Tests for H2H battery absolute metric extraction (PR C4).

Validates:
- Absolute per-team metrics (abs_net_eppd_team0, abs_net_eppd_team1)
- Self-play full-game metrics (fullgame_eppd, fullgame_cvar_5)
- Cross-matchup per-team CVaR (cvar_5_team0, cvar_5_team1)
- Bootstrap CIs for fullgame_eppd (deal-level resampling)
- Schema version bump to h2h_battery_v2
"""

import importlib.util
import json
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Import script module via importlib.util (same pattern as test_h2h_battery.py)
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
generate_summary = _battery_mod.generate_summary
parse_run_results = _battery_mod.parse_run_results
_compute_team_points = _battery_mod._compute_team_points
_bootstrap_ci_fullgame = _battery_mod._bootstrap_ci_fullgame

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SMALL_ROSTER = [
    {"name": "alpha", "class_name": "AlphaBot"},
    {"name": "beta", "class_name": "BetaBot"},
]


def _make_hand_end_record(matchup_id, t0, t1, winning_bid, bidder_position, made_bid):
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


def _write_jsonl(path, records):
    """Write records as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _make_skeleton_and_parse(roster, matchup_records_map, tmp_path, n_per=100):
    """Build skeleton summary, write JSONL, parse, and return result.

    Parameters
    ----------
    roster : list[dict]
        Bidder roster.
    matchup_records_map : dict[str, list[dict]]
        Maps matchup_id -> list of hand_end records.
    tmp_path : Path
        Temp directory for JSONL files.
    n_per : int
        Deals per matchup for skeleton.

    Returns
    -------
    dict
        Parsed summary with populated cells.
    """
    matchups = generate_matchups(roster)
    config = generate_h2h_config(roster, matchups, seed=42, n_per=n_per)
    summary = generate_summary(
        mode="QUICK",
        seed=42,
        n_per=n_per,
        roster=roster,
        matchups=matchups,
        config_dict=config,
    )

    # Flatten all records into one JSONL file
    all_records = []
    for records in matchup_records_map.values():
        all_records.extend(records)

    run_dir = tmp_path / "test_run"
    _write_jsonl(run_dir / "game_log.jsonl", all_records)

    return parse_run_results(str(run_dir), summary, seed=42)


# ---------------------------------------------------------------------------
# Tests: Schema version
# ---------------------------------------------------------------------------


class TestSchemaVersion:
    def test_schema_version_v2(self):
        """Schema should be h2h_battery_v2."""
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
        assert summary["schema"] == "h2h_battery_v2"

    def test_skeleton_has_v2_fields(self):
        """Skeleton cells contain all new v2 fields with None defaults."""
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

        for cell in summary["cells"].values():
            assert "abs_net_eppd_team0" in cell
            assert "abs_net_eppd_team1" in cell
            assert "fullgame_eppd" in cell
            assert "fullgame_cvar_5" in cell
            assert "fullgame_ci_low" in cell
            assert "fullgame_ci_high" in cell
            assert "cvar_5_team0" in cell
            assert "cvar_5_team1" in cell
            # All default to None
            assert cell["abs_net_eppd_team0"] is None
            assert cell["fullgame_eppd"] is None
            assert cell["cvar_5_team0"] is None


# ---------------------------------------------------------------------------
# Tests: Absolute delta consistency
# ---------------------------------------------------------------------------


class TestAbsoluteDeltaConsistency:
    def test_absolute_delta_consistency(self, tmp_path):
        """abs_net_eppd_team0 - abs_net_eppd_team1 == net_eppd_delta."""
        mid = "alpha_self_play"
        records = []
        for _ in range(50):
            # Team 0 declares, makes bid of 6, gets 7 tricks
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))
            # Team 1 declares, makes bid of 5, gets 6 tricks
            records.append(_make_hand_end_record(mid, 4, 6, 5, 1, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=100
        )
        cell = result["cells"][mid]

        delta_from_abs = cell["abs_net_eppd_team0"] - cell["abs_net_eppd_team1"]
        assert abs(delta_from_abs - cell["net_eppd_delta"]) < 1e-6

    def test_absolute_delta_consistency_with_misdeals(self, tmp_path):
        """Consistency holds even with all-pass hands mixed in."""
        mid = "alpha_self_play"
        records = []
        # Normal hands
        for _ in range(30):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))
        # All-pass hands
        for _ in range(20):
            records.append(
                {
                    "event": "hand_end",
                    "matchup_id": mid,
                    "deal_id": "allpass",
                    "t0": 5,
                    "t1": 5,
                    "winning_bid": 0,
                    "bidder_position": None,
                    "made_bid": False,
                }
            )

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=50
        )
        cell = result["cells"][mid]

        delta_from_abs = cell["abs_net_eppd_team0"] - cell["abs_net_eppd_team1"]
        assert abs(delta_from_abs - cell["net_eppd_delta"]) < 1e-6


# ---------------------------------------------------------------------------
# Tests: Self-play symmetry
# ---------------------------------------------------------------------------


class TestSelfPlaySymmetry:
    def test_self_play_symmetry(self, tmp_path):
        """In self-play with symmetric data, abs metrics should be approx equal."""
        mid = "alpha_self_play"
        records = []
        for i in range(100):
            if i % 2 == 0:
                # Team 0 declares, makes, gets 6 tricks
                records.append(_make_hand_end_record(mid, 6, 4, 5, 0, True))
            else:
                # Team 1 declares, makes, gets 6 tricks
                records.append(_make_hand_end_record(mid, 4, 6, 5, 1, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=100
        )
        cell = result["cells"][mid]

        # Both teams should have same absolute average
        assert cell["abs_net_eppd_team0"] == cell["abs_net_eppd_team1"]

    def test_self_play_fullgame_eppd_equals_team_avg(self, tmp_path):
        """fullgame_eppd should equal (abs_team0 + abs_team1) / 2."""
        mid = "alpha_self_play"
        records = []
        for _ in range(50):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))
            records.append(_make_hand_end_record(mid, 4, 6, 5, 1, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=100
        )
        cell = result["cells"][mid]

        expected = (cell["abs_net_eppd_team0"] + cell["abs_net_eppd_team1"]) / 2
        assert abs(cell["fullgame_eppd"] - expected) < 1e-6


# ---------------------------------------------------------------------------
# Tests: fullgame_eppd self-play only
# ---------------------------------------------------------------------------


class TestFullgameEppdSelfPlayOnly:
    def test_fullgame_eppd_set_for_self_play(self, tmp_path):
        """fullgame_eppd should be set for self-play cells."""
        mid = "alpha_self_play"
        records = []
        for _ in range(20):
            records.append(_make_hand_end_record(mid, 6, 4, 5, 0, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=20
        )
        cell = result["cells"][mid]

        assert cell["fullgame_eppd"] is not None
        assert cell["fullgame_cvar_5"] is not None
        assert cell["fullgame_ci_low"] is not None
        assert cell["fullgame_ci_high"] is not None

    def test_fullgame_eppd_none_for_cross(self, tmp_path):
        """fullgame_eppd should remain None for cross-matchup cells."""
        mid = "alpha_vs_beta"
        records = []
        for _ in range(20):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=20
        )
        cell = result["cells"][mid]

        assert cell["fullgame_eppd"] is None
        assert cell["fullgame_cvar_5"] is None
        assert cell["fullgame_ci_low"] is None
        assert cell["fullgame_ci_high"] is None

    def test_cross_matchup_has_per_team_cvar(self, tmp_path):
        """Cross-matchup cells should have cvar_5_team0 and cvar_5_team1."""
        mid = "alpha_vs_beta"
        records = []
        for _ in range(20):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=20
        )
        cell = result["cells"][mid]

        assert cell["cvar_5_team0"] is not None
        assert cell["cvar_5_team1"] is not None
        assert isinstance(cell["cvar_5_team0"], float)
        assert isinstance(cell["cvar_5_team1"], float)

    def test_self_play_no_per_team_cvar(self, tmp_path):
        """Self-play cells should have cvar_5_team0/team1 remain None."""
        mid = "alpha_self_play"
        records = []
        for _ in range(20):
            records.append(_make_hand_end_record(mid, 6, 4, 5, 0, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=20
        )
        cell = result["cells"][mid]

        assert cell["cvar_5_team0"] is None
        assert cell["cvar_5_team1"] is None


# ---------------------------------------------------------------------------
# Tests: fullgame_cvar_5 pooling
# ---------------------------------------------------------------------------


class TestFullgameCvarPooled:
    def test_fullgame_cvar_pools_both_teams(self, tmp_path):
        """fullgame_cvar_5 should pool both teams' absolute values."""
        mid = "alpha_self_play"
        records = []
        # 100 hands: team 0 always gets 6 pts, team 1 always gets 4 pts
        for _ in range(100):
            records.append(_make_hand_end_record(mid, 6, 4, 5, 0, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=100
        )
        cell = result["cells"][mid]

        # Pooled: 100 values of 6 + 100 values of 4 = 200 values
        # Bottom 5% = bottom 10 values, all = 4
        # So fullgame_cvar_5 should be 4.0
        assert cell["fullgame_cvar_5"] == 4.0

    def test_fullgame_cvar_with_outlier(self, tmp_path):
        """fullgame_cvar_5 picks up extreme values from pooled distribution."""
        mid = "alpha_self_play"
        records = []

        # 19 hands where team0 gets 5, team1 gets 5 (all make, bid 5)
        for _ in range(19):
            records.append(_make_hand_end_record(mid, 5, 5, 5, 0, True))

        # 1 hand where team0 gets set: -10 pts, team1 gets 10 tricks
        records.append(_make_hand_end_record(mid, 0, 10, 10, 0, False))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=20
        )
        cell = result["cells"][mid]

        # Pooled: 19*5 + 1*(-10) from team0 + 19*5 + 1*10 from team1
        # = 40 values. Bottom 5% = ceil(0.05*40) = 2 values
        # Sorted: [-10, 5, 5, 5, ..., 10]. Bottom 2 = [-10, 5]
        # Mean = (-10 + 5) / 2 = -2.5
        assert cell["fullgame_cvar_5"] == -2.5


# ---------------------------------------------------------------------------
# Tests: Bootstrap CI for fullgame_eppd
# ---------------------------------------------------------------------------


class TestBootstrapCIFullgame:
    def test_bootstrap_deterministic(self):
        """Same input + seed -> same CI."""
        t0 = [5.0, 6.0, 4.0, 7.0, 3.0] * 20
        t1 = [5.0, 4.0, 6.0, 3.0, 7.0] * 20

        ci1 = _bootstrap_ci_fullgame(t0, t1, seed=42)
        ci2 = _bootstrap_ci_fullgame(t0, t1, seed=42)
        assert ci1 == ci2

    def test_bootstrap_ci_ordering(self):
        """ci_low <= fullgame_eppd <= ci_high."""
        t0 = [5.0, 6.0, 4.0, 7.0, 3.0] * 20
        t1 = [5.0, 4.0, 6.0, 3.0, 7.0] * 20

        ci_low, ci_high = _bootstrap_ci_fullgame(t0, t1, seed=42)
        fullgame_eppd = float((np.mean(t0) + np.mean(t1)) / 2)
        assert ci_low <= fullgame_eppd <= ci_high

    def test_bootstrap_single_deal(self):
        """Single deal -> CI collapses to that value."""
        ci_low, ci_high = _bootstrap_ci_fullgame([6.0], [4.0], seed=42)
        expected = (6.0 + 4.0) / 2  # = 5.0
        assert ci_low == expected
        assert ci_high == expected

    def test_bootstrap_resamples_deals_not_values(self):
        """Bootstrap should resample deals (preserving t0/t1 pairing).

        If bootstrap resampled individual team values independently,
        the CI width would differ from deal-level resampling. We verify
        that the CI is consistent with deal-level resampling by checking
        that perfectly correlated data (t0 + t1 = constant) yields a
        zero-width CI.
        """
        # Per-deal average is always 5 regardless of deal composition
        t0 = [3.0, 4.0, 5.0, 6.0, 7.0] * 20
        t1 = [7.0, 6.0, 5.0, 4.0, 3.0] * 20

        ci_low, ci_high = _bootstrap_ci_fullgame(t0, t1, seed=42)
        # Per-deal avg = 5.0 for every deal, so CI should collapse
        assert abs(ci_low - 5.0) < 1e-10
        assert abs(ci_high - 5.0) < 1e-10

    def test_bootstrap_ci_in_parsed_output(self, tmp_path):
        """Parsed self-play cells should contain fullgame CI bounds."""
        mid = "alpha_self_play"
        records = []
        for _ in range(50):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))
            records.append(_make_hand_end_record(mid, 4, 6, 5, 1, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=100
        )
        cell = result["cells"][mid]

        assert cell["fullgame_ci_low"] is not None
        assert cell["fullgame_ci_high"] is not None
        assert cell["fullgame_ci_low"] <= cell["fullgame_eppd"]
        assert cell["fullgame_eppd"] <= cell["fullgame_ci_high"]


# ---------------------------------------------------------------------------
# Tests: JSON serializability
# ---------------------------------------------------------------------------


class TestJsonSerializability:
    def test_v2_summary_json_serializable(self, tmp_path):
        """V2 summary with populated cells can round-trip through JSON."""
        mid = "alpha_self_play"
        records = []
        for _ in range(20):
            records.append(_make_hand_end_record(mid, 7, 3, 6, 0, True))
            records.append(_make_hand_end_record(mid, 4, 6, 5, 1, True))

        result = _make_skeleton_and_parse(
            _SMALL_ROSTER, {mid: records}, tmp_path, n_per=40
        )

        json_str = json.dumps(result)
        reloaded = json.loads(json_str)

        assert reloaded["schema"] == "h2h_battery_v2"
        cell = reloaded["cells"][mid]
        assert cell["abs_net_eppd_team0"] is not None
        assert cell["fullgame_eppd"] is not None

"""Tests for Arc D dashboard ME delta column.

Tests that the dashboard correctly resolves ME delta from comparator
JSON files referenced in rung bundles. Covers:
- ME delta from comparator_eval (R1+ convention)
- Battery-only bundles show em-dash (R0 convention)
- Missing comparator keys show em-dash (backward compat)
"""

import importlib.util
import json
from pathlib import Path

# Import the dashboard generator script via importlib.
_DASHBOARD_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "generate_arc_dashboard.py"
)
_spec = importlib.util.spec_from_file_location("gen_dashboard", _DASHBOARD_SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
generate_dashboard = _mod.generate_dashboard
_resolve_me_delta = _mod._resolve_me_delta


def _write_json(path, data):
    """Write JSON to file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def test_dashboard_me_delta_from_comparator_eval(tmp_path):
    """Bundle with comparator_eval path -> dashboard extracts ME delta."""
    rung_dir = tmp_path / "r1"
    rung_dir.mkdir()

    # Create comparator eval JSON with hybrid_olsa and modeloespecifico
    comp_data = {
        "schema": "arc_d_comparator_v1",
        "seed": 42,
        "n_per": 10000,
        "gate_status": "PASS",
        "bidders": {
            "hybrid_olsa": {
                "net_eppd": 1.50,
                "eppd": 2.0,
                "bid_rate": 0.3,
                "make_rate": 0.6,
                "cvar_5": -1.0,
                "net_cvar_5": -0.5,
            },
            "modeloespecifico": {
                "net_eppd": 0.80,
                "eppd": 1.2,
                "bid_rate": 0.2,
                "make_rate": 0.5,
                "cvar_5": -2.0,
                "net_cvar_5": -1.5,
            },
        },
    }
    comp_path = rung_dir / "comparator_eval_r1.json"
    _write_json(comp_path, comp_data)

    # Bundle referencing the comparator_eval (path relative to tmp_path)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r1",
        "olsa": {"selected_features": {"suit": ["a"]}},
        "olsa_full": {"selected_features": {"suit": ["a", "b"]}},
        "comparator_eval": "r1/comparator_eval_r1.json",
        "comparator_battery": None,
    }
    _write_json(rung_dir / "rung_bundle_r1.json", bundle)

    output = tmp_path / "dashboard.md"
    result = generate_dashboard(str(tmp_path), str(output))

    # ME delta = hybrid_olsa(1.50) - modeloespecifico(0.80) = +0.7000
    assert "+0.7000" in result
    assert "ME delta" in result


def test_dashboard_me_delta_battery_only_shows_dash(tmp_path):
    """Bundle with comparator_battery but no comparator_eval -> em-dash."""
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()

    # Create battery JSON (R0 convention -- one-time heuristic battery)
    battery_data = {
        "schema": "arc_d_comparator_v1",
        "seed": 42,
        "n_per": 10000,
        "gate_status": "PASS",
        "bidders": {
            "hybrid_olsa": {"net_eppd": 1.50},
            "modeloespecifico": {"net_eppd": 0.80},
        },
    }
    _write_json(rung_dir / "comparator_battery_r0.json", battery_data)

    # Bundle with battery only, no eval (R0 pattern)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {"selected_features": {"suit": ["a"]}, "net_eppd": 1.60},
        "olsa_full": {"selected_features": {"suit": ["a", "b"]}, "net_eppd": 1.48},
        "comparator_battery": "r0/comparator_battery_r0.json",
        "comparator_eval": None,
    }
    _write_json(rung_dir / "rung_bundle_r0.json", bundle)

    output = tmp_path / "dashboard.md"
    result = generate_dashboard(str(tmp_path), str(output))

    # R0 should show em-dash for ME delta (battery is NOT used for ME delta)
    assert "ME delta" in result
    # The ME delta column for r0 should be em-dash
    for line in result.split("\n"):
        if "| r0 |" in line:
            # Split row by | and check ME delta column (5th data column, index 5)
            cols = [c.strip() for c in line.split("|")]
            # cols: ['', 'r0', 'OLSa', 'Full', 'Gap', 'ME_delta', 'OLSa_feats', ...]
            me_delta_col = cols[5]
            assert (
                me_delta_col == "\u2014"
            ), f"Expected em-dash for R0, got '{me_delta_col}'"
            break


def test_dashboard_me_delta_absent(tmp_path):
    """Dashboard shows em-dash when no comparator keys exist (backward compat)."""
    rung_dir = tmp_path / "r0"
    rung_dir.mkdir()

    # Bundle without any comparator keys (pre-comparator schema)
    bundle = {
        "bundle_schema": "arc_d_rung_bundle_v1",
        "rung_id": "r0",
        "olsa": {"selected_features": {"suit": ["a"]}, "net_eppd": 0.15},
        "olsa_full": {"selected_features": {"suit": ["a", "b"]}, "net_eppd": 0.22},
    }
    _write_json(rung_dir / "rung_bundle_r0.json", bundle)

    output = tmp_path / "dashboard.md"
    result = generate_dashboard(str(tmp_path), str(output))

    # Should still have ME delta header
    assert "ME delta" in result
    # And R0 row should have em-dash for ME delta
    for line in result.split("\n"):
        if "| r0 |" in line:
            cols = [c.strip() for c in line.split("|")]
            me_delta_col = cols[5]
            assert me_delta_col == "\u2014", f"Expected em-dash, got '{me_delta_col}'"
            break

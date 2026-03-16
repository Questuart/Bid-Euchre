"""Unit tests for Arc D gate runner, bundle validator, and registry updater.

All tests are fixture-based -- no real experiment runs or files required.
Tests use tmp_path and mock file I/O where needed.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

from bid_euchre.validation.arc_d_bundle import (
    BUNDLE_SCHEMA,
    REQUIRED_H2H_INLINE_KEYS,
    REQUIRED_R1_PLUS_KEYS,
    load_and_validate_bundle,
    validate_bundle,
    validate_bundle_files_exist,
)
from bid_euchre.validation.arc_d_gate import (
    _DEFAULT_THRESHOLDS,
    _all_metrics_finite,
    _check_guardrails,
    _check_h2h_primary,
    _get_metric,
    _load_thresholds,
    normalize_eval_metrics,
    promotion_gate,
)

# Import registry updater via importlib.util to avoid sys.path manipulation.
# scripts/internal/ has no __init__.py so we load from file location directly.
_REGISTRY_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "update_arc_registry.py"
)
_spec = importlib.util.spec_from_file_location("update_arc_registry", _REGISTRY_SCRIPT)
_registry_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_registry_mod)
upsert_registry = _registry_mod.upsert_registry

# =============================================================================
# Fixtures
# =============================================================================


def _make_h2h_inline(**overrides) -> dict:
    """Create a minimal h2h_challenger_vs_incumbent inline fixture."""
    base = {
        "challenger": "olsa_full_r1",
        "incumbent": "olsa_full_r0",
        "net_eppd_delta": 0.032,
        "ci_low": 0.008,
        "ci_high": 0.056,
        "n_deals": 10000,
        "ci_method": "paired_bootstrap",
        "seat_directions": ["challenger_01", "challenger_23"],
    }
    base.update(overrides)
    return base


def _make_bundle(**overrides) -> dict:
    """Create a minimal valid arc_d_rung_bundle_v1 fixture.

    Includes R1+ keys (h2h_summary, h2h_challenger_vs_incumbent,
    gate_thresholds, progression_report) by default since the default rung_id is "r1".
    """
    base = {
        "bundle_schema": BUNDLE_SCHEMA,
        "rung_id": "r1",
        "arc": "arc_d",
        "timestamp": "2026-02-20T12:00:00Z",
        "olsa": {
            "artifact_path": "data/artifacts/arc_d/r1/hybrid_r1.json",
            "artifact_sha256": "a" * 64,
            "eval_seed42": "data/artifacts/arc_d/r1/eval_r1.json",
            "eval_seed43": "data/artifacts/arc_d/r1/eval_r1_s43.json",
            "eval_seed44": "data/artifacts/arc_d/r1/eval_r1_s44.json",
        },
        "olsa_full": {
            "artifact_path": "data/artifacts/arc_d/r1/hybrid_r1_full.json",
            "artifact_sha256": "b" * 64,
            "eval_seed42": "data/artifacts/arc_d/r1/eval_r1_full.json",
            "eval_seed43": "data/artifacts/arc_d/r1/eval_r1_full_s43.json",
            "eval_seed44": "data/artifacts/arc_d/r1/eval_r1_full_s44.json",
        },
        "incumbent": {
            "artifact_path": "data/artifacts/arc_d/r0/hybrid_r0_full.json",
            "rung_id": "r0",
            "eval_seed42": "data/artifacts/arc_d/r0/eval_r0_full.json",
            "eval_seed43": "data/artifacts/arc_d/r0/eval_r0_full_s43.json",
            "eval_seed44": "data/artifacts/arc_d/r0/eval_r0_full_s44.json",
        },
        "split_manifest": "data/artifacts/arc_d/r1/split_manifest_r1.json",
        # R1+ keys
        "h2h_summary": "data/artifacts/arc_d/r0/h2h_battery_full.json",
        "h2h_challenger_vs_incumbent": _make_h2h_inline(),
        "gate_thresholds": "data/artifacts/arc_d/r0/gate_thresholds_r1.json",
        "progression_report": "docs/04_reports/arc_d_v1/r1/r0_to_r1_progression.md",
    }
    base.update(overrides)
    # R0 bundles don't have R1+ keys
    if base.get("rung_id") == "r0":
        for key in (
            "h2h_summary",
            "h2h_challenger_vs_incumbent",
            "gate_thresholds",
            "progression_report",
        ):
            base.pop(key, None)
    return base


def _make_eval_metrics(**overrides) -> dict:
    """Create eval metrics fixture with reasonable defaults.

    Uses canonical evaluator field names (net_expected_points_per_deal, etc.)
    plus short aliases (net_eppd, etc.) for backward compat with gate logic.
    Also includes std_points and n_deals needed for SE calculation.
    """
    base = {
        "net_expected_points_per_deal": 0.50,
        "expected_points_per_deal": 0.60,
        "net_eppd": 0.50,
        "eppd": 0.60,
        "bid_rate": 0.30,
        "make_rate": 0.65,
        "cvar_5": -0.50,
        "downside_variance": 1.0,
        "std_points": 2.0,
        "n_deals": 50000,
    }
    base.update(overrides)
    # Keep net_eppd and net_expected_points_per_deal in sync when only one is overridden
    if "net_eppd" in overrides and "net_expected_points_per_deal" not in overrides:
        base["net_expected_points_per_deal"] = overrides["net_eppd"]
    if "net_expected_points_per_deal" in overrides and "net_eppd" not in overrides:
        base["net_eppd"] = overrides["net_expected_points_per_deal"]
    if "eppd" in overrides and "expected_points_per_deal" not in overrides:
        base["expected_points_per_deal"] = overrides["eppd"]
    if "expected_points_per_deal" in overrides and "eppd" not in overrides:
        base["eppd"] = overrides["expected_points_per_deal"]
    return base


def _make_artifact(artifact_type: str = "hybrid_olsa_v1", **overrides) -> dict:
    """Create a frozen artifact fixture."""
    base = {
        "type": artifact_type,
        "frozen_at": "2026-02-20T12:00:00Z",
        "artifact_sha256": "placeholder",
    }
    base.update(overrides)
    return base


def _write_json(path: Path, data: dict):
    """Write JSON dict to a file, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _content_hash_inline(metadata: dict) -> str:
    """Compute content hash matching freeze.py logic (no private import)."""
    content = {
        k: v for k, v in metadata.items() if k not in ("frozen_at", "artifact_sha256")
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _make_gate_thresholds(**overrides) -> dict:
    """Create a gate_thresholds_v1 fixture."""
    base = {
        "schema": "gate_thresholds_v1",
        "generated_at": "2026-02-25T12:00:00Z",
        "calibration_source": "h2h_battery_quick.json",
        "calibration_method": "null_distribution_quantiles",
        "seed": 42,
        "thresholds": dict(_DEFAULT_THRESHOLDS),
        "calibration_details": {
            "null_abs_values": [0.001, 0.002, 0.003],
            "q95_null_abs": 0.003,
            "q99_null_abs": 0.003,
            "self_play_net_eppd_std": 0.002,
            "seat_swap_residual_std": 0.003,
            "null_distribution_n": 3,
            "self_play_cvar5_residuals": [0.01, 0.02],
            "cvar5_residual_std": 0.007,
            "drift_check": None,
        },
    }
    base.update(overrides)
    return base


def _setup_gate_files(
    tmp_path: Path,
    bundle: dict,
    challenger_metrics: dict | None = None,
    incumbent_metrics: dict | None = None,
    olsa_metrics: dict | None = None,
    challenger_s43: dict | None = None,
    challenger_s44: dict | None = None,
    incumbent_s43: dict | None = None,
    incumbent_s44: dict | None = None,
    artifact_type: str = "hybrid_olsa_v1",
    gate_thresholds: dict | None = None,
) -> str:
    """Write bundle and referenced files to tmp_path. Returns bundle_path."""
    if challenger_metrics is None:
        challenger_metrics = _make_eval_metrics()
    if incumbent_metrics is None:
        incumbent_metrics = _make_eval_metrics(net_eppd=0.40)
    if olsa_metrics is None:
        olsa_metrics = _make_eval_metrics(net_eppd=0.45)
    if challenger_s43 is None:
        challenger_s43 = _make_eval_metrics(net_eppd=0.48)
    if challenger_s44 is None:
        challenger_s44 = _make_eval_metrics(net_eppd=0.49)
    if incumbent_s43 is None:
        incumbent_s43 = _make_eval_metrics(net_eppd=0.38)
    if incumbent_s44 is None:
        incumbent_s44 = _make_eval_metrics(net_eppd=0.39)

    # Write bundle
    bundle_path = tmp_path / "rung_bundle.json"
    _write_json(bundle_path, bundle)

    # Write OLSa_Full eval files
    olsa_full = bundle.get("olsa_full", {})
    for key, metrics in [
        ("eval_seed42", challenger_metrics),
        ("eval_seed43", challenger_s43),
        ("eval_seed44", challenger_s44),
    ]:
        path = olsa_full.get(key)
        if path:
            _write_json(tmp_path / path, metrics)

    # Write OLSa eval files (all seeds for file existence checks)
    olsa = bundle.get("olsa", {})
    olsa_eval = olsa.get("eval_seed42")
    if olsa_eval:
        _write_json(tmp_path / olsa_eval, olsa_metrics)
    for seed_key in ("eval_seed43", "eval_seed44"):
        olsa_seed_path = olsa.get(seed_key)
        if olsa_seed_path:
            _write_json(tmp_path / olsa_seed_path, olsa_metrics)

    # Write incumbent eval files
    incumbent = bundle.get("incumbent", {})
    for key, metrics in [
        ("eval_seed42", incumbent_metrics),
        ("eval_seed43", incumbent_s43),
        ("eval_seed44", incumbent_s44),
    ]:
        path = incumbent.get(key)
        if path:
            _write_json(tmp_path / path, metrics)

    # Write artifact file (frozen)
    artifact_path = olsa_full.get("artifact_path")
    if artifact_path:
        artifact = _make_artifact(artifact_type)
        content = {
            k: v
            for k, v in artifact.items()
            if k not in ("frozen_at", "artifact_sha256")
        }
        artifact["artifact_sha256"] = _content_hash_inline(content)
        _write_json(tmp_path / artifact_path, artifact)

    # Write OLSa artifact file (for file existence checks)
    olsa_artifact_path = olsa.get("artifact_path")
    if olsa_artifact_path:
        olsa_artifact = _make_artifact(artifact_type)
        olsa_content = {
            k: v
            for k, v in olsa_artifact.items()
            if k not in ("frozen_at", "artifact_sha256")
        }
        olsa_artifact["artifact_sha256"] = _content_hash_inline(olsa_content)
        _write_json(tmp_path / olsa_artifact_path, olsa_artifact)

    # Write incumbent artifact file (for file existence checks)
    inc_artifact_path = incumbent.get("artifact_path")
    if inc_artifact_path:
        _write_json(tmp_path / inc_artifact_path, _make_artifact(artifact_type))

    # Write gate thresholds file (R1+ bundles)
    gate_thresholds_path = bundle.get("gate_thresholds")
    if gate_thresholds_path:
        if gate_thresholds is None:
            gate_thresholds = _make_gate_thresholds()
        _write_json(tmp_path / gate_thresholds_path, gate_thresholds)

    # Write H2H summary file (R1+ bundles) -- minimal placeholder
    h2h_summary_path = bundle.get("h2h_summary")
    if h2h_summary_path:
        _write_json(tmp_path / h2h_summary_path, {"cells": {}})

    # Write progression report file (R1+ bundles) -- plain text, not JSON
    progression_report_path = bundle.get("progression_report")
    if progression_report_path:
        fp = tmp_path / progression_report_path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("# Placeholder progression report\ngate_status: N/A\n")

    # Write split manifest file
    split_manifest = bundle.get("split_manifest")
    if split_manifest:
        _write_json(tmp_path / split_manifest, {"split_type": "three_way"})

    return str(bundle_path)


# =============================================================================
# TestNormalizeEvalMetrics
# =============================================================================


class TestNormalizeEvalMetrics:
    """Tests for normalize_eval_metrics()."""

    def test_adds_short_aliases(self):
        """Adds net_eppd alias from net_expected_points_per_deal."""
        raw = {"net_expected_points_per_deal": 0.5, "expected_points_per_deal": 0.6}
        out = normalize_eval_metrics(raw)
        assert out["net_eppd"] == 0.5
        assert out["eppd"] == 0.6

    def test_adds_canonical_from_aliases(self):
        """Adds canonical names from short aliases."""
        raw = {"net_eppd": 0.5, "eppd": 0.6}
        out = normalize_eval_metrics(raw)
        assert out["net_expected_points_per_deal"] == 0.5
        assert out["expected_points_per_deal"] == 0.6

    def test_derives_std_from_list(self):
        """Derives std_points from net_bidder_team_points list."""
        raw = {"net_bidder_team_points": [1.0, 2.0, 3.0, 4.0, 5.0]}
        out = normalize_eval_metrics(raw)
        assert "std_points" in out
        assert abs(out["std_points"] - 1.5811) < 0.01

    def test_derives_std_from_scalar(self):
        """Falls back to std_bidder_team_points scalar."""
        raw = {"std_bidder_team_points": 2.5}
        out = normalize_eval_metrics(raw)
        assert out["std_points"] == 2.5

    def test_std_not_derived_when_present(self):
        """Does not override existing std_points."""
        raw = {"std_points": 3.0, "net_bidder_team_points": [1.0, 2.0]}
        out = normalize_eval_metrics(raw)
        assert out["std_points"] == 3.0

    def test_derives_n_deals_from_deals_total(self):
        """Derives n_deals from deals_total."""
        raw = {"deals_total": 50000}
        out = normalize_eval_metrics(raw)
        assert out["n_deals"] == 50000

    def test_passthrough_unknown_keys(self):
        """Unknown keys pass through unchanged."""
        raw = {"custom_metric": 42}
        out = normalize_eval_metrics(raw)
        assert out["custom_metric"] == 42


# =============================================================================
# TestBundleValidation
# =============================================================================


class TestBundleValidation:
    """Tests for validate_bundle() schema validation."""

    def test_valid_bundle_passes(self):
        """Minimal valid bundle passes validation."""
        bundle = _make_bundle()
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_missing_schema_fails(self):
        """Missing bundle_schema key fails."""
        bundle = _make_bundle()
        del bundle["bundle_schema"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("bundle_schema" in e for e in errors)

    def test_wrong_schema_version_fails(self):
        """Wrong bundle_schema value fails."""
        bundle = _make_bundle(bundle_schema="wrong_schema_v99")
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("bundle_schema" in e and "wrong_schema_v99" in e for e in errors)

    def test_missing_olsa_arm_fails(self):
        """Missing olsa section fails."""
        bundle = _make_bundle()
        del bundle["olsa"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("olsa" in e for e in errors)

    def test_missing_olsa_full_arm_fails(self):
        """Missing olsa_full section fails."""
        bundle = _make_bundle()
        del bundle["olsa_full"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("olsa_full" in e for e in errors)

    def test_missing_eval_seed42_fails(self):
        """Arm missing eval_seed42 key fails."""
        bundle = _make_bundle()
        del bundle["olsa_full"]["eval_seed42"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("eval_seed42" in e for e in errors)

    def test_invalid_rung_id_fails(self):
        """rung_id not in r0-r5 fails."""
        bundle = _make_bundle(rung_id="r9")
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("rung_id" in e for e in errors)

    def test_missing_incumbent_fails(self):
        """Missing incumbent section fails."""
        bundle = _make_bundle()
        del bundle["incumbent"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("incumbent" in e for e in errors)

    def test_valid_r0_bundle(self):
        """R0 bundle with rung_id='r0' passes."""
        bundle = _make_bundle(rung_id="r0")
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_valid_r5_bundle(self):
        """R5 bundle with rung_id='r5' passes."""
        bundle = _make_bundle(rung_id="r5")
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_missing_artifact_sha256_fails(self):
        """Arm missing artifact_sha256 fails."""
        bundle = _make_bundle()
        del bundle["olsa"]["artifact_sha256"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("artifact_sha256" in e for e in errors)

    def test_bundle_comparator_keys_valid(self):
        """Bundle with comparator_battery string and comparator_eval null passes."""
        bundle = _make_bundle(
            comparator_battery="data/artifacts/arc_d/r0/comparator_battery_r0.json",
            comparator_eval=None,
        )
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_bundle_without_comparator_keys_passes(self):
        """Bundle without comparator keys passes (backward compat)."""
        bundle = _make_bundle()
        # Ensure no comparator keys are present
        assert "comparator_battery" not in bundle
        assert "comparator_eval" not in bundle
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_bundle_comparator_wrong_type_fails(self):
        """Bundle with non-string comparator_battery produces error."""
        bundle = _make_bundle(comparator_battery=42)
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("comparator_battery" in e and "int" in e for e in errors)

    def test_bundle_h2h_battery_keys_valid(self):
        """Bundle with h2h_battery_quick/full string paths passes."""
        bundle = _make_bundle(
            h2h_battery_quick="data/artifacts/arc_d/r0/h2h_battery_quick_v2.json",
            h2h_battery_full="data/artifacts/arc_d/r0/h2h_battery_full_v2.json",
        )
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_bundle_without_h2h_battery_keys_passes(self):
        """Bundle without h2h_battery keys passes (backward compat)."""
        bundle = _make_bundle()
        assert "h2h_battery_quick" not in bundle
        assert "h2h_battery_full" not in bundle
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_bundle_h2h_battery_wrong_type_fails(self):
        """Bundle with non-string h2h_battery_quick produces error."""
        bundle = _make_bundle(h2h_battery_quick=42)
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("h2h_battery_quick" in e and "int" in e for e in errors)


class TestBundleFilesExist:
    """Tests for validate_bundle_files_exist()."""

    def test_all_files_exist(self, tmp_path):
        """Returns valid when all referenced files exist."""
        bundle = _make_bundle()
        # Create all referenced files
        for arm in ("olsa", "olsa_full"):
            for key in ("artifact_path", "eval_seed42", "eval_seed43", "eval_seed44"):
                path = bundle[arm].get(key)
                if path:
                    _write_json(tmp_path / path, {})
        _write_json(tmp_path / bundle["incumbent"]["artifact_path"], {})
        _write_json(tmp_path / bundle["split_manifest"], {})
        # R1+ path keys
        if bundle.get("h2h_summary"):
            _write_json(tmp_path / bundle["h2h_summary"], {})
        if bundle.get("gate_thresholds"):
            _write_json(tmp_path / bundle["gate_thresholds"], {})
        progression_report_path = bundle.get("progression_report")
        if progression_report_path:
            fp = tmp_path / progression_report_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("# Placeholder\ngate_status: N/A\n")

        valid, errors = validate_bundle_files_exist(bundle, str(tmp_path))
        assert valid, f"Expected valid, got errors: {errors}"

    def test_missing_file_fails(self, tmp_path):
        """Returns invalid when a referenced file is missing."""
        bundle = _make_bundle()
        valid, errors = validate_bundle_files_exist(bundle, str(tmp_path))
        assert not valid
        assert len(errors) > 0


class TestLoadAndValidateBundle:
    """Tests for load_and_validate_bundle()."""

    def test_nonexistent_file(self):
        """Returns error for nonexistent bundle file."""
        bundle, valid, errors = load_and_validate_bundle("/nonexistent/path.json")
        assert not valid
        assert any("not found" in e for e in errors)

    def test_invalid_json(self, tmp_path):
        """Returns error for invalid JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json{{{")
        bundle, valid, errors = load_and_validate_bundle(str(bad_file))
        assert not valid
        assert any("Failed to read" in e for e in errors)

    def test_valid_bundle_file(self, tmp_path):
        """Valid bundle JSON file loads and validates successfully."""
        bundle_data = _make_bundle()
        bundle_path = tmp_path / "bundle.json"
        _write_json(bundle_path, bundle_data)
        bundle, valid, errors = load_and_validate_bundle(str(bundle_path))
        assert valid, f"Expected valid, got errors: {errors}"
        assert bundle["rung_id"] == "r1"


# =============================================================================
# TestHelpers
# =============================================================================


class TestHelpers:
    """Tests for helper functions in arc_d_gate.py."""

    def test_all_metrics_finite_true(self):
        """Returns True for all-finite metrics."""
        metrics = _make_eval_metrics()
        assert _all_metrics_finite(metrics)

    def test_all_metrics_finite_nan(self):
        """Returns False when NaN is present."""
        metrics = _make_eval_metrics(net_eppd=float("nan"))
        assert not _all_metrics_finite(metrics)

    def test_all_metrics_finite_inf(self):
        """Returns False when Inf is present."""
        metrics = _make_eval_metrics(net_eppd=float("inf"))
        assert not _all_metrics_finite(metrics)

    def test_all_metrics_finite_neg_inf(self):
        """Returns False when -Inf is present."""
        metrics = _make_eval_metrics(net_eppd=float("-inf"))
        assert not _all_metrics_finite(metrics)

    def test_get_metric_present(self):
        """Returns value when key exists."""
        assert _get_metric({"net_eppd": 0.5}, "net_eppd") == 0.5

    def test_get_metric_missing(self):
        """Returns default when key is missing."""
        assert _get_metric({}, "net_eppd", 0.0) == 0.0

    def test_get_metric_none(self):
        """Returns default when value is None."""
        assert _get_metric({"net_eppd": None}, "net_eppd", 0.0) == 0.0


# =============================================================================
# TestGuardrails
# =============================================================================


class TestGuardrails:
    """Tests for _check_guardrails()."""

    def test_all_pass(self):
        """Returns None when all guardrails pass."""
        c = _make_eval_metrics()
        i = _make_eval_metrics()
        assert _check_guardrails(c, i) is None

    def test_bid_rate_too_low(self):
        """bid_rate < 0.05 fails."""
        c = _make_eval_metrics(bid_rate=0.04)
        i = _make_eval_metrics()
        result = _check_guardrails(c, i)
        assert result is not None
        assert "bid_rate" in result

    def test_bid_rate_too_high(self):
        """bid_rate > 0.95 fails."""
        c = _make_eval_metrics(bid_rate=0.96)
        i = _make_eval_metrics()
        result = _check_guardrails(c, i)
        assert result is not None
        assert "bid_rate" in result

    def test_make_rate_too_low(self):
        """make_rate < 0.45 fails."""
        c = _make_eval_metrics(make_rate=0.40)
        i = _make_eval_metrics()
        result = _check_guardrails(c, i)
        assert result is not None
        assert "make_rate" in result

    def test_cvar5_regression(self):
        """cvar_5 regression beyond tolerance fails."""
        c = _make_eval_metrics(cvar_5=-0.70)
        i = _make_eval_metrics(cvar_5=-0.50)
        result = _check_guardrails(c, i)
        assert result is not None
        assert "cvar_5" in result

    def test_downside_variance(self):
        """downside_variance > 1.10x incumbent fails."""
        c = _make_eval_metrics(downside_variance=1.20)
        i = _make_eval_metrics(downside_variance=1.00)
        result = _check_guardrails(c, i)
        assert result is not None
        assert "downside_variance" in result

    def test_cvar5_within_tolerance(self):
        """cvar_5 regression within tolerance passes."""
        c = _make_eval_metrics(cvar_5=-0.55)
        i = _make_eval_metrics(cvar_5=-0.50)
        assert _check_guardrails(c, i) is None

    def test_downside_variance_within_ratio(self):
        """downside_variance within 1.10x passes."""
        c = _make_eval_metrics(downside_variance=1.05)
        i = _make_eval_metrics(downside_variance=1.00)
        assert _check_guardrails(c, i) is None


# =============================================================================
# TestPromotionGate
# =============================================================================


class TestPromotionGate:
    """Tests for the promotion_gate() function."""

    def test_schema_mismatch_halt(self, tmp_path):
        """Wrong bundle schema -> HALT."""
        bundle = _make_bundle(bundle_schema="wrong_v2")
        bundle_path = _setup_gate_files(tmp_path, bundle)
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("Bundle validation FAIL" in r for r in reasons)

    def test_nan_metrics_halt(self, tmp_path):
        """NaN in challenger metrics -> HALT."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=float("nan")),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("no_nan_inf" in r for r in reasons)

    def test_inf_metrics_halt(self, tmp_path):
        """Inf in challenger metrics -> HALT."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(eppd=float("inf")),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("no_nan_inf" in r for r in reasons)

    def test_r0_auto_promote(self, tmp_path):
        """R0 with all finite metrics -> PROMOTED."""
        bundle = _make_bundle(rung_id="r0")
        bundle_path = _setup_gate_files(tmp_path, bundle)
        decision, reasons = promotion_gate(
            bundle_path, "r0", str(tmp_path), skip_eligibility=True
        )
        assert decision == "PROMOTED"
        assert any("attribution_gap" in r for r in reasons)

    def test_r0_nan_halt(self, tmp_path):
        """R0 with NaN -> HALT (even R0 requires finite metrics)."""
        bundle = _make_bundle(rung_id="r0")
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=float("nan")),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r0", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"

    def test_improvement_promoted(self, tmp_path):
        """R1 with H2H CI_low > delta_floor -> PROMOTED."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)

    def test_insufficient_delta_advanced(self, tmp_path):
        """H2H CI inconclusive -> ADVANCED."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.02, ci_high=0.04, net_eppd_delta=0.01
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(
                net_eppd=0.405, std_points=2.0, n_deals=50000
            ),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "ADVANCED"
        assert any("inconclusive" in r for r in reasons)

    def test_regression_halt(self, tmp_path):
        """H2H CI_high < -regression_threshold -> HALT."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.10, ci_high=-0.06, net_eppd_delta=-0.08
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.30),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("H2H primary" in r for r in reasons)

    def test_both_seeds_reversed_halt(self, tmp_path):
        """H2H regression -> HALT (sensitivity check is covered by H2H primary)."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.10, ci_high=-0.06, net_eppd_delta=-0.08
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.50),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
            challenger_s43=_make_eval_metrics(net_eppd=0.35),
            challenger_s44=_make_eval_metrics(net_eppd=0.36),
            incumbent_s43=_make_eval_metrics(net_eppd=0.40),
            incumbent_s44=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("H2H primary" in r for r in reasons)

    def test_one_seed_reversed_ok(self, tmp_path):
        """H2H PROMOTED overrides seed reversal (H2H primary is decisive)."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
            challenger_s43=_make_eval_metrics(net_eppd=0.35),  # reversed
            challenger_s44=_make_eval_metrics(net_eppd=0.50),  # not reversed
            incumbent_s43=_make_eval_metrics(net_eppd=0.40),
            incumbent_s44=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)

    def test_bid_rate_too_low_halt(self, tmp_path):
        """bid_rate < 0.05 -> HALT (non-R0)."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, bid_rate=0.03),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("bid_rate" in r for r in reasons)

    def test_bid_rate_too_high_halt(self, tmp_path):
        """bid_rate > 0.95 -> HALT (non-R0)."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, bid_rate=0.97),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("bid_rate" in r for r in reasons)

    def test_make_rate_too_low_halt(self, tmp_path):
        """make_rate < 0.45 -> HALT (non-R0)."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, make_rate=0.40),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("make_rate" in r for r in reasons)

    def test_cvar5_regression_halt(self, tmp_path):
        """cvar_5 regression beyond tolerance -> HALT (non-R0)."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, cvar_5=-0.70),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40, cvar_5=-0.50),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("cvar_5" in r for r in reasons)

    def test_downside_variance_halt(self, tmp_path):
        """downside_variance > 1.10x incumbent -> HALT."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(
                net_eppd=0.60, downside_variance=1.20
            ),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40, downside_variance=1.00),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("downside_variance" in r for r in reasons)

    def test_r5_cvar5_not_improved_advanced(self, tmp_path):
        """R5 with inconclusive H2H -> ADVANCED (H2H primary decisive for R1+)."""
        bundle = _make_bundle(
            rung_id="r5",
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.02, ci_high=0.04, net_eppd_delta=0.01
            ),
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, cvar_5=-0.50),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40, cvar_5=-0.50),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r5", str(tmp_path), skip_eligibility=True
        )
        assert decision == "ADVANCED"
        assert any("inconclusive" in r for r in reasons)

    def test_attribution_gap_recorded(self, tmp_path):
        """PROMOTED result includes attribution_gap value."""
        bundle = _make_bundle(rung_id="r0")
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            olsa_metrics=_make_eval_metrics(net_eppd=0.55),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r0", str(tmp_path), skip_eligibility=True
        )
        assert decision == "PROMOTED"
        assert any("attribution_gap=" in r for r in reasons)
        # Check the attribution_gap value is correct: 0.60 - 0.55 = 0.05
        gap_str = [r for r in reasons if "attribution_gap=" in r][0]
        gap_val = float(gap_str.split("=")[1])
        assert abs(gap_val - 0.05) < 0.001

    def test_guardrails_skip_r0(self, tmp_path):
        """R0 skips guardrail checks (even with bad bid_rate)."""
        bundle = _make_bundle(rung_id="r0")
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(bid_rate=0.01),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r0", str(tmp_path), skip_eligibility=True
        )
        # R0 auto-promotes regardless of guardrails
        assert decision == "PROMOTED"

    def test_eligibility_failure_halt(self, tmp_path):
        """compute_eligibility returns ineligible -> HALT."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )

        # Mock compute_eligibility to return ineligible
        from bid_euchre.reporting.eligibility import BatchGate, EligibilityResult

        mock_gate = BatchGate(
            eligible=False,
            reasons=[
                EligibilityResult(
                    rule="artifacts_frozen",
                    status="FAIL",
                    detail="Unfrozen artifacts found",
                )
            ],
            batch_id="test",
            batch_purpose="arc_d_gate",
            created_at_utc="2026-02-20T12:00:00Z",
        )

        with patch(
            "bid_euchre.reporting.eligibility.compute_eligibility",
            return_value=mock_gate,
        ):
            decision, reasons = promotion_gate(
                bundle_path, "r1", str(tmp_path), skip_eligibility=False
            )
        assert decision == "HALT"
        assert any("Eligibility FAIL" in r for r in reasons)

    def test_eligibility_success_continues(self, tmp_path):
        """compute_eligibility returns eligible -> gate continues to H2H primary."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )

        from bid_euchre.reporting.eligibility import BatchGate, EligibilityResult

        mock_gate = BatchGate(
            eligible=True,
            reasons=[
                EligibilityResult(rule="config_membership", status="PASS", detail="OK"),
                EligibilityResult(
                    rule="canonical_summaries", status="PASS", detail="OK"
                ),
                EligibilityResult(
                    rule="notebook_gate", status="PASS", detail="Optional"
                ),
                EligibilityResult(
                    rule="git_sha_consistency", status="PASS", detail="OK"
                ),
                EligibilityResult(rule="artifacts_frozen", status="PASS", detail="OK"),
                EligibilityResult(rule="split_manifests", status="PASS", detail="OK"),
            ],
            batch_id="test",
            batch_purpose="arc_d_gate",
            created_at_utc="2026-02-20T12:00:00Z",
        )

        with patch(
            "bid_euchre.reporting.eligibility.compute_eligibility",
            return_value=mock_gate,
        ):
            decision, reasons = promotion_gate(
                bundle_path, "r1", str(tmp_path), skip_eligibility=False
            )
        # H2H primary with ci_low=0.02 > delta_floor=0.01 -> PROMOTED
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)

    def test_wrong_artifact_type_halt(self, tmp_path):
        """Artifact type != hybrid_olsa_v1 -> HALT."""
        bundle = _make_bundle()
        bundle_path = _setup_gate_files(
            tmp_path, bundle, artifact_type="bidder_linear_regression_v1"
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("schema_version" in r for r in reasons)

    def test_missing_std_points_r1_uses_h2h(self, tmp_path):
        """R1+ without std_points still works via H2H primary (no SE needed)."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.02, ci_high=0.04, net_eppd_delta=0.01
            )
        )
        # Create metrics without std_points or net_bidder_team_points
        metrics_no_std = {
            "net_eppd": 0.60,
            "net_expected_points_per_deal": 0.60,
            "eppd": 0.70,
            "expected_points_per_deal": 0.70,
            "bid_rate": 0.30,
            "make_rate": 0.65,
            "cvar_5": -0.50,
            "downside_variance": 1.0,
            "n_deals": 50000,
        }
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=metrics_no_std,
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        # H2H primary is decisive for R1+ -- no SE calculation needed
        assert decision == "ADVANCED"
        assert any("inconclusive" in r for r in reasons)

    def test_evaluator_canonical_names_work(self, tmp_path):
        """Metrics using only canonical evaluator names (no aliases) work."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        # Use only canonical evaluator field names -- no short aliases
        canonical_metrics = {
            "net_expected_points_per_deal": 0.60,
            "expected_points_per_deal": 0.70,
            "bid_rate": 0.30,
            "make_rate": 0.65,
            "cvar_5": -0.50,
            "downside_variance": 1.0,
            "deals_total": 50000,
            "net_bidder_team_points": [float(i) for i in range(100)],
        }
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=canonical_metrics,
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        # H2H primary is decisive -- canonical names work through guardrails
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)


# =============================================================================
# TestThresholdLoading
# =============================================================================


class TestThresholdLoading:
    """Tests for _load_thresholds()."""

    def test_r0_uses_defaults(self):
        """R0 returns _DEFAULT_THRESHOLDS without needing artifact."""
        result = _load_thresholds("/nonexistent", "r0")
        assert result == _DEFAULT_THRESHOLDS

    def test_r1_loads_from_file(self, tmp_path):
        """R1 loads thresholds from gate_thresholds_r1.json."""
        thresholds_data = _make_gate_thresholds()
        # Override one value to verify it's loaded
        thresholds_data["thresholds"]["delta_floor"] = 0.025
        thresholds_path = tmp_path / "gate_thresholds_r1.json"
        _write_json(thresholds_path, thresholds_data)

        result = _load_thresholds(
            str(tmp_path), "r1", thresholds_path="gate_thresholds_r1.json"
        )
        assert result["delta_floor"] == 0.025

    def test_r1_auto_discovers(self, tmp_path):
        """R1 auto-discovers gate_thresholds_r1.json in base_dir."""
        thresholds_data = _make_gate_thresholds()
        thresholds_data["thresholds"]["delta_floor"] = 0.03
        _write_json(tmp_path / "gate_thresholds_r1.json", thresholds_data)

        result = _load_thresholds(str(tmp_path), "r1")
        assert result["delta_floor"] == 0.03

    def test_r1_hard_fails_without_threshold_file(self, tmp_path):
        """R1 hard fails when no threshold artifact found."""
        import pytest

        with pytest.raises(FileNotFoundError, match="R1\\+ rungs require"):
            _load_thresholds(str(tmp_path), "r1")

    def test_r1_fails_with_explicit_missing_path(self, tmp_path):
        """R1 hard fails if explicit thresholds_path doesn't exist."""
        import pytest

        with pytest.raises(FileNotFoundError, match="Threshold artifact not found"):
            _load_thresholds(str(tmp_path), "r1", thresholds_path="missing.json")

    def test_threshold_loading_schema_validation(self, tmp_path):
        """Malformed threshold artifact raises clear error."""
        import pytest

        bad_data = {"schema": "wrong_schema", "thresholds": {}}
        _write_json(tmp_path / "bad.json", bad_data)

        with pytest.raises(ValueError, match="gate_thresholds_v1"):
            _load_thresholds(str(tmp_path), "r1", thresholds_path="bad.json")

    def test_threshold_loading_missing_keys(self, tmp_path):
        """Threshold artifact missing required keys raises error."""
        import pytest

        bad_data = {
            "schema": "gate_thresholds_v1",
            "thresholds": {"delta_floor": 0.01},  # Missing other required keys
        }
        _write_json(tmp_path / "partial.json", bad_data)

        with pytest.raises(ValueError, match="missing required keys"):
            _load_thresholds(str(tmp_path), "r1", thresholds_path="partial.json")


# =============================================================================
# TestH2HPrimaryGate
# =============================================================================


class TestH2HPrimaryGate:
    """Tests for H2H-primary promotion gate (R1+)."""

    def test_h2h_primary_promoted(self, tmp_path):
        """CI_low > delta_floor -> PROMOTED."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.60),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)

    def test_h2h_primary_halt(self, tmp_path):
        """CI_high < -regression_threshold -> HALT."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.10, ci_high=-0.06, net_eppd_delta=-0.08
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(net_eppd=0.35),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "HALT"
        assert any("H2H primary" in r for r in reasons)

    def test_h2h_primary_advanced(self, tmp_path):
        """In-between CIs -> ADVANCED from H2H primary."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=-0.02, ci_high=0.04, net_eppd_delta=0.01
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            challenger_metrics=_make_eval_metrics(
                net_eppd=0.405, std_points=2.0, n_deals=50000
            ),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        assert decision == "ADVANCED"
        assert any("inconclusive" in r for r in reasons)

    def test_guardrails_use_loaded_thresholds(self, tmp_path):
        """Guardrails apply artifact threshold values, not hardcoded constants."""
        # Create thresholds with wider bid_rate range
        custom_thresholds = _make_gate_thresholds()
        custom_thresholds["thresholds"]["bid_rate_min"] = 0.01
        custom_thresholds["thresholds"]["bid_rate_max"] = 0.99

        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        )
        bundle_path = _setup_gate_files(
            tmp_path,
            bundle,
            # bid_rate=0.03 would fail default thresholds (0.05) but pass custom (0.01)
            challenger_metrics=_make_eval_metrics(net_eppd=0.60, bid_rate=0.03),
            incumbent_metrics=_make_eval_metrics(net_eppd=0.40),
            gate_thresholds=custom_thresholds,
        )
        decision, reasons = promotion_gate(
            bundle_path, "r1", str(tmp_path), skip_eligibility=True
        )
        # Should NOT halt on bid_rate because custom threshold allows 0.01-0.99
        assert decision == "PROMOTED"
        assert any("H2H primary" in r for r in reasons)

    def test_h2h_check_function_promoted(self):
        """_check_h2h_primary returns PROMOTED when ci_low > delta_floor."""
        bundle = {
            "h2h_challenger_vs_incumbent": _make_h2h_inline(
                ci_low=0.02, ci_high=0.06, net_eppd_delta=0.04
            )
        }
        thresholds = dict(_DEFAULT_THRESHOLDS)
        decision, reason = _check_h2h_primary(bundle, thresholds)
        assert decision == "PROMOTED"
        assert "H2H primary" in reason

    def test_h2h_check_function_halt(self):
        """_check_h2h_primary returns HALT when ci_high < -regression_threshold."""
        bundle = {
            "h2h_challenger_vs_incumbent": _make_h2h_inline(
                ci_low=-0.10, ci_high=-0.06, net_eppd_delta=-0.08
            )
        }
        thresholds = dict(_DEFAULT_THRESHOLDS)
        decision, reason = _check_h2h_primary(bundle, thresholds)
        assert decision == "HALT"
        assert "H2H primary" in reason

    def test_h2h_check_function_inconclusive(self):
        """_check_h2h_primary returns ADVANCED when CI spans zero."""
        bundle = {
            "h2h_challenger_vs_incumbent": _make_h2h_inline(
                ci_low=-0.02, ci_high=0.04, net_eppd_delta=0.01
            )
        }
        thresholds = dict(_DEFAULT_THRESHOLDS)
        decision, reason = _check_h2h_primary(bundle, thresholds)
        assert decision == "ADVANCED"
        assert "inconclusive" in reason

    def test_h2h_check_function_missing_data(self):
        """_check_h2h_primary returns ADVANCED when h2h data is absent."""
        bundle = {}
        thresholds = dict(_DEFAULT_THRESHOLDS)
        decision, reason = _check_h2h_primary(bundle, thresholds)
        assert decision == "ADVANCED"
        assert "absent" in reason

    def test_h2h_check_malformed_numeric_halt(self):
        """_check_h2h_primary returns HALT on non-numeric CI values."""
        bundle = {
            "h2h_challenger_vs_incumbent": _make_h2h_inline(
                ci_low="not_a_number", ci_high=0.06, net_eppd_delta=0.04
            )
        }
        thresholds = dict(_DEFAULT_THRESHOLDS)
        decision, reason = _check_h2h_primary(bundle, thresholds)
        assert decision == "HALT"
        assert "non-numeric" in reason


# =============================================================================
# TestR1BundleValidation
# =============================================================================


class TestR1BundleValidation:
    """Tests for R1+ bundle key enforcement."""

    def test_r1_bundle_missing_h2h_keys_fails(self):
        """R1 bundle without REQUIRED_R1_PLUS_KEYS -> validation error."""
        bundle = _make_bundle()
        # Remove R1+ keys
        del bundle["h2h_summary"]
        del bundle["h2h_challenger_vs_incumbent"]
        del bundle["gate_thresholds"]
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("R1+ bundle missing" in e for e in errors)

    def test_r0_bundle_without_h2h_keys_passes(self):
        """R0 bundle passes without R1+ keys (backward compat)."""
        bundle = _make_bundle(rung_id="r0")
        # R0 bundles don't have R1+ keys (stripped by _make_bundle)
        assert "h2h_summary" not in bundle
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"

    def test_r1_h2h_inline_missing_subkeys_fails(self):
        """R1 h2h_challenger_vs_incumbent missing required sub-keys -> error."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent={"challenger": "x"}  # Missing most keys
        )
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("h2h_challenger_vs_incumbent missing" in e for e in errors)

    def test_r1_h2h_inline_wrong_type_fails(self):
        """R1 h2h_challenger_vs_incumbent as non-dict -> error."""
        bundle = _make_bundle(h2h_challenger_vs_incumbent="not_a_dict")
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("h2h_challenger_vs_incumbent must be a dict" in e for e in errors)

    def test_r1_h2h_inline_null_numeric_fails(self):
        """R1 h2h_challenger_vs_incumbent with null numeric sub-keys -> error."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(ci_low=None, ci_high=None)
        )
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("ci_low" in e and "must not be null" in e for e in errors)
        assert any("ci_high" in e and "must not be null" in e for e in errors)

    def test_r1_h2h_inline_non_numeric_fails(self):
        """R1 h2h_challenger_vs_incumbent with non-numeric values -> error."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=_make_h2h_inline(net_eppd_delta="not_a_number")
        )
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any(
            "net_eppd_delta" in e and "must be numeric" in e and "str" in e
            for e in errors
        )

    def test_r1_h2h_files_checked(self, tmp_path):
        """validate_bundle_files_exist checks h2h_summary + gate_thresholds paths."""
        bundle = _make_bundle()
        # Only create base files, not h2h_summary / gate_thresholds
        for arm in ("olsa", "olsa_full"):
            for key in ("artifact_path", "eval_seed42", "eval_seed43", "eval_seed44"):
                path = bundle[arm].get(key)
                if path:
                    _write_json(tmp_path / path, {})
        _write_json(tmp_path / bundle["incumbent"]["artifact_path"], {})
        _write_json(tmp_path / bundle["split_manifest"], {})
        # Don't write h2h_summary or gate_thresholds

        valid, errors = validate_bundle_files_exist(bundle, str(tmp_path))
        assert not valid
        assert any("h2h_battery_full.json" in e for e in errors)
        assert any("gate_thresholds_r1.json" in e for e in errors)

    def test_r1_h2h_path_type_validation(self):
        """R1 h2h_summary must be string path."""
        bundle = _make_bundle(h2h_summary=42)
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("h2h_summary must be a string" in e for e in errors)

    def test_r1_gate_thresholds_path_type_validation(self):
        """R1 gate_thresholds must be string path."""
        bundle = _make_bundle(gate_thresholds={"nested": "dict"})
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("gate_thresholds must be a string" in e for e in errors)

    def test_r1_null_h2h_values_fail(self):
        """R1 bundle with null h2h_challenger_vs_incumbent -> validation error."""
        bundle = _make_bundle(
            h2h_challenger_vs_incumbent=None,
            h2h_summary=None,
            gate_thresholds=None,
        )
        # Manually set keys to None (instead of absent) to test null enforcement
        bundle["h2h_challenger_vs_incumbent"] = None
        bundle["h2h_summary"] = None
        bundle["gate_thresholds"] = None
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("must not be null" in e for e in errors)

    def test_r1_bundle_with_all_keys_passes(self):
        """R1 bundle with all required R1+ keys passes validation."""
        bundle = _make_bundle()
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"
        # Verify R1+ keys are present
        for key in REQUIRED_R1_PLUS_KEYS:
            assert key in bundle
        # Verify inline H2H has all required sub-keys
        for key in REQUIRED_H2H_INLINE_KEYS:
            assert key in bundle["h2h_challenger_vs_incumbent"]

    def test_r1_progression_report_non_string_fails(self):
        """R1 progression_report must be a string path."""
        bundle = _make_bundle(progression_report=42)
        valid, errors = validate_bundle(bundle)
        assert not valid
        assert any("progression_report must be a string" in e for e in errors)

    def test_r1_progression_report_file_checked(self, tmp_path):
        """validate_bundle_files_exist checks progression_report path."""
        bundle = _make_bundle()
        # Create all files except progression_report
        for arm in ("olsa", "olsa_full"):
            for key in ("artifact_path", "eval_seed42", "eval_seed43", "eval_seed44"):
                path = bundle[arm].get(key)
                if path:
                    _write_json(tmp_path / path, {})
        _write_json(tmp_path / bundle["incumbent"]["artifact_path"], {})
        _write_json(tmp_path / bundle["split_manifest"], {})
        _write_json(tmp_path / bundle["h2h_summary"], {"cells": {}})
        _write_json(tmp_path / bundle["gate_thresholds"], {})
        # Don't write progression_report

        valid, errors = validate_bundle_files_exist(bundle, str(tmp_path))
        assert not valid
        assert any("r0_to_r1_progression.md" in e for e in errors)

    def test_r0_bundle_no_progression_report(self):
        """R0 bundle passes without progression_report (R0 exempted)."""
        bundle = _make_bundle(rung_id="r0")
        assert "progression_report" not in bundle
        valid, errors = validate_bundle(bundle)
        assert valid, f"Expected valid, got errors: {errors}"


# =============================================================================
# TestRegistryUpdater
# =============================================================================


class TestRegistryUpdater:
    """Tests for update_arc_registry.py upsert logic."""

    def _make_decision(self, rung_id: str = "r0", decision: str = "PROMOTED") -> dict:
        return {
            "schema_version": 3,
            "rung_id": rung_id,
            "arc": "arc_d",
            "decision": decision,
            "reasons": ["attribution_gap=0.0500"],
            "bundle_path": (
                f"data/artifacts/arc_d/{rung_id}/rung_bundle_{rung_id}.json"
            ),
            "timestamp": "2026-02-20T12:00:00Z",
        }

    def test_upsert_new_row(self, tmp_path):
        """Adds row to empty/new registry."""
        registry_path = str(tmp_path / "MODEL_ARC_RUNS.md")
        bundle = _make_bundle(rung_id="r0")
        decision = self._make_decision("r0")

        result = upsert_registry(registry_path, bundle, decision, "400")
        assert "| r0 |" in result
        assert "PROMOTED" in result

    def test_upsert_replaces_existing(self, tmp_path):
        """Replaces existing rung row."""
        registry_path = tmp_path / "MODEL_ARC_RUNS.md"
        bundle = _make_bundle(rung_id="r0")
        decision = self._make_decision("r0", "PROMOTED")

        # Write initial registry
        initial = upsert_registry(str(registry_path), bundle, decision, "400")
        registry_path.write_text(initial)

        # Update with new decision
        decision2 = self._make_decision("r0", "HALT")
        result = upsert_registry(str(registry_path), bundle, decision2, "401")

        # Should have exactly one r0 row
        r0_rows = [line for line in result.split("\n") if line.startswith("| r0 |")]
        assert len(r0_rows) == 1
        assert "HALT" in r0_rows[0]

    def test_idempotent(self, tmp_path):
        """Running twice with same data produces same result."""
        registry_path = tmp_path / "MODEL_ARC_RUNS.md"
        bundle = _make_bundle(rung_id="r0")
        decision = self._make_decision("r0")

        result1 = upsert_registry(str(registry_path), bundle, decision, "400")
        registry_path.write_text(result1)

        result2 = upsert_registry(str(registry_path), bundle, decision, "400")

        assert result1 == result2

    def test_upsert_into_seeded_registry(self, tmp_path):
        """Upsert cleanly replaces *(pending)* row from PR #392 template."""
        registry_path = tmp_path / "MODEL_ARC_RUNS.md"
        # Seed with template-style content (matching PR #392)
        seeded = (
            "# Model Arc Runs\n\n"
            "Provenance registry for Arc D model promotion decisions.\n"
            "Updated by promotion scripts (`scripts/write_r0_promotion.py` for R0,\n"
            "gate runner for R1+).\n\n"
            "## Arc D: OLSa-Hybrid Bidder\n\n"
            "| Rung | Decision | OLSa_Full net_eppd | OLSa net_eppd "
            "| Attribution Gap | Date | Bundle |\n"
            "|------|----------|--------------------|---------------|"
            "-----------------|------|--------|\n"
            "| r0 | PROMOTED | *(pending)* | *(pending)* "
            "| *(pending)* | -- | `rung_bundle_r0.json` |\n"
        )
        registry_path.write_text(seeded)

        bundle = _make_bundle(rung_id="r0")
        decision = self._make_decision("r0")
        result = upsert_registry(str(registry_path), bundle, decision, "392")

        # Should have replaced the pending row
        r0_rows = [line for line in result.split("\n") if "| r0 |" in line]
        assert len(r0_rows) == 1
        assert "*(pending)*" not in r0_rows[0]
        assert "PROMOTED" in r0_rows[0]

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
    load_and_validate_bundle,
    validate_bundle,
    validate_bundle_files_exist,
)
from bid_euchre.validation.arc_d_gate import (
    _all_metrics_finite,
    _check_guardrails,
    _get_metric,
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


def _make_bundle(**overrides) -> dict:
    """Create a minimal valid arc_d_rung_bundle_v1 fixture."""
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
    }
    base.update(overrides)
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

    # Write OLSa eval files
    olsa = bundle.get("olsa", {})
    olsa_eval = olsa.get("eval_seed42")
    if olsa_eval:
        _write_json(tmp_path / olsa_eval, olsa_metrics)

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
        """R1 with sufficient improvement -> PROMOTED."""
        bundle = _make_bundle()
        # Challenger well above incumbent
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

    def test_insufficient_delta_advanced(self, tmp_path):
        """Delta below threshold -> ADVANCED."""
        bundle = _make_bundle()
        # Challenger barely above incumbent (within noise)
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
        assert any("insufficient improvement" in r for r in reasons)

    def test_regression_halt(self, tmp_path):
        """net_eppd < incumbent - 0.05 -> HALT."""
        bundle = _make_bundle()
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
        assert any("regression" in r for r in reasons)

    def test_both_seeds_reversed_halt(self, tmp_path):
        """Both seeds 43+44 reversed -> HALT."""
        bundle = _make_bundle()
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
        assert any("sensitivity" in r for r in reasons)

    def test_one_seed_reversed_ok(self, tmp_path):
        """Only one seed reversed -> continues (not HALT)."""
        bundle = _make_bundle()
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
        assert decision != "HALT" or not any("sensitivity" in r for r in reasons)

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
        """R5 cvar_5 not improved -> ADVANCED."""
        bundle = _make_bundle(rung_id="r5")
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
        assert any("cvar_5" in r for r in reasons)

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
        """compute_eligibility returns eligible -> gate continues to Tier 2."""
        bundle = _make_bundle()
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
        # Should reach PROMOTED since challenger (0.60) > incumbent (0.40) + delta
        assert decision == "PROMOTED"

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

    def test_missing_std_points_halts_r1(self, tmp_path):
        """R1+ with no std_points and no raw list -> HALT with explicit reason."""
        bundle = _make_bundle()
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
        assert decision == "HALT"
        assert any("std_points unavailable" in r for r in reasons)

    def test_evaluator_canonical_names_work(self, tmp_path):
        """Metrics using only canonical evaluator names (no aliases) work."""
        bundle = _make_bundle()
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
        # Should reach improvement gate (not HALT on missing fields)
        assert decision in ("PROMOTED", "ADVANCED")


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

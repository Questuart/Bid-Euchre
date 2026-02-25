"""Arc D promotion gate runner.

Adapter wrapping compute_eligibility() from the central eligibility engine.
Adds Arc D-specific Tier 1 (framework health) and Tier 2 (model quality)
gates on top. Returns one of: PROMOTED, ADVANCED, HALT.

The gate runner is fully deterministic from its inputs (bundle JSON + rung_id).
"""

from __future__ import annotations

import json
import logging
import math
import statistics
from pathlib import Path

from bid_euchre.models.freeze import verify_frozen
from bid_euchre.validation.arc_d_bundle import load_and_validate_bundle

logger = logging.getLogger(__name__)

# Thresholds from section 7 of the Arc D execution plan
DELTA_FLOOR = 0.01
BID_RATE_MIN = 0.05
BID_RATE_MAX = 0.95
MAKE_RATE_MIN = 0.45
CVAR5_TOLERANCE = 0.10
DOWNSIDE_VARIANCE_RATIO = 1.10
REGRESSION_THRESHOLD = 0.05

# Default thresholds dict (mirrors module-level constants)
_DEFAULT_THRESHOLDS = {
    "delta_floor": DELTA_FLOOR,
    "regression_threshold": REGRESSION_THRESHOLD,
    "bid_rate_min": BID_RATE_MIN,
    "bid_rate_max": BID_RATE_MAX,
    "make_rate_min": MAKE_RATE_MIN,
    "cvar5_tolerance": CVAR5_TOLERANCE,
    "downside_variance_ratio": DOWNSIDE_VARIANCE_RATIO,
}

# Required keys in gate_thresholds_v1 schema
_REQUIRED_THRESHOLD_KEYS = {
    "delta_floor",
    "regression_threshold",
    "bid_rate_min",
    "bid_rate_max",
    "make_rate_min",
    "cvar5_tolerance",
    "downside_variance_ratio",
}

# Metric alias map: evaluator canonical name -> short alias used by gate logic.
# The gate uses short aliases internally (net_eppd, eppd, std_points, n_deals).
# normalize_eval_metrics() maps evaluator output to these.
_METRIC_ALIASES = {
    "net_expected_points_per_deal": "net_eppd",
    "expected_points_per_deal": "eppd",
}


def normalize_eval_metrics(raw: dict) -> dict:
    """Normalize evaluator output metrics to gate-internal short aliases.

    Canonical evaluator keys (net_expected_points_per_deal, etc.) are mapped
    to short aliases (net_eppd, eppd). The std_points field is derived from
    the raw net_bidder_team_points list if present, or from
    std_bidder_team_points if the evaluator provides it.

    Args:
        raw: Dict from evaluator JSON (may be top-level or nested).

    Returns:
        New dict with both canonical and aliased keys, plus derived std_points.
    """
    out = dict(raw)

    # Add short aliases for canonical metric names
    for canonical, alias in _METRIC_ALIASES.items():
        if canonical in out and alias not in out:
            out[alias] = out[canonical]
        elif alias in out and canonical not in out:
            out[canonical] = out[alias]

    # Derive n_deals from deals_total if needed
    if "n_deals" not in out and "deals_total" in out:
        out["n_deals"] = out["deals_total"]

    # Derive std_points from raw point lists or std_bidder_team_points
    if "std_points" not in out:
        net_points = out.get("net_bidder_team_points")
        if isinstance(net_points, list) and len(net_points) >= 2:
            out["std_points"] = statistics.stdev(net_points)
        elif "std_bidder_team_points" in out:
            out["std_points"] = out["std_bidder_team_points"]
        # else: std_points remains absent -- callers must handle

    return out


def _load_eval_metrics(eval_path: str, base_dir: str) -> dict:
    """Load eval JSON, normalize, and return the metrics dict.

    Delegates parsing to the shared ``load_eval_metrics`` in
    ``bid_euchre.reporting.evaluator`` and then normalizes via
    ``normalize_eval_metrics()``.

    Args:
        eval_path: Relative path to eval JSON file.
        base_dir: Base directory to resolve relative paths.

    Returns:
        Dict of metric name -> value (normalized).

    Raises:
        FileNotFoundError: If eval file doesn't exist.
        json.JSONDecodeError: If file is invalid JSON.
    """
    from bid_euchre.reporting.evaluator import load_eval_metrics

    full_path = Path(base_dir) / eval_path
    metrics = load_eval_metrics(full_path)
    return normalize_eval_metrics(metrics)


def _all_metrics_finite(metrics: dict) -> bool:
    """Check that all numeric metric values are finite (no NaN/Inf).

    Skips list-valued fields (e.g. bidder_team_points raw lists).

    Args:
        metrics: Dict of metric name -> value.

    Returns:
        True if all numeric values are finite.
    """
    for value in metrics.values():
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return False
    return True


def _get_metric(metrics: dict, key: str, default: float = 0.0) -> float:
    """Safely extract a float metric value.

    Args:
        metrics: Dict of metric name -> value.
        key: Metric key to look up.
        default: Default value if key is missing.

    Returns:
        Float value.
    """
    val = metrics.get(key, default)
    if val is None:
        return default
    return float(val)


def _load_thresholds(
    base_dir: str,
    rung_id: str,
    thresholds_path: str | None = None,
) -> dict:
    """Load gate thresholds for the given rung.

    For R0: always returns _DEFAULT_THRESHOLDS (no artifact needed).
    For R1+:
      - If thresholds_path is provided, loads from that path (hard fail if missing/malformed).
      - Otherwise, auto-discovers gate_thresholds_r1.json in base_dir.
      - Falls back to _DEFAULT_THRESHOLDS with a warning if auto-discovery fails.

    Args:
        base_dir: Base directory for resolving relative paths.
        rung_id: Rung identifier (r0-r5).
        thresholds_path: Explicit path to gate thresholds JSON.

    Returns:
        Dict of threshold name -> value.

    Raises:
        FileNotFoundError: If explicit thresholds_path doesn't exist.
        ValueError: If threshold artifact is malformed.
    """
    if rung_id == "r0":
        return dict(_DEFAULT_THRESHOLDS)

    # R1+: try to load from artifact
    resolved_path: Path | None = None

    if thresholds_path is not None:
        resolved_path = Path(base_dir) / thresholds_path
        if not resolved_path.exists():
            raise FileNotFoundError(
                f"Threshold artifact not found: {resolved_path} "
                f"(thresholds_path={thresholds_path}, base_dir={base_dir})"
            )
    else:
        # Auto-discover: look for gate_thresholds_r1.json in base_dir
        auto_path = Path(base_dir) / "gate_thresholds_r1.json"
        if auto_path.exists():
            resolved_path = auto_path
        else:
            logger.warning(
                "No threshold artifact found for %s at %s; "
                "falling back to default thresholds",
                rung_id,
                auto_path,
            )
            return dict(_DEFAULT_THRESHOLDS)

    # Load and validate
    try:
        with open(resolved_path) as f:
            artifact = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        raise ValueError(f"Failed to read threshold artifact {resolved_path}: {e}")

    schema = artifact.get("schema")
    if schema != "gate_thresholds_v1":
        raise ValueError(
            f"Threshold artifact schema must be 'gate_thresholds_v1', "
            f"got '{schema}' in {resolved_path}"
        )

    thresholds = artifact.get("thresholds", {})
    missing = _REQUIRED_THRESHOLD_KEYS - set(thresholds.keys())
    if missing:
        raise ValueError(
            f"Threshold artifact missing required keys: {sorted(missing)} "
            f"in {resolved_path}"
        )

    return dict(thresholds)


def _check_h2h_primary(
    bundle: dict,
    thresholds: dict,
) -> tuple[str | None, str | None]:
    """Check H2H-primary promotion signal (R1+).

    Uses paired H2H challenger-vs-incumbent CI to determine promotion.

    Args:
        bundle: Validated bundle dict containing h2h_challenger_vs_incumbent.
        thresholds: Loaded threshold dict.

    Returns:
        Tuple of (decision, reason). Decision is "PROMOTED", "HALT", or None.
        None means CI is inconclusive -- fall through to ADVANCED.
    """
    h2h = bundle.get("h2h_challenger_vs_incumbent")
    if h2h is None:
        return (None, None)

    ci_low = h2h.get("ci_low")
    ci_high = h2h.get("ci_high")
    net_eppd_delta = h2h.get("net_eppd_delta")
    delta_floor = thresholds.get("delta_floor", DELTA_FLOOR)
    regression_threshold = thresholds.get("regression_threshold", REGRESSION_THRESHOLD)

    if ci_low is None or ci_high is None:
        return (None, None)

    if ci_low > delta_floor:
        return (
            "PROMOTED",
            f"H2H primary: CI_low={ci_low:.4f} > delta_floor={delta_floor:.4f} "
            f"(delta={net_eppd_delta:.4f}, CI=[{ci_low:.4f}, {ci_high:.4f}])",
        )

    if ci_high < -regression_threshold:
        return (
            "HALT",
            f"H2H primary: CI_high={ci_high:.4f} < -{regression_threshold:.4f} "
            f"(delta={net_eppd_delta:.4f}, CI=[{ci_low:.4f}, {ci_high:.4f}])",
        )

    return (None, None)


def promotion_gate(
    bundle_path: str,
    rung_id: str,
    base_dir: str | None = None,
    skip_eligibility: bool = False,
    thresholds_path: str | None = None,
) -> tuple[str, list[str]]:
    """Run the Arc D promotion gate.

    Fully deterministic from inputs. Returns (decision, reasons) where
    decision is one of: "PROMOTED", "ADVANCED", "HALT".

    For R0: existing self-play-only logic (unchanged).
    For R1+: H2H-primary promotion with self-play as fallback.
      1. Guardrails (bid_rate, make_rate, cvar5, downside_variance)
      2. H2H primary check (CI-based if h2h_challenger_vs_incumbent present)
      3. Fallback to self-play improvement gate (SE-based)

    Args:
        bundle_path: Path to rung bundle JSON.
        rung_id: Rung identifier (r0-r5).
        base_dir: Base directory for resolving relative paths.
            Defaults to current directory.
        skip_eligibility: If True, skip compute_eligibility() call.
            Used in testing to avoid needing full experiment infrastructure.
        thresholds_path: Path to gate thresholds JSON artifact.
            Auto-discovered if not provided (R1+ only).

    Returns:
        Tuple of (decision_string, list_of_reason_strings).
    """
    if base_dir is None:
        base_dir = "."

    # --- Pre-Gate: Bundle validation ---
    bundle, valid, errors = load_and_validate_bundle(
        bundle_path, check_files=(rung_id != "r0"), base_dir=base_dir
    )
    if not valid:
        return ("HALT", [f"Bundle validation FAIL: {errors}"])

    # --- Tier 1: Framework Health (all rungs, non-negotiable) ---
    tier1_result = _check_tier1(bundle, base_dir)
    if tier1_result is not None:
        return ("HALT", [tier1_result])

    # --- Pre-Gates: delegate to compute_eligibility() ---
    if not skip_eligibility:
        eligibility_result = _check_eligibility(bundle, base_dir)
        if eligibility_result is not None:
            return ("HALT", [eligibility_result])

    # --- Load metrics for Tier 2 ---
    olsa_full = bundle.get("olsa_full", {})
    olsa = bundle.get("olsa", {})

    try:
        challenger_metrics = _load_eval_metrics(olsa_full["eval_seed42"], base_dir)
    except (KeyError, FileNotFoundError, json.JSONDecodeError) as e:
        return ("HALT", [f"Failed to load challenger metrics: {e}"])

    # --- Load thresholds ---
    # Resolve thresholds_path: explicit arg > bundle's gate_thresholds > auto-discover
    effective_thresholds_path = thresholds_path
    if effective_thresholds_path is None:
        effective_thresholds_path = bundle.get("gate_thresholds")
    try:
        thresholds = _load_thresholds(base_dir, rung_id, effective_thresholds_path)
    except (FileNotFoundError, ValueError) as e:
        return ("HALT", [f"Failed to load thresholds: {e}"])

    # --- Tier 2: Guardrails (non-R0) ---
    if rung_id != "r0":
        # Load incumbent metrics for comparison
        incumbent = bundle.get("incumbent", {})
        incumbent_eval = incumbent.get("eval_seed42")
        if not incumbent_eval:
            # For non-R0, try to get incumbent from the bundle's control section
            control = bundle.get("control", {})
            incumbent_eval = control.get("eval_seed42")

        if incumbent_eval:
            try:
                incumbent_metrics = _load_eval_metrics(incumbent_eval, base_dir)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                return ("HALT", [f"Failed to load incumbent metrics: {e}"])
        else:
            return ("HALT", ["No incumbent eval_seed42 path for non-R0 rung"])

        guardrail_result = _check_guardrails(
            challenger_metrics, incumbent_metrics, thresholds
        )
        if guardrail_result is not None:
            return ("HALT", [guardrail_result])

        # --- H2H Primary Gate (R1+, if h2h data present) ---
        h2h_decision, h2h_reason = _check_h2h_primary(bundle, thresholds)
        if h2h_decision is not None:
            return (h2h_decision, [h2h_reason])

        # --- Fallback: Self-play improvement gate ---
        # Regression check
        c_net_eppd = _get_metric(challenger_metrics, "net_eppd")
        i_net_eppd = _get_metric(incumbent_metrics, "net_eppd")
        regression_threshold = thresholds.get(
            "regression_threshold", REGRESSION_THRESHOLD
        )

        if c_net_eppd < i_net_eppd - regression_threshold:
            return (
                "HALT",
                [
                    f"regression detected: net_eppd={c_net_eppd:.4f} "
                    f"< incumbent={i_net_eppd:.4f} - {regression_threshold}"
                ],
            )

        # --- Sensitivity: both seeds 43+44 reversed -> HALT ---
        sensitivity_result = _check_sensitivity(bundle, base_dir)
        if sensitivity_result is not None:
            return ("HALT", [sensitivity_result])

        # --- R5: strict cvar_5 improvement ---
        if rung_id == "r5":
            c_cvar5 = _get_metric(challenger_metrics, "cvar_5")
            i_cvar5 = _get_metric(incumbent_metrics, "cvar_5")
            if c_cvar5 <= i_cvar5:
                return (
                    "ADVANCED",
                    ["R5 cvar_5 not improved -- advancing without promotion"],
                )

        # --- Improvement gate ---
        # SE requires std_points.  normalize_eval_metrics() derives it from
        # the raw net_bidder_team_points list when possible.  If still absent,
        # HALT with an explicit reason rather than silently using a wrong value.
        delta_floor = thresholds.get("delta_floor", DELTA_FLOOR)
        if "std_points" not in challenger_metrics:
            return (
                "HALT",
                [
                    "std_points unavailable for SE calculation "
                    "(evaluator output missing net_bidder_team_points list "
                    "and std_bidder_team_points scalar)"
                ],
            )
        c_std = _get_metric(challenger_metrics, "std_points", 1.0)
        c_n = _get_metric(challenger_metrics, "n_deals", 1.0)
        se = c_std / (c_n**0.5) if c_n > 0 else 1.0
        effective_delta = max(delta_floor, 1.5 * se)

        if c_net_eppd <= i_net_eppd + effective_delta:
            return (
                "ADVANCED",
                [
                    f"insufficient improvement: delta={c_net_eppd - i_net_eppd:.4f}, "
                    f"threshold={effective_delta:.4f} "
                    f"(floor={delta_floor}, 1.5*SE={1.5 * se:.4f})"
                ],
            )

    # --- Record attribution_gap ---
    try:
        olsa_full_net_eppd = _get_metric(challenger_metrics, "net_eppd")
        olsa_metrics = _load_eval_metrics(olsa["eval_seed42"], base_dir)
        olsa_net_eppd = _get_metric(olsa_metrics, "net_eppd")
        attribution_gap = olsa_full_net_eppd - olsa_net_eppd
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        attribution_gap = 0.0

    return ("PROMOTED", [f"attribution_gap={attribution_gap:.4f}"])


def _check_tier1(bundle: dict, base_dir: str) -> str | None:
    """Run 8 Tier 1 framework health checks.

    Returns None if all pass, or an error string if any fail.
    """
    olsa_full = bundle.get("olsa_full", {})

    # 1. no_nan_inf: Check all metrics are finite
    eval_path = olsa_full.get("eval_seed42")
    if not eval_path:
        return "Tier 1 FAIL: no_nan_inf - missing eval_seed42 path"
    try:
        metrics = _load_eval_metrics(eval_path, base_dir)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return f"Tier 1 FAIL: no_nan_inf - {e}"

    if not _all_metrics_finite(metrics):
        return "Tier 1 FAIL: no_nan_inf"

    # 2. schema_version: Check artifact type is hybrid_olsa_v1
    artifact_path = olsa_full.get("artifact_path")
    if artifact_path:
        try:
            full_path = Path(base_dir) / artifact_path
            with open(full_path) as f:
                artifact = json.load(f)
            artifact_type = artifact.get("type", artifact.get("artifact_type"))
            if artifact_type != "hybrid_olsa_v1":
                return f"Tier 1 FAIL: schema_version - type={artifact_type}"
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return f"Tier 1 FAIL: schema_version - {e}"

    # 3. artifact_integrity: Check artifact is frozen
    if artifact_path:
        full_path = Path(base_dir) / artifact_path
        if not verify_frozen(full_path):
            return "Tier 1 FAIL: artifact_integrity"

    # 4. min_sample_size: Check training data size
    training_report = bundle.get("training_report")
    if training_report:
        try:
            full_path = Path(base_dir) / training_report
            with open(full_path) as f:
                report = json.load(f)
            train_rows = report.get("train_rows", 0)
            val_rows = report.get("val_rows", 0)
            if train_rows < 1000 or val_rows < 100:
                return (
                    f"Tier 1 FAIL: min_sample_size - "
                    f"train_rows={train_rows}, val_rows={val_rows}"
                )
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Training report is optional for Tier 1

    # 5. tricks_range: Check predictions in [0, 10]
    tricks_min = metrics.get("tricks_pred_min")
    tricks_max = metrics.get("tricks_pred_max")
    if tricks_min is not None and tricks_max is not None:
        if tricks_min < 0 or tricks_max > 10:
            return f"Tier 1 FAIL: tricks_range - min={tricks_min}, max={tricks_max}"

    # 6. determinism: Check determinism flag
    determinism = metrics.get("determinism_check_passed")
    if determinism is not None and not determinism:
        return "Tier 1 FAIL: determinism"

    # 7. split_hash: Check split manifest
    split_manifest = bundle.get("split_manifest")
    if split_manifest:
        try:
            full_path = Path(base_dir) / split_manifest
            with open(full_path) as f:
                manifest = json.load(f)
            if manifest.get("split_type") not in ("three_way", "two_way"):
                return "Tier 1 FAIL: split_hash - invalid split_type"
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Split manifest checked more thoroughly by compute_eligibility

    # 8. feature_count: Check feature count matches schema
    feature_count = metrics.get("feature_count")
    schema_feature_count = metrics.get("schema_feature_count")
    if (
        feature_count is not None
        and schema_feature_count is not None
        and feature_count != schema_feature_count
    ):
        return (
            f"Tier 1 FAIL: feature_count - "
            f"actual={feature_count}, schema={schema_feature_count}"
        )

    return None


def _check_eligibility(bundle: dict, base_dir: str) -> str | None:
    """Delegate to compute_eligibility() for pre-gate checks.

    Uses batch_purpose="arc_d_gate" (not "promotion") so that the central
    eligibility engine treats missing notebook-gate and missing artifact-dir
    as non-fatal.  Arc D bundles have their own Tier 1 artifact integrity
    checks, so we only delegate the subset of checks that are meaningful:
    artifact freeze verification, split manifest validation, and semantic
    gate checks.

    Returns None if eligible, or an error string if not.
    """
    # Import here to avoid circular imports and allow testing without
    # full experiment infrastructure
    from bid_euchre.reporting.eligibility import compute_eligibility

    olsa_full = bundle.get("olsa_full", {})

    # Build a minimal rollup for compute_eligibility.
    # Empty configs list means config_membership and canonical_summaries
    # pass trivially (nothing to check).
    rollup = {
        "configs": [],
        "batch": {
            "batch_id": f"arc_d_{bundle.get('rung_id', 'unknown')}",
            "batch_purpose": "arc_d_gate",
        },
    }

    # Use batch_purpose="arc_d_gate" so that:
    #   - check_notebook_gate(None, "arc_d_gate") -> PASS (optional)
    #   - check_artifacts_frozen(None, "arc_d_gate") -> PASS (optional)
    # Arc D's own Tier 1 already verifies artifact integrity directly.
    eligibility = compute_eligibility(
        rollup=rollup,
        run_base_dir=base_dir,
        batch_purpose="arc_d_gate",
        artifact_dir=str(
            Path(base_dir) / Path(olsa_full.get("artifact_path", "")).parent
        )
        if olsa_full.get("artifact_path")
        else None,
        split_manifest_dir=str(
            Path(base_dir) / Path(bundle.get("split_manifest", "")).parent
        )
        if bundle.get("split_manifest")
        else None,
        semantic_gate_dir=str(
            Path(base_dir) / Path(olsa_full.get("semantic_gate_val", "")).parent
        )
        if olsa_full.get("semantic_gate_val")
        else None,
    )

    if not eligibility.eligible:
        failed = [r for r in eligibility.reasons if r.status != "PASS"]
        return f"Eligibility FAIL: {[r.detail for r in failed]}"

    return None


def _check_guardrails(
    challenger_metrics: dict,
    incumbent_metrics: dict,
    thresholds: dict | None = None,
) -> str | None:
    """Check guardrail thresholds (non-R0 rungs).

    Args:
        challenger_metrics: Challenger eval metrics.
        incumbent_metrics: Incumbent eval metrics.
        thresholds: Optional threshold dict. Falls back to _DEFAULT_THRESHOLDS.

    Returns None if all pass, or an error string on first failure.
    """
    if thresholds is None:
        thresholds = _DEFAULT_THRESHOLDS

    bid_rate_min = thresholds.get("bid_rate_min", BID_RATE_MIN)
    bid_rate_max = thresholds.get("bid_rate_max", BID_RATE_MAX)
    make_rate_min = thresholds.get("make_rate_min", MAKE_RATE_MIN)
    cvar5_tolerance = thresholds.get("cvar5_tolerance", CVAR5_TOLERANCE)
    downside_variance_ratio = thresholds.get(
        "downside_variance_ratio", DOWNSIDE_VARIANCE_RATIO
    )

    bid_rate = _get_metric(challenger_metrics, "bid_rate", 0.5)
    if not (bid_rate_min <= bid_rate <= bid_rate_max):
        return f"bid_rate out of range [{bid_rate_min}, {bid_rate_max}]: {bid_rate:.4f}"

    make_rate = _get_metric(challenger_metrics, "make_rate", 0.5)
    if make_rate < make_rate_min:
        return f"make_rate below {make_rate_min}: {make_rate:.4f}"

    c_cvar5 = _get_metric(challenger_metrics, "cvar_5")
    i_cvar5 = _get_metric(incumbent_metrics, "cvar_5")
    if c_cvar5 < i_cvar5 - cvar5_tolerance:
        return f"cvar_5 regression beyond {cvar5_tolerance} tolerance: {c_cvar5:.4f} < {i_cvar5:.4f} - {cvar5_tolerance}"

    c_downside = _get_metric(challenger_metrics, "downside_variance", 1.0)
    i_downside = _get_metric(incumbent_metrics, "downside_variance", 1.0)
    if c_downside > i_downside * downside_variance_ratio:
        return (
            f"downside_variance exceeds {downside_variance_ratio}x incumbent: "
            f"{c_downside:.4f} > {i_downside:.4f} * {downside_variance_ratio}"
        )

    return None


def _check_sensitivity(bundle: dict, base_dir: str) -> str | None:
    """Check seed sensitivity: both seeds 43+44 reversed -> HALT.

    Returns None if OK, or an error string if both alternative seeds show reversal.
    """
    olsa_full = bundle.get("olsa_full", {})
    incumbent = bundle.get("incumbent", {})

    try:
        c43 = _load_eval_metrics(olsa_full["eval_seed43"], base_dir)
        c44 = _load_eval_metrics(olsa_full["eval_seed44"], base_dir)
    except (KeyError, FileNotFoundError, json.JSONDecodeError):
        return None  # If sensitivity evals missing, skip check

    i43_path = incumbent.get("eval_seed43")
    i44_path = incumbent.get("eval_seed44")
    if not i43_path or not i44_path:
        return None  # No incumbent sensitivity evals to compare

    try:
        i43 = _load_eval_metrics(i43_path, base_dir)
        i44 = _load_eval_metrics(i44_path, base_dir)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    d43 = _get_metric(c43, "net_eppd") - _get_metric(i43, "net_eppd")
    d44 = _get_metric(c44, "net_eppd") - _get_metric(i44, "net_eppd")

    if d43 < 0 and d44 < 0:
        return "sensitivity: both seeds 43 and 44 reversed"

    return None

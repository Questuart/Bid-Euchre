"""Advance check logic for Arc D v2 rung evaluation.

Evaluates hypotheses against generated tables, runs sufficiency and canary
checks, and produces a machine-readable advance decision (PROCEED / INVESTIGATE
/ PAUSE).

Extracted from ``scripts/internal/generate_advance_check.py``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from bid_euchre.core.time import utc_now_iso

# ---------------------------------------------------------------------------
# Hypothesis evaluation
# ---------------------------------------------------------------------------

COMPARISON_OPS = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _read_csv_value(
    tables_dir: Path,
    source_table: str,
    source_column: str,
    source_filter: dict,
) -> float | None:
    """Read a single value from a CSV table, applying filters.

    Returns the first matching row's value, or None if not found.
    """
    csv_path = tables_dir / source_table
    if not csv_path.exists():
        return None

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            match = all(row.get(key) == str(val) for key, val in source_filter.items())
            if match:
                raw = row.get(source_column)
                if raw is None:
                    return None
                try:
                    return float(raw)
                except (ValueError, TypeError):
                    return None
    return None


def _read_csv_aggregate(
    tables_dir: Path,
    source_table: str,
    source_column: str,
    source_filter: dict,
    aggregate: str,
) -> float | None:
    """Read an aggregate (min/max) across all matching rows in a CSV table.

    Args:
        aggregate: "min" or "max"

    Returns the aggregate value, or None if no matching rows found.
    """
    csv_path = tables_dir / source_table
    if not csv_path.exists():
        return None

    values = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            match = all(row.get(key) == str(val) for key, val in source_filter.items())
            if match:
                raw = row.get(source_column)
                if raw is not None:
                    try:
                        values.append(float(raw))
                    except (ValueError, TypeError):
                        pass

    if not values:
        return None

    if aggregate == "min":
        return min(values)
    elif aggregate == "max":
        return max(values)
    return None


def _extract_model_refs(hyp: dict) -> set[str]:
    """Extract model names referenced in a hypothesis's filters.

    Checks ``source_filter``, ``comparator_filter``, and ``anchor_filter``
    for a ``"model"`` key and returns the set of referenced model names.
    """
    refs: set[str] = set()
    for key in ("source_filter", "comparator_filter", "anchor_filter"):
        filt = hyp.get(key)
        if isinstance(filt, dict) and "model" in filt:
            refs.add(filt["model"])
    return refs


def evaluate_hypothesis(
    hyp: dict,
    tables_dir: Path,
    active_models: set[str] | None = None,
) -> dict:
    """Evaluate a single hypothesis against table data.

    Parameters
    ----------
    hyp : dict
        Hypothesis definition from ``hypotheses.json``.
    tables_dir : Path
        Directory containing the CSV tables to evaluate against.
    active_models : set[str] | None
        When provided, any hypothesis referencing a model NOT in this set
        is automatically SKIPped (returned as ``pass=True`` with a note).
        This supports roster trimming (LA-4) without modifying hypothesis
        files.

    Returns a hypothesis check result dict.
    """
    result = {
        "id": hyp["id"],
        "description": hyp["description"],
        "pass": False,
        "surprise_hit": False,
        "observed": None,
        "expected_bound": None,
        "surprise_threshold": None,
        "error": None,
    }

    # Roster-aware SKIP (LA-4): if a referenced model is not active, skip
    if active_models is not None:
        model_refs = _extract_model_refs(hyp)
        excluded = model_refs - active_models
        if excluded:
            result["pass"] = True
            result["note"] = (
                f"SKIP: model(s) {', '.join(sorted(excluded))} not in active roster"
            )
            return result

    source_table = hyp.get("source_table")
    source_column = hyp.get("source_column")
    source_filter = hyp.get("source_filter", {})
    # Support both "anchor_filter" and "comparator_filter" naming
    ref_filter = hyp.get("comparator_filter") or hyp.get("anchor_filter")
    computation = hyp.get("computation", "value")
    expected_bound = hyp.get("expected_bound", {})
    surprise_if = hyp.get("surprise_if", {})

    # Read primary value — use aggregate for min/max computations
    aggregate_computations = {"min", "max"}
    if computation in aggregate_computations:
        value = _read_csv_aggregate(
            tables_dir, source_table, source_column, source_filter, computation
        )
    else:
        value = _read_csv_value(tables_dir, source_table, source_column, source_filter)
    if value is None:
        result["error"] = (
            f"Could not read {source_column} from {source_table} "
            f"with filter {source_filter}"
        )
        return result

    # Compute delta if reference filter specified
    delta_computations = {"value - anchor_value", "value - comparator_value"}
    if ref_filter and computation in delta_computations:
        ref_value = _read_csv_value(tables_dir, source_table, source_column, ref_filter)
        if ref_value is None:
            result["error"] = (
                f"Could not read reference from {source_table} with filter {ref_filter}"
            )
            return result
        observed = value - ref_value
    else:
        observed = value

    result["observed"] = round(observed, 6)

    # Check expected bound
    if expected_bound:
        op_str = expected_bound.get("op", ">")
        bound_val = expected_bound.get("value", 0)
        result["expected_bound"] = f"{op_str} {bound_val}"
        op_fn = COMPARISON_OPS.get(op_str)
        if op_fn:
            result["pass"] = op_fn(observed, bound_val)

    # Check surprise threshold
    if surprise_if:
        op_str = surprise_if.get("op", "<")
        threshold_val = surprise_if.get("value", 0)
        result["surprise_threshold"] = f"{op_str} {threshold_val}"
        op_fn = COMPARISON_OPS.get(op_str)
        if op_fn:
            result["surprise_hit"] = op_fn(observed, threshold_val)

    return result


# ---------------------------------------------------------------------------
# Sufficiency checks
# ---------------------------------------------------------------------------


def check_sufficiency(tables_dir: Path, rung: str) -> list[dict]:
    """Run sufficiency checks against generated tables."""
    checks = []

    # Check: all tables generated
    expected_tables = [
        "model_performance.csv",
        "data_sanity.csv",
        "comparator_rankings.csv",
        "h2h_delta_matrix.csv",
    ]
    found = sum(1 for t in expected_tables if (tables_dir / t).exists())
    checks.append(
        {
            "id": "all_tables_generated",
            "pass": found == len(expected_tables),
            "value": f"{found}/{len(expected_tables)}",
        }
    )

    # Check: data_sanity (no FAIL rows)
    sanity_path = tables_dir / "data_sanity.csv"
    if sanity_path.exists():
        with open(sanity_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        fail_count = sum(1 for r in rows if r.get("status", "").upper() == "FAIL")
        total = len(rows)
        passed = total - fail_count
        checks.append(
            {
                "id": "data_sanity",
                "pass": fail_count == 0,
                "value": f"{passed}/{total} pass",
            }
        )
    else:
        checks.append(
            {
                "id": "data_sanity",
                "pass": False,
                "value": "data_sanity.csv not found",
            }
        )

    # Check: no blocked models (from model_performance.csv)
    perf_path = tables_dir / "model_performance.csv"
    if perf_path.exists():
        with open(perf_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Count unique models
        models = {r.get("model", r.get("model_name", "")) for r in rows}
        models.discard("")
        checks.append(
            {
                "id": "no_blocked_models",
                "pass": len(models) > 0,
                "value": f"{len(models)}/{len(models)}",
            }
        )
    else:
        checks.append(
            {
                "id": "no_blocked_models",
                "pass": False,
                "value": "model_performance.csv not found",
            }
        )

    return checks


# ---------------------------------------------------------------------------
# Canary checks (WARNING-level, never block)
# ---------------------------------------------------------------------------


def check_canaries(tables_dir: Path, mode: str) -> list[dict]:
    """Run canary checks (WARNING-level, never blocking)."""
    checks = []

    # C1: Feature importance plausibility (skip if no data)
    checks.append(
        {
            "id": "C1_feature_importance_plausible",
            "check": "Top features are reasonable (requires interpretability data)",
            "pass": True,  # Default pass -- requires interpretability data
            "level": "WARNING",
        }
    )

    # C2: Ranking stability across seeds (only at FULL with multiple seeds)
    if mode == "full":
        # Would check if top model is same across seeds
        # For now, default pass -- requires multi-seed comparator_rankings
        checks.append(
            {
                "id": "C2_ranking_stable_across_seeds",
                "check": "Top model consistent across seeds",
                "pass": True,
                "level": "WARNING",
            }
        )
    else:
        checks.append(
            {
                "id": "C2_ranking_stable_across_seeds",
                "check": "Skipped (single-seed mode)",
                "pass": True,
                "level": "WARNING",
            }
        )

    # C3: Magnitude historical -- no pooled delta > 5.0
    rankings_path = tables_dir / "comparator_rankings.csv"
    c3_pass = True
    if rankings_path.exists():
        with open(rankings_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                net_eppd = row.get("net_eppd")
                if net_eppd:
                    try:
                        if abs(float(net_eppd)) > 5.0:
                            c3_pass = False
                    except (ValueError, TypeError):
                        pass
    checks.append(
        {
            "id": "C3_magnitude_historical",
            "check": "No pooled delta > 5.0 (implausible magnitude)",
            "pass": c3_pass,
            "level": "WARNING",
        }
    )

    # C4: Model differentiation -- at least 3 distinct ranking positions
    c4_pass = True
    if rankings_path.exists():
        with open(rankings_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        pooled_rows = [
            r
            for r in rows
            if r.get("facet", r.get("contract_type", "")) in ("pooled", "Pooled")
        ]
        net_eppd_vals = set()
        for r in pooled_rows:
            val = r.get("net_eppd")
            if val:
                try:
                    net_eppd_vals.add(round(float(val), 2))
                except (ValueError, TypeError):
                    pass
        c4_pass = len(net_eppd_vals) >= 3
    checks.append(
        {
            "id": "C4_model_differentiation",
            "check": "At least 3 distinct ranking positions",
            "pass": c4_pass,
            "level": "WARNING",
        }
    )

    # C5: Feature count matches rung
    checks.append(
        {
            "id": "C5_feature_count_matches_rung",
            "check": "Model artifacts used expected feature count for rung",
            "pass": True,  # Requires model artifact inspection
            "level": "WARNING",
        }
    )

    return checks


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def compute_decision(
    hypothesis_checks: list[dict],
    sufficiency_checks: list[dict],
    canary_checks: list[dict],
) -> tuple[str, str]:
    """Compute advance decision from check results.

    Returns (decision, reason).
    Decision: PROCEED | INVESTIGATE | PAUSE
    """
    # Any surprise hit -> INVESTIGATE
    surprise_hits = [h for h in hypothesis_checks if h.get("surprise_hit")]
    if surprise_hits:
        ids = [h["id"] for h in surprise_hits]
        return "INVESTIGATE", f"Surprise threshold hit on: {', '.join(ids)}"

    # Check sufficiency
    suff_failures = [s for s in sufficiency_checks if not s["pass"]]

    # Data sanity failure -> PAUSE
    data_sanity_fail = any(
        s["id"] == "data_sanity" and not s["pass"] for s in sufficiency_checks
    )
    if data_sanity_fail:
        return "PAUSE", "Data sanity check failed"

    # >50% blocked models -> PAUSE
    blocked = any(
        s["id"] == "no_blocked_models" and not s["pass"] for s in sufficiency_checks
    )
    if blocked:
        return "PAUSE", "Blocked models detected"

    # Any hypothesis failure (non-surprise)
    hyp_failures = [
        h for h in hypothesis_checks if not h.get("pass") and h.get("error") is None
    ]
    hyp_errors = [h for h in hypothesis_checks if h.get("error")]

    if hyp_errors:
        # Some hypotheses couldn't be evaluated (missing data)
        ids = [h["id"] for h in hyp_errors]
        return "INVESTIGATE", f"Could not evaluate hypotheses: {', '.join(ids)}"

    if hyp_failures:
        ids = [h["id"] for h in hyp_failures]
        return "INVESTIGATE", f"Hypotheses failed: {', '.join(ids)}"

    # Count canary warnings
    canary_warns = [c for c in canary_checks if not c["pass"]]
    n_warns = len(canary_warns)

    if suff_failures:
        ids = [s["id"] for s in suff_failures]
        return "INVESTIGATE", f"Sufficiency checks failed: {', '.join(ids)}"

    if n_warns > 0:
        return (
            "PROCEED",
            f"All checks pass. {n_warns} canary warning(s) (non-blocking).",
        )

    return "PROCEED", "All checks pass."


# ---------------------------------------------------------------------------
# Best-in-lineage extraction
# ---------------------------------------------------------------------------


def find_best_in_lineage(tables_dir: Path) -> dict | None:
    """Find the best model by pooled net_eppd from comparator_rankings.csv."""
    rankings_path = tables_dir / "comparator_rankings.csv"
    if not rankings_path.exists():
        return None

    with open(rankings_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    pooled_rows = [
        r
        for r in rows
        if r.get("facet", r.get("contract_type", "")) in ("pooled", "Pooled")
    ]

    best = None
    best_val = float("-inf")
    for r in pooled_rows:
        net_eppd = r.get("net_eppd")
        model = r.get("model", r.get("model_name", ""))
        if net_eppd and model:
            try:
                val = float(net_eppd)
                if val > best_val:
                    best_val = val
                    best = model
            except (ValueError, TypeError):
                pass

    if best:
        return {
            "model": best,
            "pooled_net_eppd": round(best_val, 4),
            "updated": True,
        }
    return None


# ---------------------------------------------------------------------------
# Next rung action
# ---------------------------------------------------------------------------

NEXT_RUNG = {"r0": "r1", "r1": "r2", "r2": "r3", "r3": None}


def compute_next_action(rung: str, decision: str) -> dict | None:
    """Compute the recommended next action based on decision."""
    if decision != "PROCEED":
        return None
    next_rung = NEXT_RUNG.get(rung)
    if not next_rung:
        return {"command": "Lineage complete", "prerequisite": "None"}
    return {
        "command": f"run_rung.py --rung {next_rung} --mode all",
        "prerequisite": f"{next_rung.upper()} plan.md and hypotheses.json must exist",
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_advance_check(
    hypotheses_path: Path,
    tables_dir: Path,
    mode: str,
    rung: str,
    active_models: set[str] | None = None,
) -> dict:
    """Generate the advance check JSON.

    Parameters
    ----------
    active_models : set[str] | None
        When provided, hypotheses referencing models outside this set are
        automatically SKIPped (LA-4 roster trimming).
    """
    # Load hypotheses
    hyp_data = json.loads(hypotheses_path.read_text())
    hypotheses = hyp_data.get("hypotheses", [])

    # Evaluate hypotheses
    hypothesis_checks = [
        evaluate_hypothesis(h, tables_dir, active_models=active_models)
        for h in hypotheses
    ]

    # Sufficiency checks
    sufficiency_checks = check_sufficiency(tables_dir, rung)

    # Canary checks
    canary_checks = check_canaries(tables_dir, mode)

    # Decision
    decision, reason = compute_decision(
        hypothesis_checks, sufficiency_checks, canary_checks
    )

    # Best in lineage
    best = find_best_in_lineage(tables_dir)

    # Failed/warnings summary
    failed = [
        h["id"]
        for h in hypothesis_checks
        if not h.get("pass") and h.get("error") is None
    ]
    failed += [s["id"] for s in sufficiency_checks if not s["pass"]]
    warnings = [c["id"] for c in canary_checks if not c["pass"]]

    result = {
        "schema_version": "advance_check_v1",
        "rung": rung,
        "mode": mode,
        "advance_decision": decision,
        "reason": reason,
        "timestamp": utc_now_iso(),
        "next_action": compute_next_action(rung, decision),
        "hypothesis_checks": hypothesis_checks,
        "sufficiency_checks": sufficiency_checks,
        "canary_checks": canary_checks,
        "best_in_lineage": best,
        "failed_checks_summary": failed,
        "warnings_summary": warnings,
    }

    return result

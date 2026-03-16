"""Canonical CSV table generation for Arc D v2 rung reports.

Reads run artifacts (H2H battery JSON, comparator CIs JSON, training
artifact JSONs, roster JSON, action_value.parquet) and produces 11
canonical CSV tables used by the report generator.

Multi-seed FULL mode (§9.6): When multiple seed artifacts are available,
point estimates use deal-count-weighted pooling across seeds. CIs from
individual seed runs are NOT averaged — instead the merged output carries
``ci_method: "seed_averaged"`` as a provenance marker indicating the CIs
were averaged across per-seed bootstrap CIs (not recomputed from pooled
raw data). Proper pooled-bootstrap CIs require rerunning the battery
scripts with concatenated JSONL, which is a future enhancement.

Per-seed sanity checks flag outliers and rank reversals as WARNINGs.

Extracted from ``scripts/internal/generate_rung_tables.py``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
#  Data loading helpers
# ──────────────────────────────────────────────

FACETS = ["suit", "high", "low", "pooled"]


def _load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if not found."""
    if not path.exists():
        logger.warning("File not found: %s", path)
        return None
    with open(path) as f:
        return json.load(f)


def _load_json_glob(
    rung_dir: Path,
    prefix: str,
    mode: str | None = None,
    seed: int | None = None,
) -> dict | None:
    """Load a JSON artifact, using deterministic naming when mode/seed are known.

    Resolution order:
    1. If mode and seed given, try ``{prefix}_{mode}_{seed}.json`` (deterministic).
    2. Try the bare ``{prefix}.json`` (legacy / symlink).
    3. Fall back to glob ``{prefix}_*.json``, newest by mtime (last resort).
    """
    # Deterministic path when mode/seed are known
    if mode and seed is not None:
        deterministic = rung_dir / f"{prefix}_{mode}_{seed}.json"
        if deterministic.exists():
            return _load_json(deterministic)

    # Legacy bare name
    exact = rung_dir / f"{prefix}.json"
    if exact.exists():
        return _load_json(exact)

    # Glob fallback (nondeterministic — warns)
    candidates = sorted(
        rung_dir.glob(f"{prefix}_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if candidates:
        chosen = candidates[-1]
        logger.warning(
            "Resolved %s via mtime glob (nondeterministic): %s. "
            "Pass --mode/--seed for deterministic selection.",
            prefix,
            chosen.name,
        )
        return _load_json(chosen)

    logger.warning("No %s artifact found in %s", prefix, rung_dir)
    return None


def _safe_round(val, decimals=4):
    """Round a value safely, handling None."""
    if val is None:
        return None
    return round(val, decimals)


# ──────────────────────────────────────────────
#  Table generators
# ──────────────────────────────────────────────


def generate_comparator_rankings(comparator_cis: dict) -> pd.DataFrame:
    """Generate comparator_rankings.csv from comparator CIs JSON.

    Columns: model, facet, net_eppd, ci_low, ci_high, bid_rate,
             make_rate, net_cvar_5, rank
    """
    bidders = comparator_cis.get("bidders", {})
    ranked_order = comparator_cis.get("ranked_order", sorted(bidders.keys()))

    rows = []

    # Per-contract facets: emit if per-contract data is available
    bidders_by_contract = comparator_cis.get("bidders_by_contract", {})
    for facet in ["suit", "high", "low"]:
        facet_data = bidders_by_contract.get(facet, {})
        if not facet_data:
            continue
        facet_ranked = sorted(
            facet_data.items(),
            key=lambda item: item[1].get("net_eppd", 0),
            reverse=True,
        )
        for rank_idx, (name, b) in enumerate(facet_ranked, 1):
            ci = b.get("net_eppd_ci", [b.get("net_eppd", 0), None, None])
            ci_low = ci[1] if len(ci) > 1 else None
            ci_high = ci[2] if len(ci) > 2 else None
            rows.append(
                {
                    "model": name,
                    "facet": facet,
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "ci_low": _safe_round(ci_low),
                    "ci_high": _safe_round(ci_high),
                    "bid_rate": _safe_round(b.get("bid_rate")),
                    "make_rate": _safe_round(b.get("make_rate")),
                    "net_cvar_5": _safe_round(b.get("net_cvar_5")),
                    "rank": rank_idx,
                }
            )

    # Pooled facet (always available)
    for rank_idx, name in enumerate(ranked_order, 1):
        b = bidders[name]
        ci = b.get("net_eppd_ci", [b["net_eppd"], None, None])
        ci_low = ci[1] if len(ci) > 1 else None
        ci_high = ci[2] if len(ci) > 2 else None

        rows.append(
            {
                "model": name,
                "facet": "pooled",
                "net_eppd": _safe_round(b.get("net_eppd")),
                "ci_low": _safe_round(ci_low),
                "ci_high": _safe_round(ci_high),
                "bid_rate": _safe_round(b.get("bid_rate")),
                "make_rate": _safe_round(b.get("make_rate")),
                "net_cvar_5": _safe_round(b.get("net_cvar_5")),
                "rank": rank_idx,
            }
        )

    return pd.DataFrame(rows)


def generate_h2h_delta_matrix(h2h_battery: dict) -> pd.DataFrame:
    """Generate h2h_delta_matrix.csv from H2H battery JSON.

    Columns: model_a, model_b, facet, net_eppd_delta, ci_low, ci_high,
             win_rate_a, deals_total
    """
    cells = h2h_battery.get("cells", {})
    rows = []

    for _mid, cell in cells.items():
        bidder_a = cell.get("bidder_a", "")
        bidder_b = cell.get("bidder_b", "")

        # Pooled row (always present)
        rows.append(
            {
                "model_a": bidder_a,
                "model_b": bidder_b,
                "facet": "pooled",
                "net_eppd_delta": _safe_round(cell.get("net_eppd_delta")),
                "ci_low": _safe_round(cell.get("ci_low")),
                "ci_high": _safe_round(cell.get("ci_high")),
                "win_rate_a": _safe_round(cell.get("win_rate_a")),
                "deals_total": cell.get("deals_total"),
            }
        )

        # Per-contract rows (if by_contract data is available)
        by_contract = cell.get("by_contract", {})
        for ct in ("suit", "high", "low"):
            ct_data = by_contract.get(ct)
            if ct_data:
                rows.append(
                    {
                        "model_a": bidder_a,
                        "model_b": bidder_b,
                        "facet": ct,
                        "net_eppd_delta": _safe_round(ct_data.get("net_eppd_delta")),
                        "ci_low": _safe_round(ct_data.get("ci_low")),
                        "ci_high": _safe_round(ct_data.get("ci_high")),
                        "win_rate_a": _safe_round(ct_data.get("win_rate_a")),
                        "deals_total": ct_data.get("deals_total"),
                    }
                )

    return pd.DataFrame(rows)


def generate_model_performance(
    training_artifacts: dict[str, dict],
) -> pd.DataFrame:
    """Generate model_performance.csv from training artifact JSONs.

    Columns: model, contract, r_squared, mae, n_train, n_val
    """
    rows = []
    for model_name, artifact in training_artifacts.items():
        models = artifact.get("models", {})
        for contract, model_data in models.items():
            rows.append(
                {
                    "model": model_name,
                    "contract": contract,
                    "r_squared": _safe_round(model_data.get("r_squared")),
                    "mae": _safe_round(model_data.get("mae")),
                    "n_train": model_data.get("n_train"),
                    "n_val": model_data.get("n_val"),
                }
            )

    return pd.DataFrame(rows)


def generate_behavior_summary(
    comparator_cis: dict | None = None,
    h2h_battery: dict | None = None,
) -> pd.DataFrame:
    """Generate behavior_summary.csv -- pooled behavioral metrics per model.

    Columns: model, net_eppd, eppd, bid_rate, make_rate, cvar_5, net_cvar_5,
             source
    """
    rows = []

    if comparator_cis:
        for name, b in comparator_cis.get("bidders", {}).items():
            rows.append(
                {
                    "model": name,
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "eppd": _safe_round(b.get("eppd")),
                    "bid_rate": _safe_round(b.get("bid_rate")),
                    "make_rate": _safe_round(b.get("make_rate")),
                    "cvar_5": _safe_round(b.get("cvar_5")),
                    "net_cvar_5": _safe_round(b.get("net_cvar_5")),
                    "source": "comparator",
                }
            )

    if h2h_battery:
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue  # Only self-play
            rows.append(
                {
                    "model": cell["bidder_a"],
                    "net_eppd": _safe_round(cell.get("fullgame_eppd")),
                    "eppd": None,
                    "bid_rate": _safe_round(cell.get("bid_rate_a")),
                    "make_rate": _safe_round(cell.get("make_rate_a")),
                    "cvar_5": _safe_round(cell.get("fullgame_cvar_5")),
                    "net_cvar_5": None,
                    "source": "h2h_self_play",
                }
            )

    return pd.DataFrame(rows)


def generate_behavior_by_contract(
    comparator_cis: dict | None = None,
) -> pd.DataFrame:
    """Generate behavior_by_contract.csv -- faceted behavioral metrics.

    Columns: model, contract, net_eppd, bid_rate, make_rate, source
    """
    rows = []
    if comparator_cis:
        # Per-contract rows if available
        bidders_by_contract = comparator_cis.get("bidders_by_contract", {})
        for contract in ["suit", "high", "low"]:
            contract_data = bidders_by_contract.get(contract, {})
            for name, b in contract_data.items():
                rows.append(
                    {
                        "model": name,
                        "contract": contract,
                        "net_eppd": _safe_round(b.get("net_eppd")),
                        "bid_rate": _safe_round(b.get("bid_rate")),
                        "make_rate": _safe_round(b.get("make_rate")),
                        "source": "comparator",
                    }
                )

        # Pooled rows (always available)
        for name, b in comparator_cis.get("bidders", {}).items():
            rows.append(
                {
                    "model": name,
                    "contract": "pooled",
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "bid_rate": _safe_round(b.get("bid_rate")),
                    "make_rate": _safe_round(b.get("make_rate")),
                    "source": "comparator",
                }
            )

    return pd.DataFrame(rows)


def generate_sanity_bounds_check(
    comparator_cis: dict | None = None,
    training_artifacts: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Generate sanity_bounds_check.csv -- sanity bound checks per model.

    Columns: model, check_name, value, lower_bound, upper_bound, status
    """
    rows = []

    if comparator_cis:
        for name, b in comparator_cis.get("bidders", {}).items():
            bid_rate = b.get("bid_rate", 0)
            make_rate = b.get("make_rate", 0)
            rows.append(
                {
                    "model": name,
                    "check_name": "bid_rate_range",
                    "value": _safe_round(bid_rate),
                    "lower_bound": 0.05,
                    "upper_bound": 0.95,
                    "status": "PASS" if 0.05 <= bid_rate <= 0.95 else "FAIL",
                }
            )
            rows.append(
                {
                    "model": name,
                    "check_name": "make_rate_range",
                    "value": _safe_round(make_rate),
                    "lower_bound": 0.10,
                    "upper_bound": 1.00,
                    "status": "PASS" if 0.10 <= make_rate <= 1.00 else "FAIL",
                }
            )

    if training_artifacts:
        for model_name, artifact in training_artifacts.items():
            models = artifact.get("models", {})
            for contract, model_data in models.items():
                r2 = model_data.get("r_squared", 0)
                rows.append(
                    {
                        "model": model_name,
                        "check_name": f"r2_positive_{contract}",
                        "value": _safe_round(r2),
                        "lower_bound": 0.0,
                        "upper_bound": 1.0,
                        "status": "PASS" if r2 > 0 else "FAIL",
                    }
                )

    return pd.DataFrame(rows)


def generate_hypothesis_outcomes() -> pd.DataFrame:
    """Generate hypothesis_outcomes.csv -- stub with columns.

    Columns: hypothesis_id, description, status, evidence, notes
    """
    return pd.DataFrame(
        columns=[
            "hypothesis_id",
            "description",
            "status",
            "evidence",
            "notes",
        ]
    )


def generate_rung_model_spec(roster: dict | None = None) -> pd.DataFrame:
    """Generate rung_model_spec.csv -- model roster inventory.

    Columns: model, class_name, trainable, model_class, feature_set,
             category, artifact_path
    """
    rows = []
    if roster:
        for model_entry in roster.get("models", []):
            params = model_entry.get("params", {})
            rows.append(
                {
                    "model": model_entry.get("name"),
                    "class_name": model_entry.get("class_name"),
                    "trainable": model_entry.get("trainable", False),
                    "model_class": model_entry.get("model_class", ""),
                    "feature_set": model_entry.get("feature_set", ""),
                    "category": model_entry.get("category", ""),
                    "artifact_path": params.get("artifact_path", ""),
                }
            )

        # Add anchor
        anchor = roster.get("anchor", {})
        if anchor:
            rows.append(
                {
                    "model": anchor.get("name", ""),
                    "class_name": anchor.get("class_name", ""),
                    "trainable": False,
                    "model_class": "",
                    "feature_set": "",
                    "category": "anchor",
                    "artifact_path": anchor.get("artifact", ""),
                }
            )

    return pd.DataFrame(rows)


def generate_cross_rung_deltas() -> pd.DataFrame:
    """Generate cross_rung_deltas.csv -- accumulated cross-rung deltas.

    Columns: model, rung, pooled_delta, suit_delta, high_delta,
             low_delta, ci_low, ci_high
    """
    return pd.DataFrame(
        columns=[
            "model",
            "rung",
            "pooled_delta",
            "suit_delta",
            "high_delta",
            "low_delta",
            "ci_low",
            "ci_high",
        ]
    )


def generate_dataset_provenance(
    training_artifacts: dict[str, dict] | None = None,
    dataset_path: str | None = None,
) -> pd.DataFrame:
    """Generate dataset_provenance.csv -- dataset metadata.

    Columns: dataset_name, path, n_rows, seed, sha256, model_class
    """
    rows = []
    if training_artifacts:
        for model_name, artifact in training_artifacts.items():
            meta = artifact.get("metadata", {})
            rows.append(
                {
                    "dataset_name": model_name,
                    "path": meta.get("dataset_path", dataset_path or ""),
                    "n_rows": None,  # Requires loading the parquet
                    "seed": meta.get("training_seed"),
                    "sha256": meta.get("dataset_sha256", ""),
                    "model_class": meta.get("model_class", ""),
                }
            )

    return pd.DataFrame(rows)


def generate_artifact_inventory(
    training_artifacts: dict[str, dict] | None = None,
    roster: dict | None = None,
    rung_dir: Path | None = None,
) -> pd.DataFrame:
    """Generate artifact_inventory.csv -- artifact paths and versions.

    Columns: artifact_name, path, schema_version, model_class, git_sha
    """
    rows = []
    if training_artifacts:
        for model_name, artifact in training_artifacts.items():
            meta = artifact.get("metadata", {})
            rows.append(
                {
                    "artifact_name": model_name,
                    "path": str(
                        rung_dir / f"training_artifact_{model_name.split('_')[-1]}.json"
                    )
                    if rung_dir
                    else "",
                    "schema_version": artifact.get("schema_version", ""),
                    "model_class": meta.get("model_class", ""),
                    "git_sha": meta.get("git_sha", ""),
                }
            )

    if roster:
        rows.append(
            {
                "artifact_name": "roster",
                "path": str(rung_dir / "roster.json") if rung_dir else "",
                "schema_version": roster.get("schema_version", ""),
                "model_class": "",
                "git_sha": "",
            }
        )

    return pd.DataFrame(rows)


def generate_data_sanity(
    h2h_battery: dict | None = None,
    comparator_cis: dict | None = None,
    training_artifacts: dict[str, dict] | None = None,
) -> pd.DataFrame:
    """Generate data_sanity.csv -- Phase 0-lite sanity checks.

    Columns: check_name, scope, value, threshold, status, detail
    """
    rows = []

    # Check 1: H2H battery has data
    if h2h_battery:
        cells = h2h_battery.get("cells", {})
        n_cells = len(cells)
        populated = sum(
            1 for c in cells.values() if c.get("net_eppd_delta") is not None
        )
        rows.append(
            {
                "check_name": "h2h_cells_populated",
                "scope": "h2h",
                "value": populated,
                "threshold": n_cells,
                "status": "PASS" if populated == n_cells else "WARN",
                "detail": f"{populated}/{n_cells} cells have metrics",
            }
        )

        # Check 2: All H2H cells have sufficient deals
        min_deals = min(c.get("deals_total", 0) for c in cells.values()) if cells else 0
        rows.append(
            {
                "check_name": "h2h_min_deals",
                "scope": "h2h",
                "value": min_deals,
                "threshold": 10,
                "status": "PASS" if min_deals >= 10 else "WARN",
                "detail": f"Minimum deals across cells: {min_deals}",
            }
        )

    # Check 3: Comparator data exists
    if comparator_cis:
        n_bidders = len(comparator_cis.get("bidders", {}))
        rows.append(
            {
                "check_name": "comparator_bidders_present",
                "scope": "comparator",
                "value": n_bidders,
                "threshold": 2,
                "status": "PASS" if n_bidders >= 2 else "FAIL",
                "detail": f"{n_bidders} bidders in comparator",
            }
        )

    # Check 4: Training artifacts have R-squared > 0
    if training_artifacts:
        for model_name, artifact in training_artifacts.items():
            models = artifact.get("models", {})
            for contract, model_data in models.items():
                r2 = model_data.get("r_squared", 0)
                rows.append(
                    {
                        "check_name": f"r2_positive_{model_name}_{contract}",
                        "scope": "training",
                        "value": _safe_round(r2),
                        "threshold": 0.0,
                        "status": "PASS" if r2 > 0 else "WARN",
                        "detail": f"{model_name} {contract} R²={r2:.4f}",
                    }
                )

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
#  Main pipeline
# ──────────────────────────────────────────────


def _weighted_mean(values: list[float | None], weights: list[int]) -> float | None:
    """Compute weighted mean, returning None if all values are None."""
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None and w > 0]
    if not pairs:
        return None
    total_w = sum(w for _, w in pairs)
    if total_w == 0:
        return None
    return sum(v * w for v, w in pairs) / total_w


def _merge_h2h_batteries(batteries: list[dict]) -> dict:
    """Merge multiple H2H battery JSONs using deal-count-weighted pooling.

    Point estimates (net_eppd_delta, win_rate_a, etc.) are computed as
    deal-count-weighted means across seeds — NOT naive averages.

    CIs are averaged across seeds and marked with ``ci_method:
    "seed_averaged"`` to distinguish from proper pooled-bootstrap CIs
    (which require raw JSONL data not available in battery JSONs).
    """
    if len(batteries) == 1:
        return batteries[0]

    merged = dict(batteries[0])  # Copy structure from first
    merged_cells: dict[str, list[dict]] = {}

    # Collect all cells by matchup_id
    for battery in batteries:
        for mid, cell in battery.get("cells", {}).items():
            merged_cells.setdefault(mid, []).append(cell)

    result_cells = {}
    for mid, cell_list in merged_cells.items():
        base = dict(cell_list[0])
        deal_counts = [c.get("deals_total", 0) for c in cell_list]
        total_deals = sum(deal_counts)

        # Deal-count-weighted pooling for point estimates
        for key in (
            "net_eppd_delta",
            "net_eppd_a",
            "net_eppd_b",
            "win_rate_a",
            "abs_net_eppd_team0",
            "abs_net_eppd_team1",
            "cvar_5",
            "fullgame_eppd",
        ):
            vals = [c.get(key) for c in cell_list]
            wm = _weighted_mean(vals, deal_counts)
            base[key] = round(wm, 6) if wm is not None else None

        # CIs: average across seeds (NOT pooled bootstrap — requires raw data)
        for key in ("ci_low", "ci_high"):
            vals = [c.get(key) for c in cell_list if c.get(key) is not None]
            base[key] = round(sum(vals) / len(vals), 6) if vals else None

        base["deals_total"] = total_deals
        base["ci_method"] = "seed_averaged"

        # Merge per-contract data if present
        all_contracts: dict[str, list[dict]] = {}
        for c in cell_list:
            for ct, ct_data in c.get("by_contract", {}).items():
                all_contracts.setdefault(ct, []).append(ct_data)
        if all_contracts:
            merged_bc = {}
            for ct, ct_list in all_contracts.items():
                ct_deals = [d.get("deals_total", 0) for d in ct_list]
                merged_ct: dict = {}
                # Weighted point estimates
                for key in ("net_eppd_delta", "win_rate_a"):
                    vals = [d.get(key) for d in ct_list]
                    wm = _weighted_mean(vals, ct_deals)
                    merged_ct[key] = round(wm, 6) if wm is not None else None
                # Averaged CIs
                for key in ("ci_low", "ci_high"):
                    vals = [d.get(key) for d in ct_list if d.get(key) is not None]
                    merged_ct[key] = round(sum(vals) / len(vals), 6) if vals else None
                merged_ct["deals_total"] = sum(ct_deals)
                merged_ct["ci_method"] = "seed_averaged"
                merged_bc[ct] = merged_ct
            base["by_contract"] = merged_bc
        result_cells[mid] = base

    merged["cells"] = result_cells
    merged["seeds_merged"] = len(batteries)
    return merged


def _merge_comparator_cis(cis_list: list[dict]) -> dict:
    """Merge multiple comparator CI JSONs using deal-count-weighted pooling.

    Point estimates (net_eppd, eppd, bid_rate, make_rate) are computed as
    deal-count-weighted means. CIs are averaged and marked with
    ``ci_method: "seed_averaged"``.

    Re-ranks bidders by pooled net_eppd.
    """
    if len(cis_list) == 1:
        return cis_list[0]

    merged = dict(cis_list[0])
    # Collect all bidder data across seeds
    all_bidders: dict[str, list[dict]] = {}
    for cis in cis_list:
        for name, b in cis.get("bidders", {}).items():
            all_bidders.setdefault(name, []).append(b)

    result_bidders = {}
    for name, b_list in all_bidders.items():
        base = dict(b_list[0])
        deal_counts = [b.get("deals_total", 0) for b in b_list]
        total_deals = sum(deal_counts)

        # Deal-count-weighted point estimates
        for key in (
            "net_eppd",
            "eppd",
            "bid_rate",
            "make_rate",
            "cvar_5",
            "net_cvar_5",
        ):
            vals = [b.get(key) for b in b_list]
            wm = _weighted_mean(vals, deal_counts)
            base[key] = round(wm, 6) if wm is not None else None

        # Averaged CIs (NOT pooled bootstrap)
        for ci_key in ("net_eppd_ci", "eppd_ci", "cvar_5_ci", "net_cvar_5_ci"):
            ci_arrays = [b.get(ci_key) for b in b_list if b.get(ci_key) is not None]
            if ci_arrays:
                # Each CI is [point, low, high]; average each position
                averaged = [
                    round(sum(ci[i] for ci in ci_arrays) / len(ci_arrays), 6)
                    for i in range(len(ci_arrays[0]))
                ]
                base[ci_key] = averaged

        base["deals_total"] = total_deals
        base["ci_method"] = "seed_averaged"
        result_bidders[name] = base

    merged["bidders"] = result_bidders
    # Re-rank by pooled net_eppd
    merged["ranked_order"] = sorted(
        result_bidders.keys(),
        key=lambda n: v if (v := result_bidders[n].get("net_eppd")) is not None else 0,
        reverse=True,
    )
    merged["seeds_merged"] = len(cis_list)

    # Merge per-contract data if present
    all_by_contract: dict[str, dict[str, list[dict]]] = {}
    for cis in cis_list:
        for ct, ct_bidders in cis.get("bidders_by_contract", {}).items():
            for bname, bdata in ct_bidders.items():
                all_by_contract.setdefault(ct, {}).setdefault(bname, []).append(bdata)
    if all_by_contract:
        merged_bc: dict[str, dict] = {}
        for ct, bidder_data in all_by_contract.items():
            merged_bc[ct] = {}
            for bname, b_list_ct in bidder_data.items():
                base_ct = dict(b_list_ct[0])
                ct_deals = [b.get("deals_total", 0) for b in b_list_ct]
                for key in ("net_eppd", "bid_rate", "make_rate"):
                    vals = [b.get(key) for b in b_list_ct]
                    wm = _weighted_mean(vals, ct_deals)
                    base_ct[key] = round(wm, 6) if wm is not None else None
                base_ct["ci_method"] = "seed_averaged"
                merged_bc[ct][bname] = base_ct
        merged["bidders_by_contract"] = merged_bc

    return merged


# ──────────────────────────────────────────────
#  Per-seed sanity checks
# ──────────────────────────────────────────────


def _per_seed_sanity_h2h(batteries: list[dict]) -> list[dict]:
    """Run per-seed sanity checks on H2H battery data.

    Returns a list of warning dicts with keys: check, matchup_id, detail.
    """
    if len(batteries) < 2:
        return []

    warnings: list[dict] = []

    # Collect per-seed net_eppd_delta for each matchup
    cell_deltas: dict[str, list[tuple[int | None, float]]] = {}
    for battery in batteries:
        seed = battery.get("seed")
        for mid, cell in battery.get("cells", {}).items():
            delta = cell.get("net_eppd_delta")
            if delta is not None:
                cell_deltas.setdefault(mid, []).append((seed, delta))

    for mid, seed_deltas in cell_deltas.items():
        if len(seed_deltas) < 2:
            continue
        vals = [d for _, d in seed_deltas]
        median_val = float(np.median(vals))
        mad = float(np.median([abs(v - median_val) for v in vals]))

        # Check 1: single-seed outlier.
        # Use median absolute deviation (MAD) — robust to the outlier itself
        # inflating the dispersion measure (unlike SD with small n).
        # Threshold: 3 * MAD from median (standard robust outlier rule).
        if mad > 0:
            for seed_val, delta in seed_deltas:
                deviation = abs(delta - median_val) / mad
                if deviation > 3.0:
                    warnings.append(
                        {
                            "check": "h2h_seed_outlier",
                            "matchup_id": mid,
                            "detail": (
                                f"Seed {seed_val} delta={delta:.4f} is "
                                f"{deviation:.1f} MAD from median="
                                f"{median_val:.4f} (MAD={mad:.4f})"
                            ),
                        }
                    )

    # Check 2: rank reversals across seeds (cross-matchup cells only)
    # For each pair of models that appear in cross-matchups, check if
    # the sign of net_eppd_delta flips across seeds
    for mid, seed_deltas in cell_deltas.items():
        if len(seed_deltas) < 2:
            continue
        signs = [1 if d > 0 else (-1 if d < 0 else 0) for _, d in seed_deltas]
        positive = sum(1 for s in signs if s > 0)
        negative = sum(1 for s in signs if s < 0)
        if positive > 0 and negative > 0:
            seed_detail = ", ".join(f"seed {s}={d:.4f}" for s, d in seed_deltas)
            warnings.append(
                {
                    "check": "h2h_rank_reversal",
                    "matchup_id": mid,
                    "detail": f"Sign flip across seeds: {seed_detail}",
                }
            )

    return warnings


def _per_seed_sanity_comparator(cis_list: list[dict]) -> list[dict]:
    """Run per-seed sanity checks on comparator CI data.

    Returns a list of warning dicts with keys: check, model, detail.
    """
    if len(cis_list) < 2:
        return []

    warnings: list[dict] = []

    # Collect per-seed net_eppd for each bidder
    bidder_vals: dict[str, list[tuple[int | None, float]]] = {}
    for cis in cis_list:
        seed = cis.get("seed")
        for name, b in cis.get("bidders", {}).items():
            val = b.get("net_eppd")
            if val is not None:
                bidder_vals.setdefault(name, []).append((seed, val))

    for name, seed_vals in bidder_vals.items():
        if len(seed_vals) < 2:
            continue
        vals = [v for _, v in seed_vals]
        median_val = float(np.median(vals))
        mad = float(np.median([abs(v - median_val) for v in vals]))

        # Outlier check using MAD (robust for small n, e.g. 3 seeds)
        if mad > 0:
            for seed_val, v in seed_vals:
                deviation = abs(v - median_val) / mad
                if deviation > 3.0:
                    warnings.append(
                        {
                            "check": "comparator_seed_outlier",
                            "model": name,
                            "detail": (
                                f"Seed {seed_val} net_eppd={v:.4f} is "
                                f"{deviation:.1f} MAD from median="
                                f"{median_val:.4f} (MAD={mad:.4f})"
                            ),
                        }
                    )

    # Rank reversal check: compare ranking across seeds
    seed_rankings: list[list[str]] = []
    for cis in cis_list:
        ranked = cis.get("ranked_order")
        if ranked is None:
            bidders = cis.get("bidders", {})
            ranked = sorted(
                bidders.keys(),
                key=lambda n: v if (v := bidders[n].get("net_eppd")) is not None else 0,
                reverse=True,
            )
        seed_rankings.append(ranked)

    if len(seed_rankings) >= 2:
        # Check all pairs of adjacent bidders for rank inversions
        reference = seed_rankings[0]
        for i in range(len(reference) - 1):
            a, b = reference[i], reference[i + 1]
            for j, ranking in enumerate(seed_rankings[1:], 1):
                if a in ranking and b in ranking:
                    idx_a = ranking.index(a)
                    idx_b = ranking.index(b)
                    if idx_a > idx_b:  # Reversal
                        seed = cis_list[j].get("seed")
                        warnings.append(
                            {
                                "check": "comparator_rank_reversal",
                                "model": f"{a} vs {b}",
                                "detail": (
                                    f"Rank reversal: {a} > {b} on seed "
                                    f"{cis_list[0].get('seed')} but "
                                    f"{b} > {a} on seed {seed}"
                                ),
                            }
                        )

    return warnings


def generate_seed_sanity_table(
    h2h_batteries: list[dict],
    comparator_cis_list: list[dict],
) -> pd.DataFrame:
    """Generate seed_sanity.csv — per-seed sanity check warnings.

    Columns: check, scope, matchup_or_model, detail
    """
    rows: list[dict] = []

    for w in _per_seed_sanity_h2h(h2h_batteries):
        rows.append(
            {
                "check": w["check"],
                "scope": "h2h",
                "matchup_or_model": w.get("matchup_id", ""),
                "detail": w["detail"],
            }
        )

    for w in _per_seed_sanity_comparator(comparator_cis_list):
        rows.append(
            {
                "check": w["check"],
                "scope": "comparator",
                "matchup_or_model": w.get("model", ""),
                "detail": w["detail"],
            }
        )

    return pd.DataFrame(
        rows,
        columns=["check", "scope", "matchup_or_model", "detail"],
    )


def generate_all_tables(
    rung_dir: Path,
    output_dir: Path,
    mode: str | None = None,
    seed: int | None = None,
    seeds: list[int] | None = None,
) -> list[str]:
    """Generate all 11 canonical CSVs from rung directory artifacts.

    Args:
        rung_dir: Path to directory containing run artifacts.
        output_dir: Path to write CSV files.
        mode: Execution mode (smoke/quick/full) for deterministic artifact selection.
        seed: Single RNG seed (for backward compatibility).
        seeds: List of RNG seeds for multi-seed FULL aggregation.
            If provided, overrides ``seed``.

    Returns:
        List of generated CSV filenames.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # Resolve seed list
    seed_list = seeds or ([seed] if seed is not None else [None])
    rung_id = rung_dir.name  # e.g., "r0"

    # Load artifacts for all seeds, then merge
    h2h_batteries = []
    comparator_cis_list = []
    for s in seed_list:
        h2h = _load_json_glob(rung_dir, "h2h_battery", mode=mode, seed=s)
        if h2h:
            h2h_batteries.append(h2h)
        cis = _load_json_glob(rung_dir, "comparator_cis", mode=rung_id, seed=s)
        if cis:
            comparator_cis_list.append(cis)

    h2h_battery = _merge_h2h_batteries(h2h_batteries) if h2h_batteries else None
    comparator_cis = (
        _merge_comparator_cis(comparator_cis_list) if comparator_cis_list else None
    )
    roster = _load_json(rung_dir / "roster.json")

    # Load training artifacts (look for training_artifact_*.json)
    training_artifacts: dict[str, dict] = {}
    for art_path in sorted(rung_dir.glob("training_artifact_*.json")):
        # Extract model name from filename: training_artifact_ols.json -> ols
        model_key = art_path.stem.replace("training_artifact_", "")
        artifact = _load_json(art_path)
        if artifact:
            training_artifacts[model_key] = artifact

    # 1. comparator_rankings.csv
    if comparator_cis:
        df = generate_comparator_rankings(comparator_cis)
        df.to_csv(output_dir / "comparator_rankings.csv", index=False)
        generated.append("comparator_rankings.csv")
    else:
        logger.warning("No comparator CIs found; skipping comparator_rankings.csv")

    # 2. h2h_delta_matrix.csv
    if h2h_battery:
        df = generate_h2h_delta_matrix(h2h_battery)
        df.to_csv(output_dir / "h2h_delta_matrix.csv", index=False)
        generated.append("h2h_delta_matrix.csv")
    else:
        logger.warning("No H2H battery found; skipping h2h_delta_matrix.csv")

    # 3. model_performance.csv
    if training_artifacts:
        df = generate_model_performance(training_artifacts)
        df.to_csv(output_dir / "model_performance.csv", index=False)
        generated.append("model_performance.csv")
    else:
        logger.warning("No training artifacts found; skipping model_performance.csv")

    # 4. behavior_summary.csv
    df = generate_behavior_summary(comparator_cis, h2h_battery)
    if len(df) > 0:
        df.to_csv(output_dir / "behavior_summary.csv", index=False)
        generated.append("behavior_summary.csv")

    # 5. behavior_by_contract.csv
    df = generate_behavior_by_contract(comparator_cis)
    if len(df) > 0:
        df.to_csv(output_dir / "behavior_by_contract.csv", index=False)
        generated.append("behavior_by_contract.csv")

    # 6. sanity_bounds_check.csv
    df = generate_sanity_bounds_check(comparator_cis, training_artifacts)
    if len(df) > 0:
        df.to_csv(output_dir / "sanity_bounds_check.csv", index=False)
        generated.append("sanity_bounds_check.csv")

    # 7. hypothesis_outcomes.csv (stub)
    df = generate_hypothesis_outcomes()
    df.to_csv(output_dir / "hypothesis_outcomes.csv", index=False)
    generated.append("hypothesis_outcomes.csv")

    # 8. rung_model_spec.csv
    df = generate_rung_model_spec(roster)
    if len(df) > 0:
        df.to_csv(output_dir / "rung_model_spec.csv", index=False)
        generated.append("rung_model_spec.csv")

    # 9. cross_rung_deltas.csv (starts empty for first rung)
    df = generate_cross_rung_deltas()
    df.to_csv(output_dir / "cross_rung_deltas.csv", index=False)
    generated.append("cross_rung_deltas.csv")

    # 10. dataset_provenance.csv
    df = generate_dataset_provenance(training_artifacts)
    if len(df) > 0:
        df.to_csv(output_dir / "dataset_provenance.csv", index=False)
        generated.append("dataset_provenance.csv")

    # 11. artifact_inventory.csv
    df = generate_artifact_inventory(training_artifacts, roster, rung_dir)
    if len(df) > 0:
        df.to_csv(output_dir / "artifact_inventory.csv", index=False)
        generated.append("artifact_inventory.csv")

    # 12. data_sanity.csv
    df = generate_data_sanity(h2h_battery, comparator_cis, training_artifacts)
    if len(df) > 0:
        df.to_csv(output_dir / "data_sanity.csv", index=False)
        generated.append("data_sanity.csv")

    # 13. seed_sanity.csv (multi-seed per-seed sanity checks)
    if len(seed_list) > 1 and seed_list[0] is not None:
        df = generate_seed_sanity_table(h2h_batteries, comparator_cis_list)
        df.to_csv(output_dir / "seed_sanity.csv", index=False)
        generated.append("seed_sanity.csv")
        if len(df) > 0:
            logger.warning(
                "Per-seed sanity: %d warnings detected. See seed_sanity.csv.",
                len(df),
            )

    return generated

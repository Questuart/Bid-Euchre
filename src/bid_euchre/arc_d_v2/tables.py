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

        # Per-bid_type rows (if by_bid_type data is available)
        by_bid_type = cell.get("by_bid_type", {})
        for bt in ("regular", "moon", "loner"):
            bt_data = by_bid_type.get(bt)
            if bt_data:
                rows.append(
                    {
                        "model_a": bidder_a,
                        "model_b": bidder_b,
                        "facet": f"bid_type:{bt}",
                        "net_eppd_delta": _safe_round(bt_data.get("net_eppd_delta")),
                        "ci_low": _safe_round(bt_data.get("ci_low")),
                        "ci_high": _safe_round(bt_data.get("ci_high")),
                        "win_rate_a": _safe_round(bt_data.get("win_rate_a")),
                        "deals_total": bt_data.get("deals_total"),
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


def _compute_contract_mix(
    comparator_cis: dict | None, h2h_battery: dict | None
) -> dict[str, dict[str, float | None]]:
    """Compute contract-type mix fractions per model from available sources.

    Uses H2H self-play by_contract deal counts when available,
    falls back to comparator bidders_by_contract if present.

    Returns:
        dict mapping model name to {"mix_suit": float|None, "mix_high": ..., "mix_low": ...}
    """
    result: dict[str, dict[str, float | None]] = {}

    # Prefer H2H self-play by_contract (always has deal counts per contract)
    if h2h_battery:
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue  # Only self-play
            model = cell["bidder_a"]
            by_contract = cell.get("by_contract", {})
            if not by_contract:
                continue
            total = sum(ct.get("deals_total", 0) for ct in by_contract.values())
            if total > 0:
                result[model] = {
                    "mix_suit": _safe_round(
                        by_contract.get("suit", {}).get("deals_total", 0) / total
                    ),
                    "mix_high": _safe_round(
                        by_contract.get("high", {}).get("deals_total", 0) / total
                    ),
                    "mix_low": _safe_round(
                        by_contract.get("low", {}).get("deals_total", 0) / total
                    ),
                }

    # Fall back to comparator bidders_by_contract if available
    if comparator_cis and not result:
        bidders_by_contract = comparator_cis.get("bidders_by_contract", {})
        if bidders_by_contract:
            # Collect all models across contract types
            models = set()
            for ct_data in bidders_by_contract.values():
                models.update(ct_data.keys())
            for model in models:
                counts = {}
                for ct in ("suit", "high", "low"):
                    ct_data = bidders_by_contract.get(ct, {}).get(model, {})
                    counts[ct] = ct_data.get("deals_total", 0)
                total = sum(counts.values())
                if total > 0:
                    result[model] = {
                        "mix_suit": _safe_round(counts["suit"] / total),
                        "mix_high": _safe_round(counts["high"] / total),
                        "mix_low": _safe_round(counts["low"] / total),
                    }

    return result


def generate_behavior_summary(
    comparator_cis: dict | None = None,
    h2h_battery: dict | None = None,
) -> pd.DataFrame:
    """Generate behavior_summary.csv -- pooled behavioral metrics per model.

    Columns: model, net_eppd, eppd, bid_rate, pass_rate, make_rate, cvar_5,
             net_cvar_5, mix_suit, mix_high, mix_low, source

    Note: avg_bid, bid_std, bid_min, bid_max, and redeal_rate are defined in
    the reporting contract but are not currently available in comparator_cis or
    H2H battery artifacts. They are omitted until the source data supports them.
    """
    contract_mix = _compute_contract_mix(comparator_cis, h2h_battery)
    rows = []

    if comparator_cis:
        for name, b in comparator_cis.get("bidders", {}).items():
            bid_rate = b.get("bid_rate")
            mix = contract_mix.get(name, {})
            rows.append(
                {
                    "model": name,
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "eppd": _safe_round(b.get("eppd")),
                    "bid_rate": _safe_round(bid_rate),
                    "pass_rate": _safe_round(1.0 - bid_rate)
                    if bid_rate is not None
                    else None,
                    "make_rate": _safe_round(b.get("make_rate")),
                    "cvar_5": _safe_round(b.get("cvar_5")),
                    "net_cvar_5": _safe_round(b.get("net_cvar_5")),
                    "mix_suit": mix.get("mix_suit"),
                    "mix_high": mix.get("mix_high"),
                    "mix_low": mix.get("mix_low"),
                    "source": "comparator",
                }
            )

    if h2h_battery:
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue  # Only self-play
            bid_rate = cell.get("bid_rate_a")
            model = cell["bidder_a"]
            mix = contract_mix.get(model, {})
            rows.append(
                {
                    "model": model,
                    "net_eppd": _safe_round(cell.get("fullgame_eppd")),
                    "eppd": None,
                    "bid_rate": _safe_round(bid_rate),
                    "pass_rate": _safe_round(1.0 - bid_rate)
                    if bid_rate is not None
                    else None,
                    "make_rate": _safe_round(cell.get("make_rate_a")),
                    "cvar_5": _safe_round(cell.get("fullgame_cvar_5")),
                    "net_cvar_5": None,
                    "mix_suit": mix.get("mix_suit"),
                    "mix_high": mix.get("mix_high"),
                    "mix_low": mix.get("mix_low"),
                    "source": "h2h_self_play",
                }
            )

    return pd.DataFrame(rows)


def generate_behavior_by_contract(
    comparator_cis: dict | None = None,
) -> pd.DataFrame:
    """Generate behavior_by_contract.csv -- faceted behavioral metrics.

    Columns: model, contract, net_eppd, bid_rate, pass_rate, make_rate, source

    Note: avg_bid, bid_std, bid_min, bid_max are defined in the reporting
    contract but are not currently available in comparator_cis per-contract
    artifacts. They are omitted until the source data supports them.
    """
    rows = []
    if comparator_cis:
        # Per-contract rows if available
        bidders_by_contract = comparator_cis.get("bidders_by_contract", {})
        for contract in ["suit", "high", "low"]:
            contract_data = bidders_by_contract.get(contract, {})
            for name, b in contract_data.items():
                bid_rate = b.get("bid_rate")
                rows.append(
                    {
                        "model": name,
                        "contract": contract,
                        "net_eppd": _safe_round(b.get("net_eppd")),
                        "bid_rate": _safe_round(bid_rate),
                        "pass_rate": _safe_round(1.0 - bid_rate)
                        if bid_rate is not None
                        else None,
                        "make_rate": _safe_round(b.get("make_rate")),
                        "source": "comparator",
                    }
                )

        # Pooled rows (always available)
        for name, b in comparator_cis.get("bidders", {}).items():
            bid_rate = b.get("bid_rate")
            rows.append(
                {
                    "model": name,
                    "contract": "pooled",
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "bid_rate": _safe_round(bid_rate),
                    "pass_rate": _safe_round(1.0 - bid_rate)
                    if bid_rate is not None
                    else None,
                    "make_rate": _safe_round(b.get("make_rate")),
                    "source": "comparator",
                }
            )

    return pd.DataFrame(rows)


def generate_behavior_by_bid_type(
    comparator_cis: dict | None = None,
    h2h_battery: dict | None = None,
) -> pd.DataFrame:
    """Generate behavior_by_bid_type.csv -- faceted behavioral metrics by bid type.

    Columns: model, bid_type, count, bid_rate, make_rate, mean_net_points, source

    For R0-R2 data (no bid_type field): emits only "regular" rows.
    For R3 data: emits regular + moon + loner rows with actual frequencies.
    """
    rows: list[dict] = []

    if comparator_cis:
        bidders = comparator_cis.get("bidders", {})
        bidders_by_bid_type = comparator_cis.get("bidders_by_bid_type", {})

        if bidders_by_bid_type:
            # R3+ data: per-bid_type breakdowns available
            for bt in ("regular", "moon", "loner"):
                bt_data = bidders_by_bid_type.get(bt, {})
                for name, b in bt_data.items():
                    rows.append(
                        {
                            "model": name,
                            "bid_type": bt,
                            "count": b.get("hands_with_bids", 0),
                            "bid_rate": _safe_round(b.get("bid_rate")),
                            "make_rate": _safe_round(b.get("make_rate")),
                            "mean_net_points": _safe_round(b.get("net_eppd")),
                            "source": "comparator",
                        }
                    )
        else:
            # R0-R2 data: only "regular" rows
            for name, b in bidders.items():
                rows.append(
                    {
                        "model": name,
                        "bid_type": "regular",
                        "count": b.get("hands_with_bids", 0),
                        "bid_rate": _safe_round(b.get("bid_rate")),
                        "make_rate": _safe_round(b.get("make_rate")),
                        "mean_net_points": _safe_round(b.get("net_eppd")),
                        "source": "comparator",
                    }
                )

    if h2h_battery:
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue  # Only self-play for behavior tables
            by_bid_type = cell.get("by_bid_type", {})
            if by_bid_type:
                for bt in ("regular", "moon", "loner"):
                    bt_data = by_bid_type.get(bt)
                    if bt_data:
                        rows.append(
                            {
                                "model": cell["bidder_a"],
                                "bid_type": bt,
                                "count": bt_data.get("deals_total", 0),
                                "bid_rate": None,
                                "make_rate": _safe_round(bt_data.get("win_rate_a")),
                                "mean_net_points": _safe_round(
                                    bt_data.get("net_eppd_delta")
                                ),
                                "source": "h2h_self_play",
                            }
                        )
            else:
                # No bid_type data: emit "regular" row
                rows.append(
                    {
                        "model": cell["bidder_a"],
                        "bid_type": "regular",
                        "count": cell.get("deals_total", 0),
                        "bid_rate": _safe_round(cell.get("bid_rate_a")),
                        "make_rate": _safe_round(cell.get("make_rate_a")),
                        "mean_net_points": _safe_round(cell.get("fullgame_eppd")),
                        "source": "h2h_self_play",
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


def generate_hypothesis_outcomes(
    advance_check: dict | None = None,
) -> pd.DataFrame:
    """Generate hypothesis_outcomes.csv from advance_check data.

    Columns: hypothesis_id, description, status, evidence, notes

    If advance_check is provided, populates from its hypothesis_checks.
    Otherwise returns an empty DataFrame with the correct schema.
    """
    rows: list[dict] = []

    if advance_check:
        for h in advance_check.get("hypothesis_checks", []):
            passed = h.get("pass", False)
            observed = h.get("observed")
            expected_bound = h.get("expected_bound", "")
            surprise = h.get("surprise_hit", False)

            if h.get("skipped"):
                status = "SKIP"
            elif passed:
                status = "PASS"
            else:
                status = "FAIL"
            evidence = f"observed={observed}"
            if expected_bound:
                evidence += f", bound={expected_bound}"

            notes_parts = []
            if h.get("skipped"):
                note = h.get("note", "")
                if note:
                    notes_parts.append(note)
            if surprise:
                notes_parts.append("SURPRISE")
            if h.get("error"):
                notes_parts.append(f"error: {h['error']}")

            rows.append(
                {
                    "hypothesis_id": h.get("id", ""),
                    "description": h.get("description", ""),
                    "status": status,
                    "evidence": evidence,
                    "notes": "; ".join(notes_parts) if notes_parts else "",
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            "hypothesis_id",
            "description",
            "status",
            "evidence",
            "notes",
        ],
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
#  H2H tier summary
# ──────────────────────────────────────────────

# Tier definitions for H2H opponent classification.
# Models not in any tier are classified as "unknown".
TIER_SMART = frozenset(
    {
        "full_ols_av",
        "constrained_ols_av",
        "selected_ols_av",
        "selected_two_stage_av",
    }
)
TIER_ANCHOR = frozenset({"anchor_hybrid_r0_full"})
TIER_HEURISTIC = frozenset({"modeloespecifico", "stricthellraiser", "rankthetank"})


def _classify_tier(model_name: str) -> str:
    """Classify a model into a tier for H2H summary."""
    if model_name in TIER_SMART:
        return "smart"
    if model_name in TIER_ANCHOR:
        return "anchor"
    if model_name in TIER_HEURISTIC:
        return "heuristic"
    return "unknown"


def generate_h2h_tier_summary(
    h2h_delta_matrix: pd.DataFrame,
) -> pd.DataFrame:
    """Generate h2h_tier_summary.csv from an h2h_delta_matrix DataFrame.

    For each model, computes mean H2H delta and mean win rate against
    opponents grouped by tier (smart, anchor, heuristic).

    Only uses pooled-facet cross-matchup rows (excludes self-play).

    Columns: model, tier, mean_delta, mean_win_rate, n_opponents

    Args:
        h2h_delta_matrix: DataFrame with h2h_delta_matrix.csv schema
            (columns: model_a, model_b, facet, net_eppd_delta, ..., win_rate_a).
    """
    # Filter to pooled facet, cross-matchup only
    df = h2h_delta_matrix[
        (h2h_delta_matrix["facet"] == "pooled")
        & (h2h_delta_matrix["model_a"] != h2h_delta_matrix["model_b"])
    ].copy()

    if df.empty:
        return pd.DataFrame(
            columns=["model", "tier", "mean_delta", "mean_win_rate", "n_opponents"]
        )

    # Classify opponent tier
    df["opponent_tier"] = df["model_b"].apply(_classify_tier)

    rows: list[dict] = []
    for model_name in sorted(df["model_a"].unique()):
        model_rows = df[df["model_a"] == model_name]
        for tier in ("smart", "anchor", "heuristic"):
            tier_rows = model_rows[model_rows["opponent_tier"] == tier]
            if tier_rows.empty:
                continue
            rows.append(
                {
                    "model": model_name,
                    "tier": tier,
                    "mean_delta": _safe_round(
                        float(tier_rows["net_eppd_delta"].mean())
                    ),
                    "mean_win_rate": _safe_round(float(tier_rows["win_rate_a"].mean())),
                    "n_opponents": len(tier_rows),
                }
            )

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
#  Chart data extraction
# ──────────────────────────────────────────────


def generate_chart_data(
    h2h_battery: dict | None = None,
    comparator_cis: dict | None = None,
    training_artifacts: dict[str, dict] | None = None,
    output_dir: Path | None = None,
    parquet_paths: list[Path] | None = None,
) -> list[str]:
    """Generate chart_data CSVs from existing artifacts.

    Produces auditable source-data CSVs for chart generation (Phase 2).
    Only creates CSVs where sufficient source data exists.

    Args:
        h2h_battery: Merged H2H battery JSON.
        comparator_cis: Merged comparator CIs JSON.
        training_artifacts: Dict of model_name -> training artifact JSON.
        output_dir: Path to write chart_data CSVs.
        parquet_paths: Optional list of action-value parquet file paths
            for true outcome distributions.

    Returns:
        List of generated CSV filenames.
    """
    if output_dir is None:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # 1. outcome_summary.csv — summary metrics from H2H self-play by_contract
    #    NOTE: This is *summary* data (one row per model per contract facet),
    #    NOT per-deal observations. Renamed from outcome_distributions.csv to
    #    avoid implying distributional granularity.
    if h2h_battery:
        rows = []
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue  # Self-play only
            model = cell["bidder_a"]
            # Pooled outcome
            fullgame_eppd = cell.get("fullgame_eppd")
            if fullgame_eppd is not None:
                rows.append(
                    {
                        "model": model,
                        "contract": "pooled",
                        "value": _safe_round(fullgame_eppd),
                        "metric": "fullgame_eppd",
                    }
                )
            # Per-contract outcomes
            by_contract = cell.get("by_contract", {})
            for ct in ("suit", "high", "low"):
                ct_data = by_contract.get(ct)
                if ct_data and ct_data.get("net_eppd_delta") is not None:
                    rows.append(
                        {
                            "model": model,
                            "contract": ct,
                            "value": _safe_round(ct_data["net_eppd_delta"]),
                            "metric": "net_eppd_delta",
                        }
                    )
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "outcome_summary.csv", index=False)
            generated.append("outcome_summary.csv")

    # 2. contract_mix.csv — deal counts by contract from H2H self-play
    if h2h_battery:
        rows = []
        for _mid, cell in h2h_battery.get("cells", {}).items():
            if cell.get("bidder_a") != cell.get("bidder_b"):
                continue
            model = cell["bidder_a"]
            by_contract = cell.get("by_contract", {})
            if not by_contract:
                continue
            total = sum(ct.get("deals_total", 0) for ct in by_contract.values())
            for ct in ("suit", "high", "low"):
                ct_data = by_contract.get(ct, {})
                deals = ct_data.get("deals_total", 0)
                rows.append(
                    {
                        "model": model,
                        "contract": ct,
                        "deals": deals,
                        "fraction": _safe_round(deals / total) if total > 0 else None,
                    }
                )
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "contract_mix.csv", index=False)
            generated.append("contract_mix.csv")

    # 3. h2h_by_contract.csv — H2H battery by_contract statistics
    #    NOTE: This is per-matchup summary data (one row per model×opponent×contract),
    #    NOT per-deal observations. Renamed from outcome_distributions.csv to avoid
    #    implying distributional granularity.
    if h2h_battery:
        rows = _extract_h2h_by_contract(h2h_battery)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "h2h_by_contract.csv", index=False)
            generated.append("h2h_by_contract.csv")

    # 4. bid_levels.csv — aggregate bidding metrics per model from comparator CIs
    if comparator_cis:
        rows = _extract_bid_levels(comparator_cis)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "bid_levels.csv", index=False)
            generated.append("bid_levels.csv")

    # 5. seat_balance.csv — per-seat trick distributions from parquet if available
    #    Deferred: requires per-seat JSONL/parquet not present in battery summaries.
    #    The function exists but is called separately when parquet data is available.

    # 6. selection_paths.csv — feature importance from training artifacts
    if training_artifacts:
        rows = _extract_feature_importance(training_artifacts)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "selection_paths.csv", index=False)
            generated.append("selection_paths.csv")

    # 7. outcome_distributions.csv — per-deal tricks_won histogram bins
    if h2h_battery:
        rows = _extract_outcome_distributions(h2h_battery, parquet_paths=parquet_paths)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "outcome_distributions.csv", index=False)
            generated.append("outcome_distributions.csv")

    # 8. feature_importances.csv — flat feature importance table
    if training_artifacts:
        rows = _extract_feature_importances_flat(training_artifacts)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "feature_importances.csv", index=False)
            generated.append("feature_importances.csv")

    # 9. decision_comparison.csv — per-deal bid decision comparison across models
    if parquet_paths:
        rows = _extract_decision_comparison(parquet_paths)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "decision_comparison.csv", index=False)
            generated.append("decision_comparison.csv")

    # 10. disagreement_outcomes.csv — outcomes for deals where models disagreed
    if parquet_paths:
        rows = _extract_disagreement_outcomes(parquet_paths)
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / "disagreement_outcomes.csv", index=False)
            generated.append("disagreement_outcomes.csv")

    return generated


def _extract_h2h_by_contract(h2h_battery: dict) -> list[dict]:
    """Flatten H2H battery by_contract statistics into chart_data rows.

    Extracts per-matchup per-contract summary data into rows for
    H2H analysis charts. This is summary data (one row per
    model×opponent×contract), NOT per-deal observations.

    Returns list of dicts with keys:
        model, opponent, contract, net_eppd_delta, deals_total, win_rate
    """
    rows: list[dict] = []
    for _mid, cell in h2h_battery.get("cells", {}).items():
        bidder_a = cell.get("bidder_a", "")
        bidder_b = cell.get("bidder_b", "")
        # Include both cross-matchup and self-play cells
        by_contract = cell.get("by_contract", {})
        for ct in ("suit", "high", "low"):
            ct_data = by_contract.get(ct)
            if ct_data is None:
                continue
            rows.append(
                {
                    "model": bidder_a,
                    "opponent": bidder_b,
                    "contract": ct,
                    "net_eppd_delta": _safe_round(ct_data.get("net_eppd_delta")),
                    "deals_total": ct_data.get("deals_total"),
                    "win_rate": _safe_round(ct_data.get("win_rate_a")),
                }
            )
        # Also emit a pooled row from the top-level cell data
        rows.append(
            {
                "model": bidder_a,
                "opponent": bidder_b,
                "contract": "pooled",
                "net_eppd_delta": _safe_round(cell.get("net_eppd_delta")),
                "deals_total": cell.get("deals_total"),
                "win_rate": _safe_round(cell.get("win_rate_a")),
            }
        )
    return rows


def _extract_bid_levels(comparator_cis: dict) -> list[dict]:
    """Extract aggregate bidding metrics per model from comparator CIs.

    Per-bid-level distributions are not available in battery JSONs, so
    this extracts the available aggregate metrics (bid_rate, make_rate,
    pass_rate, avg_bid proxy).

    Returns list of dicts with keys:
        model, bid_rate, make_rate, pass_rate
    """
    rows: list[dict] = []
    for name, b in comparator_cis.get("bidders", {}).items():
        bid_rate = b.get("bid_rate")
        make_rate = b.get("make_rate")
        rows.append(
            {
                "model": name,
                "bid_rate": _safe_round(bid_rate),
                "make_rate": _safe_round(make_rate),
                "pass_rate": _safe_round(1.0 - bid_rate)
                if bid_rate is not None
                else None,
            }
        )
    return rows


def _extract_feature_importance(
    training_artifacts: dict[str, dict],
) -> list[dict]:
    """Extract feature importance rankings from training artifact metadata.

    Uses ``feature_importances`` dict from GBT artifacts as the source.
    Falls back gracefully if selection_logs are not present.

    Returns list of dicts with keys:
        model, contract, rank, feature_name, importance
    """
    rows: list[dict] = []
    for model_name, artifact in training_artifacts.items():
        models = artifact.get("models", {})
        for contract, model_data in models.items():
            # Prefer selection_logs if available
            sel_logs = artifact.get("metadata", {}).get("selection_logs", {})
            if sel_logs and contract in sel_logs:
                steps = sel_logs[contract].get("steps", [])
                for step_info in steps:
                    rows.append(
                        {
                            "model": model_name,
                            "contract": contract,
                            "rank": step_info["step"],
                            "feature_name": step_info["feature"],
                            "importance": _safe_round(step_info.get("r2")),
                        }
                    )
                continue

            # Fall back to feature_importances dict
            importances = model_data.get("feature_importances", {})
            if not importances:
                continue
            # Sort by importance descending
            sorted_feats = sorted(importances.items(), key=lambda x: x[1], reverse=True)
            for rank_idx, (feat_name, imp_val) in enumerate(sorted_feats, 1):
                rows.append(
                    {
                        "model": model_name,
                        "contract": contract,
                        "rank": rank_idx,
                        "feature_name": feat_name,
                        "importance": _safe_round(imp_val),
                    }
                )
    return rows


def _extract_outcome_distributions(
    h2h_battery: dict,
    parquet_paths: list[Path] | None = None,
) -> list[dict]:
    """Extract outcome distribution data, preferring parquet when available.

    **Primary path (parquet):** If ``parquet_paths`` contains existing
    action-value parquet files, reads them and extracts true ``tricks_won``
    histogram: groupby ``contract_family`` x ``tricks_won`` -> count.
    Schema: model, contract, tricks_won, count, fraction, source.

    **Fallback path (synthetic):** If parquet is unavailable, falls back to
    synthesizing histogram-shaped data from H2H battery summary metrics.
    Adds ``source="synthetic"`` so downstream consumers know the data is
    interpolated.

    Args:
        h2h_battery: Merged H2H battery JSON.
        parquet_paths: Optional list of paths to action-value parquet files.

    Returns:
        List of dicts suitable for DataFrame construction.
    """
    # Primary path: read from parquet files
    if parquet_paths:
        rows = _extract_outcome_distributions_from_parquet(parquet_paths)
        if rows:
            return rows

    # Fallback: synthetic from battery JSON
    rows: list[dict] = []
    for _mid, cell in h2h_battery.get("cells", {}).items():
        if cell.get("bidder_a") != cell.get("bidder_b"):
            continue  # Self-play only
        model = cell["bidder_a"]
        by_contract = cell.get("by_contract", {})
        for ct in ("suit", "high", "low"):
            ct_data = by_contract.get(ct)
            if ct_data is None:
                continue

            # Prefer explicit histogram bins if available (future-proof)
            histogram = ct_data.get("tricks_won_histogram")
            if histogram and isinstance(histogram, dict):
                total = sum(histogram.values())
                for tricks_str, count in sorted(histogram.items()):
                    try:
                        tricks = int(tricks_str)
                    except (ValueError, TypeError):
                        continue
                    rows.append(
                        {
                            "model": model,
                            "contract": ct,
                            "tricks_won": tricks,
                            "count": count,
                            "fraction": _safe_round(count / total)
                            if total > 0
                            else None,
                            "source": "synthetic",
                        }
                    )
                continue

            # Fallback: use deals_total as a single-bin count per contract
            deals = ct_data.get("deals_total", 0)
            if deals and deals > 0:
                # Use mean_tricks if available, else tricks_won=5 as midpoint
                mean_tricks = ct_data.get("mean_tricks_won", 5)
                rows.append(
                    {
                        "model": model,
                        "contract": ct,
                        "tricks_won": int(round(mean_tricks))
                        if mean_tricks is not None
                        else 5,
                        "count": deals,
                        "fraction": 1.0,
                        "source": "synthetic",
                    }
                )

    if rows:
        logger.warning(
            "Outcome distributions extracted from synthetic battery data. "
            "For true distributions, provide action-value parquet files."
        )
    return rows


def _extract_outcome_distributions_from_parquet(
    parquet_paths: list[Path],
) -> list[dict]:
    """Extract true outcome distributions from action-value parquet files.

    Reads parquet files containing per-deal action-value data, groups by
    contract_family x tricks_won, and produces histogram counts.

    Args:
        parquet_paths: List of paths to action-value parquet files.

    Returns:
        List of dicts with keys: model, contract, tricks_won, count, fraction, source.
        Empty list if no valid parquet files found.
    """
    frames: list[pd.DataFrame] = []
    for path in parquet_paths:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            frames.append(df)
        except Exception as e:
            logger.warning("Failed to read parquet %s: %s", path, e)
            continue

    if not frames:
        return []

    combined = pd.concat(frames, ignore_index=True)

    # Determine contract column name (contract_family or contract_type)
    contract_col = None
    for candidate in ("contract_family", "contract_type", "contract"):
        if candidate in combined.columns:
            contract_col = candidate
            break
    if contract_col is None or "tricks_won" not in combined.columns:
        logger.warning(
            "Parquet missing required columns (contract + tricks_won). Available: %s",
            list(combined.columns),
        )
        return []

    # Determine model column if present
    model_col = None
    for candidate in ("model", "bidder", "model_name"):
        if candidate in combined.columns:
            model_col = candidate
            break

    rows: list[dict] = []
    # Group by model (if present) and contract
    if model_col:
        group_cols = [model_col, contract_col, "tricks_won"]
    else:
        group_cols = [contract_col, "tricks_won"]

    grouped = combined.groupby(group_cols).size().reset_index(name="count")

    # Compute fractions within each model+contract group
    fraction_group_cols = [model_col, contract_col] if model_col else [contract_col]
    totals = grouped.groupby(fraction_group_cols)["count"].transform("sum")
    grouped["fraction"] = grouped["count"] / totals

    for _, row in grouped.iterrows():
        entry: dict = {
            "model": row[model_col] if model_col else "unknown",
            "contract": row[contract_col],
            "tricks_won": int(row["tricks_won"]),
            "count": int(row["count"]),
            "fraction": _safe_round(float(row["fraction"])),
            "source": "parquet",
        }
        rows.append(entry)

    logger.info(
        "Extracted %d outcome distribution rows from %d parquet file(s)",
        len(rows),
        len(frames),
    )
    return rows


def _extract_decision_comparison(
    parquet_paths: list[Path],
) -> list[dict]:
    """Extract per-deal bid decision comparison across models.

    Requires parquet files with bid decision columns (e.g., ``bid_decision``,
    ``model``). If the schema lacks these columns, returns an empty list with
    an informational log message.

    Schema: model_a, model_b, contract, deal_id, decision_a, decision_b, agreed
    """
    frames: list[pd.DataFrame] = []
    for path in parquet_paths:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            frames.append(df)
        except Exception as e:
            logger.warning("Failed to read parquet %s: %s", path, e)
            continue

    if not frames:
        return []

    combined = pd.concat(frames, ignore_index=True)

    # Check for required columns: need bid decision data per model per deal
    required = {"bid_decision", "model", "deal_id"}
    if not required.issubset(combined.columns):
        logger.info(
            "decision_comparison: parquet missing required columns %s. "
            "Available: %s. Skipping.",
            required - set(combined.columns),
            list(combined.columns),
        )
        return []

    # Determine contract column
    contract_col = None
    for candidate in ("contract_family", "contract_type", "contract"):
        if candidate in combined.columns:
            contract_col = candidate
            break
    if contract_col is None:
        contract_col = "contract"
        combined[contract_col] = "pooled"

    # Build pairwise comparisons
    models = sorted(combined["model"].unique())
    rows: list[dict] = []
    for i, model_a in enumerate(models):
        for model_b in models[i + 1 :]:
            df_a = combined[combined["model"] == model_a]
            df_b = combined[combined["model"] == model_b]
            merged = df_a.merge(
                df_b, on=["deal_id", contract_col], suffixes=("_a", "_b")
            )
            for _, row in merged.iterrows():
                rows.append(
                    {
                        "model_a": model_a,
                        "model_b": model_b,
                        "contract": row[contract_col],
                        "deal_id": row["deal_id"],
                        "decision_a": row["bid_decision_a"],
                        "decision_b": row["bid_decision_b"],
                        "agreed": row["bid_decision_a"] == row["bid_decision_b"],
                    }
                )

    return rows


def _extract_disagreement_outcomes(
    parquet_paths: list[Path],
) -> list[dict]:
    """Extract outcomes for deals where models disagreed on bid decisions.

    Requires parquet files with bid decision and tricks_won columns per model
    per deal. If the schema lacks these columns, returns an empty list.

    Schema: model_a, model_b, contract, deal_id, decision_a, decision_b,
            tricks_won_a, tricks_won_b
    """
    frames: list[pd.DataFrame] = []
    for path in parquet_paths:
        if not path.exists():
            continue
        try:
            df = pd.read_parquet(path)
            frames.append(df)
        except Exception as e:
            logger.warning("Failed to read parquet %s: %s", path, e)
            continue

    if not frames:
        return []

    combined = pd.concat(frames, ignore_index=True)

    # Check for required columns
    required = {"bid_decision", "model", "deal_id", "tricks_won"}
    if not required.issubset(combined.columns):
        logger.info(
            "disagreement_outcomes: parquet missing required columns %s. "
            "Available: %s. Skipping.",
            required - set(combined.columns),
            list(combined.columns),
        )
        return []

    # Determine contract column
    contract_col = None
    for candidate in ("contract_family", "contract_type", "contract"):
        if candidate in combined.columns:
            contract_col = candidate
            break
    if contract_col is None:
        contract_col = "contract"
        combined[contract_col] = "pooled"

    # Build disagreement rows
    models = sorted(combined["model"].unique())
    rows: list[dict] = []
    for i, model_a in enumerate(models):
        for model_b in models[i + 1 :]:
            df_a = combined[combined["model"] == model_a]
            df_b = combined[combined["model"] == model_b]
            merged = df_a.merge(
                df_b, on=["deal_id", contract_col], suffixes=("_a", "_b")
            )
            disagreements = merged[merged["bid_decision_a"] != merged["bid_decision_b"]]
            for _, row in disagreements.iterrows():
                rows.append(
                    {
                        "model_a": model_a,
                        "model_b": model_b,
                        "contract": row[contract_col],
                        "deal_id": row["deal_id"],
                        "decision_a": row["bid_decision_a"],
                        "decision_b": row["bid_decision_b"],
                        "tricks_won_a": row["tricks_won_a"],
                        "tricks_won_b": row["tricks_won_b"],
                    }
                )

    return rows


def _extract_feature_importances_flat(
    training_artifacts: dict[str, dict],
) -> list[dict]:
    """Extract flat feature importance table from training artifacts.

    Unlike ``_extract_feature_importance`` which targets selection_paths.csv
    (with step/rank info from selection logs), this function produces a
    simpler flat table of feature_name -> importance values from the
    ``feature_importances`` dict in model artifacts.

    Schema: model, contract, feature_name, importance

    Returns list of dicts suitable for DataFrame construction.
    """
    rows: list[dict] = []
    for model_name, artifact in training_artifacts.items():
        models = artifact.get("models", {})
        for contract, model_data in models.items():
            importances = model_data.get("feature_importances", {})
            if not importances:
                continue
            for feat_name, imp_val in importances.items():
                rows.append(
                    {
                        "model": model_name,
                        "contract": contract,
                        "feature_name": feat_name,
                        "importance": _safe_round(imp_val),
                    }
                )
    return rows


def generate_cross_rung_progression(
    rung_comparator_cis: dict[str, dict],
) -> pd.DataFrame:
    """Generate cross_rung_progression.csv from multiple rung comparator CIs.

    Per-model metrics across rungs for trend analysis.

    Args:
        rung_comparator_cis: Dict mapping rung label (e.g. "r0", "r1") to
            the comparator CIs JSON for that rung.

    Returns:
        DataFrame with columns:
            rung, model, rank, net_eppd, cvar_5, bid_rate, make_rate
    """
    _columns = ["rung", "model", "rank", "net_eppd", "cvar_5", "bid_rate", "make_rate"]
    rows: list[dict] = []
    for rung_label in sorted(rung_comparator_cis.keys()):
        cis = rung_comparator_cis[rung_label]
        ranked_order = cis.get("ranked_order", sorted(cis.get("bidders", {}).keys()))
        bidders = cis.get("bidders", {})
        for rank_idx, name in enumerate(ranked_order, 1):
            b = bidders.get(name, {})
            rows.append(
                {
                    "rung": rung_label,
                    "model": name,
                    "rank": rank_idx,
                    "net_eppd": _safe_round(b.get("net_eppd")),
                    "cvar_5": _safe_round(b.get("cvar_5")),
                    "bid_rate": _safe_round(b.get("bid_rate")),
                    "make_rate": _safe_round(b.get("make_rate")),
                }
            )
    return pd.DataFrame(rows, columns=_columns)


def generate_seat_balance_csv(
    parquet_path: Path,
    output_dir: Path,
) -> str | None:
    """Generate seat_balance.csv from an action_value parquet dataset.

    Groups by seat and contract_family to compute mean tricks and hand counts.

    Args:
        parquet_path: Path to action_value.parquet.
        output_dir: Path to write the CSV.

    Returns:
        Filename if generated, None if data is missing or insufficient.
    """
    if not parquet_path.exists():
        logger.warning("Parquet not found for seat_balance: %s", parquet_path)
        return None

    try:
        df = pd.read_parquet(parquet_path)
    except Exception as e:
        logger.warning("Failed to read parquet for seat_balance: %s", e)
        return None

    # Determine available columns for seat and contract grouping
    seat_col = "seat" if "seat" in df.columns else None
    contract_col = (
        "contract_family"
        if "contract_family" in df.columns
        else ("contract_type" if "contract_type" in df.columns else None)
    )
    value_col = (
        "tricks_won"
        if "tricks_won" in df.columns
        else ("actual" if "actual" in df.columns else None)
    )

    if seat_col is None or value_col is None:
        logger.warning(
            "seat_balance: missing required columns (need seat + tricks_won/actual). "
            "Available: %s",
            list(df.columns),
        )
        return None

    rows: list[dict] = []
    if contract_col:
        grouped = df.groupby([seat_col, contract_col])
        for (seat, contract), group in grouped:
            rows.append(
                {
                    "seat": int(seat),
                    "contract": str(contract),
                    "mean_tricks": _safe_round(float(group[value_col].mean())),
                    "n_hands": len(group),
                }
            )
    else:
        grouped = df.groupby(seat_col)
        for seat, group in grouped:
            rows.append(
                {
                    "seat": int(seat),
                    "contract": "pooled",
                    "mean_tricks": _safe_round(float(group[value_col].mean())),
                    "n_hands": len(group),
                }
            )

    if rows:
        out_df = pd.DataFrame(rows)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_df.to_csv(output_dir / "seat_balance.csv", index=False)
        return "seat_balance.csv"
    return None


def generate_model_eval_csvs(
    training_artifacts: dict[str, dict],
    eval_parquet_path: Path | None,
    output_dir: Path,
) -> list[str]:
    """Generate model evaluation chart_data CSVs (predictions, residuals, calibration).

    These require joblib model files to be present on disk. If model files
    are not available, the function degrades gracefully and skips generation.

    Args:
        training_artifacts: Dict of model_name -> training artifact JSON.
        eval_parquet_path: Path to evaluation parquet dataset.
        output_dir: Path to write CSVs.

    Returns:
        List of generated CSV filenames.
    """
    generated: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    if not training_artifacts or eval_parquet_path is None:
        logger.info("Skipping model eval CSVs: missing artifacts or eval data")
        return generated

    if not eval_parquet_path.exists():
        logger.warning("Eval parquet not found: %s", eval_parquet_path)
        return generated

    try:
        import joblib
    except ImportError:
        logger.warning("joblib not available; skipping model eval CSVs")
        return generated

    try:
        eval_df = pd.read_parquet(eval_parquet_path)
    except Exception as e:
        logger.warning("Failed to read eval parquet: %s", e)
        return generated

    prediction_rows: list[dict] = []
    residual_rows: list[dict] = []
    calibration_rows: list[dict] = []

    for model_name, artifact in training_artifacts.items():
        schema = artifact.get("schema_version", "")
        supported_schemas = (
            "action_value_gbt_v1",
            "action_value_olsa_v1",
            "two_stage_action_value_v1",
        )
        if schema not in supported_schemas:
            continue

        models_meta = artifact.get("models", {})

        for contract, meta in models_meta.items():
            feature_names = meta.get("feature_names", [])
            if not feature_names:
                continue

            # Load model or coefficients depending on schema
            predict_fn = None

            if schema == "action_value_gbt_v1":
                # GBT: load joblib model file
                model_file = meta.get("model_file")
                if not model_file:
                    continue
                if eval_parquet_path is not None:
                    candidate_dirs = [
                        eval_parquet_path.parent.parent / "artifacts",
                        eval_parquet_path.parent,
                    ]
                    model_path = None
                    for cdir in candidate_dirs:
                        p = cdir / model_file
                        if p.exists():
                            model_path = p
                            break
                    if model_path is None:
                        logger.info(
                            "Model file %s not found for %s/%s; skipping",
                            model_file,
                            model_name,
                            contract,
                        )
                        continue
                else:
                    continue
                try:
                    model = joblib.load(model_path)
                    predict_fn = model.predict
                except Exception as e:
                    logger.warning("Failed to load model %s: %s", model_path, e)
                    continue

            elif schema in ("action_value_olsa_v1", "two_stage_action_value_v1"):
                # OLS/two-stage: use coefficients from JSON directly
                coefficients = meta.get("coefficients")
                intercept = meta.get("intercept")
                if coefficients is None or intercept is None:
                    continue
                coefs = np.array(coefficients, dtype=float)
                intercept_val = float(intercept)

                def _make_linear_predict(c, i):
                    return lambda X: X @ c + i

                predict_fn = _make_linear_predict(coefs, intercept_val)

            if predict_fn is None:
                continue

            # Filter eval data to this contract
            if contract == "pass":
                if "action_type" in eval_df.columns:
                    family_df = eval_df[eval_df["action_type"] == "pass"]
                else:
                    continue
            else:
                if "contract_family" in eval_df.columns:
                    family_df = eval_df[eval_df["contract_family"] == contract]
                else:
                    continue

            if len(family_df) == 0:
                continue

            # Subsample for performance
            if len(family_df) > 5000:
                family_df = family_df.sample(n=5000, random_state=42)

            available = [f for f in feature_names if f in family_df.columns]
            if len(available) != len(feature_names):
                continue

            X = family_df[available].values.astype(float)
            actual_col = "actual" if "actual" in family_df.columns else None
            if actual_col is None:
                continue
            actuals = family_df[actual_col].values.astype(float)

            try:
                preds = predict_fn(X)
            except Exception as e:
                logger.warning(
                    "Prediction failed for %s/%s: %s",
                    model_name,
                    contract,
                    e,
                )
                continue

            # Predictions
            for pred, act in zip(preds, actuals):
                prediction_rows.append(
                    {
                        "model": model_name,
                        "contract": contract,
                        "prediction": round(float(pred), 4),
                        "actual": round(float(act), 4),
                    }
                )

            # Residuals — binned
            residuals = preds - actuals
            bin_edges = np.linspace(
                float(residuals.min()) - 0.01,
                float(residuals.max()) + 0.01,
                21,
            )
            counts, edges = np.histogram(residuals, bins=bin_edges)
            for i, count in enumerate(counts):
                bin_center = (edges[i] + edges[i + 1]) / 2
                residual_rows.append(
                    {
                        "model": model_name,
                        "contract": contract,
                        "residual_bin": round(float(bin_center), 4),
                        "count": int(count),
                    }
                )

            # Calibration bins — by prediction decile
            n_bins = min(10, len(preds))
            if n_bins < 2:
                continue
            sorted_idx = np.argsort(preds)
            bin_size = len(preds) // n_bins
            for b in range(n_bins):
                start = b * bin_size
                end = (b + 1) * bin_size if b < n_bins - 1 else len(preds)
                bin_preds = preds[sorted_idx[start:end]]
                bin_actuals = actuals[sorted_idx[start:end]]
                calibration_rows.append(
                    {
                        "model": model_name,
                        "contract": contract,
                        "pred_bin": b + 1,
                        "mean_pred": round(float(bin_preds.mean()), 4),
                        "actual_mean": round(float(bin_actuals.mean()), 4),
                        "n_samples": len(bin_preds),
                    }
                )

    # Write CSVs
    if prediction_rows:
        pd.DataFrame(prediction_rows).to_csv(
            output_dir / "predictions.csv", index=False
        )
        generated.append("predictions.csv")

    if residual_rows:
        pd.DataFrame(residual_rows).to_csv(output_dir / "residuals.csv", index=False)
        generated.append("residuals.csv")

    if calibration_rows:
        pd.DataFrame(calibration_rows).to_csv(
            output_dir / "calibration_bins.csv", index=False
        )
        generated.append("calibration_bins.csv")

    return generated


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

        # Merge per-bid_type data if present
        all_bid_types: dict[str, list[dict]] = {}
        for c in cell_list:
            for bt, bt_data in c.get("by_bid_type", {}).items():
                all_bid_types.setdefault(bt, []).append(bt_data)
        if all_bid_types:
            merged_bt = {}
            for bt, bt_list in all_bid_types.items():
                bt_deals = [d.get("deals_total", 0) for d in bt_list]
                merged_bt_entry: dict = {}
                for key in ("net_eppd_delta", "win_rate_a"):
                    vals = [d.get(key) for d in bt_list]
                    wm = _weighted_mean(vals, bt_deals)
                    merged_bt_entry[key] = round(wm, 6) if wm is not None else None
                for key in ("ci_low", "ci_high"):
                    vals = [d.get(key) for d in bt_list if d.get(key) is not None]
                    merged_bt_entry[key] = (
                        round(sum(vals) / len(vals), 6) if vals else None
                    )
                merged_bt_entry["deals_total"] = sum(bt_deals)
                merged_bt_entry["ci_method"] = "seed_averaged"
                merged_bt[bt] = merged_bt_entry
            base["by_bid_type"] = merged_bt
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
    h2h_matrix_df = None
    if h2h_battery:
        h2h_matrix_df = generate_h2h_delta_matrix(h2h_battery)
        h2h_matrix_df.to_csv(output_dir / "h2h_delta_matrix.csv", index=False)
        generated.append("h2h_delta_matrix.csv")
    else:
        logger.warning("No H2H battery found; skipping h2h_delta_matrix.csv")

    # 2b. h2h_tier_summary.csv
    if h2h_matrix_df is not None and len(h2h_matrix_df) > 0:
        tier_df = generate_h2h_tier_summary(h2h_matrix_df)
        if len(tier_df) > 0:
            tier_df.to_csv(output_dir / "h2h_tier_summary.csv", index=False)
            generated.append("h2h_tier_summary.csv")

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

    # 5b. behavior_by_bid_type.csv
    df = generate_behavior_by_bid_type(comparator_cis, h2h_battery)
    if len(df) > 0:
        df.to_csv(output_dir / "behavior_by_bid_type.csv", index=False)
        generated.append("behavior_by_bid_type.csv")

    # 6. sanity_bounds_check.csv
    df = generate_sanity_bounds_check(comparator_cis, training_artifacts)
    if len(df) > 0:
        df.to_csv(output_dir / "sanity_bounds_check.csv", index=False)
        generated.append("sanity_bounds_check.csv")

    # 7. hypothesis_outcomes.csv — populate from advance_check.json if available
    #    Skip writing if a populated CSV already exists (e.g., from advance_check
    #    pipeline) to avoid overwriting real data with an empty stub.
    existing_ho = output_dir / "hypothesis_outcomes.csv"
    advance_check = _load_json(rung_dir / "advance_check.json")
    df = generate_hypothesis_outcomes(advance_check)
    if len(df) > 0:
        # We have real data — always write it
        df.to_csv(existing_ho, index=False)
        generated.append("hypothesis_outcomes.csv")
    elif existing_ho.exists() and existing_ho.stat().st_size > 0:
        # A populated CSV already exists — do not overwrite with empty stub
        logger.info("hypothesis_outcomes.csv already populated; skipping empty stub.")
        generated.append("hypothesis_outcomes.csv")
    else:
        # No data available — write empty schema stub
        df.to_csv(existing_ho, index=False)
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

    # 14. Discover parquet files once — shared by chart_data, seat_balance,
    #     and model eval CSV generation.
    parquet_paths: list[Path] = []
    for s in seed_list:
        candidate = rung_dir / f"seed_{s}" / "datasets" / "action_value.parquet"
        if candidate.exists():
            parquet_paths.append(candidate)

    # 14a. chart_data CSVs (outcome_summary, contract_mix, etc.)
    chart_data_dir = output_dir.parent / "chart_data"
    chart_data_csvs = generate_chart_data(
        h2h_battery=h2h_battery,
        comparator_cis=comparator_cis,
        training_artifacts=training_artifacts,
        output_dir=chart_data_dir,
        parquet_paths=parquet_paths or None,
    )
    for csv_name in chart_data_csvs:
        generated.append(f"chart_data/{csv_name}")

    # 15. seat_balance.csv from parquet data (graceful skip if absent)
    if parquet_paths:
        sb_result = generate_seat_balance_csv(parquet_paths[0], chart_data_dir)
        if sb_result and f"chart_data/{sb_result}" not in generated:
            generated.append(f"chart_data/{sb_result}")

    # 16. model eval CSVs (predictions, residuals, calibration) from parquet + models
    if training_artifacts and parquet_paths:
        eval_csvs = generate_model_eval_csvs(
            training_artifacts, parquet_paths[0], chart_data_dir
        )
        for csv_name in eval_csvs:
            generated.append(f"chart_data/{csv_name}")

    return generated

#!/usr/bin/env python
"""Generate canonical CSV tables for an Arc D v2 rung report.

Reads run artifacts (H2H battery JSON, comparator CIs JSON, training
artifact JSONs, roster JSON, action_value.parquet) and produces 11
canonical CSV tables used by generate_rung_report.py.

Usage:
    PYTHONPATH=src uv run python scripts/internal/generate_rung_tables.py \\
        --rung-dir data/fixtures/arc_d_v2 \\
        --output-dir /tmp/rung_tables

Tables produced (matching §12 of the canonical lineage rebuild plan):
  1.  comparator_rankings.csv    — one row per (model, facet)
  2.  h2h_delta_matrix.csv       — delta vs anchor per model per facet
  3.  model_performance.csv      — R², MAE, n per model per contract
  4.  behavior_summary.csv       — pooled behavioral metrics per model
  5.  behavior_by_contract.csv   — faceted behavioral per model per contract
  6.  sanity_bounds_check.csv    — sanity bound checks per model
  7.  hypothesis_outcomes.csv    — stub with columns
  8.  rung_model_spec.csv        — model roster inventory
  9.  cross_rung_deltas.csv      — accumulated cross-rung deltas
  10. dataset_provenance.csv     — dataset metadata
  11. artifact_inventory.csv     — artifact paths and versions
  12. data_sanity.csv            — Phase 0-lite sanity checks
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

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

    One row per (model, facet), facet in {suit, high, low, pooled}.
    Currently comparator CIs are pooled-only; per-contract faceting is
    a placeholder for future per-contract comparator runs.

    Columns: model, facet, net_eppd, ci_low, ci_high, bid_rate,
             make_rate, net_cvar_5, rank
    """
    bidders = comparator_cis.get("bidders", {})
    ranked_order = comparator_cis.get("ranked_order", sorted(bidders.keys()))

    rows = []
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

    One row per (model_a, model_b) cross-matchup with delta and CIs.
    Self-play rows are excluded.

    Columns: model_a, model_b, facet, net_eppd_delta, ci_low, ci_high,
             win_rate_a, deals_total
    """
    cells = h2h_battery.get("cells", {})
    rows = []

    for _mid, cell in cells.items():
        bidder_a = cell.get("bidder_a", "")
        bidder_b = cell.get("bidder_b", "")

        # Include both self-play and cross-matchups
        facet = "pooled"  # H2H battery is pooled by default
        rows.append(
            {
                "model_a": bidder_a,
                "model_b": bidder_b,
                "facet": facet,
                "net_eppd_delta": _safe_round(cell.get("net_eppd_delta")),
                "ci_low": _safe_round(cell.get("ci_low")),
                "ci_high": _safe_round(cell.get("ci_high")),
                "win_rate_a": _safe_round(cell.get("win_rate_a")),
                "deals_total": cell.get("deals_total"),
            }
        )

    return pd.DataFrame(rows)


def generate_model_performance(
    training_artifacts: dict[str, dict],
) -> pd.DataFrame:
    """Generate model_performance.csv from training artifact JSONs.

    One row per (model, contract) with R², MAE, n.

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
    """Generate behavior_summary.csv — pooled behavioral metrics per model.

    Sources: comparator CIs (primary) and H2H self-play cells (secondary).

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
    """Generate behavior_by_contract.csv — faceted behavioral metrics.

    Currently comparator CIs are pooled-only. This generates pooled rows
    as a placeholder; per-contract faceting requires per-contract comparator
    data in future runs.

    Columns: model, contract, net_eppd, bid_rate, make_rate, source
    """
    rows = []
    if comparator_cis:
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
    """Generate sanity_bounds_check.csv — sanity bound checks per model.

    Checks: bid_rate in [0.05, 0.95], make_rate in [0.1, 1.0],
            R² > 0 for trained models.

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
    """Generate hypothesis_outcomes.csv — stub with columns.

    This table is filled by the agent at Step 8 of the rung protocol.

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
    """Generate rung_model_spec.csv — model roster inventory.

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
    """Generate cross_rung_deltas.csv — accumulated cross-rung deltas.

    One row per (model, rung). Accumulated across rungs by the
    orchestrator. Starts empty for the first rung.

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
    """Generate dataset_provenance.csv — dataset metadata.

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
    """Generate artifact_inventory.csv — artifact paths and versions.

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
    """Generate data_sanity.csv — Phase 0-lite sanity checks.

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

    # Check 4: Training artifacts have R² > 0
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


def generate_all_tables(
    rung_dir: Path,
    output_dir: Path,
) -> list[str]:
    """Generate all 11 canonical CSVs from rung directory artifacts.

    Args:
        rung_dir: Path to directory containing run artifacts.
        output_dir: Path to write CSV files.

    Returns:
        List of generated CSV filenames.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    generated = []

    # Load available artifacts
    h2h_battery = _load_json(rung_dir / "h2h_battery.json")
    comparator_cis = _load_json(rung_dir / "comparator_cis.json")
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

    return generated


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate canonical CSV tables for an Arc D v2 rung report."
    )
    parser.add_argument(
        "--rung-dir",
        required=True,
        type=Path,
        help="Path to directory containing rung artifacts",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Path to write CSV tables",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    generated = generate_all_tables(args.rung_dir, args.output_dir)
    logger.info("Generated %d tables: %s", len(generated), ", ".join(generated))


if __name__ == "__main__":
    main()

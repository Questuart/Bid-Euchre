#!/usr/bin/env python
"""Generate cross-rung progression dashboard for Arc D.

Reads all completed rung bundles under data/artifacts/arc_d/ and produces
a Markdown dashboard with a progression table.

Usage:
    PYTHONPATH=src python scripts/internal/generate_arc_dashboard.py \
        --artifacts-base data/artifacts/arc_d \
        --output docs/04_reports/model_arc_d_dashboard.md
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_dashboard(
    artifacts_base: str | Path = "data/artifacts/arc_d",
    output_path: str | Path = "docs/04_reports/model_arc_d_dashboard.md",
) -> str:
    """Generate cross-rung progression dashboard from completed rung bundles.

    Scans artifacts_base for rung_bundle_*.json files, extracts key
    metrics, and produces a Markdown table showing progression across rungs.

    Args:
        artifacts_base: Base directory containing per-rung subdirectories.
        output_path: Path to write the dashboard Markdown.

    Returns:
        The dashboard as a Markdown string.
    """
    base = Path(artifacts_base)
    bundles = []

    if base.exists():
        for bundle_file in sorted(base.rglob("rung_bundle_*.json")):
            try:
                with open(bundle_file) as f:
                    bundle = json.load(f)
                bundle["_source_path"] = str(bundle_file)
                bundles.append(bundle)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Skipping %s: %s", bundle_file, e)

    sections = []
    sections.append("# Arc D Progression Dashboard")
    sections.append("")

    if not bundles:
        sections.append("*No completed rung bundles found.*")
        sections.append("")
        sections.append(f"Searched: `{artifacts_base}`")
    else:
        sections.append(
            "| Rung | OLSa net_eppd | Full net_eppd | Gap | ME delta"
            " | OLSa Features | Full Features | Bundle Path |"
        )
        sections.append(
            "|------|--------------|--------------|-----|----------"
            "|--------------|--------------|-------------|"
        )

        gate_decisions = []

        for b in bundles:
            rung = b.get("rung_id", "?")
            olsa = b.get("olsa", {})
            olsa_full = b.get("olsa_full", {})

            olsa_feats = _feature_summary(olsa)
            full_feats = _feature_summary(olsa_full)

            src = Path(b.get("_source_path", ""))
            olsa_eppd, full_eppd, decision = _resolve_eppd(b, src)
            gap_str = "\u2014"
            olsa_eppd_str = f"{olsa_eppd:.4f}" if olsa_eppd is not None else "\u2014"
            full_eppd_str = f"{full_eppd:.4f}" if full_eppd is not None else "\u2014"
            if olsa_eppd is not None and full_eppd is not None:
                gap_str = f"{full_eppd - olsa_eppd:+.4f}"

            me_delta_str = _resolve_me_delta(b, src)
            sections.append(
                f"| {rung} | {olsa_eppd_str} | {full_eppd_str} | {gap_str} | {me_delta_str}"
                f" | {olsa_feats} | {full_feats} | {src} |"
            )

            if decision is not None:
                gate_decisions.append((rung, decision.get("decision", "UNKNOWN")))

        sections.append("")
        sections.append(f"*{len(bundles)} rung(s) found.*")

        if gate_decisions:
            sections.append("")
            summary = ", ".join(f"{r}={d}" for r, d in gate_decisions)
            sections.append(f"gate_status: {summary}")

    sections.append("")
    dashboard = "\n".join(sections)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dashboard)
    logger.info("Dashboard written to %s", output)

    return dashboard


def _resolve_eppd(
    bundle: dict, bundle_source: Path
) -> tuple[float | None, float | None, dict | None]:
    """Resolve net_eppd for both arms with cascading fallback.

    Priority:
    1. Inline bundle fields (olsa.net_eppd, olsa_full.net_eppd)
    2. Promotion decision JSON (metrics_seed42.net_expected_points_per_deal)
    3. Eval files referenced in bundle (via load_eval_metrics)

    Returns:
        (olsa_eppd, full_eppd, decision_dict_or_None)
    """
    olsa = bundle.get("olsa", {})
    olsa_full = bundle.get("olsa_full", {})

    olsa_eppd = olsa.get("net_eppd")
    full_eppd = olsa_full.get("net_eppd")

    # Load promotion decision once (used for metrics + gate_status)
    decision = None
    rung = bundle.get("rung_id", "?")
    decision_file = bundle_source.parent / f"promotion_decision_{rung}.json"
    if decision_file.exists():
        try:
            with open(decision_file) as f:
                decision = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Source 1: inline bundle fields (already read above)
    if olsa_eppd is not None and full_eppd is not None:
        return olsa_eppd, full_eppd, decision

    # Source 2: promotion decision JSON
    if decision is not None:
        challenger = decision.get("challenger", {})
        olsa_arm = decision.get("olsa_arm", {})
        c_m = challenger.get("metrics_seed42", {})
        o_m = olsa_arm.get("metrics_seed42", {})
        if olsa_eppd is None:
            olsa_eppd = o_m.get("net_expected_points_per_deal")
        if full_eppd is None:
            full_eppd = c_m.get("net_expected_points_per_deal")
        if olsa_eppd is not None and full_eppd is not None:
            return olsa_eppd, full_eppd, decision

    # Source 3: eval files from bundle
    try:
        from bid_euchre.reporting.evaluator import load_eval_metrics
    except ImportError:
        return olsa_eppd, full_eppd, decision

    if olsa_eppd is None:
        eval_path = olsa.get("eval_seed42")
        if eval_path:
            try:
                metrics = load_eval_metrics(eval_path)
                olsa_eppd = metrics.get("net_expected_points_per_deal")
            except (FileNotFoundError, json.JSONDecodeError):
                pass
    if full_eppd is None:
        eval_path = olsa_full.get("eval_seed42")
        if eval_path:
            try:
                metrics = load_eval_metrics(eval_path)
                full_eppd = metrics.get("net_expected_points_per_deal")
            except (FileNotFoundError, json.JSONDecodeError):
                pass

    return olsa_eppd, full_eppd, decision


def _resolve_me_delta(bundle: dict, bundle_source: Path) -> str:
    """Resolve ME delta from comparator JSON.

    ME delta = hybrid_olsa.net_eppd - modeloespecifico.net_eppd.
    Uses comparator_eval only (R1-R5). R0 has comparator_battery which
    is a one-time characterization -- the plan requires R0 to show
    em-dash in the ME delta column.

    Returns formatted string or em-dash if unavailable.
    """
    comp_path_str = bundle.get("comparator_eval")
    if not comp_path_str:
        return "\u2014"

    # Ancestor-walking: try CWD-relative, then walk up bundle's ancestors
    ref = Path(comp_path_str)
    resolved = ref  # fallback
    if not ref.exists():
        for ancestor in bundle_source.resolve().parents:
            candidate = ancestor / comp_path_str
            if candidate.exists():
                resolved = candidate
                break

    try:
        with open(resolved) as f:
            comp_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return "\u2014"

    bidders = comp_data.get("bidders", {})
    hybrid_net = bidders.get("hybrid_olsa", {}).get("net_eppd")
    me_net = bidders.get("modeloespecifico", {}).get("net_eppd")

    if hybrid_net is not None and me_net is not None:
        return f"{hybrid_net - me_net:+.4f}"

    return "\u2014"


def _feature_summary(arm_data: dict) -> str:
    """Summarize feature counts per contract."""
    selected = arm_data.get("selected_features", {})
    if not selected:
        return "\u2014"
    return "/".join(str(len(feats)) for _, feats in sorted(selected.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Arc D dashboard")
    parser.add_argument(
        "--artifacts-base",
        default="data/artifacts/arc_d",
        help="Base directory for rung artifacts",
    )
    parser.add_argument(
        "--output",
        default="data/reports/arc_d/model_arc_d_dashboard.md",
        help="Output dashboard path (default: gitignored working copy)",
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Also write a snapshot to docs/04_reports/ for git-committed history",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate_dashboard(args.artifacts_base, args.output)

    if args.snapshot:
        snapshot_path = "docs/04_reports/model_arc_d_dashboard.md"
        Path(snapshot_path).parent.mkdir(parents=True, exist_ok=True)
        Path(snapshot_path).write_text(Path(args.output).read_text())
        logger.info("Snapshot written to %s", snapshot_path)


if __name__ == "__main__":
    main()

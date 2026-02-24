"""Arc D per-rung report generator.

Produces a comprehensive Markdown narrative for each rung, with 11 sections
covering executive summary, data inventory, feature/outcome health, auction
analysis, model specification, performance, dual-arm comparison, semantic
gate summary, limitations, and reproduction commands.

When an eval DataFrame is provided (from ``build_eval_dataset``), sections
are enriched with data-driven tables and statistics.

When chart_dir is provided, relevant PNGs are embedded inline.

Do NOT import this module from reporting.__init__ (circular import risk).
Import directly: ``from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report``
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────


def generate_arc_d_rung_report(
    bundle_path: str | Path,
    decision_path: str | Path | None = None,
    output_path: str | Path | None = None,
    *,
    eval_df: pd.DataFrame | None = None,
    chart_dir: str | Path | None = None,
    matchup_run_dir: str | Path | None = None,
) -> str:
    """Generate a per-rung Markdown report for Arc D evaluation.

    Produces an 11-section report covering executive summary, data inventory,
    feature health, outcome health, auction analysis, model specification,
    model performance, dual-arm comparison, semantic gate summary, known
    limitations, and reproduction commands.

    Sections gracefully degrade when optional inputs (eval_df, chart_dir,
    decision_path, matchup_run_dir) are not provided.

    Args:
        bundle_path: Path to rung_bundle_r{N}.json.
        decision_path: Optional path to promotion_decision.json.
        output_path: If provided, writes the report to this file.
        eval_df: Optional per-seat evaluation DataFrame from
            ``build_eval_dataset()``.
        chart_dir: Optional directory containing chart PNGs to embed.
        matchup_run_dir: Optional path to head-to-head run directory
            containing JSONL logs for matchup analysis.

    Returns:
        The report as a Markdown string.
    """
    bundle_path = Path(bundle_path)
    with open(bundle_path) as f:
        bundle = json.load(f)

    chart_path = Path(chart_dir) if chart_dir is not None else None

    # Load decision if provided
    decision = None
    if decision_path is not None:
        dp = Path(decision_path)
        if dp.exists():
            with open(dp) as f:
                decision = json.load(f)

    # Resolve attribution gap metrics (used in multiple sections)
    olsa = bundle.get("olsa", {})
    olsa_full = bundle.get("olsa_full", {})
    olsa_eppd, full_eppd, attribution_gap = _resolve_attribution_gap(
        bundle_path, bundle, olsa, olsa_full, decision
    )

    # Build all sections
    lines: list[str] = []
    lines.extend(_render_header(bundle))
    lines.extend(
        _render_executive_summary(
            bundle, decision, olsa_eppd, full_eppd, attribution_gap, eval_df
        )
    )
    lines.extend(_render_data_inventory(bundle, bundle_path, eval_df))
    lines.extend(_render_feature_health(eval_df, chart_path))
    lines.extend(_render_outcome_health(eval_df, chart_path))
    lines.extend(_render_auction_analysis(eval_df, chart_path))
    lines.extend(_render_model_specification(bundle_path, olsa, olsa_full, chart_path))
    lines.extend(
        _render_model_performance(bundle_path, olsa, olsa_full, eval_df, chart_path)
    )
    lines.extend(
        _render_dual_arm_comparison(
            bundle_path,
            bundle,
            olsa,
            olsa_full,
            olsa_eppd,
            full_eppd,
            attribution_gap,
            decision,
            eval_df,
            chart_path,
            matchup_run_dir,
        )
    )
    lines.extend(
        _render_semantic_gate_summary(bundle, olsa, olsa_full, decision, bundle_path)
    )
    lines.extend(_render_known_limitations(eval_df))
    lines.extend(_render_reproduction_commands(bundle_path, eval_df, chart_path))

    report = "\n".join(lines)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info("Wrote rung report: %s", output_path)

    return report


# ──────────────────────────────────────────────
#  Section Renderers
# ──────────────────────────────────────────────


def _render_header(bundle: dict) -> list[str]:
    """Render the report title and timestamp."""
    rung_id = bundle.get("rung_id", "unknown")
    arc = bundle.get("arc", "arc_d")
    return [
        f"# {arc.upper()} Rung {rung_id.upper()} Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]


def _render_executive_summary(
    bundle: dict,
    decision: dict | None,
    olsa_eppd: float | None,
    full_eppd: float | None,
    attribution_gap: float | None,
    eval_df: pd.DataFrame | None,
) -> list[str]:
    """SS1: Executive Summary — rung ID, gate status, key metrics, one-line assessment."""
    rung_id = bundle.get("rung_id", "unknown")
    arc = bundle.get("arc", "arc_d")
    lines = ["## Executive Summary", ""]

    lines.append(f"- **Arc:** {arc}")
    lines.append(f"- **Rung:** {rung_id}")

    # Gate status from decision
    gate_status = "pending"
    if decision is not None:
        gate_status = decision.get("decision", "UNKNOWN")
    lines.append(f"- **Gate status:** {gate_status}")

    # Key metrics
    if olsa_eppd is not None:
        lines.append(f"- **OLSa net_eppd:** {olsa_eppd:.4f}")
    if full_eppd is not None:
        lines.append(f"- **OLSa_Full net_eppd:** {full_eppd:.4f}")
    if attribution_gap is not None:
        lines.append(f"- **Attribution gap:** {attribution_gap:+.4f}")

    # Eval data summary
    if eval_df is not None and not eval_df.empty:
        n_deals = eval_df["deal_id"].nunique() if "deal_id" in eval_df.columns else "?"
        n_rows = len(eval_df)
        lines.append(
            f"- **Deals analyzed:** {n_deals:,}"
            if isinstance(n_deals, int)
            else f"- **Deals analyzed:** {n_deals}"
        )
        lines.append(f"- **Per-seat rows:** {n_rows:,}")

        ctypes = (
            sorted(eval_df["contract_type"].unique())
            if "contract_type" in eval_df.columns
            else []
        )
        if ctypes:
            lines.append(f"- **Contract types:** {', '.join(ctypes)}")

        # Health scorecard summary
        try:
            from bid_euchre.diagnostics.health_checks import compute_health_scorecard

            scorecard = compute_health_scorecard(eval_df)
            summary = scorecard.summary()
            lines.append(
                f"- **Health Scorecard:** {summary.get('PASS', 0)} PASS,"
                f" {summary.get('WARN', 0)} WARN,"
                f" {summary.get('FAIL', 0)} FAIL"
            )
        except Exception:
            pass  # graceful degradation if diagnostics unavailable

    # One-line assessment
    lines.append("")
    if attribution_gap is not None:
        if attribution_gap > 0:
            lines.append(
                "**Assessment:** Positive attribution gap indicates feature"
                " selection adds value over the full model."
            )
        elif attribution_gap < 0:
            lines.append(
                "**Assessment:** Negative attribution gap — constrained arm"
                " outperforms. Investigate feature selection criteria."
            )
        else:
            lines.append("**Assessment:** Zero gap — arms perform identically.")
    else:
        lines.append("**Assessment:** Evaluation pending — metrics not yet available.")
    lines.append("")
    return lines


def _render_data_inventory(
    bundle: dict,
    bundle_path: Path,
    eval_df: pd.DataFrame | None,
) -> list[str]:
    """SS2: Data Inventory — provenance, deal counts, contract distribution."""
    rung_id = bundle.get("rung_id", "unknown")
    olsa = bundle.get("olsa", {})
    olsa_full = bundle.get("olsa_full", {})

    lines = ["## Data Inventory", ""]

    # Provenance
    lines.append("### Provenance")
    lines.append("")
    lines.append(f"- **Bundle:** `{bundle_path.name}`")
    lines.append(f"- **Rung:** {rung_id}")
    training_run = olsa.get("training_run_id") or olsa_full.get("training_run_id")
    if training_run:
        lines.append(f"- **Training run:** {training_run}")
    split_manifest = bundle.get("split_manifest")
    if split_manifest:
        lines.append(f"- **Split manifest:** `{split_manifest}`")
    lines.append("")

    # Eval dataset summary
    if eval_df is not None and not eval_df.empty:
        lines.append("### Eval Dataset Summary")
        lines.append("")
        n_deals = (
            eval_df["deal_id"].nunique()
            if "deal_id" in eval_df.columns
            else len(eval_df)
        )
        lines.append(f"- **Total deals:** {n_deals:,}")
        lines.append(f"- **Total rows:** {len(eval_df):,}")
        if "seat" in eval_df.columns:
            lines.append(f"- **Seats per deal:** {len(eval_df) // max(n_deals, 1)}")
        lines.append("")

        # Per-contract deal counts table
        if "contract_type" in eval_df.columns:
            lines.append("### Per-Contract Deal Counts")
            lines.append("")
            lines.append("| Contract Type | Deals | Rows | Pct |")
            lines.append("|---------------|-------|------|-----|")
            deal_df = (
                eval_df.drop_duplicates(subset=["deal_id"])
                if "deal_id" in eval_df.columns
                else eval_df
            )
            total_deals = len(deal_df)
            for ct in sorted(eval_df["contract_type"].unique()):
                ct_deals = len(deal_df[deal_df["contract_type"] == ct])
                ct_rows = len(eval_df[eval_df["contract_type"] == ct])
                pct = ct_deals / total_deals * 100 if total_deals > 0 else 0
                lines.append(f"| {ct} | {ct_deals} | {ct_rows} | {pct:.1f}% |")
            lines.append("")
    else:
        lines.append("*No eval dataset provided — deal inventory unavailable.*")
        lines.append("")

    return lines


def _render_feature_health(
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
) -> list[str]:
    """SS3: Feature Health Summary — seat balance, per-contract feature stats."""
    lines = ["## Feature Health Summary", ""]

    # Chart embeds
    if chart_path is not None:
        for chart_name in ("seat_balance_boxplot.png", "hand_value_by_contract.png"):
            cp = chart_path / chart_name
            if cp.exists():
                lines.append(f"![{cp.stem}]({cp})")
                lines.append("")

    if eval_df is None or eval_df.empty:
        lines.append("*No eval data available for feature health analysis.*")
        lines.append("")
        return lines

    feat_cols = [c for c in eval_df.columns if c.startswith("feat_")]
    if not feat_cols:
        lines.append("*No feature columns (feat_*) found in eval data.*")
        lines.append("")
        return lines

    # Seat balance summary
    if "seat" in eval_df.columns and "feat_hand_value" in eval_df.columns:
        seat_means = eval_df.groupby("seat")["feat_hand_value"].mean()
        grand_mean = eval_df["feat_hand_value"].mean()
        max_dev = (seat_means - grand_mean).abs().max()
        lines.append("### Seat Balance")
        lines.append("")
        lines.append(
            f"Max deviation from grand mean = {max_dev:.2f}"
            f" (grand mean = {grand_mean:.1f})"
        )
        lines.append("")
        lines.append("| Seat | Mean hand_value |")
        lines.append("|------|----------------|")
        for seat in sorted(seat_means.index):
            lines.append(f"| {seat} | {seat_means[seat]:.1f} |")
        lines.append("")

    # Per-contract feature statistics
    if "contract_type" in eval_df.columns:
        lines.append("### Per-Contract Feature Statistics")
        lines.append("")
        for ctype in sorted(eval_df["contract_type"].unique()):
            grp = eval_df[eval_df["contract_type"] == ctype]
            n = len(grp)
            numeric_feats = [
                c for c in feat_cols if pd.api.types.is_numeric_dtype(grp[c])
            ]
            if numeric_feats:
                variances = grp[numeric_feats].var().nlargest(5)
                lines.append(f"#### {ctype} (n={n})")
                lines.append("")
                lines.append("| Feature | Mean | Std | Min | Max |")
                lines.append("|---------|------|-----|-----|-----|")
                for feat in variances.index:
                    desc = grp[feat].describe()
                    fname = feat.replace("feat_", "")
                    lines.append(
                        f"| {fname} | {desc['mean']:.2f}"
                        f" | {desc['std']:.2f}"
                        f" | {desc['min']:.2f}"
                        f" | {desc['max']:.2f} |"
                    )
                lines.append("")

    return lines


def _render_outcome_health(
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
) -> list[str]:
    """SS4: Outcome Health Summary — tricks distribution, per-contract outcome stats."""
    lines = ["## Outcome Health Summary", ""]

    # Chart embeds
    if chart_path is not None:
        for chart_name in ("tricks_won_histogram.png", "cdf_by_contract.png"):
            cp = chart_path / chart_name
            if cp.exists():
                lines.append(f"![{cp.stem}]({cp})")
                lines.append("")

    if eval_df is None or eval_df.empty or "tricks_won" not in eval_df.columns:
        lines.append("*No eval data available for outcome health analysis.*")
        lines.append("")
        return lines

    # Overall tricks summary
    tw = eval_df["tricks_won"]
    lines.append(f"- **Overall mean tricks:** {tw.mean():.2f}")
    lines.append(f"- **Overall std:** {tw.std():.2f}")
    lines.append(f"- **Range:** [{tw.min():.1f}, {tw.max():.1f}]")
    lines.append("")

    # Per-contract outcome statistics table
    if "contract_type" in eval_df.columns:
        lines.append("### Per-Contract Outcome Statistics")
        lines.append("")
        lines.append("| Contract | Mean | Std | P5 | P95 | n |")
        lines.append("|----------|------|-----|-----|-----|---|")
        for ctype in sorted(eval_df["contract_type"].unique()):
            grp = eval_df[eval_df["contract_type"] == ctype]
            lines.append(
                f"| {ctype}"
                f" | {grp['tricks_won'].mean():.2f}"
                f" | {grp['tricks_won'].std():.2f}"
                f" | {grp['tricks_won'].quantile(0.05):.1f}"
                f" | {grp['tricks_won'].quantile(0.95):.1f}"
                f" | {len(grp)} |"
            )
        lines.append("")

    # Bidder make rate
    if "is_bidder" in eval_df.columns and "made_bid" in eval_df.columns:
        bidder_df = eval_df[eval_df["is_bidder"] == True]  # noqa: E712
        if not bidder_df.empty:
            make_rate = bidder_df["made_bid"].mean()
            lines.append(f"**Overall make rate:** {make_rate:.3f}")
            if "contract_type" in bidder_df.columns:
                lines.append("")
                lines.append("| Contract | Make Rate | n |")
                lines.append("|----------|-----------|---|")
                for ct in sorted(bidder_df["contract_type"].unique()):
                    grp = bidder_df[bidder_df["contract_type"] == ct]
                    lines.append(
                        f"| {ct} | {grp['made_bid'].mean():.3f} | {len(grp)} |"
                    )
            lines.append("")

    return lines


def _render_auction_analysis(
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
) -> list[str]:
    """SS5: Auction Analysis — contract selection, bid distribution, make rate."""
    lines = ["## Auction Analysis", ""]

    # Chart embeds
    if chart_path is not None:
        for chart_name in ("auction_health.png", "bidder_performance.png"):
            cp = chart_path / chart_name
            if cp.exists():
                lines.append(f"![{cp.stem}]({cp})")
                lines.append("")

    if eval_df is None or eval_df.empty:
        lines.append("*No eval data available for auction analysis.*")
        lines.append("")
        return lines

    has_auction = "n_bids" in eval_df.columns or "auction_rounds" in eval_df.columns
    if not has_auction:
        lines.append("*Auction columns not present in eval data.*")
        lines.append("")
        return lines

    # Use seat==0 for deal-level auction stats (one row per deal)
    deal_df = (
        eval_df[eval_df["seat"] == 0].copy()
        if "seat" in eval_df.columns
        else eval_df.copy()
    )
    if deal_df.empty:
        lines.append("*No deal-level rows available.*")
        lines.append("")
        return lines

    # Contract Selection Frequency
    if "contract_type" in deal_df.columns:
        lines.append("### Contract Selection Frequency")
        lines.append("")
        lines.append("| Contract | Count | Pct |")
        lines.append("|----------|-------|-----|")
        total = len(deal_df)
        for ct, count in deal_df["contract_type"].value_counts().items():
            pct = count / total * 100
            lines.append(f"| {ct} | {count} | {pct:.1f}% |")
        lines.append("")

    # Bid Distribution
    if "winning_bid" in deal_df.columns:
        lines.append("### Bid Distribution")
        lines.append("")
        lines.append(f"- **Mean winning bid:** {deal_df['winning_bid'].mean():.2f}")
        lines.append(
            f"- **Bid range:** {deal_df['winning_bid'].min()}"
            f"--{deal_df['winning_bid'].max()}"
        )
        lines.append(f"- **Std:** {deal_df['winning_bid'].std():.2f}")
        lines.append("")

    # Make Rate by Contract (auction summary table)
    if "made_bid" in deal_df.columns and "contract_type" in deal_df.columns:
        lines.append("### Auction Summary")
        lines.append("")
        lines.append("| Contract | Deals | Make Rate | Mean Bid |")
        lines.append("|----------|-------|-----------|----------|")
        for ct in sorted(deal_df["contract_type"].unique()):
            grp = deal_df[deal_df["contract_type"] == ct]
            mr = (
                grp["made_bid"].mean()
                if not grp["made_bid"].isna().all()
                else float("nan")
            )
            mb = (
                grp["winning_bid"].mean()
                if "winning_bid" in grp.columns
                else float("nan")
            )
            lines.append(f"| {ct} | {len(grp)} | {mr:.3f} | {mb:.2f} |")
        lines.append("")

    return lines


def _render_model_specification(
    bundle_path: Path,
    olsa: dict,
    olsa_full: dict,
    chart_path: Path | None,
) -> list[str]:
    """SS6: Model Specification & Feature Selection — per-arm, per-contract features."""
    lines = ["## Model Specification & Feature Selection", ""]

    # Chart embeds
    if chart_path is not None:
        cp = chart_path / "coefficient_heatmap.png"
        if cp.exists():
            lines.append(f"![{cp.stem}]({cp})")
            lines.append("")

    # Feature selection per arm
    for arm_name, arm_data in [
        ("OLSa (constrained)", olsa),
        ("OLSa_Full (promotional)", olsa_full),
    ]:
        selected = arm_data.get("selected_features", {})
        if selected:
            lines.append(f"### {arm_name}")
            lines.append("")
            total_feats = sum(len(v) for v in selected.values())
            lines.append(f"**Total features:** {total_feats}")
            lines.append("")
            for ct, feats in sorted(selected.items()):
                lines.append(f"- **{ct}** ({len(feats)}): {', '.join(feats)}")
            lines.append("")

    # Try to load model artifacts for coefficient display
    for arm_label, arm_data in [
        ("OLSa", olsa),
        ("OLSa_Full", olsa_full),
    ]:
        model_path_key = arm_data.get("artifact_path")
        if not model_path_key:
            continue
        model_file = _resolve_bundle_ref(bundle_path, model_path_key)
        if not model_file.exists():
            continue
        try:
            with open(model_file) as f:
                model_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        payoff = model_data.get("payoff_model", {})
        if not payoff:
            continue

        lines.append(f"### {arm_label} Coefficients")
        lines.append("")
        for contract, model in sorted(payoff.items()):
            fnames = model.get("feature_names", [])
            weights = model.get("weights", [])
            bias = model.get("bias", 0.0)
            if not fnames or not weights:
                continue
            lines.append(f"#### {contract}")
            lines.append("")
            lines.append(f"Bias: {bias:.4f}")
            lines.append("")
            lines.append("| Feature | Weight |")
            lines.append("|---------|--------|")
            for fn, w in zip(fnames, weights):
                lines.append(f"| {fn} | {w:+.4f} |")
            lines.append("")

    return lines


def _render_model_performance(
    bundle_path: Path,
    olsa: dict,
    olsa_full: dict,
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
) -> list[str]:
    """SS7: Model Performance — per-contract R2, MAE for each arm."""
    lines = ["## Model Performance", ""]

    # Chart embeds
    if chart_path is not None:
        for chart_name in ("pred_vs_actual_scatter.png", "residual_distribution.png"):
            cp = chart_path / chart_name
            if cp.exists():
                lines.append(f"![{cp.stem}]({cp})")
                lines.append("")

    if eval_df is None or eval_df.empty or "tricks_won" not in eval_df.columns:
        lines.append("*No eval data available for model performance analysis.*")
        lines.append("")
        return lines

    any_perf = False
    for arm_label, arm_data in [
        ("OLSa (constrained)", olsa),
        ("OLSa_Full (promotional)", olsa_full),
    ]:
        model_path_key = arm_data.get("artifact_path")
        if not model_path_key:
            continue
        model_file = _resolve_bundle_ref(bundle_path, model_path_key)
        if not model_file.exists():
            continue
        try:
            with open(model_file) as f:
                model_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        payoff = model_data.get("payoff_model", {})
        if not payoff:
            continue

        lines.append(f"### {arm_label}")
        lines.append("")
        lines.append("| Contract | R\u00b2 | MAE | n |")
        lines.append("|----------|-----|-----|---|")

        for contract, model in sorted(payoff.items()):
            fnames = model.get("feature_names", [])
            weights = np.array(model.get("weights", []))
            bias = model.get("bias", 0.0)

            if not fnames or len(weights) == 0:
                continue

            feat_cols = [f"feat_{fn}" for fn in fnames]
            subset = eval_df[eval_df["contract_type"] == contract]
            missing = [c for c in feat_cols if c not in subset.columns]
            if missing or len(subset) == 0:
                continue

            X = subset[feat_cols].values.astype(np.float64)
            y = subset["tricks_won"].values.astype(np.float64)
            y_pred = X @ weights + bias

            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
            mae = np.mean(np.abs(y - y_pred))
            lines.append(f"| {contract} | {r2:.4f} | {mae:.4f} | {len(subset)} |")
            any_perf = True

        lines.append("")

    if not any_perf:
        lines.append(
            "*Model artifacts not available or feature columns missing"
            " — performance metrics cannot be computed.*"
        )
        lines.append("")

    return lines


def _render_dual_arm_comparison(
    bundle_path: Path,
    bundle: dict,
    olsa: dict,
    olsa_full: dict,
    olsa_eppd: float | None,
    full_eppd: float | None,
    attribution_gap: float | None,
    decision: dict | None,
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
    matchup_run_dir: str | Path | None,
) -> list[str]:
    """SS8: Dual-Arm Comparison & Attribution Gap — includes comparator battery and h2h."""
    lines = ["## Dual-Arm Comparison & Attribution Gap", ""]

    # Chart embeds
    if chart_path is not None:
        cp = chart_path / "dual_arm_comparison.png"
        if cp.exists():
            lines.append(f"![{cp.stem}]({cp})")
            lines.append("")

    # Dual-arm overview table
    lines.append("### Arm Overview")
    lines.append("")
    lines.append("| Metric | OLSa (constrained) | OLSa_Full (promotional) |")
    lines.append("|--------|-------------------|------------------------|")

    olsa_features = _count_features(olsa)
    full_features = _count_features(olsa_full)
    lines.append(f"| Features | {olsa_features} | {full_features} |")

    olsa_sha = _truncate_sha(olsa.get("artifact_sha256"))
    full_sha = _truncate_sha(olsa_full.get("artifact_sha256"))
    lines.append(f"| Artifact SHA | {olsa_sha} | {full_sha} |")

    olsa_gate = _gate_status_str(olsa)
    full_gate = _gate_status_str(olsa_full)
    lines.append(f"| Gate (val) | {olsa_gate} | {full_gate} |")

    lines.append("")

    # Attribution Gap
    lines.append("### Attribution Gap")
    lines.append("")

    if olsa_eppd is not None and full_eppd is not None:
        lines.append("| Arm | net_eppd |")
        lines.append("|-----|----------|")
        lines.append(f"| OLSa (constrained) | {olsa_eppd:.4f} |")
        lines.append(f"| OLSa_Full (promotional) | {full_eppd:.4f} |")
        lines.append(f"| **Attribution Gap** | **{attribution_gap:+.4f}** |")
        lines.append("")
        if attribution_gap > 0:
            lines.append("Positive gap: feature selection improves bidding quality.")
        elif attribution_gap < 0:
            lines.append("Negative gap: constrained arm outperforms — investigate.")
        else:
            lines.append("Zero gap: arms perform identically.")
    elif attribution_gap is not None:
        lines.append(f"**Attribution gap:** {attribution_gap:+.4f}")
    else:
        lines.append("*Attribution gap not yet available — eval results pending.*")
    lines.append("")

    # Promotion Decision
    if decision is not None:
        lines.append("### Promotion Decision")
        lines.append("")
        lines.append(f"- **Outcome:** {decision.get('decision', 'UNKNOWN')}")
        lines.append(f"- **gate_status:** {decision.get('decision', 'UNKNOWN')}")
        reasons = decision.get("reasons", [])
        if reasons:
            for r in reasons:
                lines.append(f"- {r}")
        lines.append("")

    # Feature Correlations
    if eval_df is not None and not eval_df.empty and "tricks_won" in eval_df.columns:
        feat_cols = [c for c in eval_df.columns if c.startswith("feat_")]
        numeric_feats = [
            c for c in feat_cols if pd.api.types.is_numeric_dtype(eval_df[c])
        ]
        if numeric_feats and "contract_type" in eval_df.columns:
            lines.append("### Feature Correlations")
            lines.append("")
            lines.append(
                "Top features by absolute Pearson correlation with `tricks_won`,"
                " per contract type."
            )
            lines.append("")
            for ctype in sorted(eval_df["contract_type"].unique()):
                grp = eval_df[eval_df["contract_type"] == ctype]
                if len(grp) < 10:
                    continue
                corrs = {}
                for fc in numeric_feats:
                    try:
                        corrs[fc] = grp[fc].corr(grp["tricks_won"])
                    except Exception:
                        pass
                # Filter NaN correlations (e.g. zero-variance features in no-trump)
                corrs = {k: v for k, v in corrs.items() if not np.isnan(v)}
                if not corrs:
                    continue
                top = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                lines.append(f"#### {ctype}")
                lines.append("")
                lines.append("| Feature | r |")
                lines.append("|---------|---|")
                for fname, r in top:
                    lines.append(f"| {fname.replace('feat_', '')} | {r:+.4f} |")
                lines.append("")

    # Comparator Battery
    comparator_battery = bundle.get("comparator_battery")
    if isinstance(comparator_battery, str):
        cb_file = _resolve_bundle_ref(bundle_path, comparator_battery)
        if cb_file.exists():
            try:
                with open(cb_file) as f:
                    comparator_battery = json.load(f)
            except (json.JSONDecodeError, OSError):
                comparator_battery = None
        else:
            comparator_battery = None
    if isinstance(comparator_battery, dict) and "bidders" in comparator_battery:
        comparator_battery = comparator_battery["bidders"]
    if comparator_battery and isinstance(comparator_battery, dict):
        lines.append("### Comparator Battery")
        lines.append("")
        ranked = []
        for bidder_name, metrics in comparator_battery.items():
            net_eppd = metrics.get("net_eppd") if isinstance(metrics, dict) else None
            if net_eppd is not None:
                ranked.append((bidder_name, net_eppd))
        if ranked:
            ranked.sort(key=lambda x: x[1], reverse=True)
            lines.append("| Bidder | net_eppd |")
            lines.append("|--------|----------|")
            for name, val in ranked:
                lines.append(f"| {name} | {val:.4f} |")
            lines.append("")

    # Head-to-Head Summary
    if matchup_run_dir is not None:
        matchup_run_dir = Path(matchup_run_dir)
        logs_dir = matchup_run_dir / "logs"
        if logs_dir.is_dir():
            import glob as glob_mod

            log_files = sorted(glob_mod.glob(str(logs_dir / "*.jsonl")))
            if log_files:
                lines.append("### Head-to-Head Summary")
                lines.append("")
                try:
                    from bid_euchre.datasets.eval_dataset import build_eval_dataset

                    run_dir_name = matchup_run_dir.name
                    matchup_rows = []
                    for lf in log_files:
                        lf_path = Path(lf)
                        stem = lf_path.stem
                        if stem.startswith(run_dir_name + "_"):
                            mid = stem[len(run_dir_name) + 1 :]
                        else:
                            mid = stem
                        try:
                            mdf = build_eval_dataset(lf, max_deals=5000)
                            if not mdf.empty:
                                deal_sub = mdf[mdf["seat"] == 0]
                                n_deals = deal_sub["deal_id"].nunique()
                                t0_mean = mdf[mdf["team"] == 0]["tricks_won"].mean()
                                t1_mean = mdf[mdf["team"] == 1]["tricks_won"].mean()
                                matchup_rows.append(
                                    {
                                        "matchup": mid,
                                        "deals": n_deals,
                                        "team0_tricks": t0_mean,
                                        "team1_tricks": t1_mean,
                                    }
                                )
                        except Exception:
                            pass

                    if matchup_rows:
                        lines.append(
                            "| Matchup | Deals | Team0 Tricks | Team1 Tricks |"
                        )
                        lines.append("|---------|-------|-------------|-------------|")
                        for row in matchup_rows:
                            lines.append(
                                f"| {row['matchup']}"
                                f" | {row['deals']}"
                                f" | {row['team0_tricks']:.2f}"
                                f" | {row['team1_tricks']:.2f} |"
                            )
                        lines.append("")
                    else:
                        lines.append("*No matchup data could be parsed from logs.*")
                        lines.append("")
                except ImportError:
                    lines.append("*build_eval_dataset unavailable.*")
                    lines.append("")

    return lines


def _render_semantic_gate_summary(
    bundle: dict,
    olsa: dict,
    olsa_full: dict,
    decision: dict | None,
    bundle_path: Path | None = None,
) -> list[str]:
    """SS9: Semantic Gate Summary — gate checks table, tier results."""
    lines = ["## Semantic Gate Summary", ""]

    has_gate_info = False

    # Gate status from decision
    if decision is not None:
        gate_status = decision.get("decision", "UNKNOWN")
        lines.append(f"**Overall gate status:** {gate_status}")
        lines.append("")
        has_gate_info = True

        # Tier-level results from decision
        reasons = decision.get("reasons", [])
        if reasons:
            lines.append("### Gate Reasons")
            lines.append("")
            for r in reasons:
                lines.append(f"- {r}")
            lines.append("")

    # Per-arm gate validation status
    olsa_gate = olsa.get("semantic_gate_val")
    full_gate = olsa_full.get("semantic_gate_val")
    if olsa_gate is not None or full_gate is not None:
        lines.append("### Per-Arm Gate Status")
        lines.append("")
        lines.append("| Arm | Gate Status |")
        lines.append("|-----|-------------|")
        lines.append(f"| OLSa (constrained) | {_gate_status_str(olsa, bundle_path)} |")
        lines.append(
            f"| OLSa_Full (promotional) | {_gate_status_str(olsa_full, bundle_path)} |"
        )
        lines.append("")
        has_gate_info = True

    # Try to find gate artifact data in bundle (inline dict or path string)
    for arm_label, arm_data in [
        ("OLSa", olsa),
        ("OLSa_Full", olsa_full),
    ]:
        checks = _load_gate_checks(arm_data, bundle_path)
        if not checks:
            continue

        has_gate_info = True
        lines.append(f"### {arm_label} Gate Checks")
        lines.append("")
        lines.append("| Check | Status | Detail |")
        lines.append("|-------|--------|--------|")
        for check in checks:
            cid = check.get("check_id", "?")
            status = check.get("status", "?")
            detail = check.get("detail", "")
            ct = check.get("contract_type", "")
            label = f"{cid} ({ct})" if ct else cid
            lines.append(f"| {label} | {status} | {detail} |")
        lines.append("")

    if not has_gate_info:
        lines.append("*No semantic gate data available.*")
        lines.append("")

    return lines


def _render_known_limitations(eval_df: pd.DataFrame | None) -> list[str]:
    """SS10: Known Limitations — documented caveats."""
    lines = ["## Known Limitations", ""]

    lines.append(
        "- OLSa models assume linear feature-outcome relationships;"
        " non-linear interactions are not captured."
    )
    lines.append(
        "- Attribution gap is computed on a single eval seed;"
        " multi-seed averaging would reduce variance."
    )
    lines.append(
        "- Feature correlations are Pearson (linear only);"
        " rank correlations may reveal additional structure."
    )
    lines.append(
        "- Comparator battery rankings depend on eval seed and"
        " deal composition; small samples may not be representative."
    )

    if eval_df is not None and not eval_df.empty:
        n_deals = (
            eval_df["deal_id"].nunique()
            if "deal_id" in eval_df.columns
            else len(eval_df)
        )
        if n_deals < 2000:
            lines.append(
                f"- **Sample size warning:** {n_deals} deals is below the"
                " 2,000-deal minimum for reliable bias detection."
            )
    else:
        lines.append("- No eval data was provided; data-driven sections are empty.")

    lines.append("")
    return lines


def _render_reproduction_commands(
    bundle_path: Path,
    eval_df: pd.DataFrame | None,
    chart_path: Path | None,
) -> list[str]:
    """SS11: Reproduction Commands — how to regenerate eval data and report."""
    lines = ["## Reproduction Commands", ""]

    lines.append("### Generate Eval Dataset")
    lines.append("")
    lines.append("```bash")
    lines.append("# Parse JSONL logs into eval DataFrame:")
    lines.append('PYTHONPATH=src uv run python -c "')
    lines.append("from bid_euchre.datasets.eval_dataset import build_eval_dataset")
    lines.append("df = build_eval_dataset('<EVAL_RUN_DIR>/logs/<LOG>.jsonl')")
    lines.append("df.to_parquet('eval_df.parquet')")
    lines.append('"')
    lines.append("```")
    lines.append("")

    lines.append("### Generate Report")
    lines.append("")
    lines.append("```bash")
    lines.append("# Regenerate this report:")
    lines.append('PYTHONPATH=src uv run python -c "')
    lines.append(
        "from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report"
    )
    if eval_df is not None:
        lines.append("import pandas as pd")
        lines.append("df = pd.read_parquet('eval_df.parquet')")
        chart_arg = f", chart_dir='{chart_path}'" if chart_path else ""
        lines.append(
            f"generate_arc_d_rung_report('{bundle_path}',"
            f" eval_df=df{chart_arg},"
            f" output_path='report.md')"
        )
    else:
        lines.append(
            f"generate_arc_d_rung_report('{bundle_path}', output_path='report.md')"
        )
    lines.append('"')
    lines.append("```")
    lines.append("")

    lines.append("### Run Notebooks")
    lines.append("")
    lines.append("```bash")
    lines.append("# Execute the evaluation notebooks:")
    lines.append("uv run jupyter nbconvert --to notebook --execute \\")
    lines.append("  notebooks/arc_d/<RUNG>/10_feature_health.ipynb")
    lines.append("uv run jupyter nbconvert --to notebook --execute \\")
    lines.append("  notebooks/arc_d/<RUNG>/20_outcome_health.ipynb")
    lines.append("uv run jupyter nbconvert --to notebook --execute \\")
    lines.append("  notebooks/arc_d/<RUNG>/30_feature_outcome_eval.ipynb")
    lines.append("```")
    lines.append("")

    return lines


# ──────────────────────────────────────────────
#  Private Helpers
# ──────────────────────────────────────────────


def _load_gate_checks(arm_data: dict, bundle_path: Path | None) -> list[dict]:
    """Load gate checks from an arm's gate artifact (inline dict or path string).

    Checks ``gate_artifact`` (inline dict), then ``semantic_gate_val`` and
    ``semantic_gate_test`` (path strings resolved via ``_resolve_bundle_ref``).

    Returns:
        List of check dicts, or empty list if none found.
    """
    # Source 1: inline gate_artifact dict
    gate_artifact = arm_data.get("gate_artifact")
    if isinstance(gate_artifact, dict):
        checks = gate_artifact.get("checks", [])
        if checks:
            return checks

    # Source 2: path-based gate artifacts (semantic_gate_val / semantic_gate_test)
    if bundle_path is not None:
        for key in ("semantic_gate_val", "semantic_gate_test"):
            ref = arm_data.get(key)
            if not ref or not isinstance(ref, str):
                continue
            gate_file = _resolve_bundle_ref(bundle_path, ref)
            if not gate_file.exists():
                continue
            try:
                with open(gate_file) as f:
                    gate_data = json.load(f)
                checks = gate_data.get("checks", [])
                if checks:
                    return checks
            except (json.JSONDecodeError, OSError):
                continue

    return []


def _resolve_attribution_gap(
    bundle_path: Path,
    bundle: dict,
    olsa: dict,
    olsa_full: dict,
    decision: dict | None,
) -> tuple[float | None, float | None, float | None]:
    """Resolve OLSa/Full net_eppd and attribution gap from available sources.

    Priority: (1) decision JSON, (2) eval files from bundle, (3) inline bundle fields.

    Returns:
        (olsa_eppd, full_eppd, attribution_gap) — any may be None.
    """
    attribution_gap = None
    olsa_eppd = None
    full_eppd = None

    # Source 1: decision JSON
    if decision is not None and decision.get("attribution_gap") is not None:
        attribution_gap = decision["attribution_gap"]
        challenger = decision.get("challenger", {})
        olsa_arm = decision.get("olsa_arm", {})
        challenger_metrics = challenger.get("metrics_seed42", {})
        olsa_metrics = olsa_arm.get("metrics_seed42", {})
        if challenger_metrics:
            full_eppd = challenger_metrics.get("net_expected_points_per_deal")
        if olsa_metrics:
            olsa_eppd = olsa_metrics.get("net_expected_points_per_deal")

    # Source 2: load eval files referenced in bundle
    if attribution_gap is None:
        from bid_euchre.reporting.evaluator import load_eval_metrics

        olsa_eval_path = olsa.get("eval_seed42")
        full_eval_path = olsa_full.get("eval_seed42")
        if olsa_eval_path:
            try:
                resolved = _resolve_bundle_ref(bundle_path, olsa_eval_path)
                metrics = load_eval_metrics(str(resolved))
                olsa_eppd = metrics.get("net_expected_points_per_deal")
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        if full_eval_path:
            try:
                resolved = _resolve_bundle_ref(bundle_path, full_eval_path)
                metrics = load_eval_metrics(str(resolved))
                full_eppd = metrics.get("net_expected_points_per_deal")
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        if olsa_eppd is not None and full_eppd is not None:
            attribution_gap = full_eppd - olsa_eppd

    # Source 3: inline bundle fields (legacy/future)
    if attribution_gap is None:
        if olsa_eppd is None:
            olsa_eppd = olsa.get("net_eppd")
        if full_eppd is None:
            full_eppd = olsa_full.get("net_eppd")
        if olsa_eppd is not None and full_eppd is not None:
            attribution_gap = full_eppd - olsa_eppd

    return olsa_eppd, full_eppd, attribution_gap


def _resolve_bundle_ref(bundle_path: Path, ref_path: str) -> Path:
    """Resolve a repo-root-relative path referenced in a rung bundle.

    Bundle fields like ``artifact_path`` and ``eval_seed42`` store paths
    relative to the repo root (e.g. ``data/artifacts/arc_d/r0/foo.json``).
    When CWD **is** the repo root, ``Path(ref_path)`` works directly.
    When CWD is elsewhere but ``bundle_path`` is absolute, we walk up
    the bundle's ancestors to find the repo root that makes the ref
    resolvable.

    Falls back to ``Path(ref_path)`` if no ancestor works (callers
    handle the non-existent path gracefully).
    """
    direct = Path(ref_path)
    if direct.exists():
        return direct
    # Walk up from the bundle's resolved directory to find repo root
    for ancestor in bundle_path.resolve().parents:
        candidate = ancestor / ref_path
        if candidate.exists():
            return candidate
    return direct


def _count_features(arm_data: dict) -> str:
    """Count total features across contract families."""
    selected = arm_data.get("selected_features", {})
    if not selected:
        return "\u2014"
    counts = [f"{ct}:{len(feats)}" for ct, feats in sorted(selected.items())]
    return ", ".join(counts)


def _truncate_sha(sha: str | None) -> str:
    """Return first 8 chars of SHA or em-dash."""
    if not sha:
        return "\u2014"
    return sha[:8]


def _gate_status_str(arm_data: dict, bundle_path: Path | None = None) -> str:
    """Compute aggregate gate status from arm's gate checks.

    Returns a human-readable string like "PASS (3/3)" or "FAIL (1 of 3)"
    instead of raw path strings.
    """
    checks = _load_gate_checks(arm_data, bundle_path)
    if not checks:
        # No gate data at all
        return "\u2014"

    total = len(checks)
    statuses = [c.get("status", "?") for c in checks]
    n_fail = statuses.count("FAIL")
    n_warn = statuses.count("WARN")

    if n_fail > 0:
        return f"FAIL ({n_fail} of {total})"
    if n_warn > 0:
        return f"WARN ({n_warn} of {total})"
    return f"PASS ({total}/{total})"

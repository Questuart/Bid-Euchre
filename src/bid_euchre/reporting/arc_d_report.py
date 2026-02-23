"""Arc D per-rung report generator.

Produces a Markdown narrative for each rung, comparing dual-arm
(OLSa constrained vs. OLSa_Full) evaluation results and summarizing
feature selection, attribution gap, and gate outcomes.

When an eval DataFrame is provided (from ``build_eval_dataset``), the
report includes rich data-driven sections: deal health, auction analysis,
gameplay analysis, model performance, and enhanced metrics.

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

    Reads the rung bundle and optional promotion decision, then produces
    a dual-arm comparison narrative with feature selection summary,
    attribution gap, and gate outcomes.

    When *eval_df* is provided, adds data-driven sections for deal health,
    auction analysis, gameplay analysis, model performance, feature
    correlations, and health scorecard summary.

    When *matchup_run_dir* is provided, adds a head-to-head summary
    section with win rates and competitive ranking from JSONL logs.

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

    rung_id = bundle.get("rung_id", "unknown")
    arc = bundle.get("arc", "arc_d")

    sections = []

    # --- Header ---
    sections.append(f"# {arc.upper()} Rung {rung_id.upper()} Report")
    sections.append("")
    sections.append(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    sections.append("")

    # --- Executive Summary (when eval_df available) ---
    if eval_df is not None and not eval_df.empty:
        sections.append("## Executive Summary")
        sections.append("")
        n_deals = eval_df["deal_id"].nunique()
        n_rows = len(eval_df)
        ctypes = (
            sorted(eval_df["contract_type"].unique())
            if "contract_type" in eval_df.columns
            else []
        )
        sections.append(f"- **Deals analyzed:** {n_deals:,}")
        sections.append(f"- **Per-seat rows:** {n_rows:,}")
        if ctypes:
            sections.append(f"- **Contract types:** {', '.join(ctypes)}")

        # Health scorecard summary
        try:
            from bid_euchre.diagnostics.health_checks import compute_health_scorecard

            scorecard = compute_health_scorecard(eval_df)
            summary = scorecard.summary()
            sections.append(
                f"- **Health Scorecard:** {summary.get('PASS', 0)} PASS,"
                f" {summary.get('WARN', 0)} WARN,"
                f" {summary.get('FAIL', 0)} FAIL"
            )
        except Exception:
            pass  # graceful degradation if diagnostics unavailable
        sections.append("")

    # --- Data Provenance ---
    if eval_df is not None:
        sections.append("## Data Provenance")
        sections.append("")
        sections.append(f"- **Bundle:** `{bundle_path.name}`")
        sections.append(f"- **Rung:** {rung_id}")
        training_run = bundle.get("olsa", {}).get("training_run_id") or bundle.get(
            "olsa_full", {}
        ).get("training_run_id")
        if training_run:
            sections.append(f"- **Training run:** {training_run}")
        sections.append("")

    # --- Dual-arm comparison table ---
    sections.append("## Dual-Arm Comparison")
    sections.append("")
    sections.append("| Metric | OLSa (constrained) | OLSa_Full (promotional) |")
    sections.append("|--------|-------------------|------------------------|")

    olsa = bundle.get("olsa", {})
    olsa_full = bundle.get("olsa_full", {})

    # Feature counts
    olsa_features = _count_features(olsa)
    full_features = _count_features(olsa_full)
    sections.append(f"| Features | {olsa_features} | {full_features} |")

    # Artifact SHA (truncated)
    olsa_sha = _truncate_sha(olsa.get("artifact_sha256"))
    full_sha = _truncate_sha(olsa_full.get("artifact_sha256"))
    sections.append(f"| Artifact SHA | {olsa_sha} | {full_sha} |")

    # Gate status
    olsa_gate = _gate_status_str(olsa)
    full_gate = _gate_status_str(olsa_full)
    sections.append(f"| Gate (val) | {olsa_gate} | {full_gate} |")

    sections.append("")

    # --- Feature selection summary ---
    sections.append("## Feature Selection")
    sections.append("")
    for arm_name, arm_data in [
        ("OLSa (constrained)", olsa),
        ("OLSa_Full (promotional)", olsa_full),
    ]:
        selected = arm_data.get("selected_features", {})
        if selected:
            sections.append(f"### {arm_name}")
            for ct, feats in sorted(selected.items()):
                sections.append(f"- **{ct}**: {', '.join(feats)}")
            sections.append("")

    # --- Deal Health (when eval_df available) ---
    if eval_df is not None and not eval_df.empty:
        sections.append("## Deal Health")
        sections.append("")

        feat_cols = [c for c in eval_df.columns if c.startswith("feat_")]
        if feat_cols and "contract_type" in eval_df.columns:
            for ctype in sorted(eval_df["contract_type"].unique()):
                grp = eval_df[eval_df["contract_type"] == ctype]
                n = len(grp)
                # Top 5 features by variance
                numeric_feats = [
                    c for c in feat_cols if pd.api.types.is_numeric_dtype(grp[c])
                ]
                if numeric_feats:
                    variances = grp[numeric_feats].var().nlargest(5)
                    sections.append(f"### {ctype} (n={n})")
                    sections.append("")
                    sections.append("| Feature | Mean | Std | Min | Max |")
                    sections.append("|---------|------|-----|-----|-----|")
                    for feat in variances.index:
                        desc = grp[feat].describe()
                        fname = feat.replace("feat_", "")
                        sections.append(
                            f"| {fname} | {desc['mean']:.2f}"
                            f" | {desc['std']:.2f}"
                            f" | {desc['min']:.2f}"
                            f" | {desc['max']:.2f} |"
                        )
                    sections.append("")

        # Seat balance summary
        if "seat" in eval_df.columns and "feat_hand_value" in eval_df.columns:
            seat_means = eval_df.groupby("seat")["feat_hand_value"].mean()
            grand_mean = eval_df["feat_hand_value"].mean()
            max_dev = (seat_means - grand_mean).abs().max()
            sections.append(
                f"**Seat balance:** max deviation from grand mean ="
                f" {max_dev:.2f} (grand mean = {grand_mean:.1f})"
            )
            sections.append("")

    # --- Auction Analysis (when eval_df from logs) ---
    if (
        eval_df is not None
        and not eval_df.empty
        and "n_bids" in eval_df.columns
        and "auction_rounds" in eval_df.columns
    ):
        sections.append("## Auction Analysis")
        sections.append("")

        deal_df = eval_df[eval_df["seat"] == 0].copy()
        if not deal_df.empty:
            if "contract_type" in deal_df.columns:
                sections.append("### Contract Selection")
                sections.append("")
                sections.append("| Contract | Count | Pct |")
                sections.append("|----------|-------|-----|")
                total = len(deal_df)
                for ct, count in deal_df["contract_type"].value_counts().items():
                    pct = count / total * 100
                    sections.append(f"| {ct} | {count} | {pct:.1f}% |")
                sections.append("")

            if "winning_bid" in deal_df.columns:
                sections.append("### Bid Distribution")
                sections.append("")
                sections.append(
                    f"- Mean winning bid: {deal_df['winning_bid'].mean():.2f}"
                )
                sections.append(
                    f"- Bid range: {deal_df['winning_bid'].min()}"
                    f"-{deal_df['winning_bid'].max()}"
                )
                sections.append("")

    # --- Gameplay Analysis (when eval_df available) ---
    if eval_df is not None and not eval_df.empty and "tricks_won" in eval_df.columns:
        sections.append("## Gameplay Analysis")
        sections.append("")

        if "contract_type" in eval_df.columns:
            sections.append("### Tricks Won by Contract Type")
            sections.append("")
            sections.append("| Contract | Mean | Std | 5th Pctl | 95th Pctl |")
            sections.append("|----------|------|-----|----------|-----------|")
            for ctype in sorted(eval_df["contract_type"].unique()):
                grp = eval_df[eval_df["contract_type"] == ctype]
                sections.append(
                    f"| {ctype}"
                    f" | {grp['tricks_won'].mean():.2f}"
                    f" | {grp['tricks_won'].std():.2f}"
                    f" | {grp['tricks_won'].quantile(0.05):.1f}"
                    f" | {grp['tricks_won'].quantile(0.95):.1f} |"
                )
            sections.append("")

        # Bidder make rate
        if "is_bidder" in eval_df.columns and "made_bid" in eval_df.columns:
            bidder_df = eval_df[eval_df["is_bidder"] == True]  # noqa: E712
            if not bidder_df.empty:
                make_rate = bidder_df["made_bid"].mean()
                sections.append(f"**Overall make rate:** {make_rate:.3f}")
                sections.append("")

    # --- Model Performance (when eval_df + artifacts available) ---
    if eval_df is not None and not eval_df.empty:
        # Try to load model artifacts for predictions
        model_data = None
        model_path_key = olsa_full.get("artifact_path")
        if model_path_key:
            model_file = _resolve_bundle_ref(bundle_path, model_path_key)
            if model_file.exists():
                try:
                    with open(model_file) as f:
                        model_data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass

        if model_data and "payoff_model" in model_data:
            sections.append("## Model Performance")
            sections.append("")
            payoff = model_data["payoff_model"]
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
                sections.append(
                    f"- **{contract}**: R²={r2:.4f}, MAE={mae:.4f} (n={len(subset)})"
                )
            sections.append("")

    # --- Feature Correlations (when eval_df available) ---
    if eval_df is not None and not eval_df.empty and "tricks_won" in eval_df.columns:
        feat_cols = [c for c in eval_df.columns if c.startswith("feat_")]
        numeric_feats = [
            c for c in feat_cols if pd.api.types.is_numeric_dtype(eval_df[c])
        ]
        if numeric_feats and "contract_type" in eval_df.columns:
            sections.append("## Feature Correlations")
            sections.append("")
            sections.append(
                "Top features by absolute Pearson correlation with `tricks_won`,"
                " per contract type."
            )
            sections.append("")
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
                if not corrs:
                    continue
                # Top 5 by absolute correlation
                top = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                sections.append(f"### {ctype}")
                sections.append("")
                sections.append("| Feature | r |")
                sections.append("|---------|---|")
                for fname, r in top:
                    sections.append(f"| {fname.replace('feat_', '')} | {r:+.4f} |")
                sections.append("")

    # --- Comparator Battery (when bundle has comparator_battery key) ---
    comparator_battery = bundle.get("comparator_battery")
    if comparator_battery and isinstance(comparator_battery, dict):
        sections.append("## Comparator Battery")
        sections.append("")
        # Extract and rank by net_eppd
        ranked = []
        for bidder_name, metrics in comparator_battery.items():
            net_eppd = metrics.get("net_eppd") if isinstance(metrics, dict) else None
            if net_eppd is not None:
                ranked.append((bidder_name, net_eppd))
        if ranked:
            ranked.sort(key=lambda x: x[1], reverse=True)
            sections.append("| Bidder | net_eppd |")
            sections.append("|--------|----------|")
            for name, val in ranked:
                sections.append(f"| {name} | {val:.4f} |")
            sections.append("")

    # --- Head-to-Head Summary (when matchup_run_dir provided) ---
    if matchup_run_dir is not None:
        matchup_run_dir = Path(matchup_run_dir)
        logs_dir = matchup_run_dir / "logs"
        if logs_dir.is_dir():
            import glob as glob_mod

            log_files = sorted(glob_mod.glob(str(logs_dir / "*.jsonl")))
            if log_files:
                sections.append("## Head-to-Head Summary")
                sections.append("")
                try:
                    from bid_euchre.datasets.eval_dataset import build_eval_dataset

                    matchup_rows = []
                    for lf in log_files:
                        lf_path = Path(lf)
                        # Extract matchup_id from filename: <run_id>_<matchup_id>.jsonl
                        stem = lf_path.stem
                        # matchup_id is everything after the run_id prefix
                        parts = stem.split("_", 1)
                        mid = parts[1] if len(parts) > 1 else stem
                        try:
                            mdf = build_eval_dataset(lf, max_deals=5000)
                            if not mdf.empty:
                                deal_df = mdf[mdf["seat"] == 0]
                                n_deals = deal_df["deal_id"].nunique()
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
                        sections.append(
                            "| Matchup | Deals | Team0 Tricks | Team1 Tricks |"
                        )
                        sections.append(
                            "|---------|-------|-------------|-------------|"
                        )
                        for row in matchup_rows:
                            sections.append(
                                f"| {row['matchup']}"
                                f" | {row['deals']}"
                                f" | {row['team0_tricks']:.2f}"
                                f" | {row['team1_tricks']:.2f} |"
                            )
                        sections.append("")
                    else:
                        sections.append("*No matchup data could be parsed from logs.*")
                        sections.append("")
                except ImportError:
                    sections.append("*build_eval_dataset unavailable.*")
                    sections.append("")

    # --- Chart references ---
    if chart_dir is not None:
        chart_dir = Path(chart_dir)
        sections.append("## Charts")
        sections.append("")
        chart_files = sorted(chart_dir.glob("*.png"))
        if chart_files:
            for cf in chart_files:
                sections.append(f"![{cf.stem}]({cf})")
                sections.append("")
        else:
            sections.append("*No chart PNGs found.*")
            sections.append("")

    # --- Promotion decision ---
    decision = None
    if decision_path is not None:
        decision_path = Path(decision_path)
        if decision_path.exists():
            with open(decision_path) as f:
                decision = json.load(f)
            sections.append("## Promotion Decision")
            sections.append("")
            sections.append(f"- **Outcome:** {decision.get('decision', 'UNKNOWN')}")
            sections.append(f"- **gate_status:** {decision.get('decision', 'UNKNOWN')}")
            reasons = decision.get("reasons", [])
            if reasons:
                for r in reasons:
                    sections.append(f"- {r}")
            sections.append("")

    # --- Attribution gap ---
    # Priority: (1) decision JSON, (2) eval files from bundle, (3) inline bundle fields
    sections.append("## Attribution Gap")
    sections.append("")

    attribution_gap = None
    olsa_eppd = None
    full_eppd = None

    # Source 1: decision JSON
    if decision is not None and decision.get("attribution_gap") is not None:
        attribution_gap = decision["attribution_gap"]
        # Also try to get per-arm values from decision
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
                olsa_metrics = load_eval_metrics(str(resolved))
                olsa_eppd = olsa_metrics.get("net_expected_points_per_deal")
            except (FileNotFoundError, json.JSONDecodeError):
                pass
        if full_eval_path:
            try:
                resolved = _resolve_bundle_ref(bundle_path, full_eval_path)
                full_metrics = load_eval_metrics(str(resolved))
                full_eppd = full_metrics.get("net_expected_points_per_deal")
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

    if olsa_eppd is not None and full_eppd is not None:
        sections.append("| Arm | net_eppd |")
        sections.append("|-----|----------|")
        sections.append(f"| OLSa (constrained) | {olsa_eppd:.4f} |")
        sections.append(f"| OLSa_Full (promotional) | {full_eppd:.4f} |")
        sections.append(f"| **Attribution Gap** | **{attribution_gap:+.4f}** |")
        sections.append("")
        if attribution_gap > 0:
            sections.append("Positive gap: feature selection improves bidding quality.")
        elif attribution_gap < 0:
            sections.append("Negative gap: constrained arm outperforms — investigate.")
        else:
            sections.append("Zero gap: arms perform identically.")
    elif attribution_gap is not None:
        sections.append(f"**Attribution gap:** {attribution_gap:+.4f}")
    else:
        sections.append("*Attribution gap not yet available — eval results pending.*")
    sections.append("")

    # --- Reproducibility ---
    if eval_df is not None:
        sections.append("## Reproducibility")
        sections.append("")
        sections.append("```bash")
        sections.append("# Regenerate this report with the eval dataset parser:")
        sections.append('PYTHONPATH=src uv run python -c "')
        sections.append(
            "from bid_euchre.datasets.eval_dataset import build_eval_dataset"
        )
        sections.append(
            "from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report"
        )
        sections.append("df = build_eval_dataset('<EVAL_RUN_DIR>/logs/<LOG>.jsonl')")
        sections.append(
            f"report = generate_arc_d_rung_report('{bundle_path}',"
            f" eval_df=df, output_path='report.md')"
        )
        sections.append('"')
        sections.append("```")
        sections.append("")

    report = "\n".join(sections)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info("Wrote rung report: %s", output_path)

    return report


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


def _gate_status_str(arm_data: dict) -> str:
    """Extract gate status from arm data."""
    gate_val = arm_data.get("semantic_gate_val")
    if gate_val is None:
        return "\u2014"
    return str(gate_val) if isinstance(gate_val, str) else "present"

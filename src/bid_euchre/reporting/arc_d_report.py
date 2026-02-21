"""Arc D per-rung report generator.

Produces a Markdown narrative for each rung, comparing dual-arm
(OLSa constrained vs. OLSa_Full) evaluation results and summarizing
feature selection, attribution gap, and gate outcomes.

Do NOT import this module from reporting.__init__ (circular import risk).
Import directly: ``from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report``
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_arc_d_rung_report(
    bundle_path: str | Path,
    decision_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Generate a per-rung Markdown report for Arc D evaluation.

    Reads the rung bundle and optional promotion decision, then produces
    a dual-arm comparison narrative with feature selection summary,
    attribution gap, and gate outcomes.

    Args:
        bundle_path: Path to rung_bundle_r{N}.json.
        decision_path: Optional path to promotion_decision.json.
        output_path: If provided, writes the report to this file.

    Returns:
        The report as a Markdown string.
    """
    bundle_path = Path(bundle_path)
    with open(bundle_path) as f:
        bundle = json.load(f)

    rung_id = bundle.get("rung_id", "unknown")
    arc = bundle.get("arc", "arc_d")

    sections = []
    sections.append(f"# {arc.upper()} Rung {rung_id.upper()} Report")
    sections.append("")
    sections.append(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
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

    # --- Promotion decision ---
    if decision_path is not None:
        decision_path = Path(decision_path)
        if decision_path.exists():
            with open(decision_path) as f:
                decision = json.load(f)
            sections.append("## Promotion Decision")
            sections.append("")
            sections.append(f"- **Outcome:** {decision.get('decision', 'UNKNOWN')}")
            reasons = decision.get("reasons", [])
            if reasons:
                for r in reasons:
                    sections.append(f"- {r}")
            sections.append("")

    # --- Attribution gap ---
    sections.append("## Attribution Gap")
    sections.append("")
    sections.append("The attribution gap measures the net_eppd difference between the ")
    sections.append("full-feature promotional arm and the constrained attribution arm.")
    sections.append(
        "A positive gap indicates feature selection improves bidding quality."
    )
    sections.append("")

    report = "\n".join(sections)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        logger.info("Wrote rung report: %s", output_path)

    return report


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

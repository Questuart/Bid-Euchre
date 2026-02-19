"""Model-rung report template generator.

Produces a structured Markdown report from semantic gate results,
split manifests, and performance metrics.  Charts are embedded by
reference when ``chart_dir`` is provided — all 3 required chart PNGs
must exist or a ``ValueError`` is raised.

Usage::

    from bid_euchre.reporting.report_template import generate_model_rung_report

Do NOT import via ``bid_euchre.reporting`` (circular-import risk).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_CHART_KEYS = (
    "seat_balance_boxplot",
    "pred_vs_actual_scatter",
    "residual_distribution",
)


# ──────────────────────────────────────────────
#  Section renderers
# ──────────────────────────────────────────────


def _render_executive_summary(semantic_gate: dict) -> str:
    status = semantic_gate.get("gate_status", "UNKNOWN")
    passed = semantic_gate.get("passed_checks", 0)
    total = semantic_gate.get("total_checks", 0)
    failed = semantic_gate.get("failed_checks", 0)
    mode = semantic_gate.get("mode", "UNKNOWN")
    split = semantic_gate.get("active_split", "UNKNOWN")
    return (
        "## §1 Executive Summary\n\n"
        f"- **Gate status:** {status}\n"
        f"- **Checks:** {passed}/{total} passed, {failed} failed\n"
        f"- **Mode:** {mode}\n"
        f"- **Split:** {split}\n"
    )


def _render_model_identity(model_identity: dict) -> str:
    lines = ["## §2 Model Identity\n"]
    lines.append(f"- **Artifact path:** `{model_identity.get('artifact_path', 'N/A')}`")
    lines.append(f"- **SHA256:** `{model_identity.get('sha256', 'N/A')}`")
    lines.append(f"- **Config:** `{model_identity.get('config', 'N/A')}`")
    lines.append(f"- **Git SHA:** `{model_identity.get('git_sha', 'N/A')}`")
    return "\n".join(lines) + "\n"


def _render_data_summary(semantic_gate: dict, split_manifest: Any) -> str:
    lines = ["## §3 Data Summary\n"]
    lines.append(f"- **Total hands:** {semantic_gate.get('total_hands', 'N/A')}")
    lines.append(f"- **Seed:** {semantic_gate.get('seed', 'N/A')}")

    # Split manifest table
    lines.append("")
    lines.append(_split_manifest_table(split_manifest))
    return "\n".join(lines) + "\n"


def _render_fairness(
    semantic_gate: dict,
    chart_dir: Path | None,
) -> str:
    lines = ["## §4 Fairness Assessment\n"]
    checks = _filter_checks(semantic_gate, "fairness")
    lines.append(_gate_checks_table(checks))

    if chart_dir is not None:
        chart_path = chart_dir / "seat_balance_boxplot.png"
        lines.append("")
        lines.append(f"![seat_balance_boxplot]({chart_path})")
    return "\n".join(lines) + "\n"


def _render_health(semantic_gate: dict) -> str:
    lines = ["## §5 Health Assessment\n"]
    checks = _filter_checks(semantic_gate, "health")
    lines.append(_gate_checks_table(checks))
    return "\n".join(lines) + "\n"


def _render_directional_sanity(
    semantic_gate: dict,
    chart_dir: Path | None,
) -> str:
    lines = ["## §6 Directional Sanity\n"]
    checks = _filter_checks(semantic_gate, "directional_sanity")
    lines.append(_gate_checks_table(checks))

    if chart_dir is not None:
        lines.append("")
        lines.append(
            f"![pred_vs_actual_scatter]({chart_dir / 'pred_vs_actual_scatter.png'})"
        )
        lines.append("")
        lines.append(
            f"![residual_distribution]({chart_dir / 'residual_distribution.png'})"
        )
    return "\n".join(lines) + "\n"


def _render_performance(performance_metrics: dict) -> str:
    lines = ["## §7 Performance Detail\n"]
    lines.append(_performance_table(performance_metrics))
    return "\n".join(lines) + "\n"


def _render_gate_summary(semantic_gate: dict) -> str:
    lines = ["## §8 Semantic Gate Summary\n"]
    checks = semantic_gate.get("checks", [])
    lines.append(_gate_checks_table(checks))
    return "\n".join(lines) + "\n"


def _render_reproduction(semantic_gate: dict, model_identity: dict) -> str:
    seed = semantic_gate.get("seed", 42)
    artifact = model_identity.get("artifact_path", "<artifact_path>")
    lines = [
        "## §9 Reproduction Commands\n",
        "```bash",
        "# Re-run evaluation notebook:",
        "PYTHONPATH=src uv run papermill \\",
        "    notebooks/_templates/01_model_rung_template.ipynb \\",
        "    /tmp/eval_output.ipynb \\",
        f"    -p SEED {seed} \\",
        f"    -p MODEL_ARTIFACT_PATH {artifact}",
        "```",
    ]
    return "\n".join(lines) + "\n"


def _render_limitations(limitations: list[str]) -> str:
    lines = ["## §10 Known Limitations\n"]
    if not limitations:
        lines.append("_No known limitations recorded._")
    else:
        for lim in limitations:
            lines.append(f"- {lim}")
    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────
#  Table helpers
# ──────────────────────────────────────────────


def _gate_checks_table(checks: list[dict], category: str | None = None) -> str:
    """Render a markdown table of gate checks."""
    if category is not None:
        checks = [c for c in checks if c.get("category") == category]

    lines = [
        "| check_id | category | status | threshold | observed | contract_type |",
        "|----------|----------|--------|-----------|----------|---------------|",
    ]
    for c in checks:
        lines.append(
            f"| {c.get('check_id', '')} "
            f"| {c.get('category', '')} "
            f"| {c.get('status', '')} "
            f"| {c.get('threshold', '')} "
            f"| {c.get('observed', '')} "
            f"| {c.get('contract_type', '')} |"
        )
    return "\n".join(lines)


def _performance_table(metrics: dict) -> str:
    """Render per-contract performance table."""
    lines = [
        "| contract_type | R² | R² 95% CI | MAE | MAE 95% CI | N |",
        "|---------------|-----|-----------|-----|------------|---|",
    ]
    for ct, m in sorted(metrics.items()):
        r2 = m.get("r_squared", "")
        r2_ci = m.get("r_squared_ci", "")
        mae = m.get("mae", "")
        mae_ci = m.get("mae_ci", "")
        n = m.get("n", "")
        lines.append(f"| {ct} | {r2} | {r2_ci} | {mae} | {mae_ci} | {n} |")
    return "\n".join(lines)


def _split_manifest_table(split_manifest: Any) -> str:
    """Render split manifest summary table."""
    if hasattr(split_manifest, "to_dict"):
        d = split_manifest.to_dict()
    elif isinstance(split_manifest, dict):
        d = split_manifest
    else:
        return "_Split manifest not available._"

    lines = [
        "| split_type | train | val | test | source_run_id | seed |",
        "|------------|-------|-----|------|---------------|------|",
    ]
    lines.append(
        f"| {d.get('split_type', '')} "
        f"| {d.get('train_hand_ids', '')} "
        f"| {d.get('val_hand_ids', '')} "
        f"| {d.get('test_hand_ids', '')} "
        f"| {d.get('source_run_id', '')} "
        f"| {d.get('split_seed', '')} |"
    )
    return "\n".join(lines)


def _filter_checks(semantic_gate: dict, category: str) -> list[dict]:
    """Extract checks matching a category."""
    return [c for c in semantic_gate.get("checks", []) if c.get("category") == category]


# ──────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────


def generate_model_rung_report(
    semantic_gate: dict,
    split_manifest: Any,
    performance_metrics: dict,
    model_identity: dict,
    limitations: list[str],
    output_path: Path,
    *,
    chart_dir: Path | None = None,
) -> Path:
    """Generate a structured Markdown report for model-rung evaluation.

    Parameters
    ----------
    semantic_gate : dict
        Gate artifact from ``compute_semantic_gate()``.
    split_manifest : SplitManifest or dict
        Split manifest with partition metadata.
    performance_metrics : dict
        Per-contract metrics, e.g. ``{"suit": {"r_squared": 0.22, ...}}``.
    model_identity : dict
        Model provenance: ``artifact_path``, ``sha256``, ``config``, ``git_sha``.
    limitations : list[str]
        Known limitations to document.
    output_path : Path
        Where to write the ``.md`` report file.
    chart_dir : Path or None
        Directory containing chart PNGs from the notebook.  When provided,
        all 3 required charts must exist or ``ValueError`` is raised.

    Returns
    -------
    Path
        The written report path.
    """
    # Validate chart contract
    if chart_dir is not None:
        chart_dir = Path(chart_dir)
        for key in REQUIRED_CHART_KEYS:
            chart_path = chart_dir / f"{key}.png"
            if not chart_path.exists():
                raise ValueError(f"Required chart missing: {chart_path}")

    output_path = Path(output_path)

    # Build report sections
    sections = [
        f"# Model Rung Report\n\n**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n",
        _render_executive_summary(semantic_gate),
        _render_model_identity(model_identity),
        _render_data_summary(semantic_gate, split_manifest),
        _render_fairness(semantic_gate, chart_dir),
        _render_health(semantic_gate),
        _render_directional_sanity(semantic_gate, chart_dir),
        _render_performance(performance_metrics),
        _render_gate_summary(semantic_gate),
        _render_reproduction(semantic_gate, model_identity),
        _render_limitations(limitations),
    ]

    content = "\n".join(sections)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)

    return output_path

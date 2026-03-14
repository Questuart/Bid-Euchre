"""Canonical path construction for Arc D v2 lineage.

All path logic in one place.  No more string interpolation scattered across
scripts.  Every function returns a ``pathlib.Path`` that is *repo-root-relative*
(consistent with the rest of the codebase).
"""

from pathlib import Path

# ── Lineage root paths ──────────────────────────────────────────────────────

PLANS_ROOT = Path("plans/arc_d_v2")
REPORTS_ROOT = Path("docs/04_reports/arc_d_v2")
RUNS_ROOT = Path("data/runs/arc_d_v2")

# ── Lineage-level files ─────────────────────────────────────────────────────

LINEAGE_PLAN = PLANS_ROOT / "lineage_plan.md"
LINEAGE_ROSTER = PLANS_ROOT / "roster.json"
LINEAGE_AMENDMENTS = PLANS_ROOT / "amendments.md"
SUB_PLAN_REGISTRY = PLANS_ROOT / "sub_plan_registry.md"
CROSS_RUNG_DELTAS = REPORTS_ROOT / "cross_rung_deltas.csv"

# ── Anchor model (fixed for the lineage) ────────────────────────────────────

ANCHOR_ARTIFACT = Path("data/artifacts/arc_d/r0/hybrid_r0_full.json")


# ── Rung-level plan paths ───────────────────────────────────────────────────


def rung_plan_dir(rung: str) -> Path:
    """Plans directory for a rung: ``plans/arc_d_v2/<rung>/``."""
    return PLANS_ROOT / rung


def rung_plan(rung: str) -> Path:
    """Rung plan file: ``plans/arc_d_v2/<rung>/plan.md``."""
    return rung_plan_dir(rung) / "plan.md"


def rung_hypotheses(rung: str) -> Path:
    """Hypotheses file: ``plans/arc_d_v2/<rung>/hypotheses.json``."""
    return rung_plan_dir(rung) / "hypotheses.json"


def rung_checkpoints(rung: str) -> Path:
    """Checkpoints file: ``plans/arc_d_v2/<rung>/checkpoints.md``."""
    return rung_plan_dir(rung) / "checkpoints.md"


def rung_state(rung: str) -> Path:
    """State file: ``plans/arc_d_v2/<rung>/state.json``."""
    return rung_plan_dir(rung) / "state.json"


def rung_execution_log(rung: str) -> Path:
    """Execution log: ``plans/arc_d_v2/<rung>/execution_log.jsonl``."""
    return rung_plan_dir(rung) / "execution_log.jsonl"


# ── Rung-level run paths ────────────────────────────────────────────────────


def rung_run_dir(rung: str) -> Path:
    """Run artifacts root: ``data/runs/arc_d_v2/<rung>/``."""
    return RUNS_ROOT / rung


def seed_dir(rung: str, mode: str, seed: int) -> Path:
    """Per-seed output: ``data/runs/arc_d_v2/<rung>/<mode>/seed_<N>/``."""
    return rung_run_dir(rung) / mode / f"seed_{seed}"


def seed_dataset(rung: str, mode: str, seed: int) -> Path:
    """Action-value dataset for a seed."""
    return seed_dir(rung, mode, seed) / "datasets" / "action_value.parquet"


def seed_artifacts_dir(rung: str, mode: str, seed: int) -> Path:
    """Artifacts directory for a seed."""
    return seed_dir(rung, mode, seed) / "artifacts"


def model_artifact(rung: str, mode: str, seed: int, model_name: str) -> Path:
    """Model artifact JSON for a specific model within a seed."""
    return seed_artifacts_dir(rung, mode, seed) / model_name / "artifact.json"


def seed_h2h_dir(rung: str, mode: str, seed: int) -> Path:
    """Head-to-head results directory for a seed."""
    return seed_dir(rung, mode, seed) / "h2h"


def seed_comparator_dir(rung: str, mode: str, seed: int) -> Path:
    """Comparator battery results directory for a seed."""
    return seed_dir(rung, mode, seed) / "comparator"


# ── Rung-level report paths ─────────────────────────────────────────────────


def rung_report_dir(rung: str) -> Path:
    """Report output: ``docs/04_reports/arc_d_v2/<rung>/``."""
    return REPORTS_ROOT / rung


def rung_tables_dir(rung: str) -> Path:
    """Report tables directory."""
    return rung_report_dir(rung) / "tables"


def rung_charts_dir(rung: str) -> Path:
    """Report charts directory."""
    return rung_report_dir(rung) / "charts"


def rung_chart_data_dir(rung: str) -> Path:
    """Chart backing data directory."""
    return rung_report_dir(rung) / "chart_data"


# ── Advance / evidence paths ────────────────────────────────────────────────


def advance_check_path(rung: str, mode: str) -> Path:
    """``advance_check_<mode>.json`` in rung run dir."""
    return rung_run_dir(rung) / f"advance_check_{mode}.json"


def evidence_manifest_path(rung: str) -> Path:
    """Evidence manifest: ``docs/04_reports/arc_d_v2/<rung>/evidence_manifest.json``."""
    return rung_report_dir(rung) / "evidence_manifest.json"


# ── Step logs ────────────────────────────────────────────────────────────────


def rung_heartbeat(rung: str) -> Path:
    """Heartbeat file: ``plans/arc_d_v2/<rung>/heartbeat``."""
    return rung_plan_dir(rung) / "heartbeat"


def step_log_path(rung: str, step: str, detail: str = "") -> Path:
    """Per-step subprocess log in the rung plan directory."""
    suffix = f"_{detail}" if detail else ""
    return rung_plan_dir(rung) / "logs" / f"step_{step}{suffix}.log"

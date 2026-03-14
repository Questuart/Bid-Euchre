"""Typed schemas for Arc D v2 machine-readable artifacts.

All JSON artifacts produced by the orchestrator and reporting scripts have
typed dataclass representations here.  This enforces structure and prevents
schema drift between plan, orchestrator, and reporting.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ── Step and Model Status Constants ──────────────────────────────────────────

VALID_STEP_STATUSES = frozenset(
    {
        "pending",
        "in_progress",
        "complete",
        "partial",
        "failed_retryable",
        "failed_blocking",
        "skipped",
    }
)

VALID_ADVANCE_DECISIONS = frozenset({"PROCEED", "INVESTIGATE", "PAUSE"})


# ── State Schema ─────────────────────────────────────────────────────────────


@dataclass
class ModelStatus:
    """Status of a single model within a seed step."""

    status: str  # one of VALID_STEP_STATUSES
    output: str = ""
    detail: str = ""


@dataclass
class SeedStepStatus:
    """Status of a pipeline step for a single seed."""

    status: str  # one of VALID_STEP_STATUSES
    outputs: list[str] = field(default_factory=list)
    models: dict[str, ModelStatus] = field(default_factory=dict)
    detail: str = ""


@dataclass
class AggregationStepStatus:
    """Status of an aggregation step (cross-seed)."""

    status: str = "pending"
    outputs: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class Fingerprint:
    """Reproducibility fingerprint for a run artifact."""

    roster_hash: str = ""
    seed: int = 0
    mode: str = ""
    feature_set: str = ""
    plan_sha: str = ""
    script_mtime: float = 0.0


@dataclass
class RunState:
    """Machine-readable execution state for a rung.

    Lives at ``plans/arc_d_v2/<rung>/state.json``.
    """

    schema_version: str = "rung_state_v1"
    rung: str = ""
    mode: str = ""  # smoke, quick, full
    seeds: list[int] = field(default_factory=list)
    current_step: str = ""
    step_status: str = "pending"
    status_detail: str = ""
    retries: int = 0
    max_retries: int = 3
    blocker: str | None = None
    active_investigation: str | None = None
    supersession: dict[str, Any] | None = None
    per_seed: dict[int, dict[str, SeedStepStatus]] = field(default_factory=dict)
    aggregation: dict[str, AggregationStepStatus] = field(default_factory=dict)
    fingerprints: dict[str, Fingerprint] = field(default_factory=dict)
    last_updated: str = ""

    # Per-seed pipeline steps
    _PER_SEED_STEPS: list[str] = field(
        default_factory=lambda: ["1", "2", "3", "3b", "4", "5"],
        init=False,
        repr=False,
    )
    # Aggregation steps
    _AGGREGATION_STEPS: list[str] = field(
        default_factory=lambda: ["6", "7", "8", "9"],
        init=False,
        repr=False,
    )

    @classmethod
    def create_fresh(cls, rung: str, mode: str, seeds: list[int]) -> RunState:
        """Create a fresh state for a new rung execution."""
        per_seed_steps = ["1", "2", "3", "3b", "4", "5"]
        aggregation_steps = ["6", "7", "8", "9"]

        per_seed: dict[int, dict[str, SeedStepStatus]] = {}
        for seed in seeds:
            per_seed[seed] = {
                step: SeedStepStatus(status="pending") for step in per_seed_steps
            }

        aggregation = {
            step: AggregationStepStatus(status="pending") for step in aggregation_steps
        }

        return cls(
            rung=rung,
            mode=mode,
            seeds=seeds,
            current_step="0",
            step_status="pending",
            per_seed=per_seed,
            aggregation=aggregation,
        )

    def save(self, path: Path) -> None:
        """Serialize to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # Remove private fields
        data.pop("_PER_SEED_STEPS", None)
        data.pop("_AGGREGATION_STEPS", None)
        path.write_text(json.dumps(data, indent=2, default=str) + "\n")

    @classmethod
    def load(cls, path: Path) -> RunState:
        """Deserialize from JSON file, reconstructing nested dataclasses."""
        data = json.loads(path.read_text())

        per_seed: dict[int, dict[str, SeedStepStatus]] = {}
        for seed_str, steps in data.get("per_seed", {}).items():
            seed = int(seed_str)
            per_seed[seed] = {}
            for step, step_data in steps.items():
                models: dict[str, ModelStatus] = {}
                for m_name, m_data in step_data.get("models", {}).items():
                    models[m_name] = ModelStatus(**m_data)
                per_seed[seed][step] = SeedStepStatus(
                    status=step_data["status"],
                    outputs=step_data.get("outputs", []),
                    models=models,
                    detail=step_data.get("detail", ""),
                )

        aggregation: dict[str, AggregationStepStatus] = {}
        for step, step_data in data.get("aggregation", {}).items():
            aggregation[step] = AggregationStepStatus(**step_data)

        fingerprints: dict[str, Fingerprint] = {}
        for key, fp_data in data.get("fingerprints", {}).items():
            fingerprints[key] = Fingerprint(**fp_data)

        return cls(
            schema_version=data.get("schema_version", "rung_state_v1"),
            rung=data["rung"],
            mode=data["mode"],
            seeds=data["seeds"],
            current_step=data.get("current_step", ""),
            step_status=data.get("step_status", "pending"),
            status_detail=data.get("status_detail", ""),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            blocker=data.get("blocker"),
            active_investigation=data.get("active_investigation"),
            supersession=data.get("supersession"),
            per_seed=per_seed,
            aggregation=aggregation,
            fingerprints=fingerprints,
            last_updated=data.get("last_updated", ""),
        )


# ── Hypothesis Schema ────────────────────────────────────────────────────────


@dataclass
class HypothesisBound:
    """A directional bound for hypothesis evaluation."""

    op: str  # ">", "<", ">=", "<="
    value: float


@dataclass
class Hypothesis:
    """A single testable hypothesis with metric source and bounds."""

    id: str
    description: str
    metric: str
    source_table: str
    source_column: str
    source_filter: dict[str, str]
    anchor_filter: dict[str, str] = field(default_factory=dict)
    computation: str = "value - anchor_value"
    expected_bound: HypothesisBound = field(
        default_factory=lambda: HypothesisBound(">", 0.0)
    )
    surprise_if: HypothesisBound = field(
        default_factory=lambda: HypothesisBound("<", 0.0)
    )


@dataclass
class HypothesesFile:
    """Container for a rung's hypothesis definitions.

    Lives at ``plans/arc_d_v2/<rung>/hypotheses.json``.
    """

    schema_version: str = "hypotheses_v1"
    rung: str = ""
    hypotheses: list[Hypothesis] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Serialize to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> HypothesesFile:
        """Deserialize from JSON file."""
        data = json.loads(path.read_text())
        hypotheses = []
        for h in data.get("hypotheses", []):
            hypotheses.append(
                Hypothesis(
                    id=h["id"],
                    description=h["description"],
                    metric=h["metric"],
                    source_table=h["source_table"],
                    source_column=h["source_column"],
                    source_filter=h["source_filter"],
                    anchor_filter=h.get("anchor_filter", {}),
                    computation=h.get("computation", "value - anchor_value"),
                    expected_bound=HypothesisBound(
                        **h.get("expected_bound", {"op": ">", "value": 0.0})
                    ),
                    surprise_if=HypothesisBound(
                        **h.get("surprise_if", {"op": "<", "value": 0.0})
                    ),
                )
            )
        return cls(
            schema_version=data.get("schema_version", "hypotheses_v1"),
            rung=data.get("rung", ""),
            hypotheses=hypotheses,
        )


# ── Advance Check Schema ─────────────────────────────────────────────────────


@dataclass
class CheckResult:
    """Result of a single sufficiency or canary check."""

    id: str
    pass_: bool  # ``pass`` is a Python keyword
    value: str = ""
    detail: str = ""
    level: str = "GATE"  # GATE or WARNING


@dataclass
class HypothesisCheckResult:
    """Result of evaluating a single hypothesis against observed data."""

    id: str
    description: str
    expected_bound: str
    observed: float
    pass_: bool
    surprise_threshold: str
    surprise_hit: bool


@dataclass
class BestInLineage:
    """Tracks the best model seen so far across the lineage."""

    model: str
    pooled_net_eppd: float
    updated: bool = False


@dataclass
class NextAction:
    """Recommended next action after an advance check."""

    command: str
    prerequisite: str = ""


@dataclass
class AdvanceCheck:
    """Machine-readable advance decision.

    Lives at ``data/runs/arc_d_v2/<rung>/advance_check_<mode>.json``.
    """

    schema_version: str = "advance_check_v1"
    rung: str = ""
    mode: str = ""
    advance_decision: str = ""  # PROCEED, INVESTIGATE, PAUSE
    reason: str = ""
    timestamp: str = ""
    next_action: NextAction = field(default_factory=lambda: NextAction(""))
    hypothesis_checks: list[HypothesisCheckResult] = field(default_factory=list)
    sufficiency_checks: list[CheckResult] = field(default_factory=list)
    canary_checks: list[CheckResult] = field(default_factory=list)
    best_in_lineage: BestInLineage | None = None
    failed_checks_summary: list[str] = field(default_factory=list)
    warnings_summary: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        """Serialize to JSON, renaming ``pass_`` back to ``pass``."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        _rename_pass_fields(data)
        path.write_text(json.dumps(data, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> AdvanceCheck:
        """Deserialize from JSON file."""
        data = json.loads(path.read_text())

        hypothesis_checks = []
        for h in data.get("hypothesis_checks", []):
            hypothesis_checks.append(
                HypothesisCheckResult(
                    id=h["id"],
                    description=h["description"],
                    expected_bound=h["expected_bound"],
                    observed=h["observed"],
                    pass_=h.get("pass", h.get("pass_", True)),
                    surprise_threshold=h["surprise_threshold"],
                    surprise_hit=h["surprise_hit"],
                )
            )

        sufficiency_checks = []
        for s in data.get("sufficiency_checks", []):
            sufficiency_checks.append(
                CheckResult(
                    id=s["id"],
                    pass_=s.get("pass", s.get("pass_", True)),
                    value=s.get("value", ""),
                    detail=s.get("detail", ""),
                    level=s.get("level", "GATE"),
                )
            )

        canary_checks = []
        for c in data.get("canary_checks", []):
            canary_checks.append(
                CheckResult(
                    id=c["id"],
                    pass_=c.get("pass", c.get("pass_", True)),
                    value=c.get("value", ""),
                    detail=c.get("detail", ""),
                    level=c.get("level", "WARNING"),
                )
            )

        best_data = data.get("best_in_lineage")
        best_in_lineage = BestInLineage(**best_data) if best_data is not None else None

        next_data = data.get("next_action", {})
        next_action = NextAction(
            command=next_data.get("command", ""),
            prerequisite=next_data.get("prerequisite", ""),
        )

        return cls(
            schema_version=data.get("schema_version", "advance_check_v1"),
            rung=data.get("rung", ""),
            mode=data.get("mode", ""),
            advance_decision=data.get("advance_decision", ""),
            reason=data.get("reason", ""),
            timestamp=data.get("timestamp", ""),
            next_action=next_action,
            hypothesis_checks=hypothesis_checks,
            sufficiency_checks=sufficiency_checks,
            canary_checks=canary_checks,
            best_in_lineage=best_in_lineage,
            failed_checks_summary=data.get("failed_checks_summary", []),
            warnings_summary=data.get("warnings_summary", []),
        )

    @property
    def all_pass(self) -> bool:
        """True if all gating checks pass (canary warnings don't block)."""
        return (
            all(h.pass_ for h in self.hypothesis_checks)
            and all(s.pass_ for s in self.sufficiency_checks)
            and not any(h.surprise_hit for h in self.hypothesis_checks)
        )


def _rename_pass_fields(d: dict[str, Any]) -> None:
    """Recursively rename ``pass_`` to ``pass`` in a dict for JSON serialization."""
    if "pass_" in d:
        d["pass"] = d.pop("pass_")
    for v in d.values():
        if isinstance(v, dict):
            _rename_pass_fields(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    _rename_pass_fields(item)

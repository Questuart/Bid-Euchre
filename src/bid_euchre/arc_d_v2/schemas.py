"""Typed schemas for Arc D v2 machine-readable artifacts.

All JSON artifacts produced by the orchestrator and reporting scripts have
typed dataclass representations here.  This enforces structure and prevents
schema drift between plan, orchestrator, and reporting.

The canonical ``RunState`` was originally in ``scripts/internal/rung_state.py``
and has been merged here as the single source of truth.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bid_euchre.core.time import utc_now_iso

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


# ── DAG and Step Constants ──────────────────────────────────────────────────

SCHEMA_VERSION = "rung_state_v1"

# Step definitions — hard-coded DAG
STEPS = ["0", "1", "2", "3", "3b", "4", "5", "6", "7", "8", "9"]

# Downstream dependencies for rerun invalidation
DAG_DOWNSTREAM: dict[str, list[str]] = {
    "0": ["1", "2", "3", "3b", "4", "5", "6", "7", "8"],
    "1": ["2", "3", "3b", "4", "5", "6", "7", "8"],
    "2": ["3", "3b", "4", "5", "6", "7", "8"],
    "3": ["6", "7", "8"],
    "3b": ["6", "7", "8"],
    "4": ["6", "7", "8"],
    "5": ["6", "7", "8"],
    "6": ["7", "8"],
    "7": ["8"],
    "8": ["9"],
    "9": [],
}

# Steps where rerun can be model-scoped (others are holistic)
MODEL_SCOPED_STEPS = {"2", "3", "3b"}


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
class StepState:
    """Status of a single step in the operational RunState."""

    status: str = "pending"  # pending | running | complete | failed | skipped
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    retries: int = 0
    retryable: bool = True
    # Per-model status for model-scoped steps (keyed by model name)
    models: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Fingerprint at completion (for idempotency checks)
    fingerprint: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> StepState:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TimeoutPolicy:
    """Per-step timeout limits and heartbeat configuration.

    Timeouts are in seconds.  ``step_overrides`` maps step IDs to
    step-specific timeout limits; any step not listed falls back to
    ``default``.
    """

    default: int = 3600  # 1 hour
    step_overrides: dict[str, int] = field(
        default_factory=lambda: {
            "1": 1800,  # Dataset gen: 30 min (SMOKE), may be longer for FULL
            "2": 7200,  # Training: 2 hours (all models)
            "4": 3600,  # H2H battery: 1 hour
            "5": 3600,  # Comparator: 1 hour
            "3b": 1800,  # SHAP: 30 min
        }
    )
    heartbeat_interval: int = 60  # Write heartbeat every 60s
    stale_threshold: int = 300  # Consider dead after 5min no heartbeat

    def get_timeout(self, step: str) -> int:
        """Return the timeout for a given step (override or default)."""
        return self.step_overrides.get(step, self.default)


@dataclass
class RunState:
    """Full execution state for a rung run.

    Lives at ``plans/arc_d_v2/<rung>/state.json``.

    This is the canonical (richer) RunState that supports step mutation,
    per-model tracking, fingerprinting, and human-readable summaries.
    """

    schema_version: str = SCHEMA_VERSION
    rung: str = ""
    mode: str = ""  # smoke | quick | full
    seeds: list[int] = field(default_factory=list)
    current_step: str = ""
    step_status: str = "not_started"  # not_started | running | complete | failed
    status_detail: str = ""
    retries: int = 0
    max_retries: int = 3
    blocker: str | None = None
    active_investigation: str | None = None
    supersession: dict | None = None
    timeout_policy: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    steps: dict[str, dict] = field(default_factory=dict)
    per_seed: dict[str, dict] = field(default_factory=dict)
    last_updated: str = ""
    created_at: str = ""

    @classmethod
    def load(cls, path: Path) -> RunState:
        """Load state from JSON file."""
        data = json.loads(path.read_text())

        # Reconstruct timeout policy (graceful default for older state files)
        tp_data = data.get("timeout_policy")
        if tp_data is not None:
            timeout_policy = TimeoutPolicy(
                default=tp_data.get("default", 3600),
                step_overrides=tp_data.get("step_overrides", {}),
                heartbeat_interval=tp_data.get("heartbeat_interval", 60),
                stale_threshold=tp_data.get("stale_threshold", 300),
            )
        else:
            timeout_policy = TimeoutPolicy()

        # Reconstruct step states
        state = cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            rung=data.get("rung", ""),
            mode=data.get("mode", ""),
            seeds=data.get("seeds", []),
            current_step=data.get("current_step", ""),
            step_status=data.get("step_status", "not_started"),
            status_detail=data.get("status_detail", ""),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            blocker=data.get("blocker"),
            active_investigation=data.get("active_investigation"),
            supersession=data.get("supersession"),
            timeout_policy=timeout_policy,
            steps=data.get("steps", {}),
            per_seed=data.get("per_seed", {}),
            last_updated=data.get("last_updated", ""),
            created_at=data.get("created_at", ""),
        )
        return state

    def save(self, path: Path) -> None:
        """Save state to JSON file."""
        self.last_updated = utc_now_iso()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def create_fresh(cls, rung: str, mode: str, seeds: list[int]) -> RunState:
        """Create a fresh state for a new rung run."""
        now = utc_now_iso()
        steps = {}
        for step_id in STEPS:
            steps[step_id] = StepState().to_dict()

        per_seed: dict[str, dict] = {}
        for seed in seeds:
            seed_steps = {}
            for step_id in STEPS:
                seed_steps[step_id] = StepState().to_dict()
            per_seed[str(seed)] = seed_steps

        return cls(
            rung=rung,
            mode=mode,
            seeds=seeds,
            current_step="0",
            step_status="not_started",
            steps=steps,
            per_seed=per_seed,
            last_updated=now,
            created_at=now,
        )

    def reset_for_mode(self, mode: str, seeds: list[int]) -> None:
        """Reset all steps for a new mode (e.g., QUICK -> FULL)."""
        self.mode = mode
        self.seeds = seeds
        self.current_step = "0"
        self.step_status = "not_started"
        self.blocker = None
        self.status_detail = ""

        for step_id in STEPS:
            self.steps[step_id] = StepState().to_dict()

        self.per_seed = {}
        for seed in seeds:
            seed_steps = {}
            for step_id in STEPS:
                seed_steps[step_id] = StepState().to_dict()
            self.per_seed[str(seed)] = seed_steps

    def reset_step(self, step: str) -> None:
        """Reset a step to pending."""
        self.steps[step] = StepState().to_dict()
        for seed_key in self.per_seed:
            if step in self.per_seed[seed_key]:
                self.per_seed[seed_key][step] = StepState().to_dict()

    def reset_model(self, step: str, model: str) -> None:
        """Reset a specific model within a step.

        Handles both bare model keys and seed:model aggregate keys.
        """
        pending_entry = {
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "error": None,
        }
        step_data = self.steps.get(step, {})
        models = step_data.get("models", {})

        # Reset bare model key if present
        found = False
        if model in models:
            models[model] = dict(pending_entry)
            found = True

        # Reset seed:model aggregate keys
        for key in list(models.keys()):
            if key.endswith(f":{model}"):
                models[key] = dict(pending_entry)
                found = True

        if found:
            step_data["models"] = models
            # Reset step status if it was complete
            if step_data.get("status") == "complete":
                step_data["status"] = "pending"
            self.steps[step] = step_data

        # Also reset in per_seed
        for seed_key in self.per_seed:
            seed_step = self.per_seed[seed_key].get(step, {})
            seed_models = seed_step.get("models", {})
            if model in seed_models:
                seed_models[model] = dict(pending_entry)
                seed_step["models"] = seed_models
                if seed_step.get("status") == "complete":
                    seed_step["status"] = "pending"
                self.per_seed[seed_key][step] = seed_step

    def model_status(self, seed: int, step: str, model: str) -> str:
        """Get the status of a specific model within a step for a given seed."""
        seed_key = str(seed)
        seed_data = self.per_seed.get(seed_key, {})
        step_data = seed_data.get(step, {})
        models = step_data.get("models", {})
        model_data = models.get(model, {})
        return model_data.get("status", "pending")

    def update_model(
        self,
        step: str,
        model: str,
        seed: int,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update the status of a specific model within a step."""
        now = utc_now_iso()
        model_entry = {
            "status": status,
            "completed_at": now if status in ("complete", "failed") else None,
            "started_at": now if status == "running" else None,
            "error": error,
        }

        # Update in per_seed
        seed_key = str(seed)
        if seed_key not in self.per_seed:
            self.per_seed[seed_key] = {}
        if step not in self.per_seed[seed_key]:
            self.per_seed[seed_key][step] = StepState().to_dict()
        if "models" not in self.per_seed[seed_key][step]:
            self.per_seed[seed_key][step]["models"] = {}
        self.per_seed[seed_key][step]["models"][model] = model_entry

        # Update in aggregate steps
        if "models" not in self.steps[step]:
            self.steps[step]["models"] = {}
        # Aggregate: track per-seed-model as seed:model
        agg_key = f"{seed}:{model}"
        self.steps[step]["models"][agg_key] = model_entry

    def mark_step_started(self, step: str, seed: int | None = None) -> None:
        """Mark a step as started."""
        now = utc_now_iso()
        self.current_step = step
        self.step_status = "running"
        self.steps[step]["status"] = "running"
        self.steps[step]["started_at"] = now
        if seed is not None:
            seed_key = str(seed)
            if seed_key in self.per_seed and step in self.per_seed[seed_key]:
                self.per_seed[seed_key][step]["status"] = "running"
                self.per_seed[seed_key][step]["started_at"] = now

    def mark_step_complete(
        self,
        step: str,
        seed: int | None = None,
        fingerprint: dict | None = None,
    ) -> None:
        """Mark a step as complete."""
        now = utc_now_iso()
        self.steps[step]["status"] = "complete"
        self.steps[step]["completed_at"] = now
        if fingerprint:
            self.steps[step]["fingerprint"] = fingerprint
        self.step_status = "complete"
        if seed is not None:
            seed_key = str(seed)
            if seed_key in self.per_seed and step in self.per_seed[seed_key]:
                self.per_seed[seed_key][step]["status"] = "complete"
                self.per_seed[seed_key][step]["completed_at"] = now
                if fingerprint:
                    self.per_seed[seed_key][step]["fingerprint"] = fingerprint

    def mark_step_failed(
        self,
        step: str,
        error: str,
        retryable: bool = True,
        seed: int | None = None,
    ) -> None:
        """Mark a step as failed."""
        now = utc_now_iso()
        self.steps[step]["status"] = "failed"
        self.steps[step]["completed_at"] = now
        self.steps[step]["error"] = error
        self.steps[step]["retryable"] = retryable
        self.step_status = "failed"
        self.status_detail = error
        if not retryable:
            self.blocker = error
        if seed is not None:
            seed_key = str(seed)
            if seed_key in self.per_seed and step in self.per_seed[seed_key]:
                self.per_seed[seed_key][step]["status"] = "failed"
                self.per_seed[seed_key][step]["completed_at"] = now
                self.per_seed[seed_key][step]["error"] = error

    def mark_step_skipped(self, step: str, reason: str = "") -> None:
        """Mark a step as skipped (e.g., missing dependency script)."""
        now = utc_now_iso()
        self.steps[step]["status"] = "skipped"
        self.steps[step]["completed_at"] = now
        self.steps[step]["error"] = reason or "Skipped"

    def step_is_complete(self, step: str, seed: int | None = None) -> bool:
        """Check if a step is complete (optionally for a specific seed)."""
        if seed is not None:
            seed_key = str(seed)
            seed_data = self.per_seed.get(seed_key, {})
            step_data = seed_data.get(step, {})
            return step_data.get("status") == "complete"
        return self.steps.get(step, {}).get("status") == "complete"

    def get_step_fingerprint(self, step: str, seed: int | None = None) -> dict | None:
        """Get the fingerprint from a completed step."""
        if seed is not None:
            seed_key = str(seed)
            seed_data = self.per_seed.get(seed_key, {})
            step_data = seed_data.get(step, {})
            return step_data.get("fingerprint")
        return self.steps.get(step, {}).get("fingerprint")

    def summary(self) -> str:
        """Return a human-readable summary of the current state."""
        lines = [
            f"Rung: {self.rung}",
            f"Mode: {self.mode}",
            f"Seeds: {self.seeds}",
            f"Current step: {self.current_step} ({self.step_status})",
            f"Last updated: {self.last_updated}",
        ]
        if self.blocker:
            lines.append(f"BLOCKER: {self.blocker}")
        if self.active_investigation:
            lines.append(f"Investigation: {self.active_investigation}")
        if self.supersession:
            lines.append(f"Supersession: {self.supersession}")
        lines.append("")
        lines.append("Step status:")
        for step_id, step_data in self.steps.items():
            status = step_data.get("status", "pending")
            marker = {
                "complete": "[x]",
                "running": "[~]",
                "failed": "[!]",
                "skipped": "[-]",
                "pending": "[ ]",
            }.get(status, "[?]")
            detail = ""
            if step_data.get("error"):
                detail = f" -- {step_data['error']}"
            lines.append(f"  {marker} Step {step_id}: {status}{detail}")
        return "\n".join(lines)


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

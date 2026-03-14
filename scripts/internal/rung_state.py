"""Rung orchestrator state management.

Manages the persisted execution state for rung runs. State files live under
plans/arc_d_v2/<rung>/state.json (committable, survives data cleanup).

Schema: rung_state_v1
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from bid_euchre.core.time import utc_now_iso

SCHEMA_VERSION = "rung_state_v1"

# Step definitions — hard-coded DAG (shared with run_rung.py)
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


@dataclass
class StepState:
    """Status of a single step."""

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
class RunState:
    """Full execution state for a rung run."""

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
    steps: dict[str, dict] = field(default_factory=dict)
    per_seed: dict[str, dict] = field(default_factory=dict)
    last_updated: str = ""
    created_at: str = ""

    @classmethod
    def load(cls, path: Path) -> RunState:
        """Load state from JSON file."""
        data = json.loads(path.read_text())
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

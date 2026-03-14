"""Configuration types for Arc D v2 lineage.

Typed representations for the roster (model definitions), mode contracts
(seed/deal counts), and per-rung runtime configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RosterModel:
    """A single model entry in the lineage roster."""

    name: str
    class_name: str  # Python class name (e.g., "GBTActionValueBidder")
    trainable: bool
    model_class: str = ""  # ols, gbt, two-stage, or "" for heuristics
    feature_set: str = ""  # r0, constrained, full, or "" for heuristics
    selection: str = "none"  # none, forward
    category: str = ""  # heuristic, legacy_baseline, or "" for trained models
    status: str = "active"  # active, excluded, experimental


@dataclass
class AnchorModel:
    """The fixed anchor model used as the comparator baseline."""

    name: str
    artifact: str
    class_name: str


@dataclass
class Roster:
    """Model roster for the lineage.

    Lives at ``plans/arc_d_v2/roster.json``.
    """

    schema_version: str = "roster_v1"
    lineage_id: str = "arc_d_v2"
    models: list[RosterModel] = field(default_factory=list)
    anchor: AnchorModel = field(default_factory=lambda: AnchorModel("", "", ""))

    def trainable_models(self) -> list[RosterModel]:
        """Return only trainable, active models."""
        return [m for m in self.models if m.trainable and m.status == "active"]

    def all_active_models(self) -> list[RosterModel]:
        """Return all active models (trainable and heuristic)."""
        return [m for m in self.models if m.status == "active"]

    @classmethod
    def load(cls, path: Path) -> Roster:
        """Load roster from a JSON file."""
        data = json.loads(path.read_text())
        models = [
            RosterModel(
                name=m["name"],
                class_name=m["class"],
                trainable=m["trainable"],
                model_class=m.get("model_class", ""),
                feature_set=m.get("feature_set", ""),
                selection=m.get("selection", "none"),
                category=m.get("category", ""),
                status=m.get("status", "active"),
            )
            for m in data.get("models", [])
        ]

        anchor_data = data.get("anchor", {})
        anchor = AnchorModel(
            name=anchor_data.get("name", ""),
            artifact=anchor_data.get("artifact", ""),
            class_name=anchor_data.get("class", ""),
        )

        return cls(
            schema_version=data.get("schema_version", "roster_v1"),
            lineage_id=data.get("lineage_id", "arc_d_v2"),
            models=models,
            anchor=anchor,
        )

    def save(self, path: Path) -> None:
        """Serialize roster to a JSON file."""
        data: dict = {
            "schema_version": self.schema_version,
            "lineage_id": self.lineage_id,
            "models": [
                {
                    "name": m.name,
                    "class": m.class_name,
                    "trainable": m.trainable,
                    **({"model_class": m.model_class} if m.model_class else {}),
                    **({"feature_set": m.feature_set} if m.feature_set else {}),
                    **({"selection": m.selection} if m.selection != "none" else {}),
                    **({"category": m.category} if m.category else {}),
                    **({"status": m.status} if m.status != "active" else {}),
                }
                for m in self.models
            ],
            "anchor": {
                "name": self.anchor.name,
                "artifact": self.anchor.artifact,
                "class": self.anchor.class_name,
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")


# ── Seed and Mode Contracts ──────────────────────────────────────────────────

MODES: dict[str, dict] = {
    "smoke": {"deals": 50, "seeds": [42]},
    "quick": {"deals": 2500, "seeds": [42]},
    "full": {"deals": 50000, "seeds": [42, 123, 456]},
}


@dataclass
class RungConfig:
    """Runtime configuration for a rung execution."""

    rung: str
    mode: str
    seeds: list[int]
    deals: int
    roster: Roster
    continuation_artifact: Path

    @classmethod
    def create(
        cls,
        rung: str,
        mode: str,
        roster: Roster,
        seeds: list[int] | None = None,
    ) -> RungConfig:
        """Create a rung config from mode defaults.

        Parameters
        ----------
        rung : str
            Rung identifier (e.g., "r2.0").
        mode : str
            Execution mode: "smoke", "quick", or "full".
        roster : Roster
            The model roster.
        seeds : list[int] | None
            Override default seeds for the mode.
        """
        if mode not in MODES:
            msg = f"Unknown mode {mode!r}; expected one of {sorted(MODES)}"
            raise ValueError(msg)
        mode_spec = MODES[mode]
        return cls(
            rung=rung,
            mode=mode,
            seeds=seeds if seeds is not None else mode_spec["seeds"],
            deals=mode_spec["deals"],
            roster=roster,
            continuation_artifact=Path("data/artifacts/arc_d/r0/hybrid_r0_full.json"),
        )

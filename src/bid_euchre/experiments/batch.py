"""
Batch intent metadata for promotion-track experiment runs.

Provides the BatchIntent dataclass for tagging runs with batch membership,
role, and purpose. Written into meta.json when --batch-id is given.
"""

from __future__ import annotations

import dataclasses
from typing import Any

VALID_BATCH_PURPOSES = frozenset({"promotion", "regression", "exploration"})


@dataclasses.dataclass(frozen=True)
class BatchIntent:
    """Batch membership metadata for an experiment run.

    Attributes:
        batch_id: Unique identifier for the batch (e.g. "promotion_20260210").
        batch_role: Role within the batch (e.g. "dataset_greedy", "outcomes_zoom").
        batch_purpose: Purpose category: "promotion", "regression", or "exploration".
    """

    batch_id: str
    batch_role: str
    batch_purpose: str

    def __post_init__(self) -> None:
        if not self.batch_id:
            raise ValueError("batch_id must be non-empty")
        if not self.batch_role:
            raise ValueError("batch_role must be non-empty")
        if self.batch_purpose not in VALID_BATCH_PURPOSES:
            raise ValueError(
                f"batch_purpose must be one of {sorted(VALID_BATCH_PURPOSES)}, "
                f"got {self.batch_purpose!r}"
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict for inclusion in meta.json."""
        return {
            "batch_id": self.batch_id,
            "batch_role": self.batch_role,
            "batch_purpose": self.batch_purpose,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BatchIntent:
        """Deserialize from dict (e.g. from meta.json)."""
        return cls(
            batch_id=d["batch_id"],
            batch_role=d["batch_role"],
            batch_purpose=d["batch_purpose"],
        )

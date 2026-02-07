"""
Batch intent metadata for experiment runs.

Provides optional batch metadata that can be attached to experiment runs
when they are part of a coordinated batch (e.g., promotion, regression).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BatchIntent:
    """Batch membership metadata for an experiment run.

    Attributes:
        batch_id: Unique batch identifier (e.g., "promotion_20260210").
        batch_role: Role of this run within the batch (e.g., "dataset_greedy").
        batch_purpose: Purpose category: "promotion", "regression", or "exploration".
    """

    batch_id: str
    batch_role: str
    batch_purpose: str

    VALID_PURPOSES = ("promotion", "regression", "exploration")

    def __post_init__(self):
        if not self.batch_id:
            raise ValueError("batch_id must be non-empty")
        if not self.batch_role:
            raise ValueError("batch_role must be non-empty")
        if self.batch_purpose not in self.VALID_PURPOSES:
            raise ValueError(
                f"batch_purpose must be one of {self.VALID_PURPOSES}, "
                f"got {self.batch_purpose!r}"
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict for embedding in meta.json."""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BatchIntent:
        """Deserialize from dict."""
        return cls(
            batch_id=d["batch_id"],
            batch_role=d["batch_role"],
            batch_purpose=d["batch_purpose"],
        )

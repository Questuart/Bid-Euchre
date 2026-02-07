"""Batch metadata for experiment runs.

Provides optional batch context (batch_id, batch_role, batch_purpose)
that can be attached to individual experiment runs via CLI flags.
"""

from dataclasses import asdict, dataclass
from typing import Optional

VALID_BATCH_ROLES = {"dataset", "baseline", "challenger", "gate"}
VALID_BATCH_PURPOSES = {"promotion", "exploration", "regression"}


@dataclass(frozen=True)
class BatchMetadata:
    """Immutable batch context for a single experiment run."""

    batch_id: str
    batch_role: str
    batch_purpose: str

    def __post_init__(self):
        if not self.batch_id:
            raise ValueError("batch_id must be non-empty")
        if self.batch_role not in VALID_BATCH_ROLES:
            raise ValueError(
                f"batch_role must be one of {sorted(VALID_BATCH_ROLES)}"
            )
        if self.batch_purpose not in VALID_BATCH_PURPOSES:
            raise ValueError(
                f"batch_purpose must be one of {sorted(VALID_BATCH_PURPOSES)}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_cli_args(
        cls,
        batch_id: Optional[str],
        batch_role: Optional[str],
        batch_purpose: Optional[str],
    ) -> Optional["BatchMetadata"]:
        """Create from CLI args. Returns None if all are None.

        Raises ValueError if only some flags are provided (all-or-nothing).
        """
        args = [batch_id, batch_role, batch_purpose]
        if all(a is None for a in args):
            return None
        if any(a is None for a in args):
            names = ["--batch-id", "--batch-role", "--batch-purpose"]
            provided = {n for n, v in zip(names, args) if v is not None}
            missing = set(names) - provided
            raise ValueError(
                f"Batch flags are all-or-nothing. "
                f"Provided: {sorted(provided)}, missing: {sorted(missing)}"
            )
        return cls(batch_id=batch_id, batch_role=batch_role, batch_purpose=batch_purpose)

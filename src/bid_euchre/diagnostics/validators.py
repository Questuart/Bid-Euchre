"""Validators for analysis rigor (sample sizes, budgets, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd

Purpose = Literal[
    "bias_detection",
    "feature_correlation",
    "tail_analysis",
    "production",
    "smoke_test",
]

# From .claude/rules/05_rigor.md
SAMPLE_SIZE_MINIMUMS = {
    "bias_detection": 2000,
    "feature_correlation": 1000,
    "tail_analysis": 5000,
    "production": 50000,
    "smoke_test": 100,  # Exemption for quick checks
}


@dataclass
class SampleSizeWarning:
    """Warning for insufficient sample size."""

    purpose: str
    actual: int
    minimum: int

    def __str__(self) -> str:
        return (
            f"⚠️  Sample size warning ({self.purpose}): "
            f"{self.actual} < {self.minimum} (minimum recommended)"
        )


class SampleSizeValidator:
    """Validate sample sizes meet rigor standards."""

    @classmethod
    def validate(
        cls,
        n_samples: int,
        purpose: Purpose,
    ) -> SampleSizeWarning | None:
        """Validate sample size for intended purpose.

        Args:
            n_samples: Actual sample size
            purpose: Intended analysis purpose

        Returns:
            SampleSizeWarning if insufficient, None if sufficient
        """
        minimum = SAMPLE_SIZE_MINIMUMS[purpose]

        if n_samples < minimum:
            return SampleSizeWarning(
                purpose=purpose,
                actual=n_samples,
                minimum=minimum,
            )

        return None

    @classmethod
    def check_dataframe(
        cls, df: pd.DataFrame, purpose: Purpose
    ) -> SampleSizeWarning | None:
        """Convenience method for DataFrames.

        Args:
            df: DataFrame to check
            purpose: Intended analysis purpose

        Returns:
            SampleSizeWarning if insufficient, None if sufficient
        """
        return cls.validate(len(df), purpose)

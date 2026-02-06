"""Health check computations for bidless dataset diagnostics.

Provides automated pass/warn/fail checks for dataset integrity,
designed for quick sanity verification before deeper analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: str  # "PASS", "WARN", "FAIL"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class HealthScorecard:
    """Collection of health check results."""

    checks: List[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True if no FAIL results."""
        return not any(c.status == "FAIL" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        """True if any WARN results."""
        return any(c.status == "WARN" for c in self.checks)

    def summary(self) -> Dict[str, int]:
        """Count of each status type."""
        counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for check in self.checks:
            counts[check.status] += 1
        return counts

    def get_warnings(self) -> List[CheckResult]:
        """Return all checks with WARN status."""
        return [c for c in self.checks if c.status == "WARN"]

    def get_failures(self) -> List[CheckResult]:
        """Return all checks with FAIL status."""
        return [c for c in self.checks if c.status == "FAIL"]


def compute_health_scorecard(df: pd.DataFrame) -> HealthScorecard:
    """Compute health scorecard for a bidless dataset.

    Runs a suite of integrity checks and returns a scorecard with
    PASS/WARN/FAIL status for each check.

    Args:
        df: DataFrame from load_bidless_dataset (with flattened features)

    Returns:
        HealthScorecard with all check results
    """
    scorecard = HealthScorecard()

    # Check 1: Row uniqueness
    scorecard.checks.append(_check_row_uniqueness(df))

    # Check 2: Seats per hand
    scorecard.checks.append(_check_seats_per_hand(df))

    # Check 3: NaN/Inf in features
    scorecard.checks.append(_check_feature_nans(df))

    # Check 4: Feature variance (no constant features)
    scorecard.checks.append(_check_feature_variance(df))

    # Check 5: Seat balance
    scorecard.checks.append(_check_seat_balance(df))

    # Check 6: Hand cards differ across seats
    scorecard.checks.append(_check_hands_differ(df))

    return scorecard


def _check_row_uniqueness(df: pd.DataFrame) -> CheckResult:
    """Check that (hand_id, seat) pairs are unique."""
    if "hand_id" not in df.columns or "seat" not in df.columns:
        return CheckResult(
            name="row_uniqueness",
            status="FAIL",
            message="Missing hand_id or seat columns",
        )

    duplicates = df.duplicated(subset=["hand_id", "seat"]).sum()
    if duplicates > 0:
        return CheckResult(
            name="row_uniqueness",
            status="FAIL",
            message=f"Found {duplicates} duplicate (hand_id, seat) pairs",
            details={"duplicate_count": int(duplicates)},
        )

    return CheckResult(
        name="row_uniqueness",
        status="PASS",
        message="All (hand_id, seat) pairs are unique",
    )


def _check_seats_per_hand(df: pd.DataFrame) -> CheckResult:
    """Check that each hand_id has exactly 4 seats."""
    if "hand_id" not in df.columns:
        return CheckResult(
            name="seats_per_hand",
            status="FAIL",
            message="Missing hand_id column",
        )

    seats_per_hand = df.groupby("hand_id").size()
    bad_hands = seats_per_hand[seats_per_hand != 4]

    if len(bad_hands) > 0:
        return CheckResult(
            name="seats_per_hand",
            status="FAIL",
            message=f"{len(bad_hands)} hands don't have exactly 4 seats",
            details={
                "bad_hand_count": len(bad_hands),
                "example_counts": bad_hands.head(5).to_dict(),
            },
        )

    return CheckResult(
        name="seats_per_hand",
        status="PASS",
        message=f"All {len(seats_per_hand)} hands have exactly 4 seats",
    )


def _check_feature_nans(df: pd.DataFrame) -> CheckResult:
    """Check for NaN/Inf values in feature columns."""
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    if not feat_cols:
        return CheckResult(
            name="feature_nans",
            status="WARN",
            message="No feature columns found (feat_* prefix)",
        )

    nan_counts = {}
    inf_counts = {}
    for col in feat_cols:
        if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            nan_counts[col] = int(df[col].isna().sum())
            inf_counts[col] = int(np.isinf(df[col].fillna(0)).sum())

    total_nans = sum(nan_counts.values())
    total_infs = sum(inf_counts.values())

    if total_nans > 0 or total_infs > 0:
        return CheckResult(
            name="feature_nans",
            status="FAIL",
            message=f"Found {total_nans} NaN and {total_infs} Inf values in features",
            details={"nan_counts": nan_counts, "inf_counts": inf_counts},
        )

    return CheckResult(
        name="feature_nans",
        status="PASS",
        message=f"No NaN/Inf values in {len(feat_cols)} feature columns",
    )


def _check_feature_variance(df: pd.DataFrame) -> CheckResult:
    """Check for constant features (zero variance)."""
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    if not feat_cols:
        return CheckResult(
            name="feature_variance",
            status="WARN",
            message="No feature columns found",
        )

    constant_cols = []
    for col in feat_cols:
        if df[col].dtype in [np.float64, np.float32, np.int64, np.int32]:
            if df[col].std() == 0:
                constant_cols.append(col)

    if constant_cols:
        return CheckResult(
            name="feature_variance",
            status="WARN",
            message=f"{len(constant_cols)} feature(s) have zero variance (constant)",
            details={"constant_features": constant_cols},
        )

    return CheckResult(
        name="feature_variance",
        status="PASS",
        message=f"All {len(feat_cols)} features have non-zero variance",
    )


def _check_seat_balance(df: pd.DataFrame) -> CheckResult:
    """Check that hand_value is roughly balanced across seats.

    Uses bounded tolerance (20-30% per seat) instead of statistical tests
    to avoid CI flakiness.
    """
    if "seat" not in df.columns or "feat_hand_value" not in df.columns:
        return CheckResult(
            name="seat_balance",
            status="WARN",
            message="Missing seat or feat_hand_value column",
        )

    means = df.groupby("seat")["feat_hand_value"].mean()
    if len(means) != 4:
        return CheckResult(
            name="seat_balance",
            status="WARN",
            message=f"Expected 4 seats, found {len(means)}",
        )

    global_mean = df["feat_hand_value"].mean()
    # Allow 5% deviation from global mean
    tolerance = 0.05 * abs(global_mean) if global_mean != 0 else 0.1

    deviations = {}
    worst_deviation = 0
    for seat in range(4):
        if seat in means.index:
            dev = abs(means[seat] - global_mean)
            deviations[seat] = dev
            worst_deviation = max(worst_deviation, dev)

    if worst_deviation > tolerance:
        return CheckResult(
            name="seat_balance",
            status="WARN",
            message=f"Seat means deviate by up to {worst_deviation:.3f} from global mean",
            details={
                "seat_means": means.to_dict(),
                "global_mean": global_mean,
                "tolerance": tolerance,
            },
        )

    return CheckResult(
        name="seat_balance",
        status="PASS",
        message="Seat hand_value means are balanced within tolerance",
        details={"seat_means": means.to_dict(), "global_mean": global_mean},
    )


def _check_hands_differ(df: pd.DataFrame) -> CheckResult:
    """Check that hand_cards differ across seats within each hand.

    This catches the per-seat feature bug where all seats got the same hand data.
    """
    if "hand_cards" not in df.columns or "hand_id" not in df.columns:
        return CheckResult(
            name="hands_differ",
            status="WARN",
            message="Missing hand_cards or hand_id column",
        )

    # Sample a subset of hands to check (for performance)
    sample_hands = df["hand_id"].unique()[:100]

    identical_count = 0
    for hand_id in sample_hands:
        hand_rows = df[df["hand_id"] == hand_id]
        if len(hand_rows) < 2:
            continue

        # Convert hand_cards to comparable format (handles both lists and numpy arrays)
        cards = hand_rows["hand_cards"].apply(lambda x: tuple(sorted(x)))
        unique_cards = cards.nunique()

        # All 4 seats should have different cards
        if unique_cards < len(hand_rows):
            identical_count += 1

    if identical_count > 0:
        return CheckResult(
            name="hands_differ",
            status="FAIL",
            message=f"{identical_count}/{len(sample_hands)} sampled hands have identical cards across seats",
            details={"identical_hands": identical_count, "sampled_hands": len(sample_hands)},
        )

    return CheckResult(
        name="hands_differ",
        status="PASS",
        message=f"All {len(sample_hands)} sampled hands have distinct cards per seat",
    )


def display_scorecard(scorecard: HealthScorecard) -> str:
    """Format scorecard as a human-readable string.

    Args:
        scorecard: HealthScorecard to display

    Returns:
        Formatted string with status badges
    """
    summary = scorecard.summary()
    header = f"Health Scorecard: {summary['PASS']} PASS, {summary['WARN']} WARN, {summary['FAIL']} FAIL"

    lines = [header, "=" * len(header), ""]

    for check in scorecard.checks:
        badge = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[check.status]
        lines.append(f"{badge} {check.name}: {check.message}")

    return "\n".join(lines)


def display_issues(scorecard: HealthScorecard) -> str:
    """Format warnings and failures as compact list.

    Returns empty string if no issues. Shows failures first, then warnings.

    Example:
        Issues found:
        ❌ row_uniqueness: Found 3 duplicate pairs
        ⚠️  feature_variance: 2 features have zero variance

    Args:
        scorecard: HealthScorecard to display issues from

    Returns:
        Formatted string with compact issue list, or empty string if no issues
    """
    failures = scorecard.get_failures()
    warnings = scorecard.get_warnings()
    issues = failures + warnings

    if not issues:
        return ""

    lines = ["Issues found:"]
    for check in issues:
        badge = "❌" if check.status == "FAIL" else "⚠️ "
        lines.append(f"{badge} {check.name}: {check.message}")

    return "\n".join(lines)

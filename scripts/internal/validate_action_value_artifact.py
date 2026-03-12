"""
Behavioral validation gate for action-value artifacts.

Checks structural integrity, offline quality, and behavioral sanity of
action_value_olsa_v1 and action_value_gbt_v1 artifacts before they are
used in experiments or reports.

This catches pathological artifacts (e.g., "always bids 10") that pass
Gate X2 R² thresholds but produce catastrophic gameplay.

CLI usage:
    uv run python scripts/internal/validate_action_value_artifact.py \
        --artifact data/artifacts/arc_d/r1_5/action_value_full.json

    # Strict mode (exits non-zero on any failure):
    uv run python scripts/internal/validate_action_value_artifact.py \
        --artifact data/artifacts/arc_d/r1_5/action_value_full.json --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    BidAction,
    BiddingObservation,
    enumerate_legal_actions,
    extract_action_features,
    extract_state_features,
    predict_ols,
)

# ── Thresholds ─────────────────────────────────────────────

# Behavioral thresholds — generous enough that any valid artifact passes
# easily, but catches catastrophic failures like "always bid 10".
MAX_AVG_BID = 8.0
MIN_PASS_RATE = 0.01
MAX_BID_10_RATE = 0.30
MIN_CONTRACT_DIVERSITY = 2
MIN_BID_LEVEL_STD = 0.5

# Enhanced R² floors (stricter than Gate X2's 0.05)
R2_FLOOR = {
    "suit": 0.20,
    "high": 0.20,
    "low": 0.20,
    "pass": 0.01,
}

MAX_MAE = 10.0


# ── Synthetic Test Hands ───────────────────────────────────


def _make_test_hands() -> list[list[Card]]:
    """Generate deterministic synthetic hands for behavioral testing.

    Returns 4 distinct hands covering different hand types:
    - Strong suit hand (lots of trump)
    - Balanced hand (spread across suits)
    - Strong no-trump hand (aces and kings)
    - Weak hand (low cards, voids)
    """
    hands = []

    # Hand 1: Strong suit hand — lots of hearts
    hands.append(
        [
            Card(rank="J", suit="H"),
            Card(rank="J", suit="D"),  # Left bower if H is trump
            Card(rank="A", suit="H"),
            Card(rank="K", suit="H"),
            Card(rank="Q", suit="H"),
            Card(rank="T", suit="H"),
            Card(rank="A", suit="S"),
            Card(rank="K", suit="S"),
            Card(rank="A", suit="C"),
            Card(rank="T", suit="D"),
        ]
    )

    # Hand 2: Balanced hand
    hands.append(
        [
            Card(rank="A", suit="C"),
            Card(rank="K", suit="C"),
            Card(rank="Q", suit="C"),
            Card(rank="A", suit="D"),
            Card(rank="K", suit="D"),
            Card(rank="A", suit="H"),
            Card(rank="K", suit="H"),
            Card(rank="A", suit="S"),
            Card(rank="K", suit="S"),
            Card(rank="Q", suit="S"),
        ]
    )

    # Hand 3: Strong high/low hand (no dominant suit)
    hands.append(
        [
            Card(rank="A", suit="C"),
            Card(rank="A", suit="D"),
            Card(rank="A", suit="H"),
            Card(rank="A", suit="S"),
            Card(rank="K", suit="C"),
            Card(rank="K", suit="D"),
            Card(rank="K", suit="H"),
            Card(rank="K", suit="S"),
            Card(rank="Q", suit="C"),
            Card(rank="Q", suit="D"),
        ]
    )

    # Hand 4: Weak hand
    hands.append(
        [
            Card(rank="T", suit="C"),
            Card(rank="T", suit="D"),
            Card(rank="T", suit="H"),
            Card(rank="T", suit="S"),
            Card(rank="J", suit="C"),
            Card(rank="Q", suit="D"),
            Card(rank="Q", suit="H"),
            Card(rank="Q", suit="S"),
            Card(rank="K", suit="C"),
            Card(rank="J", suit="S"),
        ]
    )

    return hands


def _make_test_observations() -> list[BiddingObservation]:
    """Generate deterministic test observations across hands, seats, and bid levels."""
    hands = _make_test_hands()
    observations = []

    for hand in hands:
        for seat in (0, 1, 2, 3):
            for current_high_bid in (0, 3, 7):
                observations.append(
                    BiddingObservation(
                        hand=hand,
                        seat=seat,
                        dealer_seat=0,
                        current_high_bid=current_high_bid,
                        allowed_contracts=("C", "D", "H", "S", "HIGH", "LOW"),
                        auction_transcript=(),
                    )
                )

    return observations


# ── Validation Result ──────────────────────────────────────


@dataclass
class ValidationResult:
    """Result of artifact validation."""

    passed: bool
    checks: list[dict] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            self.passed = False

    def summary(self) -> dict:
        """Return summary dict suitable for artifact metadata."""
        return {
            "passed": self.passed,
            "n_checks": len(self.checks),
            "n_passed": sum(1 for c in self.checks if c["passed"]),
            "n_failed": sum(1 for c in self.checks if not c["passed"]),
            "failures": [c for c in self.checks if not c["passed"]],
        }


# ── Structural Checks ─────────────────────────────────────


def validate_structural(artifact: dict, artifact_path: str) -> ValidationResult:
    """Validate artifact structure and metadata."""
    result = ValidationResult(passed=True)

    # Schema version
    schema = artifact.get("schema_version")
    valid_schemas = ("action_value_olsa_v1", "action_value_gbt_v1")
    result.add_check(
        "schema_version",
        schema in valid_schemas,
        f"schema_version='{schema}', expected one of {valid_schemas}",
    )

    # All 4 model families present
    models = artifact.get("models", {})
    for family in ("suit", "high", "low", "pass"):
        result.add_check(
            f"model_{family}_present",
            family in models,
            f"model family '{family}' {'present' if family in models else 'MISSING'}",
        )

    # Feature names present in each model
    for family in ("suit", "high", "low", "pass"):
        model = models.get(family, {})
        has_names = "feature_names" in model
        result.add_check(
            f"feature_names_{family}",
            has_names,
            f"{family} feature_names {'present' if has_names else 'MISSING'}",
        )

    # Required metadata
    metadata = artifact.get("metadata", {})
    for field_name in ("training_seed", "git_sha", "created_at_utc"):
        has_field = field_name in metadata
        result.add_check(
            f"metadata_{field_name}",
            has_field,
            f"metadata.{field_name} {'present' if has_field else 'MISSING'}",
        )

    # Target field
    has_target = "target" in artifact
    result.add_check(
        "target_field",
        has_target,
        f"target field {'present' if has_target else 'MISSING'}",
    )

    # GBT-specific: check model files exist
    if schema == "action_value_gbt_v1":
        artifact_dir = Path(artifact_path).parent
        for family in ("suit", "high", "low", "pass"):
            model = models.get(family, {})
            model_file = model.get("model_file")
            if model_file:
                full_path = artifact_dir / model_file
                exists = full_path.exists()
                result.add_check(
                    f"gbt_model_file_{family}",
                    exists,
                    f"{model_file} {'exists' if exists else 'NOT FOUND at ' + str(full_path)}",
                )

    return result


# ── Quality Checks ─────────────────────────────────────────


def validate_quality(artifact: dict) -> ValidationResult:
    """Validate offline quality metrics (enhanced Gate X2)."""
    result = ValidationResult(passed=True)
    models = artifact.get("models", {})

    for family, threshold in R2_FLOOR.items():
        model = models.get(family, {})
        r2 = model.get("r_squared")
        if r2 is None:
            result.add_check(
                f"r2_{family}",
                False,
                f"{family} r_squared missing",
            )
            continue
        passed = r2 > threshold
        result.add_check(
            f"r2_{family}",
            passed,
            f"{family} R²={r2:.4f} {'>' if passed else '<='} {threshold} floor",
        )

    # MAE sanity
    for family in ("suit", "high", "low", "pass"):
        model = models.get(family, {})
        mae = model.get("mae")
        if mae is not None:
            passed = mae < MAX_MAE
            result.add_check(
                f"mae_{family}",
                passed,
                f"{family} MAE={mae:.3f} {'<' if passed else '>='} {MAX_MAE}",
            )

    return result


# ── Behavioral Checks ─────────────────────────────────────


@dataclass
class BehavioralStats:
    """Statistics from behavioral probe of an artifact."""

    avg_bid: float = 0.0
    pass_rate: float = 0.0
    bid_10_rate: float = 0.0
    contract_diversity: int = 0
    bid_level_std: float = 0.0
    n_observations: int = 0


def probe_ols_artifact(artifact: dict) -> BehavioralStats:
    """Probe an OLS artifact's behavior on synthetic observations.

    Runs the same logic as ActionValueBidder.choose_bid() but directly
    on the artifact dict, without requiring a full bidder instantiation.
    """
    models = artifact.get("models", {})
    observations = _make_test_observations()

    bid_levels = []
    contracts_seen: set[str] = set()
    n_pass = 0

    feature_set = artifact.get("feature_set", "full")
    has_interactions = feature_set == "interaction"

    for obs in observations:
        legal = enumerate_legal_actions(obs)
        best_value = float("-inf")
        best_action = BidAction.pass_bid()

        for action in legal:
            if action.is_pass():
                state = extract_state_features(obs, "none", None)
                if has_interactions:
                    from bid_euchre.strategy.bidding import compute_interaction_features

                    state = np.concatenate([state, compute_interaction_features(state)])
                value = predict_ols(models["pass"], state)
            else:
                contract_type, trump_suit = action.to_contract_tuple()
                family = contract_type
                state = extract_state_features(obs, family, trump_suit)
                if has_interactions:
                    from bid_euchre.strategy.bidding import compute_interaction_features

                    state = np.concatenate([state, compute_interaction_features(state)])
                action_feats = extract_action_features(action.n)
                features = np.concatenate([state, action_feats])
                value = predict_ols(models[family], features)

            if value > best_value:
                best_value = value
                best_action = action

        if best_action.is_pass():
            n_pass += 1
            bid_levels.append(0)
        else:
            bid_levels.append(best_action.n)
            ct, _ = best_action.to_contract_tuple()
            contracts_seen.add(ct)

    bid_array = np.array(bid_levels)
    non_pass = bid_array[bid_array > 0]

    return BehavioralStats(
        avg_bid=float(np.mean(bid_array)) if len(bid_array) > 0 else 0.0,
        pass_rate=n_pass / len(observations) if observations else 0.0,
        bid_10_rate=float(np.mean(bid_array == 10)) if len(bid_array) > 0 else 0.0,
        contract_diversity=len(contracts_seen),
        bid_level_std=float(np.std(non_pass)) if len(non_pass) > 1 else 0.0,
        n_observations=len(observations),
    )


def probe_gbt_artifact(artifact_path: str) -> BehavioralStats:
    """Probe a GBT artifact's behavior by instantiating the bidder."""
    from bid_euchre.strategy.bidding import GBTActionValueBidder

    bidder = GBTActionValueBidder(
        artifact_path=artifact_path,
        name="probe",
        skip_behavioral_check=True,
    )
    observations = _make_test_observations()

    bid_levels = []
    contracts_seen: set[str] = set()
    n_pass = 0

    for obs in observations:
        action = bidder.choose_bid(obs)
        if action.is_pass():
            n_pass += 1
            bid_levels.append(0)
        else:
            bid_levels.append(action.n)
            ct, _ = action.to_contract_tuple()
            contracts_seen.add(ct)

    bid_array = np.array(bid_levels)
    non_pass = bid_array[bid_array > 0]

    return BehavioralStats(
        avg_bid=float(np.mean(bid_array)) if len(bid_array) > 0 else 0.0,
        pass_rate=n_pass / len(observations) if observations else 0.0,
        bid_10_rate=float(np.mean(bid_array == 10)) if len(bid_array) > 0 else 0.0,
        contract_diversity=len(contracts_seen),
        bid_level_std=float(np.std(non_pass)) if len(non_pass) > 1 else 0.0,
        n_observations=len(observations),
    )


def validate_behavioral(
    artifact: dict, artifact_path: str
) -> tuple[ValidationResult, BehavioralStats]:
    """Run behavioral validation on an artifact."""
    result = ValidationResult(passed=True)

    schema = artifact.get("schema_version")

    if schema == "action_value_gbt_v1":
        stats = probe_gbt_artifact(artifact_path)
    else:
        stats = probe_ols_artifact(artifact)

    result.add_check(
        "avg_bid",
        stats.avg_bid < MAX_AVG_BID,
        f"avg_bid={stats.avg_bid:.2f} {'<' if stats.avg_bid < MAX_AVG_BID else '>='} {MAX_AVG_BID}",
    )

    result.add_check(
        "pass_rate",
        stats.pass_rate > MIN_PASS_RATE,
        f"pass_rate={stats.pass_rate:.3f} {'>' if stats.pass_rate > MIN_PASS_RATE else '<='} {MIN_PASS_RATE}",
    )

    result.add_check(
        "bid_10_rate",
        stats.bid_10_rate < MAX_BID_10_RATE,
        f"bid_10_rate={stats.bid_10_rate:.3f} {'<' if stats.bid_10_rate < MAX_BID_10_RATE else '>='} {MAX_BID_10_RATE}",
    )

    result.add_check(
        "contract_diversity",
        stats.contract_diversity >= MIN_CONTRACT_DIVERSITY,
        f"contract_diversity={stats.contract_diversity} {'>=' if stats.contract_diversity >= MIN_CONTRACT_DIVERSITY else '<'} {MIN_CONTRACT_DIVERSITY}",
    )

    result.add_check(
        "bid_level_std",
        stats.bid_level_std > MIN_BID_LEVEL_STD,
        f"bid_level_std={stats.bid_level_std:.3f} {'>' if stats.bid_level_std > MIN_BID_LEVEL_STD else '<='} {MIN_BID_LEVEL_STD}",
    )

    return result, stats


# ── Full Validation ────────────────────────────────────────


def validate_artifact(artifact_path: str) -> tuple[bool, dict]:
    """Run full validation suite on an action-value artifact.

    Returns (passed, report_dict) where report_dict contains all check results
    and behavioral statistics.
    """
    path = Path(artifact_path)
    if not path.exists():
        return False, {"error": f"Artifact not found: {artifact_path}"}

    with open(path) as f:
        artifact = json.load(f)

    structural = validate_structural(artifact, artifact_path)
    quality = validate_quality(artifact)

    # Only run behavioral checks if structural checks pass
    if structural.passed:
        behavioral, stats = validate_behavioral(artifact, artifact_path)
    else:
        behavioral = ValidationResult(passed=False)
        behavioral.add_check(
            "skipped", False, "Behavioral checks skipped due to structural failures"
        )
        stats = BehavioralStats()

    all_passed = structural.passed and quality.passed and behavioral.passed

    report = {
        "artifact_path": str(artifact_path),
        "passed": all_passed,
        "structural": structural.summary(),
        "quality": quality.summary(),
        "behavioral": behavioral.summary(),
        "behavioral_stats": {
            "avg_bid": stats.avg_bid,
            "pass_rate": stats.pass_rate,
            "bid_10_rate": stats.bid_10_rate,
            "contract_diversity": stats.contract_diversity,
            "bid_level_std": stats.bid_level_std,
            "n_observations": stats.n_observations,
        },
    }

    return all_passed, report


# ── CLI ────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Validate an action-value artifact for behavioral sanity"
    )
    parser.add_argument(
        "--artifact",
        required=True,
        help="Path to the action-value artifact JSON file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code on any failure",
    )
    parser.add_argument(
        "--json-report",
        help="Path to write JSON validation report",
    )
    args = parser.parse_args()

    passed, report = validate_artifact(args.artifact)

    # Print human-readable summary
    print("=== Action-Value Artifact Validation ===")
    print(f"  Artifact: {args.artifact}")
    print(f"  Overall: {'PASS' if passed else 'FAIL'}")
    print()

    for section in ("structural", "quality", "behavioral"):
        section_data = report[section]
        status = "PASS" if section_data["n_failed"] == 0 else "FAIL"
        print(
            f"  {section.capitalize()}: {status} "
            f"({section_data['n_passed']}/{section_data['n_checks']} checks passed)"
        )
        if section_data["failures"]:
            for failure in section_data["failures"]:
                print(f"    FAIL: {failure['name']} — {failure['detail']}")

    if report.get("behavioral_stats", {}).get("n_observations", 0) > 0:
        stats = report["behavioral_stats"]
        print()
        print("  Behavioral stats:")
        print(f"    avg_bid: {stats['avg_bid']:.2f}")
        print(f"    pass_rate: {stats['pass_rate']:.3f}")
        print(f"    bid_10_rate: {stats['bid_10_rate']:.3f}")
        print(f"    contract_diversity: {stats['contract_diversity']}")
        print(f"    bid_level_std: {stats['bid_level_std']:.3f}")

    if args.json_report:
        Path(args.json_report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_report).write_text(json.dumps(report, indent=2))
        print(f"\n  Report written to: {args.json_report}")

    if args.strict and not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Blind strategy comparison for Arc D evaluation.

Anonymizes two strategy performance profiles, generates an independent
rubric-based comparison, then unblinds to reveal identities.

Usage:
    uv run python scripts/internal/blind_strategy_comparison.py \
        --profile-a data/runs/<run_a>/eval_metrics.json \
        --profile-b data/runs/<run_b>/eval_metrics.json \
        --seed 42 \
        --output blind_comparison.json

    uv run python scripts/internal/blind_strategy_comparison.py \
        --profile-a data/runs/<run_a>/eval_metrics.json \
        --profile-b data/runs/<run_b>/eval_metrics.json \
        --seed 42 \
        --format markdown
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

CONTRACT_TYPES = ("suit", "high", "low")

# Rubric criteria with weights (pooled gets 2x)
RUBRIC_CRITERIA = [
    ("pooled_net_eppd", 2.0),
    ("worst_contract_risk", 1.0),
    ("cross_contract_consistency", 1.0),
    ("statistical_significance", 1.0),
    ("seed_stability", 1.0),
]

# Keys that are safe to keep in anonymized profiles (performance-only)
_SAFE_METRIC_KEYS = frozenset(
    {
        "net_eppd",
        "net_expected_points_per_deal",
        "eppd",
        "expected_points_per_deal",
        "net_eppd_delta",
        "ci_low",
        "ci_high",
        "win_rate",
        "bid_rate",
        "make_rate",
        "cvar_5",
        "net_cvar_5",
        "downside_variance",
        "net_downside_variance",
        "pass_rate",
        "deals_total",
        "n_deals",
        "hands_with_bids",
        # Per-contract nested keys
        "pooled",
        "suit",
        "high",
        "low",
        # Multi-seed keys
        "seeds",
        "seed_deltas",
    }
)

# Keys that indicate identifying information and must be stripped
_IDENTIFYING_KEYS = frozenset(
    {
        "strategy_id",
        "strategy_name",
        "model_type",
        "model_path",
        "artifact_path",
        "feature_count",
        "feature_names",
        "training_rows",
        "class_name",
        "params",
        "config",
        "run_id",
        "source_logs",
        "provenance",
        "git_sha",
    }
)


@dataclass
class RubricScore:
    """A single criterion score in the blind comparison rubric."""

    criterion: str
    weight: float
    score_alpha: int  # 1-5
    score_beta: int  # 1-5
    reasoning: str


@dataclass
class BlindComparisonResult:
    """Full result of a blind strategy comparison."""

    seed: int
    label_assignment: dict  # {"Alpha": "real_name_a", "Beta": "real_name_b"}
    rubric: list[RubricScore] = field(default_factory=list)
    alpha_total: float = 0.0
    beta_total: float = 0.0
    winner: str = "Tie"  # "Alpha" or "Beta" or "Tie"
    winner_real_name: str = ""
    confidence: str = "weak"  # "strong", "moderate", "weak"
    summary: str = ""


# ---------------------------------------------------------------------------
# Profile loading and anonymization
# ---------------------------------------------------------------------------


def load_profile(path: str | Path) -> dict:
    """Load an eval metrics JSON profile.

    Handles three formats:
    1. Full evaluator output: {"strategies": [{...metrics...}]}
    2. Nested: {"metrics": {...}}
    3. Flat: top-level metrics dict

    Args:
        path: Path to eval metrics JSON file.

    Returns:
        Dict of metric name -> value.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is invalid JSON.
    """
    with open(path) as f:
        data = json.load(f)

    if "strategies" in data and isinstance(data["strategies"], list):
        return data["strategies"][0] if data["strategies"] else {}
    if "metrics" in data:
        return data["metrics"]
    return data


def _extract_strategy_name(profile: dict) -> str:
    """Extract a human-readable strategy name from a profile.

    Checks common keys where the name might be stored.

    Args:
        profile: Raw eval metrics dict.

    Returns:
        Strategy name string, or "unknown" if not found.
    """
    for key in ("strategy_id", "strategy_name", "name"):
        val = profile.get(key)
        if isinstance(val, str) and val:
            return val
    return "unknown"


def anonymize_profile(profile: dict) -> dict:
    """Strip all identifying information from a profile.

    Keeps only performance metrics: net_eppd, CIs, p-values, H2H deltas,
    win rates, and per-contract breakdowns. Removes strategy names, model
    types, feature counts, file paths, and training details.

    Args:
        profile: Raw eval metrics dict.

    Returns:
        New dict with only safe metric keys.
    """
    result = {}
    for key, value in profile.items():
        if key in _IDENTIFYING_KEYS:
            continue
        if isinstance(value, dict):
            # Recurse into nested dicts (e.g., per-contract metrics)
            cleaned = anonymize_profile(value)
            if cleaned:
                result[key] = cleaned
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # List of dicts (e.g., per-seed results)
            result[key] = [anonymize_profile(item) for item in value]
        else:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Metric extraction helpers
# ---------------------------------------------------------------------------


def _get_metric(profile: dict, key: str, default: float = 0.0) -> float:
    """Safely extract a float metric, handling aliases.

    Args:
        profile: Metrics dict.
        key: Metric key.
        default: Fallback value.

    Returns:
        Float metric value.
    """
    # Try direct key first
    val = profile.get(key)
    if val is not None:
        try:
            return float(val)
        except (TypeError, ValueError):
            pass

    # Try common aliases
    aliases = {
        "net_eppd": "net_expected_points_per_deal",
        "net_expected_points_per_deal": "net_eppd",
    }
    alias = aliases.get(key)
    if alias:
        val = profile.get(alias)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass

    return default


def _get_per_contract_eppd(profile: dict) -> dict[str, float]:
    """Extract per-contract net_eppd values from a profile.

    Looks for contract-type keys at top level or in nested structures.

    Args:
        profile: Metrics dict.

    Returns:
        Dict mapping contract type ("suit", "high", "low") to net_eppd.
    """
    result = {}
    for ct in CONTRACT_TYPES:
        # Try nested dict
        ct_data = profile.get(ct)
        if isinstance(ct_data, dict):
            val = _get_metric(ct_data, "net_eppd")
            result[ct] = val
        else:
            # Try flat key pattern: net_eppd_suit, net_eppd_high, etc.
            val = profile.get(f"net_eppd_{ct}")
            if val is not None:
                try:
                    result[ct] = float(val)
                except (TypeError, ValueError):
                    pass
    return result


def _get_seed_deltas(profile: dict) -> list[float]:
    """Extract per-seed delta values if multi-seed data is present.

    Args:
        profile: Metrics dict.

    Returns:
        List of per-seed delta floats, or empty list if not available.
    """
    # Try explicit seed_deltas key
    deltas = profile.get("seed_deltas")
    if isinstance(deltas, list):
        return [float(d) for d in deltas if d is not None]

    # Try seeds list
    seeds = profile.get("seeds")
    if isinstance(seeds, list):
        return [
            float(s.get("net_eppd_delta", s.get("net_eppd", 0.0)))
            for s in seeds
            if isinstance(s, dict)
        ]

    return []


# ---------------------------------------------------------------------------
# Rubric scoring
# ---------------------------------------------------------------------------


def _score_pooled_net_eppd(alpha: dict, beta: dict) -> tuple[int, int, str]:
    """Score criterion 1: pooled net_eppd delta.

    Higher pooled net_eppd is better. Score 1-5 based on relative position.

    Args:
        alpha: Anonymous profile for Strategy Alpha.
        beta: Anonymous profile for Strategy Beta.

    Returns:
        (score_alpha, score_beta, reasoning)
    """
    a_val = _get_metric(alpha, "net_eppd")
    b_val = _get_metric(beta, "net_eppd")
    delta = a_val - b_val

    # Score based on magnitude of difference
    if abs(delta) < 0.01:
        return (
            3,
            3,
            f"Pooled net_eppd nearly identical (Alpha={a_val:.3f}, Beta={b_val:.3f}, delta={delta:+.3f})",
        )

    if delta > 0:
        # Alpha better
        if abs(delta) > 0.5:
            return (
                5,
                1,
                f"Alpha strongly superior in pooled net_eppd ({a_val:.3f} vs {b_val:.3f}, delta={delta:+.3f})",
            )
        if abs(delta) > 0.2:
            return (
                4,
                2,
                f"Alpha moderately better in pooled net_eppd ({a_val:.3f} vs {b_val:.3f}, delta={delta:+.3f})",
            )
        return (
            4,
            3,
            f"Alpha slightly better in pooled net_eppd ({a_val:.3f} vs {b_val:.3f}, delta={delta:+.3f})",
        )
    else:
        # Beta better
        if abs(delta) > 0.5:
            return (
                1,
                5,
                f"Beta strongly superior in pooled net_eppd ({b_val:.3f} vs {a_val:.3f}, delta={delta:+.3f})",
            )
        if abs(delta) > 0.2:
            return (
                2,
                4,
                f"Beta moderately better in pooled net_eppd ({b_val:.3f} vs {a_val:.3f}, delta={delta:+.3f})",
            )
        return (
            3,
            4,
            f"Beta slightly better in pooled net_eppd ({b_val:.3f} vs {a_val:.3f}, delta={delta:+.3f})",
        )


def _score_worst_contract_risk(alpha: dict, beta: dict) -> tuple[int, int, str]:
    """Score criterion 2: worst-contract risk.

    Which strategy has the least-negative worst contract? Lower downside is better.

    Args:
        alpha: Anonymous profile for Strategy Alpha.
        beta: Anonymous profile for Strategy Beta.

    Returns:
        (score_alpha, score_beta, reasoning)
    """
    a_contracts = _get_per_contract_eppd(alpha)
    b_contracts = _get_per_contract_eppd(beta)

    if not a_contracts and not b_contracts:
        return (3, 3, "No per-contract data available for either strategy")

    # Use 0.0 as default if one strategy has no per-contract data
    a_worst = min(a_contracts.values()) if a_contracts else 0.0
    b_worst = min(b_contracts.values()) if b_contracts else 0.0

    a_worst_ct = min(a_contracts, key=a_contracts.get) if a_contracts else "N/A"
    b_worst_ct = min(b_contracts, key=b_contracts.get) if b_contracts else "N/A"

    delta = a_worst - b_worst

    if abs(delta) < 0.01:
        return (
            3,
            3,
            f"Similar worst-contract performance "
            f"(Alpha worst={a_worst:.3f} [{a_worst_ct}], "
            f"Beta worst={b_worst:.3f} [{b_worst_ct}])",
        )

    if delta > 0:
        # Alpha's worst is less negative -> better
        severity = 5 if delta > 0.3 else 4
        return (
            severity,
            6 - severity,
            f"Alpha has less downside risk in worst contract "
            f"(Alpha worst={a_worst:.3f} [{a_worst_ct}], "
            f"Beta worst={b_worst:.3f} [{b_worst_ct}])",
        )
    else:
        severity = 5 if abs(delta) > 0.3 else 4
        return (
            6 - severity,
            severity,
            f"Beta has less downside risk in worst contract "
            f"(Beta worst={b_worst:.3f} [{b_worst_ct}], "
            f"Alpha worst={a_worst:.3f} [{a_worst_ct}])",
        )


def _score_cross_contract_consistency(alpha: dict, beta: dict) -> tuple[int, int, str]:
    """Score criterion 3: consistency across contracts.

    Lower variance in per-contract deltas indicates more consistent improvement.

    Args:
        alpha: Anonymous profile for Strategy Alpha.
        beta: Anonymous profile for Strategy Beta.

    Returns:
        (score_alpha, score_beta, reasoning)
    """
    a_contracts = _get_per_contract_eppd(alpha)
    b_contracts = _get_per_contract_eppd(beta)

    if len(a_contracts) < 2 and len(b_contracts) < 2:
        return (3, 3, "Insufficient per-contract data for consistency comparison")

    # Compute standard deviation of per-contract values
    a_vals = list(a_contracts.values()) if len(a_contracts) >= 2 else []
    b_vals = list(b_contracts.values()) if len(b_contracts) >= 2 else []

    a_std = statistics.stdev(a_vals) if len(a_vals) >= 2 else float("inf")
    b_std = statistics.stdev(b_vals) if len(b_vals) >= 2 else float("inf")

    if a_std == float("inf") and b_std == float("inf"):
        return (3, 3, "Neither strategy has enough per-contract data")

    # Count contracts with positive net_eppd
    a_positive = sum(1 for v in a_vals if v > 0) if a_vals else 0
    b_positive = sum(1 for v in b_vals if v > 0) if b_vals else 0

    delta_std = a_std - b_std

    if abs(delta_std) < 0.05:
        return (
            3,
            3,
            f"Similar cross-contract consistency "
            f"(Alpha std={a_std:.3f}, {a_positive}/{len(a_vals)} positive; "
            f"Beta std={b_std:.3f}, {b_positive}/{len(b_vals)} positive)",
        )

    if delta_std < 0:
        # Alpha has lower std -> more consistent
        score = 4 if abs(delta_std) < 0.2 else 5
        return (
            score,
            6 - score,
            f"Alpha more consistent across contracts "
            f"(Alpha std={a_std:.3f}, {a_positive}/{len(a_vals)} positive; "
            f"Beta std={b_std:.3f}, {b_positive}/{len(b_vals)} positive)",
        )
    else:
        score = 4 if abs(delta_std) < 0.2 else 5
        return (
            6 - score,
            score,
            f"Beta more consistent across contracts "
            f"(Beta std={b_std:.3f}, {b_positive}/{len(b_vals)} positive; "
            f"Alpha std={a_std:.3f}, {a_positive}/{len(a_vals)} positive)",
        )


def _score_statistical_significance(alpha: dict, beta: dict) -> tuple[int, int, str]:
    """Score criterion 4: statistical significance.

    Does the CI exclude zero? Wider margin from zero -> higher confidence.

    Args:
        alpha: Anonymous profile for Strategy Alpha.
        beta: Anonymous profile for Strategy Beta.

    Returns:
        (score_alpha, score_beta, reasoning)
    """
    ci_low = alpha.get("ci_low")
    ci_high = alpha.get("ci_high")

    # Also check for CIs at profile level (from H2H data)
    if ci_low is None:
        ci_low = beta.get("ci_low")
    if ci_high is None:
        ci_high = beta.get("ci_high")

    if ci_low is None or ci_high is None:
        return (3, 3, "No confidence interval data available")

    try:
        ci_low = float(ci_low)
        ci_high = float(ci_high)
    except (TypeError, ValueError):
        return (3, 3, "CI values not numeric")

    if ci_low > 0:
        # CI entirely above 0 -> Alpha significantly better
        margin = ci_low
        if margin > 0.1:
            return (
                5,
                1,
                f"CI strongly favors Alpha: [{ci_low:.3f}, {ci_high:.3f}], CI_low > 0.1",
            )
        return (
            4,
            2,
            f"CI favors Alpha: [{ci_low:.3f}, {ci_high:.3f}], CI excludes zero",
        )
    elif ci_high < 0:
        # CI entirely below 0 -> Beta significantly better
        margin = abs(ci_high)
        if margin > 0.1:
            return (
                1,
                5,
                f"CI strongly favors Beta: [{ci_low:.3f}, {ci_high:.3f}], CI_high < -0.1",
            )
        return (
            2,
            4,
            f"CI favors Beta: [{ci_low:.3f}, {ci_high:.3f}], CI excludes zero",
        )
    else:
        # CI spans zero -> not significant
        return (
            3,
            3,
            f"CI spans zero: [{ci_low:.3f}, {ci_high:.3f}], result not statistically significant",
        )


def _score_seed_stability(alpha: dict, beta: dict) -> tuple[int, int, str]:
    """Score criterion 5: seed stability.

    If multi-seed data is available, check for consistency across seeds.

    Args:
        alpha: Anonymous profile for Strategy Alpha.
        beta: Anonymous profile for Strategy Beta.

    Returns:
        (score_alpha, score_beta, reasoning)
    """
    a_deltas = _get_seed_deltas(alpha)
    b_deltas = _get_seed_deltas(beta)

    if not a_deltas and not b_deltas:
        return (3, 3, "No multi-seed data available for either strategy")

    # Check which strategy has more consistent seed results
    a_consistent = True
    b_consistent = True

    if a_deltas:
        a_all_positive = all(d > 0 for d in a_deltas)
        a_all_negative = all(d < 0 for d in a_deltas)
        a_consistent = a_all_positive or a_all_negative
        a_std = statistics.stdev(a_deltas) if len(a_deltas) >= 2 else 0.0
    else:
        a_std = float("inf")

    if b_deltas:
        b_all_positive = all(d > 0 for d in b_deltas)
        b_all_negative = all(d < 0 for d in b_deltas)
        b_consistent = b_all_positive or b_all_negative
        b_std = statistics.stdev(b_deltas) if len(b_deltas) >= 2 else 0.0
    else:
        b_std = float("inf")

    # Score based on sign consistency and variance
    if a_consistent and not b_consistent:
        return (
            4,
            2,
            f"Alpha has consistent sign across seeds "
            f"(Alpha deltas={[f'{d:.3f}' for d in a_deltas]}, "
            f"Beta deltas={[f'{d:.3f}' for d in b_deltas]})",
        )
    if b_consistent and not a_consistent:
        return (
            2,
            4,
            f"Beta has consistent sign across seeds "
            f"(Beta deltas={[f'{d:.3f}' for d in b_deltas]}, "
            f"Alpha deltas={[f'{d:.3f}' for d in a_deltas]})",
        )

    # Both consistent or both inconsistent; compare variance
    if a_std == float("inf") and b_std == float("inf"):
        return (3, 3, "Insufficient multi-seed data for comparison")

    if abs(a_std - b_std) < 0.02:
        return (
            3,
            3,
            f"Similar seed stability (Alpha std={a_std:.3f}, Beta std={b_std:.3f})",
        )

    if a_std < b_std:
        return (
            4,
            2,
            f"Alpha more stable across seeds "
            f"(Alpha std={a_std:.3f}, Beta std={b_std:.3f})",
        )
    return (
        2,
        4,
        f"Beta more stable across seeds (Beta std={b_std:.3f}, Alpha std={a_std:.3f})",
    )


# Scoring function registry (criterion_name -> scoring function)
_SCORING_FUNCTIONS = {
    "pooled_net_eppd": _score_pooled_net_eppd,
    "worst_contract_risk": _score_worst_contract_risk,
    "cross_contract_consistency": _score_cross_contract_consistency,
    "statistical_significance": _score_statistical_significance,
    "seed_stability": _score_seed_stability,
}


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------


def compare_blind(
    profile_a: dict,
    profile_b: dict,
    seed: int,
) -> BlindComparisonResult:
    """Run blind comparison between two strategy profiles.

    Randomly assigns anonymous labels, strips identifying info, scores
    on a 5-criterion rubric, and determines a winner.

    Args:
        profile_a: Eval metrics dict for strategy A.
        profile_b: Eval metrics dict for strategy B.
        seed: Random seed for label assignment.

    Returns:
        BlindComparisonResult with rubric, scores, and winner.
    """
    # Extract real names before anonymizing
    name_a = _extract_strategy_name(profile_a)
    name_b = _extract_strategy_name(profile_b)

    # Anonymize profiles
    anon_a = anonymize_profile(profile_a)
    anon_b = anonymize_profile(profile_b)

    # Randomly assign labels using seeded RNG
    rng = random.Random(seed)
    swap = rng.choice([True, False])

    if swap:
        alpha_profile, beta_profile = anon_b, anon_a
        alpha_name, beta_name = name_b, name_a
    else:
        alpha_profile, beta_profile = anon_a, anon_b
        alpha_name, beta_name = name_a, name_b

    label_assignment = {"Alpha": alpha_name, "Beta": beta_name}

    # Score each criterion
    rubric = []
    for criterion_name, weight in RUBRIC_CRITERIA:
        scoring_fn = _SCORING_FUNCTIONS[criterion_name]
        score_a, score_b, reasoning = scoring_fn(alpha_profile, beta_profile)

        # Clamp scores to valid range
        score_a = max(1, min(5, score_a))
        score_b = max(1, min(5, score_b))

        rubric.append(
            RubricScore(
                criterion=criterion_name,
                weight=weight,
                score_alpha=score_a,
                score_beta=score_b,
                reasoning=reasoning,
            )
        )

    # Compute weighted totals
    total_weight = sum(r.weight for r in rubric)
    alpha_total = sum(r.score_alpha * r.weight for r in rubric) / total_weight
    beta_total = sum(r.score_beta * r.weight for r in rubric) / total_weight

    # Determine winner
    gap = alpha_total - beta_total
    if abs(gap) < 0.1:
        winner = "Tie"
        winner_real_name = ""
        confidence = "weak"
    elif gap > 0:
        winner = "Alpha"
        winner_real_name = label_assignment["Alpha"]
        if abs(gap) > 1.0:
            confidence = "strong"
        elif abs(gap) > 0.3:
            confidence = "moderate"
        else:
            confidence = "weak"
    else:
        winner = "Beta"
        winner_real_name = label_assignment["Beta"]
        if abs(gap) > 1.0:
            confidence = "strong"
        elif abs(gap) > 0.3:
            confidence = "moderate"
        else:
            confidence = "weak"

    # Generate summary
    if winner == "Tie":
        summary = (
            f"Strategies are statistically indistinguishable "
            f"(Alpha={alpha_total:.2f}, Beta={beta_total:.2f}, "
            f"gap={abs(gap):.2f})."
        )
    else:
        summary = (
            f"Strategy {winner} ({winner_real_name}) is the {confidence} "
            f"winner with a weighted score of "
            f"{alpha_total:.2f} vs {beta_total:.2f} (gap={abs(gap):.2f})."
        )

    return BlindComparisonResult(
        seed=seed,
        label_assignment=label_assignment,
        rubric=rubric,
        alpha_total=round(alpha_total, 4),
        beta_total=round(beta_total, 4),
        winner=winner,
        winner_real_name=winner_real_name,
        confidence=confidence,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def result_to_dict(result: BlindComparisonResult) -> dict:
    """Convert BlindComparisonResult to a JSON-serializable dict.

    Args:
        result: Comparison result.

    Returns:
        JSON-serializable dict.
    """
    d = asdict(result)
    d["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    d["schema"] = "blind_comparison_v1"
    return d


def result_to_markdown(result: BlindComparisonResult) -> str:
    """Convert BlindComparisonResult to a markdown report.

    Args:
        result: Comparison result.

    Returns:
        Markdown string.
    """
    lines = [
        "# Blind Strategy Comparison",
        "",
        f"**Seed:** {result.seed}",
        f"**Winner:** {result.winner}",
        f"**Confidence:** {result.confidence}",
        "",
        "## Rubric Scores",
        "",
        "| Criterion | Weight | Alpha | Beta | Reasoning |",
        "|-----------|--------|-------|------|-----------|",
    ]

    for r in result.rubric:
        lines.append(
            f"| {r.criterion} | {r.weight:.1f} | {r.score_alpha} | "
            f"{r.score_beta} | {r.reasoning} |"
        )

    lines.extend(
        [
            "",
            f"**Alpha weighted total:** {result.alpha_total:.2f}",
            f"**Beta weighted total:** {result.beta_total:.2f}",
            "",
            "## Unblinding",
            "",
            f"- **Alpha** = {result.label_assignment.get('Alpha', 'unknown')}",
            f"- **Beta** = {result.label_assignment.get('Beta', 'unknown')}",
            "",
            "## Summary",
            "",
            result.summary,
            "",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for blind strategy comparison."""
    parser = argparse.ArgumentParser(
        description="Blind strategy comparison for Arc D evaluation"
    )
    parser.add_argument(
        "--profile-a",
        required=True,
        help="Path to eval metrics JSON for first strategy",
    )
    parser.add_argument(
        "--profile-b",
        required=True,
        help="Path to eval metrics JSON for second strategy",
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Random seed for label assignment",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for comparison result (default: stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format: json or markdown (default: json)",
    )
    args = parser.parse_args()

    # Load profiles
    try:
        profile_a = load_profile(args.profile_a)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Failed to load profile A: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        profile_b = load_profile(args.profile_b)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Failed to load profile B: {e}", file=sys.stderr)
        sys.exit(1)

    # Run blind comparison
    result = compare_blind(profile_a, profile_b, seed=args.seed)

    # Format output
    if args.format == "markdown":
        output = result_to_markdown(result)
    else:
        output = json.dumps(result_to_dict(result), indent=2) + "\n"

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        print(f"Written to: {output_path}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()

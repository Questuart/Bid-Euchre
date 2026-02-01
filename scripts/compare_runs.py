#!/usr/bin/env python3
"""Compare two experiment runs with statistical rigor.

Provides bootstrap-based statistical comparison of experiment runs with:
- Mean differences and 95% confidence intervals
- Cohen's d effect sizes
- Bootstrap p-values
- Multiple output formats (human, markdown, json)

Usage:
    # Basic comparison
    python scripts/compare_runs.py \\
        --baseline data/runs/2026-01-30_baseline \\
        --candidate data/runs/2026-01-31_new_strategy

    # Markdown output for PR bodies
    python scripts/compare_runs.py \\
        --baseline data/runs/run1 \\
        --candidate data/runs/run2 \\
        --format markdown

    # JSON output for automation
    python scripts/compare_runs.py \\
        --baseline data/runs/run1 \\
        --candidate data/runs/run2 \\
        --format json > comparison.json

Example:
    Compare two runs to see if a strategy improvement is statistically significant:

    $ python scripts/compare_runs.py \\
        --baseline data/runs/baseline_greedy_42 \\
        --candidate data/runs/improved_strategy_42

    === Run Comparison ===

    Baseline:  baseline_greedy_42 (seed=42, n_per=1000)
    Candidate: improved_strategy_42 (seed=42, n_per=1000)

    --- Per-Scenario Comparison ---

    greedy/suit_H:
      avg_tricks_team0: 5.12 → 5.28 (+0.16, 95% CI: [+0.09, +0.24]) ***
      Effect size: d = 2.83 (large)
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class MetricComparison:
    """Results of comparing a single metric."""

    name: str
    baseline_mean: float
    baseline_ci: Tuple[float, float]
    candidate_mean: float
    candidate_ci: Tuple[float, float]
    delta_mean: float
    delta_ci: Tuple[float, float]
    effect_size: float  # Cohen's d
    p_value: float
    is_significant: bool


def load_results_from_distributions(run_dir: Path) -> Dict[str, Dict]:
    """Load per-scenario result JSONs and extract distributions.

    Note: Cannot use rollup.json alone - it only has aggregate means.
    Must use per-scenario results/**/*.json which include distributions
    (e.g., distribution_team0).

    Args:
        run_dir: Path to run directory (e.g., data/runs/2026-01-30_baseline)

    Returns:
        Dict mapping scenario_id to results dict with:
            - avg_tricks_team0: float
            - tricks_team0_samples: np.ndarray (expanded from distribution)
    """
    results = {}

    results_dir = run_dir / "results"
    if not results_dir.exists():
        raise ValueError(f"Results directory not found: {results_dir}")

    for results_file in results_dir.rglob("*.json"):
        with open(results_file) as f:
            data = json.load(f)

        # Extract scenario identifier (strategy/scenario)
        # e.g., results/greedy/suit_H.json -> greedy/suit_H
        relative_path = results_file.relative_to(results_dir)
        scenario_id = str(relative_path.with_suffix(""))

        # Convert distribution to array for bootstrapping
        # distribution_team0 is dict: {tricks_won: count}
        if "distribution_team0" in data:
            dist = data["distribution_team0"]
            # Expand histogram into array: {0: 10, 1: 20} -> [0]*10 + [1]*20
            tricks_array = []
            for tricks, count in dist.items():
                tricks_array.extend([int(tricks)] * count)

            results[scenario_id] = {
                "avg_tricks_team0": np.array(tricks_array).mean(),
                "tricks_team0_samples": np.array(tricks_array),
            }

    return results


def bootstrap_ci_from_samples(
    samples: np.ndarray, n_bootstrap: int, seed: int
) -> Tuple[float, float]:
    """Compute 95% CI via seeded bootstrap (deterministic).

    Uses np.random.default_rng for modern RNG interface.

    Args:
        samples: Sample array (e.g., tricks_won per hand)
        n_bootstrap: Number of bootstrap resamples
        seed: Random seed for determinism

    Returns:
        Tuple of (lower_95, upper_95) confidence interval bounds
    """
    rng = np.random.default_rng(seed)
    bootstrap_means = np.array(
        [
            rng.choice(samples, size=len(samples), replace=True).mean()
            for _ in range(n_bootstrap)
        ]
    )

    return tuple(np.percentile(bootstrap_means, [2.5, 97.5]))


def cohens_d(baseline: np.ndarray, candidate: np.ndarray) -> float:
    """Compute Cohen's d effect size.

    Args:
        baseline: Baseline sample array
        candidate: Candidate sample array

    Returns:
        Cohen's d (standardized mean difference)
    """
    pooled_std = np.sqrt(
        (baseline.std(ddof=1) ** 2 + candidate.std(ddof=1) ** 2) / 2
    )
    if pooled_std == 0:
        return 0.0
    return (candidate.mean() - baseline.mean()) / pooled_std


def compare_metric(
    baseline_samples: np.ndarray,
    candidate_samples: np.ndarray,
    metric_name: str,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> MetricComparison:
    """Compare a single metric between baseline and candidate.

    Args:
        baseline_samples: Sample array from baseline (e.g., tricks_won per hand)
        candidate_samples: Sample array from candidate
        metric_name: Name of metric for reporting
        n_bootstrap: Number of bootstrap samples (default 1000)
        seed: Random seed for determinism

    Returns:
        MetricComparison with means, CIs, effect size, significance
    """

    # Compute means and CIs
    baseline_mean = baseline_samples.mean()
    baseline_ci = bootstrap_ci_from_samples(baseline_samples, n_bootstrap, seed)

    candidate_mean = candidate_samples.mean()
    candidate_ci = bootstrap_ci_from_samples(candidate_samples, n_bootstrap, seed + 1)

    # Delta via bootstrap difference
    rng = np.random.default_rng(seed + 2)
    delta_bootstrap = np.array(
        [
            rng.choice(
                candidate_samples, size=len(candidate_samples), replace=True
            ).mean()
            - rng.choice(baseline_samples, size=len(baseline_samples), replace=True).mean()
            for _ in range(n_bootstrap)
        ]
    )

    delta_mean = candidate_mean - baseline_mean
    delta_ci = tuple(np.percentile(delta_bootstrap, [2.5, 97.5]))

    # Effect size
    effect_size = cohens_d(baseline_samples, candidate_samples)

    # Significance: CI-based (95% CI excludes 0?)
    is_significant = not (delta_ci[0] <= 0 <= delta_ci[1])

    # Two-sided p-value: P(|delta| >= |observed|)
    # Count proportion of bootstrap deltas as or more extreme than observed
    abs_delta = abs(delta_mean)
    p_value = (np.abs(delta_bootstrap) >= abs_delta).sum() / n_bootstrap
    # Ensure p_value is in [0, 1] (can be slightly >1 due to float precision)
    p_value = min(p_value, 1.0)

    return MetricComparison(
        name=metric_name,
        baseline_mean=baseline_mean,
        baseline_ci=baseline_ci,
        candidate_mean=candidate_mean,
        candidate_ci=candidate_ci,
        delta_mean=delta_mean,
        delta_ci=delta_ci,
        effect_size=effect_size,
        p_value=p_value,
        is_significant=is_significant,
    )


def format_comparison_human(
    comparisons: List[MetricComparison],
    baseline_dir: Path,
    candidate_dir: Path,
    baseline_meta: Optional[Dict] = None,
    candidate_meta: Optional[Dict] = None,
) -> str:
    """Format comparisons for human reading.

    Args:
        comparisons: List of metric comparisons
        baseline_dir: Baseline run directory path
        candidate_dir: Candidate run directory path
        baseline_meta: Optional baseline meta.json data
        candidate_meta: Optional candidate meta.json data

    Returns:
        Human-readable comparison report
    """
    lines = []
    lines.append("=== Run Comparison ===")
    lines.append("")

    # Format metadata
    baseline_seed = baseline_meta.get("seed", "?") if baseline_meta else "?"
    baseline_n_per = baseline_meta.get("n_per", "?") if baseline_meta else "?"
    candidate_seed = candidate_meta.get("seed", "?") if candidate_meta else "?"
    candidate_n_per = candidate_meta.get("n_per", "?") if candidate_meta else "?"

    lines.append(
        f"Baseline:  {baseline_dir.name} (seed={baseline_seed}, n_per={baseline_n_per})"
    )
    lines.append(
        f"Candidate: {candidate_dir.name} (seed={candidate_seed}, n_per={candidate_n_per})"
    )
    lines.append("")
    lines.append("--- Per-Scenario Comparison ---")
    lines.append("")

    for comp in comparisons:
        lines.append(f"{comp.name}:")

        # Format means with CIs
        lines.append(
            f"  Baseline:  {comp.baseline_mean:.2f} "
            f"(95% CI: [{comp.baseline_ci[0]:.2f}, {comp.baseline_ci[1]:.2f}])"
        )
        lines.append(
            f"  Candidate: {comp.candidate_mean:.2f} "
            f"(95% CI: [{comp.candidate_ci[0]:.2f}, {comp.candidate_ci[1]:.2f}])"
        )

        # Format delta
        delta_sign = "+" if comp.delta_mean >= 0 else ""
        lines.append(
            f"  Δ:         {delta_sign}{comp.delta_mean:.2f} "
            f"(95% CI: [{delta_sign if comp.delta_ci[0] >= 0 else ''}{comp.delta_ci[0]:.2f}, "
            f"{'+' if comp.delta_ci[1] >= 0 else ''}{comp.delta_ci[1]:.2f}])"
        )

        # Effect size interpretation
        abs_d = abs(comp.effect_size)
        if abs_d < 0.2:
            size_label = "negligible"
        elif abs_d < 0.5:
            size_label = "small"
        elif abs_d < 0.8:
            size_label = "medium"
        else:
            size_label = "large"

        lines.append(f"  Effect size: d = {comp.effect_size:.2f} ({size_label})")

        # Significance
        sig_stars = "***" if comp.p_value < 0.001 else ("**" if comp.p_value < 0.01 else ("*" if comp.p_value < 0.05 else ""))
        lines.append(
            f"  Significance: {sig_stars if sig_stars else 'n.s.'} (p = {comp.p_value:.3f})"
        )
        lines.append("")

    # Summary
    sig_count = sum(1 for c in comparisons if c.is_significant)
    lines.append(f"Summary: {sig_count}/{len(comparisons)} metrics show significant changes")
    lines.append("")

    return "\n".join(lines)


def format_comparison_markdown(
    comparisons: List[MetricComparison],
    baseline_dir: Path,
    candidate_dir: Path,
    baseline_meta: Optional[Dict] = None,
    candidate_meta: Optional[Dict] = None,
) -> str:
    """Format comparisons for PR bodies.

    Args:
        comparisons: List of metric comparisons
        baseline_dir: Baseline run directory path
        candidate_dir: Candidate run directory path
        baseline_meta: Optional baseline meta.json data
        candidate_meta: Optional candidate meta.json data

    Returns:
        Markdown-formatted comparison table
    """
    lines = []
    lines.append("## Run Comparison")
    lines.append("")

    # Metadata
    baseline_seed = baseline_meta.get("seed", "?") if baseline_meta else "?"
    baseline_n_per = baseline_meta.get("n_per", "?") if baseline_meta else "?"
    candidate_seed = candidate_meta.get("seed", "?") if candidate_meta else "?"
    candidate_n_per = candidate_meta.get("n_per", "?") if candidate_meta else "?"

    lines.append(
        f"**Baseline:** `{baseline_dir.name}` (seed={baseline_seed}, n_per={baseline_n_per})"
    )
    lines.append(
        f"**Candidate:** `{candidate_dir.name}` (seed={candidate_seed}, n_per={candidate_n_per})"
    )
    lines.append("")

    # Table
    lines.append("### Comparison Results")
    lines.append("")
    lines.append(
        "| Metric | Baseline | Candidate | Δ | Effect Size | Significant |"
    )
    lines.append("|--------|----------|-----------|---|-------------|-------------|")

    for comp in comparisons:
        delta_sign = "+" if comp.delta_mean >= 0 else ""
        sig_icon = "✅" if comp.is_significant else "—"
        sig_stars = (
            "***"
            if comp.p_value < 0.001
            else ("**" if comp.p_value < 0.01 else ("*" if comp.p_value < 0.05 else ""))
        )

        lines.append(
            f"| {comp.name} | "
            f"{comp.baseline_mean:.2f} | "
            f"{comp.candidate_mean:.2f} | "
            f"{delta_sign}{comp.delta_mean:.2f} | "
            f"d={comp.effect_size:.2f} | "
            f"{sig_icon} {sig_stars} |"
        )

    lines.append("")

    # Summary
    sig_count = sum(1 for c in comparisons if c.is_significant)
    if sig_count > 0:
        lines.append(
            f"**Interpretation:** {sig_count} of {len(comparisons)} metrics show statistically significant changes."
        )
    else:
        lines.append("**Interpretation:** No statistically significant changes detected.")

    lines.append("")

    return "\n".join(lines)


def format_comparison_json(
    comparisons: List[MetricComparison],
    baseline_dir: Path,
    candidate_dir: Path,
    baseline_meta: Optional[Dict] = None,
    candidate_meta: Optional[Dict] = None,
) -> str:
    """Format comparisons as JSON for programmatic use.

    Args:
        comparisons: List of metric comparisons
        baseline_dir: Baseline run directory path
        candidate_dir: Candidate run directory path
        baseline_meta: Optional baseline meta.json data
        candidate_meta: Optional candidate meta.json data

    Returns:
        JSON string
    """
    data = {
        "baseline": {
            "run_dir": str(baseline_dir),
            "run_id": baseline_dir.name,
            "seed": baseline_meta.get("seed") if baseline_meta else None,
            "n_per": baseline_meta.get("n_per") if baseline_meta else None,
        },
        "candidate": {
            "run_dir": str(candidate_dir),
            "run_id": candidate_dir.name,
            "seed": candidate_meta.get("seed") if candidate_meta else None,
            "n_per": candidate_meta.get("n_per") if candidate_meta else None,
        },
        "comparisons": [
            {
                "metric": c.name,
                "baseline_mean": c.baseline_mean,
                "baseline_ci": list(c.baseline_ci),
                "candidate_mean": c.candidate_mean,
                "candidate_ci": list(c.candidate_ci),
                "delta_mean": c.delta_mean,
                "delta_ci": list(c.delta_ci),
                "effect_size": c.effect_size,
                "p_value": c.p_value,
                "is_significant": c.is_significant,
            }
            for c in comparisons
        ],
        "summary": {
            "total_metrics": len(comparisons),
            "significant_changes": sum(1 for c in comparisons if c.is_significant),
        },
    }

    return json.dumps(data, indent=2)


def main():
    """Main comparison logic."""
    parser = argparse.ArgumentParser(
        description="Compare two experiment runs with statistical rigor"
    )
    parser.add_argument(
        "--baseline", required=True, type=Path, help="Baseline run directory"
    )
    parser.add_argument(
        "--candidate", required=True, type=Path, help="Candidate run directory"
    )
    parser.add_argument(
        "--metric",
        help="Focus on specific metric (default: compare all common scenarios)",
    )
    parser.add_argument(
        "--format",
        choices=["human", "markdown", "json"],
        default="human",
        help="Output format (default: human)",
    )
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=1000,
        help="Bootstrap samples (default 1000; use 10000 for publication-quality)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for bootstrap (default 42)"
    )

    args = parser.parse_args()

    # Verify run directories exist
    if not args.baseline.exists():
        print(f"Error: Baseline directory not found: {args.baseline}", file=sys.stderr)
        sys.exit(1)
    if not args.candidate.exists():
        print(f"Error: Candidate directory not found: {args.candidate}", file=sys.stderr)
        sys.exit(1)

    # Load meta.json for context (optional)
    baseline_meta = None
    candidate_meta = None
    try:
        baseline_meta_path = args.baseline / "meta.json"
        if baseline_meta_path.exists():
            with open(baseline_meta_path) as f:
                baseline_meta = json.load(f)
    except Exception:
        pass

    try:
        candidate_meta_path = args.candidate / "meta.json"
        if candidate_meta_path.exists():
            with open(candidate_meta_path) as f:
                candidate_meta = json.load(f)
    except Exception:
        pass

    # Load result distributions from both runs
    try:
        baseline_results = load_results_from_distributions(args.baseline)
    except ValueError as e:
        print(f"Error loading baseline results: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        candidate_results = load_results_from_distributions(args.candidate)
    except ValueError as e:
        print(f"Error loading candidate results: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify same scenarios in both runs
    baseline_scenarios = set(baseline_results.keys())
    candidate_scenarios = set(candidate_results.keys())

    if baseline_scenarios != candidate_scenarios:
        print("Warning: Scenario mismatch", file=sys.stderr)
        only_baseline = baseline_scenarios - candidate_scenarios
        only_candidate = candidate_scenarios - baseline_scenarios
        if only_baseline:
            print(f"  Only in baseline: {only_baseline}", file=sys.stderr)
        if only_candidate:
            print(f"  Only in candidate: {only_candidate}", file=sys.stderr)

    # Compare metrics for common scenarios
    comparisons = []
    common_scenarios = sorted(baseline_scenarios & candidate_scenarios)

    if not common_scenarios:
        print("Error: No common scenarios found between runs", file=sys.stderr)
        sys.exit(1)

    for scenario_id in common_scenarios:
        # For now, compare avg_tricks_team0
        # Can expand to more metrics later
        comparison = compare_metric(
            baseline_samples=baseline_results[scenario_id]["tricks_team0_samples"],
            candidate_samples=candidate_results[scenario_id]["tricks_team0_samples"],
            metric_name=f"{scenario_id}/avg_tricks_team0",
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )
        comparisons.append(comparison)

    # Output
    if args.format == "human":
        print(
            format_comparison_human(
                comparisons, args.baseline, args.candidate, baseline_meta, candidate_meta
            )
        )
    elif args.format == "markdown":
        print(
            format_comparison_markdown(
                comparisons, args.baseline, args.candidate, baseline_meta, candidate_meta
            )
        )
    elif args.format == "json":
        print(
            format_comparison_json(
                comparisons, args.baseline, args.candidate, baseline_meta, candidate_meta
            )
        )


if __name__ == "__main__":
    main()

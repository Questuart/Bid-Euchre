#!/usr/bin/env python3
"""Play Policy Gate Script.

Validates that glutton strategy is stable enough to freeze as play policy
for bidder training. Computes "glutton advantage" across multiple seeds
and directions to verify that glutton reliably outperforms greedy.

Usage:
    # Fresh runs (recommended)
    PYTHONPATH=src python scripts/play_policy_gate.py \\
        --seeds 42,43,44 \\
        --n-per 20000

    # Using existing runs
    PYTHONPATH=src python scripts/play_policy_gate.py \\
        --skip-run \\
        --run-ids 2026-02-04_run1,2026-02-04_run2,2026-02-04_run3

Gate Logic:
    - PASS: Glutton advantage CI lower > 0 (glutton significantly better)
    - WARN: CI overlaps zero (inconclusive)
    - FAIL: CI upper < 0 (greedy significantly better)

Overall status is worst-of across all seeds and both directions.
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Tuple

import numpy as np
from scipy import stats


def compute_onesample_ttest(
    samples: np.ndarray,
) -> Tuple[float, float]:
    """One-sample t-test: is the mean advantage != 0?

    Args:
        samples: Array of advantage samples.

    Returns:
        (t_stat, p_value). Returns (0.0, 1.0) for empty or n=1 input.
    """
    if len(samples) < 2:
        return (0.0, 1.0)
    t_stat, p_value = stats.ttest_1samp(samples, 0.0)
    return (float(t_stat), float(p_value))


@dataclass
class DirectionResult:
    """Results for a single direction.

    Sign convention: adv_mean > 0 means glutton outperforms greedy.
    For glutton_vs_greedy: team0 delta (2*tricks_team0 - 10) used directly.
    For greedy_vs_glutton: sign flipped so positive still = glutton better.
    """

    direction: str
    adv_mean: float
    adv_ci: Tuple[float, float]
    n_samples: int
    status: Literal["PASS", "WARN", "FAIL"]
    t_stat: float = 0.0
    p_value: float = 1.0


@dataclass
class ScenarioInfo:
    """Informational breakdown for a single scenario."""

    scenario: str
    adv_mean: float
    adv_ci: Tuple[float, float]
    note: str  # "", "uncertain", or "reversal"


@dataclass
class SeedResult:
    """Results for a single seed."""

    seed: int
    run_id: str
    directions: List[DirectionResult]
    scenarios: List[ScenarioInfo]
    status: Literal["PASS", "WARN", "FAIL"]


@dataclass
class GateResult:
    """Overall gate result."""

    seeds: List[SeedResult]
    overall_status: Literal["PASS", "WARN", "FAIL"]
    strict_mode: bool
    timestamp: str


def expand_distribution_to_adv(dist: Dict[str, int], direction: str) -> np.ndarray:
    """Expand distribution_team0 to per-hand adv samples.

    Args:
        dist: Distribution of team0 tricks {tricks_str: count}
        direction: "glutton_vs_greedy" or "greedy_vs_glutton"

    Returns:
        Array of adv samples where positive = glutton better
    """
    samples = []
    for tricks_str, count in dist.items():
        tricks = int(tricks_str)
        # delta = team0_tricks - team1_tricks = 2*team0_tricks - 10
        delta = 2 * tricks - 10
        samples.extend([delta] * count)

    samples = np.array(samples)

    # Normalize so positive always means "glutton better"
    if direction == "glutton_vs_greedy":
        # glutton is team0, so delta already has correct sign
        return samples
    elif direction == "greedy_vs_glutton":
        # greedy is team0, so flip sign to make positive = glutton better
        return -samples
    else:
        raise ValueError(f"Unknown direction: {direction}")


def pool_adv_samples(results: Dict[str, Dict], direction: str) -> np.ndarray:
    """Concatenate adv samples across all scenarios for a direction.

    Args:
        results: Dict mapping scenario_id to result dict with distribution_team0
        direction: "glutton_vs_greedy" or "greedy_vs_glutton"

    Returns:
        Concatenated array of adv samples
    """
    all_samples = []
    for scenario_id, result in results.items():
        if "distribution_team0" not in result:
            continue
        samples = expand_distribution_to_adv(result["distribution_team0"], direction)
        all_samples.append(samples)

    if not all_samples:
        return np.array([])

    return np.concatenate(all_samples)


def bootstrap_ci(
    samples: np.ndarray, n_bootstrap: int, seed: int
) -> Tuple[float, float]:
    """Compute 95% CI via seeded bootstrap.

    Args:
        samples: Sample array
        n_bootstrap: Number of bootstrap resamples
        seed: Random seed for determinism

    Returns:
        Tuple of (lower_95, upper_95) confidence interval bounds
    """
    if len(samples) == 0:
        return (0.0, 0.0)

    rng = np.random.default_rng(seed)
    bootstrap_means = np.array(
        [
            rng.choice(samples, size=len(samples), replace=True).mean()
            for _ in range(n_bootstrap)
        ]
    )

    return tuple(np.percentile(bootstrap_means, [2.5, 97.5]))


def compute_gate_status(adv_ci: Tuple[float, float]) -> Literal["PASS", "WARN", "FAIL"]:
    """Compute gate status from CI bounds.

    Args:
        adv_ci: (lower, upper) confidence interval for advantage

    Returns:
        "FAIL" if upper < 0, "PASS" if lower > 0, else "WARN"
    """
    lower, upper = adv_ci
    if upper < 0:
        return "FAIL"
    elif lower > 0:
        return "PASS"
    else:
        return "WARN"


def compute_scenario_note(adv_ci: Tuple[float, float]) -> str:
    """Compute scenario note from CI bounds.

    Args:
        adv_ci: (lower, upper) confidence interval for advantage

    Returns:
        "reversal" if upper < 0, "uncertain" if spans 0, else ""
    """
    lower, upper = adv_ci
    if upper < 0:
        return "reversal"
    elif lower <= 0 <= upper:
        return "uncertain"
    else:
        return ""


def load_results_from_run(run_dir: Path) -> Dict[str, Dict[str, Dict]]:
    """Load results organized by direction and scenario.

    Args:
        run_dir: Path to run directory

    Returns:
        Dict mapping direction -> scenario -> result dict
    """
    results_dir = run_dir / "results"
    if not results_dir.exists():
        raise ValueError(f"Results directory not found: {results_dir}")

    results: Dict[str, Dict[str, Dict]] = {}

    for results_file in results_dir.rglob("*.json"):
        with open(results_file) as f:
            data = json.load(f)

        # Extract direction/scenario from path
        # e.g., results/glutton_vs_greedy/suit_H.json
        relative_path = results_file.relative_to(results_dir)
        parts = list(relative_path.parts)
        if len(parts) >= 2:
            direction = parts[0]
            scenario = relative_path.stem
        else:
            continue

        if direction not in results:
            results[direction] = {}
        results[direction][scenario] = data

    return results


def run_experiment_for_seed(config: Path, seed: int, n_per: int, run_dir: Path) -> str:
    """Run experiment and return run_id.

    Args:
        config: Path to config YAML
        seed: Random seed
        n_per: Number of hands per scenario
        run_dir: Base directory for run outputs

    Returns:
        run_id of the generated run
    """
    cmd = [
        sys.executable,
        "experiments/run_experiment.py",
        "--config",
        str(config),
        "--seed",
        str(seed),
        "--n_per",
        str(n_per),
        "--run-dir",
        str(run_dir),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running experiment: {result.stderr}", file=sys.stderr)
        raise RuntimeError(f"Experiment failed with code {result.returncode}")

    # Parse run_id from output (last line before summary contains run directory)
    for line in result.stdout.split("\n"):
        if "Run directory:" in line:
            # Extract run_id from path
            run_path = line.split("Run directory:")[-1].strip()
            return Path(run_path).name

    raise RuntimeError("Could not find run_id in experiment output")


def load_and_evaluate_run(
    run_dir: Path,
    run_id: str,
    n_bootstrap: int,
    bootstrap_seed: int,
    strict_scenarios: bool,
) -> SeedResult:
    """Load results and compute gate metrics.

    Args:
        run_dir: Base directory for runs
        run_id: ID of specific run
        n_bootstrap: Number of bootstrap samples
        bootstrap_seed: Seed for bootstrap determinism
        strict_scenarios: Whether to fail on per-scenario reversals

    Returns:
        SeedResult with direction results and scenario breakdown
    """
    full_run_dir = run_dir / run_id
    if not full_run_dir.exists():
        raise ValueError(f"Run directory not found: {full_run_dir}")

    # Load meta.json for seed
    meta_path = full_run_dir / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        seed = meta.get("seed", 0)
    else:
        seed = 0

    # Load results by direction
    results_by_direction = load_results_from_run(full_run_dir)

    direction_results = []
    all_scenarios: List[ScenarioInfo] = []

    for direction in ["glutton_vs_greedy", "greedy_vs_glutton"]:
        if direction not in results_by_direction:
            continue

        scenario_results = results_by_direction[direction]

        # Pool samples across scenarios
        pooled_samples = pool_adv_samples(scenario_results, direction)

        if len(pooled_samples) == 0:
            continue

        # Compute pooled CI and one-sample t-test
        adv_mean = float(pooled_samples.mean())
        adv_ci = bootstrap_ci(pooled_samples, n_bootstrap, bootstrap_seed)
        status = compute_gate_status(adv_ci)
        t_stat, p_value = compute_onesample_ttest(pooled_samples)

        direction_results.append(
            DirectionResult(
                direction=direction,
                adv_mean=adv_mean,
                adv_ci=adv_ci,
                n_samples=len(pooled_samples),
                status=status,
                t_stat=t_stat,
                p_value=p_value,
            )
        )

        # Per-scenario breakdown (informational)
        for scenario, result in scenario_results.items():
            if "distribution_team0" not in result:
                continue
            samples = expand_distribution_to_adv(
                result["distribution_team0"], direction
            )
            if len(samples) == 0:
                continue
            scenario_mean = float(samples.mean())
            scenario_ci = bootstrap_ci(samples, n_bootstrap, bootstrap_seed + 1)
            note = compute_scenario_note(scenario_ci)

            all_scenarios.append(
                ScenarioInfo(
                    scenario=f"{direction}/{scenario}",
                    adv_mean=scenario_mean,
                    adv_ci=scenario_ci,
                    note=note,
                )
            )

    # Compute overall status for this seed (worst of directions)
    statuses = [d.status for d in direction_results]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    # In strict mode, check per-scenario reversals
    if strict_scenarios:
        for s in all_scenarios:
            if s.note == "reversal":
                overall = "FAIL"
                break

    return SeedResult(
        seed=seed,
        run_id=run_id,
        directions=direction_results,
        scenarios=all_scenarios,
        status=overall,
    )


def format_ci(ci: Tuple[float, float]) -> str:
    """Format CI as string."""
    sign_low = "+" if ci[0] >= 0 else ""
    sign_high = "+" if ci[1] >= 0 else ""
    return f"[{sign_low}{ci[0]:.2f}, {sign_high}{ci[1]:.2f}]"


def format_mean(mean: float) -> str:
    """Format mean as string."""
    sign = "+" if mean >= 0 else ""
    return f"{sign}{mean:.2f}"


def format_stdout_table(result: GateResult) -> str:
    """Format gate result as stdout table."""
    lines = []
    lines.append("=== Play Policy Gate ===")
    lines.append("")
    lines.append(
        f"{'Seed':<5} | {'Direction':<21} | {'Adv Mean':<8} | "
        f"{'95% CI':<17} | {'t-stat':<8} | {'p-value':<8} | {'Status':<6}"
    )
    lines.append(
        "-" * 5
        + "-|-"
        + "-" * 21
        + "-|-"
        + "-" * 8
        + "-|-"
        + "-" * 17
        + "-|-"
        + "-" * 8
        + "-|-"
        + "-" * 8
        + "-|-"
        + "-" * 6
    )

    for seed_result in result.seeds:
        for d in seed_result.directions:
            lines.append(
                f"{seed_result.seed:<5} | {d.direction:<21} | "
                f"{format_mean(d.adv_mean):<8} | {format_ci(d.adv_ci):<17} | "
                f"{d.t_stat:<8.2f} | {d.p_value:<8.4f} | {d.status:<6}"
            )

    lines.append("")
    lines.append("Per-Scenario Breakdown (informational):")
    lines.append(f"{'Scenario':<35} | {'Adv Mean':<8} | {'95% CI':<17} | {'Note':<12}")
    lines.append("-" * 35 + "-|-" + "-" * 8 + "-|-" + "-" * 17 + "-|-" + "-" * 12)

    # Deduplicate scenarios (show unique ones)
    seen = set()
    for seed_result in result.seeds:
        for s in seed_result.scenarios:
            # Only show first occurrence of each scenario
            short_name = s.scenario.split("/")[-1]
            direction = s.scenario.split("/")[0] if "/" in s.scenario else ""
            key = (direction, short_name)
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"{s.scenario:<35} | {format_mean(s.adv_mean):<8} | "
                f"{format_ci(s.adv_ci):<17} | {s.note:<12}"
            )

    lines.append("")
    lines.append(f"OVERALL: {result.overall_status}")

    return "\n".join(lines)


def save_artifacts(result: GateResult, output_dir: Path):
    """Save gate artifacts to output directory.

    Args:
        result: Gate result
        output_dir: Directory to save artifacts
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert to JSON-serializable dict
    def to_serializable(obj: Any) -> Any:
        if hasattr(obj, "__dict__"):
            return {k: to_serializable(v) for k, v in asdict(obj).items()}
        elif isinstance(obj, (list, tuple)):
            if isinstance(obj, tuple) and len(obj) == 2:
                # Treat as CI tuple
                return list(obj)
            return [to_serializable(v) for v in obj]
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        else:
            return obj

    result_dict = to_serializable(result)

    # Save JSON
    json_path = output_dir / "play_policy_gate.json"
    with open(json_path, "w") as f:
        json.dump(result_dict, f, indent=2)

    # Save Markdown
    md_path = output_dir / "play_policy_gate.md"
    with open(md_path, "w") as f:
        f.write("# Play Policy Gate Results\n\n")
        f.write(f"**Timestamp:** {result.timestamp}\n\n")
        f.write(f"**Strict Mode:** {result.strict_mode}\n\n")
        f.write(f"**Overall Status:** {result.overall_status}\n\n")
        f.write("## Results\n\n")
        f.write("```\n")
        f.write(format_stdout_table(result))
        f.write("\n```\n")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Play Policy Gate - Validate glutton stability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("experiments/configs/glutton_vs_greedy_head_to_head.yaml"),
        help="Config file (default: glutton_vs_greedy_head_to_head.yaml)",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default="42,43,44",
        help="Comma-separated seeds (default: 42,43,44)",
    )
    parser.add_argument(
        "--n-per",
        type=int,
        default=20000,
        help="Hands per scenario (default: 20000)",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("data/runs"),
        help="Base directory for runs (default: data/runs)",
    )
    parser.add_argument(
        "--run-ids",
        type=str,
        help="Comma-separated run IDs (required with --skip-run)",
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Use existing results instead of running experiments",
    )
    parser.add_argument(
        "--strict-scenarios",
        action="store_true",
        help="FAIL on any per-scenario reversal (default: pooled-only)",
    )
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=1000,
        help="Bootstrap samples (default: 1000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Bootstrap seed for determinism (default: 42)",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Validate arguments
    if args.skip_run and not args.run_ids:
        print("Error: --skip-run requires --run-ids", file=sys.stderr)
        sys.exit(1)

    # Parse seeds
    seeds = [int(s.strip()) for s in args.seeds.split(",")]

    # Get run IDs
    if args.skip_run:
        run_ids = [r.strip() for r in args.run_ids.split(",")]
        if len(run_ids) != len(seeds):
            print(
                f"Error: Number of run IDs ({len(run_ids)}) must match "
                f"number of seeds ({len(seeds)})",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        # Run experiments
        run_ids = []
        for seed in seeds:
            print(f"Running experiment with seed {seed}...")
            run_id = run_experiment_for_seed(
                args.config, seed, args.n_per, args.run_dir
            )
            run_ids.append(run_id)
            print(f"  -> {run_id}")

    # Evaluate runs
    seed_results = []
    for seed, run_id in zip(seeds, run_ids):
        print(f"Evaluating {run_id}...")
        result = load_and_evaluate_run(
            args.run_dir,
            run_id,
            args.n_bootstrap,
            args.seed,
            args.strict_scenarios,
        )
        seed_results.append(result)

    # Compute overall status (worst of seeds)
    statuses = [r.status for r in seed_results]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    # Build result
    gate_result = GateResult(
        seeds=seed_results,
        overall_status=overall,
        strict_mode=args.strict_scenarios,
        timestamp=datetime.now().isoformat(),
    )

    # Print results
    print()
    print(format_stdout_table(gate_result))

    # Save artifacts to each run directory
    for run_id in run_ids:
        artifacts_dir = args.run_dir / run_id / "artifacts"
        save_artifacts(gate_result, artifacts_dir)
        print(f"\nArtifacts saved to: {artifacts_dir}")

    # Save aggregate if multiple seeds
    if len(seeds) > 1:
        aggregate_path = (
            args.run_dir
            / f"play_policy_gate_aggregate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(aggregate_path, "w") as f:
            # Convert to serializable
            def to_serializable(obj: Any) -> Any:
                if hasattr(obj, "__dict__"):
                    return {k: to_serializable(v) for k, v in asdict(obj).items()}
                elif isinstance(obj, (list, tuple)):
                    if isinstance(obj, tuple) and len(obj) == 2:
                        return list(obj)
                    return [to_serializable(v) for v in obj]
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.integer):
                    return int(obj)
                else:
                    return obj

            json.dump(to_serializable(gate_result), f, indent=2)
        print(f"\nAggregate saved to: {aggregate_path}")

    # Exit with appropriate code
    if overall == "FAIL":
        sys.exit(1)
    elif overall == "WARN":
        sys.exit(0)  # WARN is not a failure
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""
Run an experiment suite and generate a rollup index.

Invokes experiments/run_experiment.py for each config in the suite,
optionally generates per-run reports, and creates a suite rollup run dir
with rollup.json + ROLLUP.md.

Usage:
    PYTHONPATH=src python scripts/run_suite.py \\
        --suite experiments/suites/baseline_tiny.yaml \\
        --seed 42 \\
        --n-per 20
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run an experiment suite and generate a rollup index",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--suite",
        required=True,
        help="Path to suite YAML file (e.g., experiments/suites/baseline_tiny.yaml)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Override suite seed (default: use suite.parameters.seed)"
    )
    parser.add_argument(
        "--n-per",
        type=int,
        help="Override n_per (default: use suite.parameters.n_per)"
    )
    parser.add_argument(
        "--run-dir",
        default="data/runs",
        help="Base output directory for runs (default: data/runs)"
    )
    parser.add_argument(
        "--no-reports",
        action="store_true",
        help="Skip per-run report generation (default: generate reports)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing"
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Override batch ID (default: auto-generated from suite name + seed + timestamp)"
    )
    parser.add_argument(
        "--batch-purpose",
        default=None,
        choices=["promotion", "exploration", "regression"],
        help="Override batch purpose"
    )
    return parser.parse_args()


def load_suite(suite_path: str) -> Dict:
    """Load suite YAML file."""
    suite_file = Path(suite_path)
    if not suite_file.exists():
        raise FileNotFoundError(f"Suite file not found: {suite_path}")
    
    with suite_file.open("r") as f:
        suite = yaml.safe_load(f)
    
    # Validate required fields
    if "suite_name" not in suite:
        raise ValueError("Suite YAML must contain 'suite_name'")
    if "configs" not in suite or not suite["configs"]:
        raise ValueError("Suite YAML must contain non-empty 'configs' list")
    if "parameters" not in suite:
        raise ValueError("Suite YAML must contain 'parameters'")
    
    return suite


def resolve_parameters(suite: Dict, args: argparse.Namespace) -> Dict[str, any]:
    """Resolve effective parameters (CLI overrides > suite parameters)."""
    params = suite["parameters"]
    
    # Seed: CLI > suite (required)
    seed = args.seed if args.seed is not None else params.get("seed")
    if seed is None:
        raise ValueError("Seed is required (provide via CLI --seed or suite parameters.seed)")
    
    # n_per: CLI > suite (required)
    n_per = args.n_per if args.n_per is not None else params.get("n_per")
    if n_per is None:
        raise ValueError("n_per is required (provide via CLI --n-per or suite parameters.n_per)")
    
    # log_level: suite only (default 'none')
    log_level = params.get("log_level", "none")
    
    return {
        "seed": seed,
        "n_per": n_per,
        "log_level": log_level
    }


def get_git_sha() -> str:
    """Get current git SHA (short form)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def compute_file_sha256(file_path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def aggregate_run_metrics(run_dir: Path) -> Dict[str, any]:
    """
    Aggregate metrics from a run's results directory.

    Walks results/<strategy>/<scenario>.json files and computes:
    - total_hands: sum of "hands" across all result files
    - avg_tricks: weighted average of avg_team0 (weighted by hands)
    - reason: human-readable error reason if aggregation fails
    - bad_files: list of problematic files (limited to 3)

    Returns:
        Dict with "total_hands" (int or None), "avg_tricks" (float or None),
        "reason" (str or None), and "bad_files" (list[str] or None)
    """
    results_dir = run_dir / "results"
    if not results_dir.exists():
        return {"total_hands": None, "avg_tricks": None, "reason": None, "bad_files": None}

    total_hands = 0
    weighted_tricks_sum = 0.0
    bad_files = []
    reasons = []

    # Walk results/<strategy>/<scenario>.json
    for strategy_dir in sorted(results_dir.iterdir()):
        if not strategy_dir.is_dir():
            continue
        for result_file in sorted(strategy_dir.glob("*.json")):
            try:
                with result_file.open("r") as f:
                    data = json.load(f)
                hands = data.get("hands", 0)
                avg_team0 = data.get("avg_team0")
                if hands > 0 and avg_team0 is not None:
                    total_hands += hands
                    weighted_tricks_sum += avg_team0 * hands
                else:
                    # Missing expected keys
                    missing_keys = []
                    if hands <= 0:
                        missing_keys.append("hands")
                    if avg_team0 is None:
                        missing_keys.append("avg_team0")
                    key_str = ", ".join(missing_keys)
                    reason = f"missing_key:{key_str}: {result_file.name}"
                    reasons.append(reason)
                    bad_files.append(str(result_file.relative_to(run_dir)))
            except json.JSONDecodeError:
                reason = f"json_decode_error: {result_file.name}"
                reasons.append(reason)
                bad_files.append(str(result_file.relative_to(run_dir)))
            except (KeyError, TypeError):
                reason = f"parse_error: {result_file.name}"
                reasons.append(reason)
                bad_files.append(str(result_file.relative_to(run_dir)))

    # Limit bad_files to 3 samples (sort for deterministic ordering)
    bad_files = sorted(bad_files)
    if len(bad_files) > 3:
        bad_files = bad_files[:3]

    if total_hands == 0:
        # If we had any parsing issues, report them
        if reasons:
            reasons = sorted(reasons)  # Sort for deterministic ordering
            combined_reason = "; ".join(reasons[:3])
            if len(reasons) > 3:
                combined_reason += f" ({len(reasons) - 3} more)"
            return {
                "total_hands": None,
                "avg_tricks": None,
                "reason": combined_reason,
                "bad_files": bad_files
            }
        return {"total_hands": None, "avg_tricks": None, "reason": None, "bad_files": None}

    avg_tricks = round(weighted_tricks_sum / total_hands, 2)
    return {"total_hands": total_hands, "avg_tricks": avg_tricks, "reason": None, "bad_files": None}


def discover_new_run_dir(run_base: Path, dirs_before: set) -> Path:
    """Discover the newly created run directory."""
    dirs_after = set(d.name for d in run_base.iterdir() if d.is_dir())
    new_dirs = dirs_after - dirs_before
    
    if len(new_dirs) != 1:
        raise RuntimeError(
            f"Expected exactly 1 new run directory, found {len(new_dirs)}: {new_dirs}"
        )
    
    return run_base / list(new_dirs)[0]


def resolve_batch_context(
    suite: Dict,
    args: argparse.Namespace,
    suite_name: str,
    seed: int,
) -> tuple:
    """Resolve batch metadata from suite YAML + CLI overrides.

    Returns:
        (batch_id, batch_purpose, config_overrides) tuple.
        batch_id and batch_purpose are None when batch is inactive.
    """
    suite_batch = suite.get("batch", {})
    config_overrides = suite.get("config_overrides", {})

    # CLI precedence over YAML
    batch_id = args.batch_id or suite_batch.get("batch_id")
    batch_purpose = args.batch_purpose or suite_batch.get("batch_purpose")

    # All-or-nothing: batch_id without purpose is an error
    if batch_id and not batch_purpose:
        raise ValueError(
            "batch_id provided without batch_purpose. "
            "Batch metadata requires at least batch_purpose."
        )

    # Auto-generate batch_id when purpose is set but id is not
    if batch_purpose and not batch_id:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        batch_id = f"{suite_name}_{seed}_{timestamp}"

    return batch_id, batch_purpose, config_overrides


def build_experiment_cmd(
    config_path: str,
    seed: int,
    n_per: int,
    log_level: str,
    run_base: str,
    batch_id: str | None,
    batch_role: str | None,
    batch_purpose: str | None,
    extra_args: list[str] | None,
) -> list[str]:
    """Build the command list for a single experiment run."""
    cmd = [
        "python",
        "experiments/run_experiment.py",
        "--config", config_path,
        "--seed", str(seed),
        "--n_per", str(n_per),
        "--log-level", log_level,
        "--run-dir", run_base,
    ]
    if batch_purpose:
        cmd += ["--batch-id", batch_id, "--batch-role", batch_role,
                "--batch-purpose", batch_purpose]
    if extra_args:
        cmd += extra_args
    return cmd


def run_experiment(
    config_path: str,
    seed: int,
    n_per: int,
    log_level: str,
    run_base: Path,
    batch_id: str | None = None,
    batch_role: str | None = None,
    batch_purpose: str | None = None,
    extra_args: list[str] | None = None,
) -> Path:
    """
    Run a single experiment config and return the created run directory.

    Returns:
        Path to the created run directory
    """
    # Snapshot existing directories
    dirs_before = set(d.name for d in run_base.iterdir() if d.is_dir())

    cmd = build_experiment_cmd(
        config_path, seed, n_per, log_level, str(run_base),
        batch_id, batch_role, batch_purpose, extra_args,
    )

    env = {**os.environ, "PYTHONPATH": "src"}

    print(f"  Running: {config_path}")

    try:
        subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        # Note: run_experiment.py prints canonical report generation commands
        # These can be ignored; we use scripts/generate_report.py
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Experiment failed: {config_path}", file=sys.stderr)
        print(f"Exit code: {e.returncode}", file=sys.stderr)
        print(f"Stdout:\n{e.stdout}", file=sys.stderr)
        print(f"Stderr:\n{e.stderr}", file=sys.stderr)
        raise

    # Discover the created run directory
    run_dir = discover_new_run_dir(run_base, dirs_before)
    print(f"  ✓ Run completed: {run_dir.name}")

    return run_dir


def generate_report(run_dir: Path) -> bool:
    """
    Generate report for a run directory using scripts/generate_report.py.
    
    Returns:
        True if successful, False if failed (non-fatal)
    """
    cmd = [
        "python",
        "scripts/generate_report.py",
        "--run-dir", str(run_dir)
    ]
    
    env = {**os.environ, "PYTHONPATH": "src"}
    
    try:
        subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"  ✓ Report generated: {run_dir.name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  Report generation failed for {run_dir.name}: {e}", file=sys.stderr)
        return False


def create_suite_rollup(
    suite: Dict,
    suite_path: str,
    effective_params: Dict,
    member_runs: List[Dict],
    run_base: Path,
    batch_id: str | None = None,
    batch_purpose: str | None = None,
    config_overrides: Dict | None = None,
) -> Path:
    """
    Create suite rollup run directory with metadata.
    
    Returns:
        Path to the created rollup run directory
    """
    suite_name = suite["suite_name"]
    seed = effective_params["seed"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    rollup_id = f"suite_{suite_name}_{seed}_{timestamp}"
    rollup_dir = run_base / rollup_id
    
    # Create run directory structure
    rollup_dir.mkdir(parents=True, exist_ok=True)
    (rollup_dir / "results").mkdir(exist_ok=True)
    (rollup_dir / "logs").mkdir(exist_ok=True)
    (rollup_dir / "reports").mkdir(exist_ok=True)
    (rollup_dir / "splits").mkdir(exist_ok=True)
    (rollup_dir / "artifacts").mkdir(exist_ok=True)
    
    # Write suite_effective.yaml (original suite + resolved overrides)
    effective_suite = dict(suite)
    effective_suite["parameters"] = effective_params
    
    with (rollup_dir / "suite_effective.yaml").open("w") as f:
        yaml.dump(effective_suite, f, default_flow_style=False, sort_keys=False)
    
    # Write meta.json (schema v2 for compatibility)
    created_at_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    git_sha = get_git_sha()
    
    meta = {
        "schema_version": 2,
        "run_id": rollup_id,
        "created_at_utc": created_at_utc,
        "git_sha": git_sha,
        "config_path": suite_path,
        "config_sha256": compute_file_sha256(suite_path),
        "experiment_name": suite_name,
        "suite": {
            "suite_name": suite_name,
            "seed": effective_params["seed"],
            "n_per": effective_params["n_per"],
            "log_level": effective_params["log_level"],
            "member_run_ids": [run["run_id"] for run in member_runs],
            "is_suite_run": True
        }
    }
    
    with (rollup_dir / "meta.json").open("w") as f:
        json.dump(meta, f, indent=2)
    
    # Aggregate metrics for each member run
    summary = []
    for run in member_runs:
        run_path = run_base / run["run_dir"]
        if run["status"] == "ok" and run_path.exists():
            metrics = aggregate_run_metrics(run_path)
        else:
            metrics = {"total_hands": None, "avg_tricks": None, "reason": None, "bad_files": None}

        config_name = Path(run["config_path"]).name
        summary.append({
            "config": config_name,
            "run_id": run["run_id"],
            "status": run["status"],
            "total_hands": metrics["total_hands"],
            "avg_tricks": metrics["avg_tricks"],
            "reason": metrics.get("reason"),
            "bad_files": metrics.get("bad_files")
        })

    # Sort summary by config name for deterministic ordering
    summary.sort(key=lambda x: x["config"])

    # Write rollup.json (with metrics summary)
    rollup = {
        "schema_version": 1,
        "suite_name": suite_name,
        "suite_seed": effective_params["seed"],
        "suite_n_per": effective_params["n_per"],
        "created_at_utc": created_at_utc,
        "configs": member_runs,
        "summary": summary,
    }

    # Add batch section only when batch is active
    if batch_purpose:
        overrides = config_overrides or {}
        rollup["batch"] = {
            "batch_id": batch_id,
            "batch_purpose": batch_purpose,
            "config_roles": {
                Path(c).name: overrides.get(Path(c).name, {}).get("batch_role", "baseline")
                for c in suite["configs"]
            },
        }

    with (rollup_dir / "rollup.json").open("w") as f:
        json.dump(rollup, f, indent=2, sort_keys=True)

    # Write reports/ROLLUP.md
    with (rollup_dir / "reports" / "ROLLUP.md").open("w") as f:
        f.write(f"# Suite Rollup: {suite_name}\n\n")
        f.write(f"**Seed**: {effective_params['seed']}\n\n")
        f.write(f"**n_per**: {effective_params['n_per']}\n\n")
        f.write(f"**Configs**: {len(member_runs)}\n\n")

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Config | Status | Hands | Avg Tricks | Reason |\n")
        f.write("|--------|--------|------:|----------:|--------|\n")
        for s in summary:
            status_icon = "✓" if s["status"] == "ok" else "✗"
            hands_str = str(s["total_hands"]) if s["total_hands"] is not None else "N/A"
            tricks_str = f"{s['avg_tricks']:.2f}" if s["avg_tricks"] is not None else "N/A"
            reason_str = (s.get("reason", "") or "").replace("\n", " ").replace("|", "\\|")
            f.write(f"| {s['config']} | {status_icon} | {hands_str} | {tricks_str} | {reason_str} |\n")
        f.write("\n")

        f.write("## Member Runs\n\n")
        for run in member_runs:
            status_icon = "✓" if run["status"] == "ok" else "✗"
            f.write(f"- {status_icon} `{run['run_dir']}/` - {run['config_path']}\n")
        f.write("\n---\n\n")
        f.write("**Note**: Open each run's `reports/` directory for detailed analysis.\n")

    return rollup_dir


def main():
    """Main suite runner logic."""
    args = parse_args()
    
    print(f"📦 Loading suite: {args.suite}\n")
    
    # Load suite
    suite = load_suite(args.suite)
    suite_name = suite["suite_name"]
    
    # Resolve parameters
    effective_params = resolve_parameters(suite, args)

    # Resolve batch context
    batch_id, batch_purpose, config_overrides = resolve_batch_context(
        suite, args, suite_name, effective_params["seed"]
    )

    print("======================================================================")
    print(f"🚀 Suite: {suite_name}")
    print("======================================================================")
    print(f"Configs: {len(suite['configs'])}")
    print(f"Seed: {effective_params['seed']}")
    print(f"n_per: {effective_params['n_per']}")
    print(f"log_level: {effective_params['log_level']}")
    print(f"Generate reports: {not args.no_reports}")
    if batch_purpose:
        print(f"Batch ID: {batch_id}")
        print(f"Batch purpose: {batch_purpose}")
    print("======================================================================\n")

    if args.dry_run:
        print("🔍 Dry run - commands that would be executed:\n")
        for config_path in suite["configs"]:
            config_name = Path(config_path).name
            overrides = config_overrides.get(config_name, {})
            batch_role = overrides.get("batch_role", "baseline")
            extra_args = overrides.get("extra_args", [])
            cmd = build_experiment_cmd(
                config_path, effective_params["seed"], effective_params["n_per"],
                effective_params["log_level"], args.run_dir,
                batch_id, batch_role, batch_purpose, extra_args,
            )
            print("  " + " \\\n    ".join(cmd) + "\n")
        print("Rollup would be created after all runs complete.")
        return 0
    
    # Create run base directory
    run_base = Path(args.run_dir)
    run_base.mkdir(parents=True, exist_ok=True)
    
    # Run each config
    member_runs = []
    
    for i, config_path in enumerate(suite["configs"], 1):
        print(f"[{i}/{len(suite['configs'])}] {config_path}")

        config_name = Path(config_path).name
        overrides = config_overrides.get(config_name, {})
        batch_role = overrides.get("batch_role", "baseline") if batch_purpose else None
        extra_args = overrides.get("extra_args", [])

        try:
            run_dir = run_experiment(
                config_path,
                effective_params["seed"],
                effective_params["n_per"],
                effective_params["log_level"],
                run_base,
                batch_id=batch_id,
                batch_role=batch_role,
                batch_purpose=batch_purpose,
                extra_args=extra_args or None,
            )
            
            # Load meta.json to get git_sha
            meta_path = run_dir / "meta.json"
            if meta_path.exists():
                with meta_path.open("r") as f:
                    run_meta = json.load(f)
                run_git_sha = run_meta.get("git_sha", "unknown")
            else:
                run_git_sha = "unknown"
            
            member_runs.append({
                "config_path": config_path,
                "run_id": run_dir.name,
                "run_dir": run_dir.name,  # Relative to rollup_dir.parent
                "status": "ok",
                "git_sha": run_git_sha
            })
            
            # Generate report unless --no-reports
            if not args.no_reports:
                generate_report(run_dir)
            
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            member_runs.append({
                "config_path": config_path,
                "run_id": "failed",
                "run_dir": "failed",
                "status": "failed",
                "git_sha": "unknown"
            })
            # Continue with remaining configs
        
        print()
    
    # Create suite rollup
    print("📊 Creating suite rollup...\n")
    
    rollup_dir = create_suite_rollup(
        suite,
        args.suite,
        effective_params,
        member_runs,
        run_base,
        batch_id=batch_id,
        batch_purpose=batch_purpose,
        config_overrides=config_overrides,
    )
    
    print("======================================================================")
    print("✅ Suite completed!")
    print("======================================================================")
    print(f"📁 Rollup directory: {rollup_dir}")
    print(f"📊 Member runs: {len([r for r in member_runs if r['status'] == 'ok'])}/{len(member_runs)} successful")
    print("======================================================================\n")
    
    # Return non-zero if any runs failed
    failed_count = len([r for r in member_runs if r["status"] == "failed"])
    return 1 if failed_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

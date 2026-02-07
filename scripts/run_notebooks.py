#!/usr/bin/env python
"""Execute notebooks with configurable sample sizes for validation.

Runs phase0_bidless notebooks with papermill, injecting MODE parameter
based on the selected mode:
  - smoke: SMOKE mode (~30 deals, ~10s) - fast sanity checks for CI
  - quick: QUICK mode (~2k deals, ~2-5min) - statistical validation

Usage:
    python scripts/run_notebooks.py --mode smoke   # CI (fast)
    python scripts/run_notebooks.py --mode quick   # Full validation

Modes:
    smoke: Injects MODE="SMOKE", catches import errors and shape mismatches
    quick: Uses notebook's built-in QUICK mode (~2k deals)

The MODE parameter is injected via papermill and overrides the notebook's
default MODE setting. Notebooks that use load_or_generate_outcomes() or
load_or_generate_features() will pick up the injected MODE automatically.
"""

import argparse
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bid_euchre.experiments.meta import get_git_sha, utc_now_iso


def discover_notebooks(pattern: str = "notebooks/phase0_bidless/*.ipynb") -> list[Path]:
    """Find all notebooks matching the pattern.

    Excludes archive/ subdirectory.
    """
    repo_root = Path(__file__).parent.parent
    all_notebooks = sorted(glob.glob(str(repo_root / pattern)))
    # Exclude archived notebooks
    notebooks = [Path(nb) for nb in all_notebooks if "/archive/" not in nb]
    return notebooks


def execute_notebook(
    notebook_path: Path,
    mode: str,
    output_dir: Path,
) -> tuple[bool, str, float]:
    """Execute a single notebook with papermill.

    Args:
        notebook_path: Path to the notebook
        mode: "smoke" or "quick"
        output_dir: Directory for output notebooks

    Returns:
        Tuple of (success, message, duration_seconds)
    """
    import papermill as pm

    # Map CLI mode to notebook MODE parameter
    mode_map = {
        "smoke": "SMOKE",
        "quick": "QUICK",
    }
    notebook_mode = mode_map[mode]

    # Inject parameters (overrides notebook defaults)
    # CANONICAL_MODE=False forces on-the-fly generation in CI
    parameters = {
        "MODE": notebook_mode,
        "CANONICAL_MODE": False,
    }

    output_path = output_dir / notebook_path.name

    start_time = time.time()
    try:
        pm.execute_notebook(
            str(notebook_path),
            str(output_path),
            parameters=parameters,
            kernel_name="python3",
            progress_bar=False,
        )
        duration = time.time() - start_time
        return True, "OK", duration
    except pm.PapermillExecutionError as e:
        duration = time.time() - start_time
        # Extract just the error message, not the full traceback
        error_msg = str(e).split("\n")[0] if str(e) else "Execution error"
        return False, error_msg[:200], duration
    except Exception as e:
        duration = time.time() - start_time
        return False, str(e)[:200], duration


def write_gate_artifacts(
    gate_dir: Path,
    mode: str,
    results: list[tuple[str, bool, str, float]],
) -> dict:
    """Write notebook gate JSON and markdown artifacts.

    Args:
        gate_dir: Directory to write artifacts to.
        mode: Execution mode ("smoke" or "quick").
        results: List of (name, success, message, duration) tuples.

    Returns:
        The gate dict that was written.
    """
    gate_dir.mkdir(parents=True, exist_ok=True)

    passed = sum(1 for _, success, _, _ in results if success)
    failed = sum(1 for _, success, _, _ in results if not success)

    notebooks_data = []
    for name, success, message, duration in results:
        notebooks_data.append({
            "name": name,
            "status": "PASS" if success else "FAIL",
            "duration_sec": round(duration, 2),
            "error": None if success else message,
        })

    overall_status = "PASS" if failed == 0 else "FAIL"

    gate = {
        "gate_type": "notebook_execution",
        "gate_version": 1,
        "mode": mode,
        "timestamp_utc": utc_now_iso(),
        "git_sha": get_git_sha(),
        "notebooks": notebooks_data,
        "overall_status": overall_status,
        "pass_count": passed,
        "fail_count": failed,
    }

    gate_path = gate_dir / "notebook_gate.json"
    with gate_path.open("w") as f:
        json.dump(gate, f, indent=2)

    md_path = gate_dir / "NOTEBOOK_GATE.md"
    with md_path.open("w") as f:
        f.write("# Notebook Execution Gate\n\n")
        f.write(f"**Mode**: {mode.upper()}\n\n")
        f.write(f"**Overall**: {overall_status}\n\n")
        f.write(f"**Timestamp**: {gate['timestamp_utc']}\n\n")
        f.write(f"**Git SHA**: {gate['git_sha']}\n\n")
        f.write("## Results\n\n")
        f.write("| Notebook | Status | Duration | Error |\n")
        f.write("|----------|--------|----------|-------|\n")
        for nb in notebooks_data:
            error_str = (nb["error"] or "").replace("|", "\\|").replace("\n", " ")
            f.write(
                f"| {nb['name']} | {nb['status']} "
                f"| {nb['duration_sec']:.1f}s | {error_str} |\n"
            )
        f.write(f"\n**Total**: {passed} passed, {failed} failed\n")

    return gate


def main():
    parser = argparse.ArgumentParser(
        description="Execute notebooks for validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick"],
        default="smoke",
        help="Execution mode: smoke (~30 deals, ~10s) or quick (~2k deals, ~2-5min)",
    )
    parser.add_argument(
        "--pattern",
        default="notebooks/phase0_bidless/*.ipynb",
        help="Glob pattern for notebooks to run",
    )
    parser.add_argument(
        "--keep-outputs",
        action="store_true",
        help="Keep executed notebook outputs (default: use temp dir)",
    )
    parser.add_argument(
        "--gate-output-dir",
        type=str,
        help="Directory to write notebook_gate.json and NOTEBOOK_GATE.md artifacts",
    )
    args = parser.parse_args()

    # Discover notebooks
    notebooks = discover_notebooks(args.pattern)
    if not notebooks:
        print(f"No notebooks found matching: {args.pattern}")
        sys.exit(0)

    mode_deals = {"smoke": "~30", "quick": "~2000"}
    print(f"Discovered {len(notebooks)} notebook(s)")
    print(f"Mode: {args.mode.upper()} ({mode_deals[args.mode]} deals)")
    print()

    # Create output directory
    if args.keep_outputs:
        output_dir = Path("data/notebook_outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.mkdtemp(prefix="notebook_run_")
        output_dir = Path(temp_dir)

    # Execute notebooks
    results = []
    total_start = time.time()

    for nb_path in notebooks:
        print(f"Running: {nb_path.name}...", end=" ", flush=True)
        success, message, duration = execute_notebook(nb_path, args.mode, output_dir)
        results.append((nb_path.name, success, message, duration))

        status = "PASS" if success else "FAIL"
        print(f"{status} ({duration:.1f}s)")
        if not success:
            print(f"  Error: {message}")

    total_duration = time.time() - total_start

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success, _, _ in results if success)
    failed = sum(1 for _, success, _, _ in results if not success)

    for name, success, message, duration in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name} ({duration:.1f}s)")

    print()
    print(f"Total: {passed} passed, {failed} failed ({total_duration:.1f}s)")

    if not args.keep_outputs:
        print(f"Output notebooks: {output_dir} (temp)")
    else:
        print(f"Output notebooks: {output_dir}")

    # Write gate artifacts if requested
    if args.gate_output_dir:
        write_gate_artifacts(
            Path(args.gate_output_dir), args.mode, results
        )
        print(f"\nGate artifact: {args.gate_output_dir}/notebook_gate.json")
        print(f"Gate markdown: {args.gate_output_dir}/NOTEBOOK_GATE.md")

    # Exit with error if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

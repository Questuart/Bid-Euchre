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
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Frozen schema contract for notebook_gate.json v1
NOTEBOOK_GATE_SCHEMA_VERSION = 1

NOTEBOOK_GATE_REQUIRED_FIELDS = {
    "schema_version",
    "gate_status",
    "created_at_utc",
    "mode",
    "total",
    "passed",
    "failed",
    "notebooks",
}

NOTEBOOK_RESULT_REQUIRED_FIELDS = {
    "name",
    "status",
    "duration_seconds",
    "message",
}


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
    parameters = {
        "MODE": notebook_mode,
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


def build_gate_artifact(results: list[tuple], mode: str) -> dict:
    """Build notebook gate JSON from execution results.

    Args:
        results: List of (name, success, message, duration) tuples
        mode: Execution mode ("smoke" or "quick")

    Returns:
        Gate artifact dict conforming to NOTEBOOK_GATE_SCHEMA_VERSION 1
    """
    passed = sum(1 for _, success, _, _ in results if success)
    failed = len(results) - passed
    return {
        "schema_version": NOTEBOOK_GATE_SCHEMA_VERSION,
        "gate_status": "PASS" if failed == 0 else "FAIL",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": mode,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "notebooks": [
            {
                "name": name,
                "status": "PASS" if success else "FAIL",
                "duration_seconds": round(duration, 2),
                "message": message,
            }
            for name, success, message, duration in results
        ],
    }


def build_gate_markdown(gate: dict) -> str:
    """Build NOTEBOOK_GATE.md from gate artifact dict."""
    lines = [
        f"# Notebook Gate: {gate['gate_status']}",
        "",
        f"**Mode**: {gate['mode']}",
        f"**Total**: {gate['total']} | **Passed**: {gate['passed']} | **Failed**: {gate['failed']}",
        f"**Created**: {gate['created_at_utc']}",
        "",
        "## Results",
        "",
        "| Notebook | Status | Duration (s) | Message |",
        "|----------|--------|-------------:|---------|",
    ]
    for nb in gate["notebooks"]:
        lines.append(
            f"| {nb['name']} | {nb['status']} | {nb['duration_seconds']:.2f} | {nb['message']} |"
        )
    lines.append("")
    return "\n".join(lines)


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
        default=None,
        help="Directory for gate artifacts (notebook_gate.json + NOTEBOOK_GATE.md)",
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

    # Emit gate artifacts if requested
    if args.gate_output_dir:
        gate_dir = Path(args.gate_output_dir)
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate = build_gate_artifact(results, args.mode)
        with open(gate_dir / "notebook_gate.json", "w") as f:
            json.dump(gate, f, indent=2, sort_keys=True)
        with open(gate_dir / "NOTEBOOK_GATE.md", "w") as f:
            f.write(build_gate_markdown(gate))
        print(f"Gate artifacts: {gate_dir}/")

    # Exit with error if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

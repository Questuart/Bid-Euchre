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

# Ensure src is importable for meta helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

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


def build_gate_json(
    results: list[tuple[str, bool, str, float]],
    mode: str,
) -> dict:
    """Build the notebook_gate.json structure from execution results.

    Args:
        results: List of (notebook_name, success, message, duration) tuples.
        mode: Execution mode ("smoke" or "quick").

    Returns:
        Dict suitable for JSON serialization.
    """
    notebooks = []
    for name, success, message, duration in results:
        notebooks.append({
            "name": name,
            "status": "PASS" if success else "FAIL",
            "duration_sec": round(duration, 2),
            "error": None if success else message,
        })

    pass_count = sum(1 for _, s, _, _ in results if s)
    fail_count = sum(1 for _, s, _, _ in results if not s)

    return {
        "gate_type": "notebook_execution",
        "gate_version": 1,
        "mode": mode,
        "timestamp_utc": utc_now_iso(),
        "git_sha": get_git_sha(),
        "notebooks": notebooks,
        "overall_status": "PASS" if fail_count == 0 else "FAIL",
        "pass_count": pass_count,
        "fail_count": fail_count,
    }


def build_gate_markdown(gate: dict) -> str:
    """Build NOTEBOOK_GATE.md content from the gate JSON structure."""
    lines = [
        f"# Notebook Gate — {gate['mode'].upper()} mode",
        "",
        f"**Status**: {gate['overall_status']}",
        f"**Timestamp**: {gate['timestamp_utc']}",
        f"**Git SHA**: `{gate['git_sha']}`",
        f"**Pass**: {gate['pass_count']}  |  **Fail**: {gate['fail_count']}",
        "",
        "## Results",
        "",
        "| Notebook | Status | Duration |",
        "|----------|--------|----------|",
    ]

    for nb in gate["notebooks"]:
        status_icon = "PASS" if nb["status"] == "PASS" else "FAIL"
        lines.append(f"| {nb['name']} | {status_icon} | {nb['duration_sec']:.1f}s |")

    # Show errors if any
    failures = [nb for nb in gate["notebooks"] if nb["status"] == "FAIL"]
    if failures:
        lines.extend(["", "## Errors", ""])
        for nb in failures:
            lines.append(f"- **{nb['name']}**: {nb['error']}")

    lines.append("")
    return "\n".join(lines)


def write_gate_artifacts(
    results: list[tuple[str, bool, str, float]],
    mode: str,
    gate_output_dir: str,
) -> None:
    """Write notebook_gate.json and NOTEBOOK_GATE.md to the gate output dir."""
    gate_dir = Path(gate_output_dir)
    gate_dir.mkdir(parents=True, exist_ok=True)

    gate = build_gate_json(results, mode)

    gate_json_path = gate_dir / "notebook_gate.json"
    with gate_json_path.open("w") as f:
        json.dump(gate, f, indent=2)
    print(f"\nGate JSON: {gate_json_path}")

    gate_md_path = gate_dir / "NOTEBOOK_GATE.md"
    gate_md_path.write_text(build_gate_markdown(gate))
    print(f"Gate MD:   {gate_md_path}")


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
        default=None,
        help="Directory to write notebook_gate.json and NOTEBOOK_GATE.md (e.g. <run_dir>/reports/notebook_review/)",
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

    # Write gate artifacts if --gate-output-dir given
    if args.gate_output_dir:
        write_gate_artifacts(results, args.mode, args.gate_output_dir)

    # Exit with error if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

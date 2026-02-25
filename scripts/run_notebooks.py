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
    all_notebooks = sorted(glob.glob(str(repo_root / pattern), recursive=True))
    # Exclude archived notebooks
    notebooks = [Path(nb) for nb in all_notebooks if "archive" not in Path(nb).parts]
    return notebooks


def execute_notebook(
    notebook_path: Path,
    mode: str,
    output_dir: Path,
    extra_parameters: dict | None = None,
) -> tuple[bool, str, float]:
    """Execute a single notebook with papermill.

    Args:
        notebook_path: Path to the notebook
        mode: "smoke" or "quick"
        output_dir: Directory for output notebooks
        extra_parameters: Additional papermill parameters to inject

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
    if extra_parameters:
        parameters.update(extra_parameters)

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


def build_gate_artifact(
    results: list[tuple],
    mode: str,
    validation_results: dict[str, dict] | None = None,
) -> dict:
    """Build notebook gate JSON from execution and validation results.

    Args:
        results: List of (name, success, message, duration) tuples
        mode: Execution mode ("smoke" or "quick")
        validation_results: Optional dict mapping notebook name to
            {"ok": bool, "errors": list[str]} from post-execution validation

    Returns:
        Gate artifact dict conforming to NOTEBOOK_GATE_SCHEMA_VERSION 1
    """
    notebooks = []
    for name, success, message, duration in results:
        entry = {
            "name": name,
            "status": "PASS" if success else "FAIL",
            "duration_seconds": round(duration, 2),
            "message": message,
        }
        if validation_results and name in validation_results:
            vr = validation_results[name]
            entry["validation_status"] = "PASS" if vr["ok"] else "FAIL"
            if not vr["ok"]:
                entry["validation_message"] = "; ".join(vr["errors"])
                entry["status"] = "FAIL"
        notebooks.append(entry)

    passed = sum(1 for nb in notebooks if nb["status"] == "PASS")
    failed = len(notebooks) - passed
    return {
        "schema_version": NOTEBOOK_GATE_SCHEMA_VERSION,
        "gate_status": "PASS" if failed == 0 else "FAIL",
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": mode,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "notebooks": notebooks,
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
    parser.add_argument(
        "--semantic-gate-output-dir",
        default=None,
        help="Directory for semantic gate JSON artifacts (passed as SEMANTIC_GATE_OUTPUT_DIR parameter)",
    )
    parser.add_argument(
        "--chart-output-dir",
        default=None,
        help="Directory for chart PNG artifacts (passed as CHART_OUTPUT_DIR parameter)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate executed notebooks (check structure, MODE injection, cell errors)",
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

    # Build extra papermill parameters from CLI args
    extra_parameters: dict = {}
    if args.semantic_gate_output_dir:
        extra_parameters["SEMANTIC_GATE_OUTPUT_DIR"] = args.semantic_gate_output_dir
    if args.chart_output_dir:
        extra_parameters["CHART_OUTPUT_DIR"] = args.chart_output_dir

    # Execute notebooks
    results = []
    total_start = time.time()

    for nb_path in notebooks:
        print(f"Running: {nb_path.name}...", end=" ", flush=True)
        success, message, duration = execute_notebook(
            nb_path, args.mode, output_dir, extra_parameters or None
        )
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

    # Validate executed notebooks if requested
    validation_map: dict[str, dict] | None = None
    if args.validate:
        from bid_euchre.diagnostics.notebook_validation import validate_notebook

        mode_map = {"smoke": "SMOKE", "quick": "QUICK"}
        expected_mode = mode_map[args.mode]

        print()
        print("=" * 60)
        print("VALIDATION")
        print("=" * 60)

        validation_map = {}
        validation_failures = 0
        for name, success, _, _ in results:
            if not success:
                print(f"  [SKIP] {name} (execution failed)")
                continue

            output_path = output_dir / name
            result = validate_notebook(output_path, expected_mode=expected_mode)

            if result.ok:
                validation_map[name] = {"ok": True, "errors": []}
                print(f"  [PASS] {name}")
            else:
                validation_failures += 1
                errors = list(result.errors)
                for cell_err in result.cell_errors:
                    errors.append(
                        f"Cell {cell_err.cell_index}: "
                        f"{cell_err.ename}: {cell_err.evalue}"
                    )
                validation_map[name] = {"ok": False, "errors": errors}
                print(f"  [FAIL] {name}")
                for err in errors:
                    print(f"    - {err}")

        if validation_failures > 0:
            failed += validation_failures
            print(f"\nValidation: {validation_failures} notebook(s) failed validation")

    # Emit gate artifacts if requested
    if args.gate_output_dir:
        gate_dir = Path(args.gate_output_dir)
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate = build_gate_artifact(
            results, args.mode, validation_results=validation_map
        )
        with open(gate_dir / "notebook_gate.json", "w") as f:
            json.dump(gate, f, indent=2, sort_keys=True)
        with open(gate_dir / "NOTEBOOK_GATE.md", "w") as f:
            f.write(build_gate_markdown(gate))
        print(f"Gate artifacts: {gate_dir}/")

    # Exit with error if any failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

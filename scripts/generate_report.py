#!/usr/bin/env python
"""
Generate reports for a single experiment run.

Strict I/O Contract:
- READS: <run_dir>/results/**, <run_dir>/meta.json, <run_dir>/config_effective.yaml,
         <run_dir>/datasets/** (bidless_outcomes.parquet if present)
- WRITES: <run_dir>/reports/** and <run_dir>/artifacts/**

Report Types:
- ANALYSIS_SUMMARY.md: Overview of run with links to results
- bidding_strategy/: Auction-mode bidder evaluation (if logs present)
- sanity_tests/: Strategy sanity tests (for bidless experiments)

Usage:
    PYTHONPATH=src python scripts/generate_report.py --run-dir data/runs/<run_id>
    PYTHONPATH=src python scripts/generate_report.py --run-dir data/runs/<run_id> --overwrite
"""

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from bid_euchre.diagnostics.sanity_tests import (
    SanityTestResult,
    run_sanity_tests,
    write_sanity_report,
)
from bid_euchre.reporting.evaluator import generate_bidder_evaluation


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate reports for a single experiment run",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--run-dir",
        help="Path to run directory (must contain results/, meta.json, etc.)"
    )
    parser.add_argument(
        "--batch-dir",
        help="Path to suite rollup directory for batch report generation"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing reports (if absent, error if reports/ exists)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print progress messages (default: quiet unless errors)"
    )
    parser.add_argument(
        "--fail-on-sanity-failures",
        action="store_true",
        help="Exit non-zero if any sanity test has status FAIL (and also fail if sanity cannot run)"
    )
    args = parser.parse_args()
    if not args.run_dir and not args.batch_dir:
        parser.error("Either --run-dir or --batch-dir is required")
    if args.run_dir and args.batch_dir:
        parser.error("--run-dir and --batch-dir are mutually exclusive")
    return args


def validate_run_directory(run_dir: Path) -> None:
    """
    Validate that run_dir looks like a valid run directory.
    
    Exit non-zero with clear message if invalid.
    """
    if not run_dir.exists():
        print(f"❌ Error: Run directory does not exist: {run_dir}", file=sys.stderr)
        sys.exit(1)
    
    if not run_dir.is_dir():
        print(f"❌ Error: Path is not a directory: {run_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Check for required structure (at minimum: results/ directory)
    results_dir = run_dir / "results"
    if not results_dir.exists() or not results_dir.is_dir():
        print(f"❌ Error: Not a valid run directory (missing results/): {run_dir}", file=sys.stderr)
        sys.exit(1)


def check_overwrite_policy(run_dir: Path, overwrite: bool) -> None:
    """
    Check overwrite policy for reports directory.
    
    Exit non-zero if reports/ exists with files and --overwrite not set.
    Empty reports/ directory is OK (created by PR #17 runner).
    """
    reports_dir = run_dir / "reports"
    
    if reports_dir.exists():
        # Check if reports/ has any files
        existing_files = list(reports_dir.rglob("*"))
        has_files = any(f.is_file() for f in existing_files)
        
        if has_files and not overwrite:
            print(f"❌ Error: reports/ contains existing files and --overwrite not specified: {reports_dir}", file=sys.stderr)
            print("   Use --overwrite to regenerate reports.", file=sys.stderr)
            sys.exit(1)
        elif has_files and overwrite:
            # Clean existing report files
            for f in existing_files:
                if f.is_file():
                    f.unlink()
                elif f.is_dir():
                    shutil.rmtree(f)


def discover_result_files(run_dir: Path, verbose: bool) -> List[str]:
    """
    Discover all result files under run_dir/results/.
    
    Returns list of relative paths (relative to run_dir).
    """
    results_dir = run_dir / "results"
    result_files = []
    
    if results_dir.exists():
        for file_path in sorted(results_dir.rglob("*")):
            if file_path.is_file():
                rel_path = file_path.relative_to(run_dir)
                result_files.append(str(rel_path))
                if verbose:
                    print(f"  📄 Found: {rel_path}")
    
    return result_files


def load_metadata(run_dir: Path, verbose: bool) -> Dict:
    """
    Load run metadata from meta.json and config_effective.yaml.

    Returns dict with available fields (may be incomplete if files missing).
    """
    metadata = {
        "run_id": run_dir.name,
        "seed": "unknown",
        "n_per": "unknown",
        "mode": "unknown",
        "experiment_name": "unknown",
        "git_sha": None,
        "total_hands": None,
    }

    # Try meta.json
    meta_path = run_dir / "meta.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                meta = json.load(f)
                metadata["seed"] = meta.get("seed", "unknown")
                metadata["n_per"] = meta.get("n_per", "unknown")
                metadata["git_sha"] = meta.get("git_sha")
                metadata["total_hands"] = meta.get("total_hands")
                if verbose:
                    print("  ℹ️  Loaded meta.json")
        except Exception as e:
            if verbose:
                print(f"  ⚠️  Warning: Could not parse meta.json: {e}")

    # Try config_effective.yaml
    config_path = run_dir / "config_effective.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                # Prefer meta.json values, but fall back to config
                if metadata["seed"] == "unknown" and "parameters" in config:
                    metadata["seed"] = config["parameters"].get("seed", "unknown")
                if metadata["n_per"] == "unknown" and "parameters" in config:
                    metadata["n_per"] = config["parameters"].get("n_per", "unknown")
                metadata["mode"] = config.get("mode", "unknown")
                metadata["experiment_name"] = config.get("experiment_name", "unknown")
                if verbose:
                    print("  ℹ️  Loaded config_effective.yaml")
        except Exception as e:
            if verbose:
                print(f"  ⚠️  Warning: Could not parse config_effective.yaml: {e}")

    return metadata


def generate_analysis_summary(
    run_dir: Path,
    metadata: Dict,
    result_files: List[str],
    chart_files: List[str],
    verbose: bool
) -> None:
    """
    Generate ANALYSIS_SUMMARY.md in run_dir/reports/.
    """
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    summary_path = reports_dir / "ANALYSIS_SUMMARY.md"
    
    timestamp_utc = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    # Build content
    lines = [
        "# Analysis Summary",
        "",
        f"**Run ID:** `{metadata['run_id']}`",
        f"**Experiment:** {metadata['experiment_name']}",
        f"**Seed:** {metadata['seed']}",
        f"**N Per:** {metadata['n_per']}",
        f"**Mode:** {metadata['mode']}",
        "",
        "## Results Files Discovered",
        "",
    ]
    
    if result_files:
        for rf in result_files:
            lines.append(f"- `{rf}`")
    else:
        lines.append("*No results found*")
    
    lines.extend([
        "",
        "## Charts Generated",
        "",
    ])
    
    if chart_files:
        for cf in chart_files:
            lines.append(f"- `{cf}`")
    else:
        lines.append("*No charts generated*")
    
    lines.extend([
        "",
        "---",
        f"*Generated: {timestamp_utc}*",
        ""
    ])
    
    content = "\n".join(lines)
    
    with open(summary_path, "w") as f:
        f.write(content)
    
    if verbose:
        print(f"  ✅ Generated: {summary_path.relative_to(run_dir)}")


def generate_charts(run_dir: Path, metadata: Dict, verbose: bool) -> List[str]:
    """
    Generate charts into run_dir/reports/.

    Returns list of chart filenames (relative to reports/).

    For this minimal PR: no charts yet. Future PRs can add chart generation here.
    """
    # Placeholder: no chart generation in this PR
    # Future: call existing plotting utilities from src/bid_euchre/reporting/
    return []


def summarize_sanity_results(
    results: Dict[str, SanityTestResult],
) -> Dict[str, Any]:
    """
    Summarize sanity test results for canonical summary and gating.

    Returns dict with:
    - pass_count, warn_count, fail_count, skip_count
    - failing_tests: list of test names with FAIL status
    - all_passed: bool (True iff fail_count == 0)
    """
    if not results:
        return {
            "pass_count": 0,
            "warn_count": 0,
            "fail_count": 0,
            "skip_count": 0,
            "failing_tests": [],
            "all_passed": True,
        }

    statuses = [r.status for r in results.values()]
    pass_count = statuses.count("PASS")
    warn_count = statuses.count("WARN")
    fail_count = statuses.count("FAIL")
    skip_count = statuses.count("SKIP")

    failing_tests = [name for name, r in results.items() if r.status == "FAIL"]

    return {
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "failing_tests": failing_tests,
        "all_passed": fail_count == 0,
    }


def write_canonical_summary(
    run_dir: Path,
    metadata: Dict,
    sanity_summary: Dict[str, Any],
    result_files: List[str],
) -> Tuple[Path, Path]:
    """
    Write canonical_summary.json and canonical_summary.md to artifacts/.

    Creates artifacts/ directory if needed.

    Returns:
        Tuple of (json_path, md_path)
    """
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    # Detect dataset presence
    datasets_dir = run_dir / "datasets"
    datasets_present = datasets_dir.exists() and any(datasets_dir.iterdir()) if datasets_dir.exists() else False
    bidless_parquet = (datasets_dir / "bidless.parquet").exists() if datasets_dir.exists() else False
    bidless_outcomes_parquet = (datasets_dir / "bidless_outcomes.parquet").exists() if datasets_dir.exists() else False

    # Build JSON content
    summary_data = {
        "run_id": metadata.get("run_id", "unknown"),
        "experiment_name": metadata.get("experiment_name", "unknown"),
        "seed": metadata.get("seed", "unknown"),
        "n_per": metadata.get("n_per", "unknown"),
        "git_sha": metadata.get("git_sha"),
        "total_hands": metadata.get("total_hands"),
        "sanity": sanity_summary,
        "discovered": {
            "results_files": result_files,
            "datasets_present": datasets_present,
            "bidless_parquet": bidless_parquet,
            "bidless_outcomes_parquet": bidless_outcomes_parquet,
        },
        "generated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Write JSON
    json_path = artifacts_dir / "canonical_summary.json"
    with open(json_path, "w") as f:
        json.dump(summary_data, f, indent=2)

    # Write Markdown
    md_path = artifacts_dir / "canonical_summary.md"
    sanity_status = "PASS" if sanity_summary["all_passed"] else "FAIL"
    failing_str = ", ".join(sanity_summary["failing_tests"]) if sanity_summary["failing_tests"] else "None"

    md_content = f"""# Canonical Summary

**Run ID:** `{summary_data['run_id']}`
**Experiment:** {summary_data['experiment_name']}
**Seed:** {summary_data['seed']}
**N Per:** {summary_data['n_per']}
**Git SHA:** {summary_data['git_sha'] or 'N/A'}
**Total Hands:** {summary_data['total_hands'] or 'N/A'}

## Sanity Tests

**Status:** {sanity_status}

| Metric | Count |
|--------|-------|
| PASS | {sanity_summary['pass_count']} |
| WARN | {sanity_summary['warn_count']} |
| FAIL | {sanity_summary['fail_count']} |
| SKIP | {sanity_summary['skip_count']} |

**Failing Tests:** {failing_str}

## Discovered Files

- **Results files:** {len(result_files)}
- **Datasets present:** {datasets_present}
- **bidless.parquet:** {bidless_parquet}
- **bidless_outcomes.parquet:** {bidless_outcomes_parquet}

---
*Generated: {summary_data['generated_at_utc']}*
"""

    with open(md_path, "w") as f:
        f.write(md_content)

    return json_path, md_path


def generate_batch_report(batch_dir: Path, verbose: bool) -> int:
    """Generate batch report from suite rollup directory.

    Reads rollup.json, discovers member runs, reads their canonical summaries,
    and produces BATCH_REPORT.md + batch_gate.json.

    Returns exit code.
    """
    rollup_path = batch_dir / "rollup.json"
    if not rollup_path.exists():
        print(f"Error: No rollup.json found in {batch_dir}", file=sys.stderr)
        return 1

    with open(rollup_path) as f:
        rollup = json.load(f)

    suite_name = rollup.get("suite_name", "unknown")
    member_configs = rollup.get("configs", [])

    if verbose:
        print(f"Batch report for suite: {suite_name}")
        print(f"   Member runs: {len(member_configs)}")

    # Discover member runs and read their canonical summaries
    run_base = batch_dir.parent  # Member runs are siblings of rollup dir
    member_statuses: List[Dict[str, Any]] = []

    for config in member_configs:
        run_id = config.get("run_id", "unknown")
        run_dir_name = config.get("run_dir", run_id)
        member_run_dir = run_base / run_dir_name

        status: Dict[str, Any] = {
            "run_id": run_id,
            "batch_role": None,
            "sanity_pass": 0,
            "sanity_warn": 0,
            "sanity_fail": 0,
            "sanity_skip": 0,
            "gate_status": "UNKNOWN",
        }

        # Try to read canonical_summary.json
        summary_path = member_run_dir / "artifacts" / "canonical_summary.json"
        if summary_path.exists():
            try:
                with open(summary_path) as f:
                    summary = json.load(f)
                sanity = summary.get("sanity", {})
                status["sanity_pass"] = sanity.get("pass_count", 0)
                status["sanity_warn"] = sanity.get("warn_count", 0)
                status["sanity_fail"] = sanity.get("fail_count", 0)
                status["sanity_skip"] = sanity.get("skip_count", 0)
                status["gate_status"] = (
                    "PASS" if sanity.get("all_passed", False) else "FAIL"
                )
            except Exception as e:
                if verbose:
                    print(f"   Could not read {summary_path}: {e}")
                status["gate_status"] = "UNKNOWN"
        else:
            if verbose:
                print(f"   No canonical_summary.json for {run_id}")

        # Try to read batch metadata from meta.json
        meta_path = member_run_dir / "meta.json"
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                batch = meta.get("batch", {})
                status["batch_role"] = batch.get("batch_role")
            except Exception:
                pass

        # Try to read notebook gate
        notebook_gate_path = (
            member_run_dir / "reports" / "notebook_review" / "notebook_gate.json"
        )
        if notebook_gate_path.exists():
            try:
                with open(notebook_gate_path) as f:
                    nb_gate = json.load(f)
                if nb_gate.get("overall_status") == "FAIL":
                    status["gate_status"] = "FAIL"
            except Exception:
                pass

        member_statuses.append(status)

    # Compute eligibility
    from bid_euchre.validation.promotion import compute_eligibility

    # Extract expected roles from rollup batch metadata if present
    expected_roles = None  # Could be derived from suite YAML batch_roles

    eligibility = compute_eligibility(member_statuses, expected_roles)

    # Build batch_gate.json
    rollup_batch = rollup.get("batch", {})
    batch_id = rollup_batch.get(
        "batch_id", rollup.get("suite_name", "unknown")
    )

    gate: Dict[str, Any] = {
        "gate_type": "batch_promotion",
        "gate_version": 1,
        "batch_id": batch_id,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": (
            rollup.get("configs", [{}])[0].get("git_sha", "unknown")
            if member_configs
            else "unknown"
        ),
        "member_runs": member_statuses,
        "overall_status": "PASS" if eligibility["eligible"] else "FAIL",
        "eligible": eligibility["eligible"],
        "reasons": eligibility["reasons"],
    }

    # Write artifacts
    artifacts_dir = batch_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    gate_path = artifacts_dir / "batch_gate.json"
    with open(gate_path, "w") as f:
        json.dump(gate, f, indent=2)

    # Write BATCH_REPORT.md
    reports_dir = batch_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    md_path = reports_dir / "BATCH_REPORT.md"
    with open(md_path, "w") as f:
        f.write(f"# Batch Report: {suite_name}\n\n")
        f.write(f"**Batch ID:** {batch_id}\n\n")
        f.write(f"**Overall Status:** {gate['overall_status']}\n\n")
        f.write(f"**Eligible:** {gate['eligible']}\n\n")

        if gate["reasons"]:
            f.write("## Non-Eligibility Reasons\n\n")
            for r in gate["reasons"]:
                f.write(f"- {r}\n")
            f.write("\n")

        f.write("## Member Runs\n\n")
        f.write("| Run ID | Role | PASS | WARN | FAIL | SKIP | Gate |\n")
        f.write("|--------|------|------|------|------|------|------|\n")
        for m in member_statuses:
            role = m.get("batch_role") or "---"
            f.write(
                f"| {m['run_id'][:40]} | {role} "
                f"| {m['sanity_pass']} | {m['sanity_warn']} "
                f"| {m['sanity_fail']} | {m['sanity_skip']} "
                f"| {m['gate_status']} |\n"
            )
        f.write(f"\n---\n*Generated: {gate['timestamp_utc']}*\n")

    print(f"Batch gate: {gate_path}")
    print(f"Batch report: {md_path}")
    print(f"   Eligible: {gate['eligible']}")
    if gate["reasons"]:
        for r in gate["reasons"]:
            print(f"   {r}")

    return 0


def main() -> int:
    """Main entrypoint."""
    args = parse_args()

    # Batch mode
    if args.batch_dir:
        batch_dir = Path(args.batch_dir).resolve()
        return generate_batch_report(batch_dir, args.verbose)

    # Single-run mode (existing logic)
    run_dir = Path(args.run_dir).resolve()
    
    if args.verbose:
        print(f"🔍 Validating run directory: {run_dir}")
    
    # Validate run directory
    validate_run_directory(run_dir)
    
    # Check overwrite policy
    check_overwrite_policy(run_dir, args.overwrite)
    
    if args.verbose:
        print("📊 Generating report...")
    
    # Load metadata
    if args.verbose:
        print("📖 Loading metadata...")
    metadata = load_metadata(run_dir, args.verbose)
    
    # Discover result files
    if args.verbose:
        print("🔎 Discovering result files...")
    result_files = discover_result_files(run_dir, args.verbose)
    
    # Generate charts (placeholder for now)
    chart_files = generate_charts(run_dir, metadata, args.verbose)
    
    # Generate summary
    if args.verbose:
        print("📝 Generating ANALYSIS_SUMMARY.md...")
    generate_analysis_summary(run_dir, metadata, result_files, chart_files, args.verbose)
    
    evaluation_path = generate_bidder_evaluation(run_dir)
    if evaluation_path:
        rel_path = evaluation_path.relative_to(run_dir)
        if args.verbose:
            print(f"🧮 Generated bidder evaluation: {rel_path}")
        else:
            print(f"🧮 Bidder evaluation: {rel_path}")

    # Run sanity tests for bidless experiments
    if args.verbose:
        print("🔬 Running strategy sanity tests...")

    sanity_results: Optional[Dict[str, SanityTestResult]] = None
    sanity_ran = False

    try:
        sanity_results = run_sanity_tests(str(run_dir))
        if sanity_results and "error" not in sanity_results:
            sanity_ran = True
            write_sanity_report(str(run_dir), sanity_results)
        elif args.verbose:
            print("🔬 Sanity tests: skipped (no outcomes data)")
    except Exception as e:
        if args.verbose:
            print(f"⚠️  Sanity tests failed: {e}")

    # Compute sanity summary (works even if sanity didn't run)
    if sanity_ran and sanity_results:
        sanity_summary = summarize_sanity_results(sanity_results)
    else:
        sanity_summary = summarize_sanity_results({})

    # Print sanity status summary
    if sanity_ran:
        status_parts = []
        if sanity_summary["pass_count"]:
            status_parts.append(f"{sanity_summary['pass_count']} PASS")
        if sanity_summary["warn_count"]:
            status_parts.append(f"{sanity_summary['warn_count']} WARN")
        if sanity_summary["fail_count"]:
            status_parts.append(f"{sanity_summary['fail_count']} FAIL")
        if sanity_summary["skip_count"]:
            status_parts.append(f"{sanity_summary['skip_count']} SKIP")
        print(f"🔬 Sanity tests: {', '.join(status_parts)}")

    # Write canonical summary (always, regardless of verbose mode)
    if args.verbose:
        print("📄 Writing canonical summary...")
    json_path, md_path = write_canonical_summary(
        run_dir, metadata, sanity_summary, result_files
    )
    if args.verbose:
        print(f"   Artifacts: {json_path.relative_to(run_dir)}, {md_path.relative_to(run_dir)}")

    if args.verbose:
        print("✅ Report generation complete!")
    else:
        # Always print success message even in quiet mode
        print(f"✅ Report generated: {run_dir / 'reports'}")

    # Handle --fail-on-sanity-failures gate
    if args.fail_on_sanity_failures:
        if sanity_summary["fail_count"] > 0:
            failing = sanity_summary["failing_tests"]
            print(f"❌ Sanity gate failed: {failing}")
            return 1
        if not sanity_ran:
            print("❌ Sanity gate failed: sanity tests could not run (no outcomes)")
            return 2
        # All passed
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

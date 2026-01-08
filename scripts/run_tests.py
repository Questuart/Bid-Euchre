#!/usr/bin/env python3
"""
Test runner script for the Bid Euchre simulation project.

This script provides convenient ways to run different test suites.
"""

import argparse
import importlib.util
import os
import subprocess
import sys


def run_pytest(args):
    """Try to run pytest, fallback to manual test execution if not available."""
    if importlib.util.find_spec("pytest") is not None:
        cmd = [sys.executable, "-m", "pytest"] + args
        print(f"Running: {' '.join(cmd)}")
        # Run pytest from project root directory (not scripts directory)
        project_root = os.path.join(os.path.dirname(__file__), "..")
        env = os.environ.copy()
        # Ensure src-layout imports work without per-test sys.path hacks
        env["PYTHONPATH"] = os.path.join(project_root, "src")
        return subprocess.run(cmd, cwd=project_root, env=env)
    else:
        print("⚠️  pytest not found, running tests manually...")
        return run_manual_tests(args)


def run_manual_tests(args):
    """Run tests manually without pytest."""
    print("🔧 Manual test execution not fully implemented.")
    print("💡 Use: python scripts/validate_tests.py")
    print("   Or install pytest: pip install pytest pytest-cov")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Run Bid Euchre tests")
    parser.add_argument(
        "--unit", "-u",
        action="store_true",
        help="Run unit tests only (core, rules, strategy)"
    )
    parser.add_argument(
        "--integration", "-i",
        action="store_true",
        help="Run integration tests only"
    )
    parser.add_argument(
        "--performance", "-p",
        action="store_true",
        help="Run performance tests only"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run all tests (default)"
    )
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Generate coverage report (requires pytest)"
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=None,
        help="If set, fail if total coverage is below this percentage (e.g. 80). Default: do not fail on coverage."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Determine which tests to run (translate to valid pytest args)
    test_args = []

    # Selection:
    # - unit: exclude integration + slow
    # - integration: integration marker
    # - performance: slow marker
    # - default/all: run everything
    if args.unit:
        test_args += ["-m", "not integration and not slow"]
    elif args.integration:
        test_args += ["-m", "integration"]
    elif args.performance:
        test_args += ["-m", "slow"]

    # Coverage: pytest.ini already configures coverage by default. Keep flag for
    # compatibility. When enabled, run with pytest-cov.
    if args.coverage:
        test_args += [
            "--cov=src/bid_euchre",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ]
        if args.fail_under is not None:
            test_args.append(f"--cov-fail-under={args.fail_under}")

    if args.verbose:
        test_args.append("-v")

    # Run tests
    result = run_pytest(test_args)

    # Handle both CompletedProcess objects (from subprocess) and integers (from manual testing)
    if hasattr(result, 'returncode'):
        return result.returncode
    else:
        return result


if __name__ == "__main__":
    sys.exit(main())

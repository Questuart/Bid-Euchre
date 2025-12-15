#!/usr/bin/env python3
"""
Test runner script for the Bid Euchre simulation project.

This script provides convenient ways to run different test suites.
"""

import sys
import os
import subprocess
import argparse
import importlib.util


def run_pytest(args):
    """Try to run pytest, fallback to manual test execution if not available."""
    try:
        import pytest
        cmd = [sys.executable, "-m", "pytest"] + args
        print(f"Running: {' '.join(cmd)}")
        # Run pytest from project root directory (not scripts directory)
        project_root = os.path.join(os.path.dirname(__file__), "..")
        return subprocess.run(cmd, cwd=project_root)
    except (ImportError, FileNotFoundError):
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
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Determine which tests to run
    test_args = []
    if args.unit:
        test_args.append("--unit")
    elif args.integration:
        test_args.append("--integration")
    elif args.performance:
        test_args.append("--performance")
    # --all or default doesn't add flags

    if args.coverage:
        test_args.append("--coverage")

    if args.verbose:
        test_args.append("--verbose")

    # Run tests
    result = run_pytest(test_args)

    # Handle both CompletedProcess objects (from subprocess) and integers (from manual testing)
    if hasattr(result, 'returncode'):
        return result.returncode
    else:
        return result


if __name__ == "__main__":
    sys.exit(main())

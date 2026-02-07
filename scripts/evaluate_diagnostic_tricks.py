#!/usr/bin/env python
"""DEPRECATED: Use scripts/internal/evaluate_diagnostic_tricks.py instead."""
import subprocess
import sys
import warnings

if __name__ == "__main__":
    warnings.warn(
        "scripts/evaluate_diagnostic_tricks.py has moved to scripts/internal/. "
        "Update your invocation.",
        DeprecationWarning,
        stacklevel=1,
    )
    sys.exit(
        subprocess.call(
            [sys.executable, "scripts/internal/evaluate_diagnostic_tricks.py"]
            + sys.argv[1:]
        )
    )

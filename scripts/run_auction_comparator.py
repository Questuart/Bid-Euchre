#!/usr/bin/env python
"""DEPRECATED: Use scripts/internal/run_auction_comparator.py instead."""
import subprocess
import sys
import warnings

if __name__ == "__main__":
    warnings.warn(
        "scripts/run_auction_comparator.py has moved to scripts/internal/. "
        "Update your invocation.",
        DeprecationWarning,
        stacklevel=1,
    )
    sys.exit(
        subprocess.call(
            [sys.executable, "scripts/internal/run_auction_comparator.py"]
            + sys.argv[1:]
        )
    )

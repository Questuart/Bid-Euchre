#!/usr/bin/env python
"""DEPRECATED: Use scripts/internal/play_policy_gate.py instead."""
import subprocess
import sys
import warnings

if __name__ == "__main__":
    warnings.warn(
        "scripts/play_policy_gate.py has moved to scripts/internal/. "
        "Update your invocation.",
        DeprecationWarning,
        stacklevel=1,
    )
    sys.exit(
        subprocess.call(
            [sys.executable, "scripts/internal/play_policy_gate.py"] + sys.argv[1:]
        )
    )

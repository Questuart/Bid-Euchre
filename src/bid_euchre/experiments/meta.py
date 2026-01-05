"""
Metadata helpers for experiment runs.

Utilities for generating reproducible experiment metadata including
git SHA, config hashes, and UTC timestamps.
"""

import hashlib
import subprocess
from datetime import datetime, timezone


def utc_now_iso() -> str:
    """UTC time in ISO8601 with Z suffix."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: str) -> str:
    """SHA256 of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_git_sha() -> str:
    """Best-effort git SHA (or 'unknown' if not available)."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL)
        sha = out.decode("utf-8").strip()
        return sha if sha else "unknown"
    except Exception:
        return "unknown"

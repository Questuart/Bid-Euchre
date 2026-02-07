"""Canonical run registry for Phase 0 notebooks.

Maps logical dataset keys to canonical run IDs. Notebooks use this to
resolve data paths when CANONICAL_MODE=True.

Override the data root via CANONICAL_DATA_ROOT env var (default: ../../data/runs).
"""

import os
from pathlib import Path

# Canonical run IDs (point-in-time: 2026-02-04, seed=42)
CANONICAL_RUNS = {
    "greedy_dataset": "canonical_bidless_dataset_greedy_42_20260204_221121",
    "glutton_dataset": "canonical_bidless_dataset_glutton_42_20260204_222713",
    "outcomes_zoom": "canonical_bidless_outcomes_zoom_42_20260204_222712",
    "outcomes_matrix": "canonical_bidless_outcomes_matrix_shallow_42_20260206_171634",
}


def resolve_run_dir(key: str) -> Path:
    """Resolve a canonical run key to a directory path.

    Args:
        key: Logical name from CANONICAL_RUNS (e.g., "greedy_dataset").

    Returns:
        Absolute Path to the run directory.

    Raises:
        KeyError: If key is not in the registry.
        FileNotFoundError: If the resolved directory does not exist.
    """
    if key not in CANONICAL_RUNS:
        raise KeyError(
            f"Unknown canonical run key: {key!r}. "
            f"Available: {sorted(CANONICAL_RUNS.keys())}"
        )

    run_id = CANONICAL_RUNS[key]

    # Allow override via env var
    data_root = os.environ.get(
        "CANONICAL_DATA_ROOT",
        str(Path(__file__).parent.parent.parent / "data" / "runs"),
    )

    run_dir = Path(data_root) / run_id
    if not run_dir.exists():
        raise FileNotFoundError(
            f"Canonical run directory not found: {run_dir}\n"
            f"Key: {key!r}, Run ID: {run_id}\n"
            f"Set CANONICAL_DATA_ROOT env var or generate canonical data first."
        )

    return run_dir

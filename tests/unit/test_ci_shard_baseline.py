"""Regression tests for the pytest-split duration baseline.

The `.test_durations` file is committed to the repo and used by the
sharded CI test lane (``tests-shard`` job).  These tests verify the
baseline is well-formed and reasonably complete.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DURATIONS_PATH = REPO_ROOT / ".test_durations"


class TestShardBaseline:
    """Validate the committed .test_durations file."""

    def test_durations_file_exists(self) -> None:
        assert DURATIONS_PATH.exists(), (
            ".test_durations not found at repo root — "
            "regenerate with: pytest --store-durations -m 'not slow' tests/"
        )

    def test_durations_is_valid_json(self) -> None:
        data = json.loads(DURATIONS_PATH.read_text())
        assert isinstance(data, dict), ".test_durations should be a JSON object"

    def test_durations_has_entries(self) -> None:
        data = json.loads(DURATIONS_PATH.read_text())
        assert len(data) > 100, (
            f".test_durations has only {len(data)} entries — "
            "expected at least 100 for a meaningful shard split"
        )

    def test_durations_values_are_positive_floats(self) -> None:
        data = json.loads(DURATIONS_PATH.read_text())
        bad = {
            k: v for k, v in data.items() if not isinstance(v, (int, float)) or v < 0
        }
        assert (
            not bad
        ), f"Found non-positive or non-numeric durations: {list(bad.keys())[:5]}"

    def test_durations_keys_are_test_node_ids(self) -> None:
        """Keys should look like 'tests/path/file.py::Class::method'."""
        data = json.loads(DURATIONS_PATH.read_text())
        sample = list(data.keys())[:10]
        for key in sample:
            assert "::" in key, f"Duration key doesn't look like a test node ID: {key}"
            assert key.startswith(
                "tests/"
            ), f"Duration key should start with 'tests/': {key}"

    def test_durations_support_balanced_split(self) -> None:
        """Verify the baseline has enough data for a balanced 2-way split."""
        data = json.loads(DURATIONS_PATH.read_text())
        total = sum(data.values())
        assert (
            total > 10
        ), f"Total duration too low ({total:.1f}s) for meaningful sharding"

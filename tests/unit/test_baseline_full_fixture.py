import json
from pathlib import Path

import pytest


class TestBaselineFullFixture:
    """Test validation of baseline_full_expected.json fixture schema."""

    @pytest.fixture
    def fixture_path(self):
        """Path to the baseline_full_expected.json fixture."""
        return Path("data/fixtures/baseline_full_expected.json")

    @pytest.fixture
    def fixture_data(self, fixture_path):
        """Load and return the fixture data."""
        with open(fixture_path, 'r') as f:
            return json.load(f)

    def test_json_parses(self, fixture_path):
        """Test that the fixture file contains valid JSON."""
        with open(fixture_path, 'r') as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_schema_version_exists_and_correct(self, fixture_data):
        """Test that schema_version exists and equals expected value."""
        assert "schema_version" in fixture_data
        assert fixture_data["schema_version"] == 0

    def test_default_tolerance_exists_and_numeric(self, fixture_data):
        """Test that default_tolerance exists and is numeric."""
        assert "default_tolerance" in fixture_data
        assert isinstance(fixture_data["default_tolerance"], (int, float))

    def test_configs_is_dict(self, fixture_data):
        """Test that configs is a dictionary."""
        assert "configs" in fixture_data
        assert isinstance(fixture_data["configs"], dict)

    def test_config_keys_are_basenames(self, fixture_data):
        """Test that config keys are basenames (no path separators)."""
        configs = fixture_data["configs"]
        for config_key in configs.keys():
            assert "/" not in config_key, f"Config key '{config_key}' contains path separator"
            assert "\\" not in config_key, f"Config key '{config_key}' contains path separator"
            assert config_key.endswith(".yaml"), f"Config key '{config_key}' should end with .yaml"

    def test_config_entries_have_numeric_avg_tricks(self, fixture_data):
        """Test that each config entry has numeric avg_tricks."""
        configs = fixture_data["configs"]
        for config_key, config_data in configs.items():
            assert "avg_tricks" in config_data, f"Config '{config_key}' missing avg_tricks"
            assert isinstance(config_data["avg_tricks"], (int, float)), \
                f"Config '{config_key}' avg_tricks is not numeric: {config_data['avg_tricks']}"

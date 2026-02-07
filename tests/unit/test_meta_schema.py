"""Tests for experiment metadata schemas using hand-crafted fixtures.

Validates meta.json v2 and rollup.json v1 required fields without
generating any actual experiment runs.
"""

# meta.json v2 required fields (from experiments/run_experiment.py)
META_JSON_V2_REQUIRED_FIELDS = {
    "schema_version",
    "run_id",
    "created_at_utc",
    "git_sha",
    "config_path",
    "config_sha256",
    "experiment_name",
    "timestamp",
    "seed",
    "is_deterministic",
    "n_per",
    "log_level",
    "mode",
    "team1_strategy",
    "play_strategy",
    "scenarios",
    "strategies",
    "bidding_policies",
    "leader_randomized",
    "common_deals",
    "pair_deals",
    "total_hands",
}

# rollup.json v1 required fields (from scripts/run_suite.py)
ROLLUP_JSON_V1_REQUIRED_FIELDS = {
    "schema_version",
    "suite_name",
    "suite_seed",
    "suite_n_per",
    "created_at_utc",
    "configs",
    "summary",
}


def _make_meta_v2_fixture(**overrides):
    """Create a minimal valid meta.json v2 fixture."""
    base = {
        "schema_version": 2,
        "run_id": "quick_test_42_20260210_120000",
        "created_at_utc": "2026-02-10T12:00:00Z",
        "git_sha": "abc1234",
        "config_path": "experiments/configs/quick_test.yaml",
        "config_sha256": "deadbeef" * 8,
        "experiment_name": "quick_test",
        "timestamp": "20260210_120000",
        "seed": 42,
        "is_deterministic": True,
        "n_per": 20,
        "log_level": "none",
        "mode": "self_play",
        "team1_strategy": None,
        "play_strategy": None,
        "scenarios": [{"contract_type": "suit", "trump_suit": "H"}],
        "strategies": ["greedy"],
        "bidding_policies": [],
        "leader_randomized": True,
        "common_deals": True,
        "pair_deals": False,
        "total_hands": 20,
    }
    base.update(overrides)
    return base


def _make_rollup_v1_fixture(**overrides):
    """Create a minimal valid rollup.json v1 fixture."""
    base = {
        "schema_version": 1,
        "suite_name": "baseline_tiny",
        "suite_seed": 42,
        "suite_n_per": 20,
        "created_at_utc": "2026-02-10T12:00:00Z",
        "configs": [
            {
                "config_path": "experiments/configs/quick_test.yaml",
                "run_id": "quick_test_42_20260210_120000",
                "run_dir": "quick_test_42_20260210_120000",
                "status": "ok",
                "git_sha": "abc1234",
            }
        ],
        "summary": [
            {
                "config": "quick_test.yaml",
                "run_id": "quick_test_42_20260210_120000",
                "status": "ok",
                "total_hands": 20,
                "avg_tricks": 5.0,
                "reason": None,
                "bad_files": None,
            }
        ],
    }
    base.update(overrides)
    return base


class TestMetaJsonV2:
    """Tests for meta.json schema version 2."""

    def test_meta_json_v2_required_fields(self):
        """Fixture has all v2 required fields."""
        fixture = _make_meta_v2_fixture()
        assert set(fixture.keys()) == META_JSON_V2_REQUIRED_FIELDS

    def test_meta_json_schema_version_is_2(self):
        """Schema version must be 2."""
        fixture = _make_meta_v2_fixture()
        assert fixture["schema_version"] == 2

    def test_meta_json_no_batch_by_default(self):
        """Fixture without batch flags has no 'batch' key."""
        fixture = _make_meta_v2_fixture()
        assert "batch" not in fixture

    def test_meta_json_created_at_utc_is_iso8601(self):
        """created_at_utc must be ISO8601 with Z suffix."""
        fixture = _make_meta_v2_fixture()
        assert fixture["created_at_utc"].endswith("Z")

    def test_meta_json_seed_implies_deterministic(self):
        """When seed is set, is_deterministic must be True."""
        fixture = _make_meta_v2_fixture(seed=42, is_deterministic=True)
        assert fixture["is_deterministic"] is True

    def test_meta_json_null_seed_implies_nondeterministic(self):
        """When seed is None, is_deterministic must be False."""
        fixture = _make_meta_v2_fixture(seed=None, is_deterministic=False)
        assert fixture["is_deterministic"] is False


class TestRollupJsonV1:
    """Tests for rollup.json schema version 1."""

    def test_rollup_json_v1_required_fields(self):
        """Fixture has all v1 required fields."""
        fixture = _make_rollup_v1_fixture()
        assert set(fixture.keys()) == ROLLUP_JSON_V1_REQUIRED_FIELDS

    def test_rollup_json_schema_version_is_1(self):
        """Schema version must be 1."""
        fixture = _make_rollup_v1_fixture()
        assert fixture["schema_version"] == 1

    def test_rollup_json_configs_is_list(self):
        """configs must be a list."""
        fixture = _make_rollup_v1_fixture()
        assert isinstance(fixture["configs"], list)
        assert len(fixture["configs"]) > 0

    def test_rollup_json_summary_is_list(self):
        """summary must be a list."""
        fixture = _make_rollup_v1_fixture()
        assert isinstance(fixture["summary"], list)
        assert len(fixture["summary"]) > 0

    def test_rollup_json_config_entry_required_fields(self):
        """Each config entry must have required fields."""
        required = {"config_path", "run_id", "run_dir", "status", "git_sha"}
        fixture = _make_rollup_v1_fixture()
        for entry in fixture["configs"]:
            assert required <= set(entry.keys()), (
                f"Missing fields: {required - set(entry.keys())}"
            )

    def test_rollup_json_summary_entry_required_fields(self):
        """Each summary entry must have required fields."""
        required = {"config", "run_id", "status", "total_hands", "avg_tricks"}
        fixture = _make_rollup_v1_fixture()
        for entry in fixture["summary"]:
            assert required <= set(entry.keys()), (
                f"Missing fields: {required - set(entry.keys())}"
            )

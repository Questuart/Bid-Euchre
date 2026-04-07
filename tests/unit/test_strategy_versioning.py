"""Tests for strategy versioning and fingerprinting (#2519).

Verifies:
- All registered strategies and bidding policies have VERSION > "0.0.0"
- fingerprint() returns deterministic 8-char hex strings
- Different configurations produce different fingerprints
- collect_versions() produces the expected schema
- compare_versions() detects adds, removes, version changes, config changes
"""

import re

import pytest

from bid_euchre.experiments.config import (
    BIDDING_POLICY_REGISTRY,
    PLAY_STRATEGY_REGISTRY,
)
from bid_euchre.strategy import (
    AlwaysHighestLegalStrategy,
    AlwaysLowestLegalStrategy,
    BasicStrategy,
    GluttonIsolatedStrategy,
    GluttonStrategy,
    GreedyStrategy,
    RandomLegalStrategy,
)
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BiddingPolicy,
    StrictHellRaiser,
)
from bid_euchre.strategy.versioning import collect_versions, compare_versions

# ── Item 3: VERSION constants ──────────────────────────────────────────


class TestVersionConstants:
    """Every registered strategy and bidding policy has a non-default VERSION."""

    def test_strategy_base_has_version(self):
        assert hasattr(Strategy, "VERSION")
        assert Strategy.VERSION == "0.0.0"

    def test_bidding_policy_base_has_version(self):
        assert hasattr(BiddingPolicy, "VERSION")
        assert BiddingPolicy.VERSION == "0.0.0"

    @pytest.mark.parametrize(
        "cls",
        [
            BasicStrategy,
            RandomLegalStrategy,
            AlwaysLowestLegalStrategy,
            AlwaysHighestLegalStrategy,
            GreedyStrategy,
            GluttonStrategy,
            GluttonIsolatedStrategy,
        ],
    )
    def test_play_strategy_version_set(self, cls):
        """Play strategies must have VERSION > '0.0.0'."""
        assert hasattr(cls, "VERSION")
        assert cls.VERSION != "0.0.0", f"{cls.__name__}.VERSION is still default"
        # Validate semver format (relaxed: MAJOR.MINOR.PATCH)
        assert re.match(
            r"^\d+\.\d+\.\d+$", cls.VERSION
        ), f"{cls.__name__}.VERSION = {cls.VERSION!r} is not valid semver"

    @pytest.mark.parametrize(
        "name,cls",
        [
            (name, cls)
            for name, cls in PLAY_STRATEGY_REGISTRY.items()
            # ArtifactGreedyStrategy needs artifact_path
            if name != "ArtifactGreedyStrategy"
        ],
    )
    def test_all_registered_play_strategies_versioned(self, name, cls):
        """Every class in PLAY_STRATEGY_REGISTRY must have VERSION set."""
        assert hasattr(cls, "VERSION"), f"{name} missing VERSION"
        assert cls.VERSION != "0.0.0", f"{name}.VERSION is still default '0.0.0'"

    @pytest.mark.parametrize(
        "name,cls",
        list(BIDDING_POLICY_REGISTRY.items()),
    )
    def test_all_registered_bidding_policies_versioned(self, name, cls):
        """Every class in BIDDING_POLICY_REGISTRY must have VERSION set."""
        assert hasattr(cls, "VERSION"), f"{name} missing VERSION"
        assert cls.VERSION != "0.0.0", f"{name}.VERSION is still default '0.0.0'"

    def test_glutton_shares_module_version(self):
        """GluttonStrategy and GluttonIsolatedStrategy share the same VERSION."""
        assert GluttonStrategy.VERSION == GluttonIsolatedStrategy.VERSION


# ── Item 4: fingerprint() method ───────────────────────────────────────


class TestFingerprint:
    """fingerprint() returns deterministic, distinguishing hex digests."""

    def test_strategy_fingerprint_format(self):
        s = BasicStrategy(name="test")
        fp = s.fingerprint()
        assert isinstance(fp, str)
        assert len(fp) == 8
        assert re.match(r"^[0-9a-f]{8}$", fp), f"Not hex: {fp}"

    def test_bidding_policy_fingerprint_format(self):
        b = AlwaysPassBidder(name="test")
        fp = b.fingerprint()
        assert isinstance(fp, str)
        assert len(fp) == 8
        assert re.match(r"^[0-9a-f]{8}$", fp), f"Not hex: {fp}"

    def test_fingerprint_deterministic(self):
        s1 = GluttonStrategy(name="g1")
        s2 = GluttonStrategy(name="g1")
        assert s1.fingerprint() == s2.fingerprint()

    def test_fingerprint_differs_by_name(self):
        s1 = GluttonStrategy(name="g1")
        s2 = GluttonStrategy(name="g2")
        assert s1.fingerprint() != s2.fingerprint()

    def test_fingerprint_differs_by_class(self):
        s1 = BasicStrategy(name="test")
        s2 = GreedyStrategy(name="test")
        assert s1.fingerprint() != s2.fingerprint()

    def test_glutton_fingerprint_differs_by_feature_flag(self):
        """Toggling cash_winners_on_lead changes the fingerprint."""
        s1 = GluttonStrategy(name="g", cash_winners_on_lead=False)
        s2 = GluttonStrategy(name="g", cash_winners_on_lead=True)
        assert s1.fingerprint() != s2.fingerprint()

    def test_isolated_fingerprint_differs_by_flags(self):
        """Toggling smart_leads changes the GluttonIsolated fingerprint."""
        s1 = GluttonIsolatedStrategy(name="iso", smart_leads=False)
        s2 = GluttonIsolatedStrategy(name="iso", smart_leads=True)
        assert s1.fingerprint() != s2.fingerprint()

    def test_bidding_fingerprint_deterministic(self):
        b1 = StrictHellRaiser(name="sh1")
        b2 = StrictHellRaiser(name="sh1")
        assert b1.fingerprint() == b2.fingerprint()


# ── Item 5: collect_versions() ─────────────────────────────────────────


class TestCollectVersions:
    """collect_versions() returns the expected dict schema."""

    def test_basic_schema(self):
        strategies = [GluttonStrategy(name="g1")]
        policies = [AlwaysPassBidder(name="ap")]
        result = collect_versions(strategies, policies)

        assert "play_strategies" in result
        assert "bidding_policies" in result
        assert len(result["play_strategies"]) == 1
        assert len(result["bidding_policies"]) == 1

        ps = result["play_strategies"][0]
        assert ps["name"] == "g1"
        assert ps["class"] == "GluttonStrategy"
        assert ps["version"] == GluttonStrategy.VERSION
        assert len(ps["fingerprint"]) == 8

        bp = result["bidding_policies"][0]
        assert bp["name"] == "ap"
        assert bp["class"] == "AlwaysPassBidder"
        assert bp["version"] == AlwaysPassBidder.VERSION
        assert len(bp["fingerprint"]) == 8

    def test_empty_lists(self):
        result = collect_versions([], [])
        assert result["play_strategies"] == []
        assert result["bidding_policies"] == []


# ── Item 6: compare_versions() ────────────────────────────────────────


class TestCompareVersions:
    """compare_versions() detects adds, removes, and changes."""

    def test_no_diff_on_identical(self):
        v = collect_versions(
            [GluttonStrategy(name="g")],
            [AlwaysPassBidder(name="ap")],
        )
        assert compare_versions(v, v) == []

    def test_added_strategy(self):
        old = collect_versions([], [])
        new = collect_versions([BasicStrategy(name="b")], [])
        diffs = compare_versions(old, new)
        assert len(diffs) == 1
        assert diffs[0]["change"] == "added"
        assert diffs[0]["name"] == "b"
        assert diffs[0]["category"] == "play_strategies"

    def test_removed_policy(self):
        old = collect_versions([], [AlwaysPassBidder(name="ap")])
        new = collect_versions([], [])
        diffs = compare_versions(old, new)
        assert len(diffs) == 1
        assert diffs[0]["change"] == "removed"
        assert diffs[0]["name"] == "ap"

    def test_config_changed(self):
        """Same version but different fingerprint = config_changed."""
        old = collect_versions(
            [GluttonStrategy(name="g", cash_winners_on_lead=False)], []
        )
        new = collect_versions(
            [GluttonStrategy(name="g", cash_winners_on_lead=True)], []
        )
        diffs = compare_versions(old, new)
        assert len(diffs) == 1
        assert diffs[0]["change"] == "config_changed"
        assert diffs[0]["old_fingerprint"] != diffs[0]["new_fingerprint"]

    def test_version_changed(self):
        """Simulate a version bump by patching the version dict."""
        old = collect_versions([BasicStrategy(name="b")], [])
        new = collect_versions([BasicStrategy(name="b")], [])
        # Manually change the version in the new dict to simulate a bump
        new["play_strategies"][0]["version"] = "2.0.0"
        new["play_strategies"][0]["fingerprint"] = "deadbeef"
        diffs = compare_versions(old, new)
        assert len(diffs) == 1
        assert diffs[0]["change"] == "version_changed"

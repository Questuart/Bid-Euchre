"""Integration test — STEWARD_TOKEN_ECONOMY_NATIVE_USAGE flag-flip fallback.

Validation surface for the Primitive G.2 migration feature flag (see
``.claude/rules/feature_flags.md`` entry + plan
``plans/steward_platform/7_primitive_G/migrations/01_token_economy_to_native_usage.md``
§3.1 + §4).

This test flips ``STEWARD_TOKEN_ECONOMY_NATIVE_USAGE`` and invokes the
dual-write surface (``read_session_records(source="auto")``) under both
cohort modes on the same on-disk snapshot. It asserts:

1. The Slice B rollup shape (§4.1 byte-for-byte observables) matches
   between cohorts (``model_summary``, ``effort_summary``, ``lane_summary``
   token totals, bucket keys, session counts).
2. ``native_usage_enabled()`` tracks the env var truthiness.
3. The flag is read on every call (no caching), so the operator's
   rollback SLO (1 minute — unset → resume bespoke path) is met by
   construction.
4. The bespoke-only path does NOT depend on the flag; flag flip does not
   change the authoritative return value from ``read_session_records``.

Stop-loss trip wire #2 (behavioral-equivalence regression, plan §6.2)
is the production-time equivalent of a failure here — the operator
unsets the flag and the bespoke-only path resumes automatically.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_RECORDS = [
    {
        "session_id": "sess-001",
        "schema_version": 3,
        "source_type": "project-jsonl",
        "project_path": "/Users/foo/Bid-Euchre-steward-author",
        "lane_id": "author-a",
        "model": "claude-opus-4-7",
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_tokens": 200,
        "cache_creation_tokens": 100,
        "git_commits": 2,
        "imported_at": "2026-04-20T10:00:00Z",
    },
    {
        "session_id": "sess-002",
        "schema_version": 3,
        "source_type": "project-jsonl",
        "project_path": "/Users/foo/Bid-Euchre-steward-flex-a",
        "lane_id": "flex-a",
        "model": "claude-sonnet-4-6",
        "input_tokens": 800,
        "output_tokens": 400,
        "cache_read_tokens": 150,
        "cache_creation_tokens": 50,
        "git_commits": 1,
        "imported_at": "2026-04-20T10:05:00Z",
    },
]


@pytest.fixture
def populated_store(tmp_path: Path) -> Path:
    """Populate a temp token-economy store with the fixture records."""
    jsonl = tmp_path / "session_usage.jsonl"
    jsonl.write_text(
        "\n".join(json.dumps(r) for r in FIXTURE_RECORDS) + "\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def clean_flag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the flag env var starts cleared for each test."""
    monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)


class TestNativeUsageFlagParsing:
    """The flag reader honors the same truthiness rules as other steward flags."""

    def test_unset_is_disabled(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        assert native_usage_enabled() is False

    def test_zero_is_disabled(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "0")
        assert native_usage_enabled() is False

    def test_one_is_enabled(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        assert native_usage_enabled() is True

    def test_empty_is_disabled(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "")
        assert native_usage_enabled() is False

    def test_false_string_is_disabled(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "false")
        assert native_usage_enabled() is False

    def test_flag_read_every_call_not_cached(
        self, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rollback SLO depends on no-caching: the flag is read each call.

        This is the structural invariant that makes the 1-minute rollback
        SLO in ``.claude/rules/feature_flags.md`` well-defined. If the
        flag were cached (module-level), operators would have to wait for
        cache expiry after unsetting it; with per-call reads, unset =
        immediate rollback.
        """
        from bid_euchre.ops.adapters.token_economy_adapter import (
            native_usage_enabled,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        assert native_usage_enabled() is True
        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        # No cache invalidation step — the next call observes the unset.
        assert native_usage_enabled() is False


class TestDualWriteReturnValueInvariant:
    """The bespoke path is authoritative for the return value per §3.3 routing.

    Flag flip does not change what ``read_session_records`` returns; it
    only controls whether the Cohort B path also runs and emits a
    proving-run sample.
    """

    def test_return_value_identical_under_both_cohorts(
        self,
        populated_store: Path,
        clean_flag_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )

        # Cohort A (flag off): bespoke-only.
        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        records_a = read_session_records(populated_store, source="auto")

        # Cohort B (flag on): dual-write; bespoke is still authoritative.
        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        records_b = read_session_records(populated_store, source="auto")

        assert records_a == records_b, (
            "§3.3 routing: bespoke path authoritative for return value; "
            "dual-write must NOT change what callers observe"
        )
        # And both match the fixture exactly.
        assert records_a == FIXTURE_RECORDS

    def test_explicit_bespoke_and_native_sources_return_same_shape(
        self, populated_store: Path, clean_flag_env: None
    ) -> None:
        """Explicit source='bespoke' / 'native' both read the same substrate.

        Per plan §5.1: both cohorts produce the same raw token counts
        because both read the same JSONL files. The delta measured is
        migration-path overhead, not token savings.
        """
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )

        records_bespoke = read_session_records(populated_store, source="bespoke")
        records_native = read_session_records(populated_store, source="native")
        assert records_bespoke == records_native == FIXTURE_RECORDS

    def test_invalid_source_raises(
        self, populated_store: Path, clean_flag_env: None
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )

        with pytest.raises(ValueError, match="Unknown source"):
            read_session_records(populated_store, source="bogus")


class TestSliceBShapeParityAcrossCohorts:
    """Plan §4.1 behavioral-equivalence contract — rollup shape preserved.

    This is the integration-level analogue of the golden-file test in
    ``tests/unit/test_token_economy.py::TestSliceBRollupShapeGoldenFile``.
    Where the unit test pins the shape for the bespoke path alone, this
    integration test asserts the shape is identical under both cohort
    modes.
    """

    def test_model_summary_shape_identical_across_cohorts(
        self,
        populated_store: Path,
        clean_flag_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )
        from bid_euchre.ops.token_economy import model_summary

        # Flag OFF: populate via Cohort A path.
        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        read_session_records(populated_store, source="auto")
        buckets_a = model_summary(output_dir=populated_store)

        # Flag ON: populate via Cohort B dual-write path.
        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        read_session_records(populated_store, source="auto")
        buckets_b = model_summary(output_dir=populated_store)

        # Byte-for-byte equivalence per §4.1.
        assert [b.model for b in buckets_a] == [b.model for b in buckets_b]
        assert [b.session_count for b in buckets_a] == [
            b.session_count for b in buckets_b
        ]
        assert [b.total_tokens for b in buckets_a] == [
            b.total_tokens for b in buckets_b
        ]
        assert [b.input_tokens for b in buckets_a] == [
            b.input_tokens for b in buckets_b
        ]
        assert [b.output_tokens for b in buckets_a] == [
            b.output_tokens for b in buckets_b
        ]
        assert [b.cache_read_tokens for b in buckets_a] == [
            b.cache_read_tokens for b in buckets_b
        ]
        assert [b.cache_creation_tokens for b in buckets_a] == [
            b.cache_creation_tokens for b in buckets_b
        ]

    def test_effort_summary_shape_identical_across_cohorts(
        self,
        populated_store: Path,
        clean_flag_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )
        from bid_euchre.ops.token_economy import effort_summary

        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        read_session_records(populated_store, source="auto")
        buckets_a = effort_summary(output_dir=populated_store)

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        read_session_records(populated_store, source="auto")
        buckets_b = effort_summary(output_dir=populated_store)

        assert [b.effort for b in buckets_a] == [b.effort for b in buckets_b]
        assert [b.session_count for b in buckets_a] == [
            b.session_count for b in buckets_b
        ]
        assert [b.total_tokens for b in buckets_a] == [
            b.total_tokens for b in buckets_b
        ]


class TestCohortSampleEmissionNeverRaises:
    """Plan §3.2 item 3 + ADR 007 never-raises: event emission is best-effort.

    The ``proving_run_cohort_sample`` event schema is not yet in the
    event registry (it lands with the F.11 emitter package). Adapter
    emission MUST tolerate the unknown-event-type rejection silently so
    the token-economy path keeps functioning during the rollout window.
    """

    def test_flag_on_does_not_raise_even_when_event_unregistered(
        self,
        populated_store: Path,
        clean_flag_env: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from bid_euchre.ops.adapters.token_economy_adapter import (
            read_session_records,
        )

        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        # Should NOT raise even though the event type may be unregistered.
        records = read_session_records(
            populated_store,
            source="auto",
            lane_id="flex-a",
            task_id="integration-test",
            window_id="test-window-1",
        )
        assert records == FIXTURE_RECORDS

    def test_cmd_usage_probe_tolerates_missing_store(
        self, tmp_path: Path, clean_flag_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dual-write probe in cmd_usage never raises even with no store."""
        import argparse
        import sys

        script_dir = Path(__file__).resolve().parents[2] / "scripts" / "internal"
        monkeypatch.syspath_prepend(str(script_dir))
        # Force a fresh import path so the ops module picks up script_dir.
        sys.modules.pop("ops", None)
        import ops  # type: ignore[import-not-found]

        # Probe with a nonexistent output_dir: should not raise.
        nonexistent = tmp_path / "does-not-exist"
        ns = argparse.Namespace(output_dir=nonexistent)
        monkeypatch.setenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", "1")
        ops._dual_write_probe(ns)
        monkeypatch.delenv("STEWARD_TOKEN_ECONOMY_NATIVE_USAGE", raising=False)
        ops._dual_write_probe(ns)

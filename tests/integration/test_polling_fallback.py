"""Polling-fallback feature-flag smoke (Primitive A / Primitive E handoff).

Exercises the ``STEWARD_EVENTS_POLLING_FALLBACK`` feature flag documented
in ``.claude/rules/feature_flags.md``. Phase 0 scope is **flag-shape
only** — the live polling consumer lives under Primitive E and ships in
a later packet. This stub locks in:

1. The flag is registered in the authoritative registry file.
2. The flag honors ``"0"`` / ``"1"`` parsing conventions.
3. Event-driven emission is **unaffected** by the flag (it gates
   downstream consumers, not upstream emitters).

When Primitive E lands the live consumer, this file grows a real
rollback-latency assertion (flip flag → poll restarts within 60s).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from bid_euchre.ops.event_writer import list_active_files
from bid_euchre.ops.events import emit

_FLAG_NAME = "STEWARD_EVENTS_POLLING_FALLBACK"
_REGISTRY_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "rules" / "feature_flags.md"
)


class TestPollingFallbackFlagShape:
    """Lock the flag's registry contract (Phase 0 stub)."""

    def test_flag_is_documented_in_registry(self) -> None:
        """feature_flags.md must carry an entry for the flag."""
        assert (
            _REGISTRY_PATH.exists()
        ), f"Expected feature-flag registry at {_REGISTRY_PATH}"
        content = _REGISTRY_PATH.read_text()
        assert (
            f"`{_FLAG_NAME}`" in content
        ), f"Flag {_FLAG_NAME} not documented in {_REGISTRY_PATH}"
        # Operator-visible contract fields must all appear.
        for required_section in ("Default", "Trigger", "Expected effect", "Rollback"):
            assert (
                required_section in content
            ), f"Registry entry missing section: {required_section}"

    def test_flag_parse_sanity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Standard shell-truthy conventions: ``"1"`` and ``"0"`` are both sane values."""
        for value in ("0", "1"):
            monkeypatch.setenv(_FLAG_NAME, value)
            # Stand-in parse: the live consumer will use a helper. For now,
            # lock the convention we've documented so tests catch divergence.
            parsed = os.environ.get(_FLAG_NAME) == "1"
            if value == "1":
                assert parsed is True
            else:
                assert parsed is False


class TestEmissionUnaffectedByFlag:
    """Upstream emission is orthogonal to the downstream polling flag."""

    @pytest.fixture()
    def event_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        log_dir = tmp_path / "events"
        monkeypatch.setenv("STEWARD_EVENTS_LOG_DIR", str(log_dir))
        return log_dir

    def test_emission_writes_jsonl_when_flag_off(
        self, event_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_FLAG_NAME, "0")
        emit(
            "task_started",
            packet_id="off",
            dispatched_by="orchestrator",
            priority="medium",
            domain="platform",
            lane_id="author-a",
        )
        files = list_active_files(event_env)
        assert len(files) == 1
        assert "off" in files[0].read_text()

    def test_emission_writes_jsonl_when_flag_on(
        self, event_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(_FLAG_NAME, "1")
        emit(
            "task_started",
            packet_id="on",
            dispatched_by="orchestrator",
            priority="medium",
            domain="platform",
            lane_id="author-a",
        )
        files = list_active_files(event_env)
        assert len(files) == 1
        record = json.loads(files[0].read_text().splitlines()[0])
        assert record["packet_id"] == "on"
        # Upstream emission path is unaffected — the flag gates downstream
        # consumers only.


# ---------------------------------------------------------------------------
# Primitive E coordination point — expand when the live consumer lands.
# ---------------------------------------------------------------------------
#
# When Primitive E migrates active-triage from polling to event-driven
# routing (see plans/steward_platform/verification_contract/map.md row
# A.5), add a TestPollingFallbackLiveConsumer class that:
#
#   1. Starts the event-driven consumer in a subprocess / thread.
#   2. Emits a synthetic triage-triggering event.
#   3. Asserts the consumer picks it up within event-driven latency target.
#   4. Flips STEWARD_EVENTS_POLLING_FALLBACK=1.
#   5. Asserts the polling fallback restarts within the 60s SLO.
#   6. Flips it off and asserts the event-driven path resumes.
#
# The <1min wall-clock rollback SLO is the Pattern 7 obligation this
# test will discharge — tracked in feature_flags.md.

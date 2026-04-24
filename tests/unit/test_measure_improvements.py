"""Unit tests for ``scripts/internal/measure_improvements.py`` (B.12 Phase 0).

Covers the five assertions listed in shaping §9.5, plus structural
invariants on the markdown report. Tests inject events in memory via
the ``_events`` parameter on ``run()`` so no file I/O touches
``.claude/runtime/events/``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from scripts.internal import measure_improvements as mi

# ---------------------------------------------------------------------------
# Fixture helpers — synthetic event builders
# ---------------------------------------------------------------------------


def _event(
    event_type: str,
    *,
    timestamp: datetime,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal event dict matching the Primitive A schema."""
    return {
        "event_type": event_type,
        "timestamp": timestamp.isoformat(),
        "source": "test",
        "lane_id": "flex-a",
        "payload": payload or {},
    }


def _lifecycle(
    packet_id: str,
    *,
    started: datetime,
    terminator: str = "task_completed",
    outcome: str | None = "completed",
    review_rounds: int | None = None,
) -> list[dict[str, Any]]:
    """Return a `task_started` + terminator pair for one packet."""
    finished = started + timedelta(minutes=10)
    start_payload = {"packet_id": packet_id}
    events = [_event("task_started", timestamp=started, payload=start_payload)]
    term_payload: dict[str, Any] = {"packet_id": packet_id}
    if outcome is not None:
        term_payload["outcome"] = outcome
    if review_rounds is not None:
        term_payload["review_rounds"] = review_rounds
    events.append(_event(terminator, timestamp=finished, payload=term_payload))
    return events


# ---------------------------------------------------------------------------
# Assertion 1 — retry_rate over 100 synthetic task_started/task_completed events
# ---------------------------------------------------------------------------


class TestRetryRate:
    """§9.5 assertion 1: retry_rate computes correctly on a seeded fixture."""

    def test_zero_retries_is_zero_rate(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        for i in range(100):
            events.extend(_lifecycle(f"pkt{i}", started=base + timedelta(minutes=i)))
        rate, obs = mi.compute_retry_rate(events)
        assert rate == 0.0
        assert obs == {"started": 100, "retried": 0}

    def test_known_retry_count(self) -> None:
        """Seed 100 packets: 75 clean completions + 25 retries. Expect 0.25."""
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        for i in range(75):
            events.extend(_lifecycle(f"ok{i}", started=base + timedelta(minutes=i)))
        for i in range(15):
            events.extend(
                _lifecycle(
                    f"fail{i}",
                    started=base + timedelta(hours=1, minutes=i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        for i in range(10):
            events.extend(
                _lifecycle(
                    f"block{i}",
                    started=base + timedelta(hours=2, minutes=i),
                    terminator="task_blocked",
                    outcome=None,
                )
            )
        rate, obs = mi.compute_retry_rate(events)
        assert obs == {"started": 100, "retried": 25}
        assert rate == pytest.approx(0.25)

    def test_reworked_outcome_counts_as_retry(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        events.extend(_lifecycle("a", started=base, outcome="completed"))
        events.extend(
            _lifecycle("b", started=base + timedelta(minutes=5), outcome="reworked")
        )
        rate, obs = mi.compute_retry_rate(events)
        assert obs == {"started": 2, "retried": 1}
        assert rate == pytest.approx(0.5)

    def test_empty_event_list_is_zero_rate(self) -> None:
        rate, obs = mi.compute_retry_rate([])
        assert rate == 0.0
        assert obs == {"started": 0, "retried": 0}


# ---------------------------------------------------------------------------
# Assertion 2 — routing_correction_rate over 50 synthetic dispatch events
# ---------------------------------------------------------------------------


class TestRoutingCorrectionRate:
    """§9.5 assertion 2: routing_correction_rate computes correctly."""

    def test_known_override_fraction(self) -> None:
        """Seed 50 dispatch_recommendation events; 20 have override=True."""
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        for i in range(50):
            events.append(
                _event(
                    "dispatch_recommendation",
                    timestamp=base + timedelta(minutes=i),
                    payload={
                        "packet_id": f"p{i}",
                        "override": i < 20,  # first 20 events are overrides
                    },
                )
            )
        rate, obs = mi.compute_routing_correction_rate(events)
        assert obs == {"recommendations": 50, "overrides": 20}
        assert rate == pytest.approx(0.4)

    def test_no_overrides_is_zero(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events = [
            _event(
                "dispatch_recommendation",
                timestamp=base + timedelta(minutes=i),
                payload={"packet_id": f"p{i}"},
            )
            for i in range(10)
        ]
        rate, obs = mi.compute_routing_correction_rate(events)
        assert rate == 0.0
        assert obs == {"recommendations": 10, "overrides": 0}

    def test_no_recommendations_is_zero(self) -> None:
        rate, obs = mi.compute_routing_correction_rate([])
        assert rate == 0.0
        assert obs == {"recommendations": 0, "overrides": 0}


# ---------------------------------------------------------------------------
# Assertion 3 — repeat-probe threshold (≥3 over 14 days)
# ---------------------------------------------------------------------------


class TestRepeatProbeThreshold:
    """§9.5 assertion 3: probe flag fires at the N=3 threshold."""

    def test_five_identical_signatures_flags_one_probe(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        for i in range(5):
            events.append(
                _event(
                    "dispatch_recommendation",
                    timestamp=base + timedelta(days=i * 2),  # spread over ~10 days
                    payload={
                        "packet_id": f"p{i}",
                        "packet_title": f"Fix #{1000 + i} in scoring.py",
                        "archetype": "author",
                        "task_type": "fix",
                        "resolved_effort_hint": "xhigh",
                    },
                )
            )
        probes = mi.compute_repeat_probes(events)
        assert len(probes) == 1
        probe = probes[0]
        assert probe.count == 5
        assert probe.signature == "fix scoring.py"
        assert probe.archetype == "author"
        assert probe.task_type == "fix"
        assert probe.effort == "xhigh"

    def test_below_threshold_no_probes(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events = [
            _event(
                "dispatch_recommendation",
                timestamp=base + timedelta(days=i),
                payload={
                    "packet_id": f"p{i}",
                    "packet_title": "Fix scoring edge case",
                    "archetype": "author",
                    "task_type": "fix",
                    "resolved_effort_hint": "xhigh",
                },
            )
            for i in range(2)
        ]
        probes = mi.compute_repeat_probes(events)
        assert probes == []

    def test_exactly_threshold_fires(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events = [
            _event(
                "dispatch_recommendation",
                timestamp=base + timedelta(hours=i),
                payload={
                    "packet_id": f"p{i}",
                    "packet_title": "Implement new feature",
                    "archetype": "author",
                    "task_type": "implementation",
                    "resolved_effort_hint": "xhigh",
                },
            )
            for i in range(mi.REPEAT_PROBE_MIN_OCCURRENCES)
        ]
        probes = mi.compute_repeat_probes(events)
        assert len(probes) == 1
        assert probes[0].count == mi.REPEAT_PROBE_MIN_OCCURRENCES

    def test_distinct_signatures_do_not_collapse(self) -> None:
        """Three different archetypes with the same title still produce 3 signatures."""
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        for archetype in ("author", "flex", "analyst"):
            for i in range(3):
                events.append(
                    _event(
                        "dispatch_recommendation",
                        timestamp=base + timedelta(hours=i),
                        payload={
                            "packet_id": f"{archetype}{i}",
                            "packet_title": "Refactor scoring module",
                            "archetype": archetype,
                            "task_type": "refactor",
                            "resolved_effort_hint": "xhigh",
                        },
                    )
                )
        probes = mi.compute_repeat_probes(events)
        assert len(probes) == 3
        assert {p.archetype for p in probes} == {"author", "flex", "analyst"}
        assert all(p.count == 3 for p in probes)


# ---------------------------------------------------------------------------
# Assertion 4 — tokenization normalizes packet-specific identifiers
# ---------------------------------------------------------------------------


class TestTokenization:
    """§9.5 assertion 4: three titles differing only in identifiers tokenize identically."""

    def test_three_titles_same_signature(self) -> None:
        sigs = {
            mi.tokenize_title("Fix #1234 in foo.py"),
            mi.tokenize_title("Fix #5678 in foo.py"),
            mi.tokenize_title("Fix issue in foo.py"),
        }
        assert sigs == {"fix foo.py"}

    def test_strips_hex_packet_ids(self) -> None:
        assert mi.tokenize_title("Retry packet a1b2c3d4e5f6") == "retry"
        assert mi.tokenize_title("Retry packet DEADBEEFCAFE") == "retry"

    def test_strips_file_path_prefix(self) -> None:
        assert mi.tokenize_title("Edit src/bid_euchre/scoring.py") == "edit scoring.py"
        assert (
            mi.tokenize_title("Refactor scripts/internal/thing.py")
            == "refactor thing.py"
        )

    def test_strips_stopwords(self) -> None:
        assert mi.tokenize_title("The fix for a bug") == "fix bug"

    def test_collapses_whitespace(self) -> None:
        assert mi.tokenize_title("fix   scoring   bug") == "fix scoring bug"

    def test_three_titles_cluster_into_one_probe(self) -> None:
        """End-to-end: same tokenization produces a single repeat probe."""
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        titles = [
            "Fix #1234 in foo.py",
            "Fix #5678 in foo.py",
            "Fix issue in foo.py",
        ]
        events = [
            _event(
                "dispatch_recommendation",
                timestamp=base + timedelta(hours=i),
                payload={
                    "packet_id": f"p{i}",
                    "packet_title": titles[i],
                    "archetype": "author",
                    "task_type": "fix",
                    "resolved_effort_hint": "xhigh",
                },
            )
            for i in range(3)
        ]
        probes = mi.compute_repeat_probes(events)
        assert len(probes) == 1
        assert probes[0].signature == "fix foo.py"
        assert probes[0].count == 3


# ---------------------------------------------------------------------------
# Assertion 5 — net-positive / net-negative / flat classification
# ---------------------------------------------------------------------------


class TestMechanismDeltaClassification:
    """§9.5 assertion 5: before/after retry-rate changes are classified correctly."""

    @staticmethod
    def _make_change(ts: datetime, *, revert: bool = False) -> mi.MechanismChange:
        return mi.MechanismChange(
            commit_sha="abcdef1234567890",
            summary="Revert foo" if revert else "feat: tweak policy",
            timestamp=ts,
            surfaces=(".claude/rules/prompt_policy/",),
            is_revert=revert,
        )

    def test_net_positive_when_retry_drops(self) -> None:
        """Retry rate 50% before, 10% after → net-positive."""
        change_ts = datetime(2026, 4, 15, tzinfo=timezone.utc)
        change = self._make_change(change_ts)
        pre_base = change_ts - timedelta(days=7)
        post_base = change_ts + timedelta(minutes=1)
        events: list[dict[str, Any]] = []
        # Before: 10 packets, 5 retries (50%).
        for i in range(5):
            events.extend(
                _lifecycle(f"pre_ok{i}", started=pre_base + timedelta(minutes=i))
            )
        for i in range(5):
            events.extend(
                _lifecycle(
                    f"pre_bad{i}",
                    started=pre_base + timedelta(minutes=30 + i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        # After: 10 packets, 1 retry (10%).
        for i in range(9):
            events.extend(
                _lifecycle(f"post_ok{i}", started=post_base + timedelta(minutes=i))
            )
        events.extend(
            _lifecycle(
                "post_bad",
                started=post_base + timedelta(minutes=30),
                terminator="task_failed",
                outcome=None,
            )
        )
        deltas = mi.classify_mechanism_deltas([change], events, window_days=14)
        assert len(deltas) == 1
        d = deltas[0]
        assert d.before_retry_rate == pytest.approx(0.5)
        assert d.after_retry_rate == pytest.approx(0.1)
        assert d.net_sign == "net-positive"

    def test_net_negative_when_retry_rises(self) -> None:
        change_ts = datetime(2026, 4, 15, tzinfo=timezone.utc)
        change = self._make_change(change_ts)
        pre_base = change_ts - timedelta(days=7)
        post_base = change_ts + timedelta(minutes=1)
        events: list[dict[str, Any]] = []
        # Before: 10 packets, 1 retry (10%).
        for i in range(9):
            events.extend(
                _lifecycle(f"pre_ok{i}", started=pre_base + timedelta(minutes=i))
            )
        events.extend(
            _lifecycle(
                "pre_bad",
                started=pre_base + timedelta(minutes=30),
                terminator="task_failed",
                outcome=None,
            )
        )
        # After: 10 packets, 5 retries (50%).
        for i in range(5):
            events.extend(
                _lifecycle(f"post_ok{i}", started=post_base + timedelta(minutes=i))
            )
        for i in range(5):
            events.extend(
                _lifecycle(
                    f"post_bad{i}",
                    started=post_base + timedelta(minutes=30 + i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        deltas = mi.classify_mechanism_deltas([change], events, window_days=14)
        assert deltas[0].net_sign == "net-negative"
        assert deltas[0].before_retry_rate == pytest.approx(0.1)
        assert deltas[0].after_retry_rate == pytest.approx(0.5)

    def test_flat_when_rates_match(self) -> None:
        change_ts = datetime(2026, 4, 15, tzinfo=timezone.utc)
        change = self._make_change(change_ts)
        deltas = mi.classify_mechanism_deltas([change], [], window_days=14)
        assert deltas[0].net_sign == "flat"
        assert deltas[0].before_retry_rate == 0.0
        assert deltas[0].after_retry_rate == 0.0


# ---------------------------------------------------------------------------
# author_rework_rate and skill_promotion_usefulness — secondary metric coverage
# ---------------------------------------------------------------------------


class TestAuthorReworkRate:
    def test_review_rounds_gt_1_counts_as_rework(self) -> None:
        base = datetime(2026, 4, 10, tzinfo=timezone.utc)
        events = [
            _event(
                "task_completed",
                timestamp=base,
                payload={"packet_id": "a", "review_rounds": 1},
            ),
            _event(
                "task_completed",
                timestamp=base + timedelta(minutes=1),
                payload={"packet_id": "b", "review_rounds": 3},
            ),
            _event(
                "task_completed",
                timestamp=base + timedelta(minutes=2),
                payload={"packet_id": "c", "rework": True},
            ),
            _event(
                "task_completed",
                timestamp=base + timedelta(minutes=3),
                payload={"packet_id": "d", "outcome": "reworked"},
            ),
        ]
        rate, obs = mi.compute_author_rework_rate(events)
        assert obs == {"completed": 4, "reworked": 3}
        assert rate == pytest.approx(0.75)

    def test_no_completions_is_zero(self) -> None:
        rate, obs = mi.compute_author_rework_rate([])
        assert rate == 0.0
        assert obs == {"completed": 0, "reworked": 0}


class TestSkillPromotionUsefulness:
    def test_pre_high_post_low_is_positive(self) -> None:
        """Retry rate drops after promotion → positive usefulness."""
        promo_ts = datetime(2026, 4, 15, tzinfo=timezone.utc)
        pre_base = promo_ts - timedelta(days=7)
        post_base = promo_ts + timedelta(hours=1)
        events: list[dict[str, Any]] = [
            _event("skill_promoted", timestamp=promo_ts, payload={"skill": "foo"})
        ]
        # Pre: 10 packets, 5 retries.
        for i in range(5):
            events.extend(
                _lifecycle(f"pre_ok{i}", started=pre_base + timedelta(minutes=i))
            )
        for i in range(5):
            events.extend(
                _lifecycle(
                    f"pre_bad{i}",
                    started=pre_base + timedelta(minutes=30 + i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        # Post: 10 packets, 1 retry.
        for i in range(9):
            events.extend(
                _lifecycle(f"post_ok{i}", started=post_base + timedelta(minutes=i))
            )
        events.extend(
            _lifecycle(
                "post_bad",
                started=post_base + timedelta(minutes=30),
                terminator="task_failed",
                outcome=None,
            )
        )
        usefulness, obs = mi.compute_skill_promotion_usefulness(events, window_days=14)
        assert obs == {"promotions": 1, "comparable": 1}
        assert usefulness == pytest.approx(0.4)  # 0.5 pre - 0.1 post

    def test_no_promotions_is_zero(self) -> None:
        usefulness, obs = mi.compute_skill_promotion_usefulness([], window_days=14)
        assert usefulness == 0.0
        assert obs == {"promotions": 0}


# ---------------------------------------------------------------------------
# End-to-end: run() writes a markdown artifact containing all sections
# ---------------------------------------------------------------------------


class TestRunEndToEnd:
    """run() should produce an artifact file with the expected structure."""

    def test_run_writes_artifact_with_all_sections(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 24, tzinfo=timezone.utc)
        events: list[dict[str, Any]] = []
        # Current window: 10 packets, 2 retries (20%).
        cur_base = now - timedelta(days=3)
        for i in range(8):
            events.extend(
                _lifecycle(f"cur_ok{i}", started=cur_base + timedelta(minutes=i))
            )
        for i in range(2):
            events.extend(
                _lifecycle(
                    f"cur_fail{i}",
                    started=cur_base + timedelta(minutes=30 + i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        # Prior window: 10 packets, 5 retries (50%).
        prior_base = now - timedelta(days=20)
        for i in range(5):
            events.extend(
                _lifecycle(f"prior_ok{i}", started=prior_base + timedelta(minutes=i))
            )
        for i in range(5):
            events.extend(
                _lifecycle(
                    f"prior_fail{i}",
                    started=prior_base + timedelta(minutes=30 + i),
                    terminator="task_failed",
                    outcome=None,
                )
            )
        # Three dispatch_recommendation events with identical signature in current window.
        for i in range(3):
            events.append(
                _event(
                    "dispatch_recommendation",
                    timestamp=cur_base + timedelta(hours=i),
                    payload={
                        "packet_id": f"d{i}",
                        "packet_title": "Refactor scoring module",
                        "archetype": "author",
                        "task_type": "refactor",
                        "resolved_effort_hint": "xhigh",
                    },
                )
            )
        out = mi.run(
            now=now,
            window_days=14,
            output_dir=tmp_path,
            repo_root=tmp_path,  # stops git log from reading real repo
            _events=events,
            emit_event=False,
        )
        text = out.read_text(encoding="utf-8")
        # Header & windows
        assert "Improvement Metrics" in text
        assert "Metric deltas" in text
        # Five metric rows present
        assert "retry_rate" in text
        assert "author_rework_rate" in text
        assert "routing_correction_rate" in text
        assert "prompt_policy_rollback_rate" in text
        assert "skill_promotion_usefulness" in text
        # Repeat-probe section fired
        assert "Repeat-task probes" in text
        assert "refactor scoring module" in text
        # Mechanism section present (may be empty in tmp repo — just assert header)
        assert "Mechanism-change deltas" in text
        # Current retry 20%, prior 50% — delta -30pp
        assert "20.0%" in text
        assert "50.0%" in text

    def test_run_returns_output_path(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 24, tzinfo=timezone.utc)
        out = mi.run(
            now=now,
            window_days=14,
            output_dir=tmp_path,
            repo_root=tmp_path,
            _events=[],
            emit_event=False,
        )
        assert out == tmp_path / "2026-04-24_improvement_metrics.md"
        assert out.exists()

    def test_run_with_no_events_still_writes_report(self, tmp_path: Path) -> None:
        now = datetime(2026, 4, 24, tzinfo=timezone.utc)
        out = mi.run(
            now=now,
            window_days=14,
            output_dir=tmp_path,
            repo_root=tmp_path,
            _events=[],
            emit_event=False,
        )
        text = out.read_text(encoding="utf-8")
        # With no events, retry/rework/routing are zero and no probes fire.
        assert "retry_started` = 0" in text
        assert "No task-class signatures recur" in text
        assert "No mechanism-surface commits" in text


# ---------------------------------------------------------------------------
# Event emission — best-effort guard
# ---------------------------------------------------------------------------


class TestEmission:
    def test_emit_ignores_unregistered_event_type(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ValueError from append_event (unregistered type) must not raise."""

        def _raise(*_args: Any, **_kwargs: Any) -> None:
            raise ValueError("event type not registered")

        # Patch the symbol inside bid_euchre.ops.events so the local import
        # inside emit_improvement_metrics_event picks up the faulty stub.
        from bid_euchre.ops import events as events_mod

        monkeypatch.setattr(events_mod, "append_event", _raise)
        current = mi.WindowMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
        prior = mi.WindowMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
        # Should silently swallow the ValueError.
        mi.emit_improvement_metrics_event(
            current=current,
            prior=prior,
            output_path=Path("/tmp/does-not-matter.md"),
        )

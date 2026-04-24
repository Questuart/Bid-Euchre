"""Scaffold contract tests for `scripts/internal/triage_cli.py`.

Primitive E Phase 0 Packet E1 ships `triage_cli.py` as a **scaffold** — the
live GitHub-interacting runtime is blocked on Primitive A Packet 3 (event
schema + dispatcher). These tests pin the scaffold's public contract so
downstream callers can wire to a stable surface without re-shaping.

Covered invariants:
- `SIGNAL_CLASSES` and `PRIORITIES` vocabularies match the shaping doc.
- `TriageInput` dataclass has the expected fields and is frozen.
- `file_or_recur(...)` raises `TriageRuntimeUnavailable` (a subclass of
  `NotImplementedError`) with a pointer to Primitive A.
- `is_valid_signal_class` / `is_valid_priority` helpers behave correctly.

The live-runtime tests land in a follow-up packet once Primitive A merges.
"""

from __future__ import annotations

import dataclasses

import pytest

from scripts.internal import triage_cli


def test_signal_classes_match_shaping_doc() -> None:
    """Five signal classes enumerated in shaping §2 (and §4)."""
    assert triage_cli.SIGNAL_CLASSES == (
        "ci_red",
        "review_blocked",
        "stalled_lane",
        "orphan_worktree",
        "token_burn",
    )


def test_priorities_vocabulary() -> None:
    assert triage_cli.PRIORITIES == ("low", "normal", "high", "urgent")


def test_triage_input_is_frozen_dataclass() -> None:
    """TriageInput is immutable (frozen=True) and has the shaping-doc fields."""
    assert dataclasses.is_dataclass(triage_cli.TriageInput)
    fields = {f.name for f in dataclasses.fields(triage_cli.TriageInput)}
    assert fields == {
        "signal_class",
        "title_hint",
        "body_sections",
        "labels",
        "priority",
        "incident_fingerprint",
        "source_event_id",
        "extra_context",
    }

    # Verify frozen=True by attempting mutation
    instance = triage_cli.TriageInput(
        signal_class="ci_red",
        title_hint="fix: CI red",
        body_sections={"Context": "example"},
        labels=["fix:test"],
        priority="high",
        incident_fingerprint="abc123",
        source_event_id="evt-1",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.signal_class = "review_blocked"  # type: ignore[misc]


def test_triage_input_accepts_extra_context_default() -> None:
    """extra_context defaults to empty dict; does not require callers to pass."""
    instance = triage_cli.TriageInput(
        signal_class="stalled_lane",
        title_hint="lane stalled",
        body_sections={},
        labels=[],
        priority="low",
        incident_fingerprint="fp",
        source_event_id="eid",
    )
    assert instance.extra_context == {}


def test_file_or_recur_is_scaffold_not_runtime() -> None:
    """The scaffold must raise; a live implementation must ship with
    primitive-A-packet-3 unblocker evidence in the new tests.

    This lock is load-bearing: silently replacing the scaffold without
    proving primitive-A merge would drift the integration.
    """
    payload = triage_cli.TriageInput(
        signal_class="ci_red",
        title_hint="fix: CI red on main",
        body_sections={"Context": "example"},
        labels=["fix:test"],
        priority="high",
        incident_fingerprint="deterministic-hash",
        source_event_id="evt-1",
    )
    with pytest.raises(triage_cli.TriageRuntimeUnavailable) as excinfo:
        triage_cli.file_or_recur(payload)
    msg = str(excinfo.value)
    assert "Primitive A" in msg, "Scaffold error must cite Primitive A as unblocker"
    assert "ci_red" in msg, "Scaffold error must include payload signal_class"
    assert (
        "deterministic-hash" in msg
    ), "Scaffold error must include payload fingerprint for traceability"


def test_runtime_unavailable_is_notimplementederror() -> None:
    """Callers that catch NotImplementedError must still see the scaffold raise."""
    assert issubclass(triage_cli.TriageRuntimeUnavailable, NotImplementedError)


def test_is_valid_helpers() -> None:
    for sc in triage_cli.SIGNAL_CLASSES:
        assert triage_cli.is_valid_signal_class(sc)
    assert not triage_cli.is_valid_signal_class("unknown_class")

    for pr in triage_cli.PRIORITIES:
        assert triage_cli.is_valid_priority(pr)
    assert not triage_cli.is_valid_priority("URGENT")  # case-sensitive


def test_public_api_exports() -> None:
    """__all__ is the documented public surface — narrow leaks are an API change."""
    expected = {
        "PRIORITIES",
        "Priority",
        "SIGNAL_CLASSES",
        "SignalClass",
        "TriageInput",
        "TriageResult",
        "TriageRuntimeUnavailable",
        "file_or_recur",
        "is_valid_priority",
        "is_valid_signal_class",
    }
    assert set(triage_cli.__all__) == expected

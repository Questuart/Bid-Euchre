"""Unit tests for ``bid_euchre.ops.event_schema``.

Covers registry completeness, §9.7 first-class ID discipline, version
constants, and EventTypeSpec introspection helpers per Primitive A Phase 0
Readiness (shaping §2 + §6).
"""

from __future__ import annotations

import pytest

from bid_euchre.ops import event_schema as es

# ---------------------------------------------------------------------------
# Version + baseline
# ---------------------------------------------------------------------------


def test_schema_version_is_v1_0():
    """Phase 0 Readiness target per shaping §2.1."""
    assert es.SCHEMA_VERSION == "1.0"


def test_first_class_id_fields_has_nine_entries():
    """§9.7 first-class IDs per shaping §2.3."""
    assert len(es.FIRST_CLASS_ID_FIELDS) == 9
    assert set(es.FIRST_CLASS_ID_FIELDS) == {
        "project_id",
        "cell_id",
        "session_id",
        "task_id",
        "lane_id",
        "trace_id",
        "incident_fingerprint",
        "prompt_policy_version",
        "schema_version",
    }


def test_correlation_fields_has_four_entries():
    """ADR 007 adopted pattern per shaping §2.4."""
    assert len(es.CORRELATION_FIELDS) == 4
    assert set(es.CORRELATION_FIELDS) == {"seq", "pid", "timestamp_ns", "turn_id"}


def test_verbosity_tiers_enumerated():
    """Three tiers per ADR 007 / shaping §3.3."""
    assert set(es.VERBOSITY_TIERS) == {"minimal", "summary", "full"}


def test_baseline_fields_union_of_ids_and_correlation_and_event_type():
    """Baseline fields populated by dispatcher on every record."""
    expected = (
        set(es.FIRST_CLASS_ID_FIELDS) | set(es.CORRELATION_FIELDS) | {"event_type"}
    )
    assert set(es.BASELINE_FIELDS) == expected
    assert set(es.baseline_fields()) == expected


# ---------------------------------------------------------------------------
# EVENT_FIELD_REGISTRY completeness
# ---------------------------------------------------------------------------


def test_registry_has_at_least_35_event_types():
    """Shaping §2.2 total: 18 native/lifecycle/task + 4 canary + 4 archivist
    + 4 promotion + 3 rollback + 2 latency = 35 event types minimum."""
    assert len(es.EVENT_FIELD_REGISTRY) >= 35


def test_registry_includes_all_native_lifecycle_types():
    """All 15 native lifecycle hook events absorbed at v1.0 per §4.1."""
    for event_type in es.NATIVE_LIFECYCLE_EVENT_TYPES:
        assert (
            event_type in es.EVENT_FIELD_REGISTRY
        ), f"missing native lifecycle event type: {event_type}"


def test_registry_includes_all_steward_operational_classes():
    """≥4 steward operational classes required per Phase 0 Readiness (§6.2)."""
    # 7 classes declared in schema; Phase 0 requires ≥4.
    assert len(es.STEWARD_OPERATIONAL_CLASSES) >= 4
    for class_name, event_types in es.STEWARD_OPERATIONAL_CLASSES.items():
        assert len(event_types) >= 1, f"class {class_name} has no event types"
        for event_type in event_types:
            assert (
                event_type in es.EVENT_FIELD_REGISTRY
            ), f"class {class_name} references unregistered type {event_type}"


def test_registry_includes_canary_lifecycle_types():
    """H.0 canary types registered at v1.0 per §4.3 coordination."""
    canary_types = es.STEWARD_OPERATIONAL_CLASSES["canary_lifecycle"]
    assert len(canary_types) == 4
    for t in canary_types:
        assert es.is_known_event_type(t)


def test_registry_includes_worktree_types():
    """Primitive G coupling per shaping §4.3 — schema registers, G emits."""
    assert es.is_known_event_type("worktree_create")
    assert es.is_known_event_type("worktree_remove")


def test_all_event_type_specs_are_eventtype_spec_instances():
    """Every registry value must be an EventTypeSpec."""
    for event_type, spec in es.EVENT_FIELD_REGISTRY.items():
        assert isinstance(
            spec, es.EventTypeSpec
        ), f"{event_type} spec is {type(spec)!r}, not EventTypeSpec"


def test_all_verbosity_defaults_are_valid():
    """Every registered type has a valid verbosity_default."""
    for event_type, spec in es.EVENT_FIELD_REGISTRY.items():
        assert (
            spec.verbosity_default in es.VERBOSITY_TIERS
        ), f"{event_type} has invalid verbosity_default {spec.verbosity_default!r}"


def test_required_and_optional_fields_disjoint_per_event_type():
    """A field may be either required or optional, not both."""
    for event_type, spec in es.EVENT_FIELD_REGISTRY.items():
        overlap = set(spec.required_fields) & set(spec.optional_fields)
        assert (
            not overlap
        ), f"{event_type} has fields in both required and optional: {overlap}"


def test_no_event_type_uses_baseline_field_as_required_or_optional():
    """Registered slots must not collide with baseline fields — baseline
    is populated by the dispatcher, not by the caller."""
    baseline = set(es.BASELINE_FIELDS)
    for event_type, spec in es.EVENT_FIELD_REGISTRY.items():
        all_slots = set(spec.required_fields) | set(spec.optional_fields)
        collision = all_slots & baseline
        # `event_type` is a baseline key; it's fine for the string to
        # collide as a bare token, but not as a registered slot.
        assert not collision, f"{event_type} slot(s) collide with baseline: {collision}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_is_known_event_type_positive():
    assert es.is_known_event_type("task_started")
    assert es.is_known_event_type("pre_tool_use")
    assert es.is_known_event_type("canary_run_complete")


def test_is_known_event_type_negative():
    assert not es.is_known_event_type("bogus_event_type")
    assert not es.is_known_event_type("")
    assert not es.is_known_event_type("recap_summary")  # Phase 1 deferral per §4.6


def test_get_spec_returns_correct_spec():
    spec = es.get_spec("task_started")
    assert spec is not None
    assert isinstance(spec, es.EventTypeSpec)
    assert "packet_id" in spec.required_fields


def test_get_spec_unknown_returns_none():
    assert es.get_spec("definitely_not_registered") is None


def test_registered_types_sorted_and_complete():
    types = es.registered_types()
    assert len(types) == len(es.EVENT_FIELD_REGISTRY)
    assert list(types) == sorted(types)


def test_known_field_for_event_recognizes_required():
    assert es.known_field_for_event("task_started", "packet_id")
    assert es.known_field_for_event("task_started", "dispatched_by")


def test_known_field_for_event_recognizes_optional():
    assert es.known_field_for_event("task_started", "effort_hint")


def test_known_field_for_event_negative():
    assert not es.known_field_for_event("task_started", "bogus_field")
    assert not es.known_field_for_event("unknown_event", "any_field")


def test_eventtype_spec_known_field_helper():
    spec = es.EventTypeSpec(required_fields=("r1",), optional_fields=("o1",))
    assert spec.known_field("r1")
    assert spec.known_field("o1")
    assert not spec.known_field("other")


def test_eventtype_spec_is_frozen():
    spec = es.EventTypeSpec()
    with pytest.raises((AttributeError, Exception)):  # dataclass(frozen=True)
        spec.required_fields = ("x",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Phase 1 deferral guard — recap absorption is not in v1.0
# ---------------------------------------------------------------------------


def test_recap_absorption_is_not_in_v1_0():
    """Per shaping §4.6: recap absorption is Phase 1 work. Guard against
    accidental Phase 0 registration."""
    for event_type in es.EVENT_FIELD_REGISTRY:
        assert "recap" not in event_type.lower(), (
            f"recap event {event_type!r} is Phase 1 per §4.6 — must not "
            f"appear in v1.0 registry"
        )

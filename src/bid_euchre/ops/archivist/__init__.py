"""Archivist — Primitive D Phase 0 lessons + GC collectors.

See ``plans/steward_platform/4_primitive_D/shaping.md`` §4.1 and §4.2
for the design. The archivist collects lesson signals (lessons mode) and
GC proposals (gc mode, Phase 0 scaffold; activation is Phase 1) and
writes dated candidate markdown files under ``knowledge/_candidates/``.

Public surface:

- ``run_lessons`` — execute one lessons-mode run
- ``run_gc`` — execute one GC-mode run (Phase 0 scaffold)
- ``LessonsRunResult`` / ``GCRunResult`` — result dataclasses
- ``KBSnapshot`` / ``load_fake_kb_snapshot`` — GC test helpers
- ``emit_candidate_*`` — flag-gated Primitive A event emitters
"""

from __future__ import annotations

from .events import (
    EMISSION_ENV_VAR,
    EVENT_CANDIDATE_PROMOTED,
    EVENT_CANDIDATE_PROPOSED,
    EVENT_CANDIDATE_REJECTED,
    EVENT_GC_PROPOSED,
    emission_enabled,
    emit_candidate_promoted,
    emit_candidate_proposed,
    emit_candidate_rejected,
    emit_gc_proposed,
)
from .gc import (
    GC_CLASSES,
    GCProposal,
    GCRunResult,
    KBSnapshot,
    load_fake_kb_snapshot,
    run_gc,
)
from .lessons import (
    DEFAULT_CANDIDATES_DIR,
    LessonCandidate,
    LessonsRunResult,
    run_lessons,
)

__all__ = [
    "DEFAULT_CANDIDATES_DIR",
    "EMISSION_ENV_VAR",
    "EVENT_CANDIDATE_PROMOTED",
    "EVENT_CANDIDATE_PROPOSED",
    "EVENT_CANDIDATE_REJECTED",
    "EVENT_GC_PROPOSED",
    "GC_CLASSES",
    "GCProposal",
    "GCRunResult",
    "KBSnapshot",
    "LessonCandidate",
    "LessonsRunResult",
    "emission_enabled",
    "emit_candidate_promoted",
    "emit_candidate_proposed",
    "emit_candidate_rejected",
    "emit_gc_proposed",
    "load_fake_kb_snapshot",
    "run_gc",
    "run_lessons",
]

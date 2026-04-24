# Candidate: test_candidate (fixture)

> Fixture file for Primitive C rollback test (§4.7 of
> `plans/steward_platform/3_primitive_C/shaping.md`). Used by
> `scripts/internal/archivist.py --promote` to verify the forward +
> reverse (un-promotion) path produces matching events and returns
> NOTES.md to byte-identical pre-promotion state.
>
> **Fixture purpose only** — not real KB content. Do not promote this
> into live NOTES.md outside test runs.

## Candidate kind: lessons

### Fixture lesson — rollback round-trip proof

**Context:** Packet C-Exec integration validation (Primitive C Phase 0).

**Lesson:** A promotion followed by an un-promotion must leave NOTES.md
byte-identical to its pre-promotion state. The archivist's `--promote`
computes a short hash of the inserted entry and writes a
`_promoted/<date>_<class>_<hash>.md` audit-trail entry; `--unpromote`
removes both and emits `kb_artifact_unpromoted`.

**Source:** `plans/steward_platform/3_primitive_C/shaping.md` §4.7
rollback-test spec.

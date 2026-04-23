---
name: create-plan
description: Scaffold a new plan, sub-plan, or primitive-closeout artifact from the canonical template with a mandatory `## Verification Plan` section per Pattern 10 (§10.9 governing plan). Refuses to output a plan whose Verification Plan section is missing, empty, placeholder-filled (TBD/TODO/FIXME/XXX), or fails to cover every deliverable enumerated in the plan's Work section.
---

# /create-plan — Author a New Plan with Verification-Contract Enforcement

Create a new plan, sub-plan, or primitive-closeout markdown artifact from
the canonical template at `plans/_templates/` with Pattern 10 compliance
enforced at creation time. This is the **first** of seven defense-in-depth
enforcement surfaces for Pattern 10 — see
`plans/steward_platform/verification_contract/shaping.md` §3 for the full
catalog.

## Arguments

- `kind` (required) — one of:
  - `sub_plan` — sub-plan under a governing plan
  - `execution_plan` — bounded execution plan (per slice / per PR)
  - `primitive_closeout` — Phase 0 primitive closeout artifact
  - `session` — session-scoped plan at `plans/sessions/YYYY-MM-DD_<slug>.md`
- `path` (required) — destination path for the new plan

## When to Use

- You are about to author a new plan of any kind
- You are drafting a session-scoped plan for a standalone task
- You are scaffolding a primitive closeout and need the
  Readiness-rows-as-verification-surfaces structure

Do **not** use for: edits to existing plans (just edit the file); ad-hoc
scratch notes; PR bodies (use `.github/pull_request_template.md`).

## Workflow

### Phase 1 — Copy template + stamp header

1. Read the relevant template:
   - `plans/_templates/sub_plan.md`
   - `plans/_templates/execution_plan.md`
   - `plans/_templates/primitive_closeout.md`
2. Write the template to the destination `path`, replacing placeholder
   header fields (title, parent plan, date, owner).

### Phase 2 — Populate the `## Verification Plan` section

The `## Verification Plan` section is **mandatory** and must contain a
table with these columns:

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|

Every Work bullet in the plan body must have a matching row in this
section, OR be covered by a row in the canonical map at
`plans/steward_platform/verification_contract/map.md`.

**Deliverable-class → surface-class defaults:** see the Pattern 10 table
at §10.9 of `plans/steward_platform/governing_plan.md`.

### Phase 3 — Refusal logic (hard stop)

Before writing the file to disk, this skill must **refuse** with a
pointer to the template worked example when any of the following are
true:

1. `## Verification Plan` section is missing
2. `## Verification Plan` section is present but the table is empty
   (header row only)
3. Any row contains a placeholder token in the `Verification surface`
   column: `TBD`, `TODO`, `FIXME`, `XXX`
4. Any Work bullet in the plan body lacks a matching row in the
   Verification Plan table and lacks a row in
   `plans/steward_platform/verification_contract/map.md`

Refusal message format:

    /create-plan REFUSED: Pattern 10 (§10.9) requires a complete
    Verification Plan section. Missing: <list>. See the worked example
    in plans/_templates/sub_plan.md §Verification Plan.

### Phase 4 — Post-write validation

After writing the plan, run the lint to confirm the file is clean:

    uv run python scripts/internal/agent_readability_lint.py \
        check verification-contract <path>

Expected: exits 0 with no findings. If findings are present, the
refusal logic failed — file a bug.

## Gotchas

- This skill enforces Pattern 10 at **creation time**; the
  `review_driver.py` V1–V6 prechecks enforce it again at **PR time**.
  Both layers are defense-in-depth. Do not weaken this skill on the
  assumption that PR-time enforcement will catch the gap.
- Placeholder detection is **strict-existence / lenient-form**: any
  surface column that contains one of the placeholder tokens (even as
  a substring) is refused. Acceptable surface *forms* include relative
  paths, `path::test_name` forms, commands (`make check`), and
  review-artifact references.
- Session-scoped plans (`kind=session`) have the same Verification
  Plan obligation. A one-off bugfix session plan should still name its
  verification surface (typically a single `tests/unit/test_*.py::test_*`
  entry).

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §3.2(ii) —
  this skill's design specification
- `plans/steward_platform/verification_contract/shaping.md` §6 —
  template structure (worked examples)
- `plans/_templates/sub_plan.md` §Verification Plan — worked example
- `scripts/internal/agent_readability_lint.py` — run-against-existing
  verification surface (§3.2(iii))

## Status

**Stub (Packet 2b).** The refusal logic above is specified but the
automated execution path is a manual checklist for now — the author
reads the plan's Verification Plan section and verifies each refusal
condition by hand. A follow-up packet in Primitive H.0 will lift the
checklist into a codified skill-execution script. The specification
above is normative; the execution is manual until the follow-up lands.

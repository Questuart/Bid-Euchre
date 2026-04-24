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

### Phase 3 — Refusal logic (hard stop, codified in R1-R4)

Before writing the file to disk, this skill must **refuse** with a
pointer to the template worked example when any of R1-R4 fires. The
four conditions, ordered by detection, are:

| # | Condition | Refusal message fragment |
|---|---|---|
| **R1** | `## Verification Plan` section is missing | `Missing ``## Verification Plan`` section` |
| **R2** | Section present but table is empty (header row only) | `` `## Verification Plan` section is empty (header row only)`` |
| **R3** | Any row contains a placeholder token (`TBD`/`TODO`/`FIXME`/`XXX`) in the Verification surface column | `Row for deliverable ``<name>`` carries placeholder surface ``<val>`` ` |
| **R4** | Any Work bullet lacks a matching row (in this plan OR in `plans/steward_platform/verification_contract/map.md`) | `Work bullet §<N.M> has no Verification Plan row and no map.md coverage` |

**Refusal evaluation is automated.** Any lane (or the skill itself)
can verify the four conditions on a draft plan by invoking:

    uv run python scripts/internal/create_plan_refusal.py <path>

Exit code 0 = pass; exit code 2 = refuse (with the exact message
below on stderr). Do NOT write a plan whose refusal evaluator returns
2.

**Exact refusal message format (§4.4.2; emitted verbatim):**

```
/create-plan REFUSED: Pattern 10 (§10.9) requires a complete Verification Plan section.

Refusal reasons:
  R<N>: <fragment from the R1-R4 table>
  [additional R<N> lines if multiple conditions fire]

See the worked example in plans/_templates/sub_plan.md §Verification Plan.
See Pattern 10 table at §10.9 of plans/steward_platform/governing_plan.md for
deliverable-class → surface-class defaults.

No plan file was written. Fix the above and re-invoke /create-plan.
```

If the skill is scripted: exit code 2. If the skill is operator-invoked
interactively: the refusal message is displayed and no file is created.

### Phase 4 — Post-write validation

After writing the plan, re-run the refusal evaluator and the lint to
confirm the file is clean:

    uv run python scripts/internal/create_plan_refusal.py <path>
    uv run python scripts/internal/agent_readability_lint.py \
        check verification-contract <path>

Both must exit 0. If either returns a finding, the refusal logic
failed — file a bug.

### Acceptance command (§4.4.3)

```bash
# Any lane can verify this skill refuses correctly:
uv run python -m pytest tests/unit/test_create_plan_refusal.py -v
# Expected: all tests pass (one per refusal condition R1-R4 plus happy path)
```

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

**Codified (Packet C-Exec, Primitive C Phase 0).** The refusal logic
is enforced by `scripts/internal/create_plan_refusal.py` and exercised
by `tests/unit/test_create_plan_refusal.py`. Any lane invoking this
skill MUST run the refusal evaluator before writing the plan file;
failure to do so is a process violation (caught at PR time by
`review_driver.py` V7 precheck in the steady state).

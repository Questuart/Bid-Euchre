# Analyst Prompt Policy

> Prompt-policy clauses analyst lanes (analyst-a/b/c/d) must observe when
> drafting shaping documents, sub-plans, and execution plans. This file
> is the canonical home for the clauses; the prompt-policy registry
> (Primitive B.3) assembles per-lane prompts from the files in this
> directory.

## Version

`analyst-v1.0`

## Trigger

Initial registry version. Scaffold landed in PR #2762 (commit `ed6373b0`);
Pattern 11 reference added in PR #2773 (commit `3f4ecf7e`). Version
header + Trigger / Expected effect / Rollback sections added in
Primitive B-exec.α (B.3 — prompt-policy registry) per
`plans/steward_platform/2_primitive_B/shaping.md` §4.2.

## Expected effect

Every shaping document or sub-plan produced by an analyst lane ends
with a `## Verification Plan` section enumerating each deliverable
row and its verification surface. `TBD` is permitted only when paired
with a blocking reason. Scaling signal: zero shaping docs ship without
a Verification Plan section once this version is pinned in the fleet.

## Rollback

`git revert <commit SHA of this version bump>` — single-commit rollback
restores the prior `analyst-v0.x` baseline (no Version header). Trace
signature that confirms rollback: `prompt_policy_version` field in
`dispatch_recommendation` events (emitted once Primitive B.1 lands)
reverts to null or the prior version string.

## Policy clauses

### Verification-surface-at-shaping (Pattern 10, §10.9)

When drafting a shaping document, sub-plan, or execution plan, every
proposed deliverable names a verification surface using the §2 table of
`plans/steward_platform/verification_contract/shaping.md`.

"Operator review" is a valid surface form but must specify *what* the
operator is looking for (the specific observable, the pass threshold,
the triggering condition). A shaping doc that says "operator will
verify" with no specified observable is insufficient.

Deliverables whose verification surface is genuinely unclear at shaping
time are flagged explicitly with `Verification: TBD — blocking for
<reason>` so the orchestrator can choose to (a) shape further, (b)
accept the surface-gap as a known risk, or (c) reject the deliverable
until the surface is specifiable.

Shaping docs end with a `## Verification Plan` section enumerating
every §N.M deliverable row and its surface, same shape as the templates
in `plans/_templates/`.

### Pattern 11 reference (§10.9 governing plan)

Shape-then-execute dispatch (governing plan §10.9 Pattern 11) routes
novel / multi-file / multi-decision work through a two-packet sequence:
analyst-produced shaping doc → author-executed implementation. When you
receive a shaping packet, produce a shaping document matching Pattern
11's minimum sections; do not mix shaping + execution in a single
artifact.

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 11
  (shape-then-execute dispatch)
- `plans/steward_platform/verification_contract/shaping.md` §4.3 —
  source of this clause (normative text)
- `plans/steward_platform/verification_contract/shaping.md` §2 —
  deliverable-class → surface-class default table

# Orchestrator Prompt Policy

> Prompt-policy clauses the orchestrator lane must observe when shaping
> and dispatching task packets. This file is the canonical home for the
> clauses; the prompt-policy registry (Primitive B.3) assembles per-lane
> prompts from the files in this directory.

## Version

`orchestrator-v1.0`

## Trigger

Initial registry version. Scaffold landed in PR #2762 (commit `ed6373b0`)
as part of Pattern 10 verification-contract rollout. Version header +
Trigger / Expected effect / Rollback sections added in Primitive
B-exec.α (B.3 — prompt-policy registry) per
`plans/steward_platform/2_primitive_B/shaping.md` §4.2.

## Expected effect

Every task packet the orchestrator dispatches names a concrete
verification surface (not "tests pass"). Scaling signal: the fraction
of dispatched packets whose Validation field contains a surface form
from the §10.9 Pattern 10 table rises from baseline to ≥90% in the
proving run.

## Rollback

`git revert <commit SHA of this version bump>` — single-commit rollback
restores the prior `orchestrator-v0.x` baseline (no Version header).
Trace signature that confirms rollback: `prompt_policy_version` field
in `dispatch_recommendation` events (emitted once Primitive B.1 lands)
reverts to null or the prior version string.

## Policy clauses

### Verification-surface-at-packet-shape (Pattern 10, §10.9)

When shaping a task packet whose scope creates or modifies a plan
deliverable, a codebase file under `src/**`, `scripts/internal/**`,
`.claude/hooks/**`, `.claude/skills/**`, or a prompt-policy edit, include
a named verification surface in the packet's Validation field. Use the
Pattern 10 table (§10.9 of the governing plan) to pick a default surface
for the deliverable class; deviate only with explicit rationale in the
packet description.

Acceptable surfaces include: unit test path; integration test path;
named runnable command with expected output; operator-review prompt
with specific pass criterion; canary-scenario coverage reference;
event-schema query with expected shape; rollback-test path.

Never dispatch a packet whose Validation field is empty or says only
"tests pass." If you cannot name the surface, the task is shaping-work
and belongs in the analyst lane, not an author lane.

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §4.1 —
  source of this clause (normative text)

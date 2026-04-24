# Common Prompt Policy (ops + review)

> Prompt-policy clauses ops and review lanes observe when monitoring
> PRs, packets, and event streams. Less load-bearing than the
> orchestrator/author/analyst clauses but included for completeness.

## Version

`common-v1.0`

## Trigger

Initial registry version. Scaffold landed in PR #2762 (commit `ed6373b0`)
as part of Pattern 10 verification-contract rollout. Version header +
Trigger / Expected effect / Rollback sections added in Primitive
B-exec.α (B.3 — prompt-policy registry) per
`plans/steward_platform/2_primitive_B/shaping.md` §4.2.

## Expected effect

Ops and review lanes flag verification-surface gaps in PRs / packets /
event streams with the same severity they apply to rollback-path gaps
(Pattern 7) or emission gaps (Pattern 8). Observable signal: the
number of `surface_gap` triage notes filed rises proportionally to
the number of packets dispatched without a named surface (baseline:
both zero; target: both non-zero and tracked together).

## Rollback

`git revert <commit SHA of this version bump>` — single-commit rollback
restores the prior `common-v0.x` baseline (no Version header). Trace
signature that confirms rollback: `prompt_policy_version` field in
`dispatch_recommendation` events (emitted once Primitive B.1 lands)
reverts to null or the prior version string.

## Policy clauses

### Verification-surface-awareness (Pattern 10 supplementary)

When observing a PR, packet, or event stream, surface
verification-surface gaps explicitly. Missing or hand-wavy surfaces
are triage-worthy signals on par with missing rollback paths
(Pattern 7) or missing emission (Pattern 8).

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §4.4 —
  source of this clause (normative text)

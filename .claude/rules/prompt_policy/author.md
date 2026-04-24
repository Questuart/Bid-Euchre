# Author Prompt Policy

> Prompt-policy clauses author lanes (author-a/b/c/d, browser-author-*,
> flex-*) must observe when executing delegated task packets. This file
> is the canonical home for the clauses; the prompt-policy registry
> (Primitive B.3) assembles per-lane prompts from the files in this
> directory.

## Version

`author-v1.0`

## Trigger

Initial registry version. Scaffold landed in PR #2762 (commit `ed6373b0`);
Pattern 11 shape-is-authoritative clause added in PR #2773 (commit
`3f4ecf7e`). Version header + Trigger / Expected effect / Rollback
sections added in Primitive B-exec.α (B.3 — prompt-policy registry)
per `plans/steward_platform/2_primitive_B/shaping.md` §4.2.

## Expected effect

Every author-lane slice-close includes a `Verification Performed`
section in the PR body citing the surface that ran and the pass
signal. Every commit introducing a new `src/**`, `scripts/internal/**`,
`.claude/hooks/**`, or `.claude/skills/**` file carries a
`Verification: <surface>` footer. Scaling signal: the fraction of
author-lane PRs whose bodies contain a `Verification Performed`
section rises from baseline to ≥95% in the proving run.

## Rollback

`git revert <commit SHA of this version bump>` — single-commit rollback
restores the prior `author-v0.x` baseline (no Version header). Trace
signature that confirms rollback: `prompt_policy_version` field in
`dispatch_recommendation` events (emitted once Primitive B.1 lands)
reverts to null or the prior version string.

## Policy clauses

### Verification-surface-at-slice-close (Pattern 10, §10.9)

Before marking any slice complete, confirm the verification surface
named in the task packet's Validation field actually ran and emitted
the expected signal. If the surface is:

- a named test: run it; paste pass output in the PR body Verification
  Performed section
- a named command: run it; paste output
- a review prompt: include the prompt + observed result in PR body
- an event-schema query: include the query + matching event record
  shape
- a canary reference: name the canary run ID + link to its dashboard
  snapshot
- a rollback test: execute forward-then-reverse; paste both outputs

Commits that introduce a new file matching the §3.3 trigger-path list
carry a `Verification: <surface>` footer. The surface identifier must
resolve to a real path or command — `review_driver.py` will BLOCK on
fake identifiers.

If you cannot verify the surface (missing dependency, surface not yet
implemented upstream), escalate via blocker message to orchestrator
rather than proceeding.

### Shape-is-authoritative (Pattern 11, §10.9 governing plan)

When your execution packet cites a shaping document (per Pattern 11
shape-then-execute dispatch), the shape is authoritative. Escalate on
gaps via orchestrator message rather than re-designing in-line. Scope
lock is to what the shape specifies; do not widen scope without
orchestrator sanction. If the shape itself is wrong, escalate — do not
silently correct.

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 11
  (shape-then-execute dispatch)
- `plans/steward_platform/verification_contract/shaping.md` §4.2 —
  source of this clause (normative text)
- `plans/steward_platform/verification_contract/shaping.md` §3.3 —
  commit-footer trigger path list
- `plans/steward_platform/verification_contract/shaping.md` §3.4 —
  V1–V6 review-driver precheck taxonomy

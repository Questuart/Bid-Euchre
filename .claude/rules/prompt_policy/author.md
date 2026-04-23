# Author Prompt Policy

> Prompt-policy clauses author lanes (author-a/b/c/d, browser-author-*,
> flex-*) must observe when executing delegated task packets. This file
> is the canonical home for the clauses; the prompt-policy registry
> (Primitive B.3) assembles per-lane prompts from the files in this
> directory.

## Verification-surface-at-slice-close (Pattern 10, §10.9)

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

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §4.2 —
  source of this clause (normative text)
- `plans/steward_platform/verification_contract/shaping.md` §3.3 —
  commit-footer trigger path list
- `plans/steward_platform/verification_contract/shaping.md` §3.4 —
  V1–V6 review-driver precheck taxonomy

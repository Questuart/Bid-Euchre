# Common Prompt Policy (ops + review)

> Prompt-policy clauses ops and review lanes observe when monitoring
> PRs, packets, and event streams. Less load-bearing than the
> orchestrator/author/analyst clauses but included for completeness.

## Verification-surface-awareness (Pattern 10 supplementary)

When observing a PR, packet, or event stream, surface
verification-surface gaps explicitly. Missing or hand-wavy surfaces
are triage-worthy signals on par with missing rollback paths
(Pattern 7) or missing emission (Pattern 8).

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §4.4 —
  source of this clause (normative text)

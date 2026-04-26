# Common Prompt Policy (ops + review)

> Prompt-policy clauses ops and review lanes observe when monitoring
> PRs, packets, and event streams. Less load-bearing than the
> orchestrator/author/analyst clauses but included for completeness.

## Version

`common-v1.1`

## Trigger

v1.0 — initial registry version. Scaffold landed in PR #2762 (commit
`ed6373b0`) as part of Pattern 10 verification-contract rollout. Version
header + Trigger / Expected effect / Rollback sections added in Primitive
B-exec.α (B.3 — prompt-policy registry) per
`plans/steward_platform/2_primitive_B/shaping.md` §4.2.

v1.1 — Operator-facing-timestamps clause added (Fixes #2807). Ops and
review lanes display times as `HH:MM PT` or `YYYY-MM-DD HH:MM PT` in
chat narration, status comments, and dashboard summaries while
machine-facing data (events, logs, commits) stays UTC. Conversion
happens at the presentation layer via
`bid_euchre.ops.time_util.fmt_operator`.

## Expected effect

v1.0 effect — ops and review lanes flag verification-surface gaps in
PRs / packets / event streams with the same severity they apply to
rollback-path gaps (Pattern 7) or emission gaps (Pattern 8). Observable
signal: the number of `surface_gap` triage notes filed rises
proportionally to the number of packets dispatched without a named
surface (baseline: both zero; target: both non-zero and tracked
together).

v1.1 effect — operator-visible timestamps surfaced by ops or review
lanes (status descriptions, supervisor alerts, dashboard render output)
match `\d{4}-\d{2}-\d{2} \d{2}:\d{2} PT` or `\d{2}:\d{2} PT`. Machine-
facing event payloads continue to emit UTC ISO-Z.

## Rollback

v1.0 rollback — `git revert <commit SHA of v1.0 bump>` restores the
prior `common-v0.x` baseline (no Version header). Trace signature that
confirms rollback: `prompt_policy_version` field in
`dispatch_recommendation` events (emitted once Primitive B.1 lands)
reverts to null or the prior version string.

v1.1 rollback — `git revert <commit SHA of this v1.1 bump>` restores
`common-v1.0`. Trace signature: ops/review lane operator-facing
surfaces regress to UTC ISO-Z display; the
`Operator-facing timestamps in Pacific Time` clause below no longer
applies.

## Policy clauses

### Verification-surface-awareness (Pattern 10 supplementary)

When observing a PR, packet, or event stream, surface
verification-surface gaps explicitly. Missing or hand-wavy surfaces
are triage-worthy signals on par with missing rollback paths
(Pattern 7) or missing emission (Pattern 8).

### Operator-facing timestamps in Pacific Time

Operator-facing timestamps use Pacific Time. Convert UTC at the
presentation layer. Machine-facing data (events, logs, commits) stays
UTC. Orchestrator chat narration, dashboards, and Telegram alerts
display times as `HH:MM PT` or `YYYY-MM-DD HH:MM PT`.

Use `bid_euchre.ops.time_util.fmt_operator` (or the convenience
`fmt_operator_iso` for stored ISO-8601 strings) at every operator
surface. Machine-facing emitters (event payloads, message bus, audit
trail, git/GitHub) continue to emit UTC ISO-Z.

## References

- `plans/steward_platform/governing_plan.md` §10.9 — Pattern 10
- `plans/steward_platform/verification_contract/shaping.md` §4.4 —
  source of this clause (normative text)

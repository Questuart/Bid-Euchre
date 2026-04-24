# Orchestrator Prompt Policy

> Prompt-policy clauses the orchestrator lane must observe when shaping
> and dispatching task packets. This file is the canonical home for the
> clauses; the prompt-policy registry (Primitive B.3) assembles per-lane
> prompts from the files in this directory.

## Version

`orchestrator-v1.1`

## Trigger

v1.0 — initial registry version. Scaffold landed in PR #2762
(commit `ed6373b0`) as part of Pattern 10 verification-contract rollout.
Version header + Trigger / Expected effect / Rollback sections added in
Primitive B-exec.α (B.3 — prompt-policy registry) per
`plans/steward_platform/2_primitive_B/shaping.md` §4.2.

v1.1 — Deterministic ops-signal-bridge clause added (Fixes #2806). The
ops lane now produces a single authoritative brief covering every
observation the orchestrator cron needs (expanded `supervisor_alert`
findings, open PRs, merged PRs since last read, pending inbox,
dispatched packets, TUI task status). The orchestrator consumes this
via `/read-ops-brief` rather than reinventing subsets via ad-hoc shell
(`gh pr list`, `ops.py task list`, `ops.py inbox`). Replaces the
coarse `ack-all` pattern that was dropping the monitor's findings
wholesale.

## Expected effect

v1.0 effect — every task packet the orchestrator dispatches names a
concrete verification surface (not "tests pass"). Scaling signal: the
fraction of dispatched packets whose Validation field contains a
surface form from the §10.9 Pattern 10 table rises from baseline to
≥90% in the proving run.

v1.1 effect — every orchestrator cron fire begins with a single
`/read-ops-brief` invocation; zero cron fires invoke `gh pr list`,
`ops.py task list`, or `ops.py inbox` directly. Scaling signal:
`recent_ops_alerts[*].findings[]` from the brief JSON are routed
through the skill's category table and acked **after** routing (not
coarsely batch-acked), so monitor findings are no longer dropped.

## Rollback

v1.0 rollback — `git revert <commit SHA of v1.0 bump>` restores the
prior `orchestrator-v0.x` baseline (no Version header). Trace
signature: `prompt_policy_version` field in `dispatch_recommendation`
events (emitted once Primitive B.1 lands) reverts to null or the prior
version string.

v1.1 rollback — `git revert <commit SHA of this v1.1 bump>` restores
`orchestrator-v1.0`. Trace signature: orchestrator cron fires stop
beginning with `/read-ops-brief` and resume issuing `gh pr list` /
`ops.py task list` / `ops.py inbox` directly; the `Cron-fire-through-brief`
clause below no longer applies. The CLI subcommand, builder module, and
skill remain committed (they are not load-bearing without the policy
mandate); a deeper rollback would additionally revert the #2806 PR.

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

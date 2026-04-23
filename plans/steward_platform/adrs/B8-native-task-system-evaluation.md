# ADR B8 — Native Task/Dependency System Evaluation

**Status:** SEEDED (draft 8); filing at Phase 0 kickoff
**Primitive:** B (dispatch/skill/prompt-policy) sub-deliverable B.8
**Supersedes:** none
**Seed source:** `plans/steward_platform/plugin_source_evaluation.md` §3 + §6.2 (analyst-a, 2026-04-23)

---

## Context

Claude Code's `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` (enabled via settings.json or environment flag) provides a team-lead + teammates + shared task list + mailbox architecture. Draft 8 B.8 commits to an ADR evaluating which parts of steward's `ops/task_queue.py` + `ops/worker_pool.py` + `ops/scheduler.py` contract are subsumed by native substrate.

Key source-derived observations from analyst-a (reading docs at `code.claude.com/docs/en/agent-teams` and Task-tool / TeammateTool APIs):

- **Native tasks are session-ephemeral.** Teammates die with the lead session; no restart/resumption per the experimental limitations.
- **No `scope_declared` field.** Native tasks carry subject / description / optional activeForm / metadata dict. No equivalent of steward's scope-lock (declared file patterns that must not be exceeded).
- **No domain routing.** No platform vs. browser-game pool concept.
- **No lane affinity.** No equivalent of "author-a stays author-a across sessions" — teammates are allocated ad-hoc from a pool.
- **No routing metadata.** No `task_type` / `complexity_estimate` / `model_hint` / `effort_hint` on native task objects (which drive steward's adaptive dispatch advisor).
- **TeammateTool + SendMessage/broadcast** provide intra-session mailbox semantics; they do not carry durable cross-restart guarantees.

Lifecycle hooks (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) are already in draft 8 Tier S Primitive A scope independent of this ADR.

## Decision

**Keep `ops/task_queue.py`, `ops/worker_pool.py`, `ops/scheduler.py`, and the orchestrator → author-lane nudge protocol bespoke.** Native Agent Teams substrate does not subsume steward's durable packet semantics.

**Adopt the following from Agent Teams as supplemental (not replacement):**

1. **Lifecycle hooks** (`TeammateIdle`, `TaskCreated`, `TaskCompleted`) emitted into `ops/events.py` schema — already covered by Tier S absorption in Primitive A.
2. **`SendMessage` + `broadcast`** as a supplemental intra-session channel for orchestrator ↔ lane coordination pings. Steward's message bus (`ops/message_bus.py`) remains authoritative for durable / cross-restart semantics.

**Do not enable `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` on steward lanes by default.** Retainable operator decision: per-lane experimentation is tolerated; it does not compete with the bus.

## Consequences

- Steward's task contract (scope-locked packets + domain routing + lane affinity + routing metadata) survives unchanged as the canonical dispatch model.
- Scope-lock discipline remains orthogonal to any native task primitive, preserving its value independent of substrate evolution.
- §9.7 first-class IDs remain expressible on steward packets; `agent_id` / `agent_type` from Agent Teams hooks can be correlated via a lookup table if per-lane experimentation happens.
- Phase 3 re-evaluation trigger: if `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` graduates from experimental AND native tasks gain scope/metadata/durability fields, revisit this ADR.

## Alternatives considered

1. **Adopt Agent Teams as packet-dispatch substrate.** Rejected. Would require building 6 extensions atop native substrate — scope field, domain routing, lane affinity, durable cross-restart state, routing metadata (4 fields), message-bus bridge. More work than keeping bespoke.
2. **Replace message bus with `SendMessage`.** Rejected. Session-ephemeral; loses cross-restart durability that steward's orchestrator → author-lane protocol depends on.
3. **Pilot on a single flex lane for observation.** Deferred to operator per analyst-a's open question. Source-level evaluation is sufficient to close B.8 without empirical data.

## Open questions

1. Pilot `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` on one flex lane to observe empirical behavior (sharpens the "graduates from experimental" Phase 3 re-evaluation trigger)?

## Source evidence

- Docs read: `https://code.claude.com/docs/en/agent-teams`
- Task tool / TeammateTool API references (accessible via Claude Code docs + `claude --help` subcommand inspection)
- Evaluation artifact: `plans/steward_platform/plugin_source_evaluation.md` §3 (analyst-a, 2026-04-23)

## Phase 2 Decision Inputs

**Portability readiness:** no change (steward's dispatch model remains the portable seam).
**Meta-layer need:** no change.
**Kill signal for primitive(s) named:** no.
**Re-evaluation needed in Phase 3:** yes, soft trigger if Agent Teams graduates from experimental AND native task schema gains scope/metadata/durability fields. Recommended evaluation window: 6 months post Phase 2 close or when upstream change lands, whichever sooner.
**Surprise finding:** Agent Teams' "persistent task system" framing is misleading — native tasks are session-ephemeral with no restart. Reinforces the ADR discipline requiring source-level verification (Pattern 9 load-bearing-ownership lint extended to Tier S candidates).
**Disposition:** open (pending Phase 0 kickoff filing)

# Agentic Orchestration Platform — Amendments

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Last updated:** 2026-03-23 (A8 remote-ops v1 shaping)

---

## A1 — Platform-1 entry criteria and filesystem boundary (2026-03-20)

**PR:** #1090 (docs: gate Platform-1 on review-surface stabilization)

**What changed:**
1. **Platform-1 entry criteria** — Added two new entry criteria:
   - Review-surface stability (reviewing-changes advisory status settled,
     claude-review visible without poisoning CI, Codex Cloud behavior recorded)
   - Repo-bounded filesystem access (default deny for external paths)
2. **Filesystem access boundary** — New subsection under Security/Safety
   defining repo-bounded filesystem access as the default, with explicit
   exception + audit path for outside-repo access.
3. **Platform-12 rewrite** — "Interim advisory CI path" renamed to "Interim
   Codex overlay path." Constraints updated to reflect that Codex Cloud
   delivers findings as PR issue comments (not checks/statuses), and that
   the comment-ingestion bridge is the integration mechanism.

**Rationale:** Codex Cloud proving-run findings (2026-03-20) revealed that
Codex Cloud does not produce check runs, commit statuses, or PR review
objects. The filesystem access boundary was added based on operational
experience with autonomous agents accessing paths outside the repo tree.

---

## A2 — Front-load primary PR review architecture into Platform-3 (2026-03-20)

**PR:** #1180 (docs: front-load primary PR review architecture)

**What changed:**
1. **Platform-3 scope expanded** — Platform-3 now owns the primary PR review
   architecture: durable review request/verdict state (extending the
   `ReviewRequest`/`ReviewVerdict` models from #1176) and a merge-safety gate
   driven by verdict state rather than hook-coupled subprocess parsing.
   Platform-3 renamed from "Communication Bus V1" to "Communication Bus V1
   And Primary PR Review Substrate." A new sub-slice `Platform-3d` covers
   review request/verdict state and the merge-safety gate.
2. **Platform-12 reframed** — Platform-12 (Cross-Model Review And Maintenance)
   is now explicitly an extension of Platform-3's review substrate. Second-model
   findings are recorded as verdicts in the Platform-3 review bus, not as a
   separate review truth model. Platform-12 does not redefine the review
   architecture; it adds cross-model execution as a consumer.
3. **SendMessage deferral** — `SendMessage`-style lane-to-lane delivery is
   explicitly deferred as a convenience layer on top of the durable review
   bus. It is not the source of review truth.
4. **Batch B pass gate updated** — Added a review-substrate acceptance
   criterion: one real PR review request stored durably as a `ReviewRequest`,
   receiving a `ReviewVerdict`, driving merge-safety state without subprocess
   parsing.
5. **Instrumentation** — Platform-3 instrumentation gains review request →
   verdict latency and merge-safety gate accuracy metrics.

**Rationale:** The review substrate should ship early so all downstream slices
(dashboard, supervisor, cross-model review) build on durable review state from
the start. Deferring the primary review architecture to Platform-12 would
force interim work to rely on hook-coupled subprocess parsing and transient
terminal output — the exact failure mode the platform is designed to replace.

---

## A3 — Agent frontmatter hardening and lane-boundary enforcement (2026-03-22)

**PR:** pending follow-up

**What changed:**
1. **Agent definitions recognized as platform substrate** — The governing plan
   now treats `.claude/agents/` as more than prompt text. Frontmatter
   capabilities such as `tools:`, `model:`, and later lane-scoped `memory:`
   are explicit platform inputs rather than incidental implementation detail.
2. **Structural role-boundary note added** — Future worker-pool and service-lane
   design should prefer enforced capability boundaries where the agent runtime
   supports them, instead of relying only on prompt wording.
3. **Future-slice mapping captured** — Platform-7 now carries the note that
   worker classes should reuse agent-profile tool restrictions; Platform-11
   carries the note that any memory layer should remain lane-scoped; and
   Platform-12 carries the note that per-lane `model:` selection is a service-
   lane configuration concern rather than a new review truth model.
4. **Narrow follow-up path allowed** — A small post-Batch-C hardening PR may add
   agent-frontmatter restrictions and low-risk model annotations without
   reopening Batch C acceptance or changing task/message/review runtime truth.

**Rationale:** Platform-5 shipped canonical prompts, but non-author role
boundaries are still mostly honor-system. The native agent feature set already
supports stronger structure than prompts alone. Capturing that now prevents
Platform-7, Platform-11, and Platform-12 from inventing a parallel capability
model later, while keeping the current runtime architecture unchanged.

---

## A4 — Agent teams terminology and boundary (2026-03-22)

**PR:** pending follow-up

**What changed:**
1. **Terminology correction** — The plan uses "agent swarm" informally in some
   contexts. The correct Claude Code term is "agent teams" (experimental,
   enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Plan text should use
   "agent teams" where referring to Claude's multi-agent display/communication
   feature.
2. **Subagent resume capability noted** — Stopped subagents can be resumed via
   `SendMessage` using the agent ID. This is not team-exclusive. The platform's
   current subprocess dispatch model can leverage resume without requiring full
   team mode.
3. **Boundary clarification** — Agent teams provide direct teammate messaging
   and split-pane display. These are a **convenience execution layer**, not a
   coordination truth model. The platform must not move durable coordination
   (task packets, message bus, review state, dashboard state) into
   team-session-scoped communication. Repo-owned state remains authoritative
   regardless of whether execution uses subagents, agent teams, or manual tmux
   panes.

**Rationale:** Platform-7 (worker pool manager) will introduce open-on-demand
pane dispatch. Agent teams may be a useful implementation mechanism for that,
but the coordination contract stays repo-owned. This amendment prevents future
scope creep where team messaging replaces the durable bus.

---

## A5 — Platform-8 channel preflight, safety gates, and operator fallback (2026-03-22)

**PR:** pending follow-up

**What changed:**
1. **Platform-8 preflight made explicit** — The governing plan now calls out
   the Claude Channels prerequisites that can block the slice before design
   proving begins: compatible Claude Code version, claude.ai login, channel
   enablement, `--channels` startup, and plugin/runtime dependencies.
2. **Security boundary tightened** — Platform-8 now requires pairing/allowlist
   handling for two-way channels and keeps permission relay disabled by default
   until a later bounded-command proving step explicitly enables it.
3. **Fallback adapter clarified** — The plan now distinguishes:
   - a **channel fallback adapter** that still satisfies Platform-8
     (for example fakechat or a minimal repo-owned webhook channel server), and
   - an **operator-side SSH/Termius fallback** that helps with debugging and
     recovery but does not itself satisfy the remote-channel slice.
4. **Operator-side runbook recorded** — The plan now includes a brief
   post-Platform-8 SSH/Termius walkthrough and smoke test for recovering access
   to the steward machine when the Telegram path fails.

**Rationale:** The original Platform-8 definition captured the product goal but
not the operational bootstrap, sender-gating, or debugging realities surfaced
by Claude's official Channels docs. Capturing these details now makes the slice
more likely to prove cleanly without confusing channel transport failure,
operator access failure, and architecture failure.

---

## A6 — BD-004 staged delivery-adapter roadmap (2026-03-22)

**PR:** pending follow-up

**What changed:**
1. **Batch D gate aligned with the real Phase 3 blocker** -- The governing and
   Phase 3 plans now state explicitly that, for the shipped tmux-first steward
   layout, a dispatched task must be able to land in the target live author
   session through a repo-owned delivery adapter.
2. **`v1` delivery path made explicit** -- Phase 3 closes BD-004 with the
   narrowest adapter that fits the current runtime: durable task/message state
   plus a packet-specific tmux pane nudge into the already-running lane session.
3. **`v2` upgrade path recorded** -- Platform-8 may later replace that pane
   nudge with a Claude Channels sidecar that watches durable state and pushes
   lane-local events into the running session, while keeping repo-owned state as
   truth.
4. **`v3` transport upgrade recorded** -- If `cmux` workspace/surface metadata
   becomes live and stable, the delivery adapter may later move from tmux
   targeting to `cmux` surface targeting without changing the durable contract.

**Rationale:** The discussion around BD-004 established a three-stage answer:
close the current gate cheaply with the existing tmux session model, preserve a
clean upgrade path to Claude Channels once remote-channel prerequisites exist,
and treat `cmux` as a later transport/presentation upgrade rather than as
control-plane truth. Recording the full ladder now prevents future slices from
re-litigating the same architectural boundary.

---

## A7 — Phase 3 closeout and dual-domain transition entry (2026-03-22)

**PR:** SP-3-04 closeout PR

**What changed:**
1. **Phase 3 durably closed** — All planning state (checkpoints, plan, QA log,
   sub-plan registry, governing plan) reconciled to reflect Phase 3 completion.
   BD-004 marked fixed (PR #1263), BD-001/BD-002/BD-003 marked fixed (PR #1261).
   Platform-7 marked COMPLETE. Batch D pass gate checklist fully checked.
2. **No active numbered phase** — The governing plan checkpoint contract now
   states that no numbered phase is currently active. Phase 4 and Phase 5 are
   both unblocked but not yet entered.
3. **Dual-domain transition entry recorded** — SP-3-05 registered as a proposed
   sub-plan for the dual-domain steward layout transition. This is a bounded
   transition package between Phase 3 and Platform-8, not a new numbered phase.
   It enables concurrent platform and browser-game development.
4. **Next governed action made explicit** — The sequence is: SP-3-05 (layout
   transition), then Phase 4 scope lock. Browser-game work may proceed after
   the transition package is in place.

**Rationale:** Phase 3 runtime work was complete but durable planning state
lagged behind shipped reality. This amendment closes that gap and establishes
the dual-domain layout transition as the next governed action, preventing
future sessions from having to reconstruct intent from chat history.

---

## A8 — Phase 4 thin remote-ops v1 and away-from-desk velocity (2026-03-23)

**PR:** this PR (SP-3-05 closeout + governance landing)

**What changed:**
1. **Scope/goals reframed** — The governing plan now states explicitly that
   away-from-desk operator velocity is part of the Phase 4 value proposition,
   not just a convenience feature.
2. **Thin remote v1 defined** — Phase 4 now assumes a single remote operator,
   treats the remote channel as a thin transport into `orchestrator`, and
   keeps repo-owned runtime state as the only operational truth.
3. **No remote-specific workflow intelligence in v1** — The plan now
   explicitly avoids introducing a separate remote command grammar, classifier,
   or remote-only preview heuristics in the first rollout. Free-form remote
   messages are allowed and follow the existing orchestrator workflow.
4. **Remote flow simplified** — The communication-layer flow now routes
   inbound remote messages to `orchestrator`, which remains the single ingress
   and mediates routing to `ops`, `review`, or worker lanes as needed.
5. **Phase 4 scaffolding added** — Phase 4 now has a concrete `plan.md` and
   `checkpoints.md` outline covering transport, audit trail, alerting,
   queue-moving remote actions, and a first hardening pass.

**Rationale:** For this repo, remote reachability is a direct throughput
multiplier because it reduces idle time while the operator is away from the
desk. The cheapest reliable first version is a dumb transport into the
existing orchestrator workflow, not a smarter remote-only control surface.

# Phase 4 — Remote Channel

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase:** `4_remote_channel`
**Status:** READY FOR ENTRY
**Last updated:** 2026-03-23 by Codex (thin remote-ops v1 outline)

---

## Scope

Phase 4 covers `Platform-8` and `Platform-9`: remote operator transport,
repo-owned remote audit trail, idle-attention alerts, and away-from-desk
queue-moving supervision. The first version assumes one remote operator and
treats the remote channel as a thin transport into `orchestrator`.

## Prerequisites

- Phase 3 (`3_supervision_and_scaling`) is COMPLETE
- SP-3-05 (dual-domain steward layout transition) is COMPLETE (2026-03-23,
  proving run passed)
- Existing repo-owned truth surfaces remain authoritative: lane/session
  registry, message bus, task state/task queue, and review verdict state
- Kill switch / mute path is designed before enabling external channel access
- SP-4-02 (remote-ops preflight hardening) hardens dispatch lifecycle before
  Platform-8 transport work begins
- SP-4-03 (token economy observability) establishes a token-cost baseline
  before remote transport adds a new cost dimension. SP-4-02 and SP-4-03
  are safe to run in parallel (disjoint file scopes).

## Phase Constraints

- Telegram first; Discord is deferred unless later experience justifies it
- Inbound remote messages go to `orchestrator`
- No remote-specific classifier, preview grammar, or separate command language
  in v1
- Free-form remote messages are allowed and follow the same orchestrator
  workflow as local prompts
- Existing repo-owned safeguards remain unchanged: review truth, merge gates,
  filesystem boundary, and destructive-action approvals
- Every inbound and outbound remote exchange must be durably recorded in
  repo-owned state
- The remote layer must not become a second control plane

## Slices

| Slice | Goal | Status | Batch | Depends On |
|-------|------|--------|-------|------------|
| `Platform-8a` | Channel preflight, Telegram transport skeleton, kill/mute/fallback hooks | READY FOR SCOPE LOCK | E | Phase 3, Amendment A5 |
| `Platform-8b` | Repo-owned audit trail for inbound/outbound remote exchanges | READY FOR SCOPE LOCK | E | Platform-3, Platform-8a |
| `Platform-9a` | Idle-attention alerts and remote acknowledgement loop | READY FOR SCOPE LOCK | E | Platform-6, Platform-8b |
| `Platform-9b` | Away-from-desk queue-moving supervision through `orchestrator` | READY FOR SCOPE LOCK | E | Platform-2, Platform-8b, Platform-9a |
| `Platform-9c` | First hardening pass from real remote use | READY FOR SCOPE LOCK | E | Platform-9b |

## Batch E Pass Gate

Before treating Phase 5 as ready, verify Batch E (Platform-8 + Platform-9):

- [ ] Telegram proving run works end-to-end for one remote operator
- [ ] Every inbound and outbound remote exchange is recorded in repo-owned state
- [ ] Kill switch and mute path work without needing desktop intervention
- [ ] At least one alert path is proven with acknowledgement, dedupe, and
  backoff behavior
- [ ] The operator can keep work moving while away from the desk through
  `orchestrator`
- [ ] No remote-only truth, command plane, or author-lane ingress is introduced
- [ ] Existing review, merge, and filesystem safeguards behave the same for
  remote and local requests

## Rollout Order

1. Scope lock and transport preflight
2. Telegram transport plus repo-owned logging
3. Kill switch, mute, and operator fallback
4. Alert / acknowledgement loop
5. Queue-moving remote workflows through `orchestrator`
6. First hardening pass from real use

## High-Value Workflows To Prove

- Ask `orchestrator` for a status summary from the phone
- Receive an idle, blocker, or review-ready alert remotely
- Acknowledge an alert so the system stops repeating it
- Request review for a PR or active task
- Reroute or resume work through `orchestrator`
- Pause retries or escalation churn
- Inspect blocker context without opening the desktop steward session

## Non-Goals

- A special remote-only command language
- Remote-specific preview heuristics or risk classifiers
- Direct remote ingress to author lanes
- Replacing the steward desktop session as the richest operator interface

## Sub-Plans

| ID | Title | Status | File |
|----|-------|--------|------|
| SP-4-01 | Platform-8 scope lock | completed | `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8-scope-lock.md` |
| SP-4-02 | Remote-ops preflight hardening | in_progress | `plans/agent_ops/4_remote_channel/sub/2026-03-23_remote-ops-preflight-hardening.md` |
| SP-4-03 | Token economy observability and dashboard | proposed | `plans/agent_ops/4_remote_channel/sub/2026-03-23_token-economy-observability-and-dashboard.md` |

## Step Sequence

See `plans/agent_ops/4_remote_channel/checkpoints.md` for current step progress. Phase 4 follows the standard
step template from the governing plan: scope lock -> implementation ->
verification -> handoff, repeated per slice.
